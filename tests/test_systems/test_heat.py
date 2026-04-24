"""Tests for hackerzork.systems.heat."""
from __future__ import annotations

import pytest

from hackerzork.systems.events import EventBus
from hackerzork.systems.heat import (
    HEAT_COSTS,
    HeatStatus,
    HeatSystem,
    _THRESHOLDS,
    _MIN_MODIFIER,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sys(with_bus: bool = False) -> tuple[HeatSystem, EventBus | None]:
    if with_bus:
        bus = EventBus()
        return HeatSystem(events=bus), bus
    return HeatSystem(), None


def _sys_with_bus() -> tuple[HeatSystem, EventBus]:
    hs, bus = _sys(with_bus=True)
    assert bus is not None
    return hs, bus


def _emitted(bus: EventBus, name: str) -> list[dict]:
    return [e.data for e in bus.history(name)]


# ---------------------------------------------------------------------------
# Heat accumulation
# ---------------------------------------------------------------------------


class TestHeatAccumulation:
    def test_starts_at_zero(self):
        hs, _ = _sys()
        assert hs.level == 0.0

    def test_add_heat_increases_level(self):
        hs, _ = _sys()
        hs.add_heat(10.0)
        assert hs.level == 10.0

    def test_add_heat_clamped_at_100(self):
        hs, _ = _sys()
        hs.add_heat(200.0)
        # burn fires at 100, resets to 0
        assert hs.level == 0.0

    def test_multiple_adds_accumulate(self):
        hs, _ = _sys()
        hs.add_heat(10.0)
        hs.add_heat(15.0)
        assert hs.level == 25.0

    def test_reduce_heat_decreases_level(self):
        hs, _ = _sys()
        hs.add_heat(30.0)
        hs.reduce_heat(10.0)
        assert hs.level == 20.0

    def test_reduce_heat_clamped_at_zero(self):
        hs, _ = _sys()
        hs.add_heat(5.0)
        hs.reduce_heat(50.0)
        assert hs.level == 0.0

    def test_add_zero_heat_no_change(self):
        hs, _ = _sys()
        hs.add_heat(0.0)
        assert hs.level == 0.0

    def test_fractional_heat(self):
        hs, _ = _sys()
        hs.add_heat(0.5)
        assert abs(hs.level - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# heat_changed events
# ---------------------------------------------------------------------------


class TestHeatChangedEvents:
    def test_add_heat_emits_heat_changed(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(5.0)
        events = _emitted(bus, "heat_changed")
        assert len(events) >= 1
        assert any(e["direction"] == "up" for e in events)

    def test_reduce_heat_emits_heat_changed_down(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(20.0)
        bus.clear_history()
        hs.reduce_heat(5.0)
        events = _emitted(bus, "heat_changed")
        assert any(e["direction"] == "down" for e in events)

    def test_heat_changed_carries_level(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(10.0)
        events = _emitted(bus, "heat_changed")
        up_event = next(e for e in events if e["direction"] == "up")
        assert up_event["level"] == 10.0

    def test_heat_changed_carries_source(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(5.0, source="nmap")
        events = _emitted(bus, "heat_changed")
        assert any(e.get("source") == "nmap" for e in events)


# ---------------------------------------------------------------------------
# Threshold transitions
# ---------------------------------------------------------------------------


class TestThresholds:
    def test_starts_safe(self):
        hs, _ = _sys()
        assert hs.current_threshold == "safe"
        assert hs.get_threshold_name() == "safe"

    def test_threshold_safe_below_25(self):
        hs, _ = _sys()
        hs.add_heat(24.0)
        assert hs.current_threshold == "safe"

    def test_threshold_monitored_at_25(self):
        hs, _ = _sys()
        hs.add_heat(25.0)
        assert hs.current_threshold == "monitored"

    def test_threshold_active_response_at_50(self):
        hs, _ = _sys()
        hs.add_heat(50.0)
        assert hs.current_threshold == "active_response"

    def test_threshold_hunted_at_75(self):
        hs, _ = _sys()
        hs.add_heat(75.0)
        assert hs.current_threshold == "hunted"

    def test_threshold_critical_at_90(self):
        hs, _ = _sys()
        hs.add_heat(90.0)
        assert hs.current_threshold == "critical"

    def test_threshold_event_emitted_on_crossing(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(25.0)
        crossings = _emitted(bus, "heat_threshold_crossed")
        assert len(crossings) == 1
        assert crossings[0]["from_threshold"] == "safe"
        assert crossings[0]["to_threshold"] == "monitored"

    def test_no_event_when_no_crossing(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(10.0)
        bus.clear_history()
        hs.add_heat(5.0)  # still in safe
        crossings = _emitted(bus, "heat_threshold_crossed")
        assert crossings == []

    def test_crossing_multiple_thresholds_emits_final(self):
        hs, bus = _sys_with_bus()
        # Jump from 0 to 80 — crosses safe→monitored→active_response→hunted
        hs.add_heat(80.0)
        crossings = _emitted(bus, "heat_threshold_crossed")
        assert len(crossings) == 1
        assert crossings[0]["to_threshold"] == "hunted"

    def test_threshold_decreases_on_reduce(self):
        hs, _ = _sys()
        hs.add_heat(30.0)  # monitored
        hs.reduce_heat(10.0)  # back to safe
        assert hs.current_threshold == "safe"

    def test_threshold_decrease_emits_event(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(30.0)   # safe → monitored
        bus.clear_history()
        hs.reduce_heat(10.0)  # monitored → safe
        crossings = _emitted(bus, "heat_threshold_crossed")
        assert len(crossings) == 1
        assert crossings[0]["from_threshold"] == "monitored"
        assert crossings[0]["to_threshold"] == "safe"


# ---------------------------------------------------------------------------
# Decay
# ---------------------------------------------------------------------------


class TestDecay:
    def test_tick_reduces_level(self):
        hs, _ = _sys()
        hs.add_heat(10.0)
        hs.tick(10.0)  # 10 game-minutes × 0.1/min = 1.0 decay
        assert abs(hs.level - 9.0) < 1e-9

    def test_tick_does_not_go_below_zero(self):
        hs, _ = _sys()
        hs.add_heat(0.5)
        hs.tick(100.0)
        assert hs.level == 0.0

    def test_tick_no_decay_at_zero(self):
        hs, bus = _sys_with_bus()
        hs.tick(100.0)
        assert _emitted(bus, "heat_changed") == []

    def test_tick_emits_heat_changed(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(10.0)
        bus.clear_history()
        hs.tick(10.0)
        events = _emitted(bus, "heat_changed")
        assert any(e["source"] == "decay" for e in events)

    def test_custom_decay_rate(self):
        hs, _ = _sys()
        hs.decay_rate = 0.5
        hs.add_heat(10.0)
        hs.tick(4.0)  # 4 min × 0.5 = 2.0 decay
        assert abs(hs.level - 8.0) < 1e-9

    def test_tick_can_cross_threshold_downward(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(26.0)  # in monitored
        bus.clear_history()
        hs.tick(20.0)  # 20 min × 0.1 = 2.0 decay → 24.0 → safe
        crossings = _emitted(bus, "heat_threshold_crossed")
        assert any(c["to_threshold"] == "safe" for c in crossings)


# ---------------------------------------------------------------------------
# Stealth modifiers
# ---------------------------------------------------------------------------


class TestStealthModifiers:
    def test_no_modifier_full_heat(self):
        hs, _ = _sys()
        hs.add_heat(10.0)
        assert hs.level == 10.0

    def test_vpn_halves_heat(self):
        hs, _ = _sys()
        hs.add_stealth_modifier("vpn", 0.5)
        hs.add_heat(10.0)
        assert abs(hs.level - 5.0) < 1e-9

    def test_tor_reduces_heat_70_percent(self):
        hs, _ = _sys()
        hs.add_stealth_modifier("tor", 0.3)
        hs.add_heat(10.0)
        assert abs(hs.level - 3.0) < 1e-9

    def test_modifiers_stack_multiplicatively(self):
        hs, _ = _sys()
        hs.add_stealth_modifier("vpn", 0.5)
        hs.add_stealth_modifier("tor", 0.5)
        hs.add_heat(10.0)
        # 10 × 0.5 × 0.5 = 2.5
        assert abs(hs.level - 2.5) < 1e-9

    def test_removing_modifier_restores_full_heat(self):
        hs, _ = _sys()
        hs.add_stealth_modifier("vpn", 0.5)
        hs.remove_stealth_modifier("vpn")
        hs.add_heat(10.0)
        assert hs.level == 10.0

    def test_modifier_clamped_to_min(self):
        hs, _ = _sys()
        # Stacking many deep reductions can't go below _MIN_MODIFIER
        for i in range(10):
            hs.add_stealth_modifier(f"m{i}", 0.1)
        effective = hs.effective_multiplier()
        assert effective >= _MIN_MODIFIER

    def test_has_stealth_modifier(self):
        hs, _ = _sys()
        assert not hs.has_stealth_modifier("vpn")
        hs.add_stealth_modifier("vpn", 0.5)
        assert hs.has_stealth_modifier("vpn")

    def test_effective_multiplier_no_mods(self):
        hs, _ = _sys()
        assert hs.effective_multiplier() == 1.0

    def test_effective_multiplier_with_mod(self):
        hs, _ = _sys()
        hs.add_stealth_modifier("vpn", 0.5)
        assert abs(hs.effective_multiplier() - 0.5) < 1e-9

    def test_modifier_clamps_out_of_range(self):
        hs, _ = _sys()
        hs.add_stealth_modifier("broken", 2.0)  # > 1.0
        assert hs._stealth_modifiers["broken"] <= 1.0
        hs.add_stealth_modifier("negative", -1.0)  # < 0.0
        assert hs._stealth_modifiers["negative"] >= 0.0


# ---------------------------------------------------------------------------
# Burn and reset
# ---------------------------------------------------------------------------


class TestBurnAndReset:
    def test_burn_triggers_at_100(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(100.0)
        burns = _emitted(bus, "identity_burned")
        assert len(burns) == 1

    def test_burn_resets_level_to_zero(self):
        hs, _ = _sys()
        hs.add_heat(100.0)
        assert hs.level == 0.0

    def test_burn_resets_threshold_to_safe(self):
        hs, _ = _sys()
        hs.add_heat(100.0)
        assert hs.current_threshold == "safe"

    def test_burn_emits_threshold_reset(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(100.0)
        crossings = _emitted(bus, "heat_threshold_crossed")
        assert any(
            c["from_threshold"] == "burned" and c["to_threshold"] == "safe"
            for c in crossings
        )

    def test_burn_count_increments(self):
        hs, _ = _sys()
        hs.add_heat(100.0)
        assert hs._burn_count == 1
        hs.add_heat(100.0)
        assert hs._burn_count == 2

    def test_burn_event_carries_count(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(100.0)
        burns = _emitted(bus, "identity_burned")
        assert burns[0]["burn_count"] == 1

    def test_incremental_add_to_100_also_burns(self):
        hs, bus = _sys_with_bus()
        hs.add_heat(95.0)
        bus.clear_history()
        hs.add_heat(10.0)  # pushes over 100
        assert hs.level == 0.0
        burns = _emitted(bus, "identity_burned")
        assert len(burns) == 1


# ---------------------------------------------------------------------------
# Event bus integration
# ---------------------------------------------------------------------------


class TestEventBusIntegration:
    def test_scan_performed_adds_heat(self):
        hs, bus = _sys_with_bus()
        bus.emit("scan_performed", target="10.0.0.1", stealth=False, port_count=10, open_ports=3)
        assert hs.level > 0.0

    def test_scan_performed_stealth_less_heat(self):
        hs_normal, bus_normal = _sys_with_bus()
        hs_stealth, bus_stealth = _sys_with_bus()

        bus_normal.emit("scan_performed", target="10.0.0.1", stealth=False, port_count=10, open_ports=3)
        bus_stealth.emit("scan_performed", target="10.0.0.1", stealth=True, port_count=10, open_ports=3)

        assert hs_stealth.level < hs_normal.level

    def test_stealth_scan_30_percent_less(self):
        hs_normal, bus_normal = _sys_with_bus()
        hs_stealth, bus_stealth = _sys_with_bus()

        bus_normal.emit("scan_performed", target="10.0.0.1", stealth=False, port_count=10, open_ports=3)
        bus_stealth.emit("scan_performed", target="10.0.0.1", stealth=True, port_count=10, open_ports=3)

        ratio = hs_stealth.level / hs_normal.level
        assert abs(ratio - 0.7) < 1e-9

    def test_ping_sent_adds_heat(self):
        hs, bus = _sys_with_bus()
        bus.emit("ping_sent", target="10.0.0.1")
        assert abs(hs.level - HEAT_COSTS["ping"]) < 1e-9

    def test_ssh_attempted_adds_heat(self):
        hs, bus = _sys_with_bus()
        bus.emit("ssh_attempted", target="10.0.0.1", port=22, user="root")
        assert abs(hs.level - HEAT_COSTS["ssh_connect"]) < 1e-9

    def test_http_request_adds_heat(self):
        hs, bus = _sys_with_bus()
        bus.emit("http_request_made", target="10.0.0.1", method="GET", path="/", port=80)
        assert hs.level > 0.0

    def test_nc_connection_adds_heat(self):
        hs, bus = _sys_with_bus()
        bus.emit("nc_connection", target="10.0.0.1", port=80, zero_io=True)
        assert hs.level > 0.0

    def test_multiple_events_accumulate(self):
        hs, bus = _sys_with_bus()
        bus.emit("ping_sent", target="10.0.0.1")
        bus.emit("scan_performed", target="10.0.0.1", stealth=False, port_count=5, open_ports=2)
        expected = HEAT_COSTS["ping"] + HEAT_COSTS["port_scan"]
        assert abs(hs.level - expected) < 1e-9


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    def test_returns_heat_status(self):
        hs, _ = _sys()
        status = hs.get_status()
        assert isinstance(status, HeatStatus)

    def test_status_level_accurate(self):
        hs, _ = _sys()
        hs.add_heat(30.0)
        status = hs.get_status()
        assert abs(status.level - 30.0) < 0.01

    def test_status_threshold_accurate(self):
        hs, _ = _sys()
        hs.add_heat(30.0)
        assert hs.get_status().threshold == "monitored"

    def test_status_has_threats_when_monitored(self):
        hs, _ = _sys()
        hs.add_heat(30.0)
        status = hs.get_status()
        assert len(status.active_threats) > 0

    def test_status_no_threats_when_safe(self):
        hs, _ = _sys()
        status = hs.get_status()
        assert status.active_threats == []

    def test_time_to_safe_calculation(self):
        hs, _ = _sys()
        hs.decay_rate = 1.0
        hs.add_heat(50.0)
        status = hs.get_status()
        # 50.0 / 1.0 = 50.0 game-minutes
        assert abs(status.time_to_safe - 50.0) < 0.1

    def test_time_to_safe_infinite_when_no_decay(self):
        hs, _ = _sys()
        hs.decay_rate = 0.0
        hs.add_heat(10.0)
        status = hs.get_status()
        assert status.time_to_safe == float("inf")

    def test_status_decay_rate_matches(self):
        hs, _ = _sys()
        hs.decay_rate = 0.25
        status = hs.get_status()
        assert status.decay_rate == 0.25


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_contains_keys(self):
        hs, _ = _sys()
        d = hs.to_dict()
        assert "level" in d
        assert "decay_rate" in d
        assert "current_threshold" in d
        assert "burn_count" in d
        assert "stealth_modifiers" in d

    def test_roundtrip_level(self):
        hs, _ = _sys()
        hs.add_heat(42.3)
        state = hs.to_dict()
        hs2 = HeatSystem()
        hs2.load_state(state)
        assert abs(hs2.level - 42.3) < 1e-9

    def test_roundtrip_stealth_modifiers(self):
        hs, _ = _sys()
        hs.add_stealth_modifier("vpn", 0.5)
        state = hs.to_dict()
        hs2 = HeatSystem()
        hs2.load_state(state)
        assert hs2.has_stealth_modifier("vpn")
        assert abs(hs2._stealth_modifiers["vpn"] - 0.5) < 1e-9

    def test_roundtrip_burn_count(self):
        hs, _ = _sys()
        hs.add_heat(100.0)  # triggers burn → count = 1
        state = hs.to_dict()
        hs2 = HeatSystem()
        hs2.load_state(state)
        assert hs2._burn_count == 1

    def test_roundtrip_threshold(self):
        hs, _ = _sys()
        hs.add_heat(60.0)
        state = hs.to_dict()
        hs2 = HeatSystem()
        hs2.load_state(state)
        assert hs2.current_threshold == "active_response"
