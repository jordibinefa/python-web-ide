# IDE Python al navegador

> **[Read in English](README.md)**

Un IDE de Python que funciona al navegador, basat en [Pyodide](https://pyodide.org) (CPython
compilat a WebAssembly), executant-se sencer dins un Web Worker — **sense backend, sense
execució de codi al servidor**. Els alumnes escriuen codi en un editor amb pestanyes
(CodeMirror 6) i l'executen directament al seu propi navegador: gràfics amb
matplotlib/numpy/pandas, programes amb finestres amb un subconjunt de `tkinter`, missatgeria
MQTT per WebSocket, i peticions HTTP senzilles amb un subconjunt de `requests` — tot al
client.

Instància en viu: https://py.binefa.cat

## Com funciona

```
Navegador (alumne)
──────────────────────────────────────────────────────────
Escriu codi (pestanyes, CodeMirror)
        │
        ▼
Pyodide (WebAssembly) dins un Web Worker
  ├─ tkinter_shim.py    → finestres/widgets (SharedArrayBuffer ↔ fil principal)
  ├─ paho_mqtt_shim.py  → MQTT.js per WebSocket (broker públic broker.emqx.io)
  ├─ http_shim.py       → XMLHttpRequest síncron (requests.get/post)
  └─ fs_shim.py         → open() vigilat → pestanyes de fitxers de dades, inclosos al ZIP
        │
        ▼
TOT s'executa AL NAVEGADOR. nginx només serveix fitxers estàtics
(HTML/JS/CSS + el runtime de Pyodide) — no hi ha cap backend.
```

Com que no hi ha backend, la instal·lació és molt més lleugera que una eina docent típica
basada en Docker: `nginx:alpine` pesa pocs MB, i l'únic pas "feixuc" és baixar el runtime de
Pyodide i els paquets científics un sol cop (vegeu més avall) — no cal compilar ni construir
cap imatge.

---

## Instal·lació

Tria el teu cas:

