"""Network simulation — the hackable internet."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Port:
    number: int
    service: str
    version: str
    vuln: str | None
    state: str = "open"  # open | closed | filtered


@dataclass
class Firewall:
    enabled: bool
    rules: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._block_all_except: bool = False
        self._allowed_ports: set[int] = set()
        self._blocked_ports: set[int] = set()
        self._parse_rules()

    def _parse_rules(self) -> None:
        self._block_all_except = False
        self._allowed_ports = set()
        self._blocked_ports = set()
        for rule in self.rules:
            r = rule.strip()
            if r.startswith("block_all_inbound_except"):
                self._block_all_except = True
                start = r.find("[")
                end = r.find("]")
                if start != -1 and end != -1:
                    for tok in r[start + 1 : end].split(","):
                        tok = tok.strip()
                        if tok.isdigit():
                            self._allowed_ports.add(int(tok))
            elif r.startswith("block_port:"):
                tok = r.split(":", 1)[1].strip()
                if tok.isdigit():
                    self._blocked_ports.add(int(tok))

    def allows_port(self, port: int) -> bool:
        if not self.enabled:
            return True
        if port in self._blocked_ports:
            return False
        if self._block_all_except:
            return port in self._allowed_ports
        return True

    def add_rule(self, rule: str) -> None:
        self.rules.append(rule)
        self._parse_rules()


@dataclass
class Loot:
    type: str  # "file" | "credential" | "key"
    path: str = ""
    content: str = ""
    username: str = ""
    password: str = ""
    service: str = ""
    description: str = ""


@dataclass
class NetworkNode:
    id: str
    name: str
    ip: str
    hostname: str
    ports: list[Port]
    firewall: Firewall
    difficulty: int
    heat_modifier: float
    loot: list[Loot]
    connections: list[str]  # node IDs (not IPs)
    story_flags: dict[str, Any] = field(default_factory=dict)
    compromised: bool = False
    hardened: int = 0

    def get_port(self, number: int) -> Port | None:
        return next((p for p in self.ports if p.number == number), None)


# ---------------------------------------------------------------------------
# Scan/result types
# ---------------------------------------------------------------------------


@dataclass
class PortResult:
    port: int
    state: str  # "open" | "closed" | "filtered"
    service: str = ""


@dataclass
class ServiceResult:
    port: int
    service: str
    version: str
    vuln: str | None = None


@dataclass
class PingResult:
    ip: str
    alive: bool
    latency_ms: float
    ttl: int


@dataclass
class ExploitResult:
    success: bool
    message: str
    loot: list[Loot] | None = None
    heat_cost: float = 0.0


# ---------------------------------------------------------------------------
# YAML loading helpers
# ---------------------------------------------------------------------------


def _port_from_dict(d: dict) -> Port:
    return Port(
        number=int(d["port"]),
        service=str(d.get("service", "")),
        version=str(d.get("version", "")),
        vuln=d.get("vuln") or None,
        state=str(d.get("state", "open")),
    )


def _firewall_from_dict(d: dict | None) -> Firewall:
    if not d:
        return Firewall(enabled=False)
    return Firewall(
        enabled=bool(d.get("enabled", False)),
        rules=list(d.get("rules", [])),
    )


def _loot_from_dict(d: dict) -> Loot:
    return Loot(
        type=str(d.get("type", "file")),
        path=str(d.get("path", "")),
        content=str(d.get("content", "")),
        username=str(d.get("username", "")),
        password=str(d.get("password", "")),
        service=str(d.get("service", "")),
        description=str(d.get("description", "")),
    )


def _node_from_dict(d: dict) -> NetworkNode:
    return NetworkNode(
        id=str(d["id"]),
        name=str(d.get("name", d["id"])),
        ip=str(d["ip"]),
        hostname=str(d.get("hostname", "")),
        ports=[_port_from_dict(p) for p in d.get("ports", [])],
        firewall=_firewall_from_dict(d.get("firewall")),
        difficulty=int(d.get("difficulty", 1)),
        heat_modifier=float(d.get("heat_modifier", 1.0)),
        loot=[_loot_from_dict(lt) for lt in d.get("loot", [])],
        connections=list(d.get("connections", [])),
        story_flags=dict(d.get("story_flags", {})),
    )


# ---------------------------------------------------------------------------
# NetworkSim
# ---------------------------------------------------------------------------

_BASE_HEAT = {
    "ping": 0.1,
    "scan": 2.0,
    "service_scan": 4.0,
    "exploit": 10.0,
    "exploit_fail": 5.0,
}

# Synthetic gateway/relay IPs shown in traceroute paths
_GATEWAY = "10.0.0.1"
_ISP_HOP = "72.14.192.1"


class NetworkSim:
    def __init__(self) -> None:
        self.nodes: dict[str, NetworkNode] = {}       # keyed by IP
        self._nodes_by_id: dict[str, NetworkNode] = {}  # keyed by node ID
        self.discovered: set[str] = set()             # IPs known to the player
        self.compromised: set[str] = set()            # IPs the player has rooted

    # -------------------------------------------------------------------------
    # Node management
    # -------------------------------------------------------------------------

    def load_nodes(self, path: str) -> None:
        """Load all .yaml node files from a directory."""
        dir_path = pathlib.Path(path)
        if not dir_path.is_dir():
            return
        for yaml_file in sorted(dir_path.glob("*.yaml")):
            with open(yaml_file) as fh:
                data = yaml.safe_load(fh)
            if not data:
                continue
            node = _node_from_dict(data)
            self.nodes[node.ip] = node
            self._nodes_by_id[node.id] = node

    def add_node(self, node: NetworkNode) -> None:
        """Register a node directly (useful for tests)."""
        self.nodes[node.ip] = node
        self._nodes_by_id[node.id] = node

    def discover_node(self, ip: str) -> NetworkNode | None:
        """Mark a node as discovered. Returns node if it exists."""
        node = self.nodes.get(ip)
        if node:
            self.discovered.add(ip)
        return node

    # -------------------------------------------------------------------------
    # Scanning
    # -------------------------------------------------------------------------

    def ping(self, ip: str) -> PingResult:
        """Check if host is up."""
        node = self.nodes.get(ip)
        if node is None:
            return PingResult(ip=ip, alive=False, latency_ms=0.0, ttl=0)
        # Deterministic latency from IP hash so tests are stable
        latency = 10.0 + (hash(ip) % 900) / 10.0
        return PingResult(ip=ip, alive=True, latency_ms=round(latency, 1), ttl=64)

    def scan_ports(
        self, ip: str, ports: list[int] | None = None
    ) -> list[PortResult]:
        """Simulate port scan. Returns open/filtered/closed results."""
        node = self.nodes.get(ip)
        if node is None:
            return []

        targets = ports if ports else [p.number for p in node.ports]

        results: list[PortResult] = []
        for number in targets:
            port_obj = node.get_port(number)
            if port_obj is None:
                results.append(PortResult(port=number, state="closed"))
                continue
            if not node.firewall.allows_port(number):
                results.append(PortResult(port=number, state="filtered"))
            else:
                results.append(
                    PortResult(port=number, state=port_obj.state, service=port_obj.service)
                )
        return results

    def scan_services(self, ip: str) -> list[ServiceResult]:
        """Version-detection scan — returns richer info than port scan."""
        node = self.nodes.get(ip)
        if node is None:
            return []

        results: list[ServiceResult] = []
        for port in node.ports:
            if not node.firewall.allows_port(port.number):
                continue
            results.append(
                ServiceResult(
                    port=port.number,
                    service=port.service,
                    version=port.version,
                    vuln=port.vuln,
                )
            )
        return results

    def traceroute(self, ip: str) -> list[str]:
        """Return a list of IP hops from local machine to target."""
        node = self.nodes.get(ip)
        hops: list[str] = [_GATEWAY, _ISP_HOP]

        # Insert up to one intermediate known node for realism
        intermediate_ips = [
            n.ip
            for n in self.nodes.values()
            if n.ip != ip and n.ip in self.discovered
        ]
        if intermediate_ips:
            # Pick deterministically from the hash of the target IP
            pick = intermediate_ips[hash(ip) % len(intermediate_ips)]
            hops.append(pick)

        hops.append(ip if node else "*")
        return hops

    # -------------------------------------------------------------------------
    # Firewall
    # -------------------------------------------------------------------------

    def check_firewall(self, ip: str, port: int) -> bool:
        """Returns True if the port is accessible through the firewall."""
        node = self.nodes.get(ip)
        if node is None:
            return False
        return node.firewall.allows_port(port)

    # -------------------------------------------------------------------------
    # Exploitation
    # -------------------------------------------------------------------------

    def attempt_exploit(self, ip: str, port: int, exploit: str) -> ExploitResult:
        """Try to exploit a vulnerability. Hardens node on failure."""
        node = self.nodes.get(ip)
        if node is None:
            return ExploitResult(
                success=False,
                message=f"No route to host: {ip}",
                heat_cost=1.0,
            )

        heat = _BASE_HEAT["exploit"] * node.heat_modifier

        # Firewall check
        if not node.firewall.allows_port(port):
            return ExploitResult(
                success=False,
                message=f"Port {port} is filtered",
                heat_cost=heat * 0.5,
            )

        port_obj = node.get_port(port)
        if port_obj is None or port_obj.state != "open":
            return ExploitResult(
                success=False,
                message=f"Port {port} is not open",
                heat_cost=heat * 0.5,
            )

        # Vulnerability match — exploit name must appear in vuln string
        if port_obj.vuln is None or exploit.lower() not in port_obj.vuln.lower():
            self.harden_node(ip)
            return ExploitResult(
                success=False,
                message=f"Exploit '{exploit}' failed against {port_obj.service} on port {port}",
                heat_cost=_BASE_HEAT["exploit_fail"] * node.heat_modifier,
            )

        # Difficulty / hardening gate — too many hardenings close off cheap exploits
        if node.hardened >= node.difficulty + 2:
            self.harden_node(ip)
            return ExploitResult(
                success=False,
                message=f"Intrusion detected — {node.hostname} has patched the vulnerability",
                heat_cost=heat,
            )

        # Success
        self.compromise_node(ip)
        return ExploitResult(
            success=True,
            message=f"Exploited {port_obj.service} on {node.hostname} — root shell obtained",
            loot=list(node.loot),
            heat_cost=heat,
        )

    # -------------------------------------------------------------------------
    # Post-exploit
    # -------------------------------------------------------------------------

    def compromise_node(self, ip: str) -> None:
        """Mark node as compromised; discover its connections."""
        node = self.nodes.get(ip)
        if node is None:
            return
        node.compromised = True
        self.compromised.add(ip)
        self.discovered.add(ip)
        # Reveal connected nodes
        for conn_id in node.connections:
            neighbour = self._nodes_by_id.get(conn_id)
            if neighbour:
                self.discovered.add(neighbour.ip)

    def harden_node(self, ip: str) -> None:
        """Called when an exploit attempt fails — node gets harder."""
        node = self.nodes.get(ip)
        if node is None:
            return
        node.hardened += 1
        node.difficulty = max(node.difficulty, node.hardened)

        # Patch the most recently exploited (most specific) vulnerability
        for port in node.ports:
            if port.vuln is not None:
                port.vuln = None
                break

        # Add a firewall rule on the first unprotected port
        open_ports = [
            p.number for p in node.ports if node.firewall.allows_port(p.number)
        ]
        if open_ports and node.hardened > 1:
            node.firewall.add_rule(f"block_port: {open_ports[0]}")

    def get_connections(self, ip: str) -> list[str]:
        """Return IPs of nodes connected to this one.

        Only reveals IPs the player has already discovered (post-compromise).
        """
        node = self.nodes.get(ip)
        if node is None or ip not in self.compromised:
            return []
        result: list[str] = []
        for conn_id in node.connections:
            neighbour = self._nodes_by_id.get(conn_id)
            if neighbour:
                result.append(neighbour.ip)
        return result

    # -------------------------------------------------------------------------
    # Serialization helpers
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "discovered": sorted(self.discovered),
            "compromised": sorted(self.compromised),
            "nodes": {
                ip: {
                    "compromised": node.compromised,
                    "hardened": node.hardened,
                    "ports": [
                        {"number": p.number, "vuln": p.vuln, "state": p.state}
                        for p in node.ports
                    ],
                    "firewall_rules": list(node.firewall.rules),
                    "difficulty": node.difficulty,
                }
                for ip, node in self.nodes.items()
            },
        }

    def load_state(self, state: dict) -> None:
        """Restore mutable runtime state (not the static topology)."""
        self.discovered = set(state.get("discovered", []))
        self.compromised = set(state.get("compromised", []))
        for ip, nstate in state.get("nodes", {}).items():
            node = self.nodes.get(ip)
            if node is None:
                continue
            node.compromised = nstate.get("compromised", False)
            node.hardened = nstate.get("hardened", 0)
            node.difficulty = nstate.get("difficulty", node.difficulty)
            node.firewall.rules = nstate.get("firewall_rules", node.firewall.rules)
            node.firewall._parse_rules()
            port_states = {p["number"]: p for p in nstate.get("ports", [])}
            for port in node.ports:
                if port.number in port_states:
                    port.vuln = port_states[port.number].get("vuln")
                    port.state = port_states[port.number].get("state", port.state)
