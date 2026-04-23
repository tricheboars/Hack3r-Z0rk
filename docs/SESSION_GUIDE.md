# H@ck3r-Z0rk — Claude Code Session Guide

## How This Works

Each session builds one piece of the game. Copy the prompt below into Claude Code and let it rip. Sessions are ordered — do them in sequence since later modules depend on earlier ones.

After each session, run `pytest tests/ -v` to make sure everything passes before moving on.

---

## Session 1: Command Parser & Registry

> Build the command parser and command registry. Read `CLAUDE.md` for architecture context and `docs/specs/01_command_parser.md` for the detailed spec. Implement `hackerzork/engine/command_parser.py` and `hackerzork/engine/command_registry.py`. Write tests in `tests/test_engine/test_command_parser.py`. The parser should handle bash-like input: flags, quoted strings, pipes, redirection, env var expansion, and semicolons. The registry uses a `@register_command` decorator pattern. Run pytest when done.

---

## Session 2: Event Bus

> Build the event bus system. Read `CLAUDE.md` and `docs/specs/02_event_bus.md`. Implement `hackerzork/systems/events.py` with the `EventBus` and `Event` classes. It needs `on`, `off`, `emit`, `emit_async`, and `history` methods. Handlers should never crash the bus. Write tests in `tests/test_systems/test_events.py`. Run pytest when done.

---

## Session 3: Virtual Filesystem

> Build the virtual filesystem. Read `CLAUDE.md` and `docs/specs/03_virtual_fs.md`. Implement `hackerzork/systems/virtual_fs.py` — a full in-memory Unix-like filesystem with path resolution, file CRUD, directory operations, permissions (octal and rwx string), ownership, and timestamps. It should load initial state from YAML templates. Write tests in `tests/test_systems/test_virtual_fs.py`. Also create the initial home directory template at `hackerzork/data/filesystem/home.yaml` based on the spec. Run pytest when done.

---

## Session 4: Filesystem Commands

> Build the filesystem commands. Read `CLAUDE.md` and `docs/specs/01_command_parser.md` for the CommandContext pattern. Implement `hackerzork/commands/filesystem.py` with these commands: `ls`, `cd`, `cat`, `pwd`, `mkdir`, `rm`, `cp`, `mv`, `chmod`, `touch`, `find`, `grep`. Each command uses the `@register_command` decorator and operates on the VirtualFS via `ctx.fs`. Make `ls -la` output look like real Linux. Write tests in `tests/test_commands/test_filesystem.py`. Run pytest when done.

---

## Session 5: Shell REPL

> Build the main shell loop. Read `CLAUDE.md` and the command parser/registry code in `hackerzork/engine/`. Implement `hackerzork/engine/shell.py` — the REPL that reads input, parses it, dispatches to commands, and prints output. Also implement `hackerzork/engine/history.py` for command history and `hackerzork/engine/tab_complete.py` for tab completion. The shell should display a customizable prompt (from .bashrc), support arrow keys for history, and handle Ctrl+C gracefully. Use the Rich library for styled output. Wire it into `hackerzork/game.py` so `python -m hackerzork.main` boots into the shell. Run pytest when done.

---

## Session 6: Network Simulation

> Build the network simulation. Read `CLAUDE.md` and `docs/specs/04_network.md`. Implement `hackerzork/systems/network.py` with `NetworkSim`, `NetworkNode`, `Port`, and `ExploitResult` classes. Support node loading from YAML, port scanning, service enumeration, firewall checking, exploit attempts, node hardening on failure, and connection discovery on compromise. Create a sample network node YAML at `hackerzork/data/nodes/node_001.yaml`. Write tests in `tests/test_systems/test_network.py`. Run pytest when done.

---

## Session 7: Network Commands

> Build the network commands. Read `CLAUDE.md` and look at how `hackerzork/commands/filesystem.py` registers commands. Implement `hackerzork/commands/network_cmds.py` with: `nmap` (port/service scanning), `ssh` (connect to remote nodes), `ping`, `traceroute`, `curl`, and `netcat`. Each command should emit events via `ctx.events` so the heat system can track them. Make output look like the real tools. Write tests in `tests/test_commands/test_network.py`. Run pytest when done.

---

## Session 8: Heat System

> Build the heat/trace system. Read `CLAUDE.md` and `docs/specs/05_heat_system.md`. Implement `hackerzork/systems/heat.py` with the `HeatSystem` class. It listens to events from the event bus and accumulates heat. Implement thresholds (safe, monitored, active_response, hunted, critical, burned), decay over time, stealth modifiers, and the identity burn mechanic at 100. Emit `heat_changed` and `heat_threshold` events. Write tests in `tests/test_systems/test_heat.py`. Run pytest when done.

