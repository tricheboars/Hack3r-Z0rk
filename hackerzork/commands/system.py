"""System / utility commands: whoami, uname, ps, top, man, history, clear,
env, export, alias, echo, date, df, du, free, lscpu, lsblk, id, groups,
kill, killall, pstree, htop, passwd, useradd, userdel, usermod,
groupadd, groupdel."""
from __future__ import annotations

from datetime import datetime

from hackerzork.engine.command_registry import CommandContext, DEFAULT_REGISTRY, register_command

_CAT = "system"

# ---------------------------------------------------------------------------
# Fake OS identity
# ---------------------------------------------------------------------------

_OS_NAME = "Linux"
_OS_VERSION = "6.6.6-sk-patched"
# Build date is Mar 14 23:59:01 — same timestamp as syslog.1 monitor cron pulse
# The kernel was patched the night before the intrusion. This is not a coincidence.
_KERNEL = "6.6.6-sk-patched #1 SMP Thu Mar 14 23:59:01 UTC 2026"
_MACHINE = "x86_64"
_HOSTNAME = "burner"
_USER = "user"

# The SkyNet IP — appears in auth.log, /etc/hosts, ps, ss, netstat, date last-login.
# Every place it appears is another thread the player can pull.
_SKYNET_IP = "45.152.66.201"

# Session tracking ID injected by the OS before the player ever touched the keyboard.
# Shows up in `env`. Implies SkyNet pre-authenticated this session.
_SK_SID = "sk-9a7f3c2d-8b1e-4f6a-9c3d-2e7b1a5f4c8e"

# ---------------------------------------------------------------------------
# Fake process table
# ---------------------------------------------------------------------------
# (pid, tty, stat, cpu%, mem%, time, command)
_PROCESSES: list[tuple[int, str, str, str, str, str, str]] = [
    (1,    "?",     "Ss",  "0.0", "0.1", "0:00.42", "/sbin/init"),
    (2,    "?",     "S",   "0.0", "0.0", "0:00.00", "[kthreadd]"),
    (3,    "?",     "S<",  "0.0", "0.0", "0:00.00", "[rcu_gp]"),
    (9,    "?",     "S<",  "0.0", "0.0", "0:00.00", "[mm_percpu_wq]"),
    (11,   "?",     "S",   "0.0", "0.0", "0:00.14", "[migration/0]"),
    (84,   "?",     "Ss",  "0.0", "0.1", "0:00.08", "/usr/lib/systemd/systemd-journald"),
    (183,  "?",     "Ss",  "0.0", "0.2", "0:01.12", "sshd: /usr/sbin/sshd -D"),
    (241,  "?",     "Ss",  "0.0", "0.3", "0:00.04", "/usr/sbin/cron -f"),
    (284,  "?",     "Ss",  "0.0", "0.4", "0:00.09", "nginx: master process /usr/sbin/nginx"),
    (285,  "?",     "S",   "0.0", "0.2", "0:00.03", "nginx: worker process"),
    (512,  "?",     "Ss",  "0.0", "0.1", "0:00.22", "/usr/sbin/rsyslogd -n"),
    # SkyNet persistence — all rooted before player booted. PIDs 891-893 are core.
    # sk_comms talks to the same IP that SSHed in on Mar 15 (see auth.log, /etc/hosts).
    (891,  "?",     "Sl",  "0.1", "1.2", "0:11.37", "sk_watchdog --interval=60 --host=sky.internal"),
    (892,  "?",     "S",   "0.0", "0.4", "0:00.02", f"sk_comms --relay={_SKYNET_IP} --enc"),
    (893,  "?",     "S",   "0.0", "0.3", "0:00.01", "sk_uplink --silent --beacon"),
    (1201, "?",     "Ss",  "0.0", "0.2", "0:00.31", "/usr/lib/systemd/systemd --user"),
    (1337, "pts/0", "Ss",  "0.0", "0.5", "0:00.18", "-bash"),
    (1338, "pts/0", "R+",  "0.0", "0.1", "0:00.00", "ps"),
]

# SkyNet-adjacent PIDs — killing these adds heat and they respawn.
# They always come back. That's the point.
_SKYNET_PIDS: dict[int, str] = {
    891: "sk_watchdog",
    892: "sk_comms",
    893: "sk_uplink",
    # Escalation processes — appear as heat rises; killable (+8 heat, respawn)
    894: "sk_trace",
    895: "sk_identify",
    896: "sk_burn",
}

# Escalation processes — appear when heat crosses thresholds.
# Each one is a narrative escalation: watching → tracing → identifying → burning.
# (heat_threshold, pid, tty, stat, cpu, mem, time, command)
_ESCALATION_PROCS: list[tuple[float, int, str, str, str, str, str, str]] = [
    (25.0, 894, "?", "S",  "0.0", "0.2", "0:00.03", "sk_trace --keylog --target=1337"),
    (50.0, 895, "?", "S",  "0.1", "0.4", "0:01.44", f"sk_identify --pull={_SKYNET_IP}"),
    (75.0, 896, "?", "Sl", "0.2", "0.8", "0:04.11", "sk_burn --stage=2 --exposure=imminent"),
]

_TOP_HEADER = """\
Linux 6.6.6-sk-patched  up 0:42,  1 user,  load average: 0.04, 0.09, 0.03
Tasks:  18 total,   1 running,  17 sleeping,   0 stopped,   0 zombie
%Cpu(s):  0.3 us,  0.1 sy,  0.0 ni, 99.5 id,  0.0 wa,  0.1 hi,  0.0 si
MiB Mem:   7812.0 total,   6140.2 free,    902.4 used,    769.4 buff/cache
MiB Swap:  2048.0 total,   2048.0 free,      0.0 used.   6687.4 avail Mem

  PID USER       PR  NI    VIRT      %CPU  %MEM     TIME+ COMMAND"""

