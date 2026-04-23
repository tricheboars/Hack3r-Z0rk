# Spec: Event Bus

## Module: `hackerzork/systems/events.py`

### Purpose
Decoupled inter-system communication. Any system can emit events, any system can listen. This is how the heat system knows you scanned something, how the meta engine knows you found a clue, and how the audio system knows to change the mood.

### API
```python
class EventBus:
    def on(self, event_name: str, handler: Callable) -> None
        """Register a handler for an event."""

    def off(self, event_name: str, handler: Callable) -> None
        """Unregister a handler."""

    def emit(self, event_name: str, **data) -> None
        """Emit an event to all registered handlers."""

    async def emit_async(self, event_name: str, **data) -> None
        """Async emit for handlers that need to await."""

    def history(self, event_name: str | None = None) -> list[Event]
        """Return event history, optionally filtered by name."""

@dataclass
class Event:
    name: str
    data: dict
    timestamp: float
```

### Standard Events
| Event | Emitted By | Data | Consumed By |
|-------|-----------|------|------------|
| `command_entered` | shell | `{cmd, raw_input}` | meta, history |
| `scan_performed` | nmap cmd | `{target, ports, stealth}` | heat, meta |
| `exploit_attempted` | hack cmds | `{target, vuln, success}` | heat, state, meta |
| `node_compromised` | hack cmds | `{node_id, method}` | state, network, comms, meta |
| `file_read` | cat/less | `{path, node}` | meta |
| `ssh_connected` | ssh cmd | `{target, user}` | heat, state |
| `heat_changed` | heat system | `{level, delta, threshold_crossed}` | audio, meta |
| `heat_threshold` | heat system | `{level, threshold_name}` | comms, effects, meta |
| `message_received` | comms | `{from, channel, content}` | meta |
| `state_changed` | state | `{flag, old, new}` | meta, comms |
| `meta_escalation` | meta engine | `{level, effect}` | effects, audio |

### Design Notes
- Handlers run synchronously by default (emit), async option available (emit_async)
- Event history is stored for the meta engine to analyze patterns
- History has a configurable max size (default 1000 events)
- Events are dict-serializable for save/load

### Tests: `tests/test_systems/test_events.py`
- Test register/unregister handlers
- Test emit calls all handlers
- Test event history recording
- Test no errors on emit with no handlers
- Test handler exceptions don't crash the bus
