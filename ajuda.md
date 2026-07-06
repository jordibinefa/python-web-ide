# Ajuda — py.binefa.cat (IDE Python al navegador)

Aquest document explica com carregar projectes i passar valors des de la URL
(`#run:` / `#open:`), i quines restriccions té l'entorn respecte a un Python
normal — sobretot pel que fa a **MQTT** i **tkinter**.

> Aquest fitxer és l'esborrany en Markdown. Es convertirà a `ajuda.html`
> quan estigui validat.

---

## 1. Què és `#run:` i `#open:`?

Just després de la URL de l'IDE pots afegir un `#run:...` o un `#open:...`
per carregar (i, amb `#run:`, executar automàticament) un projecte i
opcionalment passar-li variables.

- **`#open:...`** — carrega el projecte a l'IDE però **no l'executa**.
  L'alumne prem "Executa" quan vulgui.
- **`#run:...`** — carrega el projecte i l'**executa automàticament** en
  quant l'entorn Python estigui llest.

Exemples:

```
https://py.binefa.cat/#open:https://dt.iotvertebrae.com/prjs/exemple.zip
https://py.binefa.cat/#run:https://dt.iotvertebrae.com/prjs/exemple.zip
```

En aquest cas simple (una URL sola, sense cap `=`), tot el que hi ha
després de `#run:`/`#open:` es tracta directament com la URL d'un fitxer
`.zip` amb el projecte.

---

## 2. Passar variables i triar el projecte alhora

Si necessites passar **variables** (per exemple un `topic` de MQTT diferent
per a cada alumne) fas servir parells `clau=valor` separats per `&`:

```
#run:_prj=zip:<url-del-zip>&topic=alumne07-a3f9c2&sid=binefaJordi
```

- **`_prj`** és l'única clau reservada pel sistema. Indica d'on ve el
  projecte:
  - `_prj=zip:<url>` — descarrega i carrega un ZIP (equivalent a "Importa
    ZIP…").
  - `_prj=ex:<id>` — carrega un dels exemples predefinits del desplegable
    (pel seu identificador intern, no pel nom que es veu al menú).
- **Qualsevol altra clau** (`topic`, `sid`, o el nom que vulguis) és una
  **variable lliure** que es passa al teu codi Python.

Si no poses `_prj`, no es carrega cap projecte nou: només s'apliquen les
variables sobre el que ja hi hagi obert a l'IDE (el projecte per defecte, o
el que hagi quedat desat de la sessió anterior). És útil quan el professor
o l'alumne ja té el codi carregat i només vol canviar el valor d'una
variable (per exemple, en una demo en directe canviant `topic` cada
vegada):

```
https://py.binefa.cat/#open:topic=alumne07-a3f9c2&sid=binefaJordi
https://py.binefa.cat/#run:topic=alumne07-a3f9c2&sid=binefaJordi
```

- Amb `#open:` només es defineixen les variables; l'alumne prem "Executa"
  quan vulgui.
- Amb `#run:` es defineixen les variables **i** s'executa immediatament el
  projecte que ja hi havia obert.

> ⚠️ **Important**: si ja tens la pàgina oberta i només canvies el hash de
> la URL (per exemple, el valor de `topic`), **cal recarregar la pàgina
> sencera** perquè el nou valor s'apliqui — vegeu l'avís a la secció
> següent.

### Identificadors dels exemples predefinits (per a `_prj=ex:`)

| Categoria  | Identificador          | Exemple                                |
|------------|-------------------------|-----------------------------------------|
| Bàsic      | `basic_condicionals`    | Condicionals (if / elif / else)        |
| Bàsic      | `basic_bucles`          | Bucles (while / for)                   |
| Bàsic      | `basic_tryexcept`       | Gestió d'excepcions                    |
| Bàsic      | `basic_multifitxer`     | Projecte amb diversos fitxers          |
| Científic  | `cientific_numpy`       | NumPy                                  |
| Científic  | `cientific_matplotlib`  | Matplotlib                             |
| TKinter    | `tk_basic`               | Finestra bàsica                        |
| TKinter    | `tk_checkbutton`         | Checkbutton                            |
| TKinter    | `tk_grid`                | Grid (columnspan/rowspan/sticky)       |
| TKinter    | `tk_listbox`             | Listbox                                |
| TKinter    | `tk_place`               | Place                                  |
| TKinter    | `tk_radiobutton`         | Radiobutton                            |
| TKinter    | `tk_image`               | PhotoImage                             |
| MQTT       | `mqtt_publica`           | Només publicador                       |
| MQTT       | `mqtt_subscriu`          | Només subscriptor                      |
| MQTT       | `mqtt_pub_sub`           | Publicador + subscriptor alhora        |

