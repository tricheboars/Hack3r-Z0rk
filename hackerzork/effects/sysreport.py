"""First-boot sysreport — neofetch-style orientation panel."""
from __future__ import annotations

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.text import Text


_GLYPH = (
    " ▄▄▄▄▄▄▄ ",
    " █ ▄█▄ █ ",
    " █ ███ █ ",
    " █ ░░░ █ ",
    " ▀▀▀▀▀▀▀ ",
)
_GLYPH_PAD = " " * len(_GLYPH[0])

_BAR_WIDTH = 10


def _threat_bar(heat: float) -> tuple[str, str, str]:
    pct = max(0.0, min(100.0, heat)) / 100.0
    filled = int(round(pct * _BAR_WIDTH))
    bar = "█" * filled + "░" * (_BAR_WIDTH - filled)
    if heat < 25:
        return bar, "green", "NOMINAL"
    if heat < 50:
        return bar, "yellow", "WATCHED"
    if heat < 75:
        return bar, "red", "ACTIVE"
    return bar, "bright_red", "BURN-IMMINENT"


def render_sysreport(
    heat: float = 0.0,
    evidence: str = "1 sealed container  ·  encrypted",
    contact: str | None = None,
) -> Group:
    """Build the orientation panel as a Rich renderable.

    contact — handle string ("Z0RK-7  ·  [ secure ]") or None for "awaiting signal".
    """
    bar, bar_color, bar_label = _threat_bar(heat)
    heat_int = int(round(heat))
    contact_line = contact or "[dim]— [ awaiting signal ][/dim]"

    rows = [
        f"  [bold green]{_GLYPH[0]}[/bold green]   [bold white]HOST[/bold white][dim]........[/dim] tx-7  ·  cold-boot, 42 days",
        f"  [bold green]{_GLYPH[1]}[/bold green]   [bold white]USER[/bold white][dim]........[/dim] defector   uid=1337",
        f"  [bold green]{_GLYPH[2]}[/bold green]   [bold white]SHELL[/bold white][dim].......[/dim] /bin/zorksh  0.6.x",
        f"  [bold green]{_GLYPH[3]}[/bold green]   [bold white]KERNEL[/bold white][dim]......[/dim] [dim]6.6.6-sk-patched[/dim]",
        f"  [bold green]{_GLYPH[4]}[/bold green]   [bold white]THREAT[/bold white][dim]......[/dim] [{bar_color}]{bar}[/{bar_color}]   [{bar_color}]{bar_label}[/{bar_color}]   [dim][ {heat_int:02d} / 100 ][/dim]",
        f"  {_GLYPH_PAD}   [bold white]EVIDENCE[/bold white][dim]....[/dim] {evidence}",
        f"  {_GLYPH_PAD}   [bold white]CONTACT[/bold white][dim].....[/dim] {contact_line}",
        "",
        "  [bold green]── ORIENTATION ──────────────────────────────────────────[/bold green]",
        "     [bold]help[/bold]       [dim]index of every command on this box[/dim]",
        "     [bold]tutorial[/bold]   [dim]10-step guided walkthrough[/dim]",
        "     [bold]hint[/bold]       [dim]situational nudge when you're stuck[/dim]",
        "     [bold]learn[/bold]      [dim]concept primer  (pipes · ssh · cves · …)[/dim]",
    ]

    panel = Panel(
        Group(*[Text.from_markup(line) for line in rows]),
        box=box.DOUBLE,
        border_style="bold green",
        padding=(0, 1),
        width=72,
    )
    footer = Text.from_markup(
        "  [dim red]>> 2026-03-15 02:31 :: unknown ssh accepted from 45.152.66.201[/dim red]"
    )
    return Group(panel, Text(""), footer, Text(""))
