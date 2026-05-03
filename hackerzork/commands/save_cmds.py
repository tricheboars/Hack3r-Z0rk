"""Save and load commands.

save [name]   — serialize all game state to a named slot
load [name]   — restore from a named save slot
saves         — list all save slots for the current player
"""
from __future__ import annotations

import re
from pathlib import Path

from hackerzork.engine.command_registry import CommandContext, register_command

_BASE_SAVE_DIR = Path.home() / ".hackerzork" / "saves"
_REAL_SAVE_DIR = _BASE_SAVE_DIR  # patched in tests

_SAFE_NAME = re.compile(r'^[A-Za-z0-9_\-\.]{1,32}$')


def _player_dir(ctx: CommandContext) -> Path:
    """Return the save directory for the current player session."""
    player_id = (ctx.env or {}).get("HZ_PLAYER_ID", "local")
    # Sanitise — player_id is set by the client, don't trust it for paths
    safe_id = re.sub(r'[^A-Za-z0-9_\-]', '', player_id)[:32] or "local"
    d = _REAL_SAVE_DIR / safe_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_path(ctx: CommandContext, name: str) -> Path:
    """Map a slot name to a real filesystem path."""
    if not name.endswith(".json"):
        name = name + ".json"
    return _player_dir(ctx) / name


def _heat_level(ctx: CommandContext) -> float:
    return float(ctx.heat.level) if ctx.heat else 0.0


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------

@register_command(
    name="save",
    usage="save [name]",
    help_text="Save game to a named slot (default: quicksave). Names: letters, numbers, _ - only.",
    category="system",
)
def cmd_save(ctx: CommandContext, args: list[str]) -> str:
    if ctx.save_system is None:
        return "[save] Save system unavailable."

    if len(args) > 1:
        joined = " ".join(args)
        return (
            f"[save] Invalid save name: '{joined}'\n"
            "       Save names cannot contain spaces.\n"
            "       Names must be 1–32 characters: letters, numbers, _ or -\n"
            "       Example: save chapter1"
        )

    name = args[0] if args else "quicksave"

    if not _SAFE_NAME.match(name):
        return (
            f"[save] Invalid save name: '{name}'\n"
            "       Names must be 1–32 characters: letters, numbers, _ or -\n"
            "       Example: save chapter1"
        )

    real_path = _save_path(ctx, name)

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
    # Inject the save slot name into the summary
    summary = summary.replace("SAVED", f"SAVED  [{name}]", 1)

    heat = _heat_level(ctx)
    if heat >= 50.0:
        summary = ctx.save_system.corrupt_display(summary, heat_level=heat)

    return summary


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

@register_command(
    name="load",
    usage="load [name]",
    help_text="Restore game from a named save slot (default: quicksave). Use 'saves' to list slots.",
    category="system",
)
def cmd_load(ctx: CommandContext, args: list[str]) -> str:
    if ctx.save_system is None:
        return "[load] Save system unavailable."

    if len(args) > 1:
        joined = " ".join(args)
        return (
            f"[load] Invalid save name: '{joined}'\n"
            "       Save names cannot contain spaces.\n"
            "       Use 'saves' to list available slots."
        )

    name = args[0] if args else "quicksave"

    if not _SAFE_NAME.match(name):
        return (
            f"[load] Invalid save name: '{name}'\n"
            "       Use 'saves' to list available slots."
        )

    real_path = _save_path(ctx, name)

    try:
        data = ctx.save_system.read(real_path)
    except FileNotFoundError:
        # Helpful: list what slots exist
        player_dir = _player_dir(ctx)
        slots = _list_slots(player_dir)
        if slots:
            slot_list = "  " + "\n  ".join(slots)
            return (
                f"[load] No save named '{name}'\n"
                f"Available saves:\n{slot_list}"
            )
        return (
            f"[load] No save named '{name}' — and no saves exist yet.\n"
            "       Use 'save <name>' to create one."
        )
    except (ValueError, Exception) as e:
        return f"[load] Failed to read save '{name}': {e}"

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
    summary = summary.replace("LOADED", f"LOADED  [{name}]", 1)
    summary = summary.replace("RESTORED", f"RESTORED  [{name}]", 1)

    heat = _heat_level(ctx)
    if heat >= 50.0:
        summary = ctx.save_system.corrupt_load_display(summary, heat_level=heat)

    return summary


# ---------------------------------------------------------------------------
# saves
# ---------------------------------------------------------------------------

def _list_slots(player_dir: Path) -> list[str]:
    """Return sorted list of save slot names for a player directory."""
    if not player_dir.exists():
        return []
    import json as _json
    import os as _os

    slots = []
    for f in sorted(player_dir.iterdir()):
        if f.suffix != ".json":
            continue
        name = f.stem
        try:
            stat = f.stat()
            mtime = _os.path.getmtime(f)
            import datetime as _dt
            ts = _dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            size_kb = stat.st_size // 1024
            # Try to read heat level quickly
            try:
                raw = _json.loads(f.read_text())
                heat = raw.get("heat", {}).get("level", 0.0)
                flags = len(raw.get("state", {}).get("flags", []))
                slots.append(f"{name:<20}  {ts}  heat:{heat:4.1f}  flags:{flags}")
            except Exception:
                slots.append(f"{name:<20}  {ts}  ({size_kb}kb)")
        except OSError:
            slots.append(name)
    return slots


@register_command(
    name="saves",
    usage="saves",
    help_text="List all save slots for your current session.",
    category="system",
)
def cmd_saves(ctx: CommandContext, args: list[str]) -> str:
    player_dir = _player_dir(ctx)
    slots = _list_slots(player_dir)
    if not slots:
        return (
            "No saves found.\n"
            "  save <name>   — create a save slot\n"
            "  load <name>   — restore from a slot"
        )

    player_id = (ctx.env or {}).get("HZ_PLAYER_ID", "local")
    lines = [
        f"Save slots  [player: {player_id[:8]}...]",
        "",
        f"  {'SLOT':<20}  {'SAVED AT':<16}  INFO",
        "  " + "─" * 60,
    ]
    for slot in slots:
        lines.append(f"  {slot}")
    lines.append("")
    lines.append("  load <name>  to restore a slot")
    return "\n".join(lines)
