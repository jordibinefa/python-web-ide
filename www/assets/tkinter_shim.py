# -*- coding: utf-8 -*-
"""
Shim minim de tkinter per a l'IDE Python en navegador (Pyodide + Web Worker).

Cobreix les fases 1-8 del pla:
    Tk, Label, Entry, Button, messagebox.showinfo / askokcancel,
    Radiobutton, IntVar, StringVar, Listbox, Checkbutton, PhotoImage
amb pack() / grid() / place().

DISSENY
-------
Cap operacio toca el DOM des d'aqui (el worker no hi te acces). Cada operacio
es tradueix en una crida sincrona __tk_call__(op, payload_json) cap al fil
principal, que es l'equivalent generic del __js_input__ que ja existeix per a
input(): bloqueja NOMES el worker (Atomics.wait), mai el navegador.

__tk_call__ l'injecta el worker.js. Aquest fitxer s'executa dins un modul nou
(types.ModuleType('tkinter')) que es registra directament a
sys.modules['tkinter'] abans de cada execucio — no es escriu mai al FS ni
passa per sys.path, perque Pyodide intercepta 'import tkinter' amb un finder
propi a sys.meta_path que sempre guanya a sys.path.

Tk.mainloop() es BLOQUEJANT (Atomics.wait): mentre esta actiu, el fil del
worker no pot fer res mes — inclos processar MQTT.js, que viu al mateix
worker. Per a programes que combinin una finestra amb codi asincron
(MQTT, temporitzadors, ...), fer servir Tk.update() en lloc de mainloop():
processa els esdeveniments pendents i torna IMMEDIATAMENT, sense bloquejar
mai — patro real de tkinter, tambe valid fora del navegador:
    while not aturat:
        finestra.update()
        await asyncio.sleep(0.05)
update() es un pont NO bloquejant (__tk_poll_events__, sense Atomics/SAB):
els clics arriben per una cua omplerta via postMessage normal des del fil
principal (tkFireEvent), independent del mecanisme de mainloop().

LIMITACIONS CONEGUDES (v0, deliberades)
----------------------------------------
- No hi ha Canvas ni Toplevel (no calen per al currículum actual).
- grid() posiciona per columna/fila real (CSS Grid amb auto-placement), amb
  columnspan/rowspan i sticky basics (n/s/e/w i combinacions). No suporta
  columnconfigure()/rowconfigure() (pesos de redimensionament).
- pack() suporta side=TOP/BOTTOM/LEFT/RIGHT, padx, pady, fill basic.
- bind() generic no esta implementat; nomes el cas concret command= del Button.
- PhotoImage.width()/height() retornen 0 (mesurar-les requeriria decodificar
  la imatge de forma asincrona, incompatible amb el pont sincron actual).
  No es un problema per als exercicis del manual, que no en depenen.
- No hi ha gestio d'excepcions especialment amigable: un error de l'alumne
  (p.ex. ValueError de float()) sortira per stderr com qualsevol altre.
"""
import json as _json    # alias per no filtrar 'json' amb 'from tkinter import *'
import base64 as _b64   # idem, per a PhotoImage(file=...)

_next_id = [1]          # l'id 0 esta reservat per a l'arrel (Tk)
_callbacks = {}         # id widget -> funcio Python (command=)
_destroyed_roots = set()


def _new_id():
    _next_id[0] += 1
    return _next_id[0]


def _call(op, **payload):
    """RPC sincron cap al fil principal. payload es serialitza a JSON
    perque mai calgui passar un PyProxy/dict a traves del Worker boundary."""
    raw = __tk_call__(op, _json.dumps(payload, ensure_ascii=False))
    if not raw:
        return None
    return _json.loads(raw)


def _serialize_opts(opts):
    """Converteix valors no serialitzables directament per JSON (ara per ara
    nomes PhotoImage) en una referencia {'__photoimage__': id} que el
    renderer del fil principal sap interpretar."""
    out = {}
    for k, v in opts.items():
        if isinstance(v, PhotoImage):
            out[k] = {"__photoimage__": v.id}
        else:
            out[k] = v
    return out


class _Widget:
    """Base de tots els widgets. master=None vol dir 'arrel' (nomes Tk)."""

    def __init__(self, master=None, **kwargs):
        self.id = _new_id()
        self.master = master
        master_id = master.id if master is not None else None
        _call("create", id=self.id, type=type(self).__name__,
              master=master_id, opts=_serialize_opts(kwargs))

    # -- configuracio --------------------------------------------------
    def config(self, **kwargs):
        _call("config", id=self.id, opts=_serialize_opts(kwargs))

    configure = config

    def cget(self, key):
        res = _call("cget", id=self.id, key=key)
        return res.get("value") if res else None

    # -- gestors de geometria -------------------------------------------
    def pack(self, **kwargs):
        _call("layout", id=self.id, manager="pack", opts=kwargs)

    def grid(self, **kwargs):
        _call("layout", id=self.id, manager="grid", opts=kwargs)

    def place(self, **kwargs):
        _call("layout", id=self.id, manager="place", opts=kwargs)

    # -- cicle de vida ----------------------------------------------------
    def destroy(self):
        _call("destroy", id=self.id)


