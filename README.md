# H@ck3r-Z0rk

```
$ sudo ./jack_in --target=skynet --proxy=tor.7hop --paranoid
[ OK ] spoofing MAC ........... 13:37:de:ad:be:ef ........ [ done ]
[ OK ] routing thru 7 prox13s ............................ [ done ]
[ OK ] mounting /dev/r34l1ty ............................. [ done ]
[ !! ] trac3 d3t3ct3d — pwn1ng c0unt3rm3asur3s ........... [ ████ ]

░▒▓███▓▒░▒▓███▓▒░▒▓███▓▒░ wake up, neo. ░▒▓███▓▒░▒▓███▓▒░▒▓███▓▒░

 ██╗  ██╗ █████╗  ██████╗██╗  ██╗██████╗ ██████╗
 ██║  ██║██╔══██╗██╔════╝██║ ██╔╝╚════██╗██╔══██╗   .--.
 ███████║███████║██║     █████╔╝  █████╔╝██████╔╝  |o_o |
 ██╔══██║██╔══██║██║     ██╔═██╗  ╚═══██╗██╔══██╗  |:_/ |
 ██║  ██║██║  ██║╚██████╗██║  ██╗██████╔╝██║  ██║ //   \ \
 ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝(|     | )
        ─=≡Σ((( ─  Z 0 R K  ─ )))Σ≡=─           /'\_   _/`\
                                                \___)=(___/

░▒▓████████████████████████████████████████████████████████▓▒░

root@blackbox:~# whoami
> ex-corporate. one burner laptop. one USB drive. z3r0 fr13nds.
root@blackbox:~# cat /etc/motd
> th3y kn0w y0u kn0w.  r u n n i n g  i s  t h e  0 n l y  m 0 v e.
root@blackbox:~# _
```

A cyberpunk hacking text adventure played through a simulated terminal.

You are an ex-corporate defector. You discovered something that was never meant to be found. Now you're on the run with a burner laptop, a USB drive full of evidence, and a broken AI tool that might be your only ally — if you can figure out how to turn it on.

## What Is This?

A Zork-style text adventure where **you actually hack.** Real Linux commands. Real networking concepts. Real cryptography. Played through a fake OS that feels indistinguishable from a real terminal.

The tone is Mr. Robot meets Pony Island. It starts gritty and paranoid. It ends... somewhere else.

## Requirements

- Python **3.11–3.13** (3.14 isn't supported yet — pygame doesn't ship wheels for it)
- A terminal
- Computer science knowledge (or a willingness to learn)

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

## Status

Active development — core engine complete, narrative systems wiring in progress. 1025 tests passing.

| # | Module | Status |
|---|--------|--------|
| 1 | Command parser + registry | ✅ Done |
| 2 | Event bus | ✅ Done |
| 3 | Virtual filesystem | ✅ Done |
| 4 | Filesystem commands (`ls`, `cat`, `chmod`, 20+ more) | ✅ Done |
| 5 | Shell REPL, tab completion, command history | ✅ Done |
| 6 | Network simulation (nodes, ports, firewall, loot) | ✅ Done |
| 7 | Network commands (`nmap`, `ssh`, `curl`, `netcat`, 9 more) | ✅ Done |
| 8 | Heat / trace system (escalation, decay, burn at 100) | ✅ Done |
| 9 | Toolkit + packaging (`apt`, `shadow`, kit commits, poison vectors) | ✅ Done |
| 10 | System commands (`ps`, `top`, `kill`, `env`, `history`, 25+ more) | ✅ Done |
| 11 | Audio engine (4-layer: ambient, diegetic, reactive, music) | ✅ Done |
| 12 | Visual effects (typewriter, glitch, matrix rain, animations) | ✅ Done |
| 13 | Comms system (IRC channels, encrypted DMs) | 🔨 In progress |
| 14 | Save / load + game state machine | |
| 15 | SkyNet meta engine + fourth-wall breaks | |
| 16 | Full integration + boot sequence | |

## License

MIT
