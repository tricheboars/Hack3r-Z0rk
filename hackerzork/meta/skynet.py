"""SkyNet observation and escalation engine.

SkyNet listens to every event on the bus, accumulates awareness, advances
through 6 escalation tiers, and decides when to intervene. It is the brain;
FourthWallBreaker is the hands.

Awareness is a float 0–100. Escalation tier is derived from awareness:
  0  [  0, 15) — dormant
  1  [ 15, 35) — subtle
  2  [ 35, 55) — unsettling
  3  [ 55, 75) — overt
  4  [ 75, 90) — hostile
  5  [ 90,100] — full assault
"""
from __future__ import annotations

import random
import time
from typing import Any


# ---------------------------------------------------------------------------
# Awareness costs per event
# ---------------------------------------------------------------------------

_AWARENESS_COSTS: dict[str, float] = {
    "encrypted_file_accessed": 8.0,
    "surveillance_discovered":  20.0,
    "skynet_process_killed":    20.0,
    "ssh_connected":            5.0,
    "ssh_attempted":            2.0,
    "scan_performed":           3.0,
    "heat_threshold_crossed":   8.0,
    "identity_burned":          25.0,
    "flag_set":                 5.0,
    "irc_joined":               4.0,
    "irc_message_posted":       1.0,
    "content_searched":         2.0,
    "file_shredded":            6.0,
    "dm_sent":                  3.0,
    "exploit_attempted":        5.0,
    "exploit_succeeded":        8.0,
    "exploit_failed":           3.0,
    "story_event":              3.0,
}

# Per-flag boosts when flag_set fires
_FLAG_AWARENESS: dict[str, float] = {
    "shadow_unlocked":          12.0,
    "relay_alpha_compromised":  15.0,
    "z0rk7_contact_established": 10.0,
    "kit_committed":            6.0,
    "surveillance_seen":        18.0,
}

# Tier thresholds (lower bound of each tier)
_TIER_THRESHOLDS = [0.0, 15.0, 35.0, 55.0, 75.0, 90.0]

# Possible intervention types per tier
_TIER_INTERVENTIONS: dict[int, list[str]] = {
    0: [],
    1: ["subtle_typo", "log_injection"],
    2: ["inject_text", "change_terminal_title"],
    3: ["command_echo_corruption", "corrupt_prompt", "fake_system_error"],
    4: ["fake_crash", "plant_evidence", "corrupt_command_output"],
    5: ["address_player", "fake_reboot", "phantom_cursor"],
}

# Probability of intervention per evaluate() call, per tier
_TIER_PROBABILITY = {0: 0.0, 1: 0.06, 2: 0.10, 3: 0.15, 4: 0.25, 5: 0.40}

# Minimum seconds between interventions per tier
_TIER_COOLDOWN = {0: 9999, 1: 120, 2: 90, 3: 60, 4: 30, 5: 15}


# ---------------------------------------------------------------------------
# SkyNetEngine
# ---------------------------------------------------------------------------

