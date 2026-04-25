"""Powerline-style Nerd Font prompt — oh-my-bash aesthetic for H@ck3r-Z0rk.

Two rendering modes selected by ``set_nerd_font_active()``:

  • Nerd Font mode   — Powerline separators + NF glyph icons (requires a Nerd
                       Font Mono terminal font, e.g. HackNerdFontMono-Regular)
  • Fallback mode    — same colours, standard-Unicode box-drawing + text badges;
                       looks great in any modern terminal with no special font.

Two-line layout (both modes):
    Line 1  — decorative segment bar; readline ignores width here (no wrapping)
    Line 2  — input indicator ``╰─❯ ``; all ANSI wrapped in \\001\\002
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackerzork.systems.heat import HeatSystem
    from hackerzork.systems.virtual_fs import VirtualFS


# ---------------------------------------------------------------------------
# Module-level Nerd Font flag — set by game.py after detection
# ---------------------------------------------------------------------------

_nerd_font_active: bool = True   # optimistic default; fonts.py corrects this


def set_nerd_font_active(value: bool) -> None:
    global _nerd_font_active
    _nerd_font_active = value


def nerd_font_active() -> bool:
    return _nerd_font_active


# ---------------------------------------------------------------------------
# Nerd Font glyph table (all from the "Mono" variant — 1 column wide)
# ---------------------------------------------------------------------------

_G = {
    # Powerline
    "sep":     "",   # solid right-arrow segment separator
    "thin":    "",   # thin right-arrow same-colour divider

    # Filesystem / directory icons
    "home":    "",   #
    "folder":  "",   #
    "lock":    "",   # fa-lock  ─ evidence, .ssh
    "key":     "",   # fa-key   ─ ssh keys
    "wrench":  "",   # fa-wrench ─ tools
    "mail":    "",   # fa-envelope ─ old_emails
    "gear":    "",   # fa-gear  ─ /etc, dotfiles
    "log":     "",   # fa-file-text ─ /var/log
    "game":    "",   # fa-gamepad
    "note":    "",   # fa-sticky-note
    "trash":   "",   # fa-trash

    # Status / heat
    "term":    "",   # fa-terminal  (user segment)
    "bolt":    "",   # fa-bolt      (heat warning)
    "warn":    "",   # fa-exclamation-triangle
    "fire":    "",   # fa-fire
    "skull":   "",   # skull        (heat critical)
    "eye":     "",   # fa-eye

    # Network
    "net":     "",   # fa-wifi
}

# Fallback glyphs — standard Unicode, no Nerd Font required.
# ⌂ U+2302  ⚡ U+26A1  ⚠ U+26A0  ☠ U+2620  ⚙ U+2699  ✉ U+2709
_F = {
    "sep":    "╌",
    "home":   "⌂",   "folder":  "▸",  "lock":  "▣",
    "key":    "◈",   "wrench":  "⚙",  "mail":  "✉",
    "gear":   "⚙",   "log":     "≡",  "game":  "▶",
    "note":   "✎",   "trash":   "✗",  "term":  "❭",
    "bolt":   "⚡",  "warn":    "⚠",  "fire":  "▲",
    "skull":  "☠",   "eye":     "◉",  "net":   "◈",
}


# ---------------------------------------------------------------------------
# ANSI 256-colour helpers
# ---------------------------------------------------------------------------

def _fg(n: int) -> str:
    return f"\033[38;5;{n}m"

def _bg(n: int) -> str:
    return f"\033[48;5;{n}m"

_RST   = "\033[0m"
_DIM   = "\033[2m"
_BOLD  = "\033[1m"

_FG_WHITE  = _fg(255)
_FG_LGREY  = _fg(245)
_FG_BGREEN = _fg(82)    # ╰─❯ indicator colour

# Background palette indices (shared between modes)
_BG_DKGREEN  = 22    # user/host segment
_BG_DTEAL    = 23    # directory — normal
_BG_DBLUE    = 17    # directory — restricted / classified
_BG_AMBER    = 130   # heat: monitored
_BG_ORANGE   = 124   # heat: active response
_BG_RED      = 88    # heat: hunted / critical


# ---------------------------------------------------------------------------
# Directory metadata  →  (icon_key, static_hint, bg_index)
# ---------------------------------------------------------------------------

_DIR_META: dict[str, tuple[str, str | None, int]] = {
    "/home/user":               ("home",   None,          _BG_DTEAL),
    "/home/user/.ssh":          ("key",    "keys",        _BG_DBLUE),
    "/home/user/evidence":      ("lock",   "classified",  _BG_DBLUE),
    "/home/user/.old_emails":   ("mail",   "archived",    _BG_DTEAL),
    "/home/user/tools":         ("wrench", None,          _BG_DTEAL),
    "/home/user/notes":         ("note",   None,          _BG_DTEAL),
    "/home/user/games":         ("game",   None,          _BG_DTEAL),
    "/home/user/.dotfiles":     ("gear",   None,          _BG_DTEAL),
    "/home/user/.config":       ("gear",   None,          _BG_DTEAL),
    "/var/log":                 ("log",    "logs",        _BG_DTEAL),
    "/etc":                     ("gear",   "sys",         _BG_DBLUE),
    "/tmp":                     ("trash",  "volatile",    _BG_DTEAL),
}


# ---------------------------------------------------------------------------
# Segment type
# ---------------------------------------------------------------------------

@dataclass
class _Seg:
    text: str    # printable content (icon + label)
    bg:   int    # 256-colour bg index
    hint: str    # dim badge suffix (empty = none)


# ---------------------------------------------------------------------------
# NerdPrompt
# ---------------------------------------------------------------------------

class NerdPrompt:
    """Renders an oh-my-bash Powerline prompt in either NF or fallback mode."""

    def __init__(
        self,
        env:  dict[str, str],
        fs:   VirtualFS | None  = None,
        heat: HeatSystem | None = None,
    ) -> None:
        self._env  = env
        self._fs   = fs
        self._heat = heat

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def render(self) -> str:
        """Return the full two-line prompt string for readline / input()."""
        segs       = self._build_segs()
        bar        = self._render_nf(segs) if _nerd_font_active else self._render_fallback(segs)
        input_line = (
            f"\001{_fg(_BG_DKGREEN)}\002╰"
            f"\001{_RST}\002"
            f"\001{_fg(240)}\002─"
            f"\001{_RST}\002"
            f"\001{_FG_BGREEN}\002❯"
            f"\001{_RST}\002 "
        )
        return f"{bar}\n{input_line}"

    # -------------------------------------------------------------------------
    # Segment construction (shared between both render modes)
    # -------------------------------------------------------------------------

    def _build_segs(self) -> list[_Seg]:
        segs: list[_Seg] = []

        # User / host
        user = self._env.get("USER", "user")
        icon = _G["term"] if _nerd_font_active else _F["term"]
        segs.append(_Seg(f" {icon} {user}@hackerzork ", _BG_DKGREEN, ""))

        # Directory
        cwd  = self._env.get("CWD", "/home/user")
        home = self._env.get("HOME", "/home/user")
        display = (
            "~"          if cwd == home else
            "~" + cwd[len(home):] if cwd.startswith(home + "/") else
            cwd
        )
        icon_key, static_hint, dir_bg = _DIR_META.get(cwd, ("folder", None, _BG_DTEAL))
        hint  = static_hint or self._dynamic_hint(cwd)
        glyph = _G[icon_key] if _nerd_font_active else _F[icon_key]
        segs.append(_Seg(f" {glyph} {display} ", dir_bg, hint or ""))

        # Heat segment (hidden when < 25)
        heat_seg = self._heat_seg()
        if heat_seg:
            segs.append(heat_seg)

        return segs

    def _heat_seg(self) -> _Seg | None:
        level = float(getattr(self._heat, "level", 0.0)) if self._heat else 0.0
        if level < 25.0:
            return None
        pct = int(level)
        if _nerd_font_active:
            if level < 50:   icon, bg = _G["bolt"],  _BG_AMBER
            elif level < 75: icon, bg = _G["warn"],  _BG_ORANGE
            elif level < 90: icon, bg = _G["fire"],  _BG_RED
            else:            icon, bg = _G["skull"], _BG_RED
        else:
            if level < 50:   icon, bg = _F["bolt"],  _BG_AMBER
            elif level < 75: icon, bg = _F["warn"],  _BG_ORANGE
            elif level < 90: icon, bg = _F["fire"],  _BG_RED
            else:            icon, bg = _F["skull"], _BG_RED
        return _Seg(f" {icon} {pct} ", bg, "")

    def _dynamic_hint(self, path: str) -> str | None:
        """Peek into the VFS for encrypted files → show badge."""
        if self._fs is None:
            return None
        try:
            entries = self._fs.list_dir(path)
        except Exception:
            return None
        enc = sum(1 for e in entries if getattr(e, "encrypted", False))
        if enc:
            lock = _G["lock"] if _nerd_font_active else _F["lock"]
            return f"{lock} {enc}enc"
        return None

    # -------------------------------------------------------------------------
    # Nerd Font rendering  (Powerline ▶ separators)
    # -------------------------------------------------------------------------

    def _render_nf(self, segs: list[_Seg]) -> str:
        """Segment bar with Powerline solid-arrow separators.

        ANSI codes here do NOT need \\001\\002 wrapping — readline ignores the
        first line entirely for width measurement.
        """
        out = ""
        for i, seg in enumerate(segs):
            out += f"{_bg(seg.bg)}{_FG_WHITE}{seg.text}"
            if seg.hint:
                out += f"{_DIM}{_FG_LGREY} {seg.hint} {_RST}{_bg(seg.bg)}"
            if i + 1 < len(segs):
                nxt = segs[i + 1]
                out += f"{_RST}{_fg(seg.bg)}{_bg(nxt.bg)}{_G['sep']}"
            else:
                out += f"{_RST}{_fg(seg.bg)}{_G['sep']}{_RST}"
        return out

    # -------------------------------------------------------------------------
    # Fallback rendering  (standard Unicode, no Nerd Font required)
    # -------------------------------------------------------------------------

    def _render_fallback(self, segs: list[_Seg]) -> str:
        """Coloured segment bar using standard-Unicode separators.

        Uses the same 256-colour palette as NF mode so it looks equally polished
        on any modern terminal — just without the Powerline arrow separators.
        """
        out = ""
        for i, seg in enumerate(segs):
            out += f"{_bg(seg.bg)}{_FG_WHITE}{seg.text}"
            if seg.hint:
                out += f"{_DIM}{_FG_LGREY}({seg.hint}){_RST}{_bg(seg.bg)} "
            if i + 1 < len(segs):
                # Thin coloured bridge between segments
                nxt = segs[i + 1]
                out += f"{_RST}{_fg(seg.bg)} {_fg(240)}╌{_fg(nxt.bg)} {_RST}"
            else:
                # Trailing cap
                out += f"{_RST}"
        return out
