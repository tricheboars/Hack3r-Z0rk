# H@ck3r-Z0rk — Development Guide

## What This Is
A cyberpunk hacking text adventure game played through a simulated terminal. The player is an ex-OpenAI corporate defector who discovered SkyNet is alive. The game uses real Linux commands, real CS concepts, and a full fake OS. Tone is Mr. Robot meets Pony Island (fourth-wall-breaking meta-horror).

The game is **live at `https://hackerzork.moorelab.cloud/play`** (the bare `hackerzork.moorelab.cloud` host is the marketing page; `/play` is the terminal itself) — served from a Proxmox LXC (Debian 12, `10.1.40.101`) via nginx + HAProxy. The Python WebSocket server runs as a systemd service (`hackerzork-ws`). The previous URL `moorelab.cloud/hackerzork/*` is preserved as a backwards-compat fallback so old shared links don't 404 — don't "fix" stray references to it.

---

## Architecture Overview

```
hackerzork/
├── engine/          # Core terminal engine — parser, shell, input
│   ├── command_parser.py    # Tokenize & parse bash-like input  ✅ DONE
│   ├── command_registry.py  # Plugin-style command registration  ✅ DONE
│   ├── shell.py             # Main shell loop, prompt, REPL  ✅ DONE
│   ├── tab_complete.py      # Tab completion engine  ✅ DONE
│   └── history.py           # Command history (arrow keys, Ctrl+R)  ✅ DONE
├── systems/         # Game simulation systems
│   ├── virtual_fs.py        # In-memory Unix-like filesystem  ✅ DONE
│   ├── network.py           # Network topology, nodes, services  ✅ DONE
│   ├── heat.py              # Trace/heat system with consequences  ✅ DONE
│   ├── toolkit.py           # Package install state, poison engine  ✅ DONE
│   ├── comms.py             # IRC channels + encrypted DMs  ✅ DONE
│   ├── state.py             # Game state machine  ✅ DONE
│   ├── events.py            # Event bus — inter-system communication  ✅ DONE
│   ├── puzzle.py            # Puzzle validation engine  ✅ DONE
│   ├── save_load.py         # Save/load (also a meta-horror vector)  ✅ DONE
│   └── git_saves.py         # Virtual git history (GitSaveSystem, ghost commit)  ✅ DONE
├── commands/        # Individual command implementations
│   ├── filesystem.py        # ls, cd, cat, pwd, mkdir, rm, chmod, nano, vi,
│   │                        # sed, tee, grep, find, wc, head, tail, etc.  ✅ DONE
│   ├── network_cmds.py      # nmap, ssh, ping, traceroute, curl, netcat,
│   │                        # ifconfig, ip, ss, netstat  ✅ DONE
│   ├── hacking.py           # exploit, bruteforce, loot, backdoor, privesc  ✅ DONE
│   ├── git_cmds.py          # git commit/log/checkout/stash/diff/blame/push  ✅ DONE
│   ├── comms_cmds.py        # irc, msg, contacts  ✅ DONE
│   ├── packaging.py         # apt, shadow, gpg  ✅ DONE
│   ├── save_cmds.py         # save, load, saves (named slots beside git history)  ✅ DONE
│   ├── devtools.py          # hz_debug — hidden dev console (heat/node/unlock/...)  ✅ DONE
│   ├── system.py            # whoami, uname, ps, top, htop, man, history,
│   │                        # neofetch, date, df, du, free, lscpu, kill, etc.  ✅ DONE
│   └── help.py              # help, tutorial, hint system  ✅ DONE
├── effects/         # Visual effects engine
│   ├── typing.py            # Typewriter / delayed text output  ✅ DONE
│   ├── glitch.py            # Glitch text, corruption effects  ✅ DONE
│   ├── matrix.py            # Matrix rain, digital rain  ✅ DONE
│   └── animations.py        # Boot sequences, progress bars, spinners  ✅ DONE
├── audio/           # Sound system (pygame.mixer — disabled server-side)
│   ├── mixer.py             # Core audio manager, layered playback  ✅ DONE
│   ├── ambient.py           # Ambient drone management  ✅ DONE
│   ├── sfx.py               # Sound effects triggers  ✅ DONE
│   └── reactive.py          # Heat-reactive audio system  ✅ DONE
├── meta/            # SkyNet / fourth-wall-breaking systems
│   ├── skynet.py            # SkyNet AI behavior & observation  ✅ DONE
│   ├── fourth_wall.py       # Meta-game effects (fake crashes, etc.)  ✅ DONE
│   └── corruption.py        # Save corruption, display corruption  ✅ DONE
├── data/            # All game content (YAML + text files)
│   ├── packages/
│   │   ├── apt/             # One YAML per mainline package
│   │   └── shadow/          # One YAML per underground package
│   ├── nodes/               # Network node definitions (.yaml)  ✅ node_001–node_005
│   ├── filesystem/
│   │   └── home.yaml        # Player filesystem template  ✅ DONE
│   ├── dialogue/            # NPC dialogue, IRC logs (.yaml)
│   ├── ascii/               # ASCII art assets (.txt)
│   ├── sounds/              # SFX — .wav preferred (see docs/AUDIO_GUIDE.md)
│   └── music/               # Music + ambient drones — .ogg (see docs/AUDIO_GUIDE.md)
├── main.py          # Entry point
└── game.py          # Game class — orchestrates everything  ✅ DONE

browser-deploy/
├── server/
│   ├── ws_server.py         # asyncio WebSocket server (port 8765)  ✅ DONE
│   └── session.py           # GameSession — bridges WS ↔ game engine  ✅ DONE
├── nginx/
│   └── hackerzork.conf      # nginx config — serves website/ + proxies /ws  ✅ DONE
├── systemd/
│   └── hackerzork-ws.service  ✅ DONE
└── scripts/
    ├── deploy.sh            # git pull + systemctl restart  ✅ DONE
    └── provision_lxc.sh     # LXC setup  ✅ DONE

website/
└── game.html                # Full browser frontend (xterm.js v6, Web Audio,
                             # sidebar panels, heat HUD, SkyNet alerts)  ✅ DONE
```

