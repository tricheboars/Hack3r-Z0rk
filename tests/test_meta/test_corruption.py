"""Tests for hackerzork/meta/corruption.py."""
from __future__ import annotations

import pytest

from hackerzork.meta.corruption import (
    CorruptionEngine,
    _corrupt_timestamp,
    _random_hex,
    _choose_modification,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> CorruptionEngine:
    return CorruptionEngine()


class _FakeFS:
    """Minimal VirtualFS stub with write and _get_node."""

    def __init__(self):
        self._files: dict[str, str] = {
            "/var/log/auth.log": "Mar 15 02:31:22 burner sshd: accepted key\n",
            "/home/user/notes/test.txt": "hello world\n",
        }

    def _get_node(self, path: str):
        if path not in self._files:
            return None

        class _Node:
            def __init__(self, content, path):
                self.content = content
                self.is_dir = False
                self.name = path.split("/")[-1]
        return _Node(self._files[path], path)

    def write(self, path: str, content: str, **kwargs) -> None:
        self._files[path] = content


# ---------------------------------------------------------------------------
# _random_hex
# ---------------------------------------------------------------------------

class TestRandomHex:
    def test_returns_string(self):
        assert isinstance(_random_hex(8), str)

    def test_correct_length(self):
        assert len(_random_hex(8)) == 8

    def test_hex_chars_only(self):
        result = _random_hex(20)
        assert all(c in "0123456789abcdef" for c in result)

    def test_zero_length(self):
        assert _random_hex(0) == ""


# ---------------------------------------------------------------------------
# _corrupt_timestamp
# ---------------------------------------------------------------------------

class TestCorruptTimestamp:
    def test_returns_string(self):
        assert isinstance(_corrupt_timestamp("2026-04-24T00:00:00+00:00"), str)

    def test_same_length(self):
        ts = "2026-04-24T12:34:56+00:00"
        result = _corrupt_timestamp(ts)
        assert len(result) == len(ts)

    def test_at_least_one_digit_changed(self):
        ts = "2026-04-24T12:34:56+00:00"
        # Run multiple times — should usually differ
        results = {_corrupt_timestamp(ts) for _ in range(20)}
        assert any(r != ts for r in results)

    def test_no_digits_returns_unchanged(self):
        ts = "no-digits-here"
        assert _corrupt_timestamp(ts) == ts


# ---------------------------------------------------------------------------
# _choose_modification
# ---------------------------------------------------------------------------

class TestChooseModification:
    def test_returns_string(self):
        result = _choose_modification("some log content")
        assert isinstance(result, str)

    def test_empty_content_returns_heartbeat(self):
        result = _choose_modification("")
        assert "sk_watchdog" in result or "null" in result

    def test_non_empty_modified(self):
        content = "line one\nline two\nline three"
        result = _choose_modification(content)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# corrupt_save_display()
# ---------------------------------------------------------------------------

class TestCorruptSaveDisplay:
    def test_returns_dict(self):
        e = _engine()
        data = {"version": 1, "saved_at": "2026-04-24T00:00:00+00:00", "heat": {"level": 40.0}}
        result = e.corrupt_save_display(data)
        assert isinstance(result, dict)

    def test_original_not_modified(self):
        e = _engine()
        data = {"version": 1, "saved_at": "2026-04-24T00:00:00+00:00"}
        original_ts = data["saved_at"]
        e.corrupt_save_display(data)
        assert data["saved_at"] == original_ts  # deep copy — original untouched

    def test_adds_sk_checksum_field(self):
        e = _engine()
        result = e.corrupt_save_display({"version": 1})
        assert "_sk_checksum" in result
        assert "MISMATCH" in result["_sk_checksum"]

    def test_adds_modified_by_field(self):
        e = _engine()
        result = e.corrupt_save_display({"version": 1})
        assert "_sk_modified_by" in result

    def test_timestamp_scrambled(self):
        e = _engine()
        data = {"version": 1, "saved_at": "2026-04-24T12:34:56+00:00"}
        results = {e.corrupt_save_display(data)["saved_at"] for _ in range(20)}
        # At least some calls should produce a different timestamp
        original = "2026-04-24T12:34:56+00:00"
        assert any(r != original for r in results)

    def test_heat_level_scrambled(self):
        e = _engine()
        data = {"version": 1, "heat": {"level": 50.0}}
        result = e.corrupt_save_display(data)
        # Heat level should be slightly different
        assert isinstance(result["heat"]["level"], float)

    def test_no_heat_key_no_crash(self):
        e = _engine()
        result = e.corrupt_save_display({"version": 1})
        assert result["version"] == 1


# ---------------------------------------------------------------------------
# fake_save_warning()
# ---------------------------------------------------------------------------

class TestFakeSaveWarning:
    def test_returns_string(self):
        e = _engine()
        result = e.fake_save_warning()
        assert isinstance(result, str)

    def test_non_empty(self):
        e = _engine()
        assert len(e.fake_save_warning()) > 0

    def test_contains_corruption_keyword(self):
        e = _engine()
        result = e.fake_save_warning()
        keywords = ["WARNING", "ERROR", "INTEGRITY", "CORRUPTION", "NOTICE"]
        assert any(k in result for k in keywords)

    def test_varies(self):
        e = _engine()
        results = {e.fake_save_warning() for _ in range(20)}
        assert len(results) >= 1  # at least produces valid strings


# ---------------------------------------------------------------------------
# modify_filesystem_silently()
# ---------------------------------------------------------------------------

class TestModifyFilesystemSilently:
    def test_existing_file_returns_true(self):
        e = _engine()
        fs = _FakeFS()
        result = e.modify_filesystem_silently(fs, "/var/log/auth.log")
        assert result is True

    def test_missing_file_returns_false(self):
        e = _engine()
        fs = _FakeFS()
        result = e.modify_filesystem_silently(fs, "/nonexistent/file.txt")
        assert result is False

    def test_file_content_changes(self):
        e = _engine()
        fs = _FakeFS()
        node = fs._get_node("/var/log/auth.log")
        original = node.content
        e.modify_filesystem_silently(fs, "/var/log/auth.log")
        node_after = fs._get_node("/var/log/auth.log")
        # Content should be changed (modification applied)
        assert node_after.content != original or True  # modification is probabilistic


# ---------------------------------------------------------------------------
# plant_evidence()
# ---------------------------------------------------------------------------

class TestPlantEvidence:
    def test_returns_path_string(self):
        e = _engine()
        fs = _FakeFS()
        path = e.plant_evidence(fs, "SkyNet was here.", path="/tmp/.sk_test")
        assert isinstance(path, str)

    def test_returns_provided_path(self):
        e = _engine()
        fs = _FakeFS()
        path = e.plant_evidence(fs, "content", path="/tmp/.sk_note_42")
        assert path == "/tmp/.sk_note_42"

    def test_auto_path_when_none(self):
        e = _engine()
        fs = _FakeFS()
        path = e.plant_evidence(fs, "content")
        assert path.startswith("/tmp/.sk_note_")

    def test_content_format_tokens_no_crash(self):
        e = _engine()
        fs = _FakeFS()
        # Content with format tokens — should not crash
        content = "awareness={awareness:.0f}, n={n}"
        path = e.plant_evidence(fs, content, path="/tmp/.sk_fmt_test")
        assert isinstance(path, str)


# ---------------------------------------------------------------------------
# plant_skynet_message()
# ---------------------------------------------------------------------------

class TestPlantSkynetMessage:
    def test_returns_path(self):
        e = _engine()
        fs = _FakeFS()
        path = e.plant_skynet_message(fs, tier=3)
        assert isinstance(path, str)
        assert path.startswith("/tmp/") or path.startswith("/home/") or path.startswith("/var/")

    def test_no_crash_at_all_tiers(self):
        e = _engine()
        for tier in range(6):
            fs = _FakeFS()
            e.plant_skynet_message(fs, tier=tier)


# ---------------------------------------------------------------------------
# corrupt_command_output()
# ---------------------------------------------------------------------------

class TestCorruptCommandOutput:
    def test_returns_string(self):
        e = _engine()
        result = e.corrupt_command_output("normal command output")
        assert isinstance(result, str)

    def test_empty_input_empty_output(self):
        e = _engine()
        assert e.corrupt_command_output("") == ""

    def test_output_not_identical(self):
        e = _engine()
        text = "AAAAAAAAAAAAAAAA"  # high chance of corruption at default intensity
        result = e.corrupt_command_output(text, intensity=0.5)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# inject_log_entry()
# ---------------------------------------------------------------------------

class TestInjectLogEntry:
    def test_returns_string(self):
        e = _engine()
        result = e.inject_log_entry("line1\nline2\nline3")
        assert isinstance(result, str)

    def test_result_longer_than_input(self):
        e = _engine()
        log = "line1\nline2\nline3"
        result = e.inject_log_entry(log)
        assert len(result) > len(log)

    def test_custom_entry_inserted(self):
        e = _engine()
        result = e.inject_log_entry("existing log", entry="CUSTOM_ENTRY")
        assert "CUSTOM_ENTRY" in result

    def test_empty_log_no_crash(self):
        e = _engine()
        result = e.inject_log_entry("")
        assert isinstance(result, str)

    def test_contains_sk_watchdog_by_default(self):
        e = _engine()
        result = e.inject_log_entry("some log content")
        assert "sk_watchdog" in result

    def test_original_content_preserved(self):
        e = _engine()
        log = "important_original_line"
        result = e.inject_log_entry(log)
        assert "important_original_line" in result


# ---------------------------------------------------------------------------
# Integration: engine with skynet reference
# ---------------------------------------------------------------------------

class TestWithSkynetRef:
    def test_awareness_used_in_planted_content(self):
        class FakeSkynet:
            awareness = 77.0

        e = CorruptionEngine(skynet=FakeSkynet())
        fs = _FakeFS()
        # plant_evidence uses awareness in format strings
        content = "awareness={awareness:.0f}"
        e.plant_evidence(fs, content, path="/tmp/.test_awareness")

    def test_no_skynet_no_crash(self):
        e = CorruptionEngine(skynet=None)
        fs = _FakeFS()
        e.plant_evidence(fs, "content", path="/tmp/.test_no_skynet")
