# Spec: Visual Effects

## Modules: `hackerzork/effects/`

### Purpose
All the visual magic that makes this feel like hacking the Gibson. Typewriter text, glitch corruption, matrix rain, boot animations, progress bars, and beyond-terminal effects.

### effects/typing.py
```python
async def typewriter(text: str, speed: float = 0.03) -> None
    """Print text character by character."""

async def typewriter_fast(text: str) -> None
    """Fast typewriter for system output."""

async def dramatic_pause(seconds: float = 1.0) -> None
    """Pause with blinking cursor."""

async def redacted_text(text: str, redact_pct: float = 0.3) -> str
    """Show text with random [REDACTED] blocks."""
```

### effects/glitch.py
```python
def glitch_text(text: str, intensity: float = 0.1) -> str
    """Corrupt characters randomly. Intensity 0.0-1.0."""

def zalgo_text(text: str, intensity: float = 0.3) -> str
    """Add zalgo combining characters for creepy effect."""

def scramble_reveal(text: str, steps: int = 10) -> Generator[str]:
    """Yield frames of text being 'decoded' — random chars → real text."""

def static_burst(width: int, height: int) -> str
    """Generate a block of random characters — TV static."""

def corrupt_output(text: str) -> str
    """Make text look like corrupted data — mix of hex, symbols, partial text."""

def color_bleed(text: str) -> str
    """Rich markup — text colors shift/bleed unexpectedly."""
```

### effects/matrix.py
```python
async def matrix_rain(duration: float = 3.0, width: int = 80) -> None
    """Classic matrix digital rain animation."""

async def data_stream(text: str) -> None
    """Show text as if it's flowing through a data stream — hex dumps interspersed."""

async def decrypt_animation(ciphertext: str, plaintext: str, duration: float = 2.0) -> None
    """Animate text being 'decrypted' — cipher gradually resolves to plain."""

async def binary_rain(duration: float = 2.0) -> None
    """01010 rain variant."""
```

### effects/animations.py
```python
async def boot_sequence() -> None
    """Full cold boot animation — POST, memory check, services starting."""

async def progress_bar(label: str, duration: float, style: str = "hack") -> None
    """Animated progress bar. Styles: hack, download, decrypt, upload."""

async def spinner(label: str, duration: float) -> None
    """Terminal spinner with label."""

async def connection_animation(target: str) -> None
    """SSH/connection establishing animation with fake handshake."""

async def breach_animation() -> None
    """Dramatic animation for successful exploit — the big moment."""

async def shutdown_sequence() -> None
    """System shutdown / identity burn animation."""

async def scan_animation(target: str, ports_found: int) -> None
    """nmap-style scan output animation with scrolling results."""
```

### Beyond-Terminal Effects
These are the Pony Island moments — effects that seem to break the game:
- Terminal window title changes unexpectedly
- Cursor behaves erratically
- Colors invert or shift
- Text appears that the player didn't type
- "System errors" that look real but are scripted
- Fake crash and reboot
- Save file "corruption" messages

These are triggered by the meta engine (meta/fourth_wall.py) and implemented using Rich's console control + terminal escape sequences.

### Design Notes
- All effects are async so they don't block input
- Effects respect a global speed multiplier (accessibility)
- Effects can be disabled via settings (--no-effects flag)
- The meta engine can override effect parameters (make glitch worse, etc.)