class Tk(_Widget):
    """Finestra arrel. Sempre id=0 (nomes en pot haver-hi una en aquest v0)."""

    def __init__(self):
        self.id = 0
        self.master = None
        self._running = False
        _call("create", id=0, type="Tk", master=None, opts={})

    def title(self, text):
        _call("config", id=self.id, opts={"_title": text})

    def geometry(self, spec):
        _call("config", id=self.id, opts={"_geometry": spec})

    def configure(self, **kwargs):
        # bg= a l'arrel es habitual ("ventana_principal.configure(bg='yellow')")
        _call("config", id=self.id, opts=kwargs)

    config = configure

    def destroy(self):
        _destroyed_roots.add(self.id)
        self._running = False
        _call("destroy", id=self.id)

    def mainloop(self):
        self._running = True
        while self._running:
            ev = _call("wait_event")
            if not ev or ev.get("type") == "quit":
                break
            if ev.get("type") == "command":
                cb = _callbacks.get(ev.get("id"))
                if cb is not None:
                    cb()
            if self.id in _destroyed_roots:
                break

    def update(self):
        """Real de tkinter: processa els esdeveniments pendents (clics,
        canvis de Radiobutton/Checkbutton, ...) UN COP i torna immediatament
        — a diferencia de mainloop(), MAI bloqueja.

        Al navegador aixo es el que permet combinar una finestra tkinter amb
        codi asincron (p.ex. MQTT) sense que la finestra bloquegi mai el fil
        del worker: en lloc de root.mainloop(), es fa
            while not aturat:
                root.update()
                await asyncio.sleep(0.05)
        Aquest patro es tambe valid amb tkinter real (Raspberry Pi, PC) —
        no cal cap adaptacio per portar-lo fora del navegador.

        NOTA: no barregis update() i mainloop() al mateix programa; tria un
        dels dos segons si necessites codi asincron en paral·lel o no.
        """
        raw = __tk_poll_events__()
        try:
            events = _json.loads(raw) if raw else []
        except Exception:
            events = []
        for ev in events:
            if ev.get("type") == "command":
                cb = _callbacks.get(ev.get("id"))
                if cb is not None:
                    cb()

    def update_idletasks(self):
        # El renderer ja aplica cada canvi (create/config) de seguida, no hi
        # ha cua d'"idle tasks" per buidar — es un no-op real i inofensiu.
        pass


class Label(_Widget):
    pass


class Entry(_Widget):
    def get(self):
        res = _call("get", id=self.id)
        return (res or {}).get("value", "")

    def insert(self, index, text):
        _call("insert", id=self.id, index=index, text=text)

    def delete(self, first, last=None):
        _call("delete", id=self.id, first=first, last=last)


class Button(_Widget):
    def __init__(self, master=None, command=None, **kwargs):
        super().__init__(master, **kwargs)
        if command is not None:
            _callbacks[self.id] = command

    def config(self, **kwargs):
        command = kwargs.pop("command", None)
        if command is not None:
            _callbacks[self.id] = command
        if kwargs:
            super().config(**kwargs)

    configure = config


class Radiobutton(_Widget):
    """Necessita una 'variable' (IntVar/StringVar) compartida entre tots els
    Radiobutton d'un mateix grup: es qui sap quin esta seleccionat. El
    'value' es el valor que pren la variable quan ES SELECCIONA aquest boto."""

    def __init__(self, master=None, command=None, variable=None, value=None,
                 **kwargs):
        opts = dict(kwargs)
        opts["_variable"] = variable.id if variable is not None else None
        opts["_value"] = value
        super().__init__(master, **opts)
        if command is not None:
            _callbacks[self.id] = command

    def config(self, **kwargs):
        command = kwargs.pop("command", None)
        if command is not None:
            _callbacks[self.id] = command
        if kwargs:
            super().config(**kwargs)

    configure = config


class Variable:
    """Base minima per a IntVar/StringVar: nomes el necessari perque
    Radiobutton funcioni (get/set). No es un widget (no es pack()/grid())."""

    def __init__(self, master=None, value=None, name=None):
        self.id = _new_id()
        _call("var_create", id=self.id, value=value)

    def get(self):
        res = _call("var_get", id=self.id)
        return (res or {}).get("value")

    def set(self, value):
        _call("var_set", id=self.id, value=value)


class IntVar(Variable):
    def __init__(self, master=None, value=0, name=None):
        super().__init__(master, 0 if value is None else value, name)

    def get(self):
        v = super().get()
        return int(v) if v is not None else 0


class StringVar(Variable):
    def __init__(self, master=None, value="", name=None):
        super().__init__(master, "" if value is None else value, name)

    def get(self):
        v = super().get()
        return "" if v is None else str(v)


