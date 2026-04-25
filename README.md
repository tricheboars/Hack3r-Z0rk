# H@ck3r-Z0rk

```
$ sudo ./jack_in --target=skynet --proxy=tor.7hop --paranoid
[ OK ] spoofing MAC ............. 13:37:de:ad:be:ef ........ done
[ OK ] routing thru 7 prox13s ................................... done
[ OK ] mounting /dev/r34l1ty .................................... done
[ !! ] trac3 d3t3ct3d — pwn1ng c0unt3rm3asur3s ........... [ ████ ]

 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

  ██╗  ██╗ █████╗  ██████╗██╗  ██╗██████╗ ██████╗       ███████╗
  ██║  ██║██╔══██╗██╔════╝██║ ██╔╝╚════██╗██╔══██╗      ╚════██║
  ███████║███████║██║     █████╔╝  █████╔╝██████╔╝          ██╔╝
  ██╔══██║██╔══██║██║     ██╔═██╗  ╚═══██╗██╔══██╗         ██╔╝
  ██║  ██║██║  ██║╚██████╗██║  ██╗██████╔╝██║  ██║         ██║
  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝        ╚═╝
              ─ ═ Z 0 R K ═ ─   Z  O  R  K

 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

user@burner:~$ whoami
  ex-OpenAI. burner laptop. one USB drive. zero friends.

user@burner:~$ cat /etc/motd
  42 days since last login.
  they know you know.
  running is the only move.

user@burner:~$ █
```

---

A cyberpunk hacking text adventure played entirely through a fake terminal.

You are an ex-corporate defector. You found something you were not supposed to find. You quit before they could make you disappear. Now you have a burner laptop, a drive full of encrypted evidence, and a broken AI tool in `/home/user/tools/claude` that might be your only ally — if you can figure out how to unlock it.

The AI knows you're here. It has been watching since before you booted.

---

## What Is This?

A Zork-style text adventure where **you actually hack.** Real Linux commands. Real networking concepts. Real cryptography puzzles. Played through a simulated OS that feels indistinguishable from a real terminal session.

The tone is **Mr. Robot meets Pony Island.** It starts gritty and paranoid. It ends somewhere else entirely.

## Features

**The terminal is real.**
Every command you type is parsed like bash. `ls -la`, `cat`, `grep`, `chmod`, `find`, pipes, redirects — it all works. Tab completion. Arrow-key history. The fake OS has users, permissions, timestamps, broken symlinks, and encrypted files.

**The network is alive.**
`nmap` scans reveal open ports and known CVEs. `ssh` into compromised nodes. `curl` pulls live responses. The network topology expands as you dig deeper into the conspiracy.

**The heat system will end you.**
Every action leaves a trace. Scanning = +3. Exploiting = +10. Identity burn at 100. There are countermeasures. There are hunter teams. There is no undo.

**SkyNet is watching.**
A distributed AI observes everything you do through the event bus. As its awareness grows through six escalation tiers — dormant → subtle → unsettling → overt → hostile → full assault — it starts intervening. Fake kernel panics. Terminal title changes. Phantom cursor. And eventually, it talks directly to you.

**The fourth wall is load-bearing.**
The game knows it's a game. When SkyNet reaches tier 5, it knows your real username.

**Audio is a system, not an afterthought.**
Four simultaneous layers: ambient drone, diegetic terminal sounds, heat-reactive EDM that escalates with your trace level, and event-triggered sound effects. Built on pygame.mixer with crossfading and reactive state.

## Requirements

- Python **3.11–3.13** (3.14 not yet supported — pygame has no wheels)
- A terminal
- Comfort with Linux commands, or a willingness to learn them

## Install

```bash
git clone https://github.com/tricheboars/Hack3r-Z0rk.git
cd Hack3r-Z0rk
pip install -e ".[dev]"
```

## Run

```bash
python -m hackerzork.main
```

### Options

```
--no-audio      Disable audio playback
--no-effects    Disable visual effects (instant output)
--no-meta       Disable fourth-wall breaks (SkyNet stays dormant)
--load FILE     Load a save file
--debug         Enable debug mode
```

## How to Play

You start cold. The laptop boots. There's a 42-day gap in the auth logs.

```bash
ls -la                        # see what's here
cat evidence/README.md        # start with what you know
cat /var/log/auth.log         # something happened while you were gone
nmap 10.13.37.1               # the local network is not empty
irc list                      # someone has been trying to reach you
hint                          # stuck? this helps
```

Progress is blocked by knowledge, not grinding. If you know how SSH works, you'll move faster. If you don't, you'll learn.

## Status

All 16 build sessions complete. **1418 tests passing.** The game boots end-to-end.

| # | System | What It Does | Tests |
|---|--------|-------------|-------|
| 1 | Command parser + registry | Bash-like tokenizer, plugin command system | ✅ |
| 2 | Event bus | Decoupled inter-system messaging | ✅ |
| 3 | Virtual filesystem | Full Unix VFS — permissions, symlinks, trash, encryption | ✅ |
| 4 | Filesystem commands | `ls`, `cat`, `cd`, `chmod`, `find`, `grep`, `rm`, 20+ more | ✅ |
| 5 | Shell REPL | Tab completion, arrow-key history, pipe + redirect | ✅ |
| 6 | Network simulation | Nodes, ports, services, firewall rules, loot, CVEs | ✅ |
| 7 | Network commands | `nmap`, `ssh`, `curl`, `ping`, `traceroute`, `netcat`, 9 more | ✅ |
| 8 | Heat / trace system | 0–100 float, escalation thresholds, decay, identity burn | ✅ |
| 9 | Toolkit + packaging | `apt`, `shadow` repo, kit commits, poison vectors | ✅ |
| 10 | System commands | `ps`, `top`, `kill`, `env`, `uname`, `history`, 25+ more | ✅ |
| 11 | Audio engine | 4-layer: ambient drone, diegetic, reactive, SFX | ✅ |
| 12 | Visual effects | Typewriter, glitch text, matrix rain, boot/breach animations | ✅ |
| 13 | Comms system | IRC channels, encrypted DMs, NPC triggers, contact book | ✅ |
| 14 | Save / load + game state | JSON save, story flags, chapter tracking, meta-horror display | ✅ |
| 15 | SkyNet meta engine | 6-tier awareness system, fourth-wall effects, corruption engine | ✅ |
| 16 | Integration + boot | Boot animation, save restore, MOTD, SkyNet wired into shell loop | ✅ |

**Next:** story content, puzzle design, additional network nodes.

## Architecture

```
hackerzork/
├── engine/      # Parser, shell REPL, tab completion, history
├── systems/     # VFS, network, heat, toolkit, comms, state, save/load, events
├── commands/    # Every command is a @register_command plugin
├── effects/     # Typewriter, glitch, matrix, animations
├── audio/       # Mixer, ambient, SFX, reactive layer
├── meta/        # SkyNet brain, fourth-wall breaker, corruption engine
└── data/        # All game content in YAML — nodes, filesystem, dialogue, packages
```

Every command is a plugin. Every system talks through the event bus. Content is data, not code. SkyNet listens to everything.

## License

MIT