- [Màquina virtual Linux (Debian / Ubuntu)](#opció-a--màquina-virtual-linux-debian--ubuntu)
- [Windows amb WSL2](#opció-b--windows-amb-wsl2)
- [VPS amb Traefik i HTTPS](#opció-c--vps-amb-traefik-i-https)

---

## Opció A — Màquina virtual Linux (Debian / Ubuntu)

### Requisits previs

- Debian 13 / Ubuntu 22.04 o superior
- Docker Engine (vegeu més avall si encara no el tens)
- Connexió a Internet per a la configuració inicial (per baixar el runtime de Pyodide)

### 1. Instal·lar Docker Engine

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli \
  containerd.io docker-buildx-plugin docker-compose-plugin

# Opcional: evitar escriure sudo a cada comanda
sudo usermod -aG docker $USER && newgrp docker
```

> **Debian 13 (trixie):** si el repositori falla, substitueix `$VERSION_CODENAME` per
> `bookworm` a la comanda echo. Els paquets són compatibles.

### 2. Obtenir el projecte

```bash
git clone https://github.com/jordibinefa/python-web-ide.git
cd python-web-ide
```

### 3. Baixar el runtime de Pyodide (no és al repositori)

`www/vendor/pyodide/0.28.3/` **no** es versiona a Git — el runtime més els paquets científics
plegats pesen centenars de MB, i tot és contingut redistribuïble de tercers, així que no té
sentit versionar-ho. Primer, baixa el runtime base:

```bash
cd www
mkdir -p vendor/pyodide/0.28.3 && cd vendor/pyodide/0.28.3

for f in pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip pyodide-lock.json; do
  curl -fsSL -o "$f" "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/$f"
done

cd ../../../..   # torna a l'arrel del projecte
```

Després, baixa els paquets científics opcionals (numpy, pandas, matplotlib i les seves
dependències transitives), amb verificació SHA-256:

```bash
python3 vendor-package.py numpy pandas matplotlib
```

Això cobreix tot el que necessita la categoria d'exemples "Científic". Pots saltar-te aquest
pas si no els necessites — l'IDE funciona igualment sense això, `import numpy` simplement
fallarà amb `ModuleNotFoundError` fins que ho facis.

### 4. Arrencar

```bash
docker compose -f docker-compose.local.yml up -d
```

### 5. Verificar

Obre `http://localhost:8080` al navegador.

> **Nota:** la pàgina s'ha de servir per HTTP(S) des d'un servidor web real, mai obrint-la com
> a fitxer local (`file://`) — `tkinter`/`input()` necessiten `SharedArrayBuffer`, que els
> navegadors només permeten amb les capçaleres d'aïllament cross-origin adequades (ja
> configurades a `nginx.conf`, no cal tocar res més).

---

## Opció B — Windows amb WSL2

### Requisits previs

- Windows 10 (21H2 o superior) o Windows 11
- WSL2 habilitat amb una distribució Ubuntu instal·lada

### 1. Habilitar WSL2

Obre PowerShell **com a administrador**:

```powershell
wsl --install
# Reinicia l'ordinador si t'ho demana
```

Si ja tens WSL instal·lat però en versió 1:

```powershell
wsl --set-default-version 2
```

### 2. Instal·lar Docker Desktop

Descarrega i instal·la [Docker Desktop per a Windows](https://www.docker.com/products/docker-desktop/).
Durant la instal·lació, assegura't que l'opció **"Use the WSL 2 based engine"** està marcada.
Un cop instal·lat, obre Docker Desktop → **Settings → Resources → WSL Integration** i activa
la integració amb la teva distribució Ubuntu.

### 3. Obtenir el projecte i baixar el runtime de Pyodide

Obre el terminal d'Ubuntu (WSL):

```bash
git clone https://github.com/jordibinefa/python-web-ide.git
cd python-web-ide/www
mkdir -p vendor/pyodide/0.28.3 && cd vendor/pyodide/0.28.3

for f in pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip pyodide-lock.json; do
  curl -fsSL -o "$f" "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/$f"
done

cd ../../../..
python3 vendor-package.py numpy pandas matplotlib
```

### 4. Arrencar

```bash
docker compose -f docker-compose.local.yml up -d
```

### 5. Verificar

Obre `http://localhost:8080` al navegador de Windows (Chrome, Edge...).

> **Nota:** WSL2 reenvia automàticament els ports al sistema Windows. No cal configurar res
> addicional.

---

## Opció C — VPS amb Traefik i HTTPS

### Requisits previs

- VPS amb Debian/Ubuntu i Docker instal·lat
- Traefik funcionant amb la xarxa externa `proxy` i el certresolver `letsencrypt`
- Registre DNS apuntant al VPS

### 1. Apuntar el DNS

Al teu proveïdor DNS, afegeix un registre A:

```
py.eldomini.cat  →  IP_DEL_VPS
```

### 2. Obtenir el projecte, baixar el runtime i configurar el domini

```bash
git clone https://github.com/jordibinefa/python-web-ide.git
cd python-web-ide/www
mkdir -p vendor/pyodide/0.28.3 && cd vendor/pyodide/0.28.3

for f in pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip pyodide-lock.json; do
  curl -fsSL -o "$f" "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/$f"
done

cd ../../../..
python3 vendor-package.py numpy pandas matplotlib

sed -i 's/py.exemple.cat/py.eldomini.cat/g' docker-compose.vps.yml
```

### 3. Arrencar

```bash
docker compose -f docker-compose.vps.yml up -d
```

### 4. Verificar

```bash
curl -I https://py.eldomini.cat
```

> **Nota:** el certificat HTTPS pot trigar uns minuts a emetre's la primera vegada.

---

## Exemples MQTT

La categoria d'exemples "MQTT" es connecta al broker públic de proves
**[broker.emqx.io](https://www.emqx.com/en/mqtt/public-mqtt5-broker)** per WebSocket — no cal
muntar cap broker propi, funciona directament amb qualsevol de les opcions anteriors. Si vols
un entorn totalment fora de línia / privat per a l'aula, munta el teu propi broker amb un
listener WebSocket (per exemple, Eclipse Mosquitto) i edita la URL del broker dins dels
scripts d'exemple (`mqtt_publica.py`, `mqtt_subscriu.py`, `mqtt_pub_sub.py`).

---

## Funcionalitats

- Editor amb pestanyes (CodeMirror 6) amb ressaltat de sintaxi Python
- Importació/exportació ZIP de projectes sencers, amb exemples predefinits per categoria
  (Bàsic, Científic, TKinter, MQTT)
- Subconjunt de `tkinter` (finestres, widgets, `mainloop()`/`update()`) — vegeu
  [`CONTEXT_tkinter_shim.md`](CONTEXT_tkinter_shim.md) per al seu disseny i limitacions
  conegudes
- Subconjunt de `requests` (`get`/`post`, amb `json=`/`params=`/`headers=`) sobre un
  `XMLHttpRequest` síncron — no calen backend ni proxy
- MQTT (`paho.mqtt.client`) per WebSocket
- Pestanyes de fitxers de dades: els fitxers creats amb `open(..., "w")` obtenen la seva
  pròpia pestanya, a l'estil d'onlinegdb.com, i s'inclouen a l'exportació ZIP
- Directives al hash de la URL (`#run:`, `#open:`) per incrustar o llançar un projecte
  directament des d'un enllaç — vegeu [`www/ajuda.html`](www/ajuda.html)

## Estructura del repositori

```
python-web-ide/
├── docker-compose.local.yml   ← ús local (VM / WSL), port 8080, sense Traefik
├── docker-compose.vps.yml     ← ús en VPS, Traefik + HTTPS
├── nginx.conf                 ← capçaleres COOP/COEP/CORP (calen per a SharedArrayBuffer)
├── vendor-package.py          ← baixa els paquets opcionals de Pyodide (numpy, pandas...)
├── ajuda.md
├── README.md
├── LLEGEIX-ME.md
├── CONTEXT_*.md               ← notes de desenvolupament (disseny dels shims, paranys
│                                 coneguts) — no calen per executar l'IDE, útils si l'amplies
└── www/
    ├── index.html             ← el propi IDE (pestanyes, editor, orquestració del worker)
    ├── ajuda.html
    ├── assets/
    │   ├── tkinter_shim.py
    │   ├── paho_mqtt_shim.py
    │   ├── http_shim.py
    │   ├── fs_shim.py
    │   └── worker.js
    ├── exemples/               ← projectes d'exemple predefinits (.zip) + index.txt
    └── vendor/
        ├── codemirror/6.0.2/
        ├── jszip/3.10.1/
        ├── mqtt/5.15.1/
        ├── paho/1.0/
        └── pyodide/0.28.3/    ← NO és a Git, vegeu "Baixar el runtime de Pyodide" més amunt
```

## Gestió del contenidor

```bash
# Aturar
docker compose -f docker-compose.local.yml down

# Reiniciar
docker compose -f docker-compose.local.yml restart

# Veure logs en temps real
docker compose -f docker-compose.local.yml logs -f
```

(canvia `-f docker-compose.local.yml` per `-f docker-compose.vps.yml` en un VPS)

---

## Resolució de problemes

**Pàgina en blanc, o errors a la consola que mencionen `SharedArrayBuffer`**
La pàgina s'ha de servir per HTTP(S) des d'un servidor web real (mai obrint-la com a fitxer
local `file://`), i la resposta necessita les capçaleres
`Cross-Origin-Opener-Policy`/`Cross-Origin-Embedder-Policy` ja configurades a `nginx.conf`. Si
poses un altre reverse proxy davant de nginx, assegura't que no elimina aquestes capçaleres.

**`tkinter`/`input()` donen un error que menciona `SharedArrayBuffer`**
Mateixa causa que l'anterior — comprova les capçaleres de resposta contra la teva pròpia URL:
`curl -I https://la-teva-url/`.

**Els exemples MQTT no es connecten**
Comprova que les connexions WebSocket de sortida cap a `broker.emqx.io` no estan bloquejades
per un tallafocs (algunes xarxes escolars bloquegen ports no estàndard).

**`ModuleNotFoundError: numpy` / `pandas` / `matplotlib`**
Executa `python3 vendor-package.py numpy pandas matplotlib` (pas 3 de cada opció
d'instal·lació de més amunt).

**La primera càrrega és lenta**
Normal — el navegador es baixa el runtime de Pyodide (desenes de MB) per primer cop.
`nginx.conf` configura una caché de llarga durada (`Cache-Control: immutable`) a `/vendor/`,
així que les càrregues següents són instantànies.

**El certificat HTTPS no apareix (VPS)**
Espera uns minuts i comprova el DNS: `dig py.eldomini.cat`.

---

## Llicència

MIT — lliure per usar, adaptar i compartir amb finalitats educatives.
