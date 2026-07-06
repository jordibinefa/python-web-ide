# Context: python-web-ide — shim de tkinter + MQTT (estat actual)

Aquest document resumeix les decisions clau i paranys ja resolts del projecte
`py-web` (IDE Python amb Pyodide + Web Worker, shim de tkinter i MQTT). Si
comences un xat nou amb Claude per continuar, enganxa aquest fitxer +
l'`index.html` actual com a primer missatge.

> Aquest document tracta la **implementació del shim en si** (com es
> construeix l'IDE). Si el que necessites és context per **escriure codi
> Python d'exemple** que funcioni tant a py.binefa.cat com en un terminal
> normal (tkinter/paho-mqtt reals), fes servir `CONTEXT_AI_py_binefa_cat.md`
> en lloc d'aquest — cobreix el patró de portabilitat (`asyncio.run()` vs.
> `await` de nivell superior, cua thread-safe per a MQTT real, rutes de
> fitxers, etc.) après desenvolupant `tk_mqtt_smm.py`.

## Desplegament (canvi respecte a versions anteriors)

El projecte ara viu al VPS (`vps-f95c103f-vps-ovh-net`), servit amb
**`docker-compose.yml` + `nginx.conf`** dins `~/py-web/`, NO amb el
`server.py` local de desenvolupament. Estructura:

```
py-web/
├── docker-compose.yml
├── nginx.conf
├── vendor-package.py
└── www/
    ├── index.html              (el fitxer principal, tot incrustat)
    ├── tkinter_shim.py         (còpia de referència, no s'usa en runtime)
    ├── exemples/               (ZIPs i assets per provar/demostrar)
    │   ├── py/                 (scripts MQTT "reals" per a Pi/fora del navegador)
    │   │   ├── mqtt_pub_sub.py
    │   │   ├── mqtt_publica.py
    │   │   ├── mqtt_subscriu.py
    │   │   └── paho_shim.py
    │   ├── tk*.zip, tkGrid00.zip, tkImg.zip, tkListBox.zip, ...
    │   ├── matplot00.zip, exImport00.zip
    │   └── logoEcat.png
    └── vendor/
        ├── codemirror/6.0.2/
        ├── jszip/3.10.1/
        ├── mqtt/5.15.1/mqtt.min.js        (MQTT.js, llibreria real)
        ├── paho/1.0/paho-mqtt.js          (wrapper JS PROPI, no el Paho oficial)
        └── pyodide/0.28.3/
```

⚠️ **Pendent de verificar / possible inconsistència**: alguns comentaris dins
`index.html` (prop de `SharedArrayBuffer` i dels missatges d'avís de
tkinter/input) encara diuen *"serveix amb `python3 server.py`"*. Ara que es
serveix amb nginx, cal confirmar que `nginx.conf` envia les capçaleres
**COOP/COEP** (`Cross-Origin-Opener-Policy: same-origin` i
`Cross-Origin-Embedder-Policy: require-corp`), imprescindibles perquè
`SharedArrayBuffer` funcioni — i actualitzar els textos d'avís si cal.

## `#run:`/`#open:` a la URL — ja implementat

Vegeu `ajuda.md` (a `www/ajuda.md`, encara pendent de convertir a
`ajuda.html`) per a l'especificació completa amb exemples. Resum tècnic:

- Sintaxi: `#run:<url.zip>` (cas simple) o `#run:_prj=zip:<url>&clau=valor&...`
  / `#run:_prj=ex:<id>&...` (amb variables). `#open:` fa el mateix pero sense
  auto-executar.
- `_prj` es l'unica clau reservada; la resta de claus es passen literalment
  com a `str` a `pyodide.globals` (mai coerció de tipus), re-injectades
  **cada execucio** (mateix punt que tkinter/paho es re-registren).
- Whitelist de dominis per a `_prj=zip:` (12 dominis, veure
  `DOMINIS_PERMESOS` a `index.html`); fora de la llista o error de CORS →
  avis per consola + `alert()`.
