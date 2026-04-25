"""Nerd Font detection, auto-install, and download for H@ck3r-Z0rk.

Usage flow at startup
─────────────────────
1. Game calls ``ensure_nerd_font(data_dir, cache_dir)``.
2. Any TTF/OTF dropped in ``data/fonts/`` is installed automatically.
3. If nothing is in data/fonts/, we check system font dirs.
4. We probe the live terminal with a cursor-position query to know whether the
   currently *active* terminal font can actually render Nerd Font glyphs.
5. If active   → returns ``FontResult.active``    (use NF prompt)
   If installed but inactive → ``FontResult.needs_restart``  (show hint)
   If not installed          → ``FontResult.missing``        (offer to download)
6. If the user approves, we download Hack Nerd Font Mono (~1.8 MB) from the
   official nerd-fonts GitHub release and install it.

Supported platforms: macOS, Linux.  Windows falls back gracefully.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import sys
import zipfile
from enum import Enum, auto
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FONT_NAME     = "HackNerdFontMono-Regular"
FONT_FILENAME = f"{FONT_NAME}.ttf"

# Release ZIP from the official nerd-fonts project (Apache 2 / MIT licensed)
_NF_RELEASE   = "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/Hack.zip"
_ZIP_MEMBER   = "HackNerdFontMono-Regular.ttf"

# Glyph used for the terminal probe — Powerline solid right-arrow
_PROBE_GLYPH  = ""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class FontResult(Enum):
    active          = auto()   # Nerd Font glyphs render correctly right now
    needs_restart   = auto()   # Font installed but terminal restart required
    missing         = auto()   # Not installed, user declined or download failed
    downloaded      = auto()   # Just installed this session — restart required


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def _system_font_dir() -> Path | None:
    """Return the user-writable system font directory for this platform."""
    p = platform.system()
    if p == "Darwin":
        return Path.home() / "Library" / "Fonts"
    if p == "Linux":
        return Path.home() / ".local" / "share" / "fonts"
    return None


def _refresh_font_cache() -> None:
    """Refresh the OS font cache after installing new fonts (Linux only)."""
    if platform.system() == "Linux":
        try:
            import subprocess
            font_dir = _system_font_dir()
            subprocess.run(["fc-cache", "-f", str(font_dir)],
                           capture_output=True, timeout=15)
        except Exception:
            pass


def is_nerd_font_installed() -> bool:
    """Return True if any Nerd Font TTF/OTF exists in the system font dir."""
    d = _system_font_dir()
    if d is None or not d.exists():
        return False
    for f in d.iterdir():
        n = f.name.lower()
        if ("nerdfont" in n or "nerd font" in n or "nerdfonts" in n):
            return True
    return False


def install_font(src: Path) -> bool:
    """Copy *src* TTF/OTF into the system font directory.  Returns success."""
    d = _system_font_dir()
    if d is None:
        return False
    try:
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, d / src.name)
        _refresh_font_cache()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Auto-install from data/fonts/
# ---------------------------------------------------------------------------

def install_bundled_fonts(data_fonts_dir: Path) -> list[Path]:
    """Install any TTF/OTF from *data_fonts_dir* that aren't already installed.

    Returns list of fonts successfully installed this call.
    """
    installed: list[Path] = []
    d = _system_font_dir()
    if d is None or not data_fonts_dir.exists():
        return installed
    for src in data_fonts_dir.iterdir():
        if src.suffix.lower() not in (".ttf", ".otf"):
            continue
        dest = d / src.name
        if not dest.exists():
            if install_font(src):
                installed.append(src)
    return installed


# ---------------------------------------------------------------------------
# Terminal probe — cursor position query
# ---------------------------------------------------------------------------

def probe_terminal_nerd_font(timeout: float = 0.4) -> bool:
    """Return True if the live terminal renders Nerd Font glyphs as 1 column wide.

    Sends the Powerline separator glyph (U+E0B0), then ESC[6n (cursor position
    request).  If the cursor advanced by 1 column the glyph is single-width →
    Nerd Font is active.  If it advanced by 2 the terminal treats it as a
    double-width character (replacement box) → no active Nerd Font.

    Returns False on any error or timeout (safe default).
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    if platform.system() == "Windows":
        return False

    try:
        import select
        import termios
        import tty
    except ImportError:
        return False

    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
    except termios.error:
        return False

    response = b""
    try:
        tty.setraw(fd)
        # CR to column 1, print the probe glyph, request cursor position
        sys.stdout.write("\r" + _PROBE_GLYPH + "\033[6n")
        sys.stdout.flush()

        # Read until we get the 'R' that terminates the CPR response
        while True:
            r, _, _ = select.select([sys.stdin], [], [], timeout)
            if not r:
                break
            chunk = os.read(fd, 32)
            response += chunk
            if b"R" in response:
                break
            timeout = 0.1   # tighten timeout after first byte arrives
    except Exception:
        return False
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Erase the probe glyph from the terminal
        sys.stdout.write("\r \r")
        sys.stdout.flush()

    m = re.search(rb"\033\[(\d+);(\d+)R", response)
    if not m:
        return False

    col = int(m.group(2))
    # col 2 → glyph took 1 column  (Nerd Font working)
    # col 3 → glyph took 2 columns (no Nerd Font — box character)
    return col == 2


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_font(cache_dir: Path, on_progress=None) -> Path | None:
    """Download Hack Nerd Font Mono Regular into *cache_dir*.

    *on_progress* is called with (bytes_done, total_bytes) during the download.
    Returns the Path to the installed TTF, or None on failure.
    """
    import urllib.request

    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_ttf = cache_dir / FONT_FILENAME

    if cached_ttf.exists():
        return cached_ttf

    zip_path = cache_dir / "Hack.zip"
    try:
        def _reporthook(block_num, block_size, total_size):
            if on_progress and total_size > 0:
                done = min(block_num * block_size, total_size)
                on_progress(done, total_size)

        urllib.request.urlretrieve(_NF_RELEASE, zip_path, reporthook=_reporthook)

        with zipfile.ZipFile(zip_path) as zf:
            # Find the Mono Regular member (name may vary slightly between releases)
            member = next(
                (n for n in zf.namelist() if "Mono" in n and "Regular" in n and n.endswith(".ttf")),
                None,
            )
            if member is None:
                return None
            data = zf.read(member)

        cached_ttf.write_bytes(data)
        return cached_ttf

    except Exception:
        return None
    finally:
        zip_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# High-level orchestrator
# ---------------------------------------------------------------------------

def ensure_nerd_font(
    data_fonts_dir: Path,
    cache_dir: Path,
    *,
    ask: bool = True,
) -> tuple[FontResult, list[str]]:
    """Check for Nerd Font support and install if possible.

    Returns ``(FontResult, messages)`` where *messages* is a list of
    human-readable strings to display during the boot sequence.
    """
    msgs: list[str] = []

    # 1. Auto-install anything placed in data/fonts/
    bundled = install_bundled_fonts(data_fonts_dir)
    if bundled:
        names = ", ".join(f.name for f in bundled)
        msgs.append(f"[fonts] Installed bundled font(s): {names}")

    # 2. Probe the live terminal
    nf_active = probe_terminal_nerd_font()
    if nf_active:
        return FontResult.active, msgs

    # 3. Font might be installed but terminal not restarted
    if bundled or is_nerd_font_installed():
        msgs.append(
            "[fonts] Nerd Font installed — set your terminal font to "
            f"'{FONT_NAME}' and restart to activate."
        )
        return FontResult.needs_restart, msgs

    # 4. Nothing installed — offer to download
    if not ask:
        return FontResult.missing, msgs

    # Interactive prompt (shown before the shell REPL starts)
    try:
        sys.stdout.write(
            "\n  [fonts] Nerd Font not detected. Download Hack Nerd Font Mono (~7 MB)? [Y/n] "
        )
        sys.stdout.flush()
        ans = sys.stdin.readline().strip().lower()
    except Exception:
        return FontResult.missing, msgs

    if ans in ("n", "no"):
        msgs.append("[fonts] Skipped — using ASCII prompt fallback.")
        return FontResult.missing, msgs

    # Download with simple progress
    _progress: list[str] = []

    def _on_progress(done: int, total: int) -> None:
        pct = done * 100 // total
        bar  = "█" * (pct // 5) + "░" * (20 - pct // 5)
        sys.stdout.write(f"\r  [fonts] Downloading... [{bar}] {pct:3d}%")
        sys.stdout.flush()

    sys.stdout.write("\n")
    ttf = download_font(cache_dir, on_progress=_on_progress)
    sys.stdout.write("\n")

    if ttf is None:
        msgs.append("[fonts] Download failed — using ASCII prompt fallback.")
        return FontResult.missing, msgs

    ok = install_font(ttf)
    if ok:
        msgs.append(
            f"[fonts] {FONT_FILENAME} installed. "
            f"Set your terminal font to '{FONT_NAME}' and restart."
        )
        return FontResult.downloaded, msgs

    msgs.append("[fonts] Install failed — using ASCII prompt fallback.")
    return FontResult.missing, msgs
