"""Glitch effects — text corruption, zalgo, scramble reveal, static, color bleed."""
from __future__ import annotations

import random
import string
from typing import Generator

# ---------------------------------------------------------------------------
# Character sets
# ---------------------------------------------------------------------------

_GLITCH_CHARS = list("!@#$%^&*<>[]{}|\\~`" + string.punctuation + "░▒▓█▄▀■□▪▫")
_HEX_CHARS = list("0123456789ABCDEF")
_MATRIX_CHARS = list("ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ")

# Zalgo combining diacritical marks (Unicode 0x0300–0x036F)
_ZALGO_UP   = [chr(c) for c in range(0x0300, 0x0316)]
_ZALGO_MID  = [chr(c) for c in range(0x0316, 0x0333)]
_ZALGO_DOWN = [chr(c) for c in range(0x0333, 0x036F)]


# ---------------------------------------------------------------------------
# glitch_text
# ---------------------------------------------------------------------------

def glitch_text(text: str, intensity: float = 0.1) -> str:
    """Randomly corrupt characters. intensity 0.0–1.0."""
    intensity = max(0.0, min(1.0, intensity))
    out: list[str] = []
    for ch in text:
        if ch not in (" ", "\n") and random.random() < intensity:
            out.append(random.choice(_GLITCH_CHARS))
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# zalgo_text
# ---------------------------------------------------------------------------

def zalgo_text(text: str, intensity: float = 0.3) -> str:
    """Add zalgo combining characters above/below each character."""
    intensity = max(0.0, min(1.0, intensity))
    out: list[str] = []
    for ch in text:
        out.append(ch)
        if ch not in (" ", "\n"):
            n_up   = random.randint(0, int(4 * intensity))
            n_mid  = random.randint(0, int(2 * intensity))
            n_down = random.randint(0, int(3 * intensity))
            for _ in range(n_up):
                out.append(random.choice(_ZALGO_UP))
            for _ in range(n_mid):
                out.append(random.choice(_ZALGO_MID))
            for _ in range(n_down):
                out.append(random.choice(_ZALGO_DOWN))
    return "".join(out)


# ---------------------------------------------------------------------------
# scramble_reveal
# ---------------------------------------------------------------------------

def scramble_reveal(text: str, steps: int = 10) -> Generator[str, None, None]:
    """Yield `steps` frames of text being decoded: random chars → real text.

    Frame 0: all random. Frame steps-1: full plaintext.
    Characters are revealed left-to-right proportionally.
    """
    chars = list(text)
    n = len(chars)
    for step in range(steps):
        revealed = int(n * step / max(steps - 1, 1))
        frame: list[str] = []
        for i, ch in enumerate(chars):
            if i < revealed or ch in (" ", "\n"):
                frame.append(ch)
            else:
                frame.append(random.choice(_MATRIX_CHARS + _HEX_CHARS))
        yield "".join(frame)
    yield text  # final frame is always the real text


# ---------------------------------------------------------------------------
# static_burst
# ---------------------------------------------------------------------------

def static_burst(width: int = 80, height: int = 5) -> str:
    """Generate a block of random characters — TV static."""
    rows: list[str] = []
    charset = _GLITCH_CHARS + _HEX_CHARS + list(string.ascii_letters + string.digits)
    for _ in range(height):
        rows.append("".join(random.choice(charset) for _ in range(width)))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# corrupt_output
# ---------------------------------------------------------------------------

def corrupt_output(text: str) -> str:
    """Make text look like corrupted data — mix of hex, symbols, partial text."""
    words = text.split()
    out: list[str] = []
    for word in words:
        r = random.random()
        if r < 0.15:
            # Replace with hex sequence
            out.append("0x" + "".join(random.choices(_HEX_CHARS, k=4)))
        elif r < 0.25:
            # Shred the word partially
            shredded = list(word)
            for i in range(len(shredded)):
                if random.random() < 0.4:
                    shredded[i] = random.choice(_GLITCH_CHARS)
            out.append("".join(shredded))
        elif r < 0.30:
            # Insert null-byte style artifact
            out.append(word + "\\x00")
        else:
            out.append(word)
    return " ".join(out)


# ---------------------------------------------------------------------------
# color_bleed
# ---------------------------------------------------------------------------

_BLEED_COLORS = ["red", "green", "yellow", "cyan", "magenta", "blue", "bright_red", "bright_green"]


def color_bleed(text: str) -> str:
    """Return Rich markup where text colors shift unpredictably per word."""
    words = text.split()
    out: list[str] = []
    prev_color = ""
    for word in words:
        # Occasionally a word bleeds into the wrong color
        if random.random() < 0.3:
            color = random.choice([c for c in _BLEED_COLORS if c != prev_color])
            out.append(f"[{color}]{word}[/{color}]")
            prev_color = color
        else:
            out.append(word)
            prev_color = ""
    return " ".join(out)
