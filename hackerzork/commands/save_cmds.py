"""Save and load commands.

save [file]   — serialize all game state to JSON
load [file]   — restore from a save file
"""
from __future__ import annotations

from pathlib import Path

from hackerzork.engine.command_registry import CommandContext, register_command

_DEFAULT_SAVE = "/home/user/.hackerzork_save.json"
_REAL_SAVE_DIR = Path.home() / ".hackerzork"


def _real_path(vfs_path: str) -> Path:
    """Map a VFS save path to a real filesystem path for disk I/O."""
    name = Path(vfs_path).name or ".hackerzork_save.json"
    _REAL_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    return _REAL_SAVE_DIR / name


def _heat_level(ctx: CommandContext) -> float:
    return float(ctx.heat.level) if ctx.heat else 0.0


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------

@register_command(
    name="save",
    usage="save [filename]",
    help_text="Save game state to disk. Default: ~/.hackerzork_save.json",
    category="system",
)
def cmd_save(ctx: CommandContext, args: list[str]) -> str:
    if ctx.save_system is None:
        return "[save] Save system unavailable."

    vfs_path = args[0] if args else _DEFAULT_SAVE
    real_path = _real_path(vfs_path)

    data = ctx.save_system.collect(
        fs=ctx.fs,
        network=ctx.network,
        heat=ctx.heat,
        toolkit=ctx.toolkit,
        comms=ctx.comms,
        state=ctx.state,
        history=ctx.history,
        env=ctx.env,
    )

    ctx.save_system.write(data, real_path)

    summary = ctx.save_system.format_save_summary(data)
    heat = _heat_level(ctx)
    if heat >= 50.0:
        summary = ctx.save_system.corrupt_display(summary, heat_level=heat)

    return summary


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

@register_command(
    name="load",
    usage="load [filename]",
    help_text="Restore game state from a save file.",
    category="system",
)
def cmd_load(ctx: CommandContext, args: list[str]) -> str:
    if ctx.save_system is None:
        return "[load] Save system unavailable."

    vfs_path = args[0] if args else _DEFAULT_SAVE
    real_path = _real_path(vfs_path)

    try:
        data = ctx.save_system.read(real_path)
    except FileNotFoundError:
        return f"[load] No save file found at: {vfs_path}"
    except (ValueError, Exception) as e:
        return f"[load] Failed to read save: {e}"

    ctx.save_system.apply(
        data,
        fs=ctx.fs,
        network=ctx.network,
        heat=ctx.heat,
        toolkit=ctx.toolkit,
        comms=ctx.comms,
        state=ctx.state,
        history=ctx.history,
        env=ctx.env,
    )

    summary = ctx.save_system.format_load_summary(data)
    heat = _heat_level(ctx)
    if heat >= 50.0:
        summary = ctx.save_system.corrupt_load_display(summary, heat_level=heat)

    return summary
