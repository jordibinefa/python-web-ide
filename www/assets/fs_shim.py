# -*- coding: utf-8 -*-
"""
Shim de fitxers de dades per a l'IDE Python en navegador (Pyodide + Web Worker).

Quan el codi de l'alumne crea o escriu un fitxer amb open(...) (p.ex.
open("demofile3.txt", "w")), aquest modul ho detecta i n'avisa el fil
principal perque hi aparegui una pestanya nova a l'IDE -- a l'estil
d'onlinegdb.com -- i el fitxer s'inclogui a l'exportacio ZIP del projecte.

Vegeu contextFitxersPyBinefaCat.md per al disseny complet (ja tancat amb
Jordi el 2026-07-06): actualitzacio de pestanya nomes si no hi ha edicions
pendents, persistencia entre execucions gestionada pel fil principal,
fitxers binaris mostrats nomes com a "N bytes" (mai el contingut real),
editable, exportacio ZIP nomes de les pestanyes visibles, sense
subdirectoris en aquesta v0.

DISSENY
-------
Nomes intervenim a close()/flush() (MAI a cada write(), per no ser massa
xerraire): en aquest moment llegim el contingut ACTUAL del fitxer des del
FS virtual de Pyodide i notifiquem el fil principal amb
    __file_changed__(nom, contingut, es_text, mida_bytes)
Es un pont "fire-and-forget" (sense resposta, sense Atomics/SharedArrayBuffer
-- a diferencia de __tk_call__, aqui no cal bloquejar el worker per res),
injectat pel worker.js igual que __send_image__.

Exclusions (mai tractats com a "fitxer de dades nou"):
- els .py del projecte (son pestanyes de codi, no fitxers de dades)
- els assets (imatges pujades amb el boto "Importa imatge...")
Aquesta llista la fixa el worker.js just abans de cada execucio, cridant
__fs_configure__(noms_json) amb els noms (sense '/') a excloure.

Nomes fitxers directament a l'arrel ('/nom', sense subdirectoris addicionals)
-- si el path te una '/' de mes, no es notifica res (v0 sense os.mkdir()).

PORTABILITAT (fora del navegador)
----------------------------------
Si __file_changed__ no existeix com a builtin (execucio normal en un
terminal, Raspberry Pi, etc.), open() es comporta EXACTAMENT com el real:
cap efecte advers, cap notificacio, cap overhead rellevant. Aquest modul
nomes es carrega dins l'entorn del navegador (worker.js l'injecta), aixi
que aquesta comprovacio es mes aviat una xarxa de seguretat que un cas
d'us real.
"""
import builtins as _builtins
import io as _io

_open_real = _builtins.open
_excluded = set()   # noms (sense '/'): .py del projecte + assets/imatges


def __fs_configure__(noms_json):
    """Cridat pel worker.js abans de cada 'run' amb els noms (JSON, llista
    de strings sense '/') a excloure de la deteccio de "fitxer de dades
    nou": els .py del projecte actual i els assets (imatges)."""
    global _excluded
    import json as _json
    try:
        _excluded = set(_json.loads(noms_json))
    except Exception:
        _excluded = set()


def _nom_arrel(path):
    """Retorna el nom net (sense '/') si `path` apunta directament a
    l'arrel del FS virtual ('/nom' o 'nom'), o None si te subdirectoris
    addicionals (fora d'abast en aquesta primera versio)."""
    p = str(path)
    if p.startswith('/'):
        p = p[1:]
    if '/' in p or '\\' in p or p == '':
        return None
    return p


def _es_mode_escriptura(mode):
    return any(c in mode for c in ('w', 'a', 'x', '+'))


class _FitxerVigilat(_io.IOBase):
    """Embolcall d'un fitxer obert en mode escriptura: delega TOTES les
    operacions al fitxer real (self._real) i nomes intercepta close() i
    flush() per notificar el fil principal amb el contingut actual --
    igual que ho faria un 'save' explicit, pero automatic."""

    def __init__(self, real, nom, path_original):
        self._real = real
        self._nom = nom
        # IMPORTANT: guardem el path EXACTE tal com l'ha passat l'alumne a
        # open() (relatiu o absolut), NO un path "corregit" a l'arrel. No
        # podem donar per fet quin és el cwd real de Pyodide en aquest
        # entorn -- nomes sabem que reobrir EXACTAMENT el mateix path que
        # ja s'ha obert amb exit apunta, per definicio, al mateix fitxer.
        self._path = path_original
        self._tancat = False

    def _notifica(self):
        try:
            with _open_real(self._path, 'rb') as fh:
                dades = fh.read()
        except OSError:
            return
        try:
            text = dades.decode('utf-8')
            __file_changed__(self._nom, text, True, len(dades))
        except UnicodeDecodeError:
            import base64 as _b64
            b64 = _b64.b64encode(dades).decode('ascii')
            __file_changed__(self._nom, b64, False, len(dades))

    # -- API de fitxer: delega-ho tot, nomes afegim la notificacio ------
    def flush(self):
        self._real.flush()
        self._notifica()

    def close(self):
        if self._tancat:
            return
        self._tancat = True
        try:
            self._real.close()
        finally:
            self._notifica()

    def write(self, *a, **kw):
        return self._real.write(*a, **kw)

    def writelines(self, *a, **kw):
        return self._real.writelines(*a, **kw)

    def read(self, *a, **kw):
        return self._real.read(*a, **kw)

    def readline(self, *a, **kw):
        return self._real.readline(*a, **kw)

    def readlines(self, *a, **kw):
        return self._real.readlines(*a, **kw)

    def seek(self, *a, **kw):
        return self._real.seek(*a, **kw)

    def tell(self):
        return self._real.tell()

    def truncate(self, *a, **kw):
        return self._real.truncate(*a, **kw)

    def readable(self):
        return self._real.readable()

    def writable(self):
        return True

    def seekable(self):
        return self._real.seekable()

    def __iter__(self):
        return iter(self._real)

    def __next__(self):
        return next(self._real)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def __getattr__(self, attr):
        # Qualsevol altra cosa que no haguem embolcallat explicitament
        # (p.ex. .name, .mode, .encoding) es delega al fitxer real.
        return getattr(self._real, attr)


def _open_vigilat(file, mode='r', *args, **kwargs):
    real = _open_real(file, mode, *args, **kwargs)

    if not _es_mode_escriptura(mode):
        return real   # lectura pura: mai genera una pestanya nova

    if not hasattr(_builtins, '__file_changed__'):
        return real   # fora del navegador: cap notificacio, cap efecte advers

    nom = _nom_arrel(file)
    if nom is None:
        return real   # subdirectoris: fora d'abast en aquesta v0

    if nom.endswith('.py') or nom in _excluded:
        return real   # .py del projecte / asset: mai "fitxer de dades nou"

    return _FitxerVigilat(real, nom, file)


_builtins.open = _open_vigilat
_builtins.__fs_configure__ = __fs_configure__
