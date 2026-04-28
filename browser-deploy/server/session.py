"""GameSession — bridges one WebSocket connection to the H@ck3r-Z0rk engine.

See specs/02_shell_adapter.md for the full design spec.

TODO (Claude Code session 1):
  - Implement GameSession.start() — boot Game, capture Console output
  - Implement GameSession.run()   — async recv/execute/send loop
  - Implement GameSession.teardown()
  - Wire side-channel JSON events for SkyNet, audio, glitch effects
"""
from __future__ import annotations

import asyncio
import io
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

    async def start(self) -> None:
        """Boot the game engine and send the MOTD to the client.

        TODO: implement per specs/02_shell_adapter.md
        """
        raise NotImplementedError("Implement in Claude Code session 1")

    async def run(self) -> None:
        """Main async loop: receive lines, execute, send output back.

        TODO: implement per specs/02_shell_adapter.md
        """
        raise NotImplementedError("Implement in Claude Code session 1")

    async def teardown(self) -> None:
        """Clean up session resources on disconnect.

        TODO: implement in Claude Code session 1
        """
        log.info("session=%s  teardown", self.session_id)

    def _drain_buf(self) -> str:
        """Drain the Rich console StringIO buffer and return its contents."""
        if self._buf is None:
            return ""
        val = self._buf.getvalue()
        self._buf.truncate(0)
        self._buf.seek(0)
        return val
