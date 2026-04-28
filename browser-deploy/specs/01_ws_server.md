# Spec 01 — WebSocket Server (`ws_server.py`)

## Purpose

The entry point for the browser deployment. Listens for WebSocket connections,
creates a `GameSession` per connection, and manages the session lifecycle.

## File: `server/ws_server.py`

## Dependencies

```
websockets>=12.0
```

## Behavior

### Startup

1. Read config from environment variables (see CLAUDE.md for the full list)
2. Bind a WebSocket server on `HZ_HOST:HZ_PORT`
3. Log startup info to stdout
4. Accept connections indefinitely

### Per-connection flow

```
client connects
    → check HZ_MAX_SESSIONS cap (reject with message if over limit)
    → create GameSession(ws)
    → session.start()       # boots game, sends MOTD
    → session.run()         # async loop — recv/execute/send
    → session.teardown()    # cleanup on disconnect or timeout
client disconnects
```

### Graceful shutdown

Handle `SIGTERM` and `SIGINT`:
- Stop accepting new connections
- Send `\r\n[Server shutting down]\r\n` to all active sessions
- Close all WebSocket connections cleanly
- Exit

## Interface

```python
async def main() -> None:
    """Start the WebSocket server."""

async def handle_connection(ws: websockets.ServerConnection) -> None:
    """Called by websockets library for each new connection."""
```

## Error handling

- If `GameSession.start()` raises, send an error message to the client and close
- Log all exceptions with traceback
- Never let one bad session crash the server

## Logging

Use Python's standard `logging` module. Format:
```
2026-04-27 09:14:00 [INFO]  session=abc123  connected from 192.168.1.5
2026-04-27 09:14:01 [INFO]  session=abc123  game booted in 1.2s
2026-04-27 09:45:00 [INFO]  session=abc123  disconnected after 1859s
```
