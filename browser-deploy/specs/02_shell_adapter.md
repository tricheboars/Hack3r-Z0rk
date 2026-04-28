# Spec 02 — Shell Adapter / GameSession (`session.py`)

## Purpose

`GameSession` is the glue between a WebSocket connection and the H@ck3r-Z0rk
game engine. It boots the game, captures its output, and bridges I/O.

## File: `server/session.py`

## The Output Capture Problem

The game uses `rich.Console` which writes to stdout by default. We need to
capture that output and send it over the WebSocket instead.

**Solution**: create a `Console` that writes to a `StringIO` buffer, then
drain the buffer after each `shell.execute()` call.

```python
import io
from rich.console import Console

buf = io.StringIO()
console = Console(file=buf, highlight=False, markup=True, force_terminal=True,
                  force_jupyter=False, color_system="truecolor", width=220)
# After execute():
output = buf.getvalue()
buf.truncate(0)
buf.seek(0)
```

`force_terminal=True` + `color_system="truecolor"` ensures Rich emits real
ANSI escape sequences even though it's writing to a StringIO (not a real TTY).
xterm.js handles ANSI natively.

## Class: `GameSession`

```python
@dataclass
class GameSession:
    session_id: str          # short random ID for logging
    ws: websockets.ServerConnection
    _game: Game | None = None
    _shell: Shell | None = None
    _console: Console | None = None
    _buf: io.StringIO | None = None
    _last_activity: float    # time.monotonic() — for timeout
    _running: bool = False
```

### `async start() -> None`

1. Create `StringIO` buffer and `Console` pointing at it
2. Instantiate `Game(audio_enabled=False, effects_enabled=True, meta_enabled=True)`
3. Call `game.boot()` — this seeds VFS, wires all systems
4. Extract `shell` and `ctx` from the booted game
5. Send the MOTD to the client
6. Set `_running = True`

Boot is synchronous and ~0.5–2s. Run it in an executor so the event loop
isn't blocked:
```python
loop = asyncio.get_event_loop()
await loop.run_in_executor(None, self._game.boot)
```

### `async run() -> None`

Main async loop. Wraps in `asyncio.wait_for` with `HZ_SESSION_TIMEOUT`:

```python
async for message in self.ws:
    self._last_activity = time.monotonic()
    line = message.strip()

    if line in ("exit", "quit"):
        await self.ws.send("\r\nGoodbye.\r\n")
        return

    # Execute in executor (shell.execute is sync)
    loop = asyncio.get_event_loop()
    output = await loop.run_in_executor(None, self._shell.execute, line)

    # Drain Rich console buffer
    rich_out = self._drain_buf()

    # Combine: Rich output takes precedence (it's what the game prints)
    # plain `output` return value is a fallback for commands that return
    # strings directly without going through Console
    full_output = rich_out or output
    if full_output:
        await self.ws.send(full_output.replace("\n", "\r\n"))

    # SkyNet observation — may inject side-channel JSON events
    if self._shell._ctx.skynet is not None:
        await self._shell._ctx.skynet.maybe_intervene()
        skynet_out = self._drain_buf()
        if skynet_out:
            await self.ws.send(skynet_out.replace("\n", "\r\n"))

    # Send prompt after output
    await self.ws.send("\r\n" + self._shell._prompt())
```

### `async teardown() -> None`

- Set `_running = False`
- Call any game cleanup (save state, etc.)
- Log session end

### `_drain_buf() -> str`

```python
def _drain_buf(self) -> str:
    val = self._buf.getvalue()
    self._buf.truncate(0)
    self._buf.seek(0)
    return val
```

## Side-channel events (SkyNet / audio / glitch)

When SkyNet wants to trigger browser-side effects, it sends a JSON message
alongside normal text output. Format:

```json
{"type": "event", "name": "skynet_alert", "payload": {"level": 2}}
{"type": "event", "name": "audio_cue", "payload": {"sound": "heat_warning"}}
{"type": "event", "name": "glitch", "payload": {"duration_ms": 800}}
```

The frontend (`term.js`) detects messages starting with `{` and routes them
to the appropriate browser handler instead of printing to the terminal.

For now, emit a placeholder JSON event whenever SkyNet's `maybe_intervene()`
returns a non-None action. The full event system can be wired up later.

## Timeout handling

Wrap `run()` in:
```python
try:
    await asyncio.wait_for(self.run(), timeout=HZ_SESSION_TIMEOUT)
except asyncio.TimeoutError:
    await self.ws.send("\r\n[Session timed out after inactivity]\r\n")
```
