"""Tests for hackerzork.systems.events."""
from __future__ import annotations

import asyncio
import time

import pytest

from hackerzork.systems.events import Event, EventBus


# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------


class TestEvent:
    def test_fields(self):
        e = Event(name="foo", data={"x": 1}, timestamp=42.0)
        assert e.name == "foo"
        assert e.data == {"x": 1}
        assert e.timestamp == 42.0

    def test_timestamp_defaults_to_now(self):
        before = time.time()
        e = Event(name="foo", data={})
        after = time.time()
        assert before <= e.timestamp <= after

    def test_to_dict_roundtrip(self):
        original = Event(name="scan_performed", data={"target": "10.0.0.1"}, timestamp=100.0)
        d = original.to_dict()
        restored = Event.from_dict(d)
        assert restored.name == original.name
        assert restored.data == original.data
        assert restored.timestamp == original.timestamp

    def test_to_dict_is_serializable(self):
        import json
        e = Event(name="foo", data={"k": "v"}, timestamp=1.0)
        json.dumps(e.to_dict())  # should not raise


# ---------------------------------------------------------------------------
# EventBus — registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_on_registers_handler(self):
        bus = EventBus()
        called = []
        bus.on("test", lambda e: called.append(e))
        bus.emit("test")
        assert len(called) == 1

    def test_on_same_handler_twice_deduplicates(self):
        bus = EventBus()
        called = []

        def h(e):
            called.append(e)

        bus.on("test", h)
        bus.on("test", h)
        bus.emit("test")
        assert len(called) == 1

    def test_off_unregisters_handler(self):
        bus = EventBus()
        called = []

        def h(e):
            called.append(e)

        bus.on("test", h)
        bus.off("test", h)
        bus.emit("test")
        assert called == []

    def test_off_missing_handler_is_silent(self):
        bus = EventBus()
        bus.off("nonexistent", lambda e: None)  # should not raise

    def test_multiple_handlers_all_called(self):
        bus = EventBus()
        results = []
        bus.on("x", lambda e: results.append("a"))
        bus.on("x", lambda e: results.append("b"))
        bus.emit("x")
        assert set(results) == {"a", "b"}


# ---------------------------------------------------------------------------
# EventBus — emit
# ---------------------------------------------------------------------------


class TestEmit:
    def test_emit_passes_event_to_handler(self):
        bus = EventBus()
        received = []
        bus.on("ping", lambda e: received.append(e))
        bus.emit("ping", val=42)
        assert len(received) == 1
        assert received[0].name == "ping"
        assert received[0].data == {"val": 42}

    def test_emit_with_no_handlers_is_silent(self):
        bus = EventBus()
        bus.emit("nothing_listening")  # should not raise

    def test_emit_only_triggers_matching_event(self):
        bus = EventBus()
        fired = []
        bus.on("a", lambda e: fired.append("a"))
        bus.on("b", lambda e: fired.append("b"))
        bus.emit("a")
        assert fired == ["a"]

    def test_handler_exception_does_not_crash_bus(self):
        bus = EventBus()
        results = []

        def bad(e):
            raise RuntimeError("boom")

        def good(e):
            results.append("ok")

        bus.on("x", bad)
        bus.on("x", good)
        bus.emit("x")  # should not raise
        assert results == ["ok"]

    def test_handler_exception_does_not_prevent_history(self):
        bus = EventBus()
        bus.on("x", lambda e: (_ for _ in ()).throw(ValueError("fail")))
        bus.emit("x", key="val")
        assert len(bus.history("x")) == 1

    def test_emit_records_event_data_correctly(self):
        bus = EventBus()
        bus.emit("scan_performed", target="10.0.0.1", stealth=True)
        events = bus.history("scan_performed")
        assert len(events) == 1
        assert events[0].data == {"target": "10.0.0.1", "stealth": True}


# ---------------------------------------------------------------------------
# EventBus — emit_async
# ---------------------------------------------------------------------------


class TestEmitAsync:
    def test_async_emit_calls_sync_handler(self):
        bus = EventBus()
        called = []
        bus.on("ev", lambda e: called.append(e))
        asyncio.run(bus.emit_async("ev", x=1))
        assert len(called) == 1

    def test_async_emit_calls_async_handler(self):
        bus = EventBus()
        called = []

        async def h(e):
            called.append(e)

        bus.on("ev", h)
        asyncio.run(bus.emit_async("ev"))
        assert len(called) == 1

    def test_async_handler_exception_does_not_crash_bus(self):
        bus = EventBus()
        results = []

        async def bad(e):
            raise RuntimeError("async boom")

        def good(e):
            results.append("ok")

        bus.on("ev", bad)
        bus.on("ev", good)
        asyncio.run(bus.emit_async("ev"))  # should not raise
        assert results == ["ok"]

    def test_async_emit_records_history(self):
        bus = EventBus()
        asyncio.run(bus.emit_async("fired", n=7))
        assert len(bus.history("fired")) == 1
        assert bus.history("fired")[0].data == {"n": 7}


# ---------------------------------------------------------------------------
# EventBus — history
# ---------------------------------------------------------------------------


class TestHistory:
    def test_history_all(self):
        bus = EventBus()
        bus.emit("a")
        bus.emit("b")
        bus.emit("a")
        assert len(bus.history()) == 3

    def test_history_filtered(self):
        bus = EventBus()
        bus.emit("a")
        bus.emit("b")
        bus.emit("a")
        assert len(bus.history("a")) == 2
        assert len(bus.history("b")) == 1

    def test_history_returns_copy(self):
        bus = EventBus()
        bus.emit("a")
        h = bus.history()
        h.clear()
        assert len(bus.history()) == 1  # original not mutated

    def test_history_empty_when_no_events(self):
        bus = EventBus()
        assert bus.history() == []
        assert bus.history("foo") == []

    def test_history_max_size_enforced(self):
        bus = EventBus(max_history=5)
        for _ in range(10):
            bus.emit("tick")
        assert len(bus.history()) == 5

    def test_history_keeps_most_recent_on_overflow(self):
        bus = EventBus(max_history=3)
        for i in range(5):
            bus.emit("n", i=i)
        kept = [e.data["i"] for e in bus.history()]
        assert kept == [2, 3, 4]

    def test_clear_history(self):
        bus = EventBus()
        bus.emit("a")
        bus.emit("b")
        bus.clear_history()
        assert bus.history() == []


# ---------------------------------------------------------------------------
# Standard event smoke tests (names from the spec table)
# ---------------------------------------------------------------------------


class TestStandardEvents:
    def test_command_entered(self):
        bus = EventBus()
        bus.emit("command_entered", cmd="ls", raw_input="ls -la")
        assert bus.history("command_entered")[0].data["cmd"] == "ls"

    def test_scan_performed(self):
        bus = EventBus()
        bus.emit("scan_performed", target="10.13.37.1", ports=[22, 80], stealth=False)
        d = bus.history("scan_performed")[0].data
        assert d["target"] == "10.13.37.1"
        assert 22 in d["ports"]

    def test_node_compromised(self):
        bus = EventBus()
        bus.emit("node_compromised", node_id="node_001", method="exploit")
        assert bus.history("node_compromised")[0].data["node_id"] == "node_001"

    def test_heat_threshold(self):
        bus = EventBus()
        fired = []
        bus.on("heat_threshold", lambda e: fired.append(e.data["threshold_name"]))
        bus.emit("heat_threshold", level=50.0, threshold_name="active_countermeasures")
        assert fired == ["active_countermeasures"]
