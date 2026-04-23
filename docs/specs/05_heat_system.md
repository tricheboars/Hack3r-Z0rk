# Spec: Heat System

## Module: `hackerzork/systems/heat.py`

### Purpose
Tracks the player's exposure level. Every aggressive action generates heat. Heat triggers escalating consequences. The player must balance aggression with stealth.

### API
```python
class HeatSystem:
    def __init__(self, events: EventBus):
        self.level: float = 0.0         # 0.0 to 100.0
        self.decay_rate: float = 0.1    # Per game-minute
        self.current_threshold: str = "safe"

    def add_heat(self, amount: float, source: str) -> None
        """Add heat from an action. Emits heat_changed event."""

    def reduce_heat(self, amount: float, source: str) -> None
        """Reduce heat (e.g., using stealth tools, waiting)."""

    def tick(self, game_minutes: float) -> None
        """Called each game tick. Applies decay."""

    def get_status(self) -> HeatStatus
        """Current heat level and active threats."""

    def get_threshold_name(self) -> str
        """Current named threshold."""

@dataclass
class HeatStatus:
    level: float
    threshold: str
    decay_rate: float
    active_threats: list[str]
    time_to_safe: float  # Estimated game-minutes to reach 0

# Heat costs for common actions
HEAT_COSTS = {
    "ping": 0.5,
    "port_scan": 2.0,
    "service_scan": 5.0,
    "exploit_attempt": 10.0,
    "exploit_success": 5.0,   # Lower because you're in now
    "exploit_fail": 15.0,     # Failed = noisy
    "ssh_connect": 1.0,
    "file_exfil": 3.0,
    "brute_force": 20.0,
}
```

### Thresholds
| Level | Name | Effects |
|-------|------|---------|
| 0-24 | `safe` | No countermeasures. Ambient audio is calm. |
| 25-49 | `monitored` | Passive monitoring. Occasional warning in logs. Audio tension rises. |
| 50-74 | `active_response` | ICE programs activate. Some ports close. Firewall rules tighten. Commands may be intercepted. |
| 75-89 | `hunted` | Hunter teams dispatched. Nodes may lock you out. Allies send panicked messages. Time pressure. |
| 90-99 | `critical` | Identity nearly burned. Extreme countermeasures. Audio is alarm + distortion. |
| 100 | `burned` | Forced identity burn. Player must relocate. Lose access to some compromised nodes. Heat resets to 0. |

### Stealth Modifiers
- Using VPN/proxy: -50% heat generation
- Tor routing: -70% heat generation (slower operations)
- Stealth scan flags (-sS): -30% heat vs normal scan
- Time of day (in-game): Night operations generate less heat

### Tests: `tests/test_systems/test_heat.py`
- Test heat accumulation
- Test threshold transitions and events
- Test decay over time
- Test stealth modifiers
- Test burn and reset at 100
