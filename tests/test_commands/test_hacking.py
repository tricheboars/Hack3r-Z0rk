"""Tests for hackerzork.commands.hacking."""
from __future__ import annotations

import pytest

import hackerzork.commands.hacking  # noqa: F401 — registers commands
from hackerzork.commands.hacking import (
    cmd_backdoor,
    cmd_bruteforce,
    cmd_exploit,
    cmd_loot,
    cmd_privesc,
)
from hackerzork.engine.command_registry import CommandContext
from hackerzork.systems.heat import HeatSystem
from hackerzork.systems.network import Firewall, Loot, NetworkNode, NetworkSim, Port
from hackerzork.systems.state import GameState
from hackerzork.systems.virtual_fs import VirtualFS

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FS_TEMPLATE = {
    "/home/user": {
        "_meta": {"permissions": "755", "owner": "user"},
        "notes/": {"_meta": {"permissions": "755", "owner": "user"}},
    },
    "/tmp": {},
}


def _make_port(number: int, service: str = "http", version: str = "1.0",
               vuln: str | None = None, state: str = "open") -> Port:
    return Port(number=number, service=service, version=version, vuln=vuln, state=state)


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
    compromised: bool = False,
) -> NetworkNode:
    node = NetworkNode(
        id=node_id,
        name="Test Node",
        ip=ip,
        hostname=hostname,
        ports=ports or [
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
    node.compromised = compromised
    return node


def _make_ctx(
    node: NetworkNode | None = None,
    extra_nodes: list[NetworkNode] | None = None,
    discovered: bool = True,
    compromised: bool = False,
    with_heat: bool = False,
    with_state: bool = False,
) -> CommandContext:
    fs = VirtualFS(template=_FS_TEMPLATE)
    net = NetworkSim()
    if node is not None:
        net.add_node(node)
        if discovered:
            net.discovered.add(node.ip)
        if compromised:
            net.compromise_node(node.ip)
    for n in extra_nodes or []:
        net.add_node(n)

    heat = HeatSystem() if with_heat else None
    state = GameState() if with_state else None

    env = {"CWD": "/home/user", "HOME": "/home/user", "USER": "user"}
    return CommandContext(fs=fs, network=net, env=env, heat=heat, state=state)


def _run(fn, ctx, args) -> str:
    return fn(ctx, args)


# ---------------------------------------------------------------------------
# exploit
# ---------------------------------------------------------------------------


class TestExploit:
    def test_missing_target(self):
        ctx = _make_ctx()
        out = _run(cmd_exploit, ctx, [])
        assert "missing target" in out.lower() or "Usage" in out

    def test_missing_port(self):
        ctx = _make_ctx(_make_node())
        out = _run(cmd_exploit, ctx, ["-e", "CVE-2021-23017", "10.0.0.1"])
        assert "-p PORT" in out

    def test_missing_exploit(self):
        ctx = _make_ctx(_make_node())
        out = _run(cmd_exploit, ctx, ["-p", "80", "10.0.0.1"])
        assert "-e EXPLOIT" in out

    def test_no_route(self):
        ctx = _make_ctx()
        out = _run(cmd_exploit, ctx, ["-p", "80", "-e", "CVE-2021-23017", "1.2.3.4"])
        assert "no route" in out.lower()

    def test_not_discovered(self):
        node = _make_node()
        ctx = _make_ctx(node, discovered=False)
        out = _run(cmd_exploit, ctx, ["-p", "80", "-e", "CVE-2021-23017", "10.0.0.1"])
        assert "not yet scanned" in out.lower() or "nmap" in out.lower()

    def test_exploit_success(self):
        node = _make_node()
        ctx = _make_ctx(node, with_state=True)
        out = _run(cmd_exploit, ctx, ["-p", "80", "-e", "CVE-2021-23017", "10.0.0.1"])
        assert "[+]" in out
        assert ctx.network.nodes["10.0.0.1"].compromised is True

    def test_exploit_wrong_exploit_fails(self):
        node = _make_node()
        ctx = _make_ctx(node)
        out = _run(cmd_exploit, ctx, ["-p", "80", "-e", "wrong_exploit", "10.0.0.1"])
        assert "[-]" in out
        assert ctx.network.nodes["10.0.0.1"].compromised is False

    def test_exploit_closed_port_fails(self):
        node = _make_node(ports=[_make_port(22, "ssh", state="closed")])
        ctx = _make_ctx(node)
        out = _run(cmd_exploit, ctx, ["-p", "22", "-e", "anything", "10.0.0.1"])
        assert "[-]" in out

    def test_exploit_loot_written_to_vfs(self):
        loot = [Loot(type="file", path="/etc/secret.txt", content="SEKRET\n",
                     description="test loot")]
        node = _make_node(loot=loot)
        ctx = _make_ctx(node)
        _run(cmd_exploit, ctx, ["-p", "80", "-e", "CVE-2021-23017", "10.0.0.1"])
        # Check loot dir created
        entries = ctx.fs.list_dir("/home/user/loot/10_0_0_1")
        assert len(entries) > 0

    def test_exploit_with_heat(self):
        node = _make_node()
        ctx = _make_ctx(node, with_heat=True)
        initial = ctx.heat.level
        _run(cmd_exploit, ctx, ["-p", "80", "-e", "CVE-2021-23017", "10.0.0.1"])
        assert ctx.heat.level > initial

    def test_stealth_flag_accepted(self):
        node = _make_node()
        ctx = _make_ctx(node, with_heat=True)
        out = _run(cmd_exploit, ctx, ["-s", "-p", "80", "-e", "CVE-2021-23017", "10.0.0.1"])
        assert "stealth=ON" in out or "[+]" in out

    def test_exploit_sets_story_flag(self):
        node = _make_node()
        node.story_flags = {"on_compromise": "test_flag"}
        ctx = _make_ctx(node, with_state=True)
        _run(cmd_exploit, ctx, ["-p", "80", "-e", "CVE-2021-23017", "10.0.0.1"])
        assert ctx.state.has_flag("test_flag")


# ---------------------------------------------------------------------------
# bruteforce
# ---------------------------------------------------------------------------


class TestBruteforce:
    def test_missing_target(self):
        ctx = _make_ctx()
        out = _run(cmd_bruteforce, ctx, [])
        assert "missing target" in out.lower()

    def test_missing_port(self):
        ctx = _make_ctx(_make_node())
        out = _run(cmd_bruteforce, ctx, ["10.0.0.1"])
        assert "-p PORT" in out

    def test_no_route(self):
        ctx = _make_ctx()
        out = _run(cmd_bruteforce, ctx, ["-p", "22", "9.9.9.9"])
        assert "no route" in out.lower()

    def test_not_discovered(self):
        node = _make_node()
        ctx = _make_ctx(node, discovered=False)
        out = _run(cmd_bruteforce, ctx, ["-p", "22", "10.0.0.1"])
        assert "nmap" in out.lower() or "not yet scanned" in out.lower()

    def test_invalid_port(self):
        ctx = _make_ctx(_make_node())
        out = _run(cmd_bruteforce, ctx, ["-p", "notaport", "10.0.0.1"])
        assert "invalid port" in out.lower()

    def test_success_when_creds_match(self):
        loot = [Loot(type="credential", username="admin", password="admin",
                     service="ssh", description="")]
        node = _make_node(ports=[_make_port(22, "ssh")], loot=loot)
        ctx = _make_ctx(node)
        out = _run(cmd_bruteforce, ctx, ["-p", "22", "10.0.0.1"])
        assert "[+]" in out
        assert "admin" in out

    def test_failure_when_no_matching_creds(self):
        node = _make_node(ports=[_make_port(22, "ssh")])
        ctx = _make_ctx(node)
        out = _run(cmd_bruteforce, ctx, ["-p", "22", "10.0.0.1"])
        assert "[-]" in out

    def test_custom_wordlist(self, tmp_path):
        loot = [Loot(type="credential", username="secretuser", password="secretpass",
                     service="ftp", description="")]
        node = _make_node(ports=[_make_port(21, "ftp")], loot=loot)
        ctx = _make_ctx(node)
        ctx.fs.write_file("/home/user/words.txt", "secretuser:secretpass\nadmin:admin\n")
        out = _run(cmd_bruteforce, ctx, ["-p", "21", "-w", "/home/user/words.txt", "10.0.0.1"])
        assert "[+]" in out

    def test_generates_heat(self):
        node = _make_node(ports=[_make_port(22, "ssh")])
        ctx = _make_ctx(node, with_heat=True)
        _run(cmd_bruteforce, ctx, ["-p", "22", "10.0.0.1"])
        assert ctx.heat.level > 0


# ---------------------------------------------------------------------------
# loot
# ---------------------------------------------------------------------------


class TestLoot:
    def test_no_loot_yet(self):
        ctx = _make_ctx()
        out = _run(cmd_loot, ctx, [])
        assert "no loot" in out.lower()

    def test_shows_loot_after_exfil(self):
        node = _make_node()
        ctx = _make_ctx(node)
        # Simulate loot already in VFS
        ctx.fs.make_dir("/home/user/loot/10_0_0_1", parents=True)
        ctx.fs.write_file("/home/user/loot/10_0_0_1/creds_mysql.txt", "mysql://dbadmin:hunter2\n")
        out = _run(cmd_loot, ctx, [])
        assert "10.0.0.1" in out
        assert "creds_mysql" in out

    def test_filter_by_ip(self):
        ctx = _make_ctx()
        ctx.fs.make_dir("/home/user/loot/10_0_0_1", parents=True)
        ctx.fs.write_file("/home/user/loot/10_0_0_1/file.txt", "data\n")
        ctx.fs.make_dir("/home/user/loot/10_0_0_2", parents=True)
        ctx.fs.write_file("/home/user/loot/10_0_0_2/other.txt", "other\n")
        out = _run(cmd_loot, ctx, ["10.0.0.1"])
        # Output shows IP in brackets form
        assert "10.0.0.1" in out
        assert "other.txt" not in out


# ---------------------------------------------------------------------------
# backdoor
# ---------------------------------------------------------------------------


class TestBackdoor:
    def test_not_compromised(self):
        node = _make_node()
        ctx = _make_ctx(node)
        out = _run(cmd_backdoor, ctx, ["10.0.0.1"])
        assert "not compromised" in out.lower()

    def test_missing_target(self):
        ctx = _make_ctx()
        out = _run(cmd_backdoor, ctx, [])
        assert "missing target" in out.lower()

    def test_installs_when_compromised(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True)
        out = _run(cmd_backdoor, ctx, ["10.0.0.1"])
        assert "[+]" in out
        assert "4444" in out

    def test_custom_port(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True)
        out = _run(cmd_backdoor, ctx, ["-p", "1337", "10.0.0.1"])
        assert "1337" in out

    def test_backdoor_recorded_in_vfs(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True)
        _run(cmd_backdoor, ctx, ["10.0.0.1"])
        entries = ctx.fs.list_dir("/home/user/loot/10_0_0_1")
        assert any("backdoor" in e.name for e in entries)

    def test_generates_heat(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True, with_heat=True)
        _run(cmd_backdoor, ctx, ["10.0.0.1"])
        assert ctx.heat.level > 0


# ---------------------------------------------------------------------------
# privesc
# ---------------------------------------------------------------------------


class TestPrivesc:
    def test_not_compromised(self):
        node = _make_node()
        ctx = _make_ctx(node)
        out = _run(cmd_privesc, ctx, ["10.0.0.1"])
        assert "not yet compromised" in out.lower()

    def test_missing_target(self):
        ctx = _make_ctx()
        out = _run(cmd_privesc, ctx, [])
        assert "missing target" in out.lower()

    def test_check_only(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True)
        out = _run(cmd_privesc, ctx, ["--check", "10.0.0.1"])
        assert "check only" in out.lower() or "--check" in out.lower()
        # Should NOT say root obtained
        assert "root shell" not in out.lower()

    def test_success_on_compromised(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True, with_state=True)
        out = _run(cmd_privesc, ctx, ["10.0.0.1"])
        assert "[+]" in out
        assert "root" in out.lower()

    def test_generates_heat(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True, with_heat=True)
        _run(cmd_privesc, ctx, ["10.0.0.1"])
        assert ctx.heat.level > 0

    def test_vectors_listed(self):
        node = _make_node()
        ctx = _make_ctx(node, compromised=True)
        out = _run(cmd_privesc, ctx, ["--check", "10.0.0.1"])
        # At least one vector should be shown
        assert "[!]" in out
