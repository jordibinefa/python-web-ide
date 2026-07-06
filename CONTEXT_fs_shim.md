# Context: fs_shim.py — fitxers de dades creats pel codi Python

Aquest document tracta **específicament el shim de fitxers de dades**
(`fs_shim.py`): l'especificació original tancada amb Jordi i com s'ha
implementat. Si comences un xat nou per tocar només aquest shim, adjunta
aquest fitxer + `fs_shim.py` + `worker.js` + `index.html`.

> Substitueix `contextFitxersPyBinefaCat.md` (fusionat i eliminat): aquell
> document era l'especificació *abans* d'implementar-lo; aquest cobreix
> l'especificació **i** com ha quedat construït.
>
> Per a l'arquitectura general del projecte (desplegament, `#run:`/
> `#open:`, altres shims, incrustació en `iframe`...), fes servir
> `CONTEXT_tkinter_shim.md` — aquest document només parla de `fs_shim.py`.

---

## Motivació i espec original (tancada amb Jordi, 2026-07-06)

Que quan el codi Python de l'alumne creï/escrigui un fitxer amb
`open(...)` (p.ex. `open("demofile3.txt", "w")`), aparegui una pestanya
nova a l'IDE mostrant-ne el contingut — a l'estil d'onlinegdb.com — i que
aquest fitxer s'inclogui a l'exportació ZIP del projecte.

Decisions tancades:

1. **Actualització de la pestanya**: NO sobreescriure sempre en silenci.
   - Si la pestanya NO té edicions pendents de l'usuari → actualitzar-la
     sola quan arriba contingut nou.
   - Si SÍ que en té (l'usuari l'està editant i encara no ha tornat a
     prémer "Executa") → no sobreescriure-la; mostrar un avís discret dins
     la pestanya ("el codi ha escrit un contingut nou aquí") amb un botó
     "Refresca" (i "Ignora"/tancar l'avís).
2. **Persistència**: els fitxers de dades sobreviuen entre execucions
   ("Executa" repetit), NO es netegen com els `.py`. Com que "Interromp"
   recrea el worker sencer (Pyodide nou, FS virtual buit), aquest estat ha
   de viure al FIL PRINCIPAL (igual que `files`/`assets`) i reenviar-se
   sencer a cada "Executa" — no es pot confiar en que el worker el
   conservi sol.
   - Tancar la pestanya (×) demana confirmació amb tres opcions:
     **Elimina l'arxiu** (desapareix de l'estat, deixa d'enviar-se al
     worker, el codi el trobarà com si mai hagués existit a la següent
     execució) / **Només tanca la pestanya** (deixa d'aparèixer i
     d'exportar-se, però l'arxiu es continua enviant al worker perquè el
     codi el pugui seguir fent servir) / **Cancel·la**.
3. **Fitxers binaris** (`open(..., "wb")` o contingut no decodificable com
   a UTF-8): mostrar només `"Fitxer binari, N bytes"` — mai el contingut
   real ni en base64.
4. **Editable**: SÍ. Flux esperat: el codi crea/escriu el fitxer → apareix
   la pestanya → l'usuari edita una línia a mà → torna a prémer "Executa"
   → el codi Python, en tornar a obrir/llegir aquell fitxer, veu el canvi
   fet a l'editor (igual que ja passa amb els `.py`: el contingut de
   l'editor es reenvia sencer just abans de cada execució).
5. **Exportació ZIP**: només els fitxers de dades amb la pestanya
   VISIBLE (no tancada) s'inclouen al ZIP, igual que `files`/`assets`.
6. **Sense subdirectoris**: només fitxers directament a l'arrel (`/nom`),
   cap suport per a `os.mkdir()`/rutes niades en aquesta primera versió.

---

## Com ha quedat implementat

**Decisió de disseny**: embolcallar `builtins.open` (monkeypatch directe,
NO un mòdul nou a `sys.modules` — a diferència de tkinter/paho/requests,
`open()` ja és global i qualsevol codi que hi accedeixi per sota ja veu la
versió vigilada). Només intervé a `close()`/`flush()` (mai a cada
`write()`, per no ser massa xerraire), llegint el contingut actual del
fitxer real i notificant-ho al fil principal amb
`__file_changed__(nom, contingut, es_text, mida_bytes)` — un pont
*fire-and-forget* (sense `Atomics`/`SharedArrayBuffer`, no cal resposta),
injectat pel `worker.js` igual que `__send_image__`.

- **Exclusions**: `worker.js` crida `__fs_configure__(noms_json)` abans de
  cada `'run'` amb els noms (`.py` del projecte + assets/imatges) que MAI
  s'han de tractar com a "fitxer de dades nou".