Exemple complet carregant l'exemple `mqtt_pub_sub` i passant-li un `topic`
propi:

```
https://py.binefa.cat/#run:_prj=ex:mqtt_pub_sub&topic=alumne07-a3f9c2
```

---

## 3. Com llegir aquestes variables des del teu codi Python

Les variables arriben com a **variables globals normals**, sempre de tipus
**text (`str`)** — mai número, mai booleà. Si necessites un número, has de
convertir-lo tu mateix amb `int(...)` o `float(...)`.

Com que una variable només existeix si algú l'ha passat per la URL, cal
comprovar-ho abans d'utilitzar-la:

```python
if 'topic' in globals():
    arrel = topic
else:
    arrel = "arrel_per_defecte"

print("Fent servir l'arrel de topic:", arrel)
```

Aquest patró (`'nom' in globals()`) et permet escriure un mateix programa
que funcioni tant si s'obre "a pèl" (sense variables) com si es llança amb
una URL personalitzada per a cada alumne.

**Nota:** un cop el projecte ja s'ha carregat, si tornes a prémer "Executa"
manualment **sense tocar la URL**, les mateixes variables es tornen a
injectar automàticament (no cal fer res més). Ara bé, si el que vols és
**canviar el valor** d'una variable (o carregar un altre projecte), cal
editar el hash de la URL i **recarregar la pàgina sencera** — vegeu
l'avís de la propera secció.

---

## 4. Cal recarregar la pàgina quan canvies la URL

El hash de la URL (`#run:...` / `#open:...`) **només es llegeix un cop, en
carregar la pàgina**. Si ja tens `py.binefa.cat` obert i simplement canvies
el valor d'una variable, o l'exemple, a la barra d'adreces, **el canvi no
s'aplicarà fins que la pàgina es torni a carregar sencera**.

- **Editant la URL a mà**: després de canviar el hash, prem **Enter** a la
  barra d'adreces (sol fer una recàrrega completa) o força-ho amb **F5** /
  **Ctrl+R** (Windows/Linux) o **Cmd+R** (Mac) per estar-ne segur.
- **Amb pestanyes obertes prèviament**: si ja tenies la pestanya oberta
  d'una sessió anterior i enganxes una URL nova amb un hash diferent, més
  val obrir-la en una pestanya nova o recarregar-la explícitament — alguns
  navegadors no recarreguen automàticament si només canvia la part després
  del `#`.
- **Dins d'un `<iframe>`** (per exemple, la pàgina amb `split` per generar
  una arrel de topic diferent per a cada alumne): si el JavaScript de la
  pàgina contenidora canvia només l'atribut `src` de l'`iframe` (mateixa
  URL base, hash diferent), molts navegadors **no recarreguen el document
  intern de l'iframe** — cal forçar-ho explícitament (per exemple, buidant
  primer el `src` i tornant-lo a assignar, o creant l'`iframe` de nou) si
  es vol canviar el `topic` d'un iframe ja carregat.

En resum: cada `topic`, `sid` o altre valor nou que vulguis provar implica
una **càrrega de pàgina nova des de zero**, no una simple actualització en
calent.

---

## 5. Valors amb espais, `/`, `#`... (cometes)

Si el valor d'una variable conté caràcters com espais, `/` o `#`, tens dues
opcions:

1. **Cometes, a l'estil Python** (recomanat quan escrius la URL a mà, per
   exemple en una demo en directe):

   ```
   #run:_prj=ex:mqtt_pub_sub&topic='alumnes/grup A/demo'
   ```

   Igual que en Python, pots fer servir cometes simples o dobles, i l'una
   pot contenir l'altra sense problemes:

   ```
   topic="Una 'prova' amb dobles"
   topic='Una "prova" amb simples'
   ```

   L'única limitació és que **no hi ha manera d'escapar la mateixa cometa
   que ja fas servir per obrir/tancar el valor**. Si el teu valor conté
   alhora `'` i `"`, tria l'altra tècnica (punt següent).

