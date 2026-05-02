"""Hacking commands: exploit, bruteforce, payload, loot, backdoor, privesc."""
from __future__ import annotations

import random
import textwrap
import time

from hackerzork.engine.command_registry import CommandContext, register_command
from hackerzork.systems.network import ExploitResult, Loot, NetworkSim

_CAT = "hacking"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ANSI_RED    = "\033[31m"
_ANSI_GREEN  = "\033[32m"
_ANSI_YELLOW = "\033[33m"
_ANSI_CYAN   = "\033[36m"
_ANSI_BOLD   = "\033[1m"
_ANSI_DIM    = "\033[2m"
_ANSI_RESET  = "\033[0m"


def _emit(ctx: CommandContext, event: str, **data: object) -> None:
    if ctx.events:
        ctx.events.emit(event, **data)


def _parse_flags(args: list[str]) -> tuple[set[str], list[str]]:
    """Simple flag parser — does NOT consume -X VALUE named args."""
    flags: set[str] = set()
    positional: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and len(a) > 2:
            flags.add(a[2:])
        elif a.startswith("-") and len(a) > 1 and not a[1:].isdigit():
            for ch in a[1:]:
                flags.add(ch)
        else:
            positional.append(a)
        i += 1
    return flags, positional


import re as _re

# Named args that take a value: -p PORT  -e EXPLOIT  -w FILE
_NAMED_ARGS = {"-p", "-e", "-w"}
_IP_RE = _re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def _parse_hacking_args(
    args: list[str],
) -> tuple[set[str], dict[str, str], list[str]]:
    """Parse hacking command args into (flags, named_values, positionals).

    Handles two forms produced by the shell pipeline:
    1. Direct: ``["-p", "80", "-e", "CVE", "IP"]``  → named["p"]="80", named["e"]="CVE"
    2. Shell-reconstructed bundled: ``["-ep", "80", "CVE", "IP"]``
       → the shell parser bundled -p and -e into -ep; values are positionals in order.
       We use type discrimination to recover: port=first integer, exploit=first
       non-IP non-integer string, target=X.X.X.X address.
    """
    flags: set[str] = set()
    named: dict[str, str] = {}
    positional: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        # Direct form: -p VALUE or -e VALUE or -w VALUE (value not a flag)
        if a in _NAMED_ARGS and i + 1 < len(args) and not args[i + 1].startswith("-"):
            named[a[1:]] = args[i + 1]
            i += 2
        elif a.startswith("--") and "=" in a:
            # --key=val form
            key, _, val = a[2:].partition("=")
            named[key] = val
            i += 1
        elif a.startswith("--") and len(a) > 2:
            flags.add(a[2:])
            i += 1
        elif a.startswith("-") and len(a) > 1 and not a[1:].replace(".", "").isdigit():
            for ch in a[1:]:
                flags.add(ch)
            i += 1
        else:
            positional.append(a)
            i += 1

    # If -p or -e came through as boolean flags (bundled form), recover values
    # from positionals using type discrimination.
    remaining = list(positional)

    if "p" in flags and "p" not in named:
        # Port: first positional that is a plain integer in valid port range
        for idx, v in enumerate(remaining):
            if v.isdigit() and 1 <= int(v) <= 65535:
                named["p"] = v
                remaining.pop(idx)
                flags.discard("p")
                break

    if "e" in flags and "e" not in named:
        # Exploit: first positional that is not an IP and not a pure digit
        for idx, v in enumerate(remaining):
            if not _IP_RE.match(v) and not v.isdigit():
                named["e"] = v
                remaining.pop(idx)
                flags.discard("e")
                break

    if "w" in flags and "w" not in named:
        # Wordlist: first positional that starts with /
        for idx, v in enumerate(remaining):
            if v.startswith("/"):
                named["w"] = v
                remaining.pop(idx)
                flags.discard("w")
                break

    return flags, named, remaining


def _node_or_err(ctx: CommandContext, ip: str) -> tuple | str:
    """Return (NetworkSim, node) or error string."""
    net: NetworkSim = ctx.network
    node = net.nodes.get(ip)
    if node is None:
        return f"exploit: no route to host: {ip}"
    return net, node


