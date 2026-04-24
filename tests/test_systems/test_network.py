"""Tests for hackerzork.systems.network."""
from __future__ import annotations

import pathlib

import pytest

from hackerzork.systems.network import (
    ExploitResult,
    Firewall,
    Loot,
    NetworkNode,
    NetworkSim,
    Port,
    PortResult,
    ServiceResult,
    _node_from_dict,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _make_port(number: int, service: str = "http", vuln: str | None = None, state: str = "open") -> Port:
    return Port(number=number, service=service, version="1.0", vuln=vuln, state=state)


def _make_loot() -> list[Loot]:
    return [
        Loot(type="credential", username="admin", password="s3cr3t", service="ssh"),
        Loot(type="file", path="/etc/shadow", content="root:hashed"),
    ]


def _make_node(
    node_id: str = "node_001",
    ip: str = "10.0.0.1",
    *,
    firewall: Firewall | None = None,
    ports: list[Port] | None = None,
    difficulty: int = 1,
    connections: list[str] | None = None,
    loot: list[Loot] | None = None,
) -> NetworkNode:
    return NetworkNode(
        id=node_id,
        name="Test Node",
        ip=ip,
        hostname=f"{node_id}.test",
        ports=ports or [_make_port(22, "ssh", "CVE-2021-1234"), _make_port(80, "http")],
        firewall=firewall or Firewall(enabled=False),
        difficulty=difficulty,
        heat_modifier=1.0,
        loot=loot or _make_loot(),
        connections=connections or [],
    )


def _make_sim(*nodes: NetworkNode) -> NetworkSim:
    sim = NetworkSim()
    for node in nodes:
        sim.add_node(node)
    return sim


# ---------------------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------------------


class TestFirewall:
    def test_disabled_allows_all(self):
        fw = Firewall(enabled=False)
        assert fw.allows_port(22)
        assert fw.allows_port(9999)

    def test_block_all_except_allows_listed(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [80, 443]"])
        assert fw.allows_port(80)
        assert fw.allows_port(443)

    def test_block_all_except_blocks_unlisted(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [80, 443]"])
        assert not fw.allows_port(22)
        assert not fw.allows_port(3306)

    def test_block_specific_port(self):
        fw = Firewall(enabled=True, rules=["block_port: 22"])
        assert not fw.allows_port(22)
        assert fw.allows_port(80)

    def test_add_rule_recomputes(self):
        fw = Firewall(enabled=True)
        fw.add_rule("block_port: 3306")
        assert not fw.allows_port(3306)
        assert fw.allows_port(22)


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


class TestNodeFromDict:
    _DATA = {
        "id": "n1",
        "name": "Alpha",
        "ip": "1.2.3.4",
        "hostname": "alpha.local",
        "ports": [
            {"port": 22, "service": "ssh", "version": "OpenSSH 8.9", "vuln": None},
            {"port": 80, "service": "http", "version": "nginx 1.18", "vuln": "CVE-2021-23017"},
        ],
        "firewall": {"enabled": True, "rules": ["block_all_inbound_except: [80]"]},
        "difficulty": 2,
        "heat_modifier": 0.8,
        "loot": [{"type": "credential", "username": "admin", "password": "pass"}],
        "connections": ["n2"],
        "story_flags": {"on_compromise": "alpha_done"},
    }

    def test_fields_populated(self):
        node = _node_from_dict(self._DATA)
        assert node.id == "n1"
        assert node.ip == "1.2.3.4"
        assert node.difficulty == 2
        assert node.heat_modifier == 0.8

    def test_ports_parsed(self):
        node = _node_from_dict(self._DATA)
        assert len(node.ports) == 2
        assert node.ports[0].number == 22
        assert node.ports[1].vuln == "CVE-2021-23017"

    def test_firewall_parsed(self):
        node = _node_from_dict(self._DATA)
        assert node.firewall.enabled is True
        assert node.firewall.allows_port(80)
        assert not node.firewall.allows_port(22)

    def test_loot_parsed(self):
        node = _node_from_dict(self._DATA)
        assert len(node.loot) == 1
        assert node.loot[0].username == "admin"

    def test_connections(self):
        node = _node_from_dict(self._DATA)
        assert node.connections == ["n2"]

    def test_story_flags(self):
        node = _node_from_dict(self._DATA)
        assert node.story_flags["on_compromise"] == "alpha_done"


class TestLoadNodesFromYaml:
    def test_load_real_node_001(self):
        nodes_dir = pathlib.Path(__file__).parent.parent.parent / "hackerzork" / "data" / "nodes"
        sim = NetworkSim()
        sim.load_nodes(str(nodes_dir))
        assert "10.13.37.1" in sim.nodes

    def test_node_001_ports(self):
        nodes_dir = pathlib.Path(__file__).parent.parent.parent / "hackerzork" / "data" / "nodes"
        sim = NetworkSim()
        sim.load_nodes(str(nodes_dir))
        node = sim.nodes["10.13.37.1"]
        port_numbers = [p.number for p in node.ports]
        assert 22 in port_numbers
        assert 80 in port_numbers

    def test_node_001_firewall(self):
        nodes_dir = pathlib.Path(__file__).parent.parent.parent / "hackerzork" / "data" / "nodes"
        sim = NetworkSim()
        sim.load_nodes(str(nodes_dir))
        node = sim.nodes["10.13.37.1"]
        # SSH (22) is blocked; HTTP (80) is allowed
        assert not node.firewall.allows_port(22)
        assert node.firewall.allows_port(80)

    def test_nonexistent_dir_is_silent(self):
        sim = NetworkSim()
        sim.load_nodes("/nonexistent/path/xyz")
        assert sim.nodes == {}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_discover_known_ip(self):
        node = _make_node()
        sim = _make_sim(node)
        result = sim.discover_node("10.0.0.1")
        assert result is node
        assert "10.0.0.1" in sim.discovered

    def test_discover_unknown_ip(self):
        sim = _make_sim()
        result = sim.discover_node("99.99.99.99")
        assert result is None
        assert "99.99.99.99" not in sim.discovered

    def test_discover_does_not_compromise(self):
        node = _make_node()
        sim = _make_sim(node)
        sim.discover_node("10.0.0.1")
        assert "10.0.0.1" not in sim.compromised


# ---------------------------------------------------------------------------
# Port scanning
# ---------------------------------------------------------------------------


class TestScanPorts:
    def test_open_port_returned(self):
        node = _make_node(ports=[_make_port(22, "ssh")])
        sim = _make_sim(node)
        results = sim.scan_ports("10.0.0.1")
        assert any(r.port == 22 and r.state == "open" for r in results)

    def test_filtered_by_firewall(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [80]"])
        node = _make_node(ports=[_make_port(22, "ssh"), _make_port(80, "http")], firewall=fw)
        sim = _make_sim(node)
        results = sim.scan_ports("10.0.0.1")
        states = {r.port: r.state for r in results}
        assert states[22] == "filtered"
        assert states[80] == "open"

    def test_specific_ports_requested(self):
        node = _make_node(ports=[_make_port(22), _make_port(80), _make_port(443)])
        sim = _make_sim(node)
        results = sim.scan_ports("10.0.0.1", ports=[22, 443])
        port_nums = [r.port for r in results]
        assert 22 in port_nums
        assert 443 in port_nums
        assert 80 not in port_nums

    def test_closed_port_if_not_on_node(self):
        node = _make_node(ports=[_make_port(22)])
        sim = _make_sim(node)
        results = sim.scan_ports("10.0.0.1", ports=[9999])
        assert results[0].state == "closed"

    def test_unknown_ip_returns_empty(self):
        sim = _make_sim()
        results = sim.scan_ports("9.9.9.9")
        assert results == []


# ---------------------------------------------------------------------------
# Service scanning
# ---------------------------------------------------------------------------


class TestScanServices:
    def test_returns_version_info(self):
        node = _make_node(ports=[Port(22, "ssh", "OpenSSH 8.9", None)])
        sim = _make_sim(node)
        results = sim.scan_services("10.0.0.1")
        assert any(r.service == "ssh" and r.version == "OpenSSH 8.9" for r in results)

    def test_firewall_filtered_ports_excluded(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [80]"])
        node = _make_node(
            ports=[_make_port(22, "ssh"), _make_port(80, "http")],
            firewall=fw,
        )
        sim = _make_sim(node)
        results = sim.scan_services("10.0.0.1")
        services = [r.service for r in results]
        assert "ssh" not in services
        assert "http" in services

    def test_vuln_exposed(self):
        node = _make_node(ports=[_make_port(80, "http", vuln="CVE-2021-23017")])
        sim = _make_sim(node)
        results = sim.scan_services("10.0.0.1")
        assert any(r.vuln == "CVE-2021-23017" for r in results)


# ---------------------------------------------------------------------------
# Ping
# ---------------------------------------------------------------------------


class TestPing:
    def test_known_host_alive(self):
        node = _make_node()
        sim = _make_sim(node)
        result = sim.ping("10.0.0.1")
        assert result.alive is True
        assert result.latency_ms > 0
        assert result.ttl > 0

    def test_unknown_host_not_alive(self):
        sim = _make_sim()
        result = sim.ping("9.9.9.9")
        assert result.alive is False
        assert result.latency_ms == 0.0

    def test_latency_is_deterministic(self):
        node = _make_node()
        sim = _make_sim(node)
        r1 = sim.ping("10.0.0.1")
        r2 = sim.ping("10.0.0.1")
        assert r1.latency_ms == r2.latency_ms


# ---------------------------------------------------------------------------
# Firewall check
# ---------------------------------------------------------------------------


class TestCheckFirewall:
    def test_open_node_allows_all(self):
        node = _make_node(firewall=Firewall(enabled=False))
        sim = _make_sim(node)
        assert sim.check_firewall("10.0.0.1", 22) is True
        assert sim.check_firewall("10.0.0.1", 9999) is True

    def test_filtered_port_denied(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [80]"])
        node = _make_node(firewall=fw)
        sim = _make_sim(node)
        assert sim.check_firewall("10.0.0.1", 22) is False
        assert sim.check_firewall("10.0.0.1", 80) is True

    def test_unknown_ip_denied(self):
        sim = _make_sim()
        assert sim.check_firewall("9.9.9.9", 80) is False


# ---------------------------------------------------------------------------
# Exploit attempts
# ---------------------------------------------------------------------------


class TestExploit:
    def test_matching_vuln_succeeds(self):
        node = _make_node(ports=[_make_port(80, "http", vuln="CVE-2021-23017")])
        sim = _make_sim(node)
        result = sim.attempt_exploit("10.0.0.1", 80, "CVE-2021-23017")
        assert result.success is True
        assert result.loot is not None

    def test_exploit_partial_match(self):
        node = _make_node(ports=[_make_port(80, "http", vuln="default_credentials")])
        sim = _make_sim(node)
        result = sim.attempt_exploit("10.0.0.1", 80, "default_credentials")
        assert result.success is True

    def test_wrong_exploit_fails(self):
        node = _make_node(ports=[_make_port(80, "http", vuln="CVE-2021-23017")])
        sim = _make_sim(node)
        result = sim.attempt_exploit("10.0.0.1", 80, "wrong_exploit")
        assert result.success is False

    def test_no_vuln_fails(self):
        node = _make_node(ports=[_make_port(80, "http", vuln=None)])
        sim = _make_sim(node)
        result = sim.attempt_exploit("10.0.0.1", 80, "CVE-anything")
        assert result.success is False

    def test_firewall_blocked_fails(self):
        fw = Firewall(enabled=True, rules=["block_all_inbound_except: [443]"])
        node = _make_node(
            ports=[_make_port(80, "http", vuln="CVE-2021-23017")],
            firewall=fw,
        )
        sim = _make_sim(node)
        result = sim.attempt_exploit("10.0.0.1", 80, "CVE-2021-23017")
        assert result.success is False
        assert "filtered" in result.message.lower()

    def test_closed_port_fails(self):
        node = _make_node(ports=[_make_port(80)])  # no vuln
        sim = _make_sim(node)
        result = sim.attempt_exploit("10.0.0.1", 9999, "any")
        assert result.success is False

    def test_unknown_ip_fails(self):
        sim = _make_sim()
        result = sim.attempt_exploit("9.9.9.9", 80, "anything")
        assert result.success is False

    def test_success_marks_compromised(self):
        node = _make_node(ports=[_make_port(80, "http", vuln="CVE-2021-23017")])
        sim = _make_sim(node)
        sim.attempt_exploit("10.0.0.1", 80, "CVE-2021-23017")
        assert "10.0.0.1" in sim.compromised

    def test_heat_cost_positive(self):
        node = _make_node(ports=[_make_port(80, "http", vuln="CVE-2021-23017")])
        sim = _make_sim(node)
        result = sim.attempt_exploit("10.0.0.1", 80, "CVE-2021-23017")
        assert result.heat_cost > 0


# ---------------------------------------------------------------------------
# Hardening
# ---------------------------------------------------------------------------


class TestHardening:
    def test_hardening_increments_counter(self):
        node = _make_node()
        sim = _make_sim(node)
        sim.harden_node("10.0.0.1")
        assert node.hardened == 1

    def test_hardening_patches_first_vuln(self):
        node = _make_node(ports=[_make_port(22, "ssh", "CVE-1234"), _make_port(80)])
        sim = _make_sim(node)
        sim.harden_node("10.0.0.1")
        assert node.get_port(22).vuln is None

    def test_failed_exploit_triggers_hardening(self):
        node = _make_node(ports=[_make_port(80, "http", vuln="CVE-x")])
        sim = _make_sim(node)
        sim.attempt_exploit("10.0.0.1", 80, "wrong_exploit")
        assert node.hardened == 1

    def test_repeated_hardening_closes_ports(self):
        node = _make_node(
            ports=[_make_port(22, "ssh", "CVE-1"), _make_port(80, "http", "CVE-2")],
            firewall=Firewall(enabled=True),
        )
        sim = _make_sim(node)
        # Harden twice to trigger port-blocking rule
        sim.harden_node("10.0.0.1")
        sim.harden_node("10.0.0.1")
        # At least one port should now be blocked
        assert not node.firewall.allows_port(22)

    def test_heavily_hardened_node_blocks_exploit(self):
        node = _make_node(
            ports=[_make_port(80, "http", vuln="CVE-2021-23017")],
            difficulty=1,
        )
        sim = _make_sim(node)
        # Force hardened past the gate threshold (difficulty + 2 = 3)
        node.hardened = 4
        result = sim.attempt_exploit("10.0.0.1", 80, "CVE-2021-23017")
        assert result.success is False


# ---------------------------------------------------------------------------
# Compromise & connections
# ---------------------------------------------------------------------------


class TestCompromise:
    def test_compromise_marks_flag(self):
        node = _make_node()
        sim = _make_sim(node)
        sim.compromise_node("10.0.0.1")
        assert node.compromised is True
        assert "10.0.0.1" in sim.compromised

    def test_compromise_reveals_connections(self):
        node_a = _make_node("node_a", "10.0.0.1", connections=["node_b"])
        node_b = _make_node("node_b", "10.0.0.2")
        sim = _make_sim(node_a, node_b)
        sim.compromise_node("10.0.0.1")
        assert "10.0.0.2" in sim.discovered

    def test_get_connections_before_compromise_empty(self):
        node_a = _make_node("node_a", "10.0.0.1", connections=["node_b"])
        node_b = _make_node("node_b", "10.0.0.2")
        sim = _make_sim(node_a, node_b)
        assert sim.get_connections("10.0.0.1") == []

    def test_get_connections_after_compromise(self):
        node_a = _make_node("node_a", "10.0.0.1", connections=["node_b"])
        node_b = _make_node("node_b", "10.0.0.2")
        sim = _make_sim(node_a, node_b)
        sim.compromise_node("10.0.0.1")
        conns = sim.get_connections("10.0.0.1")
        assert "10.0.0.2" in conns

    def test_connections_unknown_node_id_skipped(self):
        node = _make_node("node_a", "10.0.0.1", connections=["ghost_node"])
        sim = _make_sim(node)
        sim.compromise_node("10.0.0.1")
        conns = sim.get_connections("10.0.0.1")
        assert conns == []


# ---------------------------------------------------------------------------
# Traceroute
# ---------------------------------------------------------------------------


class TestTraceroute:
    def test_traceroute_includes_target(self):
        node = _make_node()
        sim = _make_sim(node)
        hops = sim.traceroute("10.0.0.1")
        assert "10.0.0.1" in hops

    def test_traceroute_starts_at_gateway(self):
        node = _make_node()
        sim = _make_sim(node)
        hops = sim.traceroute("10.0.0.1")
        assert hops[0] == "10.0.0.1"  # gateway is first
        # actually gateway constant is 10.0.0.1 — verify it's first
        assert len(hops) >= 2

    def test_traceroute_unknown_ip_uses_star(self):
        sim = _make_sim()
        hops = sim.traceroute("9.9.9.9")
        assert "*" in hops


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_roundtrip_preserves_state(self):
        node = _make_node(ports=[_make_port(80, "http", vuln="CVE-x")])
        sim = _make_sim(node)
        sim.discover_node("10.0.0.1")
        sim.harden_node("10.0.0.1")
        state = sim.to_dict()

        # Build a fresh sim with the same topology
        sim2 = NetworkSim()
        node2 = _make_node(ports=[_make_port(80, "http", vuln="CVE-x")])
        sim2.add_node(node2)
        sim2.load_state(state)

        assert "10.0.0.1" in sim2.discovered
        assert sim2.nodes["10.0.0.1"].hardened == 1