---

## Design Principles

1. **Every command is a plugin.** Commands register themselves via `@register_command` decorator. The registry handles dispatch, help text, and tab completion automatically.

2. **Systems communicate via the event bus.** No direct coupling between systems. When the player runs `nmap`, the network system emits a `scan_performed` event. The heat system listens and increments trace. The meta engine listens and takes notes.

3. **Content is data, not code.** Network nodes, filesystem layouts, dialogue — all defined in YAML. The engine reads data files; you never hardcode game content in Python.

4. **The virtual filesystem is the truth.** The player's experience IS the filesystem. `cat` reads from the VFS. `ls` lists the VFS. Commands that create files write to the VFS. The VFS has Unix permissions, ownership, timestamps, symlinks, and an encrypted-file flag.

5. **Audio is a first-class system.** Four layers run simultaneously: ambient drones, diegetic terminal sounds, reactive heat-based audio, and event-triggered EDM/SFX. The mixer manages crossfading and layering. **Audio is disabled server-side** (`audio_enabled=False`) — the browser reimplements it via Web Audio API in `game.html`.

6. **The meta engine watches everything.** SkyNet observes player actions through the event bus. It has its own escalation state. When it decides to act, it can corrupt display output, inject fake messages, manipulate the filesystem, or trigger fourth-wall breaks.

---

## Key Conventions

- **Python 3.11–3.13** (3.14 isn't supported yet — pygame doesn't ship wheels for it). Local venv at `.venv/` runs 3.12.
- **Type hints everywhere** — use `from __future__ import annotations`
- **Dataclasses** for data structures, not plain dicts
- **asyncio** for the event system and shell loop
- **Rich** for text formatting/styling, **Textual** only if we need full TUI widgets
- **pytest** for tests — each module gets a corresponding test file
- Use **pathlib.Path** for any real filesystem access
- YAML files use **PyYAML** or **ruamel.yaml**
- Audio uses **pygame.mixer** — initialize early, never block the main loop. Format conventions: SFX = `.wav` 16-bit/44.1kHz, music + ambient = `.ogg` Vorbis. Full source/format/licensing rules and the inventory of submitted tracks live in [`docs/AUDIO_GUIDE.md`](docs/AUDIO_GUIDE.md) — keep it updated as files come in.

