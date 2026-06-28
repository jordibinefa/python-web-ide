# Guia: IDE Python al navegador per a classe (substitut d'onlinegdb.com)

## 0. Objectiu

Eina web, 100% client-side, per a fins a 30 alumnes simultanis, que substitueixi onlinegdb.com a classe. Ha de tenir:

- Editor de codi amb ressaltat de sintaxi Python (tema **clar**).
- Pestanyes per crear/editar/esborrar diversos fitxers `.py`, important-se entre ells.
- Consola d'execució que no es bloquegi encara que el codi de l'alumne tingui bucles llargs.
- Autoguardat al navegador + exportació/importació en ZIP.
- Tot servit com a fitxers estàtics des del VPS (mateix patró que iotv.binefa.cat / iot02sim).

## 1. Punt de partida ja validat (no cal redescobrir-ho)

Aquestes peces ja funcionen, provades en local sense errors de consola:

- **Pyodide dins d'un Web Worker**, vendoritzat a `vendor/pyodide/0.28.3/` (no CDN extern: evita CORS i dependència de xarxa externa el dia de classe).
- El worker rep la **URL base per missatge** (`{type:'init', pyodideBase}`), calculada pel fil principal amb `new URL('vendor/pyodide/0.28.3/', window.location.href)`. Mai hardcodejar la ruta dins el worker: un worker creat amb `Blob` no en pot resoldre de relatives.
- `pyodide.setStdout` / `setStderr` amb `batched` per fer arribar la sortida a la consola via `postMessage`.
- Escriptura de fitxers al sistema de fitxers virtual de Pyodide (`pyodide.FS.writeFile`) i `import` entre ells funcionant (cal `sys.path.insert(0, '/')` i invalidar `sys.modules` abans de cada execució si es vol permetre re-importar un fitxer modificat).
- El fitxer de referència és `prova-pyodide-worker.html` — Claude Code l'ha de llegir com a punt de partida real, no com a exemple a ignorar.

**Decisions ja preses, no tornar-les a obrir sense motiu:**
- Editor: **CodeMirror 6**, tema **clar** (no fosc).
- Persistència: **autoguardat** (localStorage o IndexedDB, a decidir per volum de dades) **+ exportació/importació en ZIP**.

## 2. Arquitectura proposada

```
/ (arrel servida pel VPS)
├── index.html
├── /vendor/pyodide/0.28.3/        ← ja existeix, no tocar
├── /vendor/codemirror/            ← afegir (vendoritzat, mateix motiu que Pyodide)
├── /src/
│   ├── app.js                     ← orquestra editor + pestanyes + worker + consola
│   ├── pyodide-worker.js          ← evolució del worker ja validat
│   ├── file-manager.js            ← model de fitxers en memòria + localStorage/IndexedDB
│   ├── zip-export.js              ← exportar/importar projecte (pot reaprofitar JSZip de sB0/sAi)
│   └── console-panel.js
└── /style/
```

### Flux d'execució (Run)
1. L'usuari prem "Executa".
2. `app.js` envia al worker tots els fitxers oberts del projecte (`writeFile` per cadascun).
3. Després envia `run` amb el contingut del fitxer "principal" (el que té el focus, o un marcat explícitament com a entrada).
4. El worker neteja `sys.modules` dels noms de fitxer del projecte (per permetre re-importar versions editades) i executa.
5. Stdout/stderr arriben en streaming a la consola.

### Interrupció de bucles infinits reals
Un Worker no es pot interrompre net a mig càlcul síncron. Si cal aturar:
- `worker.terminate()` + crear un worker nou + tornar a enviar `init`.
- Cal repetir la inicialització de Pyodide (cost: uns segons). És acceptable per a un cas d'aula puntual, però val la pena avisar l'alumne ("S'està reiniciant l'entorn...") perquè no sembli que s'ha penjat.

## 3. Pla de sessió amb Claude Code (per etapes, no tot de cop)

Seguint el teu estil de treball: canvis mínims, confirmar abans d'actuar, lliurar fitxers complets, validar pas a pas.

**Abans de començar**, crea un `CLAUDE.md` a l'arrel del repo amb:
```markdown
- Abans de fer cap canvi, explica el pla i espera confirmació.
- Canvis mínims i quirúrgics; evita reescriptures grans.
- Comentaris de codi en català.
- Lliura sempre fitxers complets, no fragments.
- Valida pas a pas: un canvi petit, prova al navegador, després el següent.
- El prototip prova-pyodide-worker.html és la base validada del worker: no reinventar-lo, evolucionar-lo.
```

**Etapa 1 — Esquelet i editor**
Substituir el `<textarea>` del prototip per CodeMirror 6 (tema clar), mantenint exactament la mateixa lògica de worker que ja funciona. Criteri d'èxit: el codi d'exemple actual s'executa igual que ara, només canvia l'editor.

**Etapa 2 — Pestanyes / múltiples fitxers**
Model de fitxers en memòria (nom, contingut). UI de pestanyes per crear/renombrar/esborrar. En executar, tots els fitxers del projecte es escriuen al FS virtual abans de córrer el principal. Criteri d'èxit: dos fitxers, un important l'altre, funcionant amb pestanyes (ja no amb els dos quadres de text fixos del prototip).

**Etapa 3 — Consola i control d'execució**
Millorar la consola (netejar, copiar sortida) i implementar "Interromp" amb `terminate()` + reinicialització. Criteri d'èxit: un bucle infinit es pot aturar des de la interfície.

**Etapa 4 — Persistència**
Autoguardat (cada canvi o amb un petit debounce) a localStorage/IndexedDB. Exportar projecte sencer a ZIP i importar-lo de nou. Criteri d'èxit: recarregar la pàgina no perd la feina; un ZIP exportat es pot tornar a importar i queda idèntic.

**Etapa 5 — Polit per a classe**
Disposició responsiva (pissarra/projector), missatges d'estat clars ("Carregant Python...", "Executant...", "S'està reiniciant l'entorn..."), prova de càrrega amb el `Cache-Control: immutable` ja configurat al VPS per a `vendor/pyodide`.

## 4. Coses a decidir durant el desenvolupament (no bloquegen l'inici)

- Necessites paquets més enllà de la stdlib (p. ex. `matplotlib` per a algun exemple visual)? Si sí, només cal vendoritzar el `.whl` corresponent i `loadPackage`; no cal canviar l'arquitectura.
- Vols un fitxer "principal" explícit per pestanya activa, o que sempre s'executi la pestanya que té el focus?
- Mida raonable de quota per a l'autoguardat (localStorage té un límit d'uns 5-10 MB per origen; per a codi Python és més que suficient).

## 5. Desplegament

Mateix patró que `iot02sim.binefa.cat`: directori estàtic servit per Traefik des del VPS, amb `vendor/pyodide/0.28.3/` ja configurat amb cache immutable. Quan hi hagi `vendor/codemirror/`, aplicar-hi la mateixa capçalera de cache (versió fixada al path).