def _loot_to_vfs(ctx: CommandContext, loot_list: list[Loot], ip: str) -> list[str]:
    """Write loot items into VFS and return human-readable descriptions."""
    lines: list[str] = []
    loot_dir = f"/home/user/loot/{ip.replace('.', '_')}"
    ctx.fs.make_dir(loot_dir, parents=True)

    for item in loot_list:
        if item.type == "file":
            dest = f"{loot_dir}/{item.path.split('/')[-1] or 'stolen_file'}"
            ctx.fs.write_file(dest, item.content)
            lines.append(f"  {_ANSI_GREEN}[FILE]{_ANSI_RESET} {item.path} → {dest}")
            _emit(ctx, "file_catalogued",
                  path=dest, name=dest.split("/")[-1],
                  content=item.content, modified="", owner="user",
                  encrypted=False, isNew=True)
        elif item.type == "credential":
            note = f"{item.service}://{item.username}:{item.password}\n"
            dest = f"{loot_dir}/creds_{item.service}.txt"
            ctx.fs.write_file(dest, note)
            lines.append(f"  {_ANSI_YELLOW}[CRED]{_ANSI_RESET} {item.service} — {item.username}:{item.password}")
            _emit(ctx, "file_catalogued",
                  path=dest, name=dest.split("/")[-1],
                  content=note, modified="", owner="user",
                  encrypted=False, isNew=True)
        elif item.type == "key":
            dest = f"{loot_dir}/{item.service or 'key'}.key"
            ctx.fs.write_file(dest, item.content)
            lines.append(f"  {_ANSI_CYAN}[KEY]{_ANSI_RESET} {item.description or item.service}")
        else:
            lines.append(f"  [?] {item.type}: {item.description}")

    return lines


# ---------------------------------------------------------------------------
# exploit
# ---------------------------------------------------------------------------

_EXPLOIT_FLAVOUR: dict[str, list[str]] = {
    "CVE-2021-23017": [
        "Sending malformed DNS request to nginx resolver…",
        "Overflowing response buffer (CVE-2021-23017)…",
        "Hijacking response pointer — writing shellcode stub…",
    ],
    "default_credentials": [
        "Trying default credential pairs…",
        "Attempting admin:admin… denied",
        "Attempting root:root… denied",
        "Attempting dbadmin:hunter2… ",
    ],
    "ms17-010": [
        "Sending SMBv1 TRANSACTION2 request…",
        "Triggering EternalBlue buffer overflow…",
        "Injecting DoublePulsar kernel backdoor…",
    ],
    "shellshock": [
        "Injecting payload into HTTP User-Agent header…",
        "CGI script executing env variable…",
        "Reverse shell callback established…",
    ],
    "log4shell": [
        "Injecting JNDI lookup string into log field…",
        "LDAP callback from vulnerable log4j instance…",
        "Deserializing remote class payload…",
    ],
    "default_credentials_ssh": [
        "Loading credential wordlist…",
        "Trying admin:password… denied",
        "Trying root:toor… denied",
        "Trying user:user123… ",
    ],
}

_GENERIC_FLAVOUR = [
    "Sending exploit payload…",
    "Awaiting response from target…",
    "Analyzing service response…",
]


