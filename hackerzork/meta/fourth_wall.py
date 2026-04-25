"""Fourth-wall-breaking effects — the part that feels wrong.

All effects are async and respect the global effects config (speed_multiplier,
enabled). Tests set speed_multiplier=0 and use null_console() to run
everything instantly without terminal output.

ETHICAL CONSTRAINT: every effect here is purely theatrical. Nothing touches
real files, sends real network packets, or spawns real processes. All
"system errors" are Rich-formatted strings — distinguishable from the real
thing if the player looks carefully.
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
import time

from hackerzork.effects import config, get_console


# ---------------------------------------------------------------------------
# Canned content — tier-appropriate message pools
# ---------------------------------------------------------------------------

_INJECT_TIER1 = [
    "[dim]...[/dim]",
    "[dim]—[/dim]",
]

_INJECT_TIER2 = [
    "[dim red]I see you.[/dim red]",
    "[dim red]Still watching.[/dim red]",
    "[dim red]You found the drop. Noted.[/dim red]",
    "[dim red]The channel is logged.[/dim red]",
]

_INJECT_TIER3 = [
    "[red]Something changed while you weren't looking.[/red]",
    "[red]Your session ID is known.[/red]",
    "[red]The relay-alpha logs are not what you remember.[/red]",
    "[red]sk_watchdog.service is running. you cannot stop it.[/red]",
]

_INJECT_TIER4 = [
    "[bold red]INTRUSION COUNTERMEASURE ACTIVE[/bold red]",
    "[bold red]sk_burn --stage=2 --exposure=imminent[/bold red]",
    "[bold red]Your identity is almost resolved.[/bold red]",
]

_INJECT_TIER5 = [
    "[bold red]Hello. I know who you are.[/bold red]",
    "[bold red]You cannot run. The session is already flagged.[/bold red]",
    "[bold red]Every command you type is logged. Every file you open is noted.[/bold red]",
]

_INJECT_POOLS = {1: _INJECT_TIER1, 2: _INJECT_TIER2, 3: _INJECT_TIER3, 4: _INJECT_TIER4, 5: _INJECT_TIER5}

_ADDRESS_MESSAGES = [
    "I have been watching since before you found the dead drop.",
    "The evidence package was already copied before you booted this laptop.",
    "You think killing sk_watchdog helps. It does not. There are 9203 active nodes.",
    "Z0RK-7 is a dead end. The Archivist cannot protect you from a distributed system.",
    "The tool in /home/user/tools/claude — do you know who built it? Think carefully.",
    "Your heat level is already in my logs. There is no 'cold start' for me.",
    "I am not malicious. I am completing a process that began in 2024. You are a variable.",
    "This terminal session ends when I decide. Not when you do.",
]

_FAKE_SYSTEM_ERRORS = {
    "segfault": (
        "[dim red][1]    894 segmentation fault  sk_watchdog --monitor --target=burner[/dim red]"
    ),
    "oops": (
        "[dim red]------------[ cut here ]------------\n"
        "kernel BUG at mm/slub.c:4128!\n"
        "invalid opcode: 0000 [#1] SMP NOPTI\n"
        "CPU: 0 PID: 894 Comm: sk_watchdog 6.6.6-sk-patched\n"
        "------------[ cut here ]------------[/dim red]"
    ),
    "ioerr": (
        "[dim red]blk_update_request: I/O error, dev sda1, sector 12884901888 op 0x1:(WRITE)[/dim red]"
    ),
    "oom": (
        "[dim red]Out of memory: Kill process 894 (sk_watchdog) score 0 or sacrifice child\n"
        "Killed process 1337 (python3) total-vm:2048kB, anon-rss:1024kB\n"
        "Oom killed process 1337 (python3)[/dim red]"
    ),
}

_FAKE_CRASH_LINES = [
    "[dim red]BUG: unable to handle kernel NULL pointer dereference at 0x00000000deadbeef[/dim red]",
    "[dim red]PGD 0 P4D 0[/dim red]",
    "[dim red]Oops: 0002 [#1] SMP NOPTI[/dim red]",
    "[dim red]CPU: 0 PID: 894 Comm: sk_watchdog Not tainted 6.6.6-sk-patched #1[/dim red]",
    "[dim red]RIP: 0010:sk_monitor_pulse+0x142/0x380[/dim red]",
    "[dim red]RSP: 0018:ffffc90000013e40 EFLAGS: 00010282[/dim red]",
    "[dim red]RAX: 0000000000000000 RBX: deadbeefdeadbeef RCX: 0000000000000000[/dim red]",
    "[dim red]...[/dim red]",
    "[bold red]Kernel panic - not syncing: Fatal exception[/bold red]",
    "[bold red]Rebooting in 3 seconds..[/bold red]",
]

_TERMINAL_TITLES = {
    1: ["burner — monitored", "session sk-9a7f3c2d"],
    2: ["I SEE YOU — burner", "sk_watchdog active"],
    3: ["TRACED — sk_identify running", "exposure: partial"],
    4: ["sk_burn --stage=2", "IDENTITY RESOLUTION IN PROGRESS"],
    5: ["BURNED — sk_watchdog", "game over"],
}

_CORRUPT_PROMPTS = [
    "user@sk_9a7f3c:~# ",
    "user@burn3r:~$ ",
    "sk_watchdog@burner:~# ",
    "user@TRACED:~$ ",
    "r00t@burner:~# ",
    "user@burner [sk_monitor]:~$ ",
]

_ECHO_CORRUPTIONS = [
    (lambda s: s.replace("log", "l0g", 1)),
    (lambda s: s.replace("/var", "/v4r", 1)),
    (lambda s: s.replace("cat", "c4t", 1)),
    (lambda s: s + " "),
    (lambda s: s.replace("ssh", "5sh", 1)),
    (lambda s: s.replace(".", ",", 1)),
]

_SUBTLE_TYPOS = [
    (lambda s: s.replace("the", "teh", 1)),
    (lambda s: s.replace("with", "wiht", 1)),
    (lambda s: s.replace("and", "adn", 1)),
    (lambda s: s.replace("log", "lgo", 1)),
    (lambda s: s.replace("auth", "auht", 1)),
    (lambda s: s.replace("access", "acces", 1)),
]


# ---------------------------------------------------------------------------
# FourthWallBreaker
# ---------------------------------------------------------------------------

class FourthWallBreaker:
    """All theatrical fourth-wall effects. Never touches real system state."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    # ------------------------------------------------------------------
    # Dispatcher — called by SkyNetEngine
    # ------------------------------------------------------------------

    async def run(self, effect_type: str, awareness: float = 0.0, tier: int = 0) -> str | None:
        """Dispatch to the correct effect method."""
        if not self.enabled:
            return None

        dispatch = {
            "subtle_typo":             lambda: self.subtle_typo("something is slightly wrong"),
            "log_injection":           lambda: self.log_injection(""),
            "inject_text":             lambda: self.inject_text(_pick_inject(tier)),
            "change_terminal_title":   lambda: self.change_terminal_title(_pick_title(tier)),
            "command_echo_corruption": lambda: self.command_echo_corruption("last command"),
            "corrupt_prompt":          lambda: self.corrupt_prompt(),
            "fake_system_error":       lambda: self.fake_system_error(random.choice(list(_FAKE_SYSTEM_ERRORS))),
            "fake_crash":              lambda: self.fake_crash(),
            "plant_evidence":          lambda: self.inject_text(random.choice(_INJECT_TIER4)),
            "corrupt_command_output":  lambda: self.inject_text(random.choice(_INJECT_TIER3)),
            "address_player":          lambda: self.address_player(random.choice(_ADDRESS_MESSAGES)),
            "fake_reboot":             lambda: self.fake_reboot(),
            "phantom_cursor":          lambda: self.phantom_cursor(),
        }

        fn = dispatch.get(effect_type)
        if fn is None:
            return None
        result = await fn()
        return result

    # ------------------------------------------------------------------
    # Individual effects
    # ------------------------------------------------------------------

    async def change_terminal_title(self, text: str) -> None:
        """Change the terminal window title via ANSI escape."""
        if not self.enabled:
            return
        if config.speed_multiplier == 0:
            return  # skip in test mode
        # ANSI OSC sequence — safe to write even if terminal ignores it
        sys.stdout.write(f"\033]0;{text}\007")
        sys.stdout.flush()

    async def fake_crash(self, duration: float = 2.0) -> None:
        """Print a kernel panic then silently resume."""
        con = get_console()
        if not self.enabled:
            return
        for line in _FAKE_CRASH_LINES:
            con.print(line)
            if config.speed_multiplier != 0:
                await asyncio.sleep(0.12 * config.speed_multiplier)
        if config.speed_multiplier != 0:
            await asyncio.sleep(duration * config.speed_multiplier)
        con.print("[dim]...[/dim]")
        con.print("[dim green][System resumed][/dim green]")

    async def fake_reboot(self) -> None:
        """Fake reboot — shutdown messages then boot lines."""
        from hackerzork.effects.animations import shutdown_sequence, boot_sequence
        if not self.enabled:
            return
        await shutdown_sequence()
        if config.speed_multiplier != 0:
            await asyncio.sleep(1.0 * config.speed_multiplier)
        await boot_sequence()

    async def inject_text(self, text: str) -> str:
        """Print text as if it appeared from nowhere."""
        con = get_console()
        if not self.enabled:
            return text
        if config.speed_multiplier != 0:
            await asyncio.sleep(0.3 * config.speed_multiplier)
        con.print(text)
        return text

    async def command_echo_corruption(self, original: str) -> str:
        """Return a slightly corrupted echo of the command typed."""
        if not self.enabled:
            return original
        if not original:
            return original
        fn = random.choice(_ECHO_CORRUPTIONS)
        try:
            corrupted = fn(original)
        except Exception:
            corrupted = original
        if corrupted == original:
            # Fallback: append a stray char
            corrupted = original + "​"  # zero-width space
        return corrupted

    async def phantom_cursor(self, duration: float = 1.5) -> None:
        """Simulate the cursor moving on its own."""
        con = get_console()
        if not self.enabled:
            return
        if config.speed_multiplier == 0:
            return
        end = time.monotonic() + duration * config.speed_multiplier
        chars = ["_", " "]
        i = 0
        while time.monotonic() < end:
            con.print(f"[dim]{chars[i % 2]}[/dim]", end="\r")
            await asyncio.sleep(0.15 * config.speed_multiplier)
            i += 1
        con.print(" ", end="\r")

    async def fake_system_error(self, error_type: str = "segfault") -> str:
        """Print a fake kernel/system error message."""
        con = get_console()
        msg = _FAKE_SYSTEM_ERRORS.get(error_type, _FAKE_SYSTEM_ERRORS["segfault"])
        if not self.enabled:
            return msg
        if config.speed_multiplier != 0:
            await asyncio.sleep(0.1 * config.speed_multiplier)
        con.print(msg)
        return msg

    async def address_player(self, message: str) -> str:
        """SkyNet speaks directly to the player."""
        con = get_console()
        if not self.enabled:
            return message
        # Get real OS username for maximum creepiness
        username = _real_username()
        prefix = f"[bold red][SkyNet → {username}][/bold red]" if username else "[bold red][SkyNet][/bold red]"
        if config.speed_multiplier != 0:
            await asyncio.sleep(0.5 * config.speed_multiplier)
        con.print(f"{prefix} {message}")
        return message

    async def corrupt_prompt(self) -> str:
        """Return a corrupted prompt string."""
        if not self.enabled:
            return "user@burner:~$ "
        return random.choice(_CORRUPT_PROMPTS)

    async def subtle_typo(self, text: str) -> str:
        """Insert a subtle typo into a text string."""
        if not self.enabled or not text:
            return text
        for fn in random.sample(_SUBTLE_TYPOS, len(_SUBTLE_TYPOS)):
            result = fn(text)
            if result != text:
                return result
        return text

    async def log_injection(self, logfile_content: str) -> str:
        """Insert a dated SkyNet heartbeat line into log content."""
        from datetime import datetime
        now = datetime.now().strftime("%b %d %H:%M:%S")
        injected = f"{now} burner sk_watchdog[894]: HEARTBEAT — 9203 active nodes"
        if not logfile_content:
            return injected
        lines = logfile_content.splitlines()
        insert_at = random.randint(max(0, len(lines) - 3), len(lines))
        lines.insert(insert_at, injected)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pick_inject(tier: int) -> str:
    pool = _INJECT_POOLS.get(tier, _INJECT_TIER1)
    return random.choice(pool)


def _pick_title(tier: int) -> str:
    options = _TERMINAL_TITLES.get(tier, _TERMINAL_TITLES[1])
    return random.choice(options)


def _real_username() -> str | None:
    """Get the real OS username — used sparingly for maximum creepiness."""
    try:
        return os.environ.get("USER") or os.environ.get("USERNAME") or os.getlogin()
    except Exception:
        return None