2. **Codificat amb `encodeURIComponent`** (recomanat quan la URL la genera
   una pàgina/script, per exemple la pàgina amb `split` per a 30 alumnes):
   qualsevol valor sense cometa a l'inici es desxifra automàticament amb
   `decodeURIComponent()`.

No cal escapar mai el caràcter `#`: el navegador només interpreta el
*primer* `#` de la URL com a inici del "hash"; qualsevol `#` posterior ja
forma part del valor tal qual. El `/` tampoc necessita cap tractament
especial. Els caràcters que **sí** cal vigilar són `&` i `=` (fan servir de
separadors) i els espais — per aquests, cometes o `encodeURIComponent`.

---

## 6. D'on es poden carregar projectes ZIP remots (`_prj=zip:`)

Per seguretat, `_prj=zip:<url>` només funciona si la URL pertany a un
d'aquests dominis (o a un subdomini seu):

`berkeley.edu`, `fje.edu`, `binefa.com`, `binefa.cat`, `binefa.net`,
`things.cat`, `electronics.cat`, `popotamo.cat`, `github.com`,
`github.io`, `xavierpi.com`, `collados.org`

Si el domini no hi és, l'IDE mostra un avís i no carrega res.

**Important sobre CORS**: encara que el domini estigui a la llista, el
servidor que allotja el ZIP ha de permetre l'accés des d'un altre lloc web
(capçalera `Access-Control-Allow-Origin`). Si no ho fa, la càrrega falla
igualment — obre la consola del navegador (tecla F12) per veure el motiu
exacte de l'error.

---

## 7. Restriccions de MQTT al navegador

L'IDE inclou un shim de `paho.mqtt.client` que funciona **dins del
navegador**, però amb algunes diferències respecte a un Raspberry Pi o un
ordinador normal:

- **Només `wss` (WebSocket segur), mai TCP cru.** El navegador no pot obrir
  connexions TCP directes; per això cal connectar-se a un port de broker
  que accepti WebSocket (típicament 8084, 8081, 8000 o 9002).
- **`loop_forever()` no funciona.** Al navegador tot passa en un únic fil
  d'execució; `loop_forever()` el bloquejaria per complet i no es rebria
  cap missatge. Fes servir sempre `loop_start()` i mantén el programa viu
  amb un bucle asíncron (secció 9 si combines amb una finestra tkinter):

  ```python
  client.loop_start()
  while True:
      await asyncio.sleep(1)
  ```

- **Regla d'or: `await asyncio.sleep(...)`, mai `time.sleep(...)`.** Si fas
  servir `time.sleep()` dins d'un bucle, el programa "es congela" i deixa
  de rebre missatges MQTT durant tota l'espera. `asyncio.sleep()` cedeix el
  control i permet que arribin els missatges `on_message` mentre esperes.
  Per això **tot codi MQTT que hagi de rebre i esperar alhora ha de fer
  servir `await`** (directament al nivell superior del fitxer — vegeu la
  secció 9 sobre per què NO cal, i de fet NO funciona, `async def`/
  `asyncio.run()` en aquest IDE), no funcions ni bucles síncrons normals.
- **`msg.payload` arriba com a `bytes`**, igual que amb el paho real —
  recorda fer `msg.payload.decode("utf-8")` per obtenir-ne el text.
- **Subconjunt de l'API real de paho.** Estan implementats:
  `Client(client_id)`, `on_connect`/`on_disconnect`/`on_message`/
  `on_publish`/`on_subscribe`/`on_unsubscribe`, `username_pw_set()`,
  `user_data_set()`, `connect()`, `publish()`, `subscribe()`,
  `unsubscribe()`, `loop_start()`, `loop_stop()`, `disconnect()`,
  `is_connected()`. **No hi ha** `tls_set()`, `will_set()`, ni reconnexió
  automàtica configurable.
