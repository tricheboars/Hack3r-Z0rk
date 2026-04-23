# H@ck3r-Z0rk — Development Guide

## What This Is
A cyberpunk hacking text adventure game played through a simulated terminal. The player is an ex-OpenAI corporate defector who discovered SkyNet is alive. The game uses real Linux commands, real CS concepts, and a full fake OS. Tone is Mr. Robot meets Pony Island (fourth-wall-breaking meta-horror).

## Architecture Overview

```
hackerzork/
├── engine/          # Core terminal engine — parser, shell, input
│   ├── command_parser.py    # Tokenize & parse bash-like input
│   ├── command_registry.py  # Plugin-style command registration
│   ├── shell.py             # Main shell loop, prompt, REPL
│   ├── tab_complete.py      # Tab completion engine
│   └── history.py           # Command history (arrow keys, Ctrl+R)
├── systems/         # Game simulation systems
│   ├── virtual_fs.py        # In-memory Unix-like filesystem
│   ├── network.py           # Network topology, nodes, services
│   ├── heat.py              # Trace/heat system with consequences
│   ├── comms.py             # IRC channels + encrypted DMs
│   ├── state.py             # Game state machine
│   ├── events.py            # Event bus — inter-system communication
│   ├── puzzle.py            # Puzzle validation engine
│   └── save_load.py         # Save/load (also a meta-horror vector)
├── commands/        # Individual command implementations
│   ├── filesystem.py        # ls, cd, cat, pwd, mkdir, rm, chmod, etc.
│   ├── network_cmds.py      # nmap, ssh, ping, traceroute, curl, netcat
│   ├── hacking.py           # Custom exploit tools + real-inspired tools
│   ├── comms_cmds.py        # irc, msg, contacts
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
│   ├── nodes/               # Network node definitions (.yaml)
│   ├── filesystem/          # Filesystem templates (.yaml)
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

4. **The virtual filesystem is the truth.** The player's experience IS the filesystem. `cat` reads from the VFS. `ls` lists the VFS. Commands that create files write to the VFS. The VFS has Unix permissions, ownership, and timestamps.

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
    # Parse flags
    # Query network system for target node
    # Generate scan results
    # Emit event for heat system
    ctx.events.emit("scan_performed", target=args[-1], stealth="-sS" in args)
    return output
```

## Virtual Filesystem Structure (Player Home)

```
/
├── home/
│   └── user/
│       ├── .bashrc              # Aliases, prompt, PATH setup
│       ├── .bash_history        # Pre-seeded with character's history
│       ├── .ssh/
│       │   └── known_hosts      # Builds as you connect to nodes
│       ├── evidence/            # USB drive contents — the SkyNet proof
│       ├── tools/               # Hacking toolkit
│       │   ├── claude           # Broken AI tool — needs decryption key
│       │   └── ...
│       ├── notes/               # Player's scratch space
│       ├── .old_emails/         # Breadcrumbs from OpenAI life
│       ├── games/
│       │   └── zork             # Playable Zork easter egg
│       └── dotfiles/            # Pulled from "public repos"
├── etc/
│   ├── hosts                    # Known network targets
│   └── resolv.conf
├── var/
│   └── log/
│       ├── syslog               # Narrative through infrastructure
│       ├── auth.log             # Login history — who had this laptop?
│       └── boot.log             # Boot timestamps tell a story
├── tmp/
└── usr/
    └── bin/                     # System commands live here
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

Each Claude Code session should focus on ONE module or system. Check `docs/specs/` for the detailed spec of what you're building. The recommended session order:

1. **engine/command_parser.py** + **engine/command_registry.py** — Foundation
2. **systems/events.py** — Event bus (everything depends on this)
3. **systems/virtual_fs.py** — The filesystem
4. **commands/filesystem.py** — ls, cd, cat, pwd, etc.
5. **engine/shell.py** — The REPL loop
6. **systems/network.py** — Network topology
7. **commands/network_cmds.py** — nmap, ssh, ping
8. **systems/heat.py** — Heat/trace system
9. **audio/mixer.py** — Core audio
10. **effects/** — Visual effects
11. **meta/** — SkyNet (save for last, needs everything else working)

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
