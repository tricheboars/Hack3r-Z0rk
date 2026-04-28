# H@ck3r-Z0rk — Browser Deployment Guide

## What This Subfolder Is

This is the **browser deployment layer** for H@ck3r-Z0rk. The goal: make the game
playable in any browser, with zero client install, via a real terminal emulator
(xterm.js) talking WebSocket to the Python game engine running on a Proxmox LXC.

**The game engine is not touched.** All Python code in `../hackerzork/` stays
exactly as-is. This layer is a thin I/O bridge only.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Browser (any device)                                   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  xterm.js terminal emulator                     │   │
│  │  · renders game output (ANSI codes intact)      │   │
│  │  · sends keystrokes over WebSocket              │   │
│  │  · tab-complete UI, resize support              │   │
│  └──────────────────┬──────────────────────────────┘   │
└─────────────────────│───────────────────────────────────┘
                      │  wss://  (TLS)
                      │
┌─────────────────────▼───────────────────────────────────┐
│  Proxmox LXC  (Debian 12, ~512MB RAM)                   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  nginx                                          │   │
│  │  · serves static files (index.html + xterm.js) │   │
│  │  · reverse-proxies /ws → localhost:8765         │   │
│  │  · TLS termination (Let's Encrypt or self-sign) │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │  ws://localhost:8765              │
│  ┌──────────────────▼──────────────────────────────┐   │
│  │  ws_server.py  (asyncio + websockets lib)       │   │
│  │  · one GameSession per WebSocket connection     │   │
│  │  · spawns Game + Shell per session              │   │
│  │  · pipes ws recv → shell.execute()              │   │
│  │  · pipes shell output → ws send                 │   │
│  │  · session timeout + cleanup                    │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │  Python function calls            │
│  ┌──────────────────▼──────────────────────────────┐   │
│  │  hackerzork game engine  (unchanged)            │   │
│  │  game.py → shell.py → all systems               │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Managed by: systemd unit  hackerzork-ws.service        │
└─────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
browser-deploy/
├── CLAUDE.md                  ← you are here
├── specs/
│   ├── 01_ws_server.md        ← WebSocket server spec
│   ├── 02_shell_adapter.md    ← how shell.py gets bridged
│   ├── 03_frontend.md         ← xterm.js frontend spec
│   ├── 04_nginx.md            ← nginx config spec
│   └── 05_lxc_setup.md        ← Proxmox LXC provisioning
├── server/
│   ├── ws_server.py           ← WebSocket server (TO BUILD)
│   ├── session.py             ← GameSession class (TO BUILD)
│   └── requirements.txt       ← websockets, hackerzork deps
├── frontend/
│   ├── index.html             ← xterm.js terminal page (TO BUILD)
│   └── term.js                ← WebSocket ↔ xterm.js glue (TO BUILD)
├── nginx/
│   └── hackerzork.conf        ← nginx site config (TO BUILD)
├── systemd/
│   └── hackerzork-ws.service  ← systemd unit (TO BUILD)
└── scripts/
    ├── provision_lxc.sh       ← LXC setup script (TO BUILD)
    └── deploy.sh              ← git pull + restart (TO BUILD)
```

---

## Key Design Decisions

### 1. Shell adapter strategy — NO changes to shell.py

`shell.execute(raw: str) -> str` already exists and works perfectly.
The WebSocket server calls it directly. We do NOT use `shell.run()` (which
reads from stdin). Instead, `session.py` implements its own async loop:

```python
async def _ws_loop(self, ws):
    async for message in ws:
        line = message.strip()
        if line in ("exit", "quit"):
            await ws.close(); return
        output = self._shell.execute(line)   # <- existing method, no changes
        if output:
            await ws.send(output + "\r\n")
        # SkyNet observation
        await self._shell._ctx.skynet.maybe_intervene()
```

### 2. One Game instance per WebSocket connection

Each browser tab gets a fully isolated game session — its own VirtualFS,
HeatSystem, GameState, SkyNet engine. Sessions are garbage-collected on
disconnect. No shared state between players.

### 3. Audio — disabled server-side, reimplemented client-side

`pygame.mixer` cannot run headless on an LXC. The game boots with
`audio_enabled=False`. Browser-side ambient sound and SFX are implemented
separately in `term.js` using the Web Audio API, triggered by ANSI escape
sequences or JSON side-channel messages that the server injects alongside
game output.

### 4. Effects — ANSI codes flow through xterm.js natively

Rich's ANSI output (colors, bold, dim) renders perfectly in xterm.js.
No special handling needed. Typewriter effects that currently use `time.sleep`
are replaced by streaming: the server sends output character-by-character
(or line-by-line with delay) over the WebSocket.

### 5. Transport format — plain text with optional JSON side-channel

Normal game output is plain text (with ANSI codes). Special events that need
to trigger browser-side behavior (SkyNet alerts, audio cues, glitch effects)
are sent as a JSON envelope:

```json
{"type": "event", "name": "skynet_intervene", "payload": {...}}
```

The frontend checks if a message starts with `{` and routes accordingly.

### 6. Session timeout

Sessions idle for >30 minutes are terminated server-side. The client
receives a goodbye message and the WebSocket closes cleanly.

---

## The Frontend Shell — `website/game.html` ← READ THIS FIRST

**The frontend already exists and is complete. Do NOT recreate it.**

`../website/game.html` is the fully designed browser game shell. It was built
separately in Cowork and is the authoritative UI. Your job is to make the
Python WebSocket server speak to it correctly — not to build a new frontend.

### What game.html contains

- **xterm.js terminal** (v5.3.0) — center pane, full screen, green phosphor theme
- **Right sidebar** with two panels:
  - `#net-panel` — network map, starts locked, populates via side-channel events
  - `#file-panel` — discovered files catalogue, clickable file viewer overlays
- **Heat HUD** — bottom bar, animated bar + color shift green→amber→red
- **SkyNet alert** — dismissable overlay window, bottom-right corner
- **Boot splash** — fake systemd log on load, fades to terminal
- **Demo mode** — full JS mini-sim runs when no WebSocket is available.
  This is the fallback for players before the LXC is connected.

### How it connects to your server

On load, `game.html` opens a WebSocket to:
```
ws://  + location.host + '/ws'    (HTTP)
wss:// + location.host + '/ws'    (HTTPS)
```
Override by setting `window.HZ_WS_URL` before the script tag.

nginx on the LXC serves `game.html` as a static file and proxies `/ws`
to your Python server on port 8765. That's it — no changes to `game.html`.

### Input protocol (browser → server)

The browser sends JSON objects:
```json
{ "type": "input",  "data": "<key or line>"  }
{ "type": "resize", "cols": 120, "rows": 38   }
```

Your server receives these, extracts `data`, passes to `shell.execute()`.

### Output protocol (server → browser)

**Plain text** (ANSI codes included) → xterm.js renders it directly:
```
\x1b[32muser@localhost\x1b[0m:~$ ls\r\n
```

**Side-channel JSON** → starts with `{`, routed to `handleSideChannel()`:
```json
{ "type": "event", "name": "heat_update",      "payload": { "heat": 47.3 } }
{ "type": "event", "name": "node_discovered",  "payload": { "ip": "10.13.37.1", "name": "Proxy Relay Alpha", "hostname": "relay-alpha.darknet.local", "status": "scanned", "connections": ["10.13.37.2"] } }
{ "type": "event", "name": "file_catalogued",  "payload": { "path": "/home/user/evidence/README.md", "name": "README.md", "content": "...", "modified": "2026-03-15T02:34:11", "owner": "user", "encrypted": false, "isNew": true } }
{ "type": "event", "name": "skynet_alert",     "payload": { "message": "I see you.", "level": 1 } }
{ "type": "event", "name": "glitch",           "payload": { "duration_ms": 400 } }
{ "type": "event", "name": "prompt_update",    "payload": { "user": "admin", "node": "relay-alpha" } }
```

### What fires which side-channel event

Wire these up in `session.py` by listening to the game's EventBus:

| Game event (EventBus)  | Side-channel to send          | When                          |
|------------------------|-------------------------------|-------------------------------|
| `heat_changed`         | `heat_update`                 | Every heat change             |
| `scan_performed`       | `node_discovered`             | After nmap completes          |
| `file_read`            | `file_catalogued`             | After cat/less reads a file   |
| `skynet_intervene`     | `skynet_alert`                | SkyNet fires an action        |
| `node_compromised`     | `node_discovered` (status: owned) | After successful exploit |
| `glitch_triggered`     | `glitch`                      | Meta engine corruption effects|
| `node_changed`         | `prompt_update`               | After ssh to a new node       |

Subscribe in `GameSession.start()`:
```python
ctx.events.on('heat_changed',    self._on_heat_changed)
ctx.events.on('scan_performed',  self._on_scan_performed)
ctx.events.on('file_read',       self._on_file_read)
ctx.events.on('skynet_intervene',self._on_skynet_intervene)
```

Then emit JSON alongside normal output:
```python
async def _on_heat_changed(self, **kwargs):
    heat = kwargs.get('heat', 0)
    await self.ws.send(json.dumps({
        "type": "event", "name": "heat_update",
        "payload": {"heat": round(heat, 1)}
    }))
```

### nginx static file serving

nginx serves `../website/` as the document root (not `browser-deploy/frontend/`).
`game.html` and `index.html` are both in `../website/`. Update `nginx/hackerzork.conf`:
```nginx
root /opt/hackerzork/repo/website;
```

The `frontend/` subfolder in `browser-deploy/` is now **unused** — `game.html`
is the frontend. Don't create `frontend/index.html`.

---

## Session Build Plan for Claude Code

Work through these sessions in order. Each session is self-contained.
Run `pytest` after each session before moving on.

| # | What to build | Files | Spec |
|---|---------------|-------|------|
| 1 | `session.py` — GameSession + EventBus wiring | `server/session.py` | `specs/02_shell_adapter.md` |
| 2 | `ws_server.py` — WebSocket server | `server/ws_server.py` | `specs/01_ws_server.md` |
| 3 | nginx config — serve `website/` + proxy `/ws` | `nginx/hackerzork.conf` | `specs/04_nginx.md` |
| 4 | systemd unit | `systemd/hackerzork-ws.service` | — |
| 5 | LXC provisioning script | `scripts/provision_lxc.sh` | `specs/05_lxc_setup.md` |
| 6 | Deploy script | `scripts/deploy.sh` | — |
| 7 | Integration test — connect, type `ls`, get output + heat event | `tests/test_ws_session.py` | — |

**Session 3 (frontend) from the original plan is dropped** — `game.html` already exists.

---

## Python Conventions

Same as the main project:
- Python 3.11–3.13 (`.venv/` at project root — reuse it)
- `from __future__ import annotations`
- Type hints everywhere, dataclasses for data structures
- `asyncio` throughout — never `threading`
- `websockets` library (>=12.0) for the server
- `pytest` + `pytest-asyncio` for tests
- **No pygame** in this layer — `audio_enabled=False` always

---

## Environment Variables (server)

```bash
HZ_HOST=0.0.0.0          # bind address
HZ_PORT=8765              # WebSocket port
HZ_MAX_SESSIONS=20        # hard cap on concurrent sessions
HZ_SESSION_TIMEOUT=1800   # seconds before idle kill (30 min)
HZ_DEBUG=0                # 1 = verbose logging
```

---

## Running Locally (dev)

```bash
# From project root — activate venv
source .venv/bin/activate
pip install websockets

# Start WebSocket server
python -m browser_deploy.server.ws_server

# Serve the website/ folder (game.html lives here)
cd website/
python -m http.server 3000

# Open http://localhost:3000/game.html in browser
# The terminal boots, attempts ws://localhost:3000/ws
# → nginx proxies /ws to :8765 in prod
# → in dev, point game.html at ws://localhost:8765 directly:
#   open http://localhost:3000/game.html?ws=ws://localhost:8765
#   (or set window.HZ_WS_URL in browser console before load)
```

**Quick dev trick** — in browser console before the page loads:
```js
window.HZ_WS_URL = 'ws://localhost:8765';
```
Or add `?ws=ws://localhost:8765` support to `game.html`'s WS_URL line:
```js
const WS_URL = new URLSearchParams(location.search).get('ws')
  || window.HZ_WS_URL
  || (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
```

---

## Proxmox LXC Spec

- **Template**: Debian 12 (bookworm) standard LXC
- **Resources**: 1 CPU core, 512MB RAM, 4GB disk (plenty)
- **Network**: bridged, static IP on your LAN (or DHCP reservation)
- **Packages**: python3.12, python3-venv, nginx, certbot (optional)
- **User**: `hackerzork` system user, no login shell, owns `/opt/hackerzork`
- **Deployment path**: `/opt/hackerzork/` — git clone of the repo
- **SSH keys**: Patrick's key pre-authorized in `/root/.ssh/authorized_keys`
  (use existing key from Proxmox node, or add during provision)

See `specs/05_lxc_setup.md` for the full step-by-step.

---

## Critical Notes for Claude Code

1. **Never modify files outside `browser-deploy/` or `hackerzork/`** without
   explicit instruction. The game engine is stable.

2. **`shell.execute()` is synchronous** — always call it in an executor if you
   need it not to block the event loop:
   ```python
   output = await loop.run_in_executor(None, self._shell.execute, line)
   ```

3. **Game boot is slow** (filesystem seeding, system init). Boot once at
   session creation, not per command.

4. **SkyNet's `maybe_intervene()`** is async — always `await` it.

5. **Rich Console output** in the game goes to a StringIO buffer server-side,
   not stdout. See `specs/02_shell_adapter.md` for how to capture it.

6. **Test with `pytest-asyncio`** — all WebSocket tests need
   `@pytest.mark.asyncio` and a running server fixture.