@register_command(
    name="exploit",
    usage="exploit -p PORT -e EXPLOIT <target>",
    help_text=(
        "Attempt to exploit a vulnerability on a remote target.\n"
        "  -p PORT    target port (required)\n"
        "  -e EXPLOIT exploit identifier (e.g. CVE-2021-23017, default_credentials)\n"
        "  -s         stealth mode — slower but lower heat\n\n"
        "Run nmap -sV first to discover available ports and vulns."
    ),
    category=_CAT,
)
def cmd_exploit(ctx: CommandContext, args: list[str]) -> str:
    """Exploit a vulnerability on a remote host."""
    flags, named, positional = _parse_hacking_args(args)

    port_str = named.get("p")
    exploit   = named.get("e")

    if not positional:
        return "exploit: missing target\nUsage: exploit -p PORT -e EXPLOIT <target>"
    if port_str is None:
        return "exploit: -p PORT is required\nUsage: exploit -p PORT -e EXPLOIT <target>"
    if exploit is None:
        return "exploit: -e EXPLOIT is required\nUsage: exploit -p PORT -e EXPLOIT <target>"

    try:
        port = int(port_str)
    except ValueError:
        return f"exploit: invalid port: {port_str}"

    ip = positional[0]
    stealth = "s" in flags or "stealth" in flags

    net: NetworkSim = ctx.network
    node = net.nodes.get(ip)
    if node is None:
        return f"exploit: no route to host: {ip}"

    if ip not in net.discovered:
        return (f"exploit: {ip} — host not yet scanned.\n"
                "Run nmap first to discover open ports.")

    out: list[str] = []
    out.append(f"{_ANSI_BOLD}[*] Initialising exploit: {exploit}{_ANSI_RESET}")
    out.append(f"[*] Target: {ip}:{port}  stealth={'ON' if stealth else 'OFF'}")
    out.append("")

    # Flavour text
    steps = _EXPLOIT_FLAVOUR.get(exploit, _GENERIC_FLAVOUR)
    for step in steps:
        out.append(f"    {_ANSI_DIM}{step}{_ANSI_RESET}")

    out.append("")

    _emit(ctx, "exploit_attempted", target=ip, port=port, exploit=exploit, stealth=stealth)

    # Snapshot discovered set before exploit so we can report newly found nodes
    pre_discovered = set(net.discovered)

    result: ExploitResult = net.attempt_exploit(ip, port, exploit)

    # Apply heat
    heat_cost = result.heat_cost
    if stealth:
        heat_cost *= 0.6
    if ctx.heat:
        ctx.heat.add_heat(heat_cost, source=f"exploit:{ip}")

    if result.success:
        out.append(f"{_ANSI_GREEN}{_ANSI_BOLD}[+] {result.message}{_ANSI_RESET}")
        out.append(f"[*] Heat cost: {_ANSI_YELLOW}+{heat_cost:.1f}{_ANSI_RESET}")
        out.append("")

        # Report any newly discovered neighbour IPs
        newly_found = net.discovered - pre_discovered - {ip}
        if newly_found:
            out.append(f"{_ANSI_CYAN}[*] Relay config reveals upstream nodes:{_ANSI_RESET}")
            for new_ip in sorted(newly_found):
                new_node = net.nodes.get(new_ip)
                label = f"  {new_ip}"
                if new_node and new_node.hostname:
                    label += f"  ({new_node.hostname})"
                out.append(label)
            out.append("")

        _emit(ctx, "exploit_succeeded", target=ip, port=port, exploit=exploit)
        conn_ips = [
            nbr.ip for cid in node.connections
            if (nbr := net._nodes_by_id.get(cid)) is not None
        ]
        _emit(ctx, "node_compromised",
              ip=ip,
              name=node.name,
              hostname=node.hostname,
              status="owned",
              connections=conn_ips)

        # Write loot to VFS
        if result.loot:
            out.append(f"[*] Exfiltrating loot from {node.hostname}…")
            loot_lines = _loot_to_vfs(ctx, result.loot, ip)
            out.extend(loot_lines)
            out.append("")
            _emit(ctx, "exploit_loot_exfiltrated", ip=ip, count=len(result.loot))
            if ctx.heat:
                ctx.heat.add_heat(3.0 * len(result.loot), source="file_exfil")
        else:
            out.append("[*] No accessible loot on this node.")

        # Story flags
        flag = node.story_flags.get("on_compromise")
        if flag and ctx.state:
            ctx.state.set_flag(flag)
    else:
        out.append(f"{_ANSI_RED}{_ANSI_BOLD}[-] {result.message}{_ANSI_RESET}")
        out.append(f"[*] Heat cost: {_ANSI_YELLOW}+{heat_cost:.1f}{_ANSI_RESET}")
        _emit(ctx, "exploit_failed", target=ip, port=port, exploit=exploit)

    return "\n".join(out)


# ---------------------------------------------------------------------------
# bruteforce
# ---------------------------------------------------------------------------

_BRUTE_SERVICES: dict[str, list[tuple[str, str]]] = {
    "ssh": [
        ("root", "toor"), ("admin", "admin"), ("user", "password"),
        ("ubuntu", "ubuntu"), ("pi", "raspberry"), ("root", "password"),
    ],
    "mysql": [
        ("root", ""), ("root", "root"), ("admin", "admin"),
        ("dbadmin", "hunter2"), ("mysql", "mysql"),
    ],
    "ftp": [
        ("anonymous", ""), ("ftp", "ftp"), ("admin", "admin"),
        ("user", "12345"),
    ],
    "http": [
        ("admin", "admin"), ("admin", "password"), ("root", "root"),
        ("administrator", "password123"),
    ],
}


