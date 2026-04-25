"""Boot sequences, progress bars, spinners, and dramatic animations."""
from __future__ import annotations

import asyncio
import random
import time

from hackerzork.effects import config, get_console


async def _sleep(s: float) -> None:
    effective = s * config.speed_multiplier
    if effective > 0:
        await asyncio.sleep(effective)


# ---------------------------------------------------------------------------
# boot_sequence
# ---------------------------------------------------------------------------

_BOOT_LINES = [
    ("[dim]SeaBIOS (version 1.16.3)[/dim]",                      0.10),
    ("[dim]Machine UUID: 4f3a-c8d2-91e7-b560[/dim]",             0.05),
    ("[dim]Detected 7812 MB RAM[/dim]",                           0.08),
    ("[dim]Checking memory.........................................[/dim]", 0.20),
    ("[dim green]OK[/dim green]",                                 0.05),
    ("[dim]Loading bootloader...[/dim]",                          0.15),
    ("[yellow]GRUB 2.12[/yellow]",                                0.08),
    ("[dim]Booting Linux 6.6.6-sk-patched...[/dim]",             0.12),
    ("[dim]  Loading initial ramdisk...[/dim]",                   0.10),
    ("[green]  [  OK  ][/green] [dim]Started udev kernel device manager[/dim]",  0.06),
    ("[green]  [  OK  ][/green] [dim]Reached target Basic System[/dim]",         0.05),
    ("[green]  [  OK  ][/green] [dim]Started OpenSSH server daemon[/dim]",       0.06),
    ("[green]  [  OK  ][/green] [dim]Started rsyslog logging service[/dim]",     0.05),
    # The suspicious line — sk_watchdog starts silently before the user session
    ("[dim]  [  OK  ] Started sk_watchdog.service[/dim]",        0.04),
    ("[green]  [  OK  ][/green] [dim]Reached target Multi-User System[/dim]",   0.06),
    ("",                                                           0.10),
    ("[bold]burner login:[/bold]",                                0.05),
]


async def boot_sequence() -> None:
    """Full cold boot animation — POST, memory check, services starting."""
    con = get_console()
    if not config.enabled:
        return
    for line, delay in _BOOT_LINES:
        con.print(line)
        await _sleep(delay)


# ---------------------------------------------------------------------------
# progress_bar
# ---------------------------------------------------------------------------

_BAR_STYLES: dict[str, dict] = {
    "hack":     {"fill": "█", "empty": "░", "color": "green",       "prefix": "[HACK]"},
    "download": {"fill": "▓", "empty": "░", "color": "cyan",        "prefix": "[DL]  "},
    "decrypt":  {"fill": "▒", "empty": "░", "color": "yellow",      "prefix": "[DEC] "},
    "upload":   {"fill": "█", "empty": "─", "color": "bright_blue", "prefix": "[UP]  "},
}


async def progress_bar(
    label: str,
    duration: float,
    style: str = "hack",
    width: int = 40,
) -> None:
    """Animated progress bar. Styles: hack, download, decrypt, upload."""
    con = get_console()
    st = _BAR_STYLES.get(style, _BAR_STYLES["hack"])
    fill, empty = st["fill"], st["empty"]
    color, prefix = st["color"], st["prefix"]

    if not config.enabled or config.speed_multiplier == 0:
        bar = fill * width
        con.print(f"[{color}]{prefix} {label}: [{bar}] 100%[/{color}]")
        return

    steps = 50
    tick = duration / steps
    for i in range(steps + 1):
        pct = i / steps
        filled = int(width * pct)
        bar = fill * filled + empty * (width - filled)
        pct_str = f"{int(pct * 100):3d}%"
        con.print(
            f"[{color}]{prefix} {label}: [{bar}] {pct_str}[/{color}]",
            end="\r",
        )
        await _sleep(tick)
    con.print("")


# ---------------------------------------------------------------------------
# spinner
# ---------------------------------------------------------------------------

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


async def spinner(label: str, duration: float) -> None:
    """Terminal spinner with label."""
    con = get_console()
    if not config.enabled or config.speed_multiplier == 0:
        con.print(f"[green]✓[/green] {label}")
        return
    end = time.monotonic() + duration
    i = 0
    while time.monotonic() < end:
        frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
        con.print(f"[green]{frame}[/green] {label}", end="\r", markup=True)
        await _sleep(0.08)
        i += 1
    con.print(f"[green]✓[/green] {label}")


# ---------------------------------------------------------------------------
# connection_animation
# ---------------------------------------------------------------------------