class SkyNetEngine:
    """Observes all events, accumulates awareness, decides when to intervene."""

    def __init__(self, events: Any = None, fourth_wall: Any = None, enabled: bool = True) -> None:
        self.awareness: float = 0.0
        self.escalation: int = 0
        self.observations: list[dict] = []
        self.interventions: int = 0
        self.enabled: bool = enabled

        self._events = events
        self._fourth_wall = fourth_wall
        self._last_intervention: float = 0.0

    # ------------------------------------------------------------------
    # Event binding
    # ------------------------------------------------------------------

    def bind_events(self, events: Any) -> None:
        self._events = events
        for event_name in _AWARENESS_COSTS:
            events.on(event_name, self._make_handler(event_name))

    def _make_handler(self, event_name: str):
        def handler(event):
            self.observe(event_name, **event.data)
        return handler

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    def observe(self, event_name: str, **data: Any) -> None:
        if not self.enabled:
            return

        cost = _awareness_cost(event_name, data)
        if cost <= 0:
            return

        self.awareness = min(100.0, self.awareness + cost)
        old_tier = self.escalation
        self.escalation = _tier(self.awareness)

        self.observations.append({
            "event":     event_name,
            "data":      data,
            "awareness": self.awareness,
            "tier":      self.escalation,
        })

        # Cap observations list to avoid unbounded growth
        if len(self.observations) > 200:
            self.observations = self.observations[-200:]

    # ------------------------------------------------------------------
    # Evaluation (called after each command by the shell)
    # ------------------------------------------------------------------

    def evaluate(self) -> str | None:
        """Decide whether to intervene. Returns intervention type or None."""
        if not self.enabled or self.escalation == 0:
            return None

        cooldown = _TIER_COOLDOWN[self.escalation]
        if time.monotonic() - self._last_intervention < cooldown:
            return None

        prob = _TIER_PROBABILITY[self.escalation]
        if random.random() > prob:
            return None

        return self._choose_intervention()

    def _choose_intervention(self) -> str | None:
        pool = _TIER_INTERVENTIONS.get(self.escalation, [])
        if not pool:
            return None
        return random.choice(pool)

    async def maybe_intervene(self) -> str | None:
        """Evaluate and run an intervention if warranted. Returns effect name or None."""
        effect = self.evaluate()
        if effect is None:
            return None

        self.interventions += 1
        self._last_intervention = time.monotonic()

        if self._fourth_wall is not None:
            await self._fourth_wall.run(effect, awareness=self.awareness, tier=self.escalation)

        return effect

    # ------------------------------------------------------------------
    # Forced intervention (for story triggers, ignores cooldown/probability)
    # ------------------------------------------------------------------

    async def force_intervene(self, effect: str) -> str:
        """Run a specific effect immediately, ignoring cooldown and probability."""
        self.interventions += 1
        self._last_intervention = time.monotonic()
        if self._fourth_wall is not None:
            await self._fourth_wall.run(effect, awareness=self.awareness, tier=self.escalation)
        return effect

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_watching(self) -> bool:
        return self.enabled and self.awareness > 0

    def tier_name(self) -> str:
        return _TIER_NAMES.get(self.escalation, "unknown")

    def recent_observations(self, n: int = 10) -> list[dict]:
        return self.observations[-n:]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "awareness":     self.awareness,
            "escalation":    self.escalation,
            "interventions": self.interventions,
            "observations":  self.observations[-50:],  # save last 50
        }

    def load_state(self, state: dict) -> None:
        self.awareness    = float(state.get("awareness", 0.0))
        self.escalation   = int(state.get("escalation", 0))
        self.interventions = int(state.get("interventions", 0))
        self.observations = list(state.get("observations", []))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIER_NAMES = {
    0: "dormant",
    1: "subtle",
    2: "unsettling",
    3: "overt",
    4: "hostile",
    5: "full_assault",
}


def _tier(awareness: float) -> int:
    tier = 0
    for i, threshold in enumerate(_TIER_THRESHOLDS):
        if awareness >= threshold:
            tier = i
    return tier


def _awareness_cost(event_name: str, data: dict) -> float:
    base = _AWARENESS_COSTS.get(event_name, 0.0)
    if base == 0.0:
        return 0.0

    # Special per-flag boost
    if event_name == "flag_set":
        flag = data.get("flag", "")
        return _FLAG_AWARENESS.get(flag, base)

    # Only count heat_threshold_crossed when heat is meaningfully high
    if event_name == "heat_threshold_crossed":
        level = float(data.get("level", 0))
        return base if level >= 50.0 else 0.0

    # IRC join to #z0rk_7_ops is high-signal
    if event_name == "irc_joined":
        channel = data.get("channel", "")
        return 18.0 if channel == "#z0rk_7_ops" else base

    return base
