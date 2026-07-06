let pyodideReadyPromise = null;

async function setup(pyodideBase, sharedBuffer, tkSharedBuffer, tkinterShimSource, mqttUrl, pahoUrl, pahoShimSource, fsShimSource, httpShimSource) {
  // pyodideBase arriba com a URL absoluta calculada pel fil principal,
  // perque un worker creat des d'un Blob no te ubicacio real per resoldre camins relatius.
  self.importScripts(pyodideBase + 'pyodide.js');

  // ── MQTT (model B): MQTT.js + el wrapper paho-mqtt.js viuen DINS el worker ──
  // Es carreguen amb importScripts (URLs absolutes calculades pel fil principal).
  // Si falten els fitxers vendor, NO trenquem tot l'IDE: deixem MQTT inactiu i
  // el shim de Python ja dona un error clar nomes quan algu fa mqtt.Client().
  self.__mqttLoaded = false;
  try {
    if (mqttUrl) self.importScripts(mqttUrl);   // defineix self.mqtt
    if (pahoUrl) self.importScripts(pahoUrl);   // defineix self.paho.mqtt.client
    self.__mqttLoaded = (typeof self.mqtt !== 'undefined' && typeof self.paho !== 'undefined');
  } catch (e) {
    console.error('[py-web] MQTT no disponible (vendor):', e);
  }

  const pyodide = await loadPyodide({ indexURL: pyodideBase });
  pyodide.setStdout({ batched: (msg) => self.postMessage({ type: 'stdout', text: msg }) });
  pyodide.setStderr({ batched: (msg) => self.postMessage({ type: 'stderr', text: msg }) });

  // Fixem el cwd del FS virtual a l'arrel: TOT (fitxers .py, assets,
  // fitxers de dades) s'escriu sempre a '/' des del fil principal, aixi
  // que qualsevol open() relatiu del codi de l'alumne (p.ex.
  // open("demofile3.txt", "w")) ha d'apuntar tambe a l'arrel -- si no,
  // fs_shim.py reobriria un fitxer diferent del que acaba d'escriure just
  // abans, i el "restore" entre execucions (worker.js escriu els
  // dataFiles coneguts a '/' abans de cada 'run') no coincidiria mai amb
  // on el codi de l'alumne espera trobar-los.
  pyodide.FS.chdir('/');

  // El codi de l'alumne s'executa amb runPythonAsync (un exec(), no un script
  // real), aixi que Python NO afegeix automaticament el directori actual a
  // sys.path com faria amb "python main.py" des de terminal. Sense aixo,
  // "import altre_fitxer" (on altre_fitxer.py es una altra pestanya del
  // projecte, escrita a '/') mai pot funcionar.
  pyodide.runPython("import sys\nif '/' not in sys.path:\n    sys.path.insert(0, '/')");

  // Override input() per comunicar-se de forma sincronа amb el fil principal
  // via SharedArrayBuffer + Atomics.wait (bloqueja el worker, no el navegador).
  const ctrlArr = new Int32Array(sharedBuffer, 0, 2); // [0]=estat, [1]=longitud

  pyodide.globals.set('__js_input__', (prompt = '') => {
    const promptStr = String(prompt ?? '');
    Atomics.store(ctrlArr, 0, 0);                       // Reinicia l'estat a "esperant"
    self.postMessage({ type: 'requestInput', prompt: promptStr });
    Atomics.wait(ctrlArr, 0, 0);                        // Bloqueja fins que arribi la resposta
    const len   = ctrlArr[1];
    // .slice() copia els bytes a un ArrayBuffer normal (TextDecoder rebutja vistes SharedArrayBuffer)
    const bytes = new Uint8Array(sharedBuffer, 8, len).slice();
    return new TextDecoder().decode(bytes);
  });

  pyodide.runPython('import builtins; builtins.input = __js_input__');

  // Injecta la funció per enviar imatges (matplotlib) al fil principal
  pyodide.globals.set('__send_image__', (data) => {
    self.postMessage({ type: 'image', data });
  });

  // ── Pont "fire-and-forget" per al shim de fitxers de dades (fs_shim.py) ──
  // A diferència de __tk_call__ (Atomics.wait, bloqueja el worker), aquest
  // pont no necessita resposta: el fil principal ja sap tot el que li cal
  // amb aquesta única crida (nom, contingut, si és text, mida en bytes).
  pyodide.globals.set('__file_changed__', (name, content, isText, size) => {
    self.postMessage({ type: 'fileChanged', name, content, isText, size });
  });

  // Igual que amb tkinter/paho: el shim s'executa dins el seu propi mòdul
  // (per no embrutar l'espai de noms global amb helpers interns com
  // _FitxerVigilat), però com que fs_shim NOMÉS necessita monkey-patchejar
  // builtins.open (no cal registrar-lo a sys.modules com un paquet
  // importable), n'hi ha prou d'executar-lo un únic cop aquí.
  pyodide.globals.set('__fs_shim_source__', fsShimSource);
  pyodide.runPython(`
import builtins, types
builtins.__file_changed__ = __file_changed__
_fs_shim_mod = types.ModuleType('_fs_shim')
exec(__fs_shim_source__, _fs_shim_mod.__dict__)
del _fs_shim_mod
`);

  // ── Registre del shim de requests (http_shim.py) ──────────────────────
  // A diferencia de tkinter/paho, aquest shim NO te estat intern que calgui
  // netejar entre execucions (cada get()/post() es independent), aixi que
  // amb registrar-lo UN COP aqui n'hi ha prou -- no cal repetir-ho a cada
  // 'run' com sí que cal amb tkinter (ids/callbacks) o paho (connexions
  // obertes). Fa servir XMLHttpRequest directament (from js import
  // XMLHttpRequest dins el propi http_shim.py): no calen ponts ni
  // SharedArrayBuffer, perque una petició sincrona dins un Worker ja
  // bloqueja nomes el worker, mai el navegador.
  pyodide.globals.set('__http_shim_source__', httpShimSource);
  pyodide.runPython(`
import sys, types
_requests_mod = types.ModuleType('requests')
exec(__http_shim_source__, _requests_mod.__dict__)
sys.modules['requests'] = _requests_mod
del _requests_mod
`);

  // ── Pont sincron generic per al shim de tkinter ──────────────────────
  // Mateix patro que __js_input__, pero amb un SharedArrayBuffer propi
  // (separat del d'input(), perque no es barregin esperes pendents).
  //
  // IMPORTANT: __tk_call__ es defineix SEMPRE (amb o sense SharedArrayBuffer)
  // i el modul tkinter es registra SEMPRE a sys.modules — independentment
  // de si tkSharedBuffer existeix. Si tot aixo quedava dins un "if
  // (tkSharedBuffer)", sense COOP/COEP el modul mai es registrava i
  // Pyodide acabava mostrant el seu propi "ModuleNotFoundError: tkinter"
  // (el seu finder a sys.meta_path, que guanya sempre a sys.path/sys.modules
  // buit). Ara, sense SharedArrayBuffer, "import tkinter" funciona igual,
  // i nomes falla — amb un missatge clar — quan es crida de veritat un
  // widget (Tk(), Button(), etc.).
  if (tkSharedBuffer) {
    const tkCtrl = new Int32Array(tkSharedBuffer, 0, 2);

    pyodide.globals.set('__tk_call__', (op, payloadJson) => {
      Atomics.store(tkCtrl, 0, 0);
      self.postMessage({ type: 'tkCall', op, payload: payloadJson });
      Atomics.wait(tkCtrl, 0, 0);                       // bloqueja el worker, no el navegador
      const len   = tkCtrl[1];
      const bytes = new Uint8Array(tkSharedBuffer, 8, len).slice();
      return new TextDecoder().decode(bytes);
    });

    // El shim s'executara dins un modul amb el seu propi namespace (vegeu
    // sota), aixi que __tk_call__ nomes sera visible si el posem a builtins
    // — exactament com ja fas amb "builtins.input = __js_input__" per input().
    pyodide.runPython('import builtins; builtins.__tk_call__ = __tk_call__');
  } else {
    // Sense SharedArrayBuffer (falten les capçaleres COOP/COEP de server.py):
    // "import tkinter" seguira funcionant, pero qualsevol us real donara
    // un error Python explicatiu en lloc del ModuleNotFoundError de Pyodide.
    pyodide.runPython(`
import builtins
def __tk_call_sense_sab__(op, payload_json):
    raise RuntimeError(
        "tkinter necessita SharedArrayBuffer (capçaleres COOP/COEP). "
        "Serveix aquesta pàgina amb 'python3 server.py' (no l'obris com a fitxer local)."
    )
builtins.__tk_call__ = __tk_call_sense_sab__
`);
  }

  // ── Pont NO bloquejant per a Tk.update() ──────────────────────────────
  // A diferencia de __tk_call__ (Atomics.wait, bloqueja el worker), aquesta
  // funcio nomes llegeix/buida una cua JS normal (self.__tkEventQueue,
  // omplerta via postMessage des del fil principal cada cop que hi ha un
  // clic — vegeu tkFireEvent). No necessita SharedArrayBuffer. Permet que
  // codi Python asincron faci polling d'esdeveniments tkinter sense mai
  // bloquejar el worker (i per tant sense bloquejar tampoc MQTT.js, que hi
  // viu al mateix fil).
  pyodide.globals.set('__tk_poll_events__', () => {
    const evs = self.__tkEventQueue || [];
    self.__tkEventQueue = [];
    return JSON.stringify(evs);
  });
  pyodide.runPython('import builtins; builtins.__tk_poll_events__ = __tk_poll_events__');

  // Pyodide intercepta 'import tkinter' amb un finder propi (a sys.meta_path)
  // que sempre guanya a sys.path, encara que hi haguem afegit el nostre
  // directori — per aixo NO l'escrivim al FS ni toquem sys.path.
  // En lloc d'aixo, executem el shim dins un modul nou i el registrem
  // directament a sys.modules['tkinter']: Python consulta aquesta memoria
  // cau ABANS de cap finder, aixi que el de Pyodide mai s'arriba a cridar.
  // Aquest registre es fa SEMPRE, fora del if/else anterior.
  pyodide.globals.set('__tkinter_shim_source__', tkinterShimSource);
  pyodide.runPython(`
import sys, types
_tkinter_mod = types.ModuleType('tkinter')
exec(__tkinter_shim_source__, _tkinter_mod.__dict__)
sys.modules['tkinter'] = _tkinter_mod
del _tkinter_mod
`);

  // ── Registre del paquet paho a sys.modules ───────────────────────────
  // Mateixa filosofia que tkinter: registrem paho / paho.mqtt /
  // paho.mqtt.client directament a sys.modules perque "import
  // paho.mqtt.client" no toqui mai el FS ni cap finder. El shim de Python
  // (paho_shim.py) envolta l'objecte JS globalThis.paho.mqtt.client.Client.
  pyodide.globals.set('__paho_shim_source__', pahoShimSource);
  pyodide.runPython(`
import sys, types
_paho = types.ModuleType('paho');            _paho.__path__ = []
_paho_mqtt = types.ModuleType('paho.mqtt');  _paho_mqtt.__path__ = []
_paho_client = types.ModuleType('paho.mqtt.client')
exec(__paho_shim_source__, _paho_client.__dict__)
_paho_mqtt.client = _paho_client
_paho.mqtt = _paho_mqtt
sys.modules['paho'] = _paho
sys.modules['paho.mqtt'] = _paho_mqtt
sys.modules['paho.mqtt.client'] = _paho_client
del _paho, _paho_mqtt, _paho_client
`);

  return pyodide;
}

