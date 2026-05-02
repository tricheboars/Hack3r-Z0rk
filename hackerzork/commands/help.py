"""help and hint commands."""
from __future__ import annotations

import random

from hackerzork.engine.command_registry import CommandContext, register_command


@register_command(
    name="help",
    usage="help [command]",
    help_text="List available commands or show help for a specific command",
    category="system",
)
def cmd_help(ctx: CommandContext, args: list[str]) -> str:
    registry = ctx.registry
    if registry is None:
        return "help: no registry available"

    if args:
        return registry.get_help(args[0])

    # Full listing grouped by category
    lines = [
        "[bold cyan]H@ck3r-Z0rk[/bold cyan] — Available Commands",
        "[dim]" + "─" * 44 + "[/dim]",
        "",
    ]
    for cat in registry.categories():
        handlers = registry.get_all_by_category(cat)
        if not handlers:
            continue
        lines.append(f"  [bold]{cat}[/bold]")
        for h in sorted(handlers, key=lambda x: x.name):
            lines.append(f"    [cyan]{h.name:<16}[/cyan] {h.help_text}")
        lines.append("")

    lines.append("[dim]Type 'help <command>' for detailed usage.[/dim]")
    lines.append("[dim]Type 'hint' if you're stuck.[/dim]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Contextual hints — ordered by expected early-game progression
# ---------------------------------------------------------------------------

_EARLY_HINTS = [
    "You just woke up after 42 days. Start here: ls -la",
    "Something is in the evidence/ folder. Try: cat evidence/README.md",
    "The auth log has timestamps that don't add up. Try: cat /var/log/auth.log",
    "Your .bash_history was sanitized — but not completely. cat .bash_history",
    "Some files were deleted. Try: recover /home/user/tools/exfil.py",
]

_MID_HINTS = [
    "The network is not empty. Try: nmap 10.13.37.1",
    "nmap -sV shows service versions AND vulns. That CVE number is your key.",
    "Exploit syntax: exploit -p PORT -e CVE_OR_VULN_NAME <target>",
    "Standard tools won't cut it here. Try: shadow list",
    "z0rk_7 has been trying to reach you. Try: msg list",
    "There are IRC channels. Try: irc list, then irc join #underground",
    "The broken symlink in tools/ points somewhere that doesn't exist — yet.",
]

_LATE_HINTS = [
    "The core.enc file needs a key. The key is split across relay nodes.",
    "Compromising relay-alpha reveals the next hop in the chain.",
    "The #z0rk_7_ops channel requires the shadow_unlocked flag to join.",
    "sk_watchdog.service cannot be stopped. That is intentional.",
    "The tool in /home/user/tools/claude — ask yourself who built it.",
]


@register_command(
    name="hint",
    usage="hint",
    help_text="Get a contextual hint when you're stuck",
    category="system",
)
def cmd_hint(ctx: CommandContext, args: list[str]) -> str:
    pool = _pick_hint_pool(ctx)
    text = random.choice(pool)
    return f"[yellow]HINT:[/yellow] {text}"


def _pick_hint_pool(ctx: CommandContext) -> list[str]:
    if ctx.state is None:
        return _EARLY_HINTS

    flags: set[str] = getattr(ctx.state, "flags", set())

    if "relay_alpha_compromised" in flags or "shadow_unlocked" in flags:
        return _LATE_HINTS
    if flags:
        return _MID_HINTS
    return _EARLY_HINTS
