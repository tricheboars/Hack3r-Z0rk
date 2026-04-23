"""Plugin-style command registry for the H@ck3r-Z0rk shell.

Commands register themselves with ``@register_command`` and the registry
handles dispatch, tab-completion, and help-text lookup. ``CommandContext``
is the single argument injected into every handler — it carries references
to all live game systems plus the per-call environment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # pragma: no cover — types only
    from hackerzork.systems.events import EventBus
    from hackerzork.systems.heat import HeatSystem
    from hackerzork.systems.network import NetworkSim
    from hackerzork.systems.state import GameState
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
    output: Any = None       # OutputBuffer (effects-aware writer)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class CommandHandler:
    name: str
    fn: CommandFn
    usage: str = ""
    help_text: str = ""
    category: str = "misc"
    aliases: list[str] = field(default_factory=list)

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
    ) -> CommandHandler:
        h = CommandHandler(
            name=name,
            fn=handler,
            usage=usage,
            help_text=help_text,
            category=category,
            aliases=list(aliases or []),
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
        h = self.get(name)
        if h is None:
            return f"bash: no help topic for '{name}'"
        sections = [f"NAME\n    {h.name} — {h.help_text or '(no description)'}"]
        if h.usage:
            sections.append(f"USAGE\n    {h.usage}")
        if h.aliases:
            sections.append(f"ALIASES\n    {', '.join(h.aliases)}")
        sections.append(f"CATEGORY\n    {h.category}")
        return "\n\n".join(sections)

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
        )
        return fn

    return decorator
