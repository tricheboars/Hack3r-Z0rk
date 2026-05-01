"""Tests for hackerzork/systems/save_load.py."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hackerzork.systems.save_load import SaveSystem, _count_nodes, _scramble_one_char


# ---------------------------------------------------------------------------
# Minimal stubs for all systems
# ---------------------------------------------------------------------------

class _FS:
    def to_dict(self): return {"type": "dir", "name": "/", "children": {"a": {"type": "file", "name": "a", "children": {}}}}
    def from_dict(self, d): self._restored = d

class _Network:
    def to_dict(self): return {"discovered": ["10.0.0.1"], "compromised": [], "nodes": {}}
    def load_state(self, d): self._restored = d

class _Heat:
    level = 35.0
    def to_dict(self): return {"level": 35.0, "decay_rate": 0.1, "current_threshold": "safe", "burn_count": 0, "stealth_modifiers": {}}
    def load_state(self, d): self._restored = d

class _Toolkit:
    def to_dict(self): return {"bandwidth_remaining_kb": 50000, "wallet_btc": 0.015, "shadow_enabled": False, "committed_kit": None, "kit_discount": False, "installed": {}}
    def load_state(self, d): self._restored = d

class _Comms:
    def to_dict(self): return {"player_handle": "anon", "story_flags": [], "channels": {}, "dm_threads": {}, "extra_contacts": {}}
    def load_state(self, d): self._restored = d

class _State:
    def to_dict(self): return {"flags": ["f1", "f2"], "chapter": 1, "timeline": []}
    def load_state(self, d): self._restored = d

class _History:
    def __init__(self): self._added: list[str] = []
    def get_all(self): return ["cmd1", "cmd2"]
    def add(self, cmd): self._added.append(cmd)


def _save() -> SaveSystem:
    return SaveSystem()


def _all_systems():
    return dict(
        fs=_FS(), network=_Network(), heat=_Heat(),
        toolkit=_Toolkit(), comms=_Comms(), state=_State(),
        history=_History(), env={"USER": "test"},
    )


# ---------------------------------------------------------------------------
# collect()
# ---------------------------------------------------------------------------

class TestCollect:
    def test_version_present(self):
        s = _save()
        d = s.collect(**_all_systems())
        assert d["version"] == 1

    def test_saved_at_present(self):
        s = _save()
        d = s.collect(**_all_systems())
        assert "saved_at" in d
        assert "T" in d["saved_at"]  # ISO 8601

    def test_all_sections_present(self):
        s = _save()
        d = s.collect(**_all_systems())
        for key in ("fs", "network", "heat", "toolkit", "comms", "state", "history", "env"):
            assert key in d

    def test_fs_section(self):
        s = _save()
        d = s.collect(**_all_systems())
        assert d["fs"]["type"] == "dir"

    def test_history_section(self):
        s = _save()
        d = s.collect(**_all_systems())
        assert "cmd1" in d["history"]

    def test_env_section(self):
        s = _save()
        d = s.collect(**_all_systems())
        assert d["env"]["USER"] == "test"

    def test_flags_in_state(self):
        s = _save()
        d = s.collect(**_all_systems())
        assert "f1" in d["state"]["flags"]

    def test_collect_with_none_systems_no_crash(self):
        s = _save()
        d = s.collect()  # all None
        assert d["version"] == 1
        assert d["fs"] == {}


# ---------------------------------------------------------------------------
# apply()
# ---------------------------------------------------------------------------

class TestApply:
    def test_fs_restored(self):
        s = _save()
        systems = _all_systems()
        data = s.collect(**systems)
        fs = _FS()
        s.apply(data, fs=fs)
        assert hasattr(fs, "_restored")

    def test_heat_restored(self):
        s = _save()
        systems = _all_systems()
        data = s.collect(**systems)
        heat = _Heat()
        s.apply(data, heat=heat)
        assert hasattr(heat, "_restored")
        assert heat._restored["level"] == pytest.approx(35.0)

    def test_history_restored(self):
        s = _save()
        systems = _all_systems()
        data = s.collect(**systems)
        history = _History()
        s.apply(data, history=history)
        assert "cmd1" in history._added

    def test_env_restored(self):
        s = _save()
        systems = _all_systems()
        data = s.collect(**systems)
        env: dict = {}
        s.apply(data, env=env)
        assert env["USER"] == "test"

    def test_apply_missing_key_no_crash(self):
        s = _save()
        data = {"version": 1, "saved_at": "now"}  # missing most keys
        s.apply(data, fs=_FS(), heat=_Heat())  # should not raise

    def test_apply_with_none_systems_no_crash(self):
        s = _save()
        systems = _all_systems()
        data = s.collect(**systems)
        s.apply(data)  # all None systems — should not raise

    def test_round_trip_collect_apply(self):
        s = _save()
        systems = _all_systems()
        data = s.collect(**systems)
        state = _State()
        s.apply(data, state=state)
        assert hasattr(state, "_restored")
        assert "f1" in state._restored["flags"]


# ---------------------------------------------------------------------------
# write() / read()
# ---------------------------------------------------------------------------

class TestDiskIO:
    def test_write_creates_file(self):
        s = _save()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "save.json"
            systems = _all_systems()
            data = s.collect(**systems)
            s.write(data, p)
            assert p.exists()

    def test_write_produces_valid_json(self):
        s = _save()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "save.json"
            data = s.collect(**_all_systems())
            s.write(data, p)
            raw = json.loads(p.read_text())
            assert raw["version"] == 1

    def test_read_returns_dict(self):
        s = _save()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "save.json"
            data = s.collect(**_all_systems())
            s.write(data, p)
            loaded = s.read(p)
            assert isinstance(loaded, dict)
            assert loaded["version"] == 1

    def test_read_missing_file_raises(self):
        s = _save()
        with pytest.raises(FileNotFoundError):
            s.read("/nonexistent/path/save.json")

    def test_read_wrong_version_raises(self):
        s = _save()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text(json.dumps({"version": 99, "fs": {}}))
            with pytest.raises(ValueError):
                s.read(p)

    def test_write_creates_parent_dirs(self):
        s = _save()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "subdir" / "nested" / "save.json"
            data = s.collect(**_all_systems())
            s.write(data, p)
            assert p.exists()

    def test_full_round_trip_disk(self):
        s = _save()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "save.json"
            data = s.collect(**_all_systems())
            s.write(data, p)
            loaded = s.read(p)
            assert loaded["env"]["USER"] == "test"
            assert "f1" in loaded["state"]["flags"]


# ---------------------------------------------------------------------------
# format_save_summary()
# ---------------------------------------------------------------------------

class TestFormatSaveSummary:
    def test_returns_string(self):
        s = _save()
        data = s.collect(**_all_systems())
        out = s.format_save_summary(data)
        assert isinstance(out, str)

    def test_contains_saved_marker(self):
        s = _save()
        data = s.collect(**_all_systems())
        out = s.format_save_summary(data)
        assert "SAVED" in out or "saved" in out.lower()

    def test_shows_heat_level(self):
        s = _save()
        data = s.collect(**_all_systems())
        out = s.format_save_summary(data)
        assert "35.0" in out

    def test_shows_history_count(self):
        s = _save()
        data = s.collect(**_all_systems())
        out = s.format_save_summary(data)
        assert "2" in out  # 2 history entries

    def test_shows_flag_count(self):
        s = _save()
        data = s.collect(**_all_systems())
        out = s.format_save_summary(data)
        assert "2" in out  # 2 flags


# ---------------------------------------------------------------------------
# format_load_summary()
# ---------------------------------------------------------------------------

class TestFormatLoadSummary:
    def test_returns_string(self):
        s = _save()
        data = s.collect(**_all_systems())
        out = s.format_load_summary(data)
        assert isinstance(out, str)

    def test_contains_loaded_marker(self):
        s = _save()
        data = s.collect(**_all_systems())
        out = s.format_load_summary(data)
        assert "LOADED" in out or "loaded" in out.lower() or "restored" in out.lower()


# ---------------------------------------------------------------------------
# corrupt_display() — display-only horror
# ---------------------------------------------------------------------------

class TestCorruptDisplay:
    def test_no_corruption_at_low_heat(self):
        s = _save()
        summary = "clean summary line"
        out = s.corrupt_display(summary, heat_level=0.0)
        assert out == summary  # unchanged below 25%

    def test_corruption_at_high_heat(self):
        s = _save()
        summary = "Filesystem OK (247 nodes)"
        out = s.corrupt_display(summary, heat_level=100.0)
        assert out != summary  # must be different

    def test_corruption_contains_notice(self):
        s = _save()
        out = s.corrupt_display("summary text here", heat_level=100.0)
        assert "sk_watchdog" in out or "INTEGRITY" in out or "WARNING" in out or "NOTICE" in out

    def test_corruption_preserves_original_text(self):
        # The real content should still be mostly there
        s = _save()
        original = "Filesystem OK"
        out = s.corrupt_display(original, heat_level=100.0)
        # After adding noise, original line should appear somewhere
        assert any(word in out for word in ["Filesystem", "OK", "ok"])

    def test_corruption_is_string(self):
        s = _save()
        out = s.corrupt_display("test", heat_level=80.0)
        assert isinstance(out, str)

    def test_medium_heat_some_corruption(self):
        s = _save()
        # At 50% heat (intensity = 0.5) corruption kicks in
        out = s.corrupt_display("test line", heat_level=50.0)
        assert isinstance(out, str)

    def test_corrupt_load_display_no_crash(self):
        s = _save()
        out = s.corrupt_load_display("load summary", heat_level=80.0)
        assert isinstance(out, str)

    def test_corrupt_load_low_heat_unchanged(self):
        s = _save()
        summary = "clean load summary"
        out = s.corrupt_load_display(summary, heat_level=0.0)
        assert out == summary

    def test_corrupt_load_high_heat_modified(self):
        s = _save()
        out = s.corrupt_load_display("summary line", heat_level=100.0)
        assert "SkyNet" in out or "watchdog" in out or "restore" in out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestCountNodes:
    def test_single_node(self):
        assert _count_nodes({"type": "file", "name": "x", "children": {}}) == 1

    def test_nested(self):
        tree = {"type": "dir", "name": "/", "children": {
            "a": {"type": "file", "name": "a", "children": {}},
            "b": {"type": "file", "name": "b", "children": {}},
        }}
        assert _count_nodes(tree) == 3

    def test_empty_dict(self):
        assert _count_nodes({}) == 1  # the dict itself counts as 1


class TestScrambleChar:
    def test_changes_a_char(self):
        # Input has known lookalike chars
        result = _scramble_one_char("hello0world")
        # Either changed something or returned as-is (if no match)
        assert isinstance(result, str)

    def test_no_lookalikes_returns_unchanged(self):
        s = "xyzXYZ"  # none of the lookalike chars
        result = _scramble_one_char(s)
        assert result == s

    def test_scrambles_known_char(self):
        # "O" → "0" or "0" → "O"
        seen_change = False
        for _ in range(20):
            r = _scramble_one_char("O")
            if r != "O":
                seen_change = True
                break
        assert seen_change
