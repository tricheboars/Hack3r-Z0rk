"""Save / load system — serializes all game state to JSON.

Also a meta-horror vector: the save DISPLAY can appear corrupted when SkyNet
awareness is high. The actual file on disk is always clean JSON. Only the
string shown to the player is tampered with.
"""
from __future__ import annotations

import json
import random
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAVE_VERSION = 1
DEFAULT_SAVE_NAME = ".hackerzork_save.json"

# ---------------------------------------------------------------------------
# Corruption theatre strings (display only — never written to disk)
# ---------------------------------------------------------------------------

_CORRUPTION_NOTICES = [
    "[!] sk_watchdog.service intercepted write to save buffer",
    "[!] INTEGRITY CHECK FAILED — unexpected PID 894 write",
    "[!] WARNING: save state modified by external process",
    "[!] sk_identify has flagged this session for monitoring",
    "[!] HASH MISMATCH — 1 field altered by sk_persistent_module_v3",
    "[!] NOTICE: this save was observed. it has been noted.",
]

_CORRUPTION_SUFFIXES = [
    "  # ← sk_watchdog",
    "  # ← not you",
    "  # ← modified",
    "  # ← observed",
]


# ---------------------------------------------------------------------------
# SaveSystem
# ---------------------------------------------------------------------------