- Valors sense cometa inicial → `decodeURIComponent()`; amb cometa inicial
  (`'`/`"`) → literal fins la mateixa cometa de tancament (estil Python,
  sense escapaments).
- **Cal recarregar la pagina sencera** per aplicar un canvi al hash de la
  URL (el hash nomes es llegeix un cop, en carregar). Especialment rellevant
  per a `<iframe>` (p.ex. una pagina `split` amb Snap! a l'altra meitat):
  canviar nomes el `src` d'un iframe ja carregat (mateix origen, hash
  diferent) sovint NO recarrega el document intern — cal forçar-ho.
- Funcions clau a `index.html`: `parseHashDirective()`, `parseHashParams()`,
  `dominiPermes()`, `carregaProjecteRemot()`, `carregaExempleDesDeHash()`,
  `aplicaDirectivaHash()`, `intentaAutoRun()`.

## Arquitectura general (sense canvis respecte abans)

- Pyodide corre dins un **Web Worker**; tot el que toca pantalla (finestra
  Tk) passa per `postMessage` cap al fil principal (el *renderer*).
- El shim de tkinter està **incrustat** a `index.html` com
  `<script id="tkinter-shim-src" type="text/plain">`. El fitxer
  `tkinter_shim.py` separat és només còpia de referència.
- **Pyodide intercepta `import X` amb un finder propi** per a certs mòduls
  (tkinter n'és el cas conegut): la solució sempre és registrar el mòdul
  directament a `sys.modules[...]` dins un `types.ModuleType`, MAI escriure'l
  al FS ni tocar `sys.path` per a aquests casos especials.

## MQTT / Paho — ja implementat (Model B)

**Decisió de disseny**: MQTT.js (la llibreria real, `vendor/mqtt/5.15.1/mqtt.min.js`)
i un wrapper JS propi (`vendor/paho/1.0/paho-mqtt.js`, **no** és la llibreria
oficial Eclipse Paho — és un nom triat perquè exposa una API
`globalThis.paho.mqtt.client.Client` compatible) viuen **dins del mateix Web
Worker** que Pyodide (no en un worker o iframe separat). Això evita haver de
fer un altre pont `postMessage`/`Atomics` només per a MQTT.

- Els dos scripts es carreguen amb `self.importScripts(mqttUrl)` /
  `self.importScripts(pahoUrl)` dins `setup()` del worker, **sense bloquejar
  la resta de l'IDE si falten** (`try/catch`, `self.__mqttLoaded` és un flag;
  si falten els fitxers vendor, `mqtt.Client()` dona un `RuntimeError` clar
  en comptes de trencar tot Pyodide).
- El shim Python (`paho_shim.py`, incrustat com
  `<script id="paho-shim-src" type="text/plain">`) es registra a
  `sys.modules['paho']` / `['paho.mqtt']` / `['paho.mqtt.client']` — **mateix
  patró exacte que tkinter** (mòdul nou cada execució, mai FS/sys.path).
- Neteja entre execucions: `self.__pahoCleanup()` tanca qualsevol client
  obert d'una execució anterior abans de re-registrar el mòdul — equivalent
  MQTT del que fa `netejaFinestraTk()` per a tkinter.
- **API Python resultant** (subconjunt fidel a paho-mqtt real):
  `Client(client_id)`, `on_connect/on_disconnect/on_message/on_publish/
  on_subscribe/on_unsubscribe` com a atributs-callback,
  `username_pw_set()`, `user_data_set()`, `connect(host, port=8084,
  keepalive=60)`, `publish()`, `subscribe()`, `unsubscribe()`, `loop_start()`,
  `loop_stop()`, `disconnect()`, `is_connected()`.
- `msg.payload` arriba com a **bytes** (no str), perquè `.decode("utf-8")`
  funcioni igual que amb el paho real i amb els scripts "universals"
  Pi/simulador que Jordi ja fa servir a IoT-Vertebrae.
