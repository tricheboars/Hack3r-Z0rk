"""H@ck3r-Z0rk WebSocket server entry point.

Run:
    python -m browser_deploy.server.ws_server
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import time

import websockets
import websockets.asyncio.server

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


async def handle_connection(ws: websockets.asyncio.server.ServerConnection) -> None:
    """Called by websockets library for each new connection."""
    from browser_deploy.server.session import GameSession

    peer = ws.remote_address

    if len(_sessions) >= HZ_MAX_SESSIONS:
        log.warning("Session cap reached (%d) — rejecting %s", HZ_MAX_SESSIONS, peer)
        await ws.send("\r\n[Server is at capacity. Try again later.]\r\n")
        return

    session = GameSession(ws=ws)
    _sessions[session.session_id] = session
    start_time = time.monotonic()
    log.info("session=%s  connected from %s", session.session_id, peer)

    try:
        await session.start()
        try:
            await asyncio.wait_for(session.run(), timeout=HZ_SESSION_TIMEOUT)
        except asyncio.TimeoutError:
            log.info("session=%s  timed out", session.session_id)
            try:
                await ws.send("\r\n[Session timed out after inactivity]\r\n")
            except Exception:
                pass
    except Exception:
        log.exception("session=%s  unhandled error", session.session_id)
        try:
            await ws.send("\r\n[Internal server error — session terminated]\r\n")
        except Exception:
            pass
    finally:
        await session.teardown()
        _sessions.pop(session.session_id, None)
        elapsed = time.monotonic() - start_time
        log.info("session=%s  disconnected after %.0fs", session.session_id, elapsed)


async def main() -> None:
    """Start the WebSocket server."""
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    def _handle_signal() -> None:
        log.info("Shutdown signal received")
        stop_event.set()

    try:
        loop.add_signal_handler(signal.SIGTERM, _handle_signal)
        loop.add_signal_handler(signal.SIGINT, _handle_signal)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        signal.signal(signal.SIGTERM, lambda s, f: loop.call_soon_threadsafe(_handle_signal))
        signal.signal(signal.SIGINT, lambda s, f: loop.call_soon_threadsafe(_handle_signal))

    async with websockets.asyncio.server.serve(handle_connection, HZ_HOST, HZ_PORT):
        log.info(
            "H@ck3r-Z0rk WebSocket server listening on ws://%s:%d",
            HZ_HOST,
            HZ_PORT,
        )
        log.info(
            "Max sessions: %d  Timeout: %ds  Debug: %s",
            HZ_MAX_SESSIONS,
            HZ_SESSION_TIMEOUT,
            HZ_DEBUG,
        )

        await stop_event.wait()

    # Graceful shutdown: notify all active sessions
    log.info("Closing %d active session(s)…", len(_sessions))
    for session in list(_sessions.values()):
        try:
            await session.ws.send("\r\n[Server shutting down]\r\n")
            await session.ws.close()
        except Exception:
            pass

    log.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
