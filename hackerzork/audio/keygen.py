"""Procedural SFX generator — synthesizes missing .wav files from stdlib only.

Called at startup to ensure sfx_key_click.wav, sfx_boot_beep.wav, and
sfx_boot_ready.wav exist before pygame.mixer tries to load them.
"""
from __future__ import annotations

import array
import math
import wave
from pathlib import Path


# ---------------------------------------------------------------------------
# Synthesis helpers
# ---------------------------------------------------------------------------

def _write_wav(path: Path, buf: array.array, sample_rate: int = 44100) -> None:
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(buf.tobytes())


def _synth_key_click(sample_rate: int = 44100) -> array.array:
    """25 ms clicky mechanical key: sharp transient + body resonance + noise burst."""
    n = int(sample_rate * 0.025)
    buf = array.array("h", [0] * n)
    rand_state = 12345

    for i in range(n):
        t = i / sample_rate

        # High-freq actuator click (Cherry MX Blue-ish)
        click = math.sin(2 * math.pi * 2000 * t) * math.exp(-t / 0.003)

        # Low-freq keyswitch body thock
        thock = math.sin(2 * math.pi * 280 * t) * math.exp(-t / 0.009) * 0.6

        # Crispy noise burst (the tactile "snap")
        rand_state = (rand_state * 1103515245 + 12345) & 0x7FFFFFFF
        noise = (rand_state / 0x3FFFFFFF - 1.0) * math.exp(-t / 0.0015) * 0.35

        val = max(-1.0, min(1.0, (click + thock + noise) * 0.7))
        buf[i] = int(val * 32767)

    return buf


def _synth_boot_beep(sample_rate: int = 44100) -> array.array:
    """100 ms PC-speaker style POST beep (440 Hz)."""
    n = int(sample_rate * 0.10)
    buf = array.array("h", [0] * n)
    fade_samples = int(sample_rate * 0.015)

    for i in range(n):
        t = i / sample_rate
        # Fade out at end to avoid click artifacts
        env = (n - i) / fade_samples if i > n - fade_samples else 1.0
        val = math.sin(2 * math.pi * 440 * t) * env * 0.45
        buf[i] = int(val * 32767)

    return buf


def _synth_boot_ready(sample_rate: int = 44100) -> array.array:
    """400 ms ascending two-tone: C5 → E5 — signals system ready."""
    n = int(sample_rate * 0.40)
    buf = array.array("h", [0] * n)
    half = n // 2
    fade = int(sample_rate * 0.025)

    for i in range(n):
        t = i / sample_rate
        freq = 523.25 if i < half else 659.25  # C5 then E5
        env = min(1.0, i / (sample_rate * 0.005))  # 5 ms attack
        if i > n - fade:
            env *= (n - i) / fade
        val = math.sin(2 * math.pi * freq * t) * env * 0.45
        buf[i] = int(val * 32767)

    return buf


def _synth_terminal_beep(sample_rate: int = 44100) -> array.array:
    """50 ms terminal bell at 880 Hz."""
    n = int(sample_rate * 0.05)
    buf = array.array("h", [0] * n)
    for i in range(n):
        t = i / sample_rate
        env = (n - i) / n
        buf[i] = int(math.sin(2 * math.pi * 880 * t) * env * 0.4 * 32767)
    return buf


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_GENERATORS: dict[str, object] = {
    "sfx_key_click":    _synth_key_click,
    "sfx_boot_beep":    _synth_boot_beep,
    "sfx_boot_ready":   _synth_boot_ready,
    "sfx_terminal_beep": _synth_terminal_beep,
}


def ensure_sounds(sounds_dir: Path) -> None:
    """Generate any missing procedural sound files in sounds_dir.

    Safe to call on every startup — skips files that already exist.
    Never raises; failures are silently ignored so missing audio never
    crashes the game.
    """
    sounds_dir.mkdir(parents=True, exist_ok=True)
    for stem, gen_fn in _GENERATORS.items():
        path = sounds_dir / f"{stem}.wav"
        if not path.exists():
            try:
                _write_wav(path, gen_fn())  # type: ignore[operator]
            except Exception:
                pass
