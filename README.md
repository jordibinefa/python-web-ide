# Python Web IDE

> **[Llegeix-ho en català](LLEGEIX-ME.md)**

A browser-based Python IDE powered by [Pyodide](https://pyodide.org) (CPython compiled to
WebAssembly), running entirely inside a Web Worker — **no backend, no server-side code
execution**. Students write code in a multi-tab editor (CodeMirror 6) and run it directly in
their own browser: plotting with matplotlib/numpy/pandas, GUI programs with a `tkinter`
subset, MQTT messaging over WebSocket, and simple HTTP requests with a `requests` subset —
all client-side.

Live instance: https://py.binefa.cat

## How it works

```
Browser (student)
──────────────────────────────────────────────────────────
Write code (tabs, CodeMirror)
        │
        ▼
Pyodide (WebAssembly) inside a Web Worker
  ├─ tkinter_shim.py    → widgets/windows (SharedArrayBuffer ↔ main thread)
  ├─ paho_mqtt_shim.py  → MQTT.js over WebSocket (public broker.emqx.io)
  ├─ http_shim.py       → synchronous XMLHttpRequest (requests.get/post)
  └─ fs_shim.py         → watched open() → data-file tabs, included in ZIP export
        │
        ▼
Everything runs IN THE BROWSER. nginx only serves static files
(HTML/JS/CSS + the vendored Pyodide runtime) — there is no backend at all.
```

Because there's no backend, this is much lighter to install than a typical Docker-based
classroom tool: `nginx:alpine` is a few MB, and the only "heavy" step is fetching the Pyodide
runtime and the scientific packages once (see below) — no image build, no compilation.

---

## Installation

Choose your setup:

