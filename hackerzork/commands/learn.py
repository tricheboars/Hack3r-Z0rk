"""learn command — concept pages independent of any single command.

Topics live as Markdown files under ``hackerzork/data/learn/<topic>.md``.
Adding a new topic is a one-file change with no code edits.
"""
from __future__ import annotations

import pathlib

from hackerzork.engine.command_registry import CommandContext, register_command


_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "learn"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _topics() -> list[str]:
    if not _DATA_DIR.exists():
        return []
    return sorted(p.stem for p in _DATA_DIR.glob("*.md"))


def _read_topic(name: str) -> str | None:
    path = _DATA_DIR / f"{name}.md"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _topic_summary(name: str) -> str:
    """First non-blank, non-heading line of a topic file."""
    body = _read_topic(name) or ""
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        return line
    return "(no summary)"


def _render(name: str, body: str) -> str:
    """Apply Rich-friendly markup to the markdown — light touch."""
    out: list[str] = []
    for raw in body.splitlines():
        line = raw.rstrip()
        # Bold cyan top-level headings (# Title)
        if line.startswith("# "):
            out.append(f"[bold cyan]{line[2:]}[/bold cyan]")
            continue
        # Bold yellow secondary headings (## ...)
        if line.startswith("## "):
            out.append(f"[bold yellow]{line[3:]}[/bold yellow]")
            continue
        # Tertiary headings (### ...) — dim
        if line.startswith("### "):
            out.append(f"[bold]{line[4:]}[/bold]")
            continue
        out.append(line)
    return "\n".join(out)


def _index_text() -> str:
    topics = _topics()
    if not topics:
        return (
            "[learn] No topic pages installed under data/learn/.\n"
            "Drop <topic>.md files there and they'll appear here automatically."
        )
    width = max(len(t) for t in topics) + 2
    lines = [
        "[bold cyan]LEARN — concept pages[/bold cyan]",
        "[dim]" + ("─" * 44) + "[/dim]",
        "",
    ]
    for t in topics:
        summary = _topic_summary(t)
        lines.append(f"  [cyan]{t:<{width}}[/cyan] {summary}")
    lines += [
        "",
        "[dim]Type 'learn <topic>' to read a page.[/dim]",
        "[dim]Topics complement 'man <command>' — they explain WHY, not just HOW.[/dim]",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@register_command(
    name="learn",
    usage="learn [topic]",
    help_text="Read a concept page (pipes, permissions, cves, ssh-keys, ...)",
    category="system",
    description=(
        "Concept-oriented documentation, independent of any single command.\n"
        "Where `man` answers 'what flags does ls take?', `learn` answers 'how\n"
        "do Unix permissions work, and why?'.\n"
        "\n"
        "Run with no args for the index. Run with a topic name to read it.\n"
        "Topics live under data/learn/<topic>.md — community-extendable."
    ),
    examples=[
        ("learn", "list every available topic"),
        ("learn pipes", "how `|` works and the philosophy behind it"),
        ("learn permissions", "the rwx triplets, deeply"),
        ("learn cves", "what CVEs are and how the lookup workflow works"),
    ],
    see_also=["man", "help", "tutorial", "hint"],
    concepts=["documentation"],
)
def cmd_learn(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return _index_text()
    topic = args[0].lower().replace("_", "-")
    body = _read_topic(topic)
    if body is None:
        topics = _topics()
        suggestion = ""
        # Best-effort suggestion: any topic that contains the requested string
        candidates = [t for t in topics if topic in t or t.startswith(topic[:3])]
        if candidates:
            suggestion = f"\n  Did you mean: {', '.join(candidates)}?"
        return (
            f"[learn] No topic '{topic}'.{suggestion}\n"
            f"  Available: {', '.join(topics)}"
        )
    return _render(topic, body)
