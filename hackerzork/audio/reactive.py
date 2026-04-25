"""Reactive audio — heat-state crossfade layer.

Each heat band maps to a looping tension track that crossfades on the
REACTIVE channel of the AudioMixer. The mixer calls set_reactive_state()
whenever heat crosses a threshold; this module owns the track names.

Track naming convention: reactive_<state>.ogg in data/sounds/.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackerzork.audio.mixer import AudioMixer

# ---------------------------------------------------------------------------
# Reactive track map
# ---------------------------------------------------------------------------

# Each state maps to one looping file. Files are optional — missing = silence.
# Crossfade duration is handled by AudioMixer (1500ms default).

REACTIVE_TRACKS: dict[str, str] = {
    "safe":            "reactive_safe",           # Calm. You are not yet noticed.
    "monitored":       "reactive_monitored",      # Subtle pulse. Something stirs.
    "active_response": "reactive_active_response", # Pulsing bass. They're watching.
    "hunted":          "reactive_hunted",          # Urgent. Rhythmic alarm elements.
    "critical":        "reactive_critical",        # Full alarm. Heartbeat bass.
}

# Volume multipliers per state — louder as heat rises
REACTIVE_VOLUME: dict[str, float] = {
    "safe":            0.0,   # Reactive layer silent at safe heat
    "monitored":       0.2,
    "active_response": 0.45,
    "hunted":          0.7,
    "critical":        1.0,
}

# Heat thresholds that trigger state changes (mirrors HeatSystem thresholds)
REACTIVE_THRESHOLDS: list[tuple[float, str]] = [
    (0.0,  "safe"),
    (25.0, "monitored"),
    (50.0, "active_response"),
    (75.0, "hunted"),
    (90.0, "critical"),
]


def heat_to_state(heat: float) -> str:
    """Return the reactive state name for a given heat value."""
    state = "safe"
    for threshold, name in REACTIVE_THRESHOLDS:
        if heat >= threshold:
            state = name
    return state


class ReactiveAudio:
    """Drives the reactive layer; subscribe to heat events via EventBus."""

    def __init__(self, mixer: "AudioMixer") -> None:
        self._mixer = mixer
        self._current_state = "safe"

    def on_heat_changed(self, heat: float = 0.0, **kwargs: object) -> None:
        """Call on every heat update — mixer handles deduplication."""
        self._mixer.set_reactive_state(heat)
        self._current_state = heat_to_state(heat)

    def on_heat_threshold_crossed(self, level: float = 0.0, **kwargs: object) -> None:
        self.on_heat_changed(heat=level)

    @property
    def current_state(self) -> str:
        return self._current_state

    def bind_events(self, events: object) -> None:
        """Register heat listeners on an EventBus instance."""
        try:
            events.on("heat_changed", self.on_heat_changed)
            events.on("heat_threshold_crossed", self.on_heat_threshold_crossed)
        except Exception:
            pass