- [Linux virtual machine (Debian / Ubuntu)](#option-a--linux-virtual-machine-debian--ubuntu)
- [Windows with WSL2](#option-b--windows-with-wsl2)
- [VPS with Traefik and HTTPS](#option-c--vps-with-traefik-and-https)

---

## Option A — Linux virtual machine (Debian / Ubuntu)

### Prerequisites

- Debian 13 / Ubuntu 22.04 or later
- Docker Engine (see below if you don't have it yet)
- Internet connection for the first setup (to fetch the Pyodide runtime)

### 1. Install Docker Engine

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

# Optional: run Docker without sudo
sudo usermod -aG docker $USER && newgrp docker
```

> **Debian 13 (trixie):** if the repository fails, replace `$VERSION_CODENAME` with
> `bookworm` in the echo command above. The packages are compatible.

### 2. Get the project

```bash
git clone https://github.com/jordibinefa/python-web-ide.git
cd python-web-ide
```

### 3. Fetch the Pyodide runtime (not stored in the repo)

`www/vendor/pyodide/0.28.3/` is **not** committed to Git — the runtime plus scientific
packages together weigh hundreds of MB, and they're all publicly redistributable, so there's
no point versioning them. Fetch the core runtime first:

```bash
cd www
mkdir -p vendor/pyodide/0.28.3 && cd vendor/pyodide/0.28.3

for f in pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip pyodide-lock.json; do
  curl -fsSL -o "$f" "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/$f"
done

cd ../../../..   # back to the project root
```

Then fetch the optional scientific packages (numpy, pandas, matplotlib and their transitive
dependencies), with SHA-256 verification:

```bash
python3 vendor-package.py numpy pandas matplotlib
```

This covers everything the "Científic" example category needs. You can skip this step if you
don't need those examples — the IDE works fine without them, `import numpy` will just fail
with `ModuleNotFoundError` until you run this.

### 4. Start

```bash
docker compose -f docker-compose.local.yml up -d
```

### 5. Verify

Open `http://localhost:8080` in your browser.

> **Note:** the site must be served over HTTP(S) by a real web server, never opened as a
> local `file://` — `tkinter`/`input()` need `SharedArrayBuffer`, which browsers only allow
> with the right cross-origin-isolation headers (already set in `nginx.conf`, no extra
> configuration needed).

---

## Option B — Windows with WSL2

### Prerequisites

- Windows 10 (21H2 or later) or Windows 11
- WSL2 enabled with an Ubuntu distribution installed

### 1. Enable WSL2

Open PowerShell **as administrator**:

```powershell
wsl --install
# Restart if prompted
```

If WSL is already installed but running version 1:

```powershell
wsl --set-default-version 2
```

### 2. Install Docker Desktop

Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
During installation, make sure **"Use the WSL 2 based engine"** is checked. Once installed,
open Docker Desktop → **Settings → Resources → WSL Integration** and enable integration with
your Ubuntu distribution.

### 3. Get the project and fetch the Pyodide runtime

Open the Ubuntu (WSL) terminal:

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

### 4. Start

```bash
docker compose -f docker-compose.local.yml up -d
```

### 5. Verify

Open `http://localhost:8080` in your Windows browser (Chrome, Edge...).

> **Note:** WSL2 automatically forwards ports to the Windows host. No extra configuration
> needed.

---

## Option C — VPS with Traefik and HTTPS

### Prerequisites

- VPS running Debian/Ubuntu with Docker installed
- Traefik running with the external network `proxy` and a `letsencrypt` certresolver
- A DNS record pointing to the VPS

### 1. Point your DNS

At your DNS provider, add an A record:

```
py.yourdomain.com  →  YOUR_VPS_IP
```

### 2. Get the project, fetch the runtime, and configure the domain

```bash
git clone https://github.com/jordibinefa/python-web-ide.git
cd python-web-ide/www
mkdir -p vendor/pyodide/0.28.3 && cd vendor/pyodide/0.28.3

for f in pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip pyodide-lock.json; do
  curl -fsSL -o "$f" "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/$f"
done

cd ../../../..
python3 vendor-package.py numpy pandas matplotlib

sed -i 's/py.exemple.cat/py.yourdomain.com/g' docker-compose.vps.yml
```

### 3. Start

```bash
docker compose -f docker-compose.vps.yml up -d
```

### 4. Verify

```bash
curl -I https://py.yourdomain.com
```

> **Note:** the HTTPS certificate may take a few minutes to issue on first run.

---

## MQTT examples

The "MQTT" example category connects to the public test broker
**[broker.emqx.io](https://www.emqx.com/en/mqtt/public-mqtt5-broker)** over WebSocket — no
broker setup needed, it works out of the box on any of the options above. If you want a
fully offline / private classroom setup, run your own broker with a WebSocket listener (e.g.
Eclipse Mosquitto) and edit the broker URL inside the example scripts (`mqtt_publica.py`,
`mqtt_subscriu.py`, `mqtt_pub_sub.py`).

---

## Features

- Multi-tab editor (CodeMirror 6) with Python syntax highlighting
- ZIP import/export of whole projects, with predefined examples by category (Basic,
  Scientific, TKinter, MQTT)
- `tkinter` subset (windows, widgets, `mainloop()`/`update()`) — see
  [`CONTEXT_tkinter_shim.md`](CONTEXT_tkinter_shim.md) for its design and known limitations
- `requests` subset (`get`/`post`, with `json=`/`params=`/`headers=`) over a synchronous
  `XMLHttpRequest` — no backend proxy needed
- MQTT (`paho.mqtt.client`) over WebSocket
- Data-file tabs: files created with `open(..., "w")` get their own tab, like onlinegdb.com,
  and are included in the ZIP export
- URL hash directives (`#run:`, `#open:`) to embed or launch a project directly from a link —
  see [`www/ajuda.html`](www/ajuda.html)

## Repository structure

```
python-web-ide/
├── docker-compose.local.yml   ← local use (VM / WSL), port 8080, no Traefik
├── docker-compose.vps.yml     ← VPS use, Traefik + HTTPS
├── nginx.conf                 ← COOP/COEP/CORP headers (needed for SharedArrayBuffer)
├── vendor-package.py          ← fetches optional Pyodide packages (numpy, pandas...)
├── ajuda.md
├── README.md
├── LLEGEIX-ME.md
├── CONTEXT_*.md               ← development notes (shim design, known pitfalls) —
│                                 not needed to run the IDE, useful if you extend it
└── www/
    ├── index.html             ← the IDE itself (tabs, editor, worker orchestration)
    ├── ajuda.html
    ├── assets/
    │   ├── tkinter_shim.py
    │   ├── paho_mqtt_shim.py
    │   ├── http_shim.py
    │   ├── fs_shim.py
    │   └── worker.js
    ├── exemples/               ← predefined example projects (.zip) + index.txt
    └── vendor/
        ├── codemirror/6.0.2/
        ├── jszip/3.10.1/
        ├── mqtt/5.15.1/
        ├── paho/1.0/
        └── pyodide/0.28.3/    ← NOT in Git, see "Fetch the Pyodide runtime" above
```

## Container management

```bash
# Stop
docker compose -f docker-compose.local.yml down

# Restart
docker compose -f docker-compose.local.yml restart

# Follow logs
docker compose -f docker-compose.local.yml logs -f
```

(swap `-f docker-compose.local.yml` for `-f docker-compose.vps.yml` on a VPS)

---

## Troubleshooting

**Blank page, or console errors mentioning `SharedArrayBuffer`**
The page must be served over a real HTTP(S) server (never opened as a local `file://`), and
the response needs the `Cross-Origin-Opener-Policy`/`Cross-Origin-Embedder-Policy` headers
already set in `nginx.conf`. If you put another reverse proxy in front of nginx, make sure it
isn't stripping these headers.

**`tkinter`/`input()` raise an error mentioning `SharedArrayBuffer`**
Same cause as above — check the response headers against your own URL:
`curl -I https://your-url/`.

**MQTT examples don't connect**
Check that outbound WebSocket connections to `broker.emqx.io` aren't blocked by a firewall
(school networks sometimes block non-standard ports).

**`ModuleNotFoundError: numpy` / `pandas` / `matplotlib`**
Run `python3 vendor-package.py numpy pandas matplotlib` (step 3 in each installation option
above).

**First load is slow**
Normal — the browser is downloading the Pyodide runtime (tens of MB) for the first time.
`nginx.conf` sets long-lived caching (`Cache-Control: immutable`) on `/vendor/`, so
subsequent loads are instant.

**HTTPS certificate not appearing (VPS)**
Wait a few minutes, then check DNS: `dig py.yourdomain.com`.

---

## Licence

MIT — free to use, adapt and share for educational purposes.