class SaveSystem:
    """Collect → serialize → write → read → apply all game system state."""

    def __init__(self, save_dir: Path | None = None) -> None:
        self._save_dir = save_dir

    # ------------------------------------------------------------------
    # Collect all system state into a dict
    # ------------------------------------------------------------------

    def collect(
        self,
        *,
        fs: Any = None,
        network: Any = None,
        heat: Any = None,
        toolkit: Any = None,
        comms: Any = None,
        state: Any = None,
        history: Any = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
        return {
            "version": SAVE_VERSION,
            "saved_at": now,
            "fs":      fs.to_dict()          if fs      else {},
            "network": network.to_dict()     if network else {},
            "heat":    heat.to_dict()        if heat    else {},
            "toolkit": toolkit.to_dict()     if toolkit else {},
            "comms":   comms.to_dict()       if comms   else {},
            "state":   state.to_dict()       if state   else {},
            "history": history.get_entries() if history else [],
            "env":     dict(env)             if env     else {},
        }

    # ------------------------------------------------------------------
    # Apply a save dict back to live systems
    # ------------------------------------------------------------------

    def apply(
        self,
        data: dict,
        *,
        fs: Any = None,
        network: Any = None,
        heat: Any = None,
        toolkit: Any = None,
        comms: Any = None,
        state: Any = None,
        history: Any = None,
        env: dict[str, str] | None = None,
    ) -> None:
        if fs      and "fs"      in data: fs.from_dict(data["fs"])
        if network and "network" in data: network.load_state(data["network"])
        if heat    and "heat"    in data: heat.load_state(data["heat"])
        if toolkit and "toolkit" in data: toolkit.load_state(data["toolkit"])
        if comms   and "comms"   in data: comms.load_state(data["comms"])
        if state   and "state"   in data: state.load_state(data["state"])
        if history and "history" in data:
            for cmd in data["history"]:
                history.add(cmd)
        if env is not None and "env" in data:
            env.update(data["env"])

    # ------------------------------------------------------------------
    # Disk I/O
    # ------------------------------------------------------------------

    def write(self, data: dict, path: Path | str) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return p

    def read(self, path: Path | str) -> dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Save file not found: {p}")
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if data.get("version", 0) != SAVE_VERSION:
            raise ValueError(
                f"Incompatible save version: {data.get('version')} (expected {SAVE_VERSION})"
            )
        return data

    # ------------------------------------------------------------------
    # Display formatting
    # ------------------------------------------------------------------

    def format_save_summary(self, data: dict) -> str:
        fs_nodes    = _count_nodes(data.get("fs", {}))
        net         = data.get("network", {})
        heat_level  = data.get("heat", {}).get("level", 0.0)
        pkg_count   = len(data.get("toolkit", {}).get("installed", {}))
        flag_count  = len(data.get("state", {}).get("flags", []))
        hist_count  = len(data.get("history", []))
        joined      = sum(
            1 for c in data.get("comms", {}).get("channels", {}).values()
            if c.get("joined")
        )
        saved_at    = data.get("saved_at", "unknown")
        compromised = len(net.get("compromised", []))
        discovered  = len(net.get("discovered", []))

        lines = [
            "[bold green][GAME SAVED][/bold green]",
            f"  Filesystem ......... [green]OK[/green] ({fs_nodes} nodes)",
            f"  Network ............ [green]OK[/green] ({discovered} discovered, {compromised} compromised)",
            f"  Heat level ......... [green]OK[/green] ({heat_level:.1f})",
            f"  Toolkit ............ [green]OK[/green] ({pkg_count} packages installed)",
            f"  Comms .............. [green]OK[/green] ({joined} channels joined)",
            f"  Story state ........ [green]OK[/green] ({flag_count} flags)",
            f"  History ............ [green]OK[/green] ({hist_count} entries)",
            f"  Saved at: {saved_at}",
        ]
        return "\n".join(lines)

    def format_load_summary(self, data: dict) -> str:
        saved_at = data.get("saved_at", "unknown")
        flag_count = len(data.get("state", {}).get("flags", []))
        hist_count = len(data.get("history", []))
        lines = [
            "[bold green][GAME LOADED][/bold green]",
            f"  Filesystem ......... [green]restored[/green]",
            f"  Network ............ [green]restored[/green]",
            f"  Heat level ......... [green]restored[/green]",
            f"  Toolkit ............ [green]restored[/green]",
            f"  Comms .............. [green]restored[/green]",
            f"  Story state ........ [green]restored[/green] ({flag_count} flags)",
            f"  History ............ [green]restored[/green] ({hist_count} entries)",
            f"  Save was written:  {saved_at}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Corruption theatre — display only, never touches the save file
    # ------------------------------------------------------------------

    def corrupt_display(self, summary: str, heat_level: float = 0.0) -> str:
        """Return a theatrically corrupted version of a save summary.

        The actual data on disk is untouched. This is pure display horror.
        Intensity scales with heat_level (0–100).
        """
        intensity = min(1.0, heat_level / 100.0)
        if intensity < 0.25:
            return summary  # not hot enough to corrupt

        lines = summary.splitlines()
        out: list[str] = []

        # Inject a corruption notice near the top
        notice = random.choice(_CORRUPTION_NOTICES)
        out.append(f"[dim red]{notice}[/dim red]")

        for line in lines:
            corrupted = line

            # At medium intensity: occasional suffix tag
            if intensity >= 0.5 and random.random() < 0.25:
                corrupted = line + random.choice(_CORRUPTION_SUFFIXES)

            # At high intensity: scramble a digit or char in the line
            if intensity >= 0.75 and random.random() < 0.35:
                corrupted = _scramble_one_char(corrupted)

            out.append(corrupted)

        # At high intensity: inject extra horror line
        if intensity >= 0.75:
            out.append("[dim red][!] sk_watchdog.service has observed this save. it has been noted.[/dim red]")

        return "\n".join(out)

    def corrupt_load_display(self, summary: str, heat_level: float = 0.0) -> str:
        """Corrupted load summary — SkyNet comments on the player's return."""
        intensity = min(1.0, heat_level / 100.0)
        if intensity < 0.5:
            return summary

        lines = summary.splitlines()
        out: list[str] = []

        out.append("[dim red][!] NOTICE: sk_watchdog observed this restore operation[/dim red]")

        inject_idx = max(1, len(lines) // 2)
        for i, line in enumerate(lines):
            out.append(line)
            if i == inject_idx:
                out.append("[dim red][SkyNet]: I see you're trying to restore. Hello again.[/dim red]")

        if intensity >= 0.75:
            out.append("[dim red][!] 2 entries removed from history during restore[/dim red]")

        return "\n".join(out)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_nodes(fs_dict: dict, _seen: set | None = None) -> int:
    """Recursively count filesystem nodes in a serialized VFS dict."""
    if _seen is None:
        _seen = set()
    node_id = id(fs_dict)
    if node_id in _seen:
        return 0
    _seen.add(node_id)
    count = 1
    for child in fs_dict.get("children", {}).values():
        count += _count_nodes(child, _seen)
    return count


def _scramble_one_char(s: str) -> str:
    """Replace one random character in a string with a lookalike."""
    _LOOKALIKES = {
        "O": "0", "0": "O", "l": "1", "1": "l",
        "a": "α", "e": "ε", "o": "ο", "i": "ι",
        "S": "5", "5": "S",
    }
    indices = [i for i, c in enumerate(s) if c in _LOOKALIKES]
    if not indices:
        return s
    idx = random.choice(indices)
    chars = list(s)
    chars[idx] = _LOOKALIKES[chars[idx]]
    return "".join(chars)