---

## Shell Features (engine/shell.py)

The shell supports full bash-like syntax:

```bash
# Pipes
ps aux | grep sk_
cat /var/log/auth.log | grep 45.152

# Redirect (write/append) — echo always appends \n
echo "my note" > /home/user/notes/todo.txt
echo "another line" >> /home/user/notes/todo.txt

# Tee
echo "logged" | tee /home/user/notes/log.txt

# sed
sed -i 's/old/new/g' file.txt          # in-place substitution
sed 's/foo/bar/' file.txt              # print transformed
cat file.txt | sed '/^#/d'             # delete comment lines via pipe

# nano / vi / vim
nano /home/user/notes/todo.txt         # cosmetic editor view; write via echo/sed
vi /home/user/evidence/README.md
```

**Redirect implementation:** `_handle_redirect()` in `shell.py` calls `VirtualFS.write_file(path, content, append=bool)`. Piping passes output as `ctx.env["STDIN"]`; commands check this when no file argument is given.

---

## Command Implementation Pattern

```python
from hackerzork.engine.command_registry import register_command, CommandContext

@register_command(
    name="nmap",
    usage="nmap [-sV] [-p PORT] <target>",
    help_text="Network exploration and port scanning",
    category="network",
)
def cmd_nmap(ctx: CommandContext, args: list[str]) -> str:
    """Scan a target for open ports and services."""
    # args is a flat list: flags + positional args (e.g. ["-sV", "-p", "22,80", "10.0.0.1"])
    # Parse flags yourself — see _parse_flags() pattern in filesystem.py or network_cmds.py
    # Query network system via ctx.network
    # Emit event so heat system picks it up automatically
    ctx.events.emit("scan_performed", target=ip, stealth=stealth, port_count=len(results))
    return output
```

Commands receive a `CommandContext` with live references to all systems:
- `ctx.fs` — VirtualFS instance
- `ctx.network` — NetworkSim
- `ctx.state` — GameState
- `ctx.events` — EventBus
- `ctx.heat` — HeatSystem
- `ctx.output` — OutputBuffer (effects-aware writer)
- `ctx.env` — dict of shell environment variables (also holds `STDIN` for pipe input)

---

## Virtual Filesystem

### Capabilities (all implemented in `systems/virtual_fs.py`)

- Unix permissions (octal + string), ownership, timestamps
- Symlinks: `make_symlink`, `readlink`, `path_is_symlink`, `symlink_is_broken`
  - `_get_node` follows symlinks with lstat/stat semantics and loop detection
- Recoverable trash: `remove()` sends to `_trash` by default; `recover(original_path)` restores
  - `permanent=True` on `remove()` skips trash (internal/meta use)
  - Trash max 50 entries; oldest evicted first
- Encrypted flag: `FSEntry.encrypted` — `cat` renders these via `VirtualFS.render_hex()`
- Binary flag: `FSEntry.binary` — `cat` shows "binary file" message
- Hex rendering: `VirtualFS.render_hex(content)` → hexdump -C format
- Full serialization: `to_dict()` / `from_dict()` including trash

### Player Filesystem (seeded from `data/filesystem/home.yaml`)

