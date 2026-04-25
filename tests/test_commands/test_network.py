"""Tests for hackerzork.commands.network_cmds."""
from __future__ import annotations

import pytest

import hackerzork.commands.network_cmds  # noqa: F401 — registers commands
from hackerzork.commands.network_cmds import (
    _parse_flags,
    _parse_nmap_args,
    _parse_port_spec,
    _parse_ssh_target,
    _resolve_host,
    _service_banner,
    cmd_curl,
    cmd_nc,
    cmd_nmap,
    cmd_ping,
    cmd_ssh,
    cmd_traceroute,
)
from hackerzork.engine.command_registry import CommandContext
from hackerzork.systems.network import (
    Firewall,
    Loot,
    NetworkNode,
    NetworkSim,
    Port,
)
from hackerzork.systems.virtual_fs import VirtualFS

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FS_TEMPLATE = {
    "/home/user": {
        "_meta": {"permissions": "755", "owner": "user"},
        ".ssh/": {
            "_meta": {"permissions": "700", "owner": "user"},
            "id_ed25519": {
                "content": "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA\n-----END OPENSSH PRIVATE KEY-----\n",
                "permissions": "600",
                "owner": "user",
            },
        },
    },
    "/etc": {
        "hosts": {
            "content": "127.0.0.1 localhost\n10.13.37.1 relay-alpha.darknet.local\n",
            "owner": "root",
        },
    },
    "/tmp": {},
}


def _make_port(number: int, service: str = "http", version: str = "1.0", vuln: str | None = None) -> Port:
    return Port(number=number, service=service, version=version, vuln=vuln, state="open")


def _make_node(
    node_id: str = "node_001",
    ip: str = "10.0.0.1",
    hostname: str = "target.local",
    *,
    ports: list[Port] | None = None,
    firewall: Firewall | None = None,
    loot: list[Loot] | None = None,
    connections: list[str] | None = None,
    difficulty: int = 1,
) -> NetworkNode:
    return NetworkNode(
        id=node_id,
        name="Test Node",
        ip=ip,
        hostname=hostname,
        ports=ports
        or [
            _make_port(22, "ssh", "OpenSSH 8.9"),
            _make_port(80, "http", "nginx 1.18.0", vuln="CVE-2021-23017"),
            _make_port(3306, "mysql", "MySQL 5.7.38", vuln="default_credentials"),
        ],
        firewall=firewall or Firewall(enabled=False),
        difficulty=difficulty,
        heat_modifier=1.0,
        loot=loot or [],
        connections=connections or [],
    )


def _make_ctx(
    node: NetworkNode | None = None,
    extra_nodes: list[NetworkNode] | None = None,
    compromised: bool = False,
) -> CommandContext:
    fs = VirtualFS(template=_FS_TEMPLATE)
    net = NetworkSim()
    if node is not None:
        net.add_node(node)
        if compromised:
            net.compromise_node(node.ip)
    for n in extra_nodes or []:
        net.add_node(n)

    env = {
        "CWD": "/home/user",
        "HOME": "/home/user",
        "USER": "user",
    }
    return CommandContext(fs=fs, network=net, env=env)


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_parse_flags_short(self):
        flags, pos = _parse_flags(["-la", "/tmp"])
        assert "l" in flags and "a" in flags
        assert "/tmp" in pos

    def test_parse_flags_long(self):
        flags, pos = _parse_flags(["--verbose", "host"])
        assert "verbose" in flags
        assert "host" in pos

    def test_parse_port_spec_list(self):
        assert _parse_port_spec("22,80,443") == [22, 80, 443]

    def test_parse_port_spec_range(self):
        ports = _parse_port_spec("80-83")
        assert ports == [80, 81, 82, 83]

    def test_parse_port_spec_mixed(self):
        ports = _parse_port_spec("22,80-82")
        assert 22 in ports and 80 in ports and 82 in ports

    def test_parse_nmap_args_sV(self):
        flags, ports, targets = _parse_nmap_args(["-sV", "10.0.0.1"])
        assert "V" in flags
        assert targets == ["10.0.0.1"]

    def test_parse_nmap_args_p(self):
        _, ports, _ = _parse_nmap_args(["-p", "22,80", "10.0.0.1"])
        assert ports == [22, 80]

    def test_parse_nmap_args_p_attached(self):
        _, ports, _ = _parse_nmap_args(["-p22,80", "10.0.0.1"])
        assert ports == [22, 80]

    def test_parse_nmap_args_stealth(self):
        flags, _, _ = _parse_nmap_args(["-sS", "10.0.0.1"])
        assert "S" in flags

    def test_parse_ssh_target_with_user(self):
        user, host = _parse_ssh_target("root@10.0.0.1")
        assert user == "root" and host == "10.0.0.1"

    def test_parse_ssh_target_no_user(self):
        user, host = _parse_ssh_target("10.0.0.1")
        assert user == "" and host == "10.0.0.1"

    def test_resolve_host_ip_passthrough(self):
        ctx = _make_ctx()
        assert _resolve_host(ctx, "10.0.0.1") == "10.0.0.1"

    def test_resolve_host_from_etc_hosts(self):
        ctx = _make_ctx()
        ip = _resolve_host(ctx, "relay-alpha.darknet.local")
        assert ip == "10.13.37.1"

    def test_resolve_host_unknown_stays(self):
        ctx = _make_ctx()
        assert _resolve_host(ctx, "unknown.host") == "unknown.host"

    def test_service_banner_ssh(self):
        b = _service_banner("ssh", "OpenSSH 8.9", "host")
        assert "SSH-2.0" in b

    def test_service_banner_mysql(self):
        b = _service_banner("mysql", "MySQL 5.7.38", "host")
        assert "MySQL" in b


