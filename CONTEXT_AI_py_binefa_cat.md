# Context for AI assistants: writing Python that runs on both py.binefa.cat (browser) and a real terminal

This document is for any AI assistant (Claude, or otherwise) helping Jordi —
or a student — write a Python script that must work **unmodified** in two
very different execution environments:

1. **py.binefa.cat** — a browser-based Python IDE built on **Pyodide**
   running inside a Web Worker, with a custom `tkinter` shim and a custom
   `paho.mqtt.client` shim. Code is injected via a URL hash
   (`#run:...&clau=valor`) and executed with `pyodide.runPythonAsync()`.
2. **A real terminal** — `python3 script.py` (or `python3 script.py
   key=value ...`) on a normal desktop/Raspberry Pi install, with **real**
   `tkinter` and **real** `paho-mqtt` (installed via pip).

It complements two other documents in this project:
- `ajuda.md` — user-facing (Catalan) help for people *using* py.binefa.cat.
  Section 13 of that document covers the same portability pattern described
  here, in Catalan, with less implementation rationale.
- `CONTEXT_tkinter_shim.md` — internal context for whoever maintains the
  **shim itself** (the JS/Python code that implements `tkinter`/`paho` inside
  Pyodide). That document is about building the IDE; this one is about
  writing *student/example code* that targets it.

If you are asked to write or modify a Python script that combines
`tkinter` and/or MQTT, and portability to a real terminal matters (or is
even just plausible later), apply the patterns below from the start —
retrofitting them after the fact is more error-prone than starting with
them.

---

## 1. The core problem: two incompatible `await` models

Pyodide's `runPythonAsync()` compiles the whole submitted script with a
special flag that allows **top-level `await`** (similar to IPython's
autoawait / a Jupyter cell). This means, inside py.binefa.cat, you can
write:

```python
while not stop:
    window.update()
    await asyncio.sleep(0.05)
```

directly at module level, with no enclosing `async def`. This works
*only* because Pyodide already has an asyncio event loop actively running
for the entire duration of the script's top-level execution.

A real CPython interpreter does **not** support this. `await` outside an
`async def` is a **SyntaxError raised at compile time**, unconditionally —
even if the line is never reached at runtime (e.g. inside an `if False:`
block). You cannot "hide" a bare top-level `await` behind a runtime check;
the whole file fails to parse.

The opposite is also true: calling `asyncio.run(main())` — the standard,
correct way to launch an async program from a real terminal — **crashes
inside py.binefa.cat** with:

```
RuntimeError: WebAssembly stack switching not supported in this JavaScript runtime
```

This happens because Pyodide's browser build lacks the WebAssembly
JSPI ("stack switching") feature that `asyncio.run()` would need to
create and drive a *second*, nested event loop from inside a coroutine
that is itself already running on the first one. This is **not** a
"loop already running" RuntimeError you can catch and retry — it is a
hard, unrecoverable crash the moment `asyncio.run()` is called, sourced
from the sandbox itself, not from asyncio's own state checks.

**Neither environment tolerates the other's idiom.** You cannot write one
piece of syntax that is simultaneously valid top-level `await` (for the
browser) and a normal blocking call (for the terminal). The solution is
structural, not syntactic: always define the loop body as an `async def`,
and choose how to launch it at runtime.

---

## 2. The environment-detection + dual-launch pattern

Detect the environment once, near the top of the file, before it's needed
anywhere else:

```python
import asyncio

try:
    asyncio.get_running_loop()
    in_browser = True     # Pyodide already has a loop running
except RuntimeError:
    in_browser = False    # plain terminal script: no loop yet
```

This works because Pyodide's top-level-await mechanism wraps the *entire*
module body in a synthetic coroutine that is scheduled and run on
Pyodide's own event loop (a `WebLoop`) for its whole execution — so
`asyncio.get_running_loop()` succeeds at literally any point in the
script, from the very first line onward, when running under
`runPythonAsync()`. In a plain terminal script, no loop exists yet at
module level, so the call raises `RuntimeError` and you get `False`.

Then define the loop body as a coroutine, and launch it differently per
environment:

```python
async def main_loop():
    stop = False
    while not stop:
        window.update()                # never mainloop() — see §5
        await asyncio.sleep(0.05)

if in_browser:
    # A loop is already running (that's why bare top-level `await` used
    # to work); schedule ours as a task on it instead of blocking on it.
    asyncio.ensure_future(main_loop())
else:
    # No loop yet: create one and run until main_loop() returns (which,
    # by design here, is "never", until the window is closed — see §6).
    asyncio.run(main_loop())
```