self.onmessage = async (event) => {
  const msg = event.data;

  if (msg.type === 'tkEvent') {
    // Cua no bloquejant consultada per Tk.update() (sense Atomics/SAB).
    // No cal esperar pyodideReadyPromise: nomes escriu a un array normal.
    if (!self.__tkEventQueue) self.__tkEventQueue = [];
    self.__tkEventQueue.push(msg.event);
    return;
  }

  if (msg.type === 'init') {
    pyodideReadyPromise = setup(msg.pyodideBase, msg.sharedBuffer, msg.tkSharedBuffer, msg.tkinterShimSource, msg.mqttUrl, msg.pahoUrl, msg.pahoShimSource, msg.fsShimSource, msg.httpShimSource);
    pyodideReadyPromise.then(() => self.postMessage({ type: 'ready' }));
    return;
  }

  const pyodide = await pyodideReadyPromise;


  if (msg.type === 'run') {
    self.postMessage({ type: 'busy' });
    self.__tkEventQueue = [];   // neteja events sobrants d'una execucio anterior
    try {
      // Elimina els .py existents a '/' per garantir coherencia amb el projecte actual
      for (const nom of pyodide.FS.readdir('/')) {
        if (nom.endsWith('.py')) pyodide.FS.unlink('/' + nom);
      }
      // Escriu els fitxers del projecte actual
      for (const f of msg.files) {
        pyodide.FS.writeFile(f.path, f.content);
      }
      // Escriu els assets binaris (imatges per a PhotoImage), decodificats de base64
      for (const a of (msg.assets || [])) {
        const binari = atob(a.b64);
        const bytes  = new Uint8Array(binari.length);
        for (let i = 0; i < binari.length; i++) bytes[i] = binari.charCodeAt(i);
        pyodide.FS.writeFile('/' + a.name, bytes);
      }
      // Escriu els fitxers de dades coneguts pel fil principal (TOTS: tant
      // els de pestanya visible com els de pestanya tancada-però-no-
      // eliminada — fs_shim.py, no el fil principal, decideix si en genera
      // una de nova en re-escriure'ls). Com que "Interromp" recrea el
      // worker sencer (FS virtual buit), aquest estat viu al fil principal
      // i cal reenviar-lo sencer a cada 'Executa'.
      for (const df of (msg.dataFiles || [])) {
        if (df.isText) {
          pyodide.FS.writeFile('/' + df.name, df.content);
        } else {
          const binari = atob(df.content);
          const bytes  = new Uint8Array(binari.length);
          for (let i = 0; i < binari.length; i++) bytes[i] = binari.charCodeAt(i);
          pyodide.FS.writeFile('/' + df.name, bytes);
        }
      }
      // Informa fs_shim.py de quins noms MAI s'han de tractar com a "fitxer
      // de dades nou": els .py del projecte actual i els assets (imatges).
      // Els propis fitxers de dades NO s'exclouen (reobrir-los en escriptura
      // és el cas d'ús normal, i simplement actualitza la mateixa pestanya).
      {
        const exclosos = JSON.stringify(
          msg.files.map((f) => f.path.replace(/^\//, ''))
            .concat((msg.assets || []).map((a) => a.name))
        );
        pyodide.runPython(`__fs_configure__(${JSON.stringify(exclosos)})`);
      }
      // IMPORTANT: Python cacheja per directori quins fitxers hi ha en
      // importar (FileFinder/_path_importer_cache), i el FS virtual de
      // Pyodide no sempre actualitza l'mtime de '/' de manera que Python
      // ho detecti. Sense aixo, un "import" que ha fallat un cop (p.ex. un
      // nom de pestanya que no coincidia) pot seguir fallant per sempre
      // encara que el fitxer correcte ja hi sigui — Python no torna a
      // mirar el disc. invalidate_caches() força refrescar-ho cada cop.
      pyodide.runPython('import importlib; importlib.invalidate_caches()');
      // Carrega els paquets de Pyodide que el codi importa (numpy, pandas, etc.)
      self.postMessage({ type: 'status', text: 'Carregant paquets…' });
      // "requests" SEMPRE es el nostre shim (http_shim.py, registrat a
      // sys.modules a l'inici), mai el paquet real de Pyodide/micropip --
      // per aixo n'excloem les línies d'import nomes per a l'ESCANEIG de
      // paquets (loadPackagesFromImports no sap res de sys.modules, i
      // intentaria baixar-se requests+certifi+charset-normalizer+idna+
      // urllib3 sense necessitat, generant errors de xarxa confusos a la
      // consola encara que despres el codi real funcioni be igualment).
      // NOMES afecta aquesta cerca de paquets: pyodide.runPythonAsync()
      // de mes avall sempre fa servir el codi ORIGINAL sencer.
      const codiPerEscaneig = msg.code.replace(
        /^\s*(import\s+requests\b.*|from\s+requests\b.*)$/gm, ''
      );
      await pyodide.loadPackagesFromImports(codiPerEscaneig);
      // Pateja plt.show() perque enviï la imatge al fil principal en lloc d'obrir una finestra
      await pyodide.runPythonAsync(`
import os, sys
os.environ['MPLBACKEND'] = 'Agg'
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as _plt, io as _io, base64 as _b64
    def _mpl_show(*a, **kw):
        buf = _io.BytesIO()
        for n in _plt.get_fignums():
            _plt.figure(n).savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            __send_image__(_b64.b64encode(buf.read()).decode())
            buf.seek(0)
            buf.truncate()
        _plt.close('all')
    _plt.show = _mpl_show
except (ImportError, ModuleNotFoundError):
    pass
`);
      // Invalida els moduls cachejats per permetre re-importar versions editades.
      // 'tkinter' s'exclou explicitament: si l'alumne te una pestanya anomenada
      // tkinter.py (col·lisio de nom amb el shim), no volem que aquesta
      // invalidacio esborri el nostre sys.modules['tkinter'].
      const mods = JSON.stringify(msg.moduleNames.filter((m) => m !== 'tkinter' && m !== 'paho' && m !== 'requests'));
      pyodide.runPython(`import sys\nfor m in ${mods}:\n    sys.modules.pop(m, None)`);
      // Re-registra el shim de tkinter SEMPRE i incondicionalment (no depen
      // de si encara hi era a sys.modules): aixo garanteix tant que mai
      // quedi trencat com que cada execucio comenci amb estat net (ids,
      // callbacks, finestres destruides), perque es un modul nou cada cop.
      pyodide.runPython(`
import sys, types
_tkinter_mod = types.ModuleType('tkinter')
exec(__tkinter_shim_source__, _tkinter_mod.__dict__)
sys.modules['tkinter'] = _tkinter_mod
del _tkinter_mod
`);
      // MQTT: tanca qualsevol client obert en una execucio anterior (nomes
      // pot passar si es re-executa sense reiniciar l'entorn) i re-registra
      // el shim de paho amb estat net, exactament igual que tkinter.
      if (self.__pahoCleanup) { try { self.__pahoCleanup(); } catch (_) {} }
      pyodide.runPython(`
import sys, types
_paho = types.ModuleType('paho');            _paho.__path__ = []
_paho_mqtt = types.ModuleType('paho.mqtt');  _paho_mqtt.__path__ = []
_paho_client = types.ModuleType('paho.mqtt.client')
exec(__paho_shim_source__, _paho_client.__dict__)
_paho_mqtt.client = _paho_client
_paho.mqtt = _paho_mqtt
sys.modules['paho'] = _paho
sys.modules['paho.mqtt'] = _paho_mqtt
sys.modules['paho.mqtt.client'] = _paho_client
del _paho, _paho_mqtt, _paho_client
`);
      // Variables provinents del hash de la URL (#run:/#open:...&clau=valor).
      // Es re-injecten SEMPRE abans de cada execucio -- mateix patró que
      // tkinter/paho -- perque l'alumne pugui prémer "Executa" repetidament
      // sense perdre-les. Sempre com a str (mai coerció de tipus). Des del
      // codi Python es poden detectar amb 'clau' in globals().
      for (const [k, v] of Object.entries(msg.vars || {})) {
        if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(k)) {
          self.postMessage({ type: 'stderr', text: `[py-web] Nom de variable no vàlid a la URL, s'ignora: "${k}"` });
          continue;
        }
        pyodide.globals.set(k, v);
      }
      // Actualitza el text d'estat abans d'executar: sense aixo, un programa
      // que no acaba mai (p.ex. 'while not aturat: ... await asyncio.sleep()',
      // com les demos MQTT/tkinter) es queda per sempre amb el text
      // "Carregant paquets..." encallat, ja que 'done' nomes arriba quan
      // runPythonAsync() es resol -- i en un bucle infinit, mai ho fa.
      self.postMessage({ type: 'status', text: 'Executant…' });
      await pyodide.runPythonAsync(msg.code);
    } catch (err) {
      let text = String(err);
      // Si l'error es un ModuleNotFoundError, afegim quins moduls .py hi ha
      // realment al projecte (sol ser una pestanya amb un nom que no
      // coincideix exactament amb l'import — com 'crida.py' vs 'import crida01').
      if (text.includes('ModuleNotFoundError')) {
        const disponibles = msg.moduleNames.filter((m) => m !== 'tkinter');
        text += `\n[Suggeriment] Mòduls .py disponibles al projecte (segons el nom EXACTE de la pestanya): ${JSON.stringify(disponibles)}`;
      }
      self.postMessage({ type: 'stderr', text });
    }
    self.postMessage({ type: 'done' });
  }
};
