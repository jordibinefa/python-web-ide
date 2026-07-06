/**
 * Wrapper Paho MQTT per emular l'API de Python amb MQTT.js
 * Únicament suporta WebSocket (WSS/WS) - no TCP
 *
 * ADAPTAT PER A py-web (model B): aquest fitxer es carrega DINS el Web
 * Worker (via importScripts), on NO existeix `window`. Per això tots els
 * `window.*` són ara `globalThis.*` (funciona igual al fil principal i al
 * worker). A més s'hi afegeix un petit registre de clients
 * (globalThis.__pahoClients) i una funció de neteja (globalThis.__pahoCleanup)
 * perquè, si l'alumne torna a executar sense reiniciar l'entorn, no quedin
 * connexions MQTT òrfenes obertes. Cap altre canvi respecte de l'original.
 */

// Namespace paho.mqtt.client
globalThis.paho = {
    mqtt: {
        client: {}
    }
};

/**
 * Classe MQTTClient compatible amb Paho Python
 */
class MQTTClient {
    constructor(client_id = null) {
        this.client_id = client_id || 'mqtt_' + Math.random().toString(16).substr(2, 8);
        this.mqttClient = null;
        this.connected = false;

        // Callbacks (compatibilitat amb Paho Python)
        this.on_connect = null;
        this.on_disconnect = null;
        this.on_message = null;
        this.on_publish = null;
        this.on_subscribe = null;
        this.on_unsubscribe = null;

        // Userdata (per compatibilitat)
        this.userdata = null;

        // py-web: registra el client per a poder netejar-lo en re-executar.
        (globalThis.__pahoClients || (globalThis.__pahoClients = [])).push(this);
    }

    /**
     * Connectar al broker MQTT via WebSocket
     * @param {string} host - Hostname del broker (ex: "broker.emqx.io")
     * @param {number} port - Port WebSocket (ex: 8084 per WSS, 8083 per WS)
     * @param {number} keepalive - Keepalive en segons (per defecte 60)
     * @param {object} options - Opcions addicionals (username, password, etc.)
     */
    connect(host, port = 8084, keepalive = 60, options = {}) {
        // Construir URL WebSocket
        const protocol = port === 8084 || port === 8081 || port === 8000 || port === 9002 ? 'wss' : 'ws';
        const wsUrl = `${protocol}://${host}:${port}/mqtt`;

        console.log(`Connectant a ${wsUrl}...`);

        try {
            // Opcions de connexió MQTT.js
            const mqttOptions = {
                clientId: this.client_id,
                keepalive: keepalive,
                clean: true,
                reconnectPeriod: 0, // Desactivar reconnexió automàtica
            };

            // Afegir credencials si s'han proporcionat
            if (options.username) mqttOptions.username = options.username;
            if (options.password) mqttOptions.password = options.password;

            // Crear client MQTT.js
            this.mqttClient = mqtt.connect(wsUrl, mqttOptions);

            // Event: Connexió exitosa
            this.mqttClient.on('connect', (connack) => {
                this.connected = true;
                console.log('Connectat al broker MQTT');

                // Cridar callback on_connect (Paho style)
                if (this.on_connect) {
                    // Simular paràmetres Paho: (client, userdata, flags, rc)
                    const flags = { session_present: connack.sessionPresent };
                    const rc = 0; // 0 = èxit
                    this.on_connect(this, this.userdata, flags, rc);
                }
            });

            // Event: Missatge rebut
            this.mqttClient.on('message', (topic, payload, packet) => {
                if (this.on_message) {
                    // Convertir Buffer a string
                    let payloadStr = payload.toString();
                    // Compatibilitat Python Paho: si el payload és un valor simple
                    // embolcallat en cometes (típic de Node-RED amb JSON.stringify("R")),
                    // treure les cometes envolvents per igualar el comportament de Python
                    // on msg.payload és bytes sense cometes extres.
                    // Només per valors simples (no JSON objectes/arrays).
                    if (payloadStr.length >= 2 &&
                        payloadStr.startsWith('"') && payloadStr.endsWith('"') &&
                        !payloadStr.includes('{') && !payloadStr.includes('[')) {
                        try {
                            const parsed = JSON.parse(payloadStr);
                            if (typeof parsed === 'string') {
                                payloadStr = parsed;
                            }
                        } catch (e) {
                            // No és JSON vàlid, deixar tal qual
                        }
                    }
                    // Crear objecte msg compatible amb Paho
                    const msg = {
                        topic: topic,
                        payload: payloadStr,
                        qos: packet.qos,
                        retain: packet.retain
                    };
                    this.on_message(this, this.userdata, msg);
                }
            });

            // Event: Desconnexió
            this.mqttClient.on('close', () => {
                this.connected = false;
                console.log('Desconnectat del broker MQTT');

                if (this.on_disconnect) {
                    this.on_disconnect(this, this.userdata, 0);
                }
            });

            // Event: Error
            this.mqttClient.on('error', (error) => {
                console.error('Error MQTT:', error.message);
                this.connected = false;
            });

        } catch (error) {
            console.error('Error connectant al broker:', error);

            // Cridar callback amb codi d'error
            if (this.on_connect) {
                this.on_connect(this, this.userdata, {}, 1); // rc=1 = error
            }
        }
    }

