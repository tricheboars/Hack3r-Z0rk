"""H@ck3r-Z0rk WebSocket server entry point.

See specs/01_ws_server.md for the full design spec.

TODO (Claude Code session 2):
  - Implement handle_connection() — create GameSession, manage lifecycle
  - Implement main() — bind server, handle signals, log startup
  - Enforce HZ_MAX_SESSIONS cap
  - Graceful shutdown on SIGTERM/SIGINT

Run:
    python -m browser_deploy.server.ws_server
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

log = logging.getLogger(__name__)

# ── Config from environment ────────────────────────────────────────────────
HZ_HOST            = os.getenv("HZ_HOST", "0.0.0.0")
HZ_PORT            = int(os.getenv("HZ_PORT", "8765"))
HZ_MAX_SESSIONS    = int(os.getenv("HZ_MAX_SESSIONS", "20"))
HZ_SESSION_TIMEOUT = int(os.getenv("HZ_SESSION_TIMEOUT", "1800"))
HZ_DEBUG           = os.getenv("HZ_DEBUG", "0") == "1"

logging.basicConfig(
    level=logging.DEBUG if HZ_DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Active sessions — keyed by session_id
_sessions: dict[str, object] = {}


async def handle_connection(ws) -> None:  # type: ignore[no-untyped-def]
    """Called by websockets library for each new connection.

    TODO: implement per specs/01_ws_server.md
    """
    raise NotImplementedError("Implement in Claude Code session 2")


async def main() -> None:
    """Start the WebSocket server.

    TODO: implement per specs/01_ws_server.md
    """
    raise NotImplementedError("Implement in Claude Code session 2")


if __name__ == "__main__":
    asyncio.run(main())
