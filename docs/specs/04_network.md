# Spec: Network Simulation

## Module: `hackerzork/systems/network.py`

### Purpose
Simulates the game's internet — a graph of network nodes the player discovers and infiltrates. Each node has an IP, services, vulnerabilities, a firewall, and loot.

### API
```python
class NetworkSim:
    def __init__(self):
        self.nodes: dict[str, NetworkNode] = {}
        self.discovered: set[str] = set()       # IPs the player knows about
        self.compromised: set[str] = set()      # Nodes the player has rooted

    def load_nodes(self, path: str) -> None
        """Load node definitions from YAML directory."""

    def discover_node(self, ip: str) -> NetworkNode | None
        """Mark a node as discovered. Returns node info if it exists."""

    def scan_ports(self, ip: str, ports: list[int] | None = None) -> list[PortResult]
        """Simulate port scan. Returns open ports and service banners."""

    def scan_services(self, ip: str) -> list[ServiceResult]
        """Version detection scan. More heat, more info."""

    def ping(self, ip: str) -> PingResult
        """Check if host is up. Minimal heat."""

    def traceroute(self, ip: str) -> list[str]
        """Show network path to target."""

    def check_firewall(self, ip: str, port: int) -> bool
        """Returns True if port is accessible through firewall."""

    def attempt_exploit(self, ip: str, port: int, exploit: str) -> ExploitResult
        """Try to exploit a vulnerability on a service."""

    def get_connections(self, ip: str) -> list[str]
        """Get IPs of nodes connected to this one (discovered after compromise)."""

    def compromise_node(self, ip: str) -> None
        """Mark node as compromised. Reveals connections and loot."""

    def harden_node(self, ip: str) -> None
        """Called when player fails — node gets harder."""

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
    connections: list[str]
    story_flags: dict[str, str]
    compromised: bool = False
    hardened: int = 0  # Times this node has been hardened

@dataclass
class Port:
    number: int
    service: str
    version: str
    vuln: str | None
    state: str = "open"  # open, closed, filtered

@dataclass
class ExploitResult:
    success: bool
    message: str
    loot: list[Loot] | None
    heat_cost: float
```

### Node Discovery Flow
1. Player starts knowing only a few IPs (from /etc/hosts or evidence files)
2. Scanning/compromising nodes reveals connected node IPs
3. Some nodes are only discoverable through loot (credentials, documents)
4. The network graph expands organically as the player explores

### Hardening Mechanic
When a player fails an exploit attempt:
- The node's difficulty increases
- Some vulnerabilities may be patched (removed from the node)
- New security measures appear (additional firewall rules)
- This is permanent — the world remembers your failures

### Tests: `tests/test_systems/test_network.py`
- Test node loading from YAML
- Test port scanning results
- Test firewall filtering
- Test exploit success/failure
- Test node hardening after failure
- Test connection discovery after compromise
- Test discovery state management