**Never call `asyncio.run()` unconditionally.** Always gate it behind the
`in_browser` check, or you reproduce the "WebAssembly stack switching"
crash the moment the script is loaded in the browser.

**⚠️ Confirmed regression in the browser — read before applying this
pattern to a short-lived/repeatable demo:** because
`asyncio.ensure_future()` is fire-and-forget (it schedules the task and
returns immediately), the top-level module execution finishes almost
immediately after this call — unlike the old bare-`await` pattern, where
the module literally never returned until the program was stopped. This
was initially flagged only as a *possibly cosmetic* status-text quirk, but
empirical testing on the three MQTT example scripts (`mqtt_publica`,
`mqtt_subscriu`, `mqtt_pub_sub`) showed a real functional regression: the
IDE's **"Interromp" (stop) button stops working**. The most likely
mechanism: "Interromp" injects a `KeyboardInterrupt` into the coroutine
that `runPythonAsync()` is actively awaiting — which, after this pattern
is applied, is only the (now-finished) top-level module body, not the
detached task scheduled via `ensure_future()`. There is nothing left at
that point for the interrupt to reach.

**Practical guidance based on this finding:**
- For a program the person launches **once** and stops by closing the Tk
  window itself (like `tk_mqtt_smm.py`, which has its own
  `WM_DELETE_WINDOW`-equivalent handling — see §6), this pattern is fine:
  functionally verified to keep working correctly end-to-end.
- For a **short, frequently-restarted classroom demo** where the person
  relies on the IDE's own "Interromp" button to stop/reset execution
  (typical of small standalone MQTT or asyncio examples, not bundled with
  a `tkinter` window), **do not** apply the `in_browser` + `ensure_future`
  conversion to the browser-facing `main.py`. Keep `main.py` exactly as
  it was — bare top-level `await`, browser-only — and instead ship a
  **separate, clearly-named companion file** (e.g.
  `mqtt_publica_terminal.py`) containing the `async def` +
  `asyncio.run()` version, meant to only ever be run from a terminal.
  Duplicating ~20 lines is a small price for keeping "Interromp" working
  reliably; don't apply this document's dual-launch pattern to a single
  file just because it's *possible* to unify them — check first whether
  the person actually relies on interrupting execution mid-run.

---

## 3. Passing parameters: URL hash vs. command-line arguments

In the browser, `#run:_prj=zip:<url>&key=value&...` variables are injected
by `worker.js` as plain Python globals (always `str`, never coerced),
re-injected on every "Executa". The idiomatic read pattern is:

```python
if 'key' in globals():
    ...
```

For terminal portability, the natural equivalent is `key=value` arguments
on the command line:

```
python3 script.py id=1234 temaPub1=/prova/pub/1234 autoConnecta=1
```

Unify both sources behind one helper, gated by the same `in_browser` flag:

```python
import sys

def _parse_terminal_args():
    args = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            key, value = arg.split("=", 1)
            args[key] = value
        else:
            print(f"[Warning] Ignoring non key=value argument: {arg!r}")
    return args

# Browser variables are already globals (injected before execution);
# terminal variables are parsed once from sys.argv.
_terminal_args = {} if in_browser else _parse_terminal_args()

def initial_value(name, default):
    if in_browser:
        return globals()[name] if name in globals() else default
    return _terminal_args.get(name, default)
```

Every call site that previously did `globals()[name] if name in
globals() else default` should go through this single function instead.

---

## 4. File paths (images, assets)

