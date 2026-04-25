"""Typewriter effects — character-by-character output, dramatic pauses, redacted text."""
from __future__ import annotations

import asyncio
import random

from hackerzork.effects import config, get_console


async def _sleep(seconds: float) -> None:
    effective = seconds * config.speed_multiplier
    if effective > 0:
        await asyncio.sleep(effective)


async def typewriter(text: str, speed: float = 0.03) -> None:
    """Print text character by character."""
    if not config.enabled or config.speed_multiplier == 0:
        get_console().print(text, end="", markup=False)
        get_console().print("")
        return
    con = get_console()
    for char in text:
        con.print(char, end="", markup=False)
        try:
            con.file.flush()
        except Exception:
            pass
        await _sleep(speed)
    con.print("")


async def typewriter_fast(text: str) -> None:
    """Fast typewriter — machine/system output cadence."""
    await typewriter(text, speed=0.005)


async def dramatic_pause(seconds: float = 1.0) -> None:
    """Pause with a blinking cursor indicator."""
    if not config.enabled or config.speed_multiplier == 0:
        return
    con = get_console()
    tick = 0.25
    elapsed = 0.0
    while elapsed < seconds:
        con.print(["|", " "][int(elapsed / tick) % 2], end="\r", markup=False)
        await _sleep(tick)
        elapsed += tick
    con.print(" ", end="\r")


async def redacted_text(text: str, redact_pct: float = 0.3) -> str:
    """Return text with random words replaced by [REDACTED].

    Skips words shorter than 3 chars. Returns the string — caller displays it.
    """
    words = text.split()
    result: list[str] = []
    for word in words:
        if len(word) >= 3 and random.random() < redact_pct:
            result.append("[REDACTED]")
        else:
            result.append(word)
    return " ".join(result)


async def reveal_redacted(original: str, redacted: str, speed: float = 0.04) -> None:
    """Animate un-redacting text: progressively replace [REDACTED] with original words."""
    if not config.enabled or config.speed_multiplier == 0:
        get_console().print(original, markup=False)
        return
    orig_words = original.split()
    red_words = redacted.split()
    current = list(red_words)
    con = get_console()
    for i, (orig_w, red_w) in enumerate(zip(orig_words, red_words)):
        if red_w == "[REDACTED]":
            current[i] = orig_w
            con.print(" ".join(current), markup=False)
            await _sleep(speed)
    con.print("")