# Constants habituals que apareixen al manual (tk.RIGHT, tk.END, etc.)
LEFT, RIGHT, TOP, BOTTOM = "left", "right", "top", "bottom"
END = "end"
NORMAL, DISABLED = "normal", "disabled"


def _idx(value):
    """Normalitza un index per enviar-lo al fil principal: END -> 'end',
    qualsevol altra cosa (int normalment) tal qual."""
    return "end" if value == END else value


class Checkbutton(_Widget):
    """Com Radiobutton, pero sense grup: nomes commuta entre onvalue/offvalue
    a la seva propia variable. Si no es passa 'variable=', es crea una
    IntVar interna (aixi pack()/config() etc. mai fallen)."""

    def __init__(self, master=None, command=None, variable=None,
                 onvalue=1, offvalue=0, **kwargs):
        self._variable = variable if variable is not None else IntVar(master, value=offvalue)
        self._onvalue = onvalue
        self._offvalue = offvalue
        opts = dict(kwargs)
        opts["_variable"] = self._variable.id
        opts["_onvalue"] = onvalue
        opts["_offvalue"] = offvalue
        super().__init__(master, **opts)
        if command is not None:
            _callbacks[self.id] = command

    def config(self, **kwargs):
        command = kwargs.pop("command", None)
        if command is not None:
            _callbacks[self.id] = command
        if kwargs:
            super().config(**kwargs)

    configure = config

    def select(self):
        self._variable.set(self._onvalue)

    def deselect(self):
        self._variable.set(self._offvalue)

    def toggle(self):
        actual = self._variable.get()
        self._variable.set(self._offvalue if actual == self._onvalue else self._onvalue)


class Listbox(_Widget):
    def insert(self, index, *elements):
        _call("listbox_insert", id=self.id, index=_idx(index), elements=list(elements))

    def delete(self, first, last=None):
        _call("listbox_delete", id=self.id, first=_idx(first),
              last=(None if last is None else _idx(last)))

    def get(self, first, last=None):
        if last is None:
            res = _call("listbox_get_one", id=self.id, index=_idx(first))
            return (res or {}).get("value", "")
        res = _call("listbox_get_range", id=self.id, first=_idx(first), last=_idx(last))
        return tuple((res or {}).get("values", []))

    def curselection(self):
        res = _call("listbox_curselection", id=self.id)
        return tuple((res or {}).get("indices", []))

    def size(self):
        res = _call("listbox_size", id=self.id)
        return (res or {}).get("value", 0)


class PhotoImage:
    """Recurs d'imatge. NO es un giny (no es pack()/grid()/place()): es
    nomes una referencia que es passa com a image= a un Label/Button.
    file=... ha d'apuntar a un fitxer ja present al FS virtual de Pyodide
    (el worker hi escriu els "assets" del projecte abans de cada execucio)."""

    def __init__(self, file=None, data=None, **kwargs):
        self.id = _new_id()
        b64 = data
        if file is not None and b64 is None:
            # Ruta absoluta sempre: el worker escriu els assets a l'arrel ('/'),
            # i Pyodide no garanteix que el directori de treball per defecte
            # sigui '/' (algunes versions usen '/home/pyodide'), aixi que una
            # ruta relativa podria buscar al lloc equivocat.
            path = file if file.startswith("/") else "/" + file
            try:
                with open(path, "rb") as fh:
                    b64 = _b64.b64encode(fh.read()).decode("ascii")
            except FileNotFoundError:
                import os
                disponibles = sorted(
                    n for n in os.listdir("/")
                    if not n.startswith("lib") and not n.startswith(".")
                )
                raise FileNotFoundError(
                    f"No s'ha trobat la imatge {file!r}. "
                    f"Fitxers disponibles a l'arrel del projecte: {disponibles}. "
                    "Recorda pujar-la amb el boto 'Importa imatge...' de l'IDE "
                    "(i comprova majuscules/minuscules de l'extensio i el nom)."
                ) from None
        _call("image_register", id=self.id, data=b64 or "")

    def width(self):
        return (_call("image_info", id=self.id) or {}).get("width", 0)

    def height(self):
        return (_call("image_info", id=self.id) or {}).get("height", 0)


class _MessageBox:
    @staticmethod
    def showinfo(title=None, message=None, **kw):
        _call("msgbox", kind="info", title=title or "", message=message or "")

    @staticmethod
    def showerror(title=None, message=None, **kw):
        _call("msgbox", kind="error", title=title or "", message=message or "")

    @staticmethod
    def askokcancel(title=None, message=None, **kw):
        res = _call("msgbox", kind="askokcancel",
                     title=title or "", message=message or "")
        return bool((res or {}).get("ok"))


messagebox = _MessageBox()


class _Ttk:
    """Subconjunt minim de ttk perque 'from tkinter import ttk' no falli
    (apareix a un dels exemples del manual amb ttk.Button/ttk.Frame)."""
    Button = Button
    Label = Label
    Frame = _Widget


ttk = _Ttk()