@register_command(
    name="bruteforce",
    usage="bruteforce -p PORT [-s] <target>",
    help_text=(
        "Brute-force credentials on a service.\n"
        "  -p PORT   target port\n"
        "  -s        stealth (slower, lower heat per attempt)\n"
        "  -w FILE   custom wordlist from VFS\n\n"
        "WARNING: generates significant heat. Consider using shadow/toolkit packages."
    ),
    category=_CAT,
)
def cmd_bruteforce(ctx: CommandContext, args: list[str]) -> str:
    """Brute-force service credentials."""
    flags, named, positional = _parse_hacking_args(args)

    port_str      = named.get("p")
    wordlist_path = named.get("w")

    if not positional:
        return "bruteforce: missing target\nUsage: bruteforce -p PORT <target>"
    if port_str is None:
        return "bruteforce: -p PORT is required"

    try:
        port = int(port_str)
    except ValueError:
        return f"bruteforce: invalid port: {port_str}"

    ip = positional[0]
    stealth = "s" in flags

    net: NetworkSim = ctx.network
    node = net.nodes.get(ip)
    if node is None:
        return f"bruteforce: no route to host: {ip}"

    if ip not in net.discovered:
        return f"bruteforce: {ip} — host not yet scanned. Run nmap first."

    port_obj = node.get_port(port)
    if port_obj is None:
        return f"bruteforce: port {port} is not open on {ip}"

    service = port_obj.service.lower()

    # Load custom wordlist if provided
    pairs: list[tuple[str, str]] = []
    if wordlist_path:
        try:
            content = ctx.fs.read_file(wordlist_path)
            for line in content.splitlines():
                if ":" in line:
                    u, _, p = line.partition(":")
                    pairs.append((u.strip(), p.strip()))
        except Exception:
            return f"bruteforce: cannot read wordlist: {wordlist_path}"
    else:
        pairs = list(_BRUTE_SERVICES.get(service, [("admin", "admin"), ("root", "root")]))

    out: list[str] = []
    out.append(f"{_ANSI_BOLD}[*] Brute-forcing {service} on {ip}:{port}{_ANSI_RESET}")
    out.append(f"[*] Wordlist: {len(pairs)} pairs  stealth={'ON' if stealth else 'OFF'}")
    out.append("")

    _emit(ctx, "exploit_attempted", target=ip, port=port, exploit="bruteforce", stealth=stealth)

    # Heat up front — bruteforce is noisy
    heat = 20.0 * (0.5 if stealth else 1.0)
    if ctx.heat:
        ctx.heat.add_heat(heat, source=f"bruteforce:{ip}")

    # Check for matching credentials in node loot
    found_cred: tuple[str, str] | None = None
    node_creds = {
        (item.username.lower(), item.password.lower())
        for item in node.loot
        if item.type == "credential" and item.service.lower() == service
    }
    for u, p in pairs:
        if (u.lower(), p.lower()) in node_creds:
            found_cred = (u, p)
            break

    # Print first few tries — stop just before the matching credential
    shown = 0
    for u, p in pairs:
        if shown >= 6:
            break
        if found_cred and (u.lower(), p.lower()) == (found_cred[0].lower(), found_cred[1].lower()):
            break  # success line printed below
        out.append(f"    {_ANSI_DIM}trying {u}:{p}… denied{_ANSI_RESET}")
        shown += 1

    if found_cred:
        u, p = found_cred
        out.append(f"    {_ANSI_DIM}trying {u}:{p}… {_ANSI_RESET}")
        out.append("")
        out.append(f"{_ANSI_GREEN}{_ANSI_BOLD}[+] Credentials found: {u}:{p}{_ANSI_RESET}")
        out.append(f"[*] Service: {service} on {ip}:{port}")

        # Persist cred to VFS
        cred_dir = f"/home/user/loot/{ip.replace('.', '_')}"
        ctx.fs.make_dir(cred_dir, parents=True)
        cred_file = f"{cred_dir}/creds_{service}_brute.txt"
        ctx.fs.write_file(cred_file, f"{service}://{u}:{p}\n")
        out.append(f"[*] Saved to {cred_file}")
        _emit(ctx, "exploit_succeeded", target=ip, port=port, exploit="bruteforce")
    else:
        out.append(f"    {_ANSI_DIM}…{len(pairs) - 6} more attempts…{_ANSI_RESET}")
        out.append("")
        out.append(f"{_ANSI_RED}[-] No valid credentials found.{_ANSI_RESET}")
        out.append(f"{_ANSI_YELLOW}[!] Consider acquiring a better wordlist via shadow packages.{_ANSI_RESET}")
        _emit(ctx, "exploit_failed", target=ip, port=port, exploit="bruteforce")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# loot