    /**
     * Publicar un missatge a un topic
     * @param {string} topic - Topic MQTT
     * @param {string|number} payload - Missatge a publicar
     * @param {number} qos - Quality of Service (0, 1, 2) - per defecte 0
     * @param {boolean} retain - Flag retain (per defecte false)
     */
    publish(topic, payload, qos = 0, retain = false) {
        if (!this.connected || !this.mqttClient) {
            console.error('No connectat al broker MQTT');
            return;
        }

        // Convertir payload a string si és necessari
        const payloadStr = typeof payload === 'string' ? payload : String(payload);

        this.mqttClient.publish(topic, payloadStr, { qos: qos, retain: retain }, (err) => {
            if (err) {
                console.error('Error publicant:', err);
            } else {
                if (this.on_publish) {
                    this.on_publish(this, this.userdata, topic);
                }
            }
        });
    }

    /**
     * Subscriure's a un topic
     * @param {string} topic - Topic MQTT (suporta wildcards: +, #)
     * @param {number} qos - Quality of Service (per defecte 0)
     */
    subscribe(topic, qos = 0) {
        if (!this.connected || !this.mqttClient) {
            console.error('No connectat al broker MQTT');
            return;
        }

        this.mqttClient.subscribe(topic, { qos: qos }, (err, granted) => {
            if (err) {
                console.error('Error subscrivint:', err);
            } else {
                console.log(`Subscrit a: ${topic}`);
                if (this.on_subscribe) {
                    this.on_subscribe(this, this.userdata, topic, granted);
                }
            }
        });
    }

    /**
     * Cancel·lar subscripció a un topic
     * @param {string} topic - Topic MQTT
     */
    unsubscribe(topic) {
        if (!this.connected || !this.mqttClient) {
            console.error('No connectat al broker MQTT');
            return;
        }

        this.mqttClient.unsubscribe(topic, (err) => {
            if (err) {
                console.error('Error desubscrivint:', err);
            } else {
                console.log(`Dessubscrit de: ${topic}`);
                if (this.on_unsubscribe) {
                    this.on_unsubscribe(this, this.userdata, topic);
                }
            }
        });
    }

    /**
     * Desconnectar del broker
     * @param {boolean} force - Forçar desconnexió immediata (per defecte false)
     */
    disconnect(force = false) {
        if (this.mqttClient) {
            try {
                this.mqttClient.end(force, () => {
                    this.connected = false;
                    console.log('Client MQTT desconnectat');
                });
            } catch (e) {
                console.warn('Error durant disconnect MQTT:', e.message);
                this.connected = false;
            }
        }
        this.connected = false;
    }

    /**
     * Loop start (no necessari en MQTT.js - automàtic)
     * Inclòs per compatibilitat amb Paho Python
     */
    loop_start() {
        // MQTT.js ja gestiona el loop automàticament
        console.log('Loop MQTT actiu (automàtic)');
    }

    /**
     * Loop stop (no necessari en MQTT.js)
     * Inclòs per compatibilitat amb Paho Python
     */
    loop_stop() {
        // No cal fer res, per compatibilitat
        console.log('Loop MQTT aturat');
    }

    /**
     * Comprovar si està connectat
     * @returns {boolean}
     */
    is_connected() {
        return this.connected;
    }
}

// Exportar al namespace paho
globalThis.paho.mqtt.client.Client = MQTTClient;

// Crear funció wrapper que crida 'new' automàticament (compatibilitat Python)
globalThis.paho.mqtt.client.Client = function(client_id) {
    return new MQTTClient(client_id);
};

// Mantenir referència a la classe original
globalThis.paho.mqtt.client.MQTTClient = MQTTClient;

// py-web: neteja de connexions abans de cada nova execució (evita clients
// MQTT òrfens si l'alumne re-executa sense reiniciar l'entorn).
globalThis.__pahoCleanup = function() {
    const clients = globalThis.__pahoClients || [];
    for (const c of clients) {
        try { c.disconnect(true); } catch (e) { /* ignora */ }
    }
    globalThis.__pahoClients = [];
};

console.log('✓ Paho MQTT wrapper carregat (només WebSocket WSS/WS)');
