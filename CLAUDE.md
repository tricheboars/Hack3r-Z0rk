# H@ck3r-Z0rk — Development Guide

## What This Is
A cyberpunk hacking text adventure game played through a simulated terminal. The player is an ex-OpenAI corporate defector who discovered SkyNet is alive. The game uses real Linux commands, real CS concepts, and a full fake OS. Tone is Mr. Robot meets Pony Island (fourth-wall-breaking meta-horror).

## Architecture Overview

```
hackerzork/
├── engine/          # Core terminal engine — parser, shell, input
│   ├── command_parser.py    # Tokenize & parse bash-like input  ✅ DONE
│   ├── command_registry.py  # Plugin-style command registration  ✅ DONE
│   ├── shell.py             # Main shell loop, prompt, REPL
│   ├── tab_complete.py      # Tab completion engine
│   └── history.py           # Command history (arrow keys, Ctrl+R)
├── systems/         # Game simulation systems
│   ├── virtual_fs.py        # In-memory Unix-like filesystem  ✅ DONE
│   ├── network.py           # Network topology, nodes, services
│   ├── heat.py              # Trace/heat system with consequences
│   ├── toolkit.py           # Package install state, poison engine
│   ├── comms.py             # IRC channels + encrypted DMs
│   ├── state.py             # Game state machine
│   ├── events.py            # Event bus — inter-system communication  ✅ DONE
│   ├── puzzle.py            # Puzzle validation engine
│   └── save_load.py         # Save/load (also a meta-horror vector)
├── commands/        # Individual command implementations
│   ├── filesystem.py        # ls, cd, cat, pwd, mkdir, rm, chmod, etc.
│   ├── network_cmds.py      # nmap, ssh, ping, traceroute, curl, netcat
│   ├── hacking.py           # Custom exploit tools + real-inspired tools
│   ├── comms_cmds.py        # irc, msg, contacts
│   ├── packaging.py         # apt, shadow, gpg
│   ├── system.py            # whoami, uname, ps, top, man, history
│   └── help.py              # help, tutorial, hint system
├── effects/         # Visual effects engine
│   ├── typing.py            # Typewriter / delayed text output
│   ├── glitch.py            # Glitch text, corruption effects
│   ├── matrix.py            # Matrix rain, digital rain
│   └── animations.py        # Boot sequences, progress bars, spinners
├── audio/           # Sound system (pygame.mixer)
│   ├── mixer.py             # Core audio manager, layered playback
│   ├── ambient.py           # Ambient drone management
│   ├── sfx.py               # Sound effects triggers
│   └── reactive.py          # Heat-reactive audio system
├── meta/            # SkyNet / fourth-wall-breaking systems
│   ├── skynet.py            # SkyNet AI behavior & observation
│   ├── fourth_wall.py       # Meta-game effects (fake crashes, etc.)
│   └── corruption.py        # Save corruption, display corruption
├── data/            # All game content (YAML + text files)
│   ├── packages/
│   │   ├── apt/             # One YAML per mainline package
│   │   └── shadow/          # One YAML per underground package
│   ├── nodes/               # Network node definitions (.yaml)
│   ├── filesystem/
│   │   └── home.yaml        # Player filesystem template  ✅ DONE
│   ├── dialogue/            # NPC dialogue, IRC logs (.yaml)
│   ├── ascii/               # ASCII art assets (.txt)
│   ├── sounds/              # SFX — .wav preferred (see docs/AUDIO_GUIDE.md)
│   └── music/               # Music + ambient drones — .ogg (see docs/AUDIO_GUIDE.md)
├── main.py          # Entry point
└── game.py          # Game class — orchestrates everything
```

## Design Principles

1. **Every command is a plugin.** Commands register themselves via `@register_command` decorator. The registry handles dispatch, help text, and tab completion automatically.

2. **Systems communicate via the event bus.** No direct coupling between systems. When the player runs `nmap`, the network system emits a `scan_performed` event. The heat system listens and increments trace. The meta engine listens and takes notes.

3. **Content is data, not code.** Network nodes, filesystem layouts, dialogue — all defined in YAML. The engine reads data files; you never hardcode game content in Python.

4. **The virtual filesystem is the truth.** The player's experience IS the filesystem. `cat` reads from the VFS. `ls` lists the VFS. Commands that create files write to the VFS. The VFS has Unix permissions, ownership, timestamps, symlinks, and an encrypted-file flag.

5. **Audio is a first-class system.** Four layers run simultaneously: ambient drones, diegetic terminal sounds, reactive heat-based audio, and event-triggered EDM/SFX. The mixer manages crossfading and layering.

6. **The meta engine watches everything.** SkyNet observes player actions through the event bus. It has its own escalation state. When it decides to act, it can corrupt display output, inject fake messages, manipulate the filesystem, or trigger fourth-wall breaks.

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
    # Parse flags from ctx.parsed (ParsedCommand)
    # Query network system for target node
    # Generate scan results
    # Emit event for heat system
    ctx.events.emit("scan_performed", target=args[-1], stealth="-sS" in args)
    return output
```

Commands receive a `CommandContext` with live references to all systems:
- `ctx.fs` — VirtualFS instance
- `ctx.network` — NetworkSim
- `ctx.state` — GameState
- `ctx.events` — EventBus
- `ctx.heat` — HeatSystem
- `ctx.output` — OutputBuffer (effects-aware writer)
- `ctx.env` — dict of shell environment variables

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
│   ├── notes/                   # empty — player scratch space
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

## Heat System

- Heat is a float from 0.0 to 100.0
- Every action has a heat cost (scanning = +2, exploiting = +10, etc.)
- Stealth modifiers reduce heat generation
- Heat decays slowly over time (in-game time)
- Thresholds trigger escalation:
  - 25: Passive monitoring detected
  - 50: Active countermeasures (ICE)
  - 75: Hunter teams dispatched
  - 90: Identity burn imminent
  - 100: Forced relocation — lose some progress

## Session Workflow for Claude Code

Each Claude Code session should focus on ONE module or system. Check `docs/specs/` for the detailed spec of what you're building.

| # | Module(s) | Spec | Status |
|---|-----------|------|--------|
| 1 | `engine/command_parser.py` + `engine/command_registry.py` | `01_command_parser.md` | ✅ Done |
| 2 | `systems/events.py` | `02_event_bus.md` | ✅ Done |
| 3 | `systems/virtual_fs.py` | `03_virtual_fs.md` | ✅ Done |
| 4 | `commands/filesystem.py` | `04_filesystem_commands.md` | ✅ Done |
| 5 | `engine/shell.py` + `engine/tab_complete.py` + `engine/history.py` | `05_shell.md` | ← **Next** |
| 6 | `systems/network.py` | `06_network.md` (was 04) | |
| 7 | `commands/network_cmds.py` | `07_network_cmds.md` | |
| 8 | `systems/heat.py` | `08_heat_system.md` (was 05) | |
| 9 | `systems/toolkit.py` + `commands/packaging.py` | `09_toolkit_unlocks.md` | |
| 10 | `audio/mixer.py` + `audio/ambient.py` + `audio/sfx.py` | `10_audio.md` (was 06) | |
| 11 | `effects/` | `11_effects.md` (was 07) | |
| 12 | `meta/` (skynet, fourth_wall, corruption) | `12_meta_engine.md` (was 08) | |

After each session, run `pytest` to make sure nothing is broken.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/test_engine/ -v
pytest tests/test_systems/ -v

# Run with coverage
pytest --cov=hackerzork tests/
```

## Running the Game

```bash
# From project root
python -m hackerzork.main

# Or after pip install
hackerzork
```