In the browser, `worker.js` writes project assets (images, etc.) to the
**root of Pyodide's virtual filesystem** (`/name.png`). The `PhotoImage`
shim itself already handles this transparently for `PhotoImage(file=...)`
— it silently prepends `/` if you pass a bare filename, so
`tk.PhotoImage(file="icon.png")` works unmodified in both environments
(in the browser thanks to the shim; on the desktop because it resolves
relative to the current working directory, which happens to be where
you're running the script from).

But **your own `open(...)` calls** (e.g. reading raw file bytes to base64-encode
for an MQTT payload) get no such help. On a real desktop, "current working
directory" is not necessarily "the directory the script lives in" — a
student might `cd` elsewhere and run `python3 ~/projects/foo/script.py`.
Resolve explicitly:

```python
import os

def asset_path(filename):
    if in_browser:
        return "/" + filename
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
```

Use `asset_path(...)` for anything you `open()` yourself; leave
`PhotoImage(file=...)` calls with bare filenames (no need to route them
through this helper).

---

## 5. `tkinter`: `Tk.update()`, never `mainloop()`, when combined with async code

This is unrelated to browser/terminal portability per se, but it's the
foundation the rest of this document builds on, so it's worth restating
here (see also `ajuda.md` §9 and `CONTEXT_tkinter_shim.md`): `mainloop()`
blocks (via a real, synchronous wait) until an event arrives, and while it
runs, nothing else — including MQTT network processing — gets a chance to
execute. This is true **both** in the shim (where the block happens via
`Atomics.wait`, freezing the whole Worker thread MQTT.js lives in) and in
real desktop Python (where `mainloop()` simply never returns control to
your `asyncio` loop). Always use the non-blocking `update()` inside the
async main loop pattern from §2, in both environments:

```python
async def main_loop():
    stop = False
    while not stop:
        window.update()             # process pending clicks, return immediately
        await asyncio.sleep(0.05)   # yield control so MQTT can be processed
```

Never mix `mainloop()` and `update()` in the same program.

---

## 6. Closing the window from the terminal

The shim's `Tk` class does **not** implement `.protocol()` (there's no
concept of "closing" an iframe from the outside the way an OS window
close button works, so it was never needed there). On a real desktop, if
you don't handle the window-close event, clicking the window's close (X)
button destroys the Tk window but does **not** stop your asyncio loop —
`window.update()` typically doesn't raise afterward either, so the script
just hangs, requiring `Ctrl+C`.

Gate `.protocol()` behind the same `in_browser` flag so it's never called
against the shim (which would raise `AttributeError`):

```python
window_closed = False

def _on_close():
    global window_closed
    window_closed = True
    try:
        window.destroy()
    except Exception:
        pass

if not in_browser:
    window.protocol("WM_DELETE_WINDOW", _on_close)
```

And check the flag in the loop condition (in addition to, or instead of, a
plain `stop` flag):

```python
async def main_loop():
    while not window_closed:
        try:
            window.update()
        except tk.TclError:
            break   # window already destroyed; defensive, on top of the protocol handler
        await asyncio.sleep(0.05)
```

---

## 7. MQTT: the browser shim is single-threaded, real `paho-mqtt` is not

This is the single most important, easy-to-miss gotcha for anyone porting
MQTT+tkinter code between the two environments, and it produces a
runtime error, not a syntax error, so it only surfaces when actually
tested on the desktop.

**In the browser**, the `paho.mqtt.client` shim's callbacks
(`on_connect`, `on_message`, etc.) are invoked synchronously, on the
*same single thread* everything else runs on (there are no real OS
threads inside a Web Worker in this architecture). This means example
code that touches `tkinter` widgets directly inside `on_connect`/
`on_message` works completely fine in the browser.

**On a real desktop**, `paho-mqtt`'s `client.loop_start()` spawns an
actual background **OS thread** to run the network loop, and all
callbacks fire on *that* thread. Real `tkinter` is **not thread-safe** —
touching any widget from a non-main thread raises:

```
RuntimeError: main thread is not in main loop
```

The fix, which is safe and essentially free to use in **both**
environments (in the browser it just adds at most one polling cycle of
latency, ~50ms, since there's no real concurrency to protect against
there): route all UI-touching work from MQTT callbacks through a
thread-safe `queue.Queue`, and only ever touch `tkinter` widgets from the
main loop that already owns the Tk mainloop-equivalent (`window.update()`,
running in `main_loop()`):

```python
import queue
mqtt_queue = queue.Queue()

def on_connect(client, userdata, flags, rc):
    # Safe to call paho methods themselves from this thread (e.g.
    # client.subscribe(...) — this is the standard, documented paho
    # pattern). NEVER touch tkinter widgets here directly.
    if rc == 0:
        client.subscribe(topic)
    mqtt_queue.put(("connect_status", rc))

def on_message(client, userdata, msg):
    mqtt_queue.put(("message", msg.topic, msg.payload))
    # again: no widget access here

def drain_mqtt_queue():
    """Call this once per tick from main_loop(), on the main thread."""
    while True:
        try:
            event = mqtt_queue.get_nowait()
        except queue.Empty:
            break
        if event[0] == "connect_status":
            update_ui_for_status(event[1])
        elif event[0] == "message":
            handle_message(event[1], event[2])   # tkinter access happens here, safely

async def main_loop():
    while not window_closed:
        window.update()
        drain_mqtt_queue()
        await asyncio.sleep(0.05)
```

