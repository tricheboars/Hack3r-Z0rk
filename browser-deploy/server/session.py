"""GameSession — bridges one WebSocket connection to the H@ck3r-Z0rk engine."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    import websockets

log = logging.getLogger(__name__)


@dataclass
class GameSession:
    """One player's isolated game session over a WebSocket connection."""

    ws: "websockets.ServerConnection"
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    _game: object = field(default=None, init=False, repr=False)
    _shell: object = field(default=None, init=False, repr=False)
    _console: Console | None = field(default=None, init=False, repr=False)
    _buf: io.StringIO | None = field(default=None, init=False, repr=False)
    _last_activity: float = field(default_factory=time.monotonic, init=False)
    _running: bool = field(default=False, init=False)
    _pending_events: list[str] = field(default_factory=list, init=False, repr=False)
    _terminal_cols: int = field(default=220, init=False)

    async def start(self) -> None:
        """Boot the game engine and send the initial prompt to the client."""
        from hackerzork.game import Game

        self._buf = io.StringIO()
        self._console = Console(
            file=self._buf,
            highlight=False,
            markup=True,
            force_terminal=True,
            force_jupyter=False,
            color_system="truecolor",
            width=self._terminal_cols,
        )

        self._game = Game(audio_enabled=False, effects_enabled=True, meta_enabled=True)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._game.boot)

        self._shell = self._game._shell
        # Inject our StringIO console so any Rich.print() calls are captured
        self._shell._console = self._console

        # Wire EventBus for side-channel events sent to the browser
        ctx = self._shell._ctx
        ctx.events.on("heat_changed", self._queue_heat_event)
        ctx.events.on("scan_performed", self._queue_scan_event)
        ctx.events.on("file_read", self._queue_file_event)
        ctx.events.on("skynet_intervene", self._queue_skynet_event)
        ctx.events.on("node_compromised", self._queue_node_event)
        ctx.events.on("glitch_triggered", self._queue_glitch_event)
        ctx.events.on("node_changed", self._queue_prompt_event)

        self._running = True
        log.info("session=%s  game booted", self.session_id)

        # Send initial prompt
        await self.ws.send(self._shell._prompt())

    async def run(self) -> None:
        """Main async loop: receive messages, execute commands, send output."""
        async for raw_message in self.ws:
            self._last_activity = time.monotonic()

            # Parse JSON input from browser (game.html protocol)
            try:
                msg = json.loads(raw_message)
            except (json.JSONDecodeError, ValueError):
                msg = {"type": "input", "data": str(raw_message)}

            msg_type = msg.get("type", "input")

            if msg_type == "resize":
                cols = int(msg.get("cols", 220))
                self._terminal_cols = cols
                if self._buf is not None:
                    self._console = Console(
                        file=self._buf,
                        highlight=False,
                        markup=True,
                        force_terminal=True,
                        force_jupyter=False,
                        color_system="truecolor",
                        width=cols,
                    )
                    self._shell._console = self._console
                continue

            # Input message — extract the command line
            line = msg.get("data", "").strip()

            if line in ("exit", "quit"):
                await self.ws.send("\r\nGoodbye.\r\n")
                return

            if not line:
                await self.ws.send("\r\n" + self._shell._prompt())
                continue

            # Execute synchronous shell in thread pool to avoid blocking the loop
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(None, self._shell.execute, line)

            # Drain Rich console buffer (captures any console.print() calls)
            rich_out = self._drain_buf()

            # Rich output takes precedence; return value is the fallback
            full_output = rich_out or output or ""
            if full_output:
                await self.ws.send(full_output.replace("\n", "\r\n"))

            # SkyNet observation — may inject side-channel events
            ctx = self._shell._ctx
            if ctx.skynet is not None:
                skynet_result = await ctx.skynet.maybe_intervene()
                skynet_out = self._drain_buf()
                if skynet_out:
                    await self.ws.send(skynet_out.replace("\n", "\r\n"))
                if skynet_result:
                    await self.ws.send(json.dumps({
                        "type": "event",
                        "name": "skynet_alert",
                        "payload": {"message": skynet_result, "level": 1},
                    }))

            # Flush all queued side-channel events
            await self._flush_events()

            # Send prompt ready for next command
            await self.ws.send("\r\n" + self._shell._prompt())

    async def teardown(self) -> None:
        """Clean up session resources on disconnect."""
        self._running = False
        if self._shell is not None:
            ctx = self._shell._ctx
            ctx.events.off("heat_changed", self._queue_heat_event)
            ctx.events.off("scan_performed", self._queue_scan_event)
            ctx.events.off("file_read", self._queue_file_event)
            ctx.events.off("skynet_intervene", self._queue_skynet_event)
            ctx.events.off("node_compromised", self._queue_node_event)
            ctx.events.off("glitch_triggered", self._queue_glitch_event)
            ctx.events.off("node_changed", self._queue_prompt_event)
        log.info("session=%s  teardown", self.session_id)

    def _drain_buf(self) -> str:
        """Drain the Rich console StringIO buffer and return its contents."""
        if self._buf is None:
            return ""
        val = self._buf.getvalue()
        self._buf.truncate(0)
        self._buf.seek(0)
        return val

    async def _flush_events(self) -> None:
        """Send all queued side-channel JSON events to the browser."""
        for event_json in self._pending_events:
            await self.ws.send(event_json)
        self._pending_events.clear()

    # ── Sync EventBus handlers — queue JSON for flushing after each command ──

    def _queue_heat_event(self, event: object) -> None:
        heat = getattr(event, "data", {}).get("heat", 0.0)
        self._pending_events.append(json.dumps({
            "type": "event",
            "name": "heat_update",
            "payload": {"heat": round(float(heat), 1)},
        }))

    def _queue_scan_event(self, event: object) -> None:
        data = getattr(event, "data", {})
        self._pending_events.append(json.dumps({
            "type": "event",
            "name": "node_discovered",
            "payload": {
                "ip": data.get("target", ""),
                "name": data.get("name", ""),
                "hostname": data.get("hostname", ""),
                "status": "scanned",
                "connections": data.get("connections", []),
            },
        }))

    def _queue_file_event(self, event: object) -> None:
        data = getattr(event, "data", {})
        self._pending_events.append(json.dumps({
            "type": "event",
            "name": "file_catalogued",
            "payload": {
                "path": data.get("path", ""),
                "name": data.get("name", ""),
                "content": data.get("content", ""),
                "modified": data.get("modified", ""),
                "owner": data.get("owner", ""),
                "encrypted": data.get("encrypted", False),
                "isNew": True,
            },
        }))

    def _queue_skynet_event(self, event: object) -> None:
        data = getattr(event, "data", {})
        self._pending_events.append(json.dumps({
            "type": "event",
            "name": "skynet_alert",
            "payload": {
                "message": data.get("message", ""),
                "level": data.get("level", 1),
            },
        }))

    def _queue_node_event(self, event: object) -> None:
        data = getattr(event, "data", {})
        self._pending_events.append(json.dumps({
            "type": "event",
            "name": "node_discovered",
            "payload": {
                "ip": data.get("ip", ""),
                "name": data.get("name", ""),
                "hostname": data.get("hostname", ""),
                "status": "owned",
                "connections": data.get("connections", []),
            },
        }))

    def _queue_glitch_event(self, event: object) -> None:
        data = getattr(event, "data", {})
        self._pending_events.append(json.dumps({
            "type": "event",
            "name": "glitch",
            "payload": {"duration_ms": data.get("duration_ms", 400)},
        }))

    def _queue_prompt_event(self, event: object) -> None:
        data = getattr(event, "data", {})
        self._pending_events.append(json.dumps({
            "type": "event",
            "name": "prompt_update",
            "payload": {
                "user": data.get("user", "user"),
                "node": data.get("node", ""),
            },
        }))
