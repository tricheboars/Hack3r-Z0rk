"""Powerline-style Nerd Font prompt — oh-my-bash aesthetic for H@ck3r-Z0rk.

Requires a Nerd Font Mono in the terminal (e.g. JetBrainsMono Nerd Font Mono,
Hack Nerd Font Mono, Fira Code Nerd Font Mono, etc.).  All glyphs are the
1-column "Mono" variants so readline width measurement stays correct.

Two-line layout:
    ▸ Segment bar (line 1) — readline ignores width here, ANSI codes unwrapped
    ▸ Input indicator (line 2) — all ANSI wrapped in \\001\\002, readline measures this
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackerzork.systems.heat import HeatSystem
    from hackerzork.systems.virtual_fs import VirtualFS


# ---------------------------------------------------------------------------
# Nerd Font glyph table (Nerd Font v2/v3 Mono — 1 column each)
# ---------------------------------------------------------------------------

_G = {
    # Powerline separators
    "sep":     "",   # solid right-arrow (segment boundary)
    "sep_r":   "",   # solid left-arrow  (right-side segment)
    "thin":    "",   # thin right-arrow  (same-colour divider)

    # Filesystem / directory icons
    "home":    "",   # fa-home
    "folder":  "",   # fa-folder
    "lock":    "",   # fa-lock       — evidence, .ssh
    "key":     "",   # fa-key        — .ssh keys
    "wrench":  "",   # fa-wrench     — tools
    "mail":    "",   # fa-envelope   — old_emails
    "gear":    "",   # fa-gear       — /etc, dotfiles
    "log":     "",   # fa-file-text  — /var/log
    "game":    "",   # fa-gamepad    — games/
    "note":    "",   # fa-sticky-note— notes/
    "trash":   "",   # fa-trash      — /tmp

    # Status / heat icons
    "term":    "",   # fa-terminal   — user segment
    "bolt":    "",   # fa-bolt       — heat warning
    "warn":    "",   # fa-exclamation-triangle
    "fire":    "",   # fa-fire
    "skull":   "",   # skull         — heat critical
    "eye":     "",   # fa-eye        — surveillance

    # Network
    "net":     "",   # fa-wifi       — connected node
    "plug":    "",   # fa-plug       — disconnected

    # Branch / git-style
    "branch":  "",   # Powerline branch
}


# ---------------------------------------------------------------------------
# ANSI 256-colour helpers
# ---------------------------------------------------------------------------

def _fg(n: int) -> str:
    return f"\033[38;5;{n}m"

def _bg(n: int) -> str:
    return f"\033[48;5;{n}m"

_RST          = "\033[0m"
_DIM          = "\033[2m"

# Foreground palette
_FG_WHITE     = _fg(255)
_FG_LGREY     = _fg(245)   # dim hint text
_FG_BGREEN    = _fg(82)    # bright green — ╰─❯
_FG_CYAN      = _fg(51)

# Background palette indices (also used as fg for separator arrows)
_BG_DKGREEN   = 22     # user/host segment
_BG_DTEAL     = 23     # directory segment  (normal)
_BG_DBLUE     = 17     # directory segment  (restricted)
_BG_AMBER     = 130    # heat: monitored
_BG_ORANGE    = 124    # heat: active_response
_BG_RED       = 88     # heat: hunted / critical
_BG_PURPLE    = 55     # node connected


# ---------------------------------------------------------------------------
# Directory metadata: icon key + optional hint badge
# ---------------------------------------------------------------------------

_DIR_META: dict[str, tuple[str, str | None, int]] = {
    # path                          icon       badge            bg_idx
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
# Internal segment type
# ---------------------------------------------------------------------------

@dataclass
class _Seg:
    text: str   # printable text including icon glyphs
    bg: int     # 256-colour bg index
    hint: str   # dim suffix rendered inside the segment (empty = none)


# ---------------------------------------------------------------------------
# NerdPrompt
# ---------------------------------------------------------------------------

class NerdPrompt:
    """Renders an oh-my-bash Powerline prompt with Nerd Font Mono glyphs.

    All ANSI escape codes on the *second* line (the input line) are wrapped in
    \\001...\\002 so readline measures cursor position correctly.  The first line
    (the decorative segment bar) needs no wrapping — readline ignores its width.
    """

    def __init__(
        self,
        env: dict[str, str],
        fs: VirtualFS | None = None,
        heat: HeatSystem | None = None,
    ) -> None:
        self._env  = env
        self._fs   = fs
        self._heat = heat

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def render(self) -> str:
        """Return the full prompt string.  Safe to pass directly to input()."""
        bar         = self._render_bar(self._build_segs())
        input_line  = f"\001{_fg(_BG_DKGREEN)}\002╰\001{_RST}\002\001{_fg(240)}\002─\001{_RST}\002\001{_FG_BGREEN}\002❯\001{_RST}\002 "
        return f"{bar}\n{input_line}"

    # -------------------------------------------------------------------------
    # Segment construction
    # -------------------------------------------------------------------------

    def _build_segs(self) -> list[_Seg]:
        segs: list[_Seg] = []

        # ── User / host ───────────────────────────────────────────────────────
        user = self._env.get("USER", "user")
        segs.append(_Seg(f" {_G['term']} {user}@hackerzork ", _BG_DKGREEN, ""))

        # ── Directory ─────────────────────────────────────────────────────────
        cwd  = self._env.get("CWD", "/home/user")
        home = self._env.get("HOME", "/home/user")
        display = "~" if cwd == home else (
            "~" + cwd[len(home):] if cwd.startswith(home + "/") else cwd
        )
        icon_key, static_hint, dir_bg = _DIR_META.get(cwd, ("folder", None, _BG_DTEAL))
        hint = static_hint or self._dynamic_hint(cwd)
        segs.append(_Seg(f" {_G[icon_key]} {display} ", dir_bg, hint or ""))

        # ── Heat (only when > 25) ─────────────────────────────────────────────
        heat_seg = self._heat_seg()
        if heat_seg:
            segs.append(heat_seg)

        return segs

    def _heat_seg(self) -> _Seg | None:
        level = float(getattr(self._heat, "level", 0.0)) if self._heat else 0.0
        if level < 25.0:
            return None
        pct = int(level)
        if level < 50.0:
            icon, bg = _G["bolt"],  _BG_AMBER
        elif level < 75.0:
            icon, bg = _G["warn"],  _BG_ORANGE
        elif level < 90.0:
            icon, bg = _G["fire"],  _BG_RED
        else:
            icon, bg = _G["skull"], _BG_RED
        return _Seg(f" {icon} {pct} ", bg, "")

    def _dynamic_hint(self, path: str) -> str | None:
        """Check VFS for anything hint-worthy (encrypted files, etc.)."""
        if self._fs is None:
            return None
        try:
            entries = self._fs.list_dir(path)
        except Exception:
            return None
        enc = sum(1 for e in entries if getattr(e, "encrypted", False))
        if enc:
            return f"{_G['lock']}{enc}enc"
        return None

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def _render_bar(self, segs: list[_Seg]) -> str:
        """First line — ANSI codes are NOT wrapped (readline ignores this line's width)."""
        out = ""
        for i, seg in enumerate(segs):
            # Segment body
            out += f"{_bg(seg.bg)}{_FG_WHITE}{seg.text}"
            # Hint badge (dim, lighter fg, same background)
            if seg.hint:
                out += f"{_DIM}{_fg(245)}{seg.hint} {_RST}{_bg(seg.bg)}"

            # Arrow separator
            if i + 1 < len(segs):
                nxt = segs[i + 1]
                out += f"{_RST}{_fg(seg.bg)}{_bg(nxt.bg)}{_G['sep']}"
            else:
                out += f"{_RST}{_fg(seg.bg)}{_G['sep']}{_RST}"

        return out