- **Persistència entre execucions**: com que "Interromp" recrea el worker
  sencer (FS virtual buit), l'estat (`dataFiles`) viu al **fil principal**
  (`index.html`), amb entrades `{ name, content, isText, size, tabOberta,
  brut, pendent }`. `worker.js` els reescriu a `/nom` a l'inici de cada
  `'run'`, igual que `assets`.
- **Estat "brut"**: si l'usuari edita la pestanya a mà i encara no ha
  tornat a prémer "Executa", un `fileChanged` entrant NO sobreescriu en
  silenci — es guarda a `pendent` i es mostra un avís amb botons
  "Refresca"/"Ignora" (`fsBanner` a `index.html`).
- **Fitxers binaris**: es detecten amb `UnicodeDecodeError` en decodificar
  com a UTF-8; es notifiquen en base64 (`es_text=False`), però la UI
  **mai** mostra el contingut real ni en base64 — només `"Fitxer binari, N
  bytes"`.
- **Tancar la pestanya**: modal de 3 opcions (`fsModalOverlay`) — Elimina
  l'arxiu / Només tanca la pestanya (segueix enviant-se al worker, no
  reapareix) / Cancel·la.
- **Exportació ZIP**: només les entrades amb `tabOberta === true`.
- **Sense subdirectoris** en aquesta v0 (`_nom_arrel()` a `fs_shim.py`
  retorna `None` si el path té una `/` addicional — el fitxer s'escriu
  igual, només no genera pestanya).

### Peces concretes (per no haver de redescobrir-ho)

1. **`fs_shim.py`**: classe `_FitxerVigilat` (embolcall d'`io.IOBase` que
   delega TOTA l'API de fitxer al fitxer real, i només intercepta
   `close()`/`flush()` per notificar). `_open_vigilat()` decideix si cal
   embolcallar (mode d'escriptura + no exclòs + `__file_changed__`
   disponible) o retornar el fitxer real sense tocar.
2. **`worker.js`**: `__file_changed__` (bridge cap al fil principal, sense
   Atomics), registre del shim un únic cop a `setup()` (monkeypatch, no
   cal re-registrar-lo cada `'run'` com tkinter/paho), i a cada `'run'`:
   escriptura de `dataFiles` al FS virtual (com `assets`) + crida a
   `__fs_configure__` amb els noms exclosos.
3. **`index.html`**: estat `dataFiles`, pestanyes amb icona/vora
   distintiva, textarea propi (no CodeMirror) per a la pestanya de dades
   activa, banner de "brut"/`pendent`, modal de 3 opcions en tancar,
   inclusió condicionada a l'exportació ZIP, sincronització del textarea
   abans de cada "Executa".

---

## Parany important: cwd de Pyodide i el path exacte

`fs_shim.py` **NO** força el path a `/nom` en reobrir el fitxer per
notificar-lo — reobre amb el path EXACTE que l'alumne ha passat a
`open()` (relatiu o absolut), guardat a `self._path` a `_FitxerVigilat`.
Això és deliberat: no es pot donar per fet quin és el cwd real de Pyodide
sense verificar-ho (versions diferents de Pyodide han fet servir
`/home/pyodide` per defecte, no `/`).

La solució final combina dues bandes:
- `fs_shim.py` reobre amb el path tal qual (mai "corregit").
- `worker.js` fixa explícitament `pyodide.FS.chdir('/')` a `setup()`,
  perquè un `open("nom.txt", "w")` relatiu de l'alumne coincideixi amb
  l'arrel on `worker.js` restaura `assets`/`dataFiles` a cada `'run'`.

Sense el `chdir('/')`, un `open()` relatiu podria escriure en un lloc i
`worker.js` restaurar/esperar trobar el fitxer a un altre — els dos
costats havien d'estar d'acord sobre quin és "l'arrel".

---

## Limitacions conegudes (deliberades, v0)

- Sense subdirectoris (només fitxers a l'arrel).
- Fitxers binaris mostrats només com a `"Fitxer binari, N bytes"` — mai
  editables ni visualitzables.
- "Elimina l'arxiu" en tancar la pestanya no és reversible.
- Sense límit de mida explícit per fitxer de dades (a diferència dels
  `.py`/firmware d'altres projectes de Jordi) — pendent de valorar si cal.

## Portabilitat (fora del navegador)

Aquest shim només es carrega dins l'entorn del navegador (`worker.js`
l'injecta). Fora d'aquest entorn, el mateix codi Python amb `open(...)` es
comporta exactament com el real: cap efecte advers, cap notificació, cap
overhead — vegeu `CONTEXT_AI_py_binefa_cat.md` §10 per als matisos de
portabilitat (efecte només-UI, no funcional).

## Tasques pendents / possibles ampliacions futures

- Cap de moment — la v0 cobreix l'especificació tancada sencera.
- Si mai cal: suport per a subdirectoris (`os.mkdir()` + rutes niades),
  o un límit de mida per fitxer de dades.
