"""First-use teaching footers.

When the player first uses a particular command (or command + flag combination)
the shell appends a one-line footer that explains the concept. Each footer
fires exactly once per save — the trigger is recorded as a flag on
``GameState`` (``taught_<key>``) so it survives save/load.

Footers are short. They go on the line below the actual output, prefixed with
``[ ? ]`` so they're visually distinct from program output. The intent is to
teach the *concept* behind the action, not document the command itself —
``man <cmd>`` and ``learn <topic>`` are the longer forms.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


# A trigger fires when ``predicate(args)`` returns True for the argv of the
# command (after glob expansion, before --help interception).
@dataclass
class TeachRule:
    key: str                               # state flag suffix — taught_<key>
    command: str                           # command name (e.g. "nmap")
    predicate: Callable[[list[str]], bool] # argv test
    message: str                           # one-line footer text


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------

def _always(_args: list[str]) -> bool:
    return True


def _has_flag(flag: str) -> Callable[[list[str]], bool]:
    return lambda args: flag in args


def _has_any_flag(*flags: str) -> Callable[[list[str]], bool]:
    s = set(flags)
    return lambda args: any(a in s for a in args)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
#
# Order matters within a command — the first matching rule fires (and only
# that one, per invocation). Keep messages short — one terminal line.

_RULES: list[TeachRule] = [
    # ─── Filesystem ───────────────────────────────────────────────────────
    TeachRule(
        "ls_long", "ls", _has_any_flag("-l", "-la", "-al", "-lh", "-lah"),
        "ls -l shows mode/owner/size/mtime. The first column is permissions: "
        "type + 3 triplets (user/group/other) of rwx.",
    ),
    TeachRule(
        "ls_hidden", "ls", _has_any_flag("-a", "-la", "-al", "-A"),
        "Files starting with '.' are hidden by convention. -a shows them — "
        "this is where dotfiles, history, and ssh keys live.",
    ),
    TeachRule(
        "chmod", "chmod", _always,
        "chmod uses octal: read=4, write=2, execute=1. 700 = owner full, "
        "group/other nothing. Used to lock secrets so only you can read them.",
    ),
    TeachRule(
        "find_name", "find", _has_flag("-name"),
        "find walks the tree from the start path. -name matches the basename "
        "(quote globs so the shell doesn't expand them first).",
    ),
    TeachRule(
        "find_newer", "find", _has_flag("-newer"),
        "-newer FILE matches files modified after FILE's mtime. Useful for "
        "spotting changes since a known-clean snapshot.",
    ),
    TeachRule(
        "grep_recursive", "grep", _has_any_flag("-r", "-R"),
        "grep -r recurses into directories. Combine with --include='*.log' to "
        "scope, or pipe `find` into `xargs grep` for more control.",
    ),
    TeachRule(
        "sed_inplace", "sed", _has_flag("-i"),
        "sed -i edits in place. The expression 's/OLD/NEW/g' is "
        "substitute/old/new/global. Real sysadmins live in this command.",
    ),
    TeachRule(
        "recover", "recover", _always,
        "Files often aren't gone — they're unlinked. The trash here mirrors "
        "how `rm` works in many shells: directory entry removed, inode kept.",
    ),

    # ─── Pipes & redirects (no specific flag — caught at first 'tee' or
    #     'echo > file'; rest handled by shell parser) ─────────────────────
    TeachRule(
        "tee", "tee", _always,
        "tee splits stdin to both stdout AND a file. Use it when you want to "
        "see output AND log it: `cmd | tee log.txt`.",
    ),

    # ─── Network ──────────────────────────────────────────────────────────
    TeachRule(
        "nmap_sv", "nmap", _has_flag("-sV"),
        "-sV probes for service VERSIONS by sending protocol-specific "
        "payloads. Slower than -sS but tells you WHAT is listening, not just "
        "that something is. Versions reveal CVEs.",
    ),
    TeachRule(
        "nmap", "nmap", _always,
        "A port scan sends packets to TCP/UDP ports and watches for "
        "responses. SYN/ACK = open, RST = closed, no reply = filtered. "
        "Every scan increments your heat — stealth flags reduce it.",
    ),
    TeachRule(
        "ssh", "ssh", _always,
        "SSH = encrypted shell over TCP/22. It auths via password OR a "
        "keypair (your private key in ~/.ssh/, the host's public key in "
        "~/.ssh/known_hosts). Hosts that change keys trigger MITM warnings.",
    ),
    TeachRule(
        "netcat", "nc", _always,
        "netcat ('the swiss army knife of TCP') opens raw sockets. "
        "Listen with -l, connect without. It's how you pipe data between "
        "machines without a protocol.",
    ),
    TeachRule(
        "traceroute", "traceroute", _always,
        "traceroute increments TTL from 1 upward, getting an ICMP "
        "TIME_EXCEEDED back from each router along the path. It maps the "
        "network between you and the target.",
    ),

    # ─── Hacking ──────────────────────────────────────────────────────────
    TeachRule(
        "exploit", "exploit", _always,
        "An exploit is code that abuses a specific vulnerability (the CVE). "
        "Target service version → look up the CVE → run the exploit. "
        "Most real-world ownership starts with stale software.",
    ),
    TeachRule(
        "bruteforce", "bruteforce", _always,
        "Brute force = try every credential until one works. Slow, noisy, "
        "and DETECTABLE. Modern systems rate-limit; this works because the "
        "fictional ones here don't (yet).",
    ),
    TeachRule(
        "privesc", "privesc", _always,
        "Privilege escalation = going from a low-priv shell (e.g. www-data) "
        "to root by abusing a misconfig (sudo NOPASSWD, SUID binary, kernel "
        "exploit). Initial access is half the battle.",
    ),

    # ─── System / processes ───────────────────────────────────────────────
    TeachRule(
        "ps_aux", "ps", _has_any_flag("aux", "-aux", "-ef"),
        "ps aux lists every process with user/PID/CPU/mem. Pipe through "
        "grep to find one. 'sk_*' processes here are SkyNet's watchers — "
        "killing them adds heat AND they respawn.",
    ),
    TeachRule(
        "kill", "kill", _always,
        "kill sends a signal (default SIGTERM=15: please stop). -9 = "
        "SIGKILL: cannot be ignored, no cleanup. Persistence modules respawn "
        "on either, so killing them just buys time.",
    ),

    # ─── Packaging ────────────────────────────────────────────────────────
    TeachRule(
        "apt", "apt", _always,
        "apt manages packages from configured repositories (see "
        "/etc/apt/sources.list.d/). Adding the SHADOW repo unlocks tools "
        "that aren't in mainline — dual-use stuff law-abiding distros omit.",
    ),

    # ─── Save / git ───────────────────────────────────────────────────────
    TeachRule(
        "git_log", "git",
        lambda args: bool(args) and args[0] == "log",
        "git log walks commits backwards from HEAD. The ghost commit at the "
        "root of YOUR history isn't yours — note the author and timestamp.",
    ),
]


# Index by command for fast lookup.
_BY_CMD: dict[str, list[TeachRule]] = {}
for _r in _RULES:
    _BY_CMD.setdefault(_r.command, []).append(_r)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TeachEngine:
    """Picks the right footer for a command invocation, fires it once."""

    def __init__(self, state: Any = None) -> None:
        self._state = state
        # In-memory fallback if there's no GameState (shouldn't happen in the
        # full game, but tests / minimal harnesses run without one).
        self._fired: set[str] = set()

    def maybe_footer(self, command: str, args: list[str]) -> str:
        """Return a footer string if a rule fires, else empty string."""
        rules = _BY_CMD.get(command, [])
        if not rules:
            return ""
        for rule in rules:
            try:
                if not rule.predicate(args):
                    continue
            except Exception:
                continue
            if self._is_taught(rule.key):
                continue
            self._mark_taught(rule.key)
            return f"[dim yellow][ ? ] {rule.message}[/dim yellow]\n[dim]    (silence with: hz_debug flag taught_{rule.key})[/dim]"
        return ""

    # --- helpers ---------------------------------------------------------

    def _flag_name(self, key: str) -> str:
        return f"taught_{key}"

    def _is_taught(self, key: str) -> bool:
        flag = self._flag_name(key)
        if self._state is not None and hasattr(self._state, "has_flag"):
            return self._state.has_flag(flag)
        return flag in self._fired

    def _mark_taught(self, key: str) -> None:
        flag = self._flag_name(key)
        if self._state is not None and hasattr(self._state, "set_flag"):
            self._state.set_flag(flag)
        else:
            self._fired.add(flag)


# Public so tests can introspect/extend.
RULES = _RULES
