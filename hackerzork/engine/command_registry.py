"""Plugin-style command registry for the H@ck3r-Z0rk shell.

Commands register themselves with ``@register_command`` and the registry
handles dispatch, tab-completion, and help-text lookup. ``CommandContext``
is the single argument injected into every handler — it carries references
to all live game systems plus the per-call environment.

Educational metadata
--------------------
Each command can also carry man-page-style fields:

- ``synopsis``   — one-line tagline shown in NAME (defaults to help_text)
- ``description`` — multi-paragraph DESCRIPTION explaining the underlying
  CS / security concept the command embodies
- ``examples``   — list of ``(command_line, what_it_does)`` tuples
- ``see_also``   — list of related command names
- ``concepts``   — list of ``learn`` topic keys (e.g. ``["pipes", "redirects"]``)

When any of these are present, ``get_help()`` renders a real man-page-style
output instead of the bare metadata block.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # pragma: no cover — types only
    from hackerzork.meta.skynet import SkyNetEngine
    from hackerzork.systems.comms import CommsSystem
    from hackerzork.systems.events import EventBus
    from hackerzork.systems.heat import HeatSystem
    from hackerzork.systems.network import NetworkSim
    from hackerzork.systems.save_load import SaveSystem
    from hackerzork.systems.state import GameState
    from hackerzork.systems.toolkit import Toolkit
    from hackerzork.systems.virtual_fs import VirtualFS


CommandFn = Callable[["CommandContext", list[str]], str]


@dataclass
class CommandContext:
    """Bundle of game systems passed to every command handler.

    Fields are typed as ``Any`` at runtime to avoid hard import cycles with
    systems that may not be built yet; the TYPE_CHECKING block above gives
    editors and type-checkers the real types.
    """

    fs: Any = None           # VirtualFS
    network: Any = None      # NetworkSim
    state: Any = None        # GameState
    events: Any = None       # EventBus
    heat: Any = None         # HeatSystem
    toolkit: Any = None      # Toolkit
    comms: Any = None        # CommsSystem
    save_system: Any = None  # SaveSystem
    git_saves: Any = None    # GitSaveSystem
    skynet: Any = None       # SkyNetEngine
    history: Any = None      # CommandHistory
    registry: Any = None     # CommandRegistry (for man/help)
    output: Any = None       # OutputBuffer (effects-aware writer)
    tutorial: Any = None     # TutorialEngine (set by Game.boot)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class CommandHandler:
    name: str
    fn: CommandFn
    usage: str = ""
    help_text: str = ""
    category: str = "misc"
    aliases: list[str] = field(default_factory=list)

    # Educational metadata (all optional — empty values fall back to the
    # legacy minimal man-page rendering).
    synopsis: str = ""
    description: str = ""
    examples: list[tuple[str, str]] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)

    def __call__(self, ctx: CommandContext, args: list[str]) -> str:
        return self.fn(ctx, args)


class CommandRegistry:
    """Registry of available commands, keyed by primary name + aliases."""

    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}
        self._aliases: dict[str, str] = {}  # alias -> primary name

    def register(
        self,
        name: str,
        handler: CommandFn,
        *,
        usage: str = "",
        help_text: str = "",
        category: str = "misc",
        aliases: list[str] | None = None,
        synopsis: str = "",
        description: str = "",
        examples: list[tuple[str, str]] | None = None,
        see_also: list[str] | None = None,
        concepts: list[str] | None = None,
    ) -> CommandHandler:
        h = CommandHandler(
            name=name,
            fn=handler,
            usage=usage,
            help_text=help_text,
            category=category,
            aliases=list(aliases or []),
            synopsis=synopsis,
            description=description,
            examples=list(examples or []),
            see_also=list(see_also or []),
            concepts=list(concepts or []),
        )
        self._handlers[name] = h
        for alias in h.aliases:
            self._aliases[alias] = name
        return h

    def get(self, name: str) -> CommandHandler | None:
        if name in self._handlers:
            return self._handlers[name]
        primary = self._aliases.get(name)
        if primary is not None:
            return self._handlers[primary]
        return None

    def get_all_by_category(self, category: str) -> list[CommandHandler]:
        return [h for h in self._handlers.values() if h.category == category]

    def get_completions(self, partial: str) -> list[str]:
        out: set[str] = set()
        for name in self._handlers:
            if name.startswith(partial):
                out.add(name)
        for alias in self._aliases:
            if alias.startswith(partial):
                out.add(alias)
        return sorted(out)

    def get_help(self, name: str) -> str:
        """Render a man-page-style help block for ``name``.

        Falls back to the original short metadata block if no educational
        fields (description/examples/see_also) were provided.
        """
        h = self.get(name)
        if h is None:
            return f"bash: no help topic for '{name}'"

        tagline = h.synopsis or h.help_text or "(no description)"
        sections: list[str] = [
            f"[bold cyan]NAME[/bold cyan]\n    {h.name} — {tagline}"
        ]
        if h.usage:
            sections.append(f"[bold cyan]SYNOPSIS[/bold cyan]\n    {h.usage}")
        if h.description:
            wrapped = "\n".join(
                "    " + line if line else ""
                for line in h.description.strip().splitlines()
            )
            sections.append(f"[bold cyan]DESCRIPTION[/bold cyan]\n{wrapped}")
        if h.examples:
            ex_lines = []
            for cmdline, explanation in h.examples:
                ex_lines.append(f"    [green]$ {cmdline}[/green]")
                if explanation:
                    ex_lines.append(f"        [dim]{explanation}[/dim]")
            sections.append("[bold cyan]EXAMPLES[/bold cyan]\n" + "\n".join(ex_lines))
        if h.see_also:
            sections.append(
                "[bold cyan]SEE ALSO[/bold cyan]\n    " + ", ".join(h.see_also)
            )
        if h.concepts:
            topics = ", ".join(f"learn {c}" for c in h.concepts)
            sections.append(
                f"[bold cyan]LEARN MORE[/bold cyan]\n    {topics}"
            )
        if h.aliases:
            sections.append(
                f"[bold cyan]ALIASES[/bold cyan]\n    {', '.join(h.aliases)}"
            )
        sections.append(f"[bold cyan]CATEGORY[/bold cyan]\n    {h.category}")
        return "\n\n".join(sections)

    def get_brief_help(self, name: str) -> str:
        """One-screen help for ``--help`` flag — usage + one-line summary."""
        h = self.get(name)
        if h is None:
            return f"bash: no help topic for '{name}'"
        tagline = h.help_text or h.synopsis or "(no description)"
        lines = [f"{h.name} — {tagline}"]
        if h.usage:
            lines.append(f"  usage: {h.usage}")
        if h.aliases:
            lines.append(f"  aliases: {', '.join(h.aliases)}")
        lines.append(f"  Type 'man {h.name}' for details.")
        return "\n".join(lines)

    def all(self) -> list[CommandHandler]:
        return list(self._handlers.values())

    def categories(self) -> list[str]:
        return sorted({h.category for h in self._handlers.values()})

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None


# Module-level default registry. Most production commands register here via
# the bare @register_command decorator. Tests should pass registry= to scope
# registrations to a fresh instance.
DEFAULT_REGISTRY = CommandRegistry()


def register_command(
    name: str,
    *,
    usage: str = "",
    help_text: str = "",
    category: str = "misc",
    aliases: list[str] | None = None,
    synopsis: str = "",
    description: str = "",
    examples: list[tuple[str, str]] | None = None,
    see_also: list[str] | None = None,
    concepts: list[str] | None = None,
    registry: CommandRegistry | None = None,
) -> Callable[[CommandFn], CommandFn]:
    """Decorator that registers a command handler with metadata."""
    target = registry if registry is not None else DEFAULT_REGISTRY

    def decorator(fn: CommandFn) -> CommandFn:
        target.register(
            name,
            fn,
            usage=usage,
            help_text=help_text,
            category=category,
            aliases=aliases,
            synopsis=synopsis,
            description=description,
            examples=examples,
            see_also=see_also,
            concepts=concepts,
        )
        return fn

    return decorator