# ---------------------------------------------------------------------------


@register_command(
    name="loot",
    usage="loot [<ip>]",
    help_text=(
        "Display exfiltrated loot from compromised nodes.\n"
        "  loot          — list all loot\n"
        "  loot <ip>     — show loot for specific node"
    ),
    category=_CAT,
)
def cmd_loot(ctx: CommandContext, args: list[str]) -> str:
    """Show exfiltrated loot from compromised nodes."""
    _, positional = _parse_flags(args)
    target_ip = positional[0] if positional else None

    loot_base = "/home/user/loot"
    try:
        entries = ctx.fs.list_dir(loot_base)
    except Exception:
        return "No loot collected yet.\nCompromise a node with 'exploit' to begin."

    if not entries:
        return "No loot collected yet.\nCompromise a node with 'exploit' to begin."

    out: list[str] = []
    out.append(f"{_ANSI_BOLD}Exfiltrated Loot{_ANSI_RESET}")
    out.append("─" * 40)

    for entry in sorted(entries, key=lambda e: e.name):
        entry_name = entry.name
        if entry_name.startswith("."):
            continue
        node_ip = entry_name.replace("_", ".")
        if target_ip and node_ip != target_ip:
            continue

        net: NetworkSim = ctx.network
        node = net.nodes.get(node_ip)
        label = node.hostname if node else node_ip

        out.append(f"\n{_ANSI_CYAN}{_ANSI_BOLD}[{node_ip}]{_ANSI_RESET} {_ANSI_DIM}{label}{_ANSI_RESET}")
        node_dir = f"{loot_base}/{entry_name}"
        try:
            files = ctx.fs.list_dir(node_dir)
        except Exception:
            continue
        for fentry in sorted(files, key=lambda e: e.name):
            fname = fentry.name
            fpath = f"{node_dir}/{fname}"
            try:
                content = ctx.fs.read_file(fpath)
                preview = content.strip().splitlines()[0][:60] if content.strip() else "(empty)"
            except Exception:
                preview = "(unreadable)"
            out.append(f"  {_ANSI_GREEN}{fname}{_ANSI_RESET}")
            out.append(f"    {_ANSI_DIM}{preview}{_ANSI_RESET}")

    if len(out) == 2:
        return "No loot collected yet.\nCompromise a node with 'exploit' to begin."

    return "\n".join(out)


# ---------------------------------------------------------------------------
# backdoor
# ---------------------------------------------------------------------------


@register_command(
    name="backdoor",
    usage="backdoor -p PORT <target>",
    help_text=(
        "Install a persistent backdoor on a compromised node.\n"
        "  -p PORT   port to listen on (default: 4444)\n\n"
        "Node must already be compromised. Backdoors allow re-entry\n"
        "after the session ends but generate ongoing heat."
    ),
    category=_CAT,
)
def cmd_backdoor(ctx: CommandContext, args: list[str]) -> str:
    """Install a persistent backdoor on an owned node."""
    flags, named, positional = _parse_hacking_args(args)

    bd_port = 4444
    if "p" in named:
        try:
            bd_port = int(named["p"])
        except ValueError:
            return f"backdoor: invalid port: {named['p']}"

    if not positional:
        return "backdoor: missing target\nUsage: backdoor -p PORT <target>"

    ip = positional[0]
    net: NetworkSim = ctx.network

    if ip not in net.compromised:
        return (
            f"{_ANSI_RED}[-] {ip} is not compromised.{_ANSI_RESET}\n"
            "You need a root shell first. Try 'exploit'."
        )

    node = net.nodes.get(ip)
    hostname = node.hostname if node else ip

    # Add a backdoor port to the node
    from hackerzork.systems.network import Port as NetPort
    bd_port_obj = NetPort(
        number=bd_port,
        service="backdoor",
        version="hz-shell/1.0",
        vuln=None,
        state="open",
    )
    if node:
        existing = {p.number for p in node.ports}
        if bd_port not in existing:
            node.ports.append(bd_port_obj)
            if node.firewall.enabled:
                node.firewall.add_rule(f"block_port: {bd_port}")

    # Record in VFS
    bd_dir = f"/home/user/loot/{ip.replace('.', '_')}"
    ctx.fs.make_dir(bd_dir, parents=True)
    bd_file = f"{bd_dir}/backdoor_{bd_port}.txt"
    ctx.fs.write_file(
        bd_file,
        f"BACKDOOR INSTALLED\nhost: {hostname} ({ip})\nport: {bd_port}\nprotocol: hz-shell/1.0\n"
    )

    if ctx.heat:
        ctx.heat.add_heat(5.0, source=f"backdoor:{ip}")

    _emit(ctx, "backdoor_installed", ip=ip, port=bd_port)

    return (
        f"{_ANSI_GREEN}{_ANSI_BOLD}[+] Backdoor installed on {hostname} (:{bd_port}){_ANSI_RESET}\n"
        f"[*] Use: nc {ip} {bd_port}\n"
        f"[*] Heat cost: {_ANSI_YELLOW}+5.0{_ANSI_RESET}  (ongoing +0.5/min while active)\n"
        f"[*] Logged to {bd_file}"
    )


