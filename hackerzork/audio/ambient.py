"""Ambient drone manager — selects and crossfades background atmosphere tracks.

Ambient tracks cycle based on game context (location, heat, story flags).
All ambient files live in data/sounds/ as .ogg Vorbis (see AUDIO_GUIDE.md).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackerzork.audio.mixer import AudioMixer

# ---------------------------------------------------------------------------
# Track catalogue
# ---------------------------------------------------------------------------

# Track names resolve to data/sounds/<name>.ogg (or .wav).
# Missing files degrade gracefully — no crash, no sound.

AMBIENT_TRACKS: dict[str, str] = {
    "default":     "ambient_default",    # Boot state — cold, sparse, uncertain
    "connected":   "ambient_connected",  # Active SSH session — tension rises
    "shadow":      "ambient_shadow",     # Shadow repo unlocked — paranoid drone
    "oracle":      "ambient_oracle",     # Oracle kit active — cryptic, measured
    "compromised": "ambient_compromised", # Heat > 50 — everything feels wrong
    "critical":    "ambient_critical",   # Heat > 90 — imminent
}

# Story flags → ambient context override
_FLAG_TRACK_MAP: dict[str, str] = {
    "relay_compromised":    "connected",
    "shadow_unlocked":      "shadow",
    "kit_committed_oracle": "oracle",
}


class AmbientManager:
    """Watches game state and drives ambient track selection on the mixer."""

    def __init__(self, mixer: "AudioMixer") -> None:
        self._mixer = mixer
        self._current_context = "default"
        self._active_flags: set[str] = set()

    def set_context(self, context: str, fade_ms: int = 3000) -> None:
        """Switch ambient context. Ignored if already active."""
        if context == self._current_context:
            return
        self._current_context = context
        self._apply(fade_ms)

    def notify_flag(self, flag: str) -> None:
        """Call when a story flag fires — may trigger an ambient transition."""
        self._active_flags.add(flag)
        override = _FLAG_TRACK_MAP.get(flag)
        if override:
            self.set_context(override)

    @property
    def current_context(self) -> str:
        return self._current_context

    def _apply(self, fade_ms: int = 3000) -> None:
        track = AMBIENT_TRACKS.get(self._current_context, AMBIENT_TRACKS["default"])
        self._mixer.set_ambient(track, fade_ms=fade_ms)