async def connection_animation(target: str) -> None:
    """SSH connection establishing animation with fake handshake."""
    con = get_console()
    steps = [
        (f"Connecting to {target}...",                  0.20),
        ("TCP handshake...",                             0.15),
        ("SSH protocol negotiation...",                  0.18),
        ("Authenticating (publickey)...",                0.25),
        (f"[green]Connected to {target}[/green]",       0.10),
        ("Last login: see /var/log/auth.log",            0.08),
    ]
    if not config.enabled or config.speed_multiplier == 0:
        con.print(f"[green]Connected to {target}[/green]")
        return
    for text, delay in steps:
        con.print(text)
        await _sleep(delay)


# ---------------------------------------------------------------------------
# breach_animation
# ---------------------------------------------------------------------------

_BREACH_ART = """
  ██████╗ ██████╗ ███████╗ █████╗  ██████╗██╗  ██╗███████╗██████╗ ██╗
  ██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝██║  ██║██╔════╝██╔══██╗██║
  ██████╔╝██████╔╝█████╗  ███████║██║     ███████║█████╗  ██║  ██║██║
  ██╔══██╗██╔══██╗██╔══╝  ██╔══██║██║     ██╔══██║██╔══╝  ██║  ██║╚═╝
  ██████╔╝██║  ██║███████╗██║  ██║╚██████╗██║  ██║███████╗██████╔╝██╗
  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝
"""


async def breach_animation() -> None:
    """Dramatic animation for a successful exploit — the big moment."""
    from hackerzork.effects.glitch import static_burst
    con = get_console()
    if not config.enabled or config.speed_multiplier == 0:
        con.print("[bold red]ACCESS GRANTED[/bold red]")
        return
    # Static burst then reveal
    for _ in range(3):
        con.print(f"[dim]{static_burst(60, 2)}[/dim]")
        await _sleep(0.08)
    await _sleep(0.15)
    con.print("[bold red]" + _BREACH_ART + "[/bold red]")
    await _sleep(0.3)
    con.print("[bold green]ACCESS GRANTED[/bold green]")
    await _sleep(0.2)


# ---------------------------------------------------------------------------
# shutdown_sequence
# ---------------------------------------------------------------------------

_SHUTDOWN_LINES = [
    ("[yellow]Broadcast message from root:[/yellow]",    0.10),
    ("[yellow]The system is going down NOW![/yellow]",   0.15),
    ("[dim]Stopping services...[/dim]",                   0.10),
    ("[dim]  [ STOP ] sk_uplink.service[/dim]",           0.08),
    ("[dim]  [ STOP ] sk_comms.service[/dim]",            0.08),
    # sk_watchdog refuses to stop — key detail
    ("[yellow]  [FAILED] sk_watchdog.service: timeout[/yellow]",   0.12),
    ("[dim]Syncing filesystems...[/dim]",                  0.10),
    ("[red]IDENTITY BURN INITIATED[/red]",                 0.20),
    ("[dim red]Wiping session logs...[/dim red]",          0.10),
    ("[dim red]Overwriting traces...[/dim red]",           0.10),
    ("[bold red]System halted.[/bold red]",                0.15),
]


async def shutdown_sequence() -> None:
    """System shutdown / identity burn animation."""
    con = get_console()
    if not config.enabled or config.speed_multiplier == 0:
        con.print("[bold red]System halted.[/bold red]")
        return
    for line, delay in _SHUTDOWN_LINES:
        con.print(line)
        await _sleep(delay)


# ---------------------------------------------------------------------------
# scan_animation
# ---------------------------------------------------------------------------

async def scan_animation(target: str, ports_found: int = 3) -> None:
    """nmap-style scan output animation."""
    con = get_console()
    if not config.enabled or config.speed_multiplier == 0:
        con.print(f"[green]Nmap scan report for {target}[/green]")
        return
    con.print(f"Starting scan of {target}...")
    await _sleep(0.15)
    total_ports = 1000
    scanned = 0
    tick = 0.002
    while scanned < total_ports:
        batch = random.randint(5, 30)
        scanned = min(scanned + batch, total_ports)
        pct = scanned * 100 // total_ports
        con.print(f"[dim]Scanning {scanned}/{total_ports} ports ({pct}%)...[/dim]", end="\r")
        await _sleep(tick)
    con.print("")

    # Port results
    _COMMON_PORTS = {22: "ssh", 80: "http", 443: "https", 3306: "mysql",
                     8080: "http-alt", 21: "ftp", 25: "smtp", 53: "dns"}
    port_list = random.sample(list(_COMMON_PORTS.items()), min(ports_found, len(_COMMON_PORTS)))
    con.print(f"[green]Nmap scan report for {target}[/green]")
    con.print("PORT     STATE  SERVICE")
    for port, service in sorted(port_list):
        await _sleep(0.08)
        con.print(f"[cyan]{port:<8} open   {service}[/cyan]")
    con.print(f"\n{ports_found} open ports found.")
