"""Tests for hackerzork/meta/skynet.py."""
from __future__ import annotations

import pytest

from hackerzork.meta.skynet import (
    SkyNetEngine,
    _awareness_cost,
    _tier,
    _TIER_THRESHOLDS,
    _TIER_INTERVENTIONS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine(enabled: bool = True) -> SkyNetEngine:
    return SkyNetEngine(enabled=enabled)


class MockFourthWall:
    def __init__(self):
        self.ran: list[str] = []

    async def run(self, effect: str, awareness: float = 0.0, tier: int = 0) -> str | None:
        self.ran.append(effect)
        return effect


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_awareness_starts_at_zero(self):
        e = _engine()
        assert e.awareness == 0.0

    def test_escalation_starts_at_zero(self):
        e = _engine()
        assert e.escalation == 0

    def test_no_observations(self):
        e = _engine()
        assert e.observations == []

    def test_no_interventions(self):
        e = _engine()
        assert e.interventions == 0

    def test_enabled_flag(self):
        e = _engine(enabled=False)
        assert e.enabled is False


# ---------------------------------------------------------------------------
# _awareness_cost helper
# ---------------------------------------------------------------------------

class TestAwarenessCost:
    def test_known_event(self):
        assert _awareness_cost("encrypted_file_accessed", {}) == 8.0

    def test_unknown_event(self):
        assert _awareness_cost("totally_unknown", {}) == 0.0

    def test_scan_performed(self):
        assert _awareness_cost("scan_performed", {}) == 3.0

    def test_surveillance_discovered(self):
        assert _awareness_cost("surveillance_discovered", {}) == 20.0

    def test_skynet_process_killed(self):
        assert _awareness_cost("skynet_process_killed", {}) == 20.0

    def test_flag_set_shadow_unlocked(self):
        cost = _awareness_cost("flag_set", {"flag": "shadow_unlocked"})
        assert cost == 12.0  # special override

    def test_flag_set_unknown_flag(self):
        cost = _awareness_cost("flag_set", {"flag": "some_random_flag"})
        assert cost == 5.0  # base cost

    def test_heat_threshold_at_high_level(self):
        cost = _awareness_cost("heat_threshold_crossed", {"level": 75.0})
        assert cost == 8.0

    def test_heat_threshold_at_low_level(self):
        cost = _awareness_cost("heat_threshold_crossed", {"level": 10.0})
        assert cost == 0.0  # skipped

    def test_irc_join_z0rk_7_ops(self):
        cost = _awareness_cost("irc_joined", {"channel": "#z0rk_7_ops"})
        assert cost == 18.0

    def test_irc_join_normal_channel(self):
        cost = _awareness_cost("irc_joined", {"channel": "#underground"})
        assert cost == 4.0  # base cost


# ---------------------------------------------------------------------------
# _tier helper
# ---------------------------------------------------------------------------

class TestTier:
    def test_zero_awareness_is_tier_0(self):
        assert _tier(0.0) == 0

    def test_14_is_tier_0(self):
        assert _tier(14.9) == 0

    def test_15_is_tier_1(self):
        assert _tier(15.0) == 1

    def test_35_is_tier_2(self):
        assert _tier(35.0) == 2

    def test_55_is_tier_3(self):
        assert _tier(55.0) == 3

    def test_75_is_tier_4(self):
        assert _tier(75.0) == 4

    def test_90_is_tier_5(self):
        assert _tier(90.0) == 5

    def test_100_is_tier_5(self):
        assert _tier(100.0) == 5


# ---------------------------------------------------------------------------
# observe()
# ---------------------------------------------------------------------------

class TestObserve:
    def test_observe_adds_awareness(self):
        e = _engine()
        e.observe("encrypted_file_accessed")
        assert e.awareness == 8.0

    def test_observe_multiple_events(self):
        e = _engine()
        e.observe("encrypted_file_accessed")  # +8
        e.observe("scan_performed")           # +3
        assert e.awareness == pytest.approx(11.0)

    def test_awareness_capped_at_100(self):
        e = _engine()
        for _ in range(20):
            e.observe("surveillance_discovered")  # +20 each
        assert e.awareness == 100.0

    def test_observe_records_observation(self):
        e = _engine()
        e.observe("encrypted_file_accessed")
        assert len(e.observations) == 1
        assert e.observations[0]["event"] == "encrypted_file_accessed"

    def test_observe_records_current_awareness(self):
        e = _engine()
        e.observe("encrypted_file_accessed")
        assert e.observations[0]["awareness"] == pytest.approx(8.0)

    def test_observe_updates_escalation(self):
        e = _engine()
        e.observe("surveillance_discovered")  # +20 → tier 1
        assert e.escalation == 1

    def test_observe_disabled_no_effect(self):
        e = _engine(enabled=False)
        e.observe("encrypted_file_accessed")
        assert e.awareness == 0.0
        assert len(e.observations) == 0

    def test_observe_unknown_event_no_cost(self):
        e = _engine()
        e.observe("nonexistent_event")
        assert e.awareness == 0.0
        assert len(e.observations) == 0

    def test_observations_capped_at_200(self):
        e = _engine()
        for _ in range(210):
            e.observe("irc_message_posted")  # +1 each
        assert len(e.observations) <= 200

    def test_observe_carries_data(self):
        e = _engine()
        e.observe("flag_set", flag="shadow_unlocked")
        assert e.observations[0]["data"]["flag"] == "shadow_unlocked"


# ---------------------------------------------------------------------------
# Escalation tiers
# ---------------------------------------------------------------------------

class TestEscalation:
    def test_tier_0_by_default(self):
        e = _engine()
        assert e.escalation == 0

    def test_reaches_tier_1(self):
        e = _engine()
        e.observe("surveillance_discovered")  # +20 → tier 1
        assert e.escalation == 1

    def test_reaches_tier_5(self):
        e = _engine()
        e.awareness = 90.0
        e.escalation = _tier(90.0)
        assert e.escalation == 5

    def test_tier_name_dormant(self):
        e = _engine()
        assert e.tier_name() == "dormant"

    def test_tier_name_subtle(self):
        e = _engine()
        e.awareness = 20.0
        e.escalation = 1
        assert e.tier_name() == "subtle"

    def test_tier_name_full_assault(self):
        e = _engine()
        e.escalation = 5
        assert e.tier_name() == "full_assault"


# ---------------------------------------------------------------------------
# evaluate() — intervention decisions
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_tier_0_never_intervenes(self):
        e = _engine()
        # Run many times — tier 0 should never fire
        for _ in range(100):
            assert e.evaluate() is None

    def test_disabled_never_evaluates(self):
        e = _engine(enabled=False)
        e.awareness = 80.0
        e.escalation = 4
        for _ in range(50):
            assert e.evaluate() is None

    def test_cooldown_prevents_intervention(self):
        import time
        e = _engine()
        e.awareness = 80.0
        e.escalation = 4
        e._last_intervention = time.monotonic()  # just happened
        # Should be blocked by cooldown
        result = e.evaluate()
        assert result is None

    def test_evaluate_returns_string_or_none(self):
        e = _engine()
        e.awareness = 50.0
        e.escalation = 3
        e._last_intervention = 0.0  # reset cooldown
        result = e.evaluate()
        assert result is None or isinstance(result, str)

    def test_choose_intervention_tier_1(self):
        e = _engine()
        e.escalation = 1
        # All tier-1 interventions should come from the pool
        pool = set(_TIER_INTERVENTIONS[1])
        for _ in range(20):
            choice = e._choose_intervention()
            if choice is not None:
                assert choice in pool

    def test_choose_intervention_tier_3(self):
        e = _engine()
        e.escalation = 3
        pool = set(_TIER_INTERVENTIONS[3])
        for _ in range(20):
            choice = e._choose_intervention()
            if choice is not None:
                assert choice in pool

    def test_choose_intervention_tier_0_returns_none(self):
        e = _engine()
        e.escalation = 0
        assert e._choose_intervention() is None


# ---------------------------------------------------------------------------
# maybe_intervene()
# ---------------------------------------------------------------------------

class TestMaybeIntervene:
    async def test_runs_fourth_wall_when_intervention_chosen(self):
        fw = MockFourthWall()
        e = SkyNetEngine(fourth_wall=fw, enabled=True)
        e.awareness = 50.0
        e.escalation = 3
        e._last_intervention = 0.0

        # Force a deterministic result by patching evaluate
        e.evaluate = lambda: "fake_system_error"

        result = await e.maybe_intervene()
        assert result == "fake_system_error"
        assert "fake_system_error" in fw.ran

    async def test_increments_interventions_count(self):
        fw = MockFourthWall()
        e = SkyNetEngine(fourth_wall=fw, enabled=True)
        e.evaluate = lambda: "inject_text"

        await e.maybe_intervene()
        assert e.interventions == 1

    async def test_none_result_when_no_intervention(self):
        e = _engine()
        e.evaluate = lambda: None
        result = await e.maybe_intervene()
        assert result is None

    async def test_no_fourth_wall_no_crash(self):
        e = SkyNetEngine(fourth_wall=None, enabled=True)
        e.evaluate = lambda: "inject_text"
        result = await e.maybe_intervene()
        assert result == "inject_text"  # still returns effect name


# ---------------------------------------------------------------------------
# force_intervene()
# ---------------------------------------------------------------------------

class TestForceIntervene:
    async def test_force_ignores_cooldown(self):
        import time
        fw = MockFourthWall()
        e = SkyNetEngine(fourth_wall=fw, enabled=True)
        e._last_intervention = time.monotonic()  # cooldown active

        result = await e.force_intervene("inject_text")
        assert result == "inject_text"
        assert "inject_text" in fw.ran

    async def test_force_increments_count(self):
        fw = MockFourthWall()
        e = SkyNetEngine(fourth_wall=fw, enabled=True)
        await e.force_intervene("inject_text")
        assert e.interventions == 1


# ---------------------------------------------------------------------------
# bind_events()
# ---------------------------------------------------------------------------

class TestBindEvents:
    def test_bind_registers_handlers(self):
        handlers = {}

        class MockEvents:
            def on(self, event_name, handler):
                handlers[event_name] = handler

        e = _engine()
        e.bind_events(MockEvents())
        assert "encrypted_file_accessed" in handlers
        assert "surveillance_discovered" in handlers
        assert "scan_performed" in handlers

    def test_bound_handler_calls_observe(self):
        handlers = {}

        class MockEvents:
            def on(self, event_name, handler):
                handlers[event_name] = handler

        e = _engine()
        e.bind_events(MockEvents())
        handlers["encrypted_file_accessed"]()
        assert e.awareness == 8.0


# ---------------------------------------------------------------------------
# is_watching()
# ---------------------------------------------------------------------------

class TestIsWatching:
    def test_not_watching_at_start(self):
        e = _engine()
        assert not e.is_watching()

    def test_watching_after_observation(self):
        e = _engine()
        e.observe("encrypted_file_accessed")
        assert e.is_watching()

    def test_not_watching_when_disabled(self):
        e = _engine(enabled=False)
        e.awareness = 50.0
        assert not e.is_watching()


# ---------------------------------------------------------------------------
# recent_observations()
# ---------------------------------------------------------------------------

class TestRecentObservations:
    def test_returns_last_n(self):
        e = _engine()
        for i in range(15):
            e.observe("irc_message_posted")
        recent = e.recent_observations(5)
        assert len(recent) == 5

    def test_empty_when_no_observations(self):
        e = _engine()
        assert e.recent_observations(10) == []


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_has_awareness(self):
        e = _engine()
        e.awareness = 42.0
        assert e.to_dict()["awareness"] == pytest.approx(42.0)

    def test_to_dict_has_escalation(self):
        e = _engine()
        e.escalation = 3
        assert e.to_dict()["escalation"] == 3

    def test_to_dict_has_interventions(self):
        e = _engine()
        e.interventions = 7
        assert e.to_dict()["interventions"] == 7

    def test_load_state_restores_awareness(self):
        e = _engine()
        e.load_state({"awareness": 55.0, "escalation": 3, "interventions": 2, "observations": []})
        assert e.awareness == pytest.approx(55.0)

    def test_load_state_restores_escalation(self):
        e = _engine()
        e.load_state({"awareness": 0.0, "escalation": 4, "interventions": 0, "observations": []})
        assert e.escalation == 4

    def test_load_state_empty_dict(self):
        e = _engine()
        e.load_state({})  # should not raise
        assert e.awareness == 0.0

    def test_round_trip(self):
        e1 = _engine()
        e1.awareness = 67.0
        e1.escalation = 3
        e1.interventions = 5

        e2 = _engine()
        e2.load_state(e1.to_dict())
        assert e2.awareness == pytest.approx(67.0)
        assert e2.escalation == 3
        assert e2.interventions == 5
