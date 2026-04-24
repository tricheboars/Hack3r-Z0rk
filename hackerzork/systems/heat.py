"""Heat / trace system — tracks player exposure and drives escalating consequences."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from hackerzork.systems.events import Event, EventBus


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEAT_COSTS: dict[str, float] = {
    "ping": 0.5,
    "port_scan": 2.0,
    "service_scan": 5.0,
    "exploit_attempt": 10.0,
    "exploit_success": 5.0,
    "exploit_fail": 15.0,
    "ssh_connect": 1.0,
    "file_exfil": 3.0,
    "brute_force": 20.0,
}

# (minimum level, threshold name) ordered highest-first for lookup
_THRESHOLDS: list[tuple[float, str]] = [
    (100.0, "burned"),
    (90.0, "critical"),
    (75.0, "hunted"),
    (50.0, "active_response"),
    (25.0, "monitored"),
    (0.0, "safe"),
]

_THREAT_DESCRIPTIONS: dict[str, list[str]] = {
    "safe": [],
    "monitored": [
        "Passive monitoring detected",
    ],
    "active_response": [
        "Passive monitoring detected",
        "ICE programs active",
        "Firewall rules tightening",
    ],
    "hunted": [
        "ICE programs active",
        "Hunter teams dispatched",
        "Allies reporting unusual traffic",
    ],
    "critical": [
        "Hunter teams dispatched",
        "Identity nearly burned",
        "Extreme countermeasures active",
    ],
    "burned": [],
}

# Event name → base heat cost.  Events with cost 0 are ignored.
_EVENT_HEAT: dict[str, float] = {
    "ping_sent": HEAT_COSTS["ping"],
    "scan_performed": HEAT_COSTS["port_scan"],
    "traceroute_performed": 1.0,
    "ssh_attempted": HEAT_COSTS["ssh_connect"],
    "ssh_connected": 0.0,
    "http_request_made": 0.5,
    "nc_connection": 1.0,
    "content_searched": 0.2,
    "exploit_attempted": HEAT_COSTS["exploit_attempt"],
    "exploit_failed": HEAT_COSTS["exploit_fail"],
    "exploit_succeeded": HEAT_COSTS["exploit_success"],
}

_MIN_MODIFIER = 0.05  # stealth can never reduce heat below 5 % of base


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class HeatStatus:
    level: float
    threshold: str
    decay_rate: float
    active_threats: list[str]
    time_to_safe: float  # estimated game-minutes to reach 0.0


# ---------------------------------------------------------------------------
# HeatSystem
# ---------------------------------------------------------------------------


class HeatSystem:
    def __init__(self, events: EventBus | None = None) -> None:
        self.level: float = 0.0
        self.decay_rate: float = 0.1          # per game-minute
        self.current_threshold: str = "safe"
        self._events = events
        self._stealth_modifiers: dict[str, float] = {}   # name → multiplier
        self._burn_count: int = 0
        self._handlers: list[tuple[str, Callable]] = []  # for unsubscribe

        if events is not None:
            self._subscribe(events)

    # -------------------------------------------------------------------------
    # Core heat manipulation
    # -------------------------------------------------------------------------

    def add_heat(self, amount: float, source: str = "") -> None:
        """Add heat from an action, applying active stealth modifiers."""
        adjusted = amount * self._combined_modifier()
        old_level = self.level
        self.level = min(100.0, self.level + adjusted)
        self._check_threshold(old_level)
        self._emit(
            "heat_changed",
            amount=adjusted,
            source=source,
            level=self.level,
            direction="up",
        )
        if self.level >= 100.0:
            self._trigger_burn()

    def reduce_heat(self, amount: float, source: str = "") -> None:
        """Manually reduce heat (stealth tools, cooldown abilities, etc.)."""
        old_level = self.level
        self.level = max(0.0, self.level - amount)
        self._check_threshold(old_level)
        self._emit(
            "heat_changed",
            amount=-amount,
            source=source,
            level=self.level,
            direction="down",
        )

    def tick(self, game_minutes: float) -> None:
        """Apply natural decay. Call once per in-game time step."""
        if self.level <= 0.0:
            return
        decay = self.decay_rate * game_minutes
        old_level = self.level
        self.level = max(0.0, self.level - decay)
        self._check_threshold(old_level)
        if old_level != self.level:
            self._emit(
                "heat_changed",
                amount=-decay,
                source="decay",
                level=self.level,
                direction="down",
            )

    # -------------------------------------------------------------------------
    # Status / queries
    # -------------------------------------------------------------------------

    def get_status(self) -> HeatStatus:
        """Return a snapshot of the current heat state."""
        if self.decay_rate > 0:
            time_to_safe = self.level / self.decay_rate
        else:
            time_to_safe = float("inf")
        return HeatStatus(
            level=round(self.level, 2),
            threshold=self.current_threshold,
            decay_rate=self.decay_rate,
            active_threats=list(_THREAT_DESCRIPTIONS.get(self.current_threshold, [])),
            time_to_safe=round(time_to_safe, 1),
        )

    def get_threshold_name(self) -> str:
        return self.current_threshold

    # -------------------------------------------------------------------------
    # Stealth modifiers
    # -------------------------------------------------------------------------

    def add_stealth_modifier(self, name: str, multiplier: float) -> None:
        """Register a named multiplier.  multiplier=0.5 → 50 % less heat."""
        self._stealth_modifiers[name] = max(0.0, min(1.0, multiplier))

    def remove_stealth_modifier(self, name: str) -> None:
        self._stealth_modifiers.pop(name, None)

    def has_stealth_modifier(self, name: str) -> bool:
        return name in self._stealth_modifiers

    def effective_multiplier(self) -> float:
        """Return the combined heat multiplier currently in effect."""
        return self._combined_modifier()

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "decay_rate": self.decay_rate,
            "current_threshold": self.current_threshold,
            "burn_count": self._burn_count,
            "stealth_modifiers": dict(self._stealth_modifiers),
        }

    def load_state(self, state: dict) -> None:
        self.level = float(state.get("level", 0.0))
        self.decay_rate = float(state.get("decay_rate", 0.1))
        self.current_threshold = state.get("current_threshold", "safe")
        self._burn_count = int(state.get("burn_count", 0))
        self._stealth_modifiers = dict(state.get("stealth_modifiers", {}))

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _combined_modifier(self) -> float:
        if not self._stealth_modifiers:
            return 1.0
        result = 1.0
        for m in self._stealth_modifiers.values():
            result *= m
        return max(_MIN_MODIFIER, result)

    def _level_to_threshold(self, level: float) -> str:
        for threshold_level, name in _THRESHOLDS:
            if level >= threshold_level:
                return name
        return "safe"

    def _check_threshold(self, old_level: float) -> None:
        """Update current_threshold and emit a crossing event if it changed."""
        new_threshold = self._level_to_threshold(self.level)
        old_threshold = self._level_to_threshold(old_level)
        self.current_threshold = new_threshold
        if new_threshold != old_threshold:
            self._emit(
                "heat_threshold_crossed",
                from_threshold=old_threshold,
                to_threshold=new_threshold,
                level=self.level,
            )

    def _trigger_burn(self) -> None:
        """Identity burn: emit event then reset heat to zero."""
        self._burn_count += 1
        self._emit("identity_burned", burn_count=self._burn_count, level=self.level)
        pre_burn = self.level
        self.level = 0.0
        self.current_threshold = "safe"
        self._emit(
            "heat_changed",
            amount=-pre_burn,
            source="burn_reset",
            level=0.0,
            direction="down",
        )
        self._emit(
            "heat_threshold_crossed",
            from_threshold="burned",
            to_threshold="safe",
            level=0.0,
        )

    def _subscribe(self, events: EventBus) -> None:
        """Register listeners on the event bus for all tracked action events."""
        for event_name, cost in _EVENT_HEAT.items():
            if cost <= 0:
                continue
            handler = self._make_handler(event_name, cost)
            events.on(event_name, handler)
            self._handlers.append((event_name, handler))

    def _make_handler(self, event_name: str, base_cost: float) -> Callable:
        def handler(event: Event) -> None:
            cost = base_cost
            data = event.data
            # Stealth scan flag: -30 % heat for that scan only
            if event_name == "scan_performed" and data.get("stealth"):
                cost *= 0.7
            self.add_heat(cost, source=event_name)

        return handler

    def _emit(self, event_name: str, **data: object) -> None:
        if self._events is not None:
            self._events.emit(event_name, **data)
