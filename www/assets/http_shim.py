# -*- coding: utf-8 -*-
"""
Shim minim de 'requests' (nomes get/post) per a l'IDE Python en navegador
(Pyodide + Web Worker).

Cobreix:
    requests.get(url, params=None, headers=None)
    requests.post(url, data=None, json=None, params=None, headers=None)
amb un objecte Response amb .status_code, .ok, .text, .headers, .json().

Nomes respostes de TEXT/JSON en aquesta primera versio (sense contingut
binari) -- si mes endavant cal (imatges, fitxers descarregats), es pot
afegir seguint el mateix patro que fs_shim.py (base64 + isText=False).

DISSENY
-------
A diferencia de tkinter_shim.py o fs_shim.py, aquest shim NO necessita cap
pont cap al fil principal (__tk_call__, __file_changed__, SharedArrayBuffer,
Atomics...): un Web Worker ja te el seu propi XMLHttpRequest, i Pyodide
permet accedir-hi directament amb 'from js import XMLHttpRequest'. Fent
xhr.open(metode, url, False) (el tercer parametre False vol dir "sincron"),
el propi navegador bloqueja NOMES el worker fins que arriba la resposta --
exactament com Atomics.wait bloqueja el worker per a input(), pero sense
haver de muntar cap mecanisme propi.

LIMITACIONS CONEGUDES (v0, deliberades)
----------------------------------------
- Nomes get() i post() (no put/delete/patch/head -- trivials d'afegir mes
  endavant reutilitzant _request(), pero fora d'abast en aquesta v0).
- Nomes contingut de resposta llegible com a text (.text/.json()); no hi ha
  gestio de respostes binaries.
- Sense classe d'excepcions propia (requests.exceptions.*): els errors de
  xarxa/CORS es propaguen com un ConnectionError (builtin de Python), no
  amb la jerarquia real de 'requests'. response.raise_for_status() tampoc
  hi es en aquesta v0.
- xhr.timeout normalment no te efecte en peticions SINCRONES (limitacio
  del propi navegador, no d'aquest shim): un temps d'espera molt llarg del
  servidor bloquejara el worker igualment.
- CORS: el servidor remot ha de respondre amb les capçaleres CORS
  adequades (Access-Control-Allow-Origin) perque el navegador deixi llegir
  la resposta -- aixo es un requisit del SERVIDOR, no d'aquest shim.
- Petició SINCRONA: mentre esta en curs, bloqueja TOT el worker (inclos
  qualsevol Tk.update()/MQTT.js pendents al mateix fil). Un programa amb
  una finestra tkinter que faci una crida HTTP lenta es congelara fins que
  arribi la resposta -- mateixa naturalesa que mainloop() bloquejant.

PORTABILITAT (fora del navegador)
----------------------------------
Aquest modul NOMES es carrega dins l'entorn del navegador (worker.js
l'injecta com a 'requests' a sys.modules). Fora del navegador, si el codi
de l'alumne fa "import requests", Python trobara la biblioteca real (si
esta instal·lada) en lloc d'aquest shim -- no calen precaucions addicionals
al codi de l'alumne.
"""
import json as _json
from urllib.parse import urlencode as _urlencode

from js import XMLHttpRequest


def _build_url(url, params):
    if not params:
        return url
    qs = _urlencode(params, doseq=True)
    sep = '&' if '?' in url else '?'
    return url + sep + qs


def _parse_headers(raw_headers):
    """xhr.getAllResponseHeaders() retorna un sol string amb totes les
    capçaleres separades per '\\r\\n' ("clau: valor" cada línia)."""
    headers = {}
    if not raw_headers:
        return headers
    for linia in raw_headers.strip().split('\r\n'):
        if ':' in linia:
            clau, valor = linia.split(':', 1)
            headers[clau.strip()] = valor.strip()
    return headers


class Response:
    def __init__(self, xhr, url):
        self.url = url
        self.status_code = xhr.status
        self.text = xhr.responseText or ''
        self.headers = _parse_headers(xhr.getAllResponseHeaders())
        self.ok = 200 <= self.status_code < 400

    def json(self):
        return _json.loads(self.text)

    def __repr__(self):
        return f'<Response [{self.status_code}]>'


def _request(method, url, params=None, data=None, json=None, headers=None):
    url_final = _build_url(url, params)

    cos = None
    capcaleres = dict(headers or {})
    if json is not None:
        cos = _json.dumps(json)
        capcaleres.setdefault('Content-Type', 'application/json')
    elif data is not None:
        if isinstance(data, dict):
            cos = _urlencode(data, doseq=True)
            capcaleres.setdefault('Content-Type', 'application/x-www-form-urlencoded')
        else:
            cos = data

    xhr = XMLHttpRequest.new()
    xhr.open(method, url_final, False)   # False = petició SINCRONA
    for clau, valor in capcaleres.items():
        xhr.setRequestHeader(clau, valor)

    try:
        if cos is not None:
            xhr.send(cos)
        else:
            xhr.send()
    except Exception as exc:
        # xhr.send() llença una excepcio JS (JsException) si la connexio
        # falla d'entrada (DNS, servidor caigut, CORS bloquejat...). La
        # convertim en un ConnectionError normal de Python -- l'alumne no
        # hauria de veure mai una JsException en pantalla.
        raise ConnectionError(f'No s\'ha pogut connectar a {url_final}: {exc}') from exc

    if xhr.status == 0:
        # status 0 = la petició no ha arribat a completar-se (CORS
        # bloquejat pel navegador, error de xarxa...); NO és una resposta
        # HTTP real (no confondre amb un 200/404/500).
        raise ConnectionError(
            f'No s\'ha pogut connectar a {url_final} '
            '(revisa la connexió o si el servidor permet peticions CORS)'
        )

    return Response(xhr, url_final)


def get(url, params=None, headers=None):
    return _request('GET', url, params=params, headers=headers)


def post(url, data=None, json=None, params=None, headers=None):
    return _request('POST', url, params=params, data=data, json=json, headers=headers)