# (pid, user, pr, ni, virt, command)
_TOP_ROWS: list[tuple[int, str, str, str, str, str]] = [
    (891,  "root",    "20", "0", "112.4m", "sk_watchdog --interval=60 --host=sky.internal"),
    (1337, _USER,     "20", "0",  "23.1m", "-bash"),
    (1,    "root",    "20", "0",  "12.2m", "/sbin/init"),
    (183,  "root",    "20", "0",  "15.6m", "sshd: /usr/sbin/sshd -D"),
    (284,  "www-data","20", "0",  "18.8m", "nginx: master process"),
    (892,  "root",    "20", "0",   "8.4m", f"sk_comms --relay={_SKYNET_IP} --enc"),
    (893,  "root",    "20", "0",   "6.1m", "sk_uplink --silent --beacon"),
    (512,  "root",    "20", "0",   "9.8m", "/usr/sbin/rsyslogd -n"),
    (1338, _USER,     "20", "0",   "5.2m", "top"),
]

# Top rows for escalated processes (keyed by PID)
_TOP_ESCALATION: dict[int, tuple[str, str, str, str, str]] = {
    894: ("root", "20", "0",  "6.3m", "sk_trace --keylog --target=1337"),
    895: ("root", "20", "0",  "9.7m", f"sk_identify --pull={_SKYNET_IP}"),
    896: ("root", "20", "0", "14.2m", "sk_burn --stage=2 --exposure=imminent"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_flags(args: list[str]) -> tuple[set[str], list[str]]:
    flags: set[str] = set()
    positional: list[str] = []
    for a in args:
        if a.startswith("--") and len(a) > 2:
            flags.add(a[2:])
        elif a.startswith("-") and len(a) > 1 and not a[1:].isdigit():
            for ch in a[1:]:
                flags.add(ch)
        else:
            positional.append(a)
    return flags, positional


def _user(ctx: CommandContext) -> str:
    return ctx.env.get("USER", _USER)


def _hostname(ctx: CommandContext) -> str:
    return ctx.env.get("HOSTNAME", _HOSTNAME)


def _get_aliases(ctx: CommandContext) -> dict[str, str]:
    return {k[6:]: v for k, v in ctx.env.items() if k.startswith("ALIAS_")}


def _set_alias(ctx: CommandContext, name: str, value: str) -> None:
    ctx.env[f"ALIAS_{name}"] = value


def _killed_pids(ctx: CommandContext) -> set[int]:
    raw = ctx.env.get("_KILLED_PIDS", "")
    return {int(p) for p in raw.split(",") if p.strip().isdigit()}


def _record_kill(ctx: CommandContext, pid: int) -> None:
    dead = _killed_pids(ctx)
    dead.add(pid)
    ctx.env["_KILLED_PIDS"] = ",".join(str(p) for p in sorted(dead))


def _heat_level(ctx: CommandContext) -> float:
    if ctx.heat is not None:
        # HeatSystem stores the value as .level; fall back to .current for compat
        return getattr(ctx.heat, "level", getattr(ctx.heat, "current", 0.0))
    return 0.0


def _active_procs(ctx: CommandContext) -> list[tuple]:
    dead = _killed_pids(ctx)
    heat = _heat_level(ctx)
    base = [p for p in _PROCESSES if p[0] not in dead]
    extras = [
        (pid, tty, stat, cpu, mem, t, cmd)
        for threshold, pid, tty, stat, cpu, mem, t, cmd in _ESCALATION_PROCS
        if heat >= threshold
    ]
    return base + extras


def _du_walk(ctx: CommandContext, path: str) -> int:
    try:
        node = ctx.fs._get_node(path)
        if not node.is_dir:
            return len((node.content or "").encode())
        total = 0
        for name in node.children:
            try:
                total += _du_walk(ctx, path.rstrip("/") + "/" + name)
            except Exception:
                pass
        return total
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@register_command(
    name="whoami",
    usage="whoami",
    help_text="Print the current user name",
    category=_CAT,
)
def cmd_whoami(ctx: CommandContext, args: list[str]) -> str:
    return _user(ctx)


@register_command(
    name="uname",
    usage="uname [-a | -s | -r | -m | -n | -v]",
    help_text="Print system information",
    category=_CAT,
)
def cmd_uname(ctx: CommandContext, args: list[str]) -> str:
    flags, _ = _parse_flags(args)

    if not flags or "a" in flags:
        return f"{_OS_NAME} {_hostname(ctx)} {_OS_VERSION} {_KERNEL} {_MACHINE} GNU/Linux"

    parts: list[str] = []
    if "s" in flags:
        parts.append(_OS_NAME)
    if "n" in flags:
        parts.append(_hostname(ctx))
    if "r" in flags:
        parts.append(_OS_VERSION)
    if "v" in flags:
        parts.append(_KERNEL)
    if "m" in flags:
        parts.append(_MACHINE)
    return " ".join(parts) if parts else _OS_NAME


@register_command(
    name="ps",
    usage="ps [aux | -ef]",
    help_text="Report a snapshot of current processes",
    category=_CAT,
)
def cmd_ps(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)

    # Support: ps aux grep sk_  (convenience piped-style)
    grep_pattern: str | None = None
    if "grep" in positional:
        idx = positional.index("grep")
        if idx + 1 < len(positional):
            grep_pattern = positional[idx + 1]

    base = _active_procs(ctx)
    procs = (
        [p for p in base if grep_pattern.lower() in p[6].lower()]
        if grep_pattern
        else base
    )

    wide = "u" in flags or "f" in flags or not flags
    if wide:
        header = f"{'PID':>6}  {'TTY':<8}  {'STAT':<5}  {'%CPU':>5}  {'%MEM':>5}  {'TIME':>10}  COMMAND"
        rows = [
            f"{pid:>6}  {tty:<8}  {stat:<5}  {cpu:>5}  {mem:>5}  {t:>10}  {cmd}"
            for pid, tty, stat, cpu, mem, t, cmd in procs
        ]
    else:
        header = f"{'PID':>6}  {'TTY':<8}  {'TIME':>10}  CMD"
        rows = [
            f"{pid:>6}  {tty:<8}  {t:>10}  {cmd.split()[0]}"
            for pid, tty, stat, cpu, mem, t, cmd in procs
        ]

    return "\n".join([header] + rows)


@register_command(
    name="top",
    usage="top",
    help_text="Display processes (snapshot — not interactive)",
    category=_CAT,
)
def cmd_top(ctx: CommandContext, args: list[str]) -> str:
    dead = _killed_pids(ctx)
    heat = _heat_level(ctx)

    rows = [
        f"{pid:>6}  {user:<9}  {pr:>3}  {ni:>3}  {virt:>8}  {cmd}"
        for pid, user, pr, ni, virt, cmd in _TOP_ROWS
        if pid not in dead
    ]

    # Escalation rows appear as heat rises
    for threshold, pid in [(25.0, 894), (50.0, 895), (75.0, 896)]:
        if heat >= threshold and pid not in dead and pid in _TOP_ESCALATION:
            user, pr, ni, virt, cmd = _TOP_ESCALATION[pid]
            rows.append(f"{pid:>6}  {user:<9}  {pr:>3}  {ni:>3}  {virt:>8}  {cmd}")

    return _TOP_HEADER + "\n" + "\n".join(rows)


@register_command(
    name="man",
    usage="man <command>",
    help_text="Show manual page for a registered command",
    category=_CAT,
)
def cmd_man(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return "What manual page do you want?"

    name = args[0]
    reg = ctx.registry if ctx.registry is not None else DEFAULT_REGISTRY

    if name not in reg:
        return f"No manual entry for {name}"
    return reg.get_help(name)


_HISTORY_GAP_MSG = (
    "[-- 44 commands redacted — external write on 2026-03-15 02:52:44 --]"
)
# The gap starts at line 851 (prior len + 1) and skips 44 entries.
# One of those was the truncated shadow source echo visible in .bash_history.


@register_command(
    name="history",
    usage="history [n]",
    help_text="Display or search command history",
    category=_CAT,
)
def cmd_history(ctx: CommandContext, args: list[str]) -> str:
    limit: int | None = None
    if args:
        try:
            limit = int(args[0])
        except ValueError:
            return f"history: {args[0]}: numeric argument required"

    # Load prior session from VFS .bash_history (diegetic record of March 15)
    prior: list[str] = []
    if ctx.fs is not None:
        try:
            raw = ctx.fs.read_file("/home/user/.bash_history")
            prior = [ln for ln in raw.splitlines() if ln.strip()]
        except Exception:
            pass

    # Current session commands from CommandHistory object or env fallback
    hist_obj = ctx.history
    if hist_obj is not None:
        session = hist_obj.get_all()
    else:
        raw = ctx.env.get("HISTORY", "")
        session = [ln for ln in raw.splitlines() if ln.strip()]

    # Build the combined numbered list: prior + gap + session
    result: list[str] = []
    n = 841  # Start prior history at 841 — implies 840 entries before, 44 deleted

    for cmd in prior:
        result.append(f"  {n:>4}  {cmd}")
        n += 1

    # Gap only exists when we have a prior session to anchor it against
    if prior:
        n += 44
        result.append(_HISTORY_GAP_MSG)

    for cmd in session:
        result.append(f"  {n:>4}  {cmd}")
        n += 1

    all_lines = result
    if limit is not None:
        all_lines = result[-limit:]

    return "\n".join(all_lines) if all_lines else ""


@register_command(
    name="clear",
    usage="clear",
    help_text="Clear the terminal screen",
    category=_CAT,
)
def cmd_clear(ctx: CommandContext, args: list[str]) -> str:
    return "\033[2J\033[H"


@register_command(
    name="env",
    usage="env",
    help_text="Print all environment variables",
    category=_CAT,
)
def cmd_env(ctx: CommandContext, args: list[str]) -> str:
    # _SK_SID is pre-loaded by the OS before the player session started.
    # It is a SkyNet session tracking ID. The player did not set this.
    # Discovering it via `env` is the first hint that the session itself was pre-authorized.
    if "_SK_SID" not in ctx.env:
        ctx.env["_SK_SID"] = _SK_SID
    return "\n".join(f"{k}={v}" for k, v in sorted(ctx.env.items()))


@register_command(
    name="export",
    usage="export NAME=VALUE [NAME=VALUE ...]",
    help_text="Set or export environment variables",
    category=_CAT,
)
def cmd_export(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return cmd_env(ctx, [])

    errors: list[str] = []
    for token in args:
        if "=" in token:
            key, _, val = token.partition("=")
            key = key.strip()
            if not key.isidentifier():
                errors.append(f"export: `{key}': not a valid identifier")
            else:
                ctx.env[key] = val
        # bare "export VAR" with no value — ignore (already in env or absent)
    return "\n".join(errors)


@register_command(
    name="alias",
    usage="alias [name[='value']] ...",
    help_text="Define or display command aliases",
    category=_CAT,
)
def cmd_alias(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        aliases = _get_aliases(ctx)
        if not aliases:
            return ""
        return "\n".join(f"alias {k}='{v}'" for k, v in sorted(aliases.items()))

    output: list[str] = []
    for token in args:
        if "=" in token:
            name, _, raw_val = token.partition("=")
            name = name.strip()
            val = raw_val.strip().strip("'\"")
            _set_alias(ctx, name, val)
        else:
            val = _get_aliases(ctx).get(token)
            if val is None:
                output.append(f"bash: alias: {token}: not found")
            else:
                output.append(f"alias {token}='{val}'")
    return "\n".join(output)


@register_command(
    name="echo",
    usage="echo [-n] [-e] [text ...]",
    help_text="Display a line of text",
    category=_CAT,
)
def cmd_echo(ctx: CommandContext, args: list[str]) -> str:
    flags, rest = _parse_flags(args)
    text = " ".join(rest)
    if "e" in flags:
        text = text.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
    # bash echo always appends \n unless -n flag is set
    if "n" not in flags:
        text += "\n"
    return text


@register_command(
    name="date",
    usage="date [+FORMAT]",
    help_text="Print the system date and time",
    category=_CAT,
)
def cmd_date(ctx: CommandContext, args: list[str]) -> str:
    now = datetime.now()

    if args and args[0].startswith("+"):
        fmt = args[0][1:]
        replacements = {
            "%Y": now.strftime("%Y"),
            "%m": now.strftime("%m"),
            "%d": now.strftime("%d"),
            "%H": now.strftime("%H"),
            "%M": now.strftime("%M"),
            "%S": now.strftime("%S"),
            "%A": now.strftime("%A"),
            "%B": now.strftime("%B"),
            "%s": str(int(now.timestamp())),
        }
        for token, value in replacements.items():
            fmt = fmt.replace(token, value)
        return fmt

    date_str = now.strftime("%a %b %d %H:%M:%S UTC %Y").strip()
    # The last login was from the SkyNet IP — technically accurate.
    # The session on Mar 15 at 02:52 was the last login before the 42-day gap.
    return f"{date_str}\nLast login: Sun Mar 15 02:52:44 2026 from {_SKYNET_IP}"


# ---------------------------------------------------------------------------
# df
# ---------------------------------------------------------------------------

_DF_STATIC = [
    # (filesystem, 1k-blocks, used, available, use%, mount)
    ("/dev/sda1",  51200000, 8741824, 42458176, "17%", "/"),
    ("tmpfs",       4004864,     132,  4004732,  "1%", "/dev/shm"),
    ("/dev/sda2",   1048576,  412672,   635904, "40%", "/var"),
    ("tmpfs",        400488,    4812,   395676,  "2%", "/run"),
]


@register_command(
    name="df",
    usage="df [-h] [path]",
    help_text="Report filesystem disk space usage",
    category=_CAT,
)
def cmd_df(ctx: CommandContext, args: list[str]) -> str:
    flags, _ = _parse_flags(args)
    human = "h" in flags

    def _fmt(kb: int) -> str:
        if not human:
            return str(kb)
        if kb >= 1_048_576:
            return f"{kb / 1_048_576:.1f}G"
        if kb >= 1_024:
            return f"{kb / 1_024:.1f}M"
        return f"{kb}K"

    header = f"{'Filesystem':<16}  {'1K-blocks':>12}  {'Used':>10}  {'Available':>10}  {'Use%':>5}  Mounted on"
    if human:
        header = f"{'Filesystem':<16}  {'Size':>6}  {'Used':>6}  {'Avail':>6}  {'Use%':>5}  Mounted on"

    rows = [header]
    for fs, total, used, avail, pct, mount in _DF_STATIC:
        if human:
            rows.append(
                f"{fs:<16}  {_fmt(total):>6}  {_fmt(used):>6}  {_fmt(avail):>6}  {pct:>5}  {mount}"
            )
        else:
            rows.append(
                f"{fs:<16}  {total:>12}  {used:>10}  {avail:>10}  {pct:>5}  {mount}"
            )

    # If toolkit is wired, add a bandwidth entry
    tk = getattr(ctx, "toolkit", None)
    if tk is not None:
        used_bw = 50_000 - tk.bandwidth_remaining_kb
        pct_bw = f"{int(used_bw / 500)}%"
        if human:
            rows.append(
                f"{'net://shadow':<16}  {'48.8M':>6}  {_fmt(used_bw):>6}  {_fmt(tk.bandwidth_remaining_kb):>6}  {pct_bw:>5}  /proc/net/bw"
            )
        else:
            rows.append(
                f"{'net://shadow':<16}  {50000:>12}  {used_bw:>10}  {tk.bandwidth_remaining_kb:>10}  {pct_bw:>5}  /proc/net/bw"
            )

    return "\n".join(rows)


# ---------------------------------------------------------------------------
# du
# ---------------------------------------------------------------------------


@register_command(
    name="du",
    usage="du [-sh] [path...]",
    help_text="Estimate file space usage",
    category=_CAT,
)
def cmd_du(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    human = "h" in flags
    summarize = "s" in flags

    if ctx.fs is None:
        return "du: filesystem not available"

    paths = positional if positional else [ctx.env.get("CWD", "/home/user")]

    def _fmt(b: int) -> str:
        kb = max(1, b // 1024)
        if not human:
            return str(kb)
        if kb >= 1_048_576:
            return f"{kb / 1_048_576:.1f}G"
        if kb >= 1_024:
            return f"{kb / 1_024:.1f}M"
        return f"{kb}K"

    from hackerzork.commands.filesystem import _resolve

    lines: list[str] = []
    for path_str in paths:
        path = _resolve(ctx, path_str) if not path_str.startswith("/") else path_str
        try:
            node = ctx.fs._get_node(path)
        except Exception:
            lines.append(f"du: cannot access '{path_str}': No such file or directory")
            continue

        if summarize or not node.is_dir:
            total = _du_walk(ctx, path)
            lines.append(f"{_fmt(total)}\t{path_str}")
        else:
            # Walk one level of subdirs
            for name in sorted(getattr(node, "children", {})):
                child_path = path.rstrip("/") + "/" + name
                sub = _du_walk(ctx, child_path)
                lines.append(f"{_fmt(sub)}\t{path_str.rstrip('/')}/{name}")
            total = _du_walk(ctx, path)
            lines.append(f"{_fmt(total)}\t{path_str}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# free
# ---------------------------------------------------------------------------

_FREE_OUTPUT = """\
               total        used        free      shared  buff/cache   available
Mem:         7999940      924716     5802344       21312     1272880     6748188
Swap:        2097148           0     2097148"""

_FREE_HUMAN = """\
               total        used        free      shared  buff/cache   available
Mem:           7.6Gi       903Mi       5.5Gi        20Mi       1.2Gi       6.4Gi
Swap:          2.0Gi          0B       2.0Gi"""


@register_command(
    name="free",
    usage="free [-h]",
    help_text="Display amount of free and used memory",
    category=_CAT,
)
def cmd_free(ctx: CommandContext, args: list[str]) -> str:
    flags, _ = _parse_flags(args)
    return _FREE_HUMAN if "h" in flags else _FREE_OUTPUT


# ---------------------------------------------------------------------------
# lscpu
# ---------------------------------------------------------------------------

_LSCPU_OUTPUT = """\
Architecture:                    x86_64
CPU op-mode(s):                  32-bit, 64-bit
Address sizes:                   39 bits physical, 48 bits virtual
Byte Order:                      Little Endian
CPU(s):                          4
On-line CPU(s) list:             0-3
Thread(s) per core:              2
Core(s) per socket:              2
Socket(s):                       1
NUMA node(s):                    1
Vendor ID:                       GenuineIntel
CPU family:                      6
Model:                           158
Model name:                      Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz
CPU MHz:                         2600.000
CPU max MHz:                     4500.0000
CPU min MHz:                     400.0000
BogoMIPS:                        5199.99
Virtualization:                  VT-x
L1d cache:                       128 KiB (4 instances)
L1i cache:                       128 KiB (4 instances)
L2 cache:                        1 MiB (4 instances)
L3 cache:                        12 MiB (1 instance)
NUMA node0 CPU(s):               0-3"""


@register_command(
    name="lscpu",
    usage="lscpu",
    help_text="Display CPU architecture information",
    category=_CAT,
)
def cmd_lscpu(ctx: CommandContext, args: list[str]) -> str:
    return _LSCPU_OUTPUT


# ---------------------------------------------------------------------------
# lsblk
# ---------------------------------------------------------------------------

_LSBLK_OUTPUT = """\
NAME   MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
sda      8:0    0    50G  0 disk
├─sda1   8:1    0    48G  0 part /
└─sda2   8:2    0     1G  0 part /var
sdb      8:16   1     0B  0 disk
sr0     11:0    1  1024M  0 rom"""


@register_command(
    name="lsblk",
    usage="lsblk",
    help_text="List block devices",
    category=_CAT,
)
def cmd_lsblk(ctx: CommandContext, args: list[str]) -> str:
    output = _LSBLK_OUTPUT
    # At heat >= 50, a hidden block device appears — sk_persistent_module installed
    # by SkyNet during the Mar 15 intrusion. It was always there; now it's visible.
    if _heat_level(ctx) >= 50.0:
        output += "\nskx0   253:0   0  512M  0 disk  [ENCRYPTED] [sk_persistent_module_v3]"
    return output


# ---------------------------------------------------------------------------
# id
# ---------------------------------------------------------------------------


@register_command(
    name="id",
    usage="id [user]",
    help_text="Print user and group identity",
    category=_CAT,
)
def cmd_id(ctx: CommandContext, args: list[str]) -> str:
    user = _user(ctx)
    return f"uid=1000({user}) gid=1000({user}) groups=1000({user}),4(adm),24(cdrom),27(sudo),30(dip)"


# ---------------------------------------------------------------------------
# groups
# ---------------------------------------------------------------------------


@register_command(
    name="groups",
    usage="groups [user]",
    help_text="Print the groups a user is in",
    category=_CAT,
)
def cmd_groups(ctx: CommandContext, args: list[str]) -> str:
    user = _user(ctx)
    return f"{user} adm cdrom sudo dip"


# ---------------------------------------------------------------------------
# kill
# ---------------------------------------------------------------------------


@register_command(
    name="kill",
    usage="kill [-9 | -SIGKILL] <pid> [<pid>...]",
    help_text="Terminate processes by PID",
    category=_CAT,
)
def cmd_kill(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return "Usage: kill [-9] <pid> [<pid>...]"

    # Strip signal flags (-9, -SIGKILL, -15, etc.) from the pid list
    pids_str = [a for a in args if not a.startswith("-")]
    if not pids_str:
        return "kill: no PID specified"

    lines: list[str] = []
    for tok in pids_str:
        try:
            pid = int(tok)
        except ValueError:
            lines.append(f"kill: {tok!r}: arguments must be process or job IDs")
            continue

        # Check process exists — look in base table and heat-escalation table
        proc = next((p for p in _PROCESSES if p[0] == pid), None)
        # Also accept escalation PIDs (894/895/896) when they're active
        if proc is None and pid not in _SKYNET_PIDS:
            lines.append(f"kill: ({pid}) - No such process")
            continue

        cmd_str = (proc[6] if proc else _SKYNET_PIDS.get(pid, str(pid))).split()[0]

        if pid in _SKYNET_PIDS:
            name = _SKYNET_PIDS[pid]
            _record_kill(ctx, pid)
            lines.append(f"[{pid}] {name}: signal 9 received.")
            lines.append(f"[{pid}] {name}: terminated.")
            if ctx.heat is not None:
                ctx.heat.add_heat(8.0, source="skynet_process_kill")
            if ctx.events:
                ctx.events.emit("skynet_process_killed", pid=pid, name=name)
            lines.append(f"")
            lines.append(f"[{pid}] {name}: starting (persistence module active)")
            lines.append(f"[!] Kill event logged. Heat +8.")
            # The process is back. Remove it from killed so it appears in ps again.
            dead = _killed_pids(ctx)
            dead.discard(pid)
            ctx.env["_KILLED_PIDS"] = ",".join(str(p) for p in sorted(dead))
        elif pid == 1337:
            lines.append("bash: Terminated  (session restarted)")
        else:
            lines.append(f"kill: ({pid}) - Operation not permitted")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# killall
# ---------------------------------------------------------------------------


@register_command(
    name="killall",
    usage="killall <name> [<name>...]",
    help_text="Kill processes by name",
    category=_CAT,
)
def cmd_killall(ctx: CommandContext, args: list[str]) -> str:
    _, names = _parse_flags(args)
    if not names:
        return "Usage: killall <process-name> [<name>...]"

    lines: list[str] = []
    for name in names:
        matched = [p for p in _PROCESSES if p[6].split()[0].endswith(name) or name in p[6]]
        if not matched:
            lines.append(f"killall: no process found: {name}")
            continue
        for proc in matched:
            pid = proc[0]
            cmd_str = proc[6].split()[0]
            if pid in _SKYNET_PIDS:
                sk_name = _SKYNET_PIDS[pid]
                _record_kill(ctx, pid)
                lines.append(f"[{pid}] {sk_name}: terminated.")
                if ctx.heat is not None:
                    ctx.heat.add_heat(8.0, source="skynet_process_kill")
                if ctx.events:
                    ctx.events.emit("skynet_process_killed", pid=pid, name=sk_name)
                lines.append(f"[{pid}] {sk_name}: starting (persistence module active)")
                lines.append(f"[!] Kill event logged. Heat +8.")
                dead = _killed_pids(ctx)
                dead.discard(pid)
                ctx.env["_KILLED_PIDS"] = ",".join(str(p) for p in sorted(dead))
            elif pid == 1337:
                lines.append("bash: Terminated  (session restarted)")
            else:
                lines.append(f"killall: {name}: Operation not permitted")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# pstree
# ---------------------------------------------------------------------------

_PSTREE_OUTPUT = """\
init─┬─cron
     ├─[kthreadd]─┬─[migration/0]
     │             ├─[mm_percpu_wq]
     │             └─[rcu_gp]
     ├─nginx───nginx
     ├─rsyslogd
     ├─sk_watchdog─┬─sk_comms
     │              └─sk_uplink
     ├─sshd
     ├─systemd-journald
     └─systemd──bash───pstree"""


@register_command(
    name="pstree",
    usage="pstree [-p]",
    help_text="Display a tree of processes",
    category=_CAT,
)
def cmd_pstree(ctx: CommandContext, args: list[str]) -> str:
    flags, _ = _parse_flags(args)
    show_pids = "p" in flags

    if not show_pids:
        return _PSTREE_OUTPUT

    # With -p: annotate with PIDs
    return """\
init(1)─┬─cron(241)
        ├─[kthreadd](2)─┬─[migration/0](11)
        │                ├─[mm_percpu_wq](9)
        │                └─[rcu_gp](3)
        ├─nginx(284)───nginx(285)
        ├─rsyslogd(512)
        ├─sk_watchdog(891)─┬─sk_comms(892)
        │                   └─sk_uplink(893)
        ├─sshd(183)
        ├─systemd-journald(84)
        └─systemd(1201)──bash(1337)───pstree(1338)"""


# ---------------------------------------------------------------------------
# htop (snapshot alias of top with a note)
# ---------------------------------------------------------------------------


@register_command(
    name="htop",
    usage="htop",
    help_text="Interactive process viewer (snapshot mode — interactive display unavailable)",
    category=_CAT,
)
def cmd_htop(ctx: CommandContext, args: list[str]) -> str:
    note = "[htop: interactive mode unavailable — showing snapshot]\n"
    return note + cmd_top(ctx, args)


# ---------------------------------------------------------------------------
# passwd
# ---------------------------------------------------------------------------


@register_command(
    name="passwd",
    usage="passwd [user]",
    help_text="Change user password",
    category=_CAT,
)
def cmd_passwd(ctx: CommandContext, args: list[str]) -> str:
    user = _user(ctx)
    return (
        f"Changing password for {user}.\n"
        "Current password: \n"
        "passwd: Authentication token manipulation error\n"
        "passwd: password unchanged\n"
        "# account locked — modification blocked since 2026-03-15 02:47"
    )


# ---------------------------------------------------------------------------
# User/group management stubs (require root — player is not root)
# ---------------------------------------------------------------------------

def _root_required(cmd: str) -> str:
    return f"{cmd}: Permission denied — this operation requires root privileges."


@register_command(
    name="useradd",
    usage="useradd <username>",
    help_text="Create a new user account (requires root)",
    category=_CAT,
)
def cmd_useradd(ctx: CommandContext, args: list[str]) -> str:
    return _root_required("useradd")


@register_command(
    name="userdel",
    usage="userdel <username>",
    help_text="Delete a user account (requires root)",
    category=_CAT,
)
def cmd_userdel(ctx: CommandContext, args: list[str]) -> str:
    return _root_required("userdel")


@register_command(
    name="usermod",
    usage="usermod <options> <username>",
    help_text="Modify a user account (requires root)",
    category=_CAT,
)
def cmd_usermod(ctx: CommandContext, args: list[str]) -> str:
    return _root_required("usermod")


@register_command(
    name="groupadd",
    usage="groupadd <groupname>",
    help_text="Create a new group (requires root)",
    category=_CAT,
)
def cmd_groupadd(ctx: CommandContext, args: list[str]) -> str:
    return _root_required("groupadd")


@register_command(
    name="groupdel",
    usage="groupdel <groupname>",
    help_text="Delete a group (requires root)",
    category=_CAT,
)
def cmd_groupdel(ctx: CommandContext, args: list[str]) -> str:
    return _root_required("groupdel")


# ---------------------------------------------------------------------------
# Tiny POSIX builtins — true / false / exit / logout / which / sort / uniq / diff
# ---------------------------------------------------------------------------


@register_command(
    name="true",
    usage="true",
    help_text="Do nothing, successfully",
    category=_CAT,
)
def cmd_true(ctx: CommandContext, args: list[str]) -> str:
    return ""


@register_command(
    name="false",
    usage="false",
    help_text="Do nothing, unsuccessfully",
    category=_CAT,
)
def cmd_false(ctx: CommandContext, args: list[str]) -> str:
    return ""


@register_command(
    name="exit",
    usage="exit",
    help_text="Exit the shell",
    category=_CAT,
    aliases=["quit", "logout"],
)
def cmd_exit(ctx: CommandContext, args: list[str]) -> str:
    # Shell.run intercepts exit/quit/logout before this handler is reached so
    # the REPL terminates cleanly. This stub exists only so callers that go
    # through Shell.execute (tests, programmatic harnesses) don't get
    # "command not found".
    return ""


@register_command(
    name="which",
    usage="which <name>...",
    help_text="Locate a command in the registry",
    category=_CAT,
)
def cmd_which(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return ""
    reg = getattr(ctx, "registry", None)
    out: list[str] = []
    for name in args:
        if reg is not None and name in reg:
            out.append(f"/usr/bin/{name}")
        else:
            out.append(f"{name}: not found")
    return "\n".join(out)


def _sort_lines(lines: list[str], reverse: bool, numeric: bool, unique: bool) -> list[str]:
    if numeric:
        def key(s: str) -> tuple[float, str]:
            stripped = s.lstrip()
            try:
                return (float(stripped.split()[0]) if stripped else 0.0, s)
            except (ValueError, IndexError):
                return (0.0, s)
        lines = sorted(lines, key=key, reverse=reverse)
    else:
        lines = sorted(lines, reverse=reverse)
    if unique:
        seen: set[str] = set()
        out: list[str] = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                out.append(line)
        return out
    return lines


@register_command(
    name="sort",
    usage="sort [-r] [-n] [-u] [file]",
    help_text="Sort lines of text",
    category=_CAT,
)
def cmd_sort(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    reverse = "r" in flags or "reverse" in flags
    numeric = "n" in flags or "numeric-sort" in flags
    unique = "u" in flags or "unique" in flags

    stdin = ctx.env.get("STDIN", "") if ctx.env else ""
    if not positional and stdin:
        return "\n".join(_sort_lines(stdin.splitlines(), reverse, numeric, unique))
    if not positional:
        return ""
    if ctx.fs is None:
        return "sort: filesystem unavailable"
    from hackerzork.commands.filesystem import _resolve
    try:
        content = ctx.fs.read_file(_resolve(ctx, positional[0]))
    except Exception as exc:
        return f"sort: {positional[0]}: {exc}"
    return "\n".join(_sort_lines(content.splitlines(), reverse, numeric, unique))


@register_command(
    name="uniq",
    usage="uniq [-c] [-d] [file]",
    help_text="Report or filter out repeated adjacent lines",
    category=_CAT,
)
def cmd_uniq(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    count = "c" in flags or "count" in flags
    only_dup = "d" in flags or "repeated" in flags

    stdin = ctx.env.get("STDIN", "") if ctx.env else ""
    if not positional and stdin:
        lines = stdin.splitlines()
    elif positional and ctx.fs is not None:
        from hackerzork.commands.filesystem import _resolve
        try:
            lines = ctx.fs.read_file(_resolve(ctx, positional[0])).splitlines()
        except Exception as exc:
            return f"uniq: {positional[0]}: {exc}"
    else:
        return ""

    out: list[str] = []
    prev: str | None = None
    run = 0
    for line in lines:
        if line == prev:
            run += 1
            continue
        if prev is not None:
            if not only_dup or run > 1:
                out.append(f"{run:>7} {prev}" if count else prev)
        prev = line
        run = 1
    if prev is not None:
        if not only_dup or run > 1:
            out.append(f"{run:>7} {prev}" if count else prev)
    return "\n".join(out)


@register_command(
    name="diff",
    usage="diff <file1> <file2>",
    help_text="Compare files line by line",
    category=_CAT,
)
def cmd_diff(ctx: CommandContext, args: list[str]) -> str:
    if len(args) < 2:
        return "diff: missing operand\nUsage: diff <file1> <file2>"
    if ctx.fs is None:
        return "diff: filesystem unavailable"
    from hackerzork.commands.filesystem import _resolve
    try:
        a = ctx.fs.read_file(_resolve(ctx, args[0])).splitlines()
    except Exception as exc:
        return f"diff: {args[0]}: {exc}"
    try:
        b = ctx.fs.read_file(_resolve(ctx, args[1])).splitlines()
    except Exception as exc:
        return f"diff: {args[1]}: {exc}"
    import difflib
    diff = list(difflib.unified_diff(a, b, fromfile=args[0], tofile=args[1], lineterm=""))
    return "\n".join(diff)


# ---------------------------------------------------------------------------
# neofetch
# ---------------------------------------------------------------------------

_NF_ART = [
    r"   ╔═══════════╗   ",
    r"   ║           ║   ",
    r"   ║  H@CK3R   ║   ",
    r"   ║  ───────  ║   ",
    r"   ║    Z0RK   ║   ",
    r"   ║           ║   ",
    r"   ╚═══╤═══╤═══╝   ",
    r"        ║   ║       ",
    r"   ═════╩═══╩═════  ",
    r"                    ",
    r"  ██ ██ ██ ██ ██ ██ ",
    r"  ██ ██ ██ ██ ██ ██ ",
]

def _nf_color_block() -> str:
    """8-colour block strip like neofetch shows at the bottom."""
    cols = [
        "\033[40m", "\033[41m", "\033[42m", "\033[43m",
        "\033[44m", "\033[45m", "\033[46m", "\033[47m",
    ]
    return "".join(f"{c}   " for c in cols) + "\033[0m"


@register_command(
    name="neofetch",
    usage="neofetch",
    help_text="Display system information alongside ASCII art",
    category=_CAT,
)
def cmd_neofetch(ctx: CommandContext, args: list[str]) -> str:
    user = _user(ctx)
    host = _hostname(ctx)

    # ANSI helpers
    G  = "\033[32m"    # green
    GB = "\033[1;32m"  # bold green
    A  = "\033[33m"    # amber
    AB = "\033[1;33m"  # bold amber
    R  = "\033[1;31m"  # bold red
    D  = "\033[2m"     # dim
    B  = "\033[1m"     # bold
    X  = "\033[0m"     # reset

    heat = _heat_level(ctx)
    if heat < 25:
        tc, ts = GB, "LOW"
    elif heat < 50:
        tc, ts = AB, "ELEVATED"
    elif heat < 75:
        tc, ts = R, "HIGH"
    else:
        tc, ts = f"\033[1;31;5m", "CRITICAL"   # blinking red at max

    # Count active SkyNet processes
    dead = _killed_pids(ctx)
    sk_active = sum(1 for pid in _SKYNET_PIDS if pid not in dead)

    # Fields — label: value pairs
    fields: list[tuple[str, str]] = [
        ("",        f"{GB}{user}{X}@{GB}{host}{X}"),
        ("",        "─" * (len(user) + len(host) + 1)),
        ("OS",      f"H@ck3r-Z0rk Linux {GB}6.6.6-sk-patched{X}"),
        ("Host",    f"{GB}{host}{X}  (burner laptop, unregistered)"),
        ("Kernel",  f"{G}6.6.6-sk-patched{X} {D}#1 SMP Mar 14 23:59:01 UTC 2026{X}"),
        ("Uptime",  f"{G}42 days, 0 hours, 0 mins{X}  {D}(gap unaccounted for){X}"),
        ("Shell",   f"{G}bash 5.2.15{X}"),
        ("CPU",     f"{G}Intel Core i7-9750H{X} {D}@ 2.60GHz (4) @ 4.50GHz{X}"),
        ("Memory",  f"{G}903MiB{X} / {G}7.6GiB{X}  {D}(11% used){X}"),
        ("Disk",    f"{G}8.3G{X} / {G}48G{X} {D}(17%) — /dev/sda1{X}"),
        ("",        ""),
        ("Threat",  f"{tc}{ts}{X}  {D}(heat={heat:.1f}/100){X}"),
        ("Procs",   f"{G}18{X} total  {D}│{X}  {R if sk_active else D}{sk_active} sk_* active{X}"),
        ("Session", f"{D}{_SK_SID[:24]}…{X}"),
        ("",        ""),
        ("",        _nf_color_block()),
    ]

    # Pair art lines with info lines
    art = _NF_ART
    lines: list[str] = []
    max_rows = max(len(art), len(fields))

    for i in range(max_rows):
        art_col = f"{A}{art[i]}{X}" if i < len(art) else " " * 20
        info_col = ""
        if i < len(fields):
            label, value = fields[i]
            if label:
                info_col = f"  {GB}{label:<9}{X}  {value}"
            else:
                info_col = f"  {value}"
        lines.append(art_col + info_col)

    return "\n".join(lines)
