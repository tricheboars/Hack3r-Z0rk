"""Tests for hackerzork/systems/state.py."""
from __future__ import annotations

import time

import pytest

from hackerzork.systems.state import (
    FLAG_SHADOW_UNLOCKED,
    FLAG_SURVEILLANCE_SEEN,
    GameState,
    StoryEvent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state() -> GameState:
    return GameState()


class MockEvents:
    def __init__(self):
        self.emitted: list[tuple[str, dict]] = []

    def emit(self, name: str, **kwargs):
        self.emitted.append((name, kwargs))


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_starts_with_no_flags(self):
        s = _state()
        assert len(s.flags) == 0

    def test_starts_at_chapter_zero(self):
        s = _state()
        assert s.chapter == 0

    def test_empty_timeline(self):
        s = _state()
        assert s.timeline == []


# ---------------------------------------------------------------------------
# Flag management
# ---------------------------------------------------------------------------

class TestFlags:
    def test_set_flag(self):
        s = _state()
        s.set_flag("test_flag")
        assert s.has_flag("test_flag")

    def test_has_flag_false_when_not_set(self):
        s = _state()
        assert not s.has_flag("missing")

    def test_clear_flag(self):
        s = _state()
        s.set_flag("f")
        s.clear_flag("f")
        assert not s.has_flag("f")

    def test_clear_nonexistent_no_crash(self):
        s = _state()
        s.clear_flag("nope")  # should not raise

    def test_set_flags_multiple(self):
        s = _state()
        s.set_flags("a", "b", "c")
        assert s.has_flag("a")
        assert s.has_flag("b")
        assert s.has_flag("c")

    def test_set_flag_idempotent(self):
        s = _state()
        s.set_flag("f")
        s.set_flag("f")
        assert len(s.flags) == 1

    def test_named_constants_work(self):
        s = _state()
        s.set_flag(FLAG_SHADOW_UNLOCKED)
        s.set_flag(FLAG_SURVEILLANCE_SEEN)
        assert s.has_flag(FLAG_SHADOW_UNLOCKED)
        assert s.has_flag(FLAG_SURVEILLANCE_SEEN)


# ---------------------------------------------------------------------------
# Events integration
# ---------------------------------------------------------------------------

class TestFlagEvents:
    def test_set_flag_emits_event(self):
        ev = MockEvents()
        s = GameState(events=ev)
        s.set_flag("new_flag")
        assert any(e[0] == "flag_set" for e in ev.emitted)

    def test_set_flag_event_carries_flag_name(self):
        ev = MockEvents()
        s = GameState(events=ev)
        s.set_flag("my_flag")
        evt = next(e for e in ev.emitted if e[0] == "flag_set")
        assert evt[1]["flag"] == "my_flag"

    def test_set_same_flag_twice_emits_once(self):
        ev = MockEvents()
        s = GameState(events=ev)
        s.set_flag("dup")
        s.set_flag("dup")
        flag_events = [e for e in ev.emitted if e[0] == "flag_set"]
        assert len(flag_events) == 1


# ---------------------------------------------------------------------------
# Story events / timeline
# ---------------------------------------------------------------------------

class TestTimeline:
    def test_fire_event_adds_to_timeline(self):
        s = _state()
        s.fire_event("test_event")
        assert len(s.timeline) == 1
        assert s.timeline[0].name == "test_event"

    def test_has_event(self):
        s = _state()
        s.fire_event("key_event")
        assert s.has_event("key_event")

    def test_has_event_false(self):
        s = _state()
        assert not s.has_event("unfired")

    def test_fire_multiple_events(self):
        s = _state()
        s.fire_event("a")
        s.fire_event("b")
        s.fire_event("a")
        assert len(s.events_named("a")) == 2
        assert len(s.events_named("b")) == 1

    def test_last_event(self):
        s = _state()
        s.fire_event("e", x=1)
        s.fire_event("e", x=2)
        last = s.last_event("e")
        assert last is not None
        assert last.metadata["x"] == 2

    def test_last_event_none_when_missing(self):
        s = _state()
        assert s.last_event("nope") is None

    def test_event_metadata(self):
        s = _state()
        s.fire_event("scan", target="10.0.0.1", ports=3)
        ev = s.timeline[0]
        assert ev.metadata["target"] == "10.0.0.1"
        assert ev.metadata["ports"] == 3

    def test_event_has_timestamp(self):
        s = _state()
        before = time.time()
        s.fire_event("ts_test")
        after = time.time()
        ts = s.timeline[0].timestamp_real
        assert before <= ts <= after

    def test_fire_event_emits_to_bus(self):
        ev = MockEvents()
        s = GameState(events=ev)
        s.fire_event("bus_event")
        assert any(e[0] == "story_event" for e in ev.emitted)


# ---------------------------------------------------------------------------
# Chapter advancement
# ---------------------------------------------------------------------------

class TestChapter:
    def test_advance_chapter(self):
        s = _state()
        result = s.advance_chapter()
        assert result == 1
        assert s.chapter == 1

    def test_advance_adds_timeline_event(self):
        s = _state()
        s.advance_chapter()
        assert s.has_event("chapter_1_start")

    def test_advance_twice(self):
        s = _state()
        s.advance_chapter()
        s.advance_chapter()
        assert s.chapter == 2
        assert s.has_event("chapter_2_start")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_has_flags(self):
        s = _state()
        s.set_flag("f1")
        s.set_flag("f2")
        d = s.to_dict()
        assert "f1" in d["flags"]
        assert "f2" in d["flags"]

    def test_to_dict_has_chapter(self):
        s = _state()
        s.advance_chapter()
        assert s.to_dict()["chapter"] == 1

    def test_to_dict_has_timeline(self):
        s = _state()
        s.fire_event("ev")
        d = s.to_dict()
        assert len(d["timeline"]) == 1
        assert d["timeline"][0]["name"] == "ev"

    def test_load_state_restores_flags(self):
        s = _state()
        s.load_state({"flags": ["x", "y"], "chapter": 0, "timeline": []})
        assert s.has_flag("x")
        assert s.has_flag("y")

    def test_load_state_restores_chapter(self):
        s = _state()
        s.load_state({"flags": [], "chapter": 3, "timeline": []})
        assert s.chapter == 3

    def test_load_state_restores_timeline(self):
        s = _state()
        s.load_state({
            "flags": [],
            "chapter": 0,
            "timeline": [{"name": "old_event", "timestamp_real": 0.0, "metadata": {}}],
        })
        assert s.has_event("old_event")

    def test_round_trip(self):
        s1 = _state()
        s1.set_flag("round_trip_flag")
        s1.advance_chapter()
        s1.fire_event("test_ev", val=42)

        s2 = _state()
        s2.load_state(s1.to_dict())

        assert s2.has_flag("round_trip_flag")
        assert s2.chapter == 1
        assert s2.has_event("test_ev")

    def test_load_state_empty_dict(self):
        s = _state()
        s.load_state({})  # should not raise
        assert s.chapter == 0

    def test_flags_sorted_in_to_dict(self):
        s = _state()
        s.set_flags("z_flag", "a_flag", "m_flag")
        flags = s.to_dict()["flags"]
        assert flags == sorted(flags)

    def test_summary_returns_string(self):
        s = _state()
        s.set_flag("f1")
        assert isinstance(s.summary(), str)
        assert "Chapter" in s.summary()
