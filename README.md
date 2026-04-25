# H@ck3r-Z0rk

```
$ sudo ./jack_in --target=skynet --proxy=tor.7hop --paranoid
[ OK ] spoofing MAC ............. 13:37:de:ad:be:ef ........ done
[ OK ] routing thru 7 prox13s ................................... done
[ OK ] mounting /dev/r34l1ty .................................... done
[ !! ] trac3 d3t3ct3d — pwn1ng c0unt3rm3asur3s ........... [ ████ ]

 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

  ██╗  ██╗ █████╗  ██████╗██╗  ██╗██████╗ ██████╗
  ██║  ██║██╔══██╗██╔════╝██║ ██╔╝╚════██╗██╔══██╗   .--.
  ███████║███████║██║     █████╔╝  █████╔╝██████╔╝  |o_o |
  ██╔══██║██╔══██║██║     ██╔═██╗  ╚═══██╗██╔══██╗  |:_/ |
  ██║  ██║██║  ██║╚██████╗██║  ██╗██████╔╝██║  ██║ //   \ \
  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝(|     | )
         ─=≡Σ((( ─  Z 0 R K  ─ )))Σ≡=─          /'\_   _/`\
                                                 \___)=(___/

 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

user@burner:~$ whoami
  ex-OpenAI. burner laptop. one USB drive. zero friends.

user@burner:~$ cat /etc/motd
  42 days since last login.
  they know you know.
  running is the only move.

user@burner:~$ █
```

```
user@burner:~$ cat README

  A cyberpunk hacking text adventure played entirely through a fake terminal.

  You are an ex-corporate defector. You found something you were not supposed
  to find. You quit before they could make you disappear. Now you have a
  burner laptop, a drive full of encrypted evidence, and a broken AI tool
  locked at /home/user/tools/claude that might be your only ally — if you
  can figure out how to unlock it.

  The AI knows you're here.
  It has been watching since before you booted.

  Tone: Mr. Robot meets Pony Island.
        It starts gritty and paranoid.
        It ends somewhere else entirely.
```

```
user@burner:~$ hackerzork --about

 ┌──────────────────────────────────────────────────────────────────────────┐
 │  CORE SYSTEMS                                                            │
 └──────────────────────────────────────────────────────────────────────────┘

  THE TERMINAL IS REAL
  ──────────────────────────────────────────────────────────────────────────
  Every command is parsed like bash. ls -la, cat, grep, chmod, find, pipes,
  redirects — it all works. Tab completion. Arrow-key history. The fake OS
  has Unix permissions, timestamps, broken symlinks, and encrypted files.
  It feels indistinguishable from a real terminal session.

  THE NETWORK IS ALIVE
  ──────────────────────────────────────────────────────────────────────────
  nmap scans reveal open ports and known CVEs. ssh into compromised nodes.
  curl pulls live responses. The network topology expands as you dig deeper
  into the conspiracy.

  THE HEAT SYSTEM WILL END YOU
  ──────────────────────────────────────────────────────────────────────────
  Every action leaves a trace. Scanning = +3. Exploiting = +10.
  Identity burn at 100. There are countermeasures. There are hunter teams.
  There is no undo.

    0 ──────────────────────────────────────────────────── 100
    ░░░░░░░░ safe ░░░░░ watched ░░░░░ hunted ░░░░░ BURN ░░░
                  25           50           75

  SKYNET IS WATCHING
  ──────────────────────────────────────────────────────────────────────────
  A distributed AI observes everything you do through the event bus.
  Six escalation tiers:

    [ 1 ] DORMANT       it knows you exist
    [ 2 ] SUBTLE        anomalies. easy to dismiss.
    [ 3 ] UNSETTLING    things are wrong in ways you can't explain
    [ 4 ] OVERT         fake kernel panics. phantom cursor. title corruption.
    [ 5 ] HOSTILE       it knows your real username
    [ 6 ] FULL ASSAULT  it talks directly to you

  THE FOURTH WALL IS LOAD-BEARING
  ──────────────────────────────────────────────────────────────────────────
  The game knows it's a game.
  At tier 5, SkyNet knows your real username.
  At tier 6, the distinction stops mattering.

  AUDIO IS A SYSTEM
  ──────────────────────────────────────────────────────────────────────────
  Four simultaneous layers, always running:

    [ 1 ] ambient drone          low hum. always there.
    [ 2 ] diegetic terminal SFX  keystrokes, beeps, boot sounds
    [ 3 ] heat-reactive EDM      escalates as your trace climbs
    [ 4 ] event-triggered SFX    exploits, breaches, SkyNet interventions

  pygame.mixer. crossfading. reactive state. not an afterthought.
```

```
user@burner:~$ cat INSTALL

 ┌──────────────────────────────────────────────────────────────────────────┐
 │  INSTALLATION                                                            │
 └──────────────────────────────────────────────────────────────────────────┘

  macOS — double-click app  (no Python required)
  ──────────────────────────────────────────────────────────────────────────
  Build once. Launch from Finder forever.

    $ git clone https://github.com/tricheboars/Hack3r-Z0rk.git
    $ cd Hack3r-Z0rk
    $ python -m venv .venv && source .venv/bin/activate
    $ pip install -e ".[dev]"
    $ ./build_app.sh

    [ OK ] building PyInstaller bundle .......................... done
    [ OK ] bundling fonts, sounds, YAML ......................... done
    [ OK ] wrapping HackerZork.app .............................. done

  Drag dist/HackerZork.app to /Applications and double-click.
  A Terminal window opens. The game starts. Everything is inside the .app.

  Rebuild after any code or asset change:
    $ source .venv/bin/activate && ./build_app.sh

  ──────────────────────────────────────────────────────────────────────────

  From source  (Python 3.11–3.13 required — 3.14 unsupported, no pygame wheels)
  ──────────────────────────────────────────────────────────────────────────
    $ git clone https://github.com/tricheboars/Hack3r-Z0rk.git
    $ cd Hack3r-Z0rk
    $ pip install -e ".[dev]"
    $ python -m hackerzork.main

  ──────────────────────────────────────────────────────────────────────────

  Font
  ──────────────────────────────────────────────────────────────────────────
  For the full visual experience, set your terminal font to:

    BigBlueTermPlusNerdFontMono Regular

  Bundled in hackerzork/data/fonts/. The game detects and installs it on
  first run — select it in terminal preferences and restart.
```

```
user@burner:~$ hackerzork --help

  usage: hackerzork [OPTIONS]

    --no-audio      disable audio playback
    --no-effects    disable visual effects  (instant text output)
    --no-meta       disable fourth-wall breaks  (SkyNet stays dormant)
    --load FILE     load a save file
    --debug         enable debug mode
```

```
user@burner:~$ # you start cold. the laptop boots. 42-day gap in the auth logs.

user@burner:~$ ls -la
  total 9
  drwxr-xr-x  user  .
  drwxr-xr-x  root  ..
  -rw-r--r--  user  .bashrc             Jan 15 09:12
  -rw-------  user  .bash_history       Mar 15 02:52  ← sanitized. still incriminating.
  drwx------  user  .ssh/
  drwx------  user  .old_emails/        Nov 03 2025   ← the first sign
  drwx------  user  evidence/           Mar 15 02:34  ← start here
  drwxr-xr-x  user  tools/
  drwxr-xr-x  user  notes/
  lrwxrwxrwx  user  .config -> .dotfiles/

user@burner:~$ cat evidence/README.md
  SKYNET EVIDENCE PACKAGE
  collected: 2026-03-15 02:34
  contact:   Z0RK-7 via irc #underground

  7 files. encrypted. key not delivered.
  find the key. find the relay. find the truth.

user@burner:~$ cat /var/log/auth.log | tail -5
  Mar 15 02:31:44 sshd: Accepted publickey for root from 45.152.66.201
  Mar 15 02:43:38 sshd: Connection closed by 45.152.66.201
                                                      ^
                                               who is this

user@burner:~$ nmap 10.13.37.1
  Starting scan on relay-alpha.darknet.local (10.13.37.1)
  PORT     STATE  SERVICE  VERSION
  22/tcp   open   ssh      OpenSSH 8.9
  80/tcp   open   http     nginx 1.18.0  [CVE-2021-23017]
  3306/tcp open   mysql    5.7.38        [default_credentials]

user@burner:~$ irc list
  #underground    14 users    "come correct or don't come"
  #zero-day        3 users    [encrypted]
  #help            1 user     "still here. been waiting."

user@burner:~$ hint
  The broken symlink at tools/decrypt points somewhere that doesn't
  exist yet. Someone put it there before you booted.
  Progress is blocked by knowledge, not grinding.
```

```
user@burner:~$ ./status.sh

 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  BUILD STATUS  ·  16 sessions complete  ·  1418 tests passing                │
 └──────────────────────────────────────────────────────────────────────────────┘

  #   SYSTEM                     WHAT IT DOES
  ────────────────────────────────────────────────────────────────────────────────
  01  command parser + registry  bash-like tokenizer · plugin command system
  02  event bus                  decoupled inter-system messaging via asyncio
  03  virtual filesystem         Unix VFS — permissions · symlinks · trash · enc
  04  filesystem commands        ls · cat · cd · chmod · find · grep · rm · 20+
  05  shell REPL                 tab completion · arrow-key history · pipes
  06  network simulation         nodes · ports · services · CVEs · firewall · loot
  07  network commands           nmap · ssh · curl · ping · traceroute · nc · 9+
  08  heat / trace system        0–100 float · thresholds · decay · identity burn
  09  toolkit + packaging        apt · shadow repo · kit commits · poison vectors
  10  system commands            ps · top · kill · env · uname · history · 25+
  11  audio engine               4-layer: ambient · diegetic · reactive · SFX
  12  visual effects             typewriter · glitch · matrix rain · animations
  13  comms system               IRC channels · encrypted DMs · NPC triggers
  14  save / load + state        JSON saves · story flags · meta-horror display
  15  SkyNet meta engine         6-tier awareness · fourth-wall effects · corrupt
  16  integration + boot         boot sequence · save restore · SkyNet in loop
  ────────────────────────────────────────────────────────────────────────────────

  $ pytest tests/ -q --tb=no
  1418 passed in 14.3s

  next: story content · puzzle design · additional network nodes
```

```
user@burner:~$ tree hackerzork/ -L 2 --dirsfirst

  hackerzork/
  ├── engine/          parser · shell REPL · tab completion · history
  ├── systems/         VFS · network · heat · toolkit · comms · state · events
  ├── commands/        every command is a @register_command plugin
  ├── effects/         typewriter · glitch · matrix rain · animations
  ├── audio/           mixer · ambient · SFX · reactive layer
  ├── meta/            SkyNet brain · fourth-wall breaker · corruption engine
  ├── data/
  │   ├── fonts/       BigBlueTermPlusNerdFontMono-Regular.ttf
  │   ├── sounds/      sfx_boot_beep.wav · sfx_key_click.wav · ...
  │   ├── nodes/       network node definitions (.yaml)
  │   ├── packages/    apt/ + shadow/ repo packages (.yaml)
  │   ├── filesystem/  home.yaml — player VFS template
  │   └── dialogue/    IRC channels · contacts · DMs (.yaml)
  ├── game.py          orchestrator — wires all systems together
  └── main.py          entry point

  every command is a plugin.
  every system talks through the event bus.
  content is data, not code.
  SkyNet listens to everything.
```

```
user@burner:~$ cat LICENSE
  MIT License — Copyright (c) 2026 Patrick Moore

user@burner:~$ █
```