---

## Session 9: System Commands

> Build the system/utility commands. Read `CLAUDE.md` and look at existing command implementations. Implement `hackerzork/commands/system.py` with: `whoami`, `uname`, `ps`, `top`, `man`, `history`, `clear`, `exit`, `env`, `export`, `alias`, `echo`, `date`. These give the fake OS its personality. `man` should show help for any registered command. `ps` and `top` should show fake processes. `uname` returns the fake OS info. Write tests in `tests/test_commands/test_system.py`. Run pytest when done.

---

## Session 10: Audio System

> Build the audio system. Read `CLAUDE.md` and `docs/specs/06_audio.md`. Implement `hackerzork/audio/mixer.py` (4-layer audio manager using pygame.mixer), `hackerzork/audio/ambient.py` (drone management), `hackerzork/audio/sfx.py` (sound effect triggers), and `hackerzork/audio/reactive.py` (heat-reactive audio mixing). The system must gracefully degrade when audio is disabled or sound files are missing. Wire the reactive system to listen for `heat_changed` events. Write tests — mock pygame.mixer so tests run without audio hardware. Run pytest when done.

---

## Session 11: Visual Effects

> Build the visual effects system. Read `CLAUDE.md` and `docs/specs/07_effects.md`. Implement all four modules: `hackerzork/effects/typing.py` (typewriter, dramatic pause, redacted text), `hackerzork/effects/glitch.py` (glitch text, zalgo, scramble reveal, static, corruption), `hackerzork/effects/matrix.py` (matrix rain, data stream, decrypt animation), `hackerzork/effects/animations.py` (boot sequence, progress bars, spinners, connection animation, breach animation). Use Rich for styled output. All effects should be async and respect a global speed multiplier. Write tests. Run pytest when done.

---

## Session 12: Comms System

> Build the IRC and DM communication system. Read `CLAUDE.md`. Implement `hackerzork/systems/comms.py` for managing IRC channels and encrypted DMs, and `hackerzork/commands/comms_cmds.py` with commands: `irc` (join/leave/list channels, send messages), `msg` (send encrypted DMs), `contacts` (list known contacts). Messages from NPCs arrive via the event bus based on game state triggers. The comms system should support asynchronous message delivery — NPCs message you at scripted moments. Write tests. Run pytest when done.

---

## Session 13: Save/Load & Game State

> Build the save/load and game state systems. Read `CLAUDE.md`. Implement `hackerzork/systems/state.py` (game state machine — tracks flags, story progress, unlocks) and `hackerzork/systems/save_load.py` (serialize/deserialize all game state to JSON). The save system must capture: filesystem state, network state, heat level, discovered/compromised nodes, story flags, command history, and comms history. Also make this a vector for the meta engine — the save display can be "corrupted" by SkyNet. Write tests. Run pytest when done.

---

## Session 14: Meta Engine (SkyNet)

> Build the meta engine — SkyNet's brain. Read `CLAUDE.md` and `docs/specs/08_meta_engine.md`. Implement `hackerzork/meta/skynet.py` (observation and escalation AI), `hackerzork/meta/fourth_wall.py` (fourth-wall-breaking effects), and `hackerzork/meta/corruption.py` (save/display corruption). SkyNet listens to ALL events, builds awareness, and has 6 escalation tiers from dormant to full assault. Fourth-wall effects include fake crashes, terminal title changes, phantom text, and command echo corruption. Never actually corrupt real data. Write tests. Run pytest when done.

---

## Session 15: Integration & Boot Sequence

> Wire everything together and build the cold boot experience. Update `hackerzork/game.py` to initialize all systems in the correct dependency order, wire up event listeners, and load the initial game state. Implement the full boot sequence animation (POST, memory check, services starting, prompt appearing). Make sure `python -m hackerzork.main` boots into a fully playable shell with the home filesystem, working commands, and audio. Create the help command in `hackerzork/commands/help.py`. Run the full test suite. Run pytest when done.

---

## Tips

- If Claude Code asks clarifying questions, point it to the relevant spec file in `docs/specs/`
- If a session gets too big, split it — e.g., do filesystem commands in two sessions
- Run `pytest tests/ -v` between sessions to catch regressions
- If something breaks, tell Claude Code: "Run pytest, find the failures, and fix them"
