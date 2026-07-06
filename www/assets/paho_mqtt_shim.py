"""
Shim Python de paho.mqtt.client per a l'IDE Python al navegador (py-web).

Model B: MQTT.js i el wrapper JS (paho-mqtt.js) viuen DINS el mateix Web
Worker que Pyodide. Aquest mòdul registra `paho.mqtt.client` a sys.modules i
ofereix una capa fina que envolta l'objecte JS `globalThis.paho.mqtt.client.Client`
per donar una API fidel a paho-mqtt de Python:

  - msg.payload arriba com a BYTES (perquè .decode("utf-8") funcioni igual
    que amb el paho real i amb els scripts "universals" Pi/simulador).
  - msg.topic és str; msg.qos i msg.retain també hi són.
  - username_pw_set(usuari, contrasenya) (el wrapper JS no el tenia: aquí es
    guarda i es passa a connect()).
  - Les callbacks (on_connect, on_message, ...) reben com a primer argument
    aquest objecte Python Client, no el JsProxy de sota.

NOMÉS WebSocket segur (wss). El port determina el protocol al wrapper JS:
8084/8081/8000/9002 -> wss, la resta -> ws.

Aquest fitxer s'executa dins un mòdul nou cada execució (estat net).
"""

import js
from pyodide.ffi import create_proxy


class MQTTMessage:
    """Equivalent mínim de paho.mqtt.client.MQTTMessage."""
    __slots__ = ("topic", "payload", "qos", "retain")

    def __init__(self, topic, payload, qos=0, retain=False):
        self.topic = topic        # str
        self.payload = payload    # bytes  (com el paho real)
        self.qos = qos
        self.retain = retain


class Client:
    """Subconjunt de paho.mqtt.client.Client suportat al navegador (wss)."""

    def __init__(self, client_id=None, *args, **kwargs):
        # Comprovació clara si falten els fitxers vendor (mqtt.min.js / paho-mqtt.js)
        if not hasattr(js, "paho") or not hasattr(js.paho, "mqtt"):
            raise RuntimeError(
                "MQTT no disponible: falten els fitxers vendor.\n"
                "Comprova que existeixen:\n"
                "  www/vendor/mqtt/5.15.1/mqtt.min.js\n"
                "  www/vendor/paho/1.0/paho-mqtt.js"
            )

        self._js = js.paho.mqtt.client.Client(client_id)
        self._username = None
        self._password = None
        self._userdata = None

        # Callbacks estil paho (les posa l'usuari com a atributs)
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None
        self.on_publish = None
        self.on_subscribe = None
        self.on_unsubscribe = None

        # Mantenim referències als proxies perquè no els reculli el GC.
        self._proxies = []
        self._install_bridges()

    # ── Traducció JS -> Python de les callbacks ──────────────────────────
    def _install_bridges(self):
        def _on_connect(jsclient, juserdata, jflags, rc):
            if self.on_connect:
                flags = {}
                try:
                    flags["session_present"] = bool(jflags.session_present)
                except Exception:
                    pass
                self.on_connect(self, self._userdata, flags, int(rc))

        def _on_message(jsclient, juserdata, jmsg):
            if self.on_message:
                topic = str(jmsg.topic)
                payload = str(jmsg.payload).encode("utf-8")   # -> bytes
                qos = int(jmsg.qos or 0)
                retain = bool(jmsg.retain)
                self.on_message(self, self._userdata, MQTTMessage(topic, payload, qos, retain))

        def _on_disconnect(jsclient, juserdata, rc):
            if self.on_disconnect:
                self.on_disconnect(self, self._userdata, int(rc))

        def _on_publish(jsclient, juserdata, topic):
            if self.on_publish:
                # paho real passa (client, userdata, mid); aquí mid=0
                self.on_publish(self, self._userdata, 0)

        def _on_subscribe(jsclient, juserdata, topic, granted):
            if self.on_subscribe:
                # paho real passa (client, userdata, mid, granted_qos)
                self.on_subscribe(self, self._userdata, 0, (0,))

        def _on_unsubscribe(jsclient, juserdata, topic):
            if self.on_unsubscribe:
                self.on_unsubscribe(self, self._userdata, 0)

        for name, fn in (
            ("on_connect", _on_connect),
            ("on_message", _on_message),
            ("on_disconnect", _on_disconnect),
            ("on_publish", _on_publish),
            ("on_subscribe", _on_subscribe),
            ("on_unsubscribe", _on_unsubscribe),
        ):
            p = create_proxy(fn)
            self._proxies.append(p)
            setattr(self._js, name, p)

    # ── API paho ─────────────────────────────────────────────────────────
    def username_pw_set(self, username, password=None):
        self._username = username
        self._password = password

    def user_data_set(self, userdata):
        self._userdata = userdata

    def connect(self, host, port=8084, keepalive=60, bind_address=""):
        opts = js.Object.new()
        if self._username is not None:
            opts.username = self._username
        if self._password is not None:
            opts.password = self._password
        self._js.connect(host, port, keepalive, opts)

    def publish(self, topic, payload=None, qos=0, retain=False):
        if isinstance(payload, (bytes, bytearray)):
            payload = bytes(payload).decode("utf-8", "replace")
        elif payload is None:
            payload = ""
        elif not isinstance(payload, str):
            payload = str(payload)
        self._js.publish(topic, payload, qos, retain)

    def subscribe(self, topic, qos=0):
        self._js.subscribe(topic, qos)

    def unsubscribe(self, topic):
        self._js.unsubscribe(topic)

    def loop_start(self):
        self._js.loop_start()

    def loop_stop(self, force=False):
        self._js.loop_stop()

    def loop_forever(self, *args, **kwargs):
        # En el model asíncron del navegador, loop_forever() bloquejaria el
        # bucle d'esdeveniments i NO es rebria res. Avisem clarament.
        raise RuntimeError(
            "Al navegador, loop_forever() no funciona (bloquejaria el bucle "
            "d'esdeveniments). Fes servir loop_start() i mantingues el "
            "programa viu amb 'while True: await asyncio.sleep(1)' "
            "(o, si combines amb una finestra tkinter: "
            "'while not aturat: finestra.update(); await asyncio.sleep(0.05)' "
            "en lloc de finestra.mainloop())."
        )

    def disconnect(self):
        self._js.disconnect(False)

    def is_connected(self):
        return bool(self._js.is_connected())


# Constants/àlies habituals de paho (per si algun script els fa servir)
MQTTv311 = 4
MQTTv5 = 5


def connack_string(rc):
    return {
        0: "Connection Accepted",
        1: "Connection Refused: unacceptable protocol version",
        2: "Connection Refused: identifier rejected",
        3: "Connection Refused: broker unavailable",
        4: "Connection Refused: bad user name or password",
        5: "Connection Refused: not authorised",
    }.get(int(rc), "Unknown")

