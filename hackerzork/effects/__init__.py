"""Effects system — global config shared by all effect modules."""
from __future__ import annotations

import io
from rich.console import Console


class EffectsConfig:
    """Global knob for all visual effects. Set speed_multiplier=0 for instant/test mode."""
    speed_multiplier: float = 1.0
    enabled: bool = True


config = EffectsConfig()

# Module-level console — swap out in tests with Console(file=io.StringIO())
_console = Console(highlight=False, markup=True)


def get_console() -> Console:
    return _console


def set_console(c: Console) -> None:
    global _console
    _console = c


def null_console() -> Console:
    """Return a Console that discards all output — useful for tests."""
    return Console(file=io.StringIO(), highlight=False, markup=True)