Calling `client.subscribe()`/`unsubscribe()`/`publish()` directly from
within a paho callback (even on the background thread) is fine — that's
paho's own standard, documented usage pattern, and doesn't touch
`tkinter` at all. The queue is only needed for the tkinter-facing side of
things.

---

## 8. Other shim limitations worth knowing before writing example code

These aren't specific to browser/terminal portability, but they will bite
you if you write code assuming full real-`tkinter`/real-`paho` behavior
and only test it in one environment:

- **No `Canvas`, no `Toplevel`** — only the single main window.
- **No `columnconfigure()`/`rowconfigure()`** on `grid()` — `columnspan`,
  `rowspan`, and `sticky` do work.
- **No generic `bind()`** — only `command=` on buttons/etc.
- **`PhotoImage.width()`/`.height()` always return `0`** in the shim
  (measuring would require an async image decode, incompatible with the
  shim's synchronous call bridge).
- **No `PhotoImage.subsample()`/`.zoom()`** — if a script needs to resize
  images at runtime, this must be done with Pillow (available in this
  Pyodide build) instead, or the images must be pre-sized as project
  assets before upload (e.g. with ImageMagick) rather than resized live.
- **`Label.config(image=..., text=...)` together, in the same call, breaks
  image rendering** in the shim — the image silently fails to display
  (confirmed empirically: identical image data displays correctly when
  `config()` is called with `image=...` alone, and never displays when
  `text=""` is passed alongside it, regardless of image size/content).
  Never combine them; call `config(image=...)` on its own.
- **MQTT is `wss`-only** (no raw TCP) — connect only to broker ports that
  speak WebSocket (commonly 8084/8081/8000/9002). `loop_forever()` raises
  `RuntimeError` explicitly in the shim (it would freeze the single
  thread); always use `loop_start()` + the async loop pattern from §5,
  never `time.sleep()` in a loop (it would freeze message reception the
  same way `mainloop()` would).
- **`msg.payload` is `bytes`** in both the shim and real paho — always
  `.decode("utf-8")` before treating it as text/JSON.

---

## 9. Minimal end-to-end template

Putting it all together — a skeleton combining every pattern above:

```python
import asyncio
import os
import queue
import sys

import tkinter as tk
import paho.mqtt.client as mqtt

# ── 1. Environment detection ────────────────────────────────────────────
try:
    asyncio.get_running_loop()
    in_browser = True
except RuntimeError:
    in_browser = False


def asset_path(filename):
    if in_browser:
        return "/" + filename
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def _parse_terminal_args():
    args = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            args[k] = v
    return args


_terminal_args = {} if in_browser else _parse_terminal_args()


def initial_value(name, default):
    if in_browser:
        return globals()[name] if name in globals() else default
    return _terminal_args.get(name, default)


# ── 2. MQTT: queue-based bridge to tkinter (safe in both environments) ──
mqtt_queue = queue.Queue()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(initial_value("topic", "example/topic"))
    mqtt_queue.put(("status", rc))


def on_message(client, userdata, msg):
    mqtt_queue.put(("message", msg.topic, msg.payload))


def drain_mqtt_queue():
    while True:
        try:
            event = mqtt_queue.get_nowait()
        except queue.Empty:
            break
        # handle event[0] == "status" / "message" here, touching tkinter freely


# ── 3. Window ────────────────────────────────────────────────────────────
window = tk.Tk()
window_closed = False


def _on_close():
    global window_closed
    window_closed = True
    try:
        window.destroy()
    except Exception:
        pass


if not in_browser:
    window.protocol("WM_DELETE_WINDOW", _on_close)

# ... build widgets, start the mqtt.Client(), etc. ...


# ── 4. Main loop: async def + dual launch ───────────────────────────────
async def main_loop():
    while not window_closed:
        try:
            window.update()
        except tk.TclError:
            break
        drain_mqtt_queue()
        await asyncio.sleep(0.05)


if in_browser:
    asyncio.ensure_future(main_loop())
else:
    asyncio.run(main_loop())
```

---

## 10. Keeping this document current

If you (an AI assistant) discover a new browser/terminal discrepancy while
helping with a py.binefa.cat script — a new shim limitation, a new
threading gotcha, a new path/encoding difference — add it here, and
consider whether `ajuda.md` §13 (the Catalan, user-facing version of this
same guidance) also needs the update. Treat empirical findings (things
actually observed failing/working across both environments) as more
reliable than a priori reasoning about what "should" work — several of
the gotchas above (e.g. the `image=`+`text=` bug, the exact
`asyncio.run()` crash message) were only confirmed by deliberately testing
minimal reproductions across both environments side by side.
