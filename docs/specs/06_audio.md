# Spec: Audio System

## Module: `hackerzork/audio/mixer.py`

### Purpose
Manages layered audio playback. Four simultaneous layers, crossfading, and heat-reactive mixing. Built on pygame.mixer.

### Architecture
```
Layer 1: AMBIENT    — Continuous drone/pad (loops)
Layer 2: DIEGETIC   — Terminal sounds (one-shots, triggered by actions)
Layer 3: REACTIVE   — Heat-responsive layer (crossfades based on state)
Layer 4: MUSIC      — EDM tracks for boss moments (triggered by events)
```

### API
```python
class AudioMixer:
    def __init__(self, enabled: bool = True):
        """Init pygame.mixer with 4 channels minimum."""

    def set_ambient(self, track: str, fade_ms: int = 2000) -> None
        """Crossfade to a new ambient drone."""

    def play_sfx(self, sound: str, volume: float = 1.0) -> None
        """Play a one-shot sound effect."""

    def play_diegetic(self, sound: str) -> None
        """Play a terminal sound (keystroke, beep, etc.)."""

    def set_reactive_state(self, heat_level: float) -> None
        """Update reactive layer based on heat."""

    def play_music(self, track: str, fade_in_ms: int = 1000) -> None
        """Start a music track (EDM boss track, etc.)."""

    def stop_music(self, fade_out_ms: int = 2000) -> None
        """Fade out current music."""

    def set_master_volume(self, volume: float) -> None
    def set_layer_volume(self, layer: str, volume: float) -> None
    def mute(self) -> None
    def unmute(self) -> None

    def corrupt_audio(self) -> None
        """Meta engine call — distort all audio briefly."""
```

### Sound Effect Triggers
| Action | Sound |
|--------|-------|
| Keystroke | Mechanical key click |
| Command execute | Soft terminal beep |
| Error | Error buzz |
| Scan start | Modem/dial-up connection sound |
| Scan complete | Data received chime |
| Exploit attempt | Tension build |
| Exploit success | Breach sound + bass drop |
| Exploit fail | Harsh rejection buzz |
| SSH connect | Connection established tone |
| Message received | Notification ping |
| Heat threshold | Warning siren (intensity matches level) |
| SkyNet intervention | Distorted, glitchy, unsettling |
| Boot sequence | POST beeps, drive spin-up |

### Reactive Audio States
Map heat thresholds to audio parameters:
- `safe`: Calm ambient, normal SFX
- `monitored`: Subtle tension drone mixed in
- `active_response`: Pulsing bass, faster SFX
- `hunted`: Urgent rhythmic pulse, alarm elements
- `critical`: Full alarm, distorted SFX, heartbeat bass

### Open Source Sound Sources
- freesound.org (CC0 / CC-BY)
- sonniss.com GameAudioGDC bundles (free, royalty-free)
- opengameart.org
- zapsplat.com (free tier)

### Tests: `tests/test_systems/test_audio.py`
- Test initialization (pygame.mixer.init)
- Test layer management
- Test volume controls
- Test graceful degradation when audio disabled
- Test no crash on missing sound files
