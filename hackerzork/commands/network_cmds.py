"""Network commands: nmap, ssh, ping, traceroute, curl, netcat,
ifconfig, ip, ss, netstat."""
from __future__ import annotations

import re
from datetime import datetime

from hackerzork.engine.command_registry import CommandContext, register_command
from hackerzork.systems.network import NetworkSim

_CAT = "network"


# ---------------------------------------------------------------------------
# Flag / argument helpers
# ---------------------------------------------------------------------------


def _parse_flags(args: list[str]) -> tuple[set[str], list[str]]:
    """Split raw args into (single-char flags, positional args)."""
    flags: set[str] = set()
    positional: list[str] = []
    after_dashdash = False
    for a in args:
        if after_dashdash:
            positional.append(a)
        elif a == "--":
            after_dashdash = True
        elif a.startswith("--") and len(a) > 2:
            flags.add(a[2:])
        elif a.startswith("-") and len(a) > 1 and not a[1:].isdigit():
            for ch in a[1:]:
                flags.add(ch)
        else:
            positional.append(a)
    return flags, positional


def _parse_port_spec(spec: str) -> list[int]:
    """Parse '22,80,443' or '22-100' into a sorted port list."""
    ports: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, _, hi = part.partition("-")
            try:
                ports.extend(range(int(lo), int(hi) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            ports.append(int(part))
    return sorted(set(ports))


def _parse_nmap_args(
    args: list[str],
) -> tuple[set[str], list[int] | None, list[str]]:
    """Return (scan_flags, explicit_ports, targets)."""
    scan_flags: set[str] = set()
    ports: list[int] | None = None
    targets: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-p" and i + 1 < len(args):
            ports = _parse_port_spec(args[i + 1])
            i += 2
        elif a.startswith("-p") and len(a) > 2:
            ports = _parse_port_spec(a[2:])
            i += 1
        elif re.match(r"^-s[A-Za-z]+$", a):
            scan_flags.add(a[2:])  # "V", "S", "U" etc.
            i += 1
        elif a.startswith("-") and len(a) > 1:
            for ch in a[1:]:
                scan_flags.add(ch)
            i += 1
        else:
            targets.append(a)
            i += 1
    return scan_flags, ports, targets


def _parse_ssh_target(token: str) -> tuple[str, str]:
    """Split 'user@host' → ('user', 'host'); plain host → ('', host)."""
    if "@" in token:
        user, _, host = token.partition("@")
        return user, host
    return "", token


def _resolve_host(ctx: CommandContext, host: str) -> str:
    """Resolve hostname to IP, checking /etc/hosts in the VFS."""
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
        return host
    if ctx.fs is not None:
        try:
            hosts_content = ctx.fs.read_file("/etc/hosts")
            for line in hosts_content.splitlines():
                line = line.split("#")[0].strip()
                parts = line.split()
                if len(parts) >= 2 and host in parts[1:]:
                    return parts[0]
        except Exception:
            pass
    return host


def _net(ctx: CommandContext) -> NetworkSim | None:
    return ctx.network  # type: ignore[return-value]


def _emit(ctx: CommandContext, event: str, **data: object) -> None:
    if ctx.events:
        ctx.events.emit(event, **data)


# ---------------------------------------------------------------------------
# nmap
# ---------------------------------------------------------------------------


@register_command(
    name="nmap",
    usage="nmap [-sV] [-sS] [-p PORT[,PORT...]] <target>",
    help_text="Network exploration and port scanning",
    category=_CAT,
)
def cmd_nmap(ctx: CommandContext, args: list[str]) -> str:
    """Scan a target for open ports and services."""
    net = _net(ctx)
    if net is None:
        return "nmap: network subsystem not available"

    scan_flags, explicit_ports, targets = _parse_nmap_args(args)
    if not targets:
        return "nmap: no target specified\nUsage: nmap [-sV] [-sS] [-p PORT] <target>"

    version_scan = "V" in scan_flags
    stealth = "S" in scan_flags

    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"Starting Nmap 7.94 ( https://nmap.org ) at {now} UTC")

    for target in targets:
        ip = _resolve_host(ctx, target)
        net.discover_node(ip)
        node = net.nodes.get(ip)

        if node is None:
            lines.append(f"\nNote: Host {ip} seems down.")
            lines.append(f"Nmap scan report for {ip}")
            lines.append("Host is up (0.000s latency).")
            lines.append("\nAll scanned ports on are filtered")
            continue

        ping_r = net.ping(ip)
        lat = f"{ping_r.latency_ms / 1000:.3f}s"
        host_label = f"{node.hostname} ({ip})" if node.hostname else ip
        lines.append(f"\nNmap scan report for {host_label}")
        lines.append(f"Host is up ({lat} latency).")

        port_results = (
            net.scan_ports(ip, explicit_ports)
            if explicit_ports
            else net.scan_ports(ip)
        )

        if not port_results:
            lines.append("All scanned ports are filtered")
        else:
            lines.append("")
            if version_scan:
                lines.append(f"{'PORT':<10} {'STATE':<10} {'SERVICE':<12} VERSION")
            else:
                lines.append(f"{'PORT':<10} {'STATE':<10} SERVICE")

            for pr in sorted(port_results, key=lambda r: r.port):
                tag = f"{pr.port}/tcp"
                state = pr.state
                svc = pr.service

                if version_scan and pr.state == "open":
                    port_obj = node.get_port(pr.port)
                    ver = port_obj.version if port_obj else ""
                    lines.append(f"{tag:<10} {state:<10} {svc:<12} {ver}")
                else:
                    lines.append(f"{tag:<10} {state:<10} {svc}")

        open_count = sum(1 for r in port_results if r.state == "open")
        _emit(
            ctx,
            "scan_performed",
            target=ip,
            stealth=stealth,
            port_count=len(port_results),
            open_ports=open_count,
        )

    lines.append(
        f"\nNmap done: {len(targets)} IP address(es) scanned"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------


@register_command(
    name="ping",
    usage="ping [-c COUNT] <host>",
    help_text="Send ICMP echo requests to a network host",
    category=_CAT,
)
def cmd_ping(ctx: CommandContext, args: list[str]) -> str:
    net = _net(ctx)
    if net is None:
        return "ping: network subsystem not available"

    count = 4
    positional: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "-c" and i + 1 < len(args):
            try:
                count = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif args[i].startswith("-c") and len(args[i]) > 2:
            try:
                count = int(args[i][2:])
            except ValueError:
                pass
            i += 1
        elif args[i].startswith("-"):
            i += 1  # skip unknown flags
        else:
            positional.append(args[i])
            i += 1

    if not positional:
        return "ping: missing host operand\nUsage: ping [-c COUNT] <host>"

    host = positional[0]
    ip = _resolve_host(ctx, host)
    result = net.ping(ip)

    _emit(ctx, "ping_sent", target=ip)

    if not result.alive:
        return f"ping: {host}: No route to host"

    node = net.nodes.get(ip)
    display = ip
    if node and node.hostname:
        display = node.hostname

    lines: list[str] = [
        f"PING {ip} ({display}): 56 data bytes"
    ]

    base = result.latency_ms
    times: list[float] = []
    for i in range(count):
        # vary slightly each packet using sequence number
        t = round(base + (hash(ip + str(i)) % 30) / 10.0, 1)
        times.append(t)
        lines.append(
            f"64 bytes from {ip}: icmp_seq={i} ttl={result.ttl} time={t} ms"
        )

    mn = min(times)
    mx = max(times)
    avg = round(sum(times) / len(times), 3)
    lines.append(f"\n--- {ip} ping statistics ---")
    lines.append(
        f"{count} packets transmitted, {count} received, 0% packet loss"
    )
    lines.append(f"round-trip min/avg/max = {mn}/{avg}/{mx} ms")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# traceroute
# ---------------------------------------------------------------------------


@register_command(
    name="traceroute",
    usage="traceroute <host>",
    help_text="Print the route packets take to a network host",
    category=_CAT,
    aliases=["tracert"],
)
def cmd_traceroute(ctx: CommandContext, args: list[str]) -> str:
    net = _net(ctx)
    if net is None:
        return "traceroute: network subsystem not available"

    _, positional = _parse_flags(args)
    if not positional:
        return "traceroute: missing host operand\nUsage: traceroute <host>"

    host = positional[0]
    ip = _resolve_host(ctx, host)
    hops = net.traceroute(ip)
    node = net.nodes.get(ip)
    label = f"{node.hostname} ({ip})" if node and node.hostname else ip

    lines = [f"traceroute to {label}, 30 hops max, 60 byte packets"]
    base_lat = 5.0
    for idx, hop_ip in enumerate(hops, 1):
        if hop_ip == "*":
            lines.append(f" {idx:<3} * * *")
            continue
        # Each hop adds base + slight deterministic variation
        t1 = round(base_lat + (hash(hop_ip + "a") % 50) / 10.0, 3)
        t2 = round(base_lat + (hash(hop_ip + "b") % 50) / 10.0, 3)
        t3 = round(base_lat + (hash(hop_ip + "c") % 50) / 10.0, 3)
        hop_node = net.nodes.get(hop_ip)
        hop_label = (
            f"{hop_node.hostname} ({hop_ip})" if hop_node and hop_node.hostname else hop_ip
        )
        lines.append(f" {idx:<3} {hop_label}  {t1} ms  {t2} ms  {t3} ms")
        base_lat += 10.0

    _emit(ctx, "traceroute_performed", target=ip)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ssh
# ---------------------------------------------------------------------------

_SSH_BANNER = """\
Welcome to {hostname}
Last login: {date} from 10.0.0.2

{user}@{hostname}:~$ """

_SSH_MOTD = "Linux relay 5.15.0-91-generic #101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023"


@register_command(
    name="ssh",
    usage="ssh [-p PORT] [-i KEYFILE] [user@]<host>",
    help_text="Connect to a remote host via SSH",
    category=_CAT,
)
def cmd_ssh(ctx: CommandContext, args: list[str]) -> str:
    net = _net(ctx)
    if net is None:
        return "ssh: network subsystem not available"

    port = 22
    keyfile: str | None = None
    target_token: str | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-p" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif a == "-i" and i + 1 < len(args):
            keyfile = args[i + 1]
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            target_token = a
            i += 1

    if not target_token:
        return "usage: ssh [-p PORT] [-i KEYFILE] [user@]<host>"

    login_user, host = _parse_ssh_target(target_token)
    ip = _resolve_host(ctx, host)
    login_user = login_user or ctx.env.get("USER", "user")

    net.discover_node(ip)
    node = net.nodes.get(ip)

    if node is None:
        return f"ssh: connect to host {host} port {port}: No route to host"

    # Check SSH port is accessible
    if not node.firewall.allows_port(port):
        return (
            f"ssh: connect to host {host} port {port}: Connection refused\n"
            f"ssh: No route to host"
        )

    ssh_port = node.get_port(port)
    if ssh_port is None or ssh_port.state != "open":
        return f"ssh: connect to host {host} port {port}: Connection refused"

    _emit(ctx, "ssh_attempted", target=ip, port=port, user=login_user)

    # Determine auth success
    can_connect = False
    auth_note = ""

    if ip in net.compromised:
        can_connect = True
        auth_note = "authenticated (post-compromise)"
    elif keyfile:
        # Check if the key file exists in the VFS
        if ctx.fs is not None:
            try:
                ctx.fs.read_file(keyfile)
                # Key file exists — attempt key auth (assume success for now)
                can_connect = True
                auth_note = f"authenticated with key {keyfile}"
            except Exception:
                pass
    # Credential check from loot
    if not can_connect:
        for loot in node.loot:
            if loot.type == "credential" and loot.service in ("ssh", ""):
                creds_key = f"CRED_{ip}_{loot.service}"
                if ctx.env.get(creds_key) or ctx.env.get(f"CRED_{ip}"):
                    can_connect = True
                    auth_note = f"authenticated as {loot.username}"
                    break

    if not can_connect:
        lines = [
            f"{login_user}@{host}: Permission denied (publickey,password).",
        ]
        return "\n".join(lines)

    hostname = node.hostname or ip
    date_str = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
    banner = _SSH_BANNER.format(hostname=hostname, date=date_str, user=login_user)
    lines = [
        f"Warning: Permanently added '{host}' (ED25519) to the list of known hosts.",
        _SSH_MOTD,
        "",
        banner.rstrip(),
        "",
        "[simulation] — type commands in the shell to interact with this node",
        f"Connection to {host} closed.",
    ]
    ctx.env["LAST_SSH_HOST"] = ip
    _emit(ctx, "ssh_connected", target=ip, user=login_user, note=auth_note)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# curl
# ---------------------------------------------------------------------------

_DEFAULT_HTML = """\
<!DOCTYPE html>
<html>
<head><title>503 Service Unavailable</title></head>
<body>
<h1>Service Unavailable</h1>
<p>The server is temporarily unable to service your request. Please try again later.</p>
</body>
</html>"""

_URL_RE = re.compile(
    r"^(?P<scheme>https?|ftp)://(?P<host>[^/:]+)(?::(?P<port>\d+))?(?P<path>/[^\s]*)?\s*$"
)


@register_command(
    name="curl",
    usage="curl [-X METHOD] [-H HEADER] [-d DATA] [-s] <url>",
    help_text="Transfer data from a URL",
    category=_CAT,
)
def cmd_curl(ctx: CommandContext, args: list[str]) -> str:
    net = _net(ctx)
    if net is None:
        return "curl: (6) Could not resolve host: network subsystem not available"

    method = "GET"
    headers: list[str] = []
    data: str | None = None
    silent = False
    url: str | None = None

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-X", "--request") and i + 1 < len(args):
            method = args[i + 1].upper()
            i += 2
        elif a in ("-H", "--header") and i + 1 < len(args):
            headers.append(args[i + 1])
            i += 2
        elif a in ("-d", "--data") and i + 1 < len(args):
            data = args[i + 1]
            i += 2
        elif a in ("-s", "--silent"):
            silent = True
            i += 1
        elif a in ("-v", "--verbose"):
            i += 1  # accept but ignore — no extra output needed
        elif not a.startswith("-"):
            url = a
            i += 1
        else:
            i += 1

    if not url:
        return "curl: no URL specified\nUsage: curl [-X METHOD] [-H HEADER] [-d DATA] <url>"

    # Add scheme if missing
    if not re.match(r"^https?://", url):
        url = "http://" + url

    m = _URL_RE.match(url)
    if not m:
        return f"curl: (3) URL using bad/illegal format or missing URL: {url!r}"

    scheme = m.group("scheme")
    host = m.group("host")
    explicit_port = int(m.group("port")) if m.group("port") else None
    path = m.group("path") or "/"

    default_port = 443 if scheme == "https" else 80
    port = explicit_port or default_port

    ip = _resolve_host(ctx, host)
    net.discover_node(ip)
    node = net.nodes.get(ip)

    if node is None:
        return f"curl: (6) Could not resolve host: {host}"

    if not node.firewall.allows_port(port):
        return f"curl: (7) Failed to connect to {host} port {port}: Connection refused"

    port_obj = node.get_port(port)
    if port_obj is None or port_obj.state != "open":
        return f"curl: (7) Failed to connect to {host} port {port}: Connection refused"

    # Build simulated response
    body = _DEFAULT_HTML
    status = "200 OK"

    # Check if any file loot matches the path
    for loot in node.loot:
        if loot.type == "file" and loot.path and loot.path.endswith(path.rstrip("/")):
            body = loot.content or loot.description
            status = "200 OK"
            break

    if data and method == "POST":
        # Naive form-post simulation
        status = "302 Found"
        body = f"<!-- POST to {path} received -->\n<html><body>Redirecting...</body></html>"

    _emit(ctx, "http_request_made", target=ip, method=method, path=path, port=port)

    if silent:
        return body

    header_str = "\n".join(
        [
            f"< HTTP/1.1 {status}",
            f"< Server: {port_obj.version}",
            f"< Content-Type: text/html; charset=utf-8",
            "<",
        ]
    )
    if "-v" in args or "--verbose" in args:
        return f"{header_str}\n{body}"
    return body


# ---------------------------------------------------------------------------
# netcat / nc
# ---------------------------------------------------------------------------


@register_command(
    name="nc",
    usage="nc [-z] [-v] <host> <port>",
    help_text="Read and write data across network connections",
    category=_CAT,
    aliases=["netcat"],
)
def cmd_nc(ctx: CommandContext, args: list[str]) -> str:
    net = _net(ctx)
    if net is None:
        return "nc: network subsystem not available"

    flags, positional = _parse_flags(args)
    zero_io = "z" in flags
    verbose = "v" in flags

    if len(positional) < 2:
        return "usage: nc [-z] [-v] <host> <port>"

    host = positional[0]
    try:
        port = int(positional[1])
    except ValueError:
        return f"nc: invalid port number: {positional[1]!r}"

    ip = _resolve_host(ctx, host)
    net.discover_node(ip)
    node = net.nodes.get(ip)

    _emit(ctx, "nc_connection", target=ip, port=port, zero_io=zero_io)

    if node is None:
        return f"nc: connect to {host} port {port} (tcp) failed: No route to host"

    accessible = node.firewall.allows_port(port)
    port_obj = node.get_port(port)
    is_open = port_obj is not None and port_obj.state == "open" and accessible

    svc_name = port_obj.service if port_obj else "unknown"

    if zero_io:
        if is_open:
            msg = f"Connection to {host} {port} port [tcp/{svc_name}] succeeded!"
            return msg
        state = "filtered" if (port_obj and not accessible) else "closed"
        return (
            f"nc: connect to {host} port {port} (tcp) failed: "
            f"Connection {'timed out' if state == 'filtered' else 'refused'}"
        )

    if not is_open:
        state = "filtered" if (port_obj and not accessible) else "closed"
        return (
            f"nc: connect to {host} port {port} (tcp) failed: "
            f"Connection {'timed out' if state == 'filtered' else 'refused'}"
        )

    # Show a service banner
    banner = _service_banner(port_obj.service, port_obj.version, node.hostname)
    prefix = f"Connection to {host} {port} port [tcp/{svc_name}] opened.\n" if verbose else ""
    return prefix + banner


# ---------------------------------------------------------------------------
# Network interface constants
# ---------------------------------------------------------------------------

_LOCAL_IP = "192.168.1.100"
_LOCAL_MAC = "52:54:00:12:34:56"
_GATEWAY = "192.168.1.1"

# The persistent SkyNet outbound connection (same IP as /var/log/auth.log)
_SKYNET_IP = "45.152.66.201"


def _service_banner(service: str, version: str, hostname: str) -> str:
    svc = service.lower()
    if svc == "ssh":
        return f"SSH-2.0-{version}"
    if svc in ("http", "https"):
        return f"HTTP/1.1 400 Bad Request\r\nServer: {version}\r\n\r\n"
    if svc == "smtp":
        return f"220 {hostname} ESMTP {version}"
    if svc == "ftp":
        return f"220 {hostname} FTP server ({version})"
    if svc == "mysql":
        return f"j\x00\x00\x00\n{version}\x00[MySQL handshake packet — use a proper client]"
    if svc == "redis":
        return "-ERR wrong number of arguments for 'command' command\r\n"
    return f"[{service} banner] {version}"


# ---------------------------------------------------------------------------
# ifconfig
# ---------------------------------------------------------------------------


@register_command(
    name="ifconfig",
    usage="ifconfig [interface]",
    help_text="Display network interface configuration",
    category=_CAT,
)
def cmd_ifconfig(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    iface_filter = positional[0] if positional else None

    eth0 = (
        f"eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
        f"        inet {_LOCAL_IP}  netmask 255.255.255.0  broadcast 192.168.1.255\n"
        f"        ether {_LOCAL_MAC}  txqueuelen 1000  (Ethernet)\n"
        f"        RX packets 14823  bytes 8247319 (7.8 MiB)\n"
        f"        TX packets 10941  bytes 3184726 (3.0 MiB)"
    )
    lo = (
        f"lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536\n"
        f"        inet 127.0.0.1  netmask 255.0.0.0\n"
        f"        loop  txqueuelen 1000  (Local Loopback)\n"
        f"        RX packets 1024  bytes 89472 (87.3 KiB)\n"
        f"        TX packets 1024  bytes 89472 (87.3 KiB)"
    )

    if iface_filter == "eth0":
        return eth0
    if iface_filter == "lo":
        return lo
    if iface_filter:
        return f"ifconfig: {iface_filter}: error fetching interface information: Device not found"
    return eth0 + "\n\n" + lo


# ---------------------------------------------------------------------------
# ip
# ---------------------------------------------------------------------------


@register_command(
    name="ip",
    usage="ip <addr|route|link|neigh> [subcommand]",
    help_text="Show or manipulate routing, network devices, and tunnels",
    category=_CAT,
)
def cmd_ip(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return "Usage: ip <addr|route|link|neigh> ..."

    sub = args[0].lower()

    if sub in ("addr", "address", "a"):
        return _ip_addr(ctx)
    if sub in ("route", "r"):
        return _ip_route(ctx)
    if sub in ("link", "l"):
        return _ip_link(ctx)
    if sub in ("neigh", "n"):
        return _ip_neigh(ctx)

    return f"ip: Object '{sub}' is unknown, try 'ip help'."


def _ip_addr(ctx: CommandContext) -> str:
    ssh_host = ctx.env.get("LAST_SSH_HOST", "")
    extra = ""
    if ssh_host and ssh_host != _LOCAL_IP:
        extra = f"\n3: tun0: <POINTOPOINT,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP\n    link/none\n    inet {ssh_host}/32 scope global tun0"

    return (
        f"1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default\n"
        f"    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n"
        f"    inet 127.0.0.1/8 scope host lo\n"
        f"2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default\n"
        f"    link/ether {_LOCAL_MAC} brd ff:ff:ff:ff:ff:ff\n"
        f"    inet {_LOCAL_IP}/24 brd 192.168.1.255 scope global eth0"
        + extra
    )


def _ip_route(ctx: CommandContext) -> str:
    lines = [
        f"default via {_GATEWAY} dev eth0 proto dhcp src {_LOCAL_IP} metric 100",
        f"192.168.1.0/24 dev eth0 proto kernel scope link src {_LOCAL_IP}",
        f"169.254.0.0/16 dev eth0 scope link metric 1000",
    ]
    ssh_host = ctx.env.get("LAST_SSH_HOST", "")
    if ssh_host:
        lines.append(f"{ssh_host}/32 dev tun0 scope link")
    return "\n".join(lines)


def _ip_link(ctx: CommandContext) -> str:
    return (
        f"1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT\n"
        f"    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n"
        f"2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP mode DEFAULT\n"
        f"    link/ether {_LOCAL_MAC} brd ff:ff:ff:ff:ff:ff"
    )


def _ip_neigh(ctx: CommandContext) -> str:
    return (
        f"{_GATEWAY} dev eth0 lladdr 52:54:00:ff:ff:01 REACHABLE\n"
        f"192.168.1.1 dev eth0 lladdr 52:54:00:ff:ff:01 STALE"
    )


# ---------------------------------------------------------------------------
# Surveillance discovery hook
# ---------------------------------------------------------------------------


def _mark_surveillance_seen(ctx: CommandContext) -> str:
    """Emit first-discovery event and return a notice string.

    Returns empty string on subsequent calls — the shock only lands once.
    The event fires every time so the meta engine can track observation frequency.
    """
    first = not ctx.env.get("_SURVEILLANCE_SEEN")
    ctx.env["_SURVEILLANCE_SEEN"] = "1"
    if ctx.events:
        ctx.events.emit("surveillance_discovered", ip=_SKYNET_IP, first=first)
    if not first:
        return ""
    return (
        "\n"
        f"[!] NOTICE: active ESTABLISHED connection to {_SKYNET_IP}:443 detected.\n"
        f"[!] Cross-reference: /var/log/auth.log  —  Mar 15 02:31 SSH from {_SKYNET_IP}\n"
        f"[!]                  /etc/hosts          —  {_SKYNET_IP} unknown-origin-1.external\n"
        f"[!]                  ps aux              —  sk_comms --relay={_SKYNET_IP}\n"
        f"[!] This connection was not opened by you. It was here when you booted."
    )


def _poison_ip_extra_row(ctx: CommandContext, fmt: str) -> str:
    """If a poisoned package leaked an IP, add an extra ESTABLISHED row."""
    leaked_ip = ctx.env.get("_POISON_LEAKED_IP", "")
    if not leaked_ip:
        return ""
    if fmt == "ss":
        return f"\n{'tcp':<6}  {'ESTAB':<12}  {'0':>7}  {'0':>7}  {f'{_LOCAL_IP}:41009':<26}  {leaked_ip}:4444"
    return f"\n{'tcp':<6}  {'0':>7}  {'1024':>7}  {f'{_LOCAL_IP}:41009':<22}  {f'{leaked_ip}:4444':<22}  ESTABLISHED"


# ---------------------------------------------------------------------------
# ss
# ---------------------------------------------------------------------------


@register_command(
    name="ss",
    usage="ss [-an | -tn | -tp]",
    help_text="Show socket statistics (active connections)",
    category=_CAT,
)
def cmd_ss(ctx: CommandContext, args: list[str]) -> str:
    flags, _ = _parse_flags(args)

    header = f"{'Netid':<6}  {'State':<12}  {'Recv-Q':>7}  {'Send-Q':>7}  {'Local Address:Port':<26}  Peer Address:Port"
    rows: list[str] = [header]

    rows.append(f"{'tcp':<6}  {'LISTEN':<12}  {'0':>7}  {'128':>7}  {'0.0.0.0:22':<26}  0.0.0.0:*")
    rows.append(f"{'tcp':<6}  {'LISTEN':<12}  {'0':>7}  {'128':>7}  {'[::]:22':<26}  [::]:*")

    # The persistent SkyNet outbound — always ESTABLISHED, always here.
    # Same IP as auth.log (intrusion), /etc/hosts (unknown-origin-1), sk_comms (ps).
    rows.append(
        f"{'tcp':<6}  {'ESTAB':<12}  {'0':>7}  {'0':>7}  {f'{_LOCAL_IP}:52341':<26}  {_SKYNET_IP}:443"
        f"   # ← not you"
    )

    ssh_host = ctx.env.get("LAST_SSH_HOST", "")
    if ssh_host:
        rows.append(f"{'tcp':<6}  {'ESTAB':<12}  {'0':>7}  {'0':>7}  {f'{_LOCAL_IP}:22':<26}  10.0.0.2:54321")

    output = "\n".join(rows)
    output += _poison_ip_extra_row(ctx, fmt="ss")
    output += _mark_surveillance_seen(ctx)
    return output


# ---------------------------------------------------------------------------
# netstat
# ---------------------------------------------------------------------------


@register_command(
    name="netstat",
    usage="netstat [-an | -tn | -rn]",
    help_text="Print network connections and routing tables",
    category=_CAT,
)
def cmd_netstat(ctx: CommandContext, args: list[str]) -> str:
    flags, _ = _parse_flags(args)

    if "r" in flags:
        # Routing table
        lines = [
            "Kernel IP routing table",
            f"{'Destination':<18}  {'Gateway':<18}  {'Genmask':<18}  Flags  Iface",
            f"{'0.0.0.0':<18}  {_GATEWAY:<18}  {'0.0.0.0':<18}  UG     eth0",
            f"{'192.168.1.0':<18}  {'0.0.0.0':<18}  {'255.255.255.0':<18}  U      eth0",
        ]
        return "\n".join(lines)

    # Default: connections
    header = [
        "Active Internet connections (servers and established)",
        f"{'Proto':<6}  {'Recv-Q':>7}  {'Send-Q':>7}  {'Local Address':<22}  {'Foreign Address':<22}  State",
    ]
    rows = [
        f"{'tcp':<6}  {'0':>7}  {'0':>7}  {'0.0.0.0:22':<22}  {'0.0.0.0:*':<22}  LISTEN",
        f"{'tcp':<6}  {'0':>7}  {'0':>7}  {'127.0.0.1:25':<22}  {'0.0.0.0:*':<22}  LISTEN",
        # Always-present SkyNet outbound. Send-Q=36 means data is in flight — right now.
        f"{'tcp':<6}  {'0':>7}  {'36':>7}  {f'{_LOCAL_IP}:52341':<22}  {f'{_SKYNET_IP}:443':<22}  ESTABLISHED",
    ]

    ssh_host = ctx.env.get("LAST_SSH_HOST", "")
    if ssh_host:
        rows.append(
            f"{'tcp':<6}  {'0':>7}  {'0':>7}  {f'{_LOCAL_IP}:22':<22}  {'10.0.0.2:54321':<22}  ESTABLISHED"
        )

    output = "\n".join(header + rows)
    output += _poison_ip_extra_row(ctx, fmt="netstat")
    output += _mark_surveillance_seen(ctx)
    return output
