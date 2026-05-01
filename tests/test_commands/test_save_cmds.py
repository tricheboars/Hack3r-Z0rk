"""Tests for hackerzork/commands/save_cmds.py."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import hackerzork.commands.save_cmds  # register commands
from hackerzork.engine.command_registry import CommandContext, DEFAULT_REGISTRY
from hackerzork.systems.save_load import SaveSystem


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _FS:
    def to_dict(self): return {"type": "dir", "name": "/", "children": {}}
    def from_dict(self, d): pass

class _Net:
    def to_dict(self): return {"discovered": [], "compromised": [], "nodes": {}}
    def load_state(self, d): pass

class _Heat:
    level = 10.0
    def to_dict(self): return {"level": 10.0, "decay_rate": 0.1, "current_threshold": "safe", "burn_count": 0, "stealth_modifiers": {}}
    def load_state(self, d): pass

class _Toolkit:
    def to_dict(self): return {"bandwidth_remaining_kb": 50000, "wallet_btc": 0.015, "shadow_enabled": False, "committed_kit": None, "kit_discount": False, "installed": {}}
    def load_state(self, d): pass

class _Comms:
    def to_dict(self): return {"player_handle": "anon", "story_flags": [], "channels": {}, "dm_threads": {}, "extra_contacts": {}}
    def load_state(self, d): pass

class _State:
    def to_dict(self): return {"flags": [], "chapter": 0, "timeline": []}
    def load_state(self, d): pass

class _History:
    def get_all(self): return ["ls", "pwd"]
    def add(self, cmd): pass


def _ctx(heat_level: float = 10.0) -> CommandContext:
    h = _Heat()
    h.level = heat_level
    return CommandContext(
        fs=_FS(),
        network=_Net(),
        heat=h,
        toolkit=_Toolkit(),
        comms=_Comms(),
        state=_State(),
        history=_History(),
        save_system=SaveSystem(),
        env={"USER": "user"},
    )


def _ctx_no_save() -> CommandContext:
    return CommandContext(save_system=None)


def _run(name: str, args: list[str], ctx: CommandContext) -> str:
    handler = DEFAULT_REGISTRY.get(name)
    assert handler is not None
    return handler(ctx, args)


# ---------------------------------------------------------------------------
# save — no save system
# ---------------------------------------------------------------------------

class TestSaveNoSystem:
    def test_returns_error(self):
        out = _run("save", [], _ctx_no_save())
        assert "unavailable" in out.lower()


# ---------------------------------------------------------------------------
# save — happy path
# ---------------------------------------------------------------------------

class TestSaveHappyPath:
    def test_save_returns_summary(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("hackerzork.commands.save_cmds._REAL_SAVE_DIR", Path(td)):
                ctx = _ctx()
                out = _run("save", [], ctx)
                assert "SAVED" in out or "saved" in out.lower()

    def test_save_writes_file(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("hackerzork.commands.save_cmds._REAL_SAVE_DIR", Path(td)):
                ctx = _ctx()
                _run("save", [], ctx)
                files = list(Path(td).iterdir())
                assert len(files) == 1
                data = json.loads(files[0].read_text())
                assert data["version"] == 1

    def test_save_output_is_string(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("hackerzork.commands.save_cmds._REAL_SAVE_DIR", Path(td)):
                out = _run("save", [], _ctx())
                assert isinstance(out, str)


# ---------------------------------------------------------------------------
# save — corruption at high heat
# ---------------------------------------------------------------------------

class TestSaveCorruption:
    def test_high_heat_triggers_corruption(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("hackerzork.commands.save_cmds._REAL_SAVE_DIR", Path(td)):
                ctx = _ctx(heat_level=90.0)
                out = _run("save", [], ctx)
                # Corruption adds SkyNet noise
                assert "sk_watchdog" in out or "INTEGRITY" in out or "WARNING" in out or "NOTICE" in out

    def test_low_heat_no_corruption(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("hackerzork.commands.save_cmds._REAL_SAVE_DIR", Path(td)):
                ctx = _ctx(heat_level=5.0)
                out = _run("save", [], ctx)
                assert "sk_watchdog" not in out


# ---------------------------------------------------------------------------
# load — no save system
# ---------------------------------------------------------------------------

class TestLoadNoSystem:
    def test_returns_error(self):
        out = _run("load", [], _ctx_no_save())
        assert "unavailable" in out.lower()


# ---------------------------------------------------------------------------
# load — missing file
# ---------------------------------------------------------------------------

class TestLoadMissingFile:
    def test_missing_file_returns_error(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("hackerzork.commands.save_cmds._REAL_SAVE_DIR", Path(td)):
                ctx = _ctx()
                out = _run("load", [], ctx)
                assert "No save file" in out or "not found" in out.lower()


# ---------------------------------------------------------------------------
# load — round trip
# ---------------------------------------------------------------------------

class TestLoadRoundTrip:
    def test_save_then_load(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("hackerzork.commands.save_cmds._REAL_SAVE_DIR", Path(td)):
                ctx = _ctx()
                _run("save", [], ctx)
                out = _run("load", [], ctx)
                assert "LOADED" in out or "loaded" in out.lower() or "restored" in out.lower()

    def test_load_summary_is_string(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("hackerzork.commands.save_cmds._REAL_SAVE_DIR", Path(td)):
                ctx = _ctx()
                _run("save", [], ctx)
                out = _run("load", [], ctx)
                assert isinstance(out, str)


# ---------------------------------------------------------------------------
# load — corruption at high heat
# ---------------------------------------------------------------------------

class TestLoadCorruption:
    def test_high_heat_load_corrupted(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("hackerzork.commands.save_cmds._REAL_SAVE_DIR", Path(td)):
                ctx = _ctx(heat_level=85.0)
                _run("save", [], ctx)
                out = _run("load", [], ctx)
                assert "SkyNet" in out or "watchdog" in out or "restore" in out or "NOTICE" in out
