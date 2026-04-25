"""Matrix rain and data-stream effects."""
from __future__ import annotations

import asyncio
import random
import time

from hackerzork.effects import config, get_console

_MATRIX_CHARS = list("ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
                     + "0123456789ABCDEF")
_HEX = list("0123456789ABCDEF")


async def _sleep(s: float) -> None:
    effective = s * config.speed_multiplier
    if effective > 0:
        await asyncio.sleep(effective)


def _rand_line(width: int, charset: list[str]) -> str:
    return "".join(random.choice(charset) for _ in range(width))


# ---------------------------------------------------------------------------
# matrix_rain
# ---------------------------------------------------------------------------

async def matrix_rain(duration: float = 3.0, width: int = 80) -> None:
    """Classic matrix digital rain — green katakana/digits scrolling down."""
    con = get_console()
    if not config.enabled:
        return
    if config.speed_multiplier == 0:
        con.print(f"[green]{_rand_line(width, _MATRIX_CHARS)}[/green]")
        return
    end = time.monotonic() + duration
    while time.monotonic() < end:
        line = _rand_line(width, _MATRIX_CHARS)
        # Brighten a few chars for the "lead" effect
        bright_pos = random.randint(0, len(line) - 1)
        chars = list(line)
        chars[bright_pos] = f"[bold white]{chars[bright_pos]}[/bold white]"
        con.print(f"[green]{''.join(chars)}[/green]")
        await _sleep(0.05)


# ---------------------------------------------------------------------------
# binary_rain
# ---------------------------------------------------------------------------

async def binary_rain(duration: float = 2.0) -> None:
    """Binary variant — 0s and 1s scrolling."""
    con = get_console()
    if not config.enabled:
        return
    if config.speed_multiplier == 0:
        con.print("[dim green]" + _rand_line(80, ["0", "1"]) + "[/dim green]")
        return
    end = time.monotonic() + duration
    while time.monotonic() < end:
        line = _rand_line(80, ["0", "1", "0", "1", " "])
        con.print(f"[dim green]{line}[/dim green]")
        await _sleep(0.04)


# ---------------------------------------------------------------------------
# data_stream
# ---------------------------------------------------------------------------

async def data_stream(text: str) -> None:
    """Show text as if flowing through a data channel — hex dumps interspersed."""
    con = get_console()
    if not config.enabled or config.speed_multiplier == 0:
        con.print(text, markup=False)
        return
    words = text.split()
    buf: list[str] = []
    for i, word in enumerate(words):
        buf.append(word)
        # Occasionally burst a hex noise line between words
        if i % 6 == 5:
            noise = " ".join(f"{random.randint(0,255):02X}" for _ in range(16))
            con.print(f"[dim cyan]{noise}[/dim cyan]")
            await _sleep(0.06)
    con.print(" ".join(buf), markup=False)


# ---------------------------------------------------------------------------
# decrypt_animation
# ---------------------------------------------------------------------------

async def decrypt_animation(
    ciphertext: str,
    plaintext: str,
    duration: float = 2.0,
) -> None:
    """Animate text being decrypted: cipher chars resolve to plaintext left-to-right."""
    from hackerzork.effects.glitch import scramble_reveal
    con = get_console()
    if not config.enabled or config.speed_multiplier == 0:
        con.print(plaintext, markup=False)
        return

    steps = max(8, int(duration / 0.1))
    frames = list(scramble_reveal(plaintext, steps=steps))
    tick = duration / len(frames)
    for frame in frames:
        con.print(f"[cyan]{frame}[/cyan]", markup=False)
        await _sleep(tick)