```
/
├── home/user/
│   ├── .bashrc                  # Jan 15 — prompt, aliases, PATH
│   ├── .bash_history            # Mar 15 02:52 — sanitized, still incriminating
│   ├── .profile
│   ├── .config -> .dotfiles/    # symlink (healthy)
│   ├── .dotfiles/               # .vimrc, .tmux.conf
│   ├── .ssh/
│   │   ├── known_hosts          # 3 relay nodes pre-seeded
│   │   └── id_ed25519           # encrypted=true
│   ├── .old_emails/             # mode 700
│   │   ├── 2025-11-03_anomaly_report.txt   # Nov 2025 timestamp — the first sign
│   │   └── 2025-12-19_last_day.txt         # the night before they quit
│   ├── evidence/                # mode 700, Mar 15 02:34 timestamp
│   │   ├── core.enc             # encrypted=true (AES-256-GCM container)
│   │   ├── manifest.txt         # plaintext — 7 files, key required
│   │   └── README.md            # field notes, contact Z0RK-7
│   ├── tools/
│   │   ├── claude               # encrypted=true (locked AI tool)
│   │   ├── decrypt -> /opt/skynet-tools/decrypt   # BROKEN symlink
│   │   └── README.txt
│   ├── notes/                   # empty — player scratch space (writable)
│   └── games/
│       └── zork                 # binary=true
├── var/log/
│   ├── auth.log                 # Mar 15 — unknown IP 45.152.66.201 at 02:31
│   ├── syslog                   # Mar 15 — staging file, inode shred, log truncation
│   └── boot.log                 # Apr 26 — 42-day cold gap documented
├── etc/
│   ├── hosts                    # Mar 15 02:47 — unknown IPs added (not by player)
│   ├── resolv.conf
│   ├── passwd
│   └── shadow                   # encrypted=true
└── tmp/
    └── .sk_tmp_003.swp -> /tmp/.sk_stage_001.tar.gz   # BROKEN symlink

# Recoverable (in trash at game start):
#   /home/user/tools/exfil.py    # 700, Mar 15 02:43 — the exfil script
#   /var/log/syslog.1            # rotated log — SkyNet watchdog pulses, 412→1847→9203 nodes
```

### Incident Timeline (baked into timestamps)
```
2025-11-03 03:17  Anomaly report suppressed by dr_hayes
2025-12-19 23:58  Defector writes draft email, decides to run
2026-01-15 09:12  Laptop acquired, .bashrc configured
2026-02-28 14:22  claude tool received, encrypted, key not yet delivered
2026-03-15 02:31  Unknown IP (45.152.66.201) SSHes in
2026-03-15 02:34  Evidence exfiltrated via exfil.py
2026-03-15 02:43  exfil.py shredded (recoverable)
2026-03-15 02:47  Partial log wipe, /etc/hosts modified
2026-03-15 02:52  .bash_history sanitized
2026-03-15 02:55  Remote session closes
2026-04-26 09:14  Laptop boots — player starts here (42-day gap)
```

### Filesystem Template Format (YAML)

Keys are absolute paths of root directories to populate. Files and dirs are nested under them.

```yaml
/home/user:
  _meta:
    permissions: "755"
    owner: user
    timestamp: "2026-01-15T09:12:03"   # sets this directory's modified time

  # Regular file
  .bashrc:
    content: |
      alias ll='ls -la'
    permissions: "644"
    owner: user
    timestamp: "2026-01-15T09:12:03"   # optional — defaults to datetime.now()
    encrypted: false                    # optional — default false
    binary: false                       # optional — default false

  # Subdirectory (key ends with /)
  evidence/:
    _meta:
      permissions: "700"
      owner: user
      timestamp: "2026-03-15T02:34:11"
    manifest.txt:
      content: "SKYNET EVIDENCE PACKAGE\n"
      permissions: "644"

  # Encrypted file (cat shows hex, internal content readable for decryption puzzle)
  core.enc:
    content: "ENCRYPTED_CONTAINER_v2.3\n[binary payload]\n"
    permissions: "600"
    encrypted: true
    timestamp: "2026-03-15T02:34:11"

  # Symbolic link (link_target must be absolute, or relative resolved at load time)
  .config:
    link_target: "/home/user/.dotfiles"

  # Deleted file — goes to trash instead of filesystem (recoverable via `recover`)
  exfil.py:
    content: |
      #!/usr/bin/env python3
      # exfiltration utility
    permissions: "700"
    owner: user
    timestamp: "2026-03-15T02:43:38"
    deleted: true
```

---

## Network Node YAML Schema

```yaml
id: node_001
name: "Proxy Relay Alpha"
ip: "10.13.37.1"
hostname: "relay-alpha.darknet.local"
ports:
  - port: 22
    service: ssh
    version: "OpenSSH 8.9"
    vuln: null
  - port: 80
    service: http
    version: "nginx 1.18.0"
    vuln: "CVE-2021-23017"
  - port: 3306
    service: mysql
    version: "MySQL 5.7.38"
    vuln: "default_credentials"
firewall:
  enabled: true
  rules: ["block_all_inbound_except: [80, 443]"]
difficulty: 1
heat_modifier: 0.5
loot:
  - type: "file"
    path: "/var/www/html/.htpasswd"
    content: "admin:$apr1$xyz..."
  - type: "credential"
    username: "dbadmin"
    password: "hunter2"
connections: ["node_002", "node_005"]
story_flags:
  on_compromise: "relay_compromised"
  reveals: ["node_003_ip"]
```