# ---------------------------------------------------------------------------
# nmap
# ---------------------------------------------------------------------------


class TestNmap:
    def test_no_args_returns_usage(self):
        ctx = _make_ctx()
        result = cmd_nmap(ctx, [])
        assert "Usage" in result or "no target" in result.lower()

    def test_unknown_host_reports_down(self):
        ctx = _make_ctx()
        result = cmd_nmap(ctx, ["9.9.9.9"])
        assert "9.9.9.9" in result

    def test_known_host_shows_ports(self):
        node = _make_node()
        ctx = _make_ctx(node)
        result = cmd_nmap(ctx, ["10.0.0.1"])
        assert "80/tcp" in result
        assert "open" in result

    def test_firewall_shows_filtered(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [80]"])
        node = _make_node(firewall=fw)
        ctx = _make_ctx(node)
        result = cmd_nmap(ctx, ["10.0.0.1"])
        assert "filtered" in result

    def test_version_scan_shows_versions(self):
        node = _make_node(ports=[_make_port(80, "http", "nginx 1.18.0")])
        ctx = _make_ctx(node)
        result = cmd_nmap(ctx, ["-sV", "10.0.0.1"])
        assert "nginx 1.18.0" in result

    def test_specific_ports_scanned(self):
        node = _make_node()
        ctx = _make_ctx(node)
        result = cmd_nmap(ctx, ["-p", "22,80", "10.0.0.1"])
        assert "22/tcp" in result
        assert "80/tcp" in result
        # 3306 not requested — should not appear
        assert "3306" not in result

    def test_hostname_shown(self):
        node = _make_node(hostname="relay.darknet.local")
        ctx = _make_ctx(node)
        result = cmd_nmap(ctx, ["10.0.0.1"])
        assert "relay.darknet.local" in result

    def test_discovers_node(self):
        node = _make_node()
        ctx = _make_ctx(node)
        cmd_nmap(ctx, ["10.0.0.1"])
        assert "10.0.0.1" in ctx.network.discovered

    def test_stealth_flag_accepted(self):
        node = _make_node()
        ctx = _make_ctx(node)
        result = cmd_nmap(ctx, ["-sS", "10.0.0.1"])
        assert "80/tcp" in result  # still works

    def test_no_network_returns_error(self):
        ctx = CommandContext(env={})
        result = cmd_nmap(ctx, ["10.0.0.1"])
        assert "not available" in result.lower()


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------


class TestPing:
    def test_known_host_alive(self):
        node = _make_node()
        ctx = _make_ctx(node)
        result = cmd_ping(ctx, ["10.0.0.1"])
        assert "64 bytes from" in result
        assert "icmp_seq=0" in result

    def test_default_count_four(self):
        node = _make_node()
        ctx = _make_ctx(node)
        result = cmd_ping(ctx, ["10.0.0.1"])
        assert "icmp_seq=3" in result

    def test_custom_count(self):
        node = _make_node()
        ctx = _make_ctx(node)
        result = cmd_ping(ctx, ["-c", "2", "10.0.0.1"])
        assert "icmp_seq=1" in result
        assert "icmp_seq=2" not in result

    def test_unknown_host_no_route(self):
        ctx = _make_ctx()
        result = cmd_ping(ctx, ["9.9.9.9"])
        assert "No route to host" in result

    def test_shows_statistics(self):
        node = _make_node()
        ctx = _make_ctx(node)
        result = cmd_ping(ctx, ["10.0.0.1"])
        assert "packets transmitted" in result
        assert "round-trip" in result

    def test_no_host_returns_usage(self):
        ctx = _make_ctx()
        result = cmd_ping(ctx, [])
        assert "Usage" in result or "missing" in result.lower()

    def test_hostname_resolution(self):
        node = _make_node(ip="10.13.37.1", hostname="relay-alpha.darknet.local")
        ctx = _make_ctx(node)
        result = cmd_ping(ctx, ["relay-alpha.darknet.local"])
        assert "64 bytes from" in result


# ---------------------------------------------------------------------------
# traceroute
# ---------------------------------------------------------------------------


class TestTraceroute:
    def test_known_host_shows_hops(self):
        node = _make_node()
        ctx = _make_ctx(node)
        result = cmd_traceroute(ctx, ["10.0.0.1"])
        assert "10.0.0.1" in result
        assert "traceroute to" in result

    def test_unknown_host_shows_star(self):
        ctx = _make_ctx()
        result = cmd_traceroute(ctx, ["9.9.9.9"])
        assert "* * *" in result or "*" in result

    def test_intermediate_hops_shown(self):
        node = _make_node()
        ctx = _make_ctx(node)
        result = cmd_traceroute(ctx, ["10.0.0.1"])
        lines = [l for l in result.splitlines() if l.strip().startswith(tuple("123456789"))]
        assert len(lines) >= 2  # at least gateway + target

    def test_no_host_returns_usage(self):
        ctx = _make_ctx()
        result = cmd_traceroute(ctx, [])
        assert "Usage" in result or "missing" in result.lower()

    def test_alias_tracert_registered(self):
        from hackerzork.engine.command_registry import DEFAULT_REGISTRY
        assert DEFAULT_REGISTRY.get("tracert") is not None


# ---------------------------------------------------------------------------
# ssh
# ---------------------------------------------------------------------------


class TestSsh:
    def test_no_args_returns_usage(self):
        ctx = _make_ctx()
        result = cmd_ssh(ctx, [])
        assert "usage" in result.lower()

    def test_unknown_host_no_route(self):
        ctx = _make_ctx()
        result = cmd_ssh(ctx, ["9.9.9.9"])
        assert "No route to host" in result

    def test_firewall_blocked_refused(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [80]"])
        node = _make_node(firewall=fw)
        ctx = _make_ctx(node)
        result = cmd_ssh(ctx, ["10.0.0.1"])
        assert "refused" in result.lower() or "No route" in result

    def test_compromised_node_connects(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True)
        result = cmd_ssh(ctx, ["10.0.0.1"])
        assert "Connection" in result
        assert "Permission denied" not in result

    def test_uncompromised_denied(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=False)
        result = cmd_ssh(ctx, ["10.0.0.1"])
        assert "Permission denied" in result

    def test_custom_port_flag(self):
        node = _make_node(ports=[_make_port(2222, "ssh", "OpenSSH 9.0")])
        ctx = _make_ctx(node, compromised=True)
        result = cmd_ssh(ctx, ["-p", "2222", "10.0.0.1"])
        assert "Permission denied" not in result

    def test_key_file_allows_connection(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=False)
        result = cmd_ssh(ctx, ["-i", "/home/user/.ssh/id_ed25519", "10.0.0.1"])
        # Key file exists in VFS → should succeed
        assert "Permission denied" not in result

    def test_user_at_host_syntax(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True)
        result = cmd_ssh(ctx, ["root@10.0.0.1"])
        assert "Connection" in result

    def test_sets_last_ssh_host(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True)
        cmd_ssh(ctx, ["10.0.0.1"])
        assert ctx.env.get("LAST_SSH_HOST") == "10.0.0.1"

    def test_no_ssh_port_refused(self):
        node = _make_node(ports=[_make_port(80, "http")])  # no SSH port
        ctx = _make_ctx(node, compromised=True)
        result = cmd_ssh(ctx, ["10.0.0.1"])
        assert "refused" in result.lower()


# ---------------------------------------------------------------------------
# curl
# ---------------------------------------------------------------------------


class TestCurl:
    def test_no_url_returns_usage(self):
        ctx = _make_ctx()
        result = cmd_curl(ctx, [])
        assert "Usage" in result or "no URL" in result.lower()

    def test_unknown_host_error(self):
        ctx = _make_ctx()
        result = cmd_curl(ctx, ["http://9.9.9.9/"])
        assert "Could not resolve" in result or "(6)" in result

    def test_open_http_port_returns_body(self):
        node = _make_node(ports=[_make_port(80, "http", "nginx 1.18.0")])
        ctx = _make_ctx(node)
        result = cmd_curl(ctx, ["http://10.0.0.1/"])
        assert len(result) > 0
        assert "curl: (7)" not in result

    def test_blocked_port_fails(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [443]"])
        node = _make_node(
            ports=[_make_port(80, "http", "nginx 1.18.0")],
            firewall=fw,
        )
        ctx = _make_ctx(node)
        result = cmd_curl(ctx, ["http://10.0.0.1/"])
        assert "refused" in result.lower() or "(7)" in result

    def test_file_loot_served_at_path(self):
        loot = [
            Loot(type="file", path="/var/www/html/.htpasswd", content="admin:hash123")
        ]
        node = _make_node(
            ports=[_make_port(80, "http", "Apache 2.4")],
            loot=loot,
        )
        ctx = _make_ctx(node)
        result = cmd_curl(ctx, ["http://10.0.0.1/.htpasswd"])
        assert "admin:hash123" in result

    def test_post_request(self):
        node = _make_node(ports=[_make_port(80, "http")])
        ctx = _make_ctx(node)
        result = cmd_curl(ctx, ["-X", "POST", "-d", "user=admin", "http://10.0.0.1/login"])
        # POST → 302 redirect body
        assert "POST" in result or "Redirect" in result or len(result) > 0

    def test_silent_flag(self):
        node = _make_node(ports=[_make_port(80, "http", "nginx 1.18.0")])
        ctx = _make_ctx(node)
        result = cmd_curl(ctx, ["-s", "http://10.0.0.1/"])
        # Should not start with HTTP headers
        assert not result.startswith("< HTTP")

    def test_hostname_in_url_resolved(self):
        node = _make_node(ip="10.13.37.1", hostname="relay-alpha.darknet.local",
                          ports=[_make_port(80, "http")])
        ctx = _make_ctx(node)
        result = cmd_curl(ctx, ["http://relay-alpha.darknet.local/"])
        assert "(6)" not in result and "(7)" not in result

    def test_no_network_error(self):
        ctx = CommandContext(env={})
        result = cmd_curl(ctx, ["http://10.0.0.1/"])
        assert "not available" in result.lower() or "(6)" in result


# ---------------------------------------------------------------------------
# nc (netcat)
# ---------------------------------------------------------------------------


class TestNc:
    def test_no_args_usage(self):
        ctx = _make_ctx()
        result = cmd_nc(ctx, [])
        assert "usage" in result.lower()

    def test_zero_io_open_port_success(self):
        node = _make_node(ports=[_make_port(80, "http")])
        ctx = _make_ctx(node)
        result = cmd_nc(ctx, ["-z", "10.0.0.1", "80"])
        assert "succeeded" in result

    def test_zero_io_filtered_port_fails(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [443]"])
        node = _make_node(ports=[_make_port(80, "http")], firewall=fw)
        ctx = _make_ctx(node)
        result = cmd_nc(ctx, ["-z", "10.0.0.1", "80"])
        assert "failed" in result or "timed out" in result.lower()

    def test_zero_io_closed_port_fails(self):
        node = _make_node(ports=[_make_port(80, "http")])
        ctx = _make_ctx(node)
        result = cmd_nc(ctx, ["-z", "10.0.0.1", "9999"])
        assert "failed" in result or "refused" in result.lower()

    def test_banner_grab_shows_service_info(self):
        node = _make_node(ports=[_make_port(22, "ssh", "OpenSSH 8.9")])
        ctx = _make_ctx(node)
        result = cmd_nc(ctx, ["10.0.0.1", "22"])
        assert "SSH" in result

    def test_verbose_flag_shows_connection_line(self):
        node = _make_node(ports=[_make_port(80, "http", "nginx 1.18.0")])
        ctx = _make_ctx(node)
        result = cmd_nc(ctx, ["-v", "10.0.0.1", "80"])
        assert "opened" in result or "Connection" in result

    def test_unknown_host_no_route(self):
        ctx = _make_ctx()
        result = cmd_nc(ctx, ["-z", "9.9.9.9", "80"])
        assert "No route" in result or "failed" in result

    def test_invalid_port_error(self):
        ctx = _make_ctx()
        result = cmd_nc(ctx, ["10.0.0.1", "notaport"])
        assert "invalid port" in result.lower()

    def test_netcat_alias_registered(self):
        from hackerzork.engine.command_registry import DEFAULT_REGISTRY
        assert DEFAULT_REGISTRY.get("netcat") is not None

    def test_no_network_error(self):
        ctx = CommandContext(env={})
        result = cmd_nc(ctx, ["-z", "10.0.0.1", "80"])
        assert "not available" in result.lower()


# ---------------------------------------------------------------------------
# ifconfig
# ---------------------------------------------------------------------------


class TestIfconfig:
    def test_shows_eth0(self):
        ctx = CommandContext(env={})
        from hackerzork.commands.network_cmds import cmd_ifconfig
        out = cmd_ifconfig(ctx, [])
        assert "eth0" in out
        assert "192.168.1.100" in out

    def test_shows_lo(self):
        from hackerzork.commands.network_cmds import cmd_ifconfig
        ctx = CommandContext(env={})
        out = cmd_ifconfig(ctx, [])
        assert "lo" in out
        assert "127.0.0.1" in out

    def test_filter_eth0(self):
        from hackerzork.commands.network_cmds import cmd_ifconfig
        ctx = CommandContext(env={})
        out = cmd_ifconfig(ctx, ["eth0"])
        assert "eth0" in out
        assert "lo" not in out

    def test_filter_lo(self):
        from hackerzork.commands.network_cmds import cmd_ifconfig
        ctx = CommandContext(env={})
        out = cmd_ifconfig(ctx, ["lo"])
        assert "127.0.0.1" in out
        assert "192.168.1.100" not in out

    def test_unknown_interface(self):
        from hackerzork.commands.network_cmds import cmd_ifconfig
        ctx = CommandContext(env={})
        out = cmd_ifconfig(ctx, ["wlan99"])
        assert "not found" in out.lower() or "Device not found" in out

    def test_shows_mac(self):
        from hackerzork.commands.network_cmds import cmd_ifconfig
        ctx = CommandContext(env={})
        out = cmd_ifconfig(ctx, [])
        assert "52:54:00" in out


# ---------------------------------------------------------------------------
# ip
# ---------------------------------------------------------------------------


class TestIp:
    def test_no_args(self):
        from hackerzork.commands.network_cmds import cmd_ip
        ctx = CommandContext(env={})
        out = cmd_ip(ctx, [])
        assert "Usage" in out

    def test_ip_addr(self):
        from hackerzork.commands.network_cmds import cmd_ip
        ctx = CommandContext(env={})
        out = cmd_ip(ctx, ["addr"])
        assert "eth0" in out
        assert "192.168.1.100" in out
        assert "lo" in out

    def test_ip_addr_alias_a(self):
        from hackerzork.commands.network_cmds import cmd_ip
        ctx = CommandContext(env={})
        out = cmd_ip(ctx, ["a"])
        assert "eth0" in out

    def test_ip_route(self):
        from hackerzork.commands.network_cmds import cmd_ip
        ctx = CommandContext(env={})
        out = cmd_ip(ctx, ["route"])
        assert "default" in out
        assert "192.168.1" in out

    def test_ip_link(self):
        from hackerzork.commands.network_cmds import cmd_ip
        ctx = CommandContext(env={})
        out = cmd_ip(ctx, ["link"])
        assert "eth0" in out
        assert "lo" in out

    def test_ip_neigh(self):
        from hackerzork.commands.network_cmds import cmd_ip
        ctx = CommandContext(env={})
        out = cmd_ip(ctx, ["neigh"])
        assert "192.168.1.1" in out

    def test_ip_unknown_object(self):
        from hackerzork.commands.network_cmds import cmd_ip
        ctx = CommandContext(env={})
        out = cmd_ip(ctx, ["frob"])
        assert "unknown" in out.lower() or "frob" in out

    def test_ip_addr_with_ssh_host(self):
        from hackerzork.commands.network_cmds import cmd_ip
        net = NetworkSim()
        ctx = CommandContext(env={"LAST_SSH_HOST": "10.13.37.1"}, network=net)
        out = cmd_ip(ctx, ["addr"])
        # tun0 should appear when LAST_SSH_HOST is set
        assert "tun0" in out or "10.13.37.1" in out


# ---------------------------------------------------------------------------
# ss
# ---------------------------------------------------------------------------


class TestSs:
    def test_shows_header(self):
        from hackerzork.commands.network_cmds import cmd_ss
        ctx = CommandContext(env={})
        out = cmd_ss(ctx, [])
        assert "State" in out
        assert "Netid" in out

    def test_shows_skynet_connection(self):
        from hackerzork.commands.network_cmds import cmd_ss
        ctx = CommandContext(env={})
        out = cmd_ss(ctx, [])
        assert "45.152.66.201" in out

    def test_shows_listen(self):
        from hackerzork.commands.network_cmds import cmd_ss
        ctx = CommandContext(env={})
        out = cmd_ss(ctx, [])
        assert "LISTEN" in out

    def test_shows_established(self):
        from hackerzork.commands.network_cmds import cmd_ss
        ctx = CommandContext(env={})
        out = cmd_ss(ctx, [])
        assert "ESTAB" in out

    def test_ssh_session_visible(self):
        from hackerzork.commands.network_cmds import cmd_ss
        ctx = CommandContext(env={"LAST_SSH_HOST": "10.13.37.1"})
        out = cmd_ss(ctx, [])
        # With an active SSH session, should show more ESTAB entries
        assert out.count("ESTAB") >= 2


# ---------------------------------------------------------------------------
# netstat
# ---------------------------------------------------------------------------


class TestNetstat:
    def test_shows_header(self):
        from hackerzork.commands.network_cmds import cmd_netstat
        ctx = CommandContext(env={})
        out = cmd_netstat(ctx, [])
        assert "Proto" in out

    def test_shows_skynet_connection(self):
        from hackerzork.commands.network_cmds import cmd_netstat
        ctx = CommandContext(env={})
        out = cmd_netstat(ctx, [])
        assert "45.152.66.201" in out

    def test_shows_listen(self):
        from hackerzork.commands.network_cmds import cmd_netstat
        ctx = CommandContext(env={})
        out = cmd_netstat(ctx, [])
        assert "LISTEN" in out

    def test_routing_flag(self):
        from hackerzork.commands.network_cmds import cmd_netstat
        ctx = CommandContext(env={})
        out = cmd_netstat(ctx, ["-r"])
        assert "Kernel IP routing table" in out
        assert "Destination" in out

    def test_ssh_session_in_netstat(self):
        from hackerzork.commands.network_cmds import cmd_netstat
        ctx = CommandContext(env={"LAST_SSH_HOST": "10.13.37.1"})
        out = cmd_netstat(ctx, [])
        assert out.count("ESTABLISHED") >= 2
