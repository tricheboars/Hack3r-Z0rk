"""Hidden developer console — hz_debug command.

Unlocked by reading /etc/.hz_debug in-game, which reveals the key.
Subcommands: heat, node, unlock, scan, flag, state, reset, help.

The file /etc/.hz_debug is a root-owned hidden file seeded via home.yaml.
"""
from __future__ import annotations

from hackerzork.engine.command_registry import CommandContext, register_command
from hackerzork.systems.network import Firewall, Loot, NetworkNode, Port

_CAT = "debug"

# The key the player must read from /etc/.hz_debug
_DEBUG_KEY = "h@ck3r_d3v_k3y_2026"
_KEY_FILE   = "/etc/.hz_debug"

_AMBER  = "\033[33m"
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_CYAN   = "\033[36m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"

# Runtime unlock state — persists for the session
_unlocked: bool = False


def _is_unlocked() -> bool:
    return _unlocked


def _set_unlocked(v: bool) -> None:
    global _unlocked
    _unlocked = v


# ---------------------------------------------------------------------------
# hz_debug top-level command
# ---------------------------------------------------------------------------


@register_command(
    name="hz_debug",
    usage="hz_debug <key> <subcommand> [args]",
    help_text=(
        "Hidden developer console. Not for public use.\n"
        "Subcommands: heat, node, unlock, scan, flag, state, reset\n"
        "Key required — see system documentation."
    ),
    category=_CAT,
)
def cmd_hz_debug(ctx: CommandContext, args: list[str]) -> str:
    """Developer console — requires key found in /etc/.hz_debug."""
    global _unlocked

    if not args:
        return f"{_DIM}hz_debug: command not found{_RESET}"

    # First positional arg is either the key or a subcommand if already unlocked
    if not _unlocked:
        key = args[0]
        if key != _DEBUG_KEY:
            # Plausibly deniable — looks like a shell error
            return f"hz_debug: command not found"
        _set_unlocked(True)
        sub_args = args[1:]
        if not sub_args:
            return _banner()
    else:
        # Already unlocked — key optional, but accepted if provided
        if args[0] == _DEBUG_KEY:
            sub_args = args[1:]
        else:
            sub_args = args

    if not sub_args:
        return _banner()

    subcmd = sub_args[0].lower()
    rest   = sub_args[1:]

    dispatch = {
        "help":   _sub_help,
        "heat":   _sub_heat,
        "node":   _sub_node,
        "unlock": _sub_unlock,
        "scan":   _sub_scan,
        "flag":   _sub_flag,
        "state":  _sub_state,
        "reset":  _sub_reset,
    }

    fn = dispatch.get(subcmd)
    if fn is None:
        return (
            f"{_AMBER}[hz_debug]{_RESET} unknown subcommand: {subcmd}\n"
            f"Available: {', '.join(dispatch)}"
        )

    return fn(ctx, rest)


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------


def _banner() -> str:
    return (
        f"{_AMBER}{_BOLD}"
        "╔══════════════════════════════════════╗\n"
        "║   H@CK3R-Z0RK  DEV CONSOLE  v1.0    ║\n"
        "╚══════════════════════════════════════╝"
        f"{_RESET}\n"
        f"Subcommands: {_CYAN}heat node unlock scan flag state reset help{_RESET}\n"
        f"{_DIM}hz_debug <subcommand> [args]{_RESET}"
    )


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def _sub_help(ctx: CommandContext, args: list[str]) -> str:
    return (
        f"{_AMBER}{_BOLD}hz_debug subcommands:{_RESET}\n\n"
        f"  {_CYAN}heat [set <n>]{_RESET}          — show or set heat level\n"
        f"  {_CYAN}node <ip> [compromise]{_RESET}  — inspect or compromise a node\n"
        f"  {_CYAN}unlock <feature>{_RESET}         — unlock a story flag\n"
        f"  {_CYAN}scan <ip>{_RESET}                — force-discover a node\n"
        f"  {_CYAN}flag <name> [clear]{_RESET}      — set or clear a story flag\n"
        f"  {_CYAN}state{_RESET}                    — dump full game state\n"
        f"  {_CYAN}reset heat{_RESET}               — zero the heat level\n"
        f"  {_CYAN}help{_RESET}                     — this message\n"
    )