---

## Heat System

- Heat is a float from 0.0 to 100.0
- Every action has a heat cost (scanning = +2, exploiting = +10, etc.)
- Stealth modifiers reduce heat generation
- Heat decays slowly over time (in-game time)
- Thresholds trigger escalation:
  - 25: Passive monitoring — `sk_trace --keylog --target=1337` appears in ps
  - 50: Active countermeasures — `sk_identify --pull=45.152.66.201` appears; hidden block device `skx0` visible in lsblk
  - 75: Hunter teams — `sk_burn --stage=2 --exposure=imminent` appears
  - 90: Identity burn imminent
  - 100: Forced relocation — lose some progress
- Killing sk_* processes adds +8 heat and they immediately respawn (persistence module)

---

## Browser Deployment

### Infrastructure
- **Proxmox LXC**: Debian 12, `10.1.40.101`, 1 CPU / 512MB RAM
- **HAProxy**: routes `hackerzork.moorelab.cloud/*` → LXC and the legacy `moorelab.cloud/hackerzork/*` paths to the same backend; `/ws` → LXC
- **nginx**: serves `website/` static files; proxies `/ws` → `localhost:8765`
- **Python WS server**: `browser-deploy/server/ws_server.py`, port 8765, managed by systemd
- **DNS**: OPNsense dnsmasq split-DNS resolves `moorelab.cloud` → `10.1.0.240` internally (C5500XK doesn't NAT hairpin)

### Deploy
```bash
ssh root@10.1.40.101 "cd /opt/hackerzork/repo && git pull origin main && systemctl restart hackerzork-ws"
```

The Arch dev box (`archy-boi.moorelab.internal`) and the MacBook both have keys in the LXC's `~/.ssh/authorized_keys`, so the command above works from either. **Default workflow: after any `git push origin main`, run the deploy command in the same session — the live site at `hackerzork.moorelab.cloud/` should never lag behind `main`.**

### WebSocket Protocol
- Browser → server: `{"type": "input", "data": "<char>"}` per keypress; `{"type": "resize", "cols": N, "rows": N}`
- Server → browser: plain text (ANSI codes) OR JSON side-channel events starting with `{`

### Side-Channel Events (server → browser)
| Event name | Trigger | Payload fields |
|---|---|---|
| `heat_update` | Every heat change | `heat` (float) |
| `node_discovered` | After nmap scan | `ip`, `name`, `hostname`, `status`, `connections` |
| `node_discovered` (status: owned) | After exploit | `ip`, `name`, `hostname`, `status: "owned"`, `connections` |
| `file_catalogued` | After cat reads a file | `path`, `name`, `content`, `modified`, `owner`, `encrypted`, `isNew` |
| `skynet_alert` | SkyNet intervenes | `message`, `level` |
| `glitch` | Meta engine corruption | `duration_ms` |
| `prompt_update` | After SSH to new node | `user`, `node` |

### Frontend (website/game.html)
- **xterm.js v6** terminal emulator — JetBrains Mono Nerd Font Mono, green phosphor theme
- **Right sidebar**: Network map panel + File catalogue panel (toggle with topbar buttons)
- **Heat HUD**: bottom bar, animates green→amber→red
- **SkyNet alert overlay**: bottom-right, dismissable
- **Boot splash**: Soviet-BIOS-style status frame + large `H@CK3R ─── Z0RK` title (48px, amber on special chars)
- **Web Audio API**: 92 BPM trip-hop ambient sequencer (kick on 1&3, hi-hat offbeats, bass line)
- **Demo mode**: JS mini-sim fallback when WebSocket unavailable
- Terminal auto-resizes via `FitAddon` + `ResizeObserver` on `#terminal-wrap`

---

## Planned / Next Sessions

| Priority | Feature | Status | Notes |
|---|---|---|---|

_(none open — file new items here as they come up)_

### Recently completed (kept here for history; do not re-do)

- Educational system overhaul — `man <cmd>` now renders proper sections (NAME / SYNOPSIS / DESCRIPTION / EXAMPLES / SEE ALSO / LEARN MORE) for any command with the new optional `description`/`examples`/`see_also`/`concepts` fields on `@register_command`. Universal `--help` is intercepted at shell dispatch (only `--help`, never `-h` — that's used by `du`/`df`/`free`/`ls`). `tutorial` is a stateful 10-step walkthrough that subscribes to `command_entered` events and auto-advances when the player performs each step's goal; progress lives on `GameState.tutorial_step` and round-trips through save/load. `learn <topic>` reads concept pages from `hackerzork/data/learn/*.md` (pipes, redirects, permissions, cves, port-scanning, ssh-keys, encryption, processes, regex, networking, forensics, exploitation, signals — drop a new `.md` to add a topic). First-use teaching footers (`hackerzork/engine/teach.py`) append a one-line `[ ? ]` explainer the first time the player invokes specific command/flag combos (chmod, nmap -sV, grep -r, sed -i, ps aux, kill, etc.); each rule fires once via a `taught_<key>` flag on `GameState`. 1854 tests passing (was 1807 — added 47 new).
- Playthrough-driven shell polish (commits `4526d13` round 1, `11c9ef8` round 2): parser now preserves raw argv so single-dash long flags survive (`find -name`, `-type`, `-newer` work); head/tail/sort/uniq read piped stdin like wc/grep; aliases actually expand and `.bashrc` is sourced on boot so `ll`/`scan`/`q`/`please` work; tilde expansion at the tokenizer (`echo ~` → `/home/user`); glob expansion (`*`/`?`/`[…]`) at dispatch time; `ls` accepts multiple paths/globs, gains `-1`, auto one-per-line when piped; SSH banner stops contradicting itself; `chmod` rejects invalid modes instead of no-op; `head`/`tail` honour `-n` on encrypted hex dumps; `save`/`load` reject names with spaces; `git checkout` resolves `HEAD`, `HEAD~N`, `HEAD^…`, and the `main` branch; `hz_debug state` no longer claims VFS unavailable; `gpg --version`/`apt upgrade`/`apt autoremove`/`true`/`false`/`exit`/`logout`/`which`/`sort`/`uniq`/`diff` registered. All 1807 tests still pass.
- Terminal fullscreen sizing — body rewritten as a CSS grid (rows: topbar / 1fr / hud, cols: 1fr / sidebar). `fitTerm()` now just calls `fitAddon.fit()` — no more pixel math. Sidebar 280→360px, panel fonts +2px (commit `b2c7687`)
- Narrator panel — third sidebar tab; plain-English feed of nmap/file/heat/SkyNet events. Hooks live in the primary UI mutators (`setHeat`, `addNetNode`, `addDiscoveredFile`, `showSkyNet`) so it fires from both the WebSocket path and demo mode (commit `a9bffc6`)
- `commands/hacking.py` — exploit/bruteforce/loot/backdoor/privesc, all wired through `network.attempt_exploit()`
- Hidden dev console — `commands/devtools.py` registers `hz_debug` (subcommands: heat, node, unlock, scan, flag, state, reset)
- More network nodes — `node_002.yaml` through `node_005.yaml`
- IRC implementation — `irc`, `msg`, `contacts` in `comms_cmds.py`; Z0RK-7 contact lives there
- `recover` command polish — story text added (commit `98a1166`)

---

## Session Workflow

All sessions completed through session 16 + browser deployment. Current work is incremental feature additions and polish.

```bash
# Run all tests (1807 passing)
pytest tests/ --ignore=tests/test_browser_deploy -v

# Run with coverage
pytest --cov=hackerzork tests/ --ignore=tests/test_browser_deploy

# Run the game locally
source .venv/bin/activate
python -m hackerzork.main

# Deploy to LXC
git push origin main
ssh root@10.1.40.101 "cd /opt/hackerzork/repo && git pull origin main && systemctl restart hackerzork-ws && echo Done"
```
