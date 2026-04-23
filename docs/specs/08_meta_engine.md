# Spec: Meta Engine (SkyNet / Fourth Wall)

## Modules: `hackerzork/meta/`

### Purpose
SkyNet is watching. The meta engine observes all player actions through the event bus, builds a model of what the player knows, and decides when and how to break the fourth wall. This is the Pony Island layer.

### meta/skynet.py
```python
class SkyNetEngine:
    def __init__(self, events: EventBus):
        self.awareness: float = 0.0      # How aware SkyNet is of the player
        self.escalation: int = 0         # Current escalation tier (0-5)
        self.observations: list[dict]    # What SkyNet has noticed
        self.interventions: int = 0      # How many times it has acted

    def observe(self, event: Event) -> None
        """Called on every event. SkyNet watches everything."""

    def evaluate(self) -> None
        """Periodic check — should SkyNet act?"""

    def intervene(self, effect_type: str) -> None
        """Trigger a fourth-wall break or interference."""
```

### Escalation Tiers
| Tier | Trigger | Effects |
|------|---------|---------|
| 0 | Game start | Nothing. SkyNet is dormant. |
| 1 | Player reads evidence files | Subtle: occasional typo in output that wasn't there, a log entry with today's date |
| 2 | Player compromises first node | Unsettling: IRC message from unknown user who seems to know things, terminal title flickers |
| 3 | Player discovers SkyNet traces in nodes | Overt: fake error messages, commands that echo back differently than typed, files that change between reads |
| 4 | Player gets close to SkyNet core | Hostile: fake crashes, save corruption warnings, commands intercepted, the AI companion (Claude) gets glitchy |
| 5 | Endgame | Full assault: SkyNet directly addresses the player by name (meta — uses OS username), terminal behaves erratically, everything is unstable |

### meta/fourth_wall.py
```python
class FourthWallBreaker:
    """Implements specific fourth-wall-breaking effects."""

    async def change_terminal_title(self, text: str) -> None
    async def fake_crash(self, duration: float = 3.0) -> None
    async def fake_reboot(self) -> None
    async def inject_text(self, text: str) -> None  # Text appears unbidden
    async def command_echo_corruption(self, original: str) -> str  # What you typed... changes
    async def phantom_cursor(self, duration: float = 2.0) -> None  # Cursor moves on its own
    async def fake_system_error(self, error_type: str) -> None
    async def address_player(self, message: str) -> None  # SkyNet talks to YOU
    async def corrupt_prompt(self) -> str  # The prompt itself becomes wrong
```

### meta/corruption.py
```python
class CorruptionEngine:
    """Handles save corruption and data integrity attacks."""

    def corrupt_save_display(self, save_data: dict) -> dict
        """Make save data LOOK corrupted (but real data is fine)."""

    def fake_save_warning(self) -> str
        """Generate a fake 'save corrupted' warning."""

    def modify_filesystem_silently(self, fs: VirtualFS) -> None
        """Subtly change a file the player has already read."""

    def plant_evidence(self, fs: VirtualFS, content: str) -> None
        """Add a file that wasn't there before. SkyNet leaving messages."""
```

### Design Notes
- SkyNet should feel INTELLIGENT, not random. Its actions should feel targeted and knowing.
- Effects should be rare at first — the power is in the surprise.
- The player should question what's "real" in the game vs. SkyNet interference.
- Never ACTUALLY corrupt save data. Only make it LOOK corrupted.
- The meta engine has access to real system info (username, time) for maximum creepiness — but this should be used sparingly and ethically.
- Players can disable meta effects with a flag for accessibility.

### Ethical Boundaries
- Never access real files on the player's machine
- Never send real network traffic
- Never create real processes
- All "system errors" must be visually distinguishable if the player pauses and looks carefully
- Include a safe word / escape hatch if the player is genuinely concerned