# ---------------------------------------------------------------------------
# privesc
# ---------------------------------------------------------------------------

_PRIVESC_VECTORS: list[dict] = [
    {"name": "sudo -l misconfiguration",  "flag": "sudo_nopasswd",   "heat": 3.0},
    {"name": "SUID binary (find)",        "flag": "suid_find",       "heat": 5.0},
    {"name": "writable cron job",         "flag": "writable_cron",   "heat": 4.0},
    {"name": "kernel exploit (dirty cow)","flag": "kernel_dirtycow", "heat": 8.0},
    {"name": "docker socket exposure",    "flag": "docker_socket",   "heat": 6.0},
]


@register_command(
    name="privesc",
    usage="privesc [--check] <target>",
    help_text=(
        "Attempt privilege escalation on a compromised node.\n"
        "  --check    enumerate vectors without exploiting (lower heat)\n\n"
        "Node must already be compromised."
    ),
    category=_CAT,
)
def cmd_privesc(ctx: CommandContext, args: list[str]) -> str:
    """Privilege escalation on a compromised node."""
    flags, positional = _parse_flags(args)
    check_only = "check" in flags

    if not positional:
        return "privesc: missing target\nUsage: privesc [--check] <target>"

    ip = positional[0]
    net: NetworkSim = ctx.network

    if ip not in net.compromised:
        return (
            f"{_ANSI_RED}[-] {ip} is not yet compromised.{_ANSI_RESET}\n"
            "Gain initial access first with 'exploit' or 'bruteforce'."
        )

    node = net.nodes.get(ip)
    hostname = node.hostname if node else ip

    out: list[str] = []
    out.append(f"{_ANSI_BOLD}[*] Enumerating privesc vectors on {hostname}{_ANSI_RESET}")
    out.append("")

    # Use node difficulty to seed which vectors are present
    seed = sum(ord(c) for c in ip)
    rng = random.Random(seed)
    available = rng.sample(_PRIVESC_VECTORS, k=min(3, node.difficulty + 1 if node else 2))

    for v in available:
        out.append(f"  {_ANSI_YELLOW}[!]{_ANSI_RESET} {v['name']}")

    out.append("")

    if check_only:
        if ctx.heat:
            ctx.heat.add_heat(2.0, source=f"privesc_check:{ip}")
        out.append(f"{_ANSI_DIM}[*] --check only: no exploit attempted{_ANSI_RESET}")
        return "\n".join(out)

    # Pick best (lowest heat) vector and "exploit" it
    best = min(available, key=lambda v: v["heat"])
    if ctx.heat:
        ctx.heat.add_heat(best["heat"], source=f"privesc:{ip}")

    out.append(f"[*] Exploiting: {best['name']}")
    out.append(f"{_ANSI_GREEN}{_ANSI_BOLD}[+] Root shell obtained on {hostname}{_ANSI_RESET}")
    out.append(f"[*] Heat cost: {_ANSI_YELLOW}+{best['heat']:.1f}{_ANSI_RESET}")

    if ctx.state:
        ctx.state.set_flag(f"privesc_{ip.replace('.', '_')}")

    _emit(ctx, "privesc_succeeded", ip=ip, vector=best["name"])

    return "\n".join(out)