def _sub_heat(ctx: CommandContext, args: list[str]) -> str:
    if not ctx.heat:
        return "[hz_debug] heat system not available"

    if args and args[0] == "set":
        if len(args) < 2:
            return "[hz_debug] heat set <value>"
        try:
            val = float(args[1])
        except ValueError:
            return f"[hz_debug] invalid value: {args[1]}"
        val = max(0.0, min(100.0, val))
        ctx.heat.level = val
        ctx.heat._check_threshold(0.0)
        if ctx.events:
            ctx.events.emit("heat_changed", amount=0.0, source="debug",
                            level=ctx.heat.level, direction="set")
        return f"{_AMBER}[hz_debug]{_RESET} heat set to {val:.1f}"

    h = ctx.heat
    return (
        f"{_AMBER}[hz_debug] Heat Status{_RESET}\n"
        f"  level     : {_GREEN}{h.level:.2f}{_RESET}\n"
        f"  threshold : {h.current_threshold}\n"
        f"  decay/min : {h.decay_rate:.3f}\n"
        f"  modifiers : {dict(h._stealth_modifiers)}"
    )


def _sub_node(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return "[hz_debug] node <ip> [compromise|harden|reset]"

    ip = args[0]
    action = args[1].lower() if len(args) > 1 else "info"
    net = ctx.network
    node = net.nodes.get(ip)

    if node is None:
        known = ", ".join(net.nodes.keys()) or "(none loaded)"
        return f"[hz_debug] no node at {ip}\nKnown IPs: {known}"

    if action == "compromise":
        net.compromise_node(ip)
        return f"{_GREEN}[hz_debug]{_RESET} {ip} marked as compromised"

    if action == "harden":
        net.harden_node(ip)
        return f"{_AMBER}[hz_debug]{_RESET} {ip} hardened (hardened={node.hardened})"

    if action == "reset":
        node.compromised = False
        node.hardened = 0
        net.compromised.discard(ip)
        return f"[hz_debug] {ip} reset (compromised=False, hardened=0)"

    # info
    ports_str = ", ".join(
        f"{p.number}/{p.service}" + (f"[{p.vuln}]" if p.vuln else "")
        for p in node.ports
    )
    return (
        f"{_AMBER}[hz_debug] Node: {ip}{_RESET}\n"
        f"  id         : {node.id}\n"
        f"  hostname   : {node.hostname}\n"
        f"  name       : {node.name}\n"
        f"  ports      : {ports_str}\n"
        f"  firewall   : {'on' if node.firewall.enabled else 'off'} {node.firewall.rules}\n"
        f"  difficulty : {node.difficulty}\n"
        f"  hardened   : {node.hardened}\n"
        f"  compromised: {node.compromised}\n"
        f"  connections: {node.connections}\n"
        f"  loot items : {len(node.loot)}\n"
        f"  story_flags: {node.story_flags}"
    )


def _sub_unlock(ctx: CommandContext, args: list[str]) -> str:
    """Unlock a story feature by name."""
    features = {
        "shadow": "shadow_unlocked",
        "relay":  "relay_compromised",
        "z0rk7":  "z0rk7_contact_established",
        "evidence": "evidence_decrypted",
        "skynet": "skynet_core_located",
        "intro":  "intro_complete",
    }

    if not args:
        return (
            f"{_AMBER}[hz_debug] unlock <feature>{_RESET}\n"
            f"Features: {', '.join(features)}"
        )

    name = args[0].lower()
    flag = features.get(name)
    if flag is None:
        return f"[hz_debug] unknown feature: {name}\nKnown: {', '.join(features)}"

    if ctx.state:
        ctx.state.set_flag(flag)
        return f"{_GREEN}[hz_debug]{_RESET} unlocked: {flag}"
    return "[hz_debug] state system not available"


def _sub_scan(ctx: CommandContext, args: list[str]) -> str:
    """Force-discover a node."""
    if not args:
        return "[hz_debug] scan <ip>"

    ip = args[0]
    net = ctx.network
    node = net.nodes.get(ip)
    if node is None:
        return f"[hz_debug] no node at {ip}"

    net.discovered.add(ip)
    if ctx.events:
        conn_ips = [
            nbr.ip
            for cid in node.connections
            if (nbr := net._nodes_by_id.get(cid)) is not None
        ]
        ctx.events.emit(
            "node_discovered",
            ip=ip, name=node.name, hostname=node.hostname,
            status="known", connections=conn_ips,
        )
    return f"{_GREEN}[hz_debug]{_RESET} {ip} ({node.hostname}) added to discovered set"


def _sub_flag(ctx: CommandContext, args: list[str]) -> str:
    """Set or clear a story flag."""
    if not args:
        if ctx.state:
            flags_str = "\n  ".join(sorted(ctx.state.flags)) or "(none)"
            return f"{_AMBER}[hz_debug] Active flags:{_RESET}\n  {flags_str}"
        return "[hz_debug] state system not available"

    name = args[0]
    action = args[1].lower() if len(args) > 1 else "set"

    if not ctx.state:
        return "[hz_debug] state system not available"

    if action == "clear":
        ctx.state.clear_flag(name)
        return f"[hz_debug] flag cleared: {name}"

    ctx.state.set_flag(name)
    return f"{_GREEN}[hz_debug]{_RESET} flag set: {name}"


def _sub_state(ctx: CommandContext, args: list[str]) -> str:
    """Dump full game state summary."""
    lines: list[str] = [f"{_AMBER}{_BOLD}[hz_debug] Game State Dump{_RESET}"]

    # Heat
    if ctx.heat:
        lines.append(f"\n{_CYAN}Heat:{_RESET} {ctx.heat.level:.2f} ({ctx.heat.current_threshold})")
    else:
        lines.append(f"\n{_CYAN}Heat:{_RESET} unavailable")

    # Network
    net = ctx.network
    lines.append(f"\n{_CYAN}Network:{_RESET}")
    lines.append(f"  nodes loaded : {len(net.nodes)}")
    lines.append(f"  discovered   : {sorted(net.discovered)}")
    lines.append(f"  compromised  : {sorted(net.compromised)}")

    # Story flags
    if ctx.state:
        flags_str = ", ".join(sorted(ctx.state.flags)) or "(none)"
        lines.append(f"\n{_CYAN}Flags:{_RESET} {flags_str}")
        lines.append(f"{_CYAN}Chapter:{_RESET} {ctx.state.chapter}")
    else:
        lines.append(f"\n{_CYAN}Flags:{_RESET} unavailable")

    # VFS
    try:
        entries = ctx.fs.list_dir("/home/user")
        lines.append(f"\n{_CYAN}VFS /home/user:{_RESET} {len(entries)} entries")
    except Exception:
        lines.append(f"\n{_CYAN}VFS:{_RESET} unavailable")

    return "\n".join(lines)


def _sub_reset(ctx: CommandContext, args: list[str]) -> str:
    """Reset specific subsystem."""
    if not args:
        return "[hz_debug] reset <heat|heat>"

    target = args[0].lower()
    if target == "heat":
        if ctx.heat:
            ctx.heat.level = 0.0
            ctx.heat.current_threshold = "safe"
            if ctx.events:
                ctx.events.emit("heat_changed", amount=0.0, source="debug_reset",
                                level=0.0, direction="set")
            return f"{_GREEN}[hz_debug]{_RESET} heat reset to 0.0"
        return "[hz_debug] heat system not available"

    return f"[hz_debug] unknown reset target: {target}"
