# Context: http_shim.py — `requests.get`/`post` des del navegador

Aquest document tracta **específicament el shim de `requests`**
(`http_shim.py`): la decisió d'arquitectura clau, l'API coberta i els
paranys ja trobats. Si comences un xat nou per tocar només aquest shim,
adjunta aquest fitxer + `http_shim.py` + `worker.js` + `index.html`.

> Per a l'arquitectura general del projecte (desplegament, `#run:`/
> `#open:`, altres shims, incrustació en `iframe`...), fes servir
> `CONTEXT_tkinter_shim.md` — aquest document només parla d'`http_shim.py`.
>
> Per als matisos de portabilitat cap a un terminal real (jerarquia
> d'excepcions, CORS, naturalesa bloquejant), vegeu `CONTEXT_AI_py_binefa_cat.md`
> §9 — aquell document és per a qui escriu codi d'exemple, no per a qui
> manté el shim en si.

---

## Motivació

Permetre que el codi de l'alumne faci crides HTTP reals (`requests.get`/
`requests.post`) des del navegador, per exemple contra un endpoint propi
(Node-RED, una API REST casolana...), sense necessitat de cap backend
intermedi ni de tocar `worker.js`/`index.html` per a cada cas d'ús nou.

## Decisió de disseny clau, diferent de TOTS els altres shims

**NO calen `__tk_call__`/`Atomics`/`SharedArrayBuffer`.** Un Web Worker ja
té el seu propi `XMLHttpRequest`, accessible des de Pyodide directament
amb `from js import XMLHttpRequest`. Fent la crida amb
`xhr.open(mètode, url, False)` (el `False` final = síncron), el navegador
ja bloqueja només el worker fins que arriba la resposta — exactament el
comportament que calia (que `requests.get(...)` es comporti com el
real, una crida bloquejant que retorna el resultat), sense haver de
construir cap pont propi cap al fil principal.

Això el fa estructuralment més senzill que `tkinter_shim.py` (sense estat
de widgets/ids/callbacks) o `fs_shim.py` (sense necessitat de notificar
res a la UI): és pràcticament un mòdul Python autònom, amb una sola
dependència externa (`from js import XMLHttpRequest`).

## Registre a `worker.js`

`sys.modules['requests']`, mateix patró que `paho` (mòdul nou dins
`types.ModuleType`, mai al FS ni `sys.path`), però amb una diferència
important:

- **Només es registra UN COP, a `setup()`** — a diferència de
  tkinter/paho, que es re-registren a CADA `'run'` (perquè tenen estat
  intern que cal netejar: ids de widgets, connexions MQTT obertes...).
  `http_shim.py` no té cap estat entre crides (`get()`/`post()` són
  independents), així que no cal repetir el registre.
- **Exclòs explícitament de la invalidació de mòduls** (
  `moduleNames.filter((m) => m !== 'tkinter' && m !== 'paho' && m !== 'requests')`)
  per si un alumne anomena una pestanya `requests.py`.

## Parany trobat i corregit: `loadPackagesFromImports()` no sap res de `sys.modules`

Abans d'executar el codi, `worker.js` crida
`pyodide.loadPackagesFromImports(msg.code)`, que escaneja el text a la
recerca d'`import` i intenta carregar els paquets *reals* de Pyodide que
reconeix — sense saber que `http_shim.py` ja ha registrat un `requests`
fals a `sys.modules`. Resultat observat: cada cop que el codi de l'alumne
feia `import requests`, `worker.js` intentava baixar-se el paquet real
`requests` + les seves dependències transitives (`certifi`,
`charset-normalizer`, `idna`, `urllib3`), generant errors de xarxa
confusos a la consola del navegador — en un cas concret, també un error
real d'integritat SHA-256 al CDN/proxy de Jordi, encara que el codi
acabava funcionant igualment gràcies al shim (que ja tenia
`sys.modules['requests']` ocupat abans que s'executés cap `import`).

**Fix**: abans de cridar `loadPackagesFromImports()`, es filtren amb una
expressió regular les línies `import requests`/`from requests import ...`
**NOMÉS** de la còpia de codi que s'escaneja per a l'auto-càrrega de
paquets — el codi que s'executa de veritat
(`runPythonAsync(msg.code)`) no es toca, conserva el `import requests`
original intacte.

```javascript
const codiPerEscaneig = msg.code.replace(
  /^\s*(import\s+requests\b.*|from\s+requests\b.*)$/gm, ''
);
await pyodide.loadPackagesFromImports(codiPerEscaneig);
```

## API coberta (v0, deliberadament mínima)

Decisió de Jordi: **"mínim: get/post amb json/params/headers"** (en lloc
de tots els verbs + `raise_for_status()` + excepcions pròpies) i
**"només text/JSON, sense binaris"**.

- `requests.get(url, params=None, headers=None)`
- `requests.post(url, data=None, json=None, params=None, headers=None)`
- `Response`: `.status_code`, `.ok`, `.text`, `.headers` (dict, parsejat
  de `xhr.getAllResponseHeaders()`), `.json()`.
- **NO hi ha**: `put`/`delete`/`patch`/`head`, `requests.Session`,
  `.raise_for_status()`, la jerarquia `requests.exceptions.*` (els errors
  de connexió/CORS surten com un `ConnectionError` builtin de Python —
  vegeu `CONTEXT_AI_py_binefa_cat.md` §9 per què això **no** és
  intercanviable amb `requests.exceptions.ConnectionError` real a l'hora
  de portar codi a un terminal), ni contingut de resposta binari.

## Altres limitacions conegudes (v0)

- `xhr.timeout` normalment no té efecte en peticions **síncrones**
  (limitació del navegador, no del shim) — un servidor molt lent
  bloquejarà el worker igualment, sense avís previ.
- CORS: el servidor remot ha de respondre amb
  `Access-Control-Allow-Origin` adequat — requisit del servidor, no
  d'aquest shim. Un `ConnectionError` en aquest cas es indistingible (des
  del punt de vista de l'alumne) d'un error de xarxa real.
- Petició **síncrona**: bloqueja tot el worker mentre està en curs,
  incloent `Tk.update()`/MQTT.js pendents al mateix fil — mateixa
  naturalesa que `input()`/`mainloop()` bloquejant.

## Portabilitat (fora del navegador)

Aquest mòdul només es carrega dins l'entorn del navegador (`worker.js`
l'injecta com a `'requests'` a `sys.modules`). Fora del navegador, un
`import requests` trobarà la biblioteca real (si està instal·lada) —
sense necessitat de detectar l'entorn (a diferència de tkinter/MQTT, no
hi ha conflicte síncron/asíncron aquí). Vegeu
`CONTEXT_AI_py_binefa_cat.md` §9 per als matisos que SÍ que cal conèixer
(superfície de l'API més petita al shim, jerarquia d'excepcions diferent).

## Tasques pendents / possibles ampliacions futures

- Ampliar amb més verbs (`put`/`delete`/`patch`) i una jerarquia
  d'excepcions pròpia (`requests.exceptions.*`) — deliberadament fora
  d'abast en la v0.
- Suport per a contingut binari a les respostes (imatges, fitxers
  descarregats) — es podria seguir el mateix patró que `fs_shim.py`
  (base64 + `isText=False`) si mai cal.
