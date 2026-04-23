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

🚧 **Early development** — Engine scaffolding in progress. The systems are being built module by module.

## License

MIT
