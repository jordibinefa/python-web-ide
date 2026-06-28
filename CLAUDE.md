# Instruccions per a aquest projecte

- Abans de fer cap canvi, explica el pla i espera confirmació.
- Canvis mínims i quirúrgics; evita reescriptures grans.
- Comentaris de codi en català. Fes servir imperatiu i no infinitiu (Per exemple: Executa i no pas Executar)
- Lliura sempre fitxers complets, no fragments.
- Valida pas a pas: un canvi petit, prova al navegador, després el següent.
- prova-pyodide-worker.html és la base validada del worker (Pyodide en Web Worker, vendoritzat a vendor/pyodide/0.28.3/, URL base calculada pel fil principal i
  enviada per missatge). Evolucionar-la, no reinventar-la.
- Editor de codi: CodeMirror 6, tema clar.
- Persistència: autodesat (localStorage/IndexedDB) + exportació/importació ZIP.
- Vegeu guiaPythonWeb.md per al pla complet per etapes.
