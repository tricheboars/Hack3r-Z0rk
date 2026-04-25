"""AudioMixer — four-layer audio engine built on pygame.mixer.

Layer map:
  0  AMBIENT   — continuous looping drone/pad
  1  DIEGETIC  — terminal sounds (keystrokes, beeps)
  2  REACTIVE  — heat-state crossfade layer
  3  MUSIC     — EDM / event-driven tracks
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

_SOUNDS_DIR = Path(__file__).parent.parent / "data" / "sounds"
_MUSIC_DIR  = Path(__file__).parent.parent / "data" / "music"

_LAYER_AMBIENT  = 0
_LAYER_DIEGETIC = 1
_LAYER_REACTIVE = 2
_LAYER_MUSIC    = 3

_HEAT_STATES = ["safe", "monitored", "active_response", "hunted", "critical"]

# Heat thresholds that map to reactive states (must match HeatSystem thresholds)
_REACTIVE_THRESHOLDS = [
    (0.0,  "safe"),
    (25.0, "monitored"),
    (50.0, "active_response"),
    (75.0, "hunted"),
    (90.0, "critical"),
]


def _heat_state(heat: float) -> str:
    state = "safe"
    for threshold, name in _REACTIVE_THRESHOLDS:
        if heat >= threshold:
            state = name
    return state


class AudioMixer:
    """Manages four-layer simultaneous audio with crossfading and heat-reactive mixing."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._initialized = False
        self._muted = False
        self._master_volume: float = 1.0
        self._layer_volumes: dict[int, float] = {
            _LAYER_AMBIENT:  0.6,
            _LAYER_DIEGETIC: 1.0,
            _LAYER_REACTIVE: 0.4,
            _LAYER_MUSIC:    0.8,
        }
        self._current_ambient: str | None = None
        self._current_reactive: str | None = None
        self._current_music: str | None = None
        self._reactive_state: str = "safe"
        self._sound_cache: dict[str, object] = {}

        if enabled:
            self._init_pygame()

    def _init_pygame(self) -> None:
        try:
            import pygame.mixer as mixer
            mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
            mixer.init()
            mixer.set_num_channels(8)
            self._mixer = mixer
            self._channels = {
                _LAYER_AMBIENT:  mixer.Channel(_LAYER_AMBIENT),
                _LAYER_DIEGETIC: mixer.Channel(_LAYER_DIEGETIC),
                _LAYER_REACTIVE: mixer.Channel(_LAYER_REACTIVE),
                _LAYER_MUSIC:    mixer.Channel(_LAYER_MUSIC),
            }
            self._initialized = True
            logger.debug("AudioMixer: pygame.mixer initialized")
        except Exception as exc:
            logger.warning("AudioMixer: pygame.mixer unavailable — audio disabled (%s)", exc)
            self.enabled = False

    # -------------------------------------------------------------------------
    # Sound loading
    # -------------------------------------------------------------------------

    def _load_sound(self, name: str, base_dir: Path) -> object | None:
        if not self._initialized:
            return None
        if name in self._sound_cache:
            return self._sound_cache[name]
        for ext in (".wav", ".ogg", ".mp3"):
            path = base_dir / (name + ext)
            if path.exists():
                try:
                    snd = self._mixer.Sound(str(path))
                    self._sound_cache[name] = snd
                    return snd
                except Exception as exc:
                    logger.debug("AudioMixer: failed to load %s: %s", path, exc)
        logger.debug("AudioMixer: sound not found: %s", name)
        return None

    # -------------------------------------------------------------------------
    # Ambient layer
    # -------------------------------------------------------------------------

    def set_ambient(self, track: str, fade_ms: int = 2000) -> None:
        """Crossfade to a new ambient drone. Loops indefinitely."""
        if not self._initialized or self._muted:
            return
        if track == self._current_ambient:
            return
        snd = self._load_sound(track, _SOUNDS_DIR)
        if snd is None:
            return
        ch = self._channels[_LAYER_AMBIENT]
        vol = self._layer_volumes[_LAYER_AMBIENT] * self._master_volume
        if ch.get_busy():
            ch.fadeout(fade_ms)
        snd.set_volume(vol)
        ch.play(snd, loops=-1, fade_ms=fade_ms)
        self._current_ambient = track

    def stop_ambient(self, fade_ms: int = 1000) -> None:
        if not self._initialized:
            return
        self._channels[_LAYER_AMBIENT].fadeout(fade_ms)
        self._current_ambient = None

    # -------------------------------------------------------------------------
    # SFX / diegetic layers
    # -------------------------------------------------------------------------

    def play_sfx(self, sound: str, volume: float = 1.0) -> None:
        """Play a one-shot sound effect on the DIEGETIC channel."""
        if not self._initialized or self._muted:
            return
        snd = self._load_sound(sound, _SOUNDS_DIR)
        if snd is None:
            return
        effective = volume * self._layer_volumes[_LAYER_DIEGETIC] * self._master_volume
        snd.set_volume(effective)
        # Use find_channel so SFX don't block each other
        ch = self._mixer.find_channel(force=True)
        if ch is not None:
            ch.play(snd)

    def play_diegetic(self, sound: str) -> None:
        """Alias for play_sfx — used for terminal sounds (keystrokes, beeps)."""
        self.play_sfx(sound, volume=self._layer_volumes[_LAYER_DIEGETIC])

    # -------------------------------------------------------------------------
    # Reactive layer
    # -------------------------------------------------------------------------

    def set_reactive_state(self, heat_level: float) -> None:
        """Crossfade the reactive layer based on current heat.

        Each heat band maps to a different ambient tension track.
        The track name convention is "reactive_<state>" (e.g. reactive_hunted).
        """
        new_state = _heat_state(heat_level)
        if new_state == self._reactive_state and self._current_reactive is not None:
            return
        self._reactive_state = new_state

        from hackerzork.audio.reactive import REACTIVE_TRACKS
        track = REACTIVE_TRACKS.get(new_state)
        if track is None:
            return

        if not self._initialized or self._muted:
            return

        snd = self._load_sound(track, _SOUNDS_DIR)
        if snd is None:
            return

        ch = self._channels[_LAYER_REACTIVE]
        vol = self._layer_volumes[_LAYER_REACTIVE] * self._master_volume
        if ch.get_busy():
            ch.fadeout(1500)
        snd.set_volume(vol)
        ch.play(snd, loops=-1, fade_ms=1500)
        self._current_reactive = track

    # -------------------------------------------------------------------------
    # Music layer
    # -------------------------------------------------------------------------

    def play_music(self, track: str, fade_in_ms: int = 1000) -> None:
        """Start a music track on the MUSIC channel (boss moments, events)."""
        if not self._initialized or self._muted:
            return
        snd = self._load_sound(track, _MUSIC_DIR)
        if snd is None:
            # Fall back to sounds dir
            snd = self._load_sound(track, _SOUNDS_DIR)
        if snd is None:
            return
        ch = self._channels[_LAYER_MUSIC]
        vol = self._layer_volumes[_LAYER_MUSIC] * self._master_volume
        snd.set_volume(vol)
        ch.play(snd, loops=-1, fade_ms=fade_in_ms)
        self._current_music = track

    def stop_music(self, fade_out_ms: int = 2000) -> None:
        if not self._initialized:
            return
        self._channels[_LAYER_MUSIC].fadeout(fade_out_ms)
        self._current_music = None

    # -------------------------------------------------------------------------
    # Volume controls
    # -------------------------------------------------------------------------

    def set_master_volume(self, volume: float) -> None:
        self._master_volume = max(0.0, min(1.0, volume))
        self._apply_volumes()

    def set_layer_volume(self, layer: str, volume: float) -> None:
        layer_map = {
            "ambient":  _LAYER_AMBIENT,
            "diegetic": _LAYER_DIEGETIC,
            "reactive": _LAYER_REACTIVE,
            "music":    _LAYER_MUSIC,
        }
        idx = layer_map.get(layer.lower())
        if idx is None:
            return
        self._layer_volumes[idx] = max(0.0, min(1.0, volume))
        self._apply_volumes()

    def _apply_volumes(self) -> None:
        if not self._initialized:
            return
        for layer_idx, ch in self._channels.items():
            if ch.get_busy():
                effective = self._layer_volumes[layer_idx] * self._master_volume
                ch.get_sound().set_volume(effective)

    def mute(self) -> None:
        self._muted = True
        if self._initialized:
            self._mixer.pause()

    def unmute(self) -> None:
        self._muted = False
        if self._initialized:
            self._mixer.unpause()

    # -------------------------------------------------------------------------
    # Meta engine hook
    # -------------------------------------------------------------------------

    def corrupt_audio(self) -> None:
        """Brief audio distortion — called by the meta engine on SkyNet events."""
        if not self._initialized or self._muted:
            return
        self.play_sfx("glitch_burst")
        # Temporarily slam volume, restore after distortion clip plays
        self.set_master_volume(0.15)
        try:
            import pygame
            pygame.time.delay(120)
        except Exception:
            pass
        self.set_master_volume(self._master_volume)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def shutdown(self) -> None:
        if self._initialized:
            try:
                self._mixer.fadeout(500)
                import pygame
                pygame.time.delay(600)
                self._mixer.quit()
            except Exception:
                pass
        self._initialized = False

    # -------------------------------------------------------------------------
    # Introspection (for tests / debug)
    # -------------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def reactive_state(self) -> str:
        return self._reactive_state

    @property
    def current_ambient(self) -> str | None:
        return self._current_ambient

    @property
    def current_music(self) -> str | None:
        return self._current_music