- **Només WebSocket segur (wss)**: el navegador no pot fer TCP cru. El port
  determina el protocol al wrapper JS (8084/8081/8000/9002 → wss, la resta
  → ws).
- `loop_forever()` llença `RuntimeError` explícit (bloquejaria el bucle
  d'esdeveniments del navegador) — indica fer servir `loop_start()` +
  `while True: await asyncio.sleep(...)` en el seu lloc. Aquest és el motiu
  pel qual **tots els exemples MQTT del navegador usen `async def` +
  `await asyncio.sleep()`**, mai `time.sleep()`.
- `exemples/py/*.py` són els **equivalents "reals"** (paho autèntic, per
  Raspberry Pi o fora del navegador) dels exemples del navegador —
  documentar-los com a parella pedagògica ("aquest és el que faries a un Pi
  real amb el paho de veritat").

## tkinter + async (MQTT, temporitzadors...) — Tk.update(), NO mainloop()

**Problema d'arquitectura descobert**: `Tk.mainloop()` fa `_call("wait_event")`
→ `Atomics.wait(...)`, que bloqueja **de veritat** el fil sencer del worker
(no és un `await`, no cedeix mai el control a l'event loop de JS). Com que
MQTT.js viu al mateix worker (Model B, veure més avall), mentre `mainloop()`
esta actiu — esperant un clic o processant-lo, tant se val — **MQTT no pot
rebre res**, encara que arribin dades per la xarxa (queden aparcades a
nivell de navegador fins que el fil JS torna a quedar lliure). A mes, un
clic NOMES s'entrega si en aquell instant el worker esta bloquejat dins
`wait_event()` — si `mainloop()` no corre, el clic es descarta.

**Solucio implementada**: `Tk.update()` (mètode REAL de tkinter, no un
invent d'aquest IDE) — processa els clics pendents UN COP i torna
IMMEDIATAMENT, sense bloquejar mai. Patró recomanat per a qualsevol
programa tkinter que necessiti conviure amb codi asincron:

```python
aturat = False
while not aturat:
    finestra.update()
    await asyncio.sleep(0.05)   # cedeix el control perque MQTT.js pugui rebre
```

Mecanisme intern: `update()` fa una crida NO bloquejant
(`__tk_poll_events__()`, sense Atomics/SharedArrayBuffer) que buida una cua
JS normal (`self.__tkEventQueue`), omplerta via `postMessage` des del fil
principal cada cop que hi ha un clic (`tkFireEvent()`), en paral·lel i
independent del mecanisme classic de `mainloop()`/`wait_event` (que segueix
intacte, sense tocar, per als exemples tkinter purs sense MQTT). No barrejar
`update()` i `mainloop()` al mateix programa.

**⚠️ BUG DESCOBERT: mai facis servir `asyncio.run()` dins d'aquest IDE.**
Provoca `RuntimeError: WebAssembly stack switching not supported in this
JavaScript runtime` — Pyodide ja executa el codi dins el seu propi bucle
asincron (`runPythonAsync`/`eval_code_async`, que permet `await` directament
al nivell superior del fitxer), i cridar `asyncio.run()` intenta crear un
bucle NOU de manera "sincrona" des del punt de vista de qui el crida, cosa
que requereix una funcionalitat de WebAssembly (JSPI/"stack switching") que
el build de Pyodide/navegador actual NO suporta. Quan passa, l'excepcio surt
just en arrencar i **el bucle mai arriba a executar cap volta** — els clics
no fan res, però callbacks MQTT (`on_connect`/`on_message`) SI que semblen
funcionar perquè es criden directament des del pont JS de paho, no depenen
del bucle Python. Es un símptoma enganyós: "sembla que funciona a mitges".
**Patró correcte** (el que ja fan `mqtt_pub_sub`/`mqtt_publica`/
`mqtt_subscriu`): `while ...: ... await asyncio.sleep(...)` directament al
nivell superior, SENSE `async def main()` ni `asyncio.run()`. Cost: aquest
codi ja NO es portable literalment a un terminal Python real (que rebutja
`await` fora d'una funció `async`) — per portar-lo caldria embolcallar amb
`async def main(): ...` + `asyncio.run(main())` en aquell entorn.

**⚠️ BUG DESCOBERT I CORREGIT: text d'estat encallat en programes que no
acaben mai.** El worker envia `{type:'status', text:'Carregant paquets…'}`
abans de `loadPackagesFromImports()`, i el text nomes es torna a actualitzar
quan `runPythonAsync()` es resol (missatge `'done'`). Un programa amb un
`while` infinit (com QUALSEVOL exemple MQTT asincron, no nomes
tkinter+MQTT) mai arriba a `'done'`, aixi que el text es queda per sempre
en "Carregant paquets…" (amb el punt taronja pampallugant de "busy", que si
que es correcte). Fix: s'envia un `{type:'status', text:'Executant…'}` just
abans de `runPythonAsync(msg.code)`, despres de carregar paquets.

## Maximitzar la finestra Tk i redimensionar columnes — ja implementat

Inspirat en Snap! (botons de maximitzar/compartir el canvas):
- Botó `tkMaximitzaBtn` a `.tk-window-header` (icones SVG inline
  maximitza/restaura). En maximitzar, `.tk-col` passa a `position: fixed;
  inset: 0;` (surt del `grid` de `main` per evitar interaccions estranyes
  d'alineacio vertical amb `align-content`/`justify-content` que van costar
  de depurar) i `body.tk-maximitzat` amaga capçalera/barra d'estat/peu
  sencers — no nomes codi+consola — perque la finestra Tk aprofiti tota la
  pantalla, com el canvas de Snap!.
- **Auto-maximitza en `#run:` (mai en `#open:` ni en un "Executa" manual)**:
  flag `pendentAutoMaximitzarTk`, consumit la primera vegada que apareix una
  finestra Tk (`mostraFinestraTk()`) durant AQUELLA execucio concreta.
- Columnes (codi/consola/Tk) redimensionables arrossegant separadors
  (`#resizer1`/`#resizer2`), proporcions desades a `localStorage`
  (`py-web-proporcions-columnes`). Desactivat en mobil (`≤760px`).

## Altres millores petites d'aquesta sessió

- `Entry(show='*')` — camp de contrasenya amb mascara real (abans no hi
  havia cap suport per a `show=` al renderer).
- `font=(family, size, 'bold'/'italic')`: l'ordre de tkinter es traduia
  literalment a CSS (`"Arial 10 bold"`, invalid), i el navegador ignorava
  tot el `font` sencer — corregit amb `_tkFontCss()` (ordre `[estil] mida
  familia`).

## Selector d'exemples predefinits — ja implementat

`exemplesPredefinits` (array JS dins `index.html`) + `omplePeselectorExemples()`
agrupa per `categoria` en `<optgroup>`: **Bàsic, Científic, TKinter, MQTT**.
Cada entrada té `{ id, categoria, nom, files: [...], assets: [...] }` — els
`assets` permeten que un exemple (com el de `PhotoImage`) arribi amb la seva
pròpia imatge ja inclosa, sense que l'alumne hagi de pujar-la a mà. En
seleccionar, substitueix `files`/`assets`/`activeIdx`/`nomProjecte` sencers
(amb `confirm()` previ) — mateix mecanisme que la importació de ZIP.

Exemples actuals per categoria (13+ entrades): Bàsic (×4), Científic (×2),
TKinter (×7: bàsic, entry/button, place, grid, radiobutton, listbox,
checkbox, imatge), MQTT (×3: publicador, subscriptor, pub+sub alhora).

## Incrustar `py.binefa.cat` dins d'un `<iframe>` (projecte `pahoSnap`)

Cas d'ús: una pàgina `split` amb `py.binefa.cat` (tkinter+MQTT) a una meitat
i Snap! a l'altra (`pahoSnap00.html` → desplegat a
`broker.binefa.cat/pahoSnap/index.html`). Genera un ID aleatori de 6 xifres
un cop en carregar-se i el fa servir per construir les dues URLs
(`_prj=zip:...&temaSub=/prova/<id>/#&...` per a py.binefa.cat,
`&param=/prova/<id>` per a Snap!), sincronitzant el tema MQTT entre totes
dues bandes sense que calgui coordinar-ho a mà.

**Descoberta important (va costar tres iteracions arribar-hi, val la pena
no repetir-ho): incrustar un document amb `SharedArrayBuffer`/tkinter dins
d'un `<iframe>` necessita capçaleres a TRES llocs diferents, no només al
document final:**

1. **La pàgina contenidora** (`pahoSnap00.html`, o qualsevol `split` futur)
   necessita el seu propi `Cross-Origin-Opener-Policy: same-origin` +
   `Cross-Origin-Embedder-Policy: credentialless` — sense això, l'aïllament
   cross-origin no s'aplica a TOTA la cadena de finestres i `py.binefa.cat`
   falla amb `RuntimeError: tkinter necessita SharedArrayBuffer` encara que
   el seu propi servidor ja les enviï. **Aquestes capçaleres NOMÉS es poden
   posar via servidor (nginx/Traefik), mai amb `<meta>`.**
2. **`py.binefa.cat` (el document que necessita `SharedArrayBuffer` de
   veritat)** ja enviava COOP+COEP per a ell mateix (veure `nginx.conf`),
   però li faltava `Cross-Origin-Resource-Policy: cross-origin` — sense
   aquesta, la pàgina contenidora (amb COEP actiu) el bloqueja en carregar
   l'`iframe` amb *"blocked due to its Cross-Origin-Resource-Policy header
   (or lack thereof)"*. Ja corregit a `~/py-web/nginx.conf`.
3. **Qualsevol ALTRE document incrustat al costat** (Snap!, a
   `broker.binefa.cat/snap/`), encara que ell mateix NO necessiti
   `SharedArrayBuffer`, necessita IGUALMENT capçaleres pel simple fet
   d'estar en un `<iframe>` dins d'una pàgina amb COEP actiu — i **calen
   les DUES**, no només una:
   - `Cross-Origin-Embedder-Policy: credentialless` (o `require-corp`)
   - `Cross-Origin-Resource-Policy: cross-origin`

   Font (especificació WICG de `credentialless`, no una hipòtesi): *"If the
   parent sets COEP:credentialless or COEP:require-corp, then the children
   is required to specify a CORP header when the response is cross-origin."*
   És a dir: **`credentialless` no elimina el requisit de CORP per a
   navegacions completes d'`<iframe>`** — només evita haver de posar CORP
   als SUBRECURSOS (imatges, scripts...) que aquell document carrega
   internament. Aquest matís (CORP encara cal pel document en si) és el que
   va costar més d'identificar — les dues primeres correccions (només COEP,
   només CORP a `py.binefa.cat`) van ser necessàries però no suficients.

**Desplegament final (VPS, `~/mosquitto-broker/`)**: Traefik amb un
middleware compartit `coop-coep-headers@file` (definit a
`~/traefik/config/middlewares-cors.yml`) que posa les tres capçaleres
(COOP+COEP+CORP) alhora, aplicat via **routers específics per `PathPrefix`**
(`/pahoSnap`, `/snap`) amb `priority=100` per no afectar la resta de
`broker.binefa.cat` (que no ho necessita) — el router general
(`Host` sol) es queda tal qual. Patró reutilitzable per a qualsevol futur
subdirectori que calgui incrustar en un `iframe` amb COEP actiu: afegir un
router nou amb `PathPrefix`, apuntant al mateix `service`, amb
`coop-coep-headers@file` (i `cors-headers@file` si també cal CORS) als
`middlewares`.

**A l'`<iframe>` mateix**: cal `allow="cross-origin-isolated"` a l'etiqueta
`<iframe>` que incrusta `py.binefa.cat`, perquè la pàgina delegui
explícitament aquest permís (Chrome ho respecta; Firefox mostra un avís
inofensiu *"Feature Policy: Skipping unsupported feature name
'cross-origin-isolated'"* — no és un error real, Firefox ho gestiona
diferent i no cal fer-hi res).

**Diagnòstic per a la propera vegada** (si torna a fallar): `curl -sI
<url>` mostra les capçaleres reals sense soroll de navegador/extensions —
sempre el primer pas. Si l'accés directe (fora d'`iframe`) funciona però
dins de l'`iframe` no, és gairebé sempre COOP/COEP/CORP, no una extensió
ni una política de xarxa (`about:policies` per descartar-la del tot, i
provar en un altre navegador/finestra privada per descartar extensions —
en aquest cas concret totes dues vies es van descartar abans de trobar la
causa real).

## Paranys ja trobats i corregits (tkinter, no repetir-los)

1. `sys.modules.pop()` esborrava el shim si una pestanya es deia igual que
   el mòdul (`tkinter.py`, `paho.py`...) → excloure explícitament del filtre
   d'invalidació + re-registrar incondicionalment cada execució. **El mateix
   patró ja s'aplica a `'paho'` a la invalidació de mòduls** (veure línia amb
   `moduleNames.filter((m) => m !== 'tkinter' && m !== 'paho')`).
2. `importlib` cacheja directoris → `importlib.invalidate_caches()` després
   d'escriure fitxers, abans de `runPythonAsync`.
3. `sys.path` no inclou `/` per defecte amb `runPythonAsync`/`exec()` → cal
   `sys.path.insert(0, '/')` explícit a `setup()`.
4. Rutes relatives a `PhotoImage(file=...)` → forçar ruta absoluta.
5. CSS Grid (`grid()`) s'estirava verticalment → `align-content: start` al
   contenidor.
6. Botons amb text blanc il·legible → una regla `button {...}` genèrica de
   l'IDE es filtrava cap a `.tk-button`; cal sobreescriure `color`,
   `font-weight`, `border-radius` explícitament.
7. Widgets compostos i `text=` → marcar `el._tkTextTarget` perquè
   `tkApplyOpts` no esborri fills en aplicar `text=`.
8. `estat = ...` dins un callback niat (p.ex. `on_connect` dins d'una funció
   que fa `global estat` al nivell exterior) SENSE `global estat` propi crea
   una variable LOCAL a dins del niat — la global mai s'actualitza. Detectat
   amb `pyflakes`; revisar sempre callbacks niats amb `pyflakes` abans
   d'entregar codi d'exemple.
9. `asyncio.run()` dins d'aquest IDE → `RuntimeError: WebAssembly stack
   switching not supported`. Vegeu la secció "tkinter + async" més amunt.
10. Text d'estat ("Carregant paquets…") encallat en programes amb bucle
    infinit → cal reenviar `{type:'status', text:'Executant…'}` abans de
    `runPythonAsync(msg.code)`. Vegeu la secció "tkinter + async".

## Widgets/funcions tkinter implementats (fases 1-8, totes fetes)

`Tk`, `Label`, `Entry` (amb `show=` per a contrasenyes), `Button`,
`messagebox.showinfo/askokcancel`, `Radiobutton` + `IntVar`/`StringVar`
mínimes, `Listbox`, `Checkbutton`, `PhotoImage`. Gestors: `pack()`, `grid()`
(CSS Grid real amb `columnspan`/`rowspan`/`sticky`), `place()`.
`Tk.update()`/`update_idletasks()` — vegeu la secció "tkinter + async".

## Limitacions conegudes (deliberades)

- tkinter: sense `Canvas`, `Toplevel`, `columnconfigure()`/`rowconfigure()`,
  `bind()` genèric (només `command=`), `PhotoImage.width()/height()` → `0`.
- MQTT: només `wss` (cap TCP cru), subconjunt de l'API paho (sense
  `tls_set()`, `will_set()`, reconnexió automàtica configurable, etc.).

## Tasques pendents (actualitzat)

1. ~~Provar fases 1-8 juntes~~ — fet.
2. ~~Integració MQTT/Paho~~ — **fet** (Model B, dins el worker).
3. ~~Selector d'exemples predefinits~~ — **fet** (4 categories, 16 entrades).
4. Repassar/netejar comentaris desactualitzats (esp. les referències a
   `python3 server.py` que ara haurien de parlar de nginx/docker-compose).
5. ~~Verificar que `nginx.conf` envia capçaleres COOP/COEP correctament~~ —
   **fet i verificat** (`curl -sI`), i ampliat amb `Cross-Origin-Resource-
   Policy` per poder-se incrustar en un `iframe` d'una pàgina amb COEP
   actiu (vegeu "Incrustar py.binefa.cat dins d'un iframe").
6. ~~`#run`/`#open` a la URL~~ — **fet**, vegeu la secció dedicada més amunt
   i `ajuda.md`.
7. ~~Document explicatiu per a Jordi/alumnes~~ — **fet**, `ajuda.md`
   (pendent nomes de convertir-lo a `ajuda.html` un cop validat del tot).
8. ~~Tk.update() / combinar tkinter amb codi asincron (MQTT)~~ — **fet**,
   vegeu "tkinter + async" més amunt.
9. ~~Maximitzar finestra Tk + columnes redimensionables~~ — **fet**.
10. Pendent: botó per restablir les proporcions de columnes al valor per
    defecte (1:1:1) si l'alumne les deixa molt desquadrades — no fet, nomes
    suggerit.
11. Pendent: revisar si altres exemples existents (no nomes els nous de
    MQTT+tkinter) es beneficiarien del patró `Tk.update()` en lloc de
    `mainloop()` — no fet, nomes els exemples nous el fan servir.
12. Pendent: convertir `ajuda.md` a `ajuda.html` amb l'estil visual de l'IDE.
13. ~~`pahoSnap00.html` (split py.binefa.cat + Snap!, amb tema MQTT
    aleatori compartit) + capçaleres COOP/COEP/CORP a `broker.binefa.cat`
    (Traefik) i `py.binefa.cat` (nginx)~~ — **fet i verificat**, vegeu
    "Incrustar py.binefa.cat dins d'un iframe" més amunt.
14. ~~Patró perquè un mateix script (`tk_mqtt_smm.py`) funcioni tant al
    navegador com des d'un terminal real (tkinter/paho-mqtt reals)~~ —
    **fet i documentat**, vegeu `CONTEXT_AI_py_binefa_cat.md` (detecció
    d'entorn amb `asyncio.get_running_loop()`, `ensure_future()` vs.
    `asyncio.run()`, cua thread-safe per als callbacks MQTT reals, rutes de
    fitxers, `Tk.protocol()` només al desktop). Descobert que
    `Label.config(image=..., text=...)` alhora trenca la renderització de
    la imatge al shim — cal separar-ho sempre en dues crides o ometre
    `text=`.
15. ⚠️ **Descobert i corregit**: el patró `asyncio.ensure_future()` (punt
    14) trenca el botó "Interromp" de l'IDE, no només l'estat de text —
    provat als exemples `mqtt_publica`/`mqtt_subscriu`/`mqtt_pub_sub`
    (revertits al patró `await` solt de sempre; la versió amb
    `async def`/`asyncio.run()` es va deixar en un fitxer `*_terminal.py`
    a part, mai al `main.py` del navegador). Regla pràctica documentada a
    `CONTEXT_AI_py_binefa_cat.md`: nomes aplicar el patró de detecció
    d'entorn al `main.py` quan el programa es tanca per un altre mitjà que
    no sigui "Interromp" (p. ex. la X d'una finestra tkinter, com
    `tk_mqtt_smm`); si depèn d'"Interromp", fitxer de terminal a part.