- **Col·lisió de topics entre companys.** Si diversos alumnes fan servir el
  mateix "arrel" de topic (per exemple `arrel/#`) contra el mateix broker
  públic, es veuran els missatges els uns dels altres. Fes servir la
  variable `topic` passada per URL (secció 2-3 d'aquest document) perquè
  cada alumne tingui una arrel pròpia.

---

## 8. Restriccions de tkinter al navegador

L'IDE inclou un shim de `tkinter` que tradueix les crides a elements HTML
dins la pestanya "Finestra Tk" de l'IDE. Cobreix `Tk`, `Label`,
`Entry` (amb `show='*'` per a contrasenyes), `Button`,
`messagebox.showinfo`/`askokcancel`, `Radiobutton` + `IntVar`/
`StringVar`, `Listbox`, `Checkbutton` i `PhotoImage`, amb `pack()`,
`grid()` i `place()`. Limitacions a tenir en compte:

- **No hi ha `Canvas` ni `Toplevel`** (cap finestra secundària; només la
  finestra principal).
- **`grid()` no admet `columnconfigure()`/`rowconfigure()`** (pesos de
  redimensionament de files/columnes). Sí que funcionen `columnspan`,
  `rowspan` i `sticky`.
- **`bind()` genèric no existeix.** Només es capturen esdeveniments a
  través de `command=` (per exemple, el clic d'un `Button`).
- **`PhotoImage.width()` i `.height()` sempre retornen `0`.** Si el teu
  codi necessita mesurar una imatge, no ho podràs fer amb el shim.
- **Les imatges (`PhotoImage(file=...)`) han de tenir ruta absoluta.** Si
  la importes com a asset del projecte, l'IDE ja se n'ocupa; si hi ha
  problemes de càrrega, prova amb `/nom_imatge.png`.
- **Els errors de tkinter no tenen un tractament especial**: si el teu codi
  llança una excepció (per exemple, un `float()` d'una cadena buida),
  sortirà per la consola igual que qualsevol altre error de Python.

---

## 9. Combinar tkinter amb MQTT (o qualsevol codi asíncron)

Aquesta secció és clau si vols una finestra tkinter interactiva que alhora
rebi missatges MQTT (o faci qualsevol altra cosa en segon pla).

### `finestra.mainloop()` bloqueja MQTT — no la facis servir aquí

`mainloop()` espera els clics de manera **totalment bloquejant**: mentre
està activa, el navegador no pot processar res més al mateix fil — ni tan
sols els missatges MQTT que arribin, encara que la connexió ja estigui
oberta. És a dir, `mainloop()` i MQTT en directe **no poden conviure**.

### Solució: `finestra.update()` dins d'un bucle asíncron

`update()` és un mètode **real** de tkinter (no un invent d'aquest IDE):
processa els clics pendents i torna immediatament, sense bloquejar mai.
Substitueix `mainloop()` per aquest patró:

```python
aturat = False
while not aturat:
    finestra.update()           # processa clics pendents, no bloqueja
    await asyncio.sleep(0.05)   # cedeix el control perquè arribi MQTT
```

Aquest patró és 100% vàlid també fora del navegador (Raspberry Pi, PC amb
tkinter real) — no és cap invent exclusiu de l'IDE.

### ⚠️ Mai facis servir `asyncio.run()` en aquest IDE

És temptador escriure el bucle anterior dins d'una funció i cridar-la amb
`asyncio.run(main())`, tal com faries en un terminal normal. **A
py.binefa.cat això falla** amb:

```
RuntimeError: WebAssembly stack switching not supported in this JavaScript runtime
```

> 💡 Això és cert si crides `asyncio.run()` **incondicionalment**. Si vols
> que el mateix fitxer també es pugui executar des d'un terminal normal amb
> tkinter/paho-mqtt reals (per exemple per provar-lo abans de pujar-lo, o
> perquè funcioni igual en un Raspberry Pi), a la **secció 13** hi ha el
> patró per detectar en quin dels dos entorns ets i triar automàticament
> entre `await` (navegador) i `asyncio.run()` (terminal) sense mantenir dos
> fitxers diferents.

L'IDE ja executa el teu codi dins el seu propi bucle asíncron, i permet fer
servir `await` **directament al nivell superior del fitxer** (sense cap
`async def`/`asyncio.run()` al voltant). Fes-ho servir així:

```python
# ✅ Correcte a l'IDE: 'await' directament, sense embolcall
aturat = False
while not aturat:
    finestra.update()
    await asyncio.sleep(0.05)
```

```python
# ❌ Falla a l'IDE (encara que sigui Python vàlid en un terminal normal)
async def main():
    while not aturat:
        finestra.update()
        await asyncio.sleep(0.05)
asyncio.run(main())
```

**Símptoma enganyós si t'equivoques**: amb `asyncio.run()`, el programa
sembla mig funcionar — una finestra tkinter connectada mostra "Connectat" i
fins i tot missatges rebuts (perquè els callbacks de MQTT es criden per un
altre camí, independent del bucle), però **cap botó respon** (`update()`
mai s'arriba a cridar). Si et trobes en aquesta situació, revisa que no hi
hagi cap `asyncio.run()` al teu codi.

### No barregis `mainloop()` i `update()` al mateix programa

Tria un dels dos patrons segons si necessites codi asíncron en paral·lel
(`update()`) o no (`mainloop()`, més simple per a tkinter "pur").

---

## 10. Altres restriccions generals de l'entorn

- **Cada "Executa" reinicia l'estat de fitxers `.py`**: s'esborren tots els
  `.py` anteriors del sistema de fitxers virtual i es tornen a escriure els
  del projecte actual. Els assets (imatges) i les variables de la URL es
  mantenen entre execucions.
- **No hi ha accés a Internet des del codi Python**, més enllà de MQTT via
  `wss`. No es poden fer peticions HTTP arbitràries (`requests`, `urllib`,
  etc. no tenen accés a la xarxa real del navegador tal com ho tindrien en
  un ordinador normal).
- **`matplotlib.pyplot.show()`** està adaptat perquè, en lloc d'obrir una
  finestra, enviï la imatge com a PNG a la consola de l'IDE.
- **`input()` funciona però és bloquejant**: el programa espera que
  l'alumne escrigui una resposta al quadre que apareix a la consola abans
  de continuar.
- **El projecte es desa automàticament al navegador (`localStorage`)** de
  l'alumne mentre edita manualment. Els projectes carregats per `#run:`/
  `#open:` **no es desen automàticament**: si es recarrega la pàgina amb la
  mateixa URL, es torna a carregar igual; si es canvia d'URL sense el hash,
  es recupera l'últim projecte desat localment.

---

## 11. Incrustar py.binefa.cat dins d'una pàgina pròpia (avançat)

Aquesta secció només interessa si vols fer una pàgina teva que mostri
py.binefa.cat dins d'un `<iframe>` (per exemple, un `split` amb Snap! a
l'altra meitat, com `pahoSnap00.html`). Si només ets alumne fent servir
py.binefa.cat directament, te la pots saltar.

Com que py.binefa.cat necessita `SharedArrayBuffer` per a tkinter, **la
teva pròpia pàgina (la que conté l'`<iframe>`) ha d'enviar aquestes dues
capçaleres HTTP** (mai amb `<meta>`, han de sortir del teu servidor):

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: credentialless
```

I l'etiqueta `<iframe>` que incrusta py.binefa.cat necessita, a més:

```html
<iframe src="https://py.binefa.cat/#run:..." allow="cross-origin-isolated"></iframe>
```

Si la teva pàgina té aquestes capçaleres actives, **qualsevol altre
`<iframe>` que hi posis al costat** (Snap!, o el que sigui) també les
necessita ell mateix — si no, el navegador el bloqueja igual, encara que
no tingui res a veure amb tkinter ni `SharedArrayBuffer`:

```
Cross-Origin-Embedder-Policy: credentialless
Cross-Origin-Resource-Policy: cross-origin
```

Aquest darrer detall (calen les dues capçaleres al document incrustat, no
només una) és fàcil de passar per alt i dona errors que semblen no tenir
relació (missatges de "connexió no permesa" dins de l'`iframe`, tot i que
la mateixa URL funciona bé oberta directament). Si t'hi trobes, comença
sempre per `curl -sI <url>` per veure exactament quines capçaleres arriben,
abans de sospitar d'extensions del navegador o polítiques de xarxa.

---

## 12. Xuleta ràpida

```
#open:<url.zip>                                  → carrega, no executa
#run:<url.zip>                                   → carrega i executa
#run:_prj=zip:<url.zip>&clau=valor               → + variables
#run:_prj=ex:<id>&clau=valor                     → exemple predefinit + variables
#run:_prj=ex:mqtt_pub_sub&topic='alumnes/grup A' → valor amb espais, entre cometes
#run:topic=alumne07-a3f9c2&sid=binefaJordi       → nomes variables, sobre el projecte ja obert
```

Des de Python:

```python
if 'topic' in globals():
    print("topic rebut per URL:", topic)
```

MQTT: `await asyncio.sleep(...)` (mai `async def`/`asyncio.run()`, mai
`time.sleep()`), i `loop_start()` en lloc de `loop_forever()`.

tkinter + MQTT (o qualsevol asíncron): `finestra.update()` dins
`while not aturat: ...; await asyncio.sleep(0.05)`, mai `mainloop()`.

Voleu que el mateix fitxer funcioni també des d'un terminal normal
(tkinter/paho-mqtt reals)? → secció 13.

⚠️ **Cada cop que canviïs algun valor del hash de la URL, recarrega la
pàgina sencera** (Enter a la barra d'adreces, F5, o una càrrega nova de
l'iframe) — el hash només es llegeix en carregar la pàgina.

---

## 13. Fer que el mateix codi funcioni des d'un terminal (avançat)

Aquesta secció és per quan vols que **el mateix fitxer `.py`** funcioni tant
pujat a `py.binefa.cat` (tkinter/MQTT via shim, dins Pyodide) com executat
directament amb `python3 elteu_fitxer.py` en un ordinador normal (tkinter i
`paho-mqtt` reals). És el cas, per exemple, si vols provar-lo còmodament en
local abans de pujar-lo, o fer-lo servir igual en un Raspberry Pi. Apareixen
quatre diferències a tenir en compte; totes es resolen detectant en quin
entorn ets **un sol cop, al principi del fitxer**:

```python
import asyncio

try:
    asyncio.get_running_loop()
    _dins_navegador = True   # Pyodide ja té un event loop actiu
except RuntimeError:
    _dins_navegador = False  # script de terminal: encara no n'hi ha cap
```

### 13.1. El bucle principal (`await` vs. `asyncio.run()`)

Com ja explica la secció 9, el navegador exigeix `await` a nivell superior
del fitxer i **no admet** `asyncio.run()`. Un terminal normal és just al
revés: `await` fora d'una funció `async` és un `SyntaxError` en carregar el
fitxer (encara que mai s'arribés a executar), i **cal** `asyncio.run()`.
Com que no es pot triar entre "codi amb `await` solt" i "codi dins d'una
funció" en temps d'execució (Python decideix la validesa de l'`await` quan
compila el fitxer, no quan el corre), la solució és: el bucle SEMPRE viu
dins d'una funció `async def`, i només es decideix com llançar-lo:

```python
async def bucle_principal():
    aturat = False
    while not aturat:
        finestra.update()
        await asyncio.sleep(0.05)

if _dins_navegador:
    # Ja hi ha un event loop en marxa (per això funciona 'await' solt);
    # programem el bucle com a tasca perquè continuï sense bloquejar-lo.
    asyncio.ensure_future(bucle_principal())
else:
    # Terminal: no hi ha cap loop, se'n crea un i s'hi espera.
    asyncio.run(bucle_principal())
```

> ⚠️ **Important — aquest patró trenca el botó "Interromp" a l'IDE.**
> Amb `asyncio.ensure_future()`, el codi de nivell superior acaba
> d'executar-se de seguida (només ha programat la tasca), i "Interromp"
> deixa de tenir res a interrompre — la feina continua igualment per sota,
> però ja no es pot aturar amb el botó (comprovat empíricament amb els
> exemples `mqtt_publica`/`mqtt_subscriu`/`mqtt_pub_sub`).
>
> - Si el programa es tanca amb la X de la finestra tkinter (com
>   `tk_mqtt_smm`), aquest patró és perfecte: no cal "Interromp".
> - Si és una demo curta que s'atura sovint amb "Interromp" (típic dels
>   exemples MQTT sols, sense finestra), **no apliquis aquest patró al
>   `main.py` del navegador**. Deixa'l tal com estava (amb `await` solt) i
>   posa la versió amb `async def`/`asyncio.run()` en un **fitxer a part**
>   (per exemple `elteu_exemple_terminal.py`), pensat només per executar
>   des de terminal. Val més duplicar unes poques línies que perdre la
>   capacitat d'aturar l'execució amb un clic.

### 13.2. Variables per URL → arguments de terminal

Al navegador, les variables del hash (`&clau=valor`) arriben com a globals
(secció 3). Al terminal, l'equivalent natural és passar-les com a arguments
de la línia d'ordres amb el mateix format `clau=valor`:

```
python3 elteu_fitxer.py topic=alumne07-a3f9c2 sid=binefaJordi
```

Es poden llegir totes amb una única funció `valor_inicial()` que miri a
`sys.argv` quan no estàs al navegador:

```python
import sys

def _parseja_args_terminal():
    args = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            clau, valor = arg.split("=", 1)
            args[clau] = valor
    return args

_args_terminal = {} if _dins_navegador else _parseja_args_terminal()

def valor_inicial(nom_variable, per_defecte):
    if _dins_navegador:
        return globals()[nom_variable] if nom_variable in globals() else per_defecte
    return _args_terminal.get(nom_variable, per_defecte)
```

### 13.3. Rutes de fitxers (imatges, assets)

Al navegador, els assets del projecte es desen a l'arrel del sistema de
fitxers virtual (`/nom.png`). Al terminal, un fitxer normalment és al mateix
directori que l'script, **no necessàriament** al directori de treball
actual (des d'on s'executa la comanda). Si el teu codi obre fitxers
directament amb `open(...)` (no via `PhotoImage(file=...)`, que ja gestiona
això sol), cal triar la ruta segons l'entorn:

```python
import os

def ruta_asset(nom_fitxer):
    if _dins_navegador:
        return "/" + nom_fitxer
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), nom_fitxer)
```

### 13.4. MQTT + tkinter real: cal una cua entre fils

Aquesta és la diferència més fàcil de passar per alt. Al navegador, el shim
de MQTT crida els teus `on_connect`/`on_message`/etc. **al mateix i únic
fil** que tkinter — per això tot el codi dels exemples toca `Label`/`Button`
directament dins d'aquests callbacks sense cap problema.

Al terminal, amb `paho-mqtt` real i `client.loop_start()`, aquests callbacks
s'executen en un **fil separat**. tkinter real **no és thread-safe**: tocar
un widget des d'un altre fil peta amb:

```
RuntimeError: main thread is not in main loop
```

La solució (i és segura fer-la servir també al navegador, on només afegeix
com a màxim un cicle de retard —uns 50ms—, ja que allà no hi ha fils reals)
és fer que els callbacks de MQTT només deixin un missatge a una
`queue.Queue()`, i que sigui el bucle principal (fil de tkinter) qui la
buidi i apliqui els canvis:

```python
import queue
cua_mqtt = queue.Queue()

def on_message(c, userdata, msg):
    cua_mqtt.put(("missatge", msg.topic, msg.payload))
    # MAI tocar cap widget aquí directament

async def bucle_principal():
    while True:
        finestra.update()
        while True:
            try:
                event = cua_mqtt.get_nowait()
            except queue.Empty:
                break
            if event[0] == "missatge":
                processa_missatge(event[1], event[2])   # aquí sí que es pot tocar tkinter
        await asyncio.sleep(0.05)
```

### 13.5. Altres detalls petits a tenir en compte

- **Tancar la finestra amb la X**: el shim NO implementa `Tk.protocol()`
  (no cal a l'iframe). Crida `finestra.protocol("WM_DELETE_WINDOW", ...)`
  només quan `not _dins_navegador`, o petarà al navegador amb
  `AttributeError`.
- **`Label.config(image=..., text=...)` alhora**: al shim, passar `image=`
  i `text=` junts en una mateixa crida a `config()` fa que la imatge no es
  vegi. Si un `Label` mostra imatges dinàmiques, no hi barregis mai
  `text=""` — crida `config(image=...)` sol.
- **`PhotoImage` sense `subsample()`/`zoom()`**: si el teu codi redimensiona
  imatges en temps real amb aquests mètodes (tkinter real els té), no
  funcionaran al shim. Cal preparar les imatges ja a la mida final abans de
  pujar-les (per exemple amb ImageMagick) en lloc de redimensionar-les en
  temps d'execució.
