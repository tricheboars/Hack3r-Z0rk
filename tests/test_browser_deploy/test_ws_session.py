"""Integration tests for the WebSocket server + GameSession bridge.

Architecture under test:
    websockets client  →  ws_server.handle_connection()
                       →  GameSession.start() / run()
                       →  hackerzork shell.execute()
                       →  output back to client

Two layers:
  Unit  — fake WebSocket (no network), exercises GameSession in isolation.
  Integration — real server on a random loopback port, full round-trip.

pytest-asyncio is in auto mode (see pyproject.toml).  Integration tests each
spin up their own server so they don't share event loops with module-scoped
fixtures (a known pytest-asyncio footgun).  Boot is fast enough (~0.5 s for
the server itself; game boots per connection).
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
import websockets
import websockets.asyncio.server

from browser_deploy.server.session import GameSession
from browser_deploy.server.ws_server import handle_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _collect(ws: Any, n: int, timeout: float = 30.0) -> list[str]:
    """Receive up to *n* messages with a per-message timeout."""
    msgs: list[str] = []
    for _ in range(n):
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msgs.append(msg)
        except asyncio.TimeoutError:
            break
    return msgs


def _is_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def _find_event(msgs: list[str], name: str) -> dict | None:
    """Return the first side-channel event with the given name, or None."""
    for m in msgs:
        if _is_json(m):
            obj = json.loads(m)
            if obj.get("type") == "event" and obj.get("name") == name:
                return obj
    return None


@contextlib.asynccontextmanager
async def _server_and_client() -> AsyncIterator[tuple[str, Any]]:
    """Spin up a real ws_server on a random port and yield (url, connected_ws).

    Consumes the initial prompt so callers start from a clean ready state.
    """
    async with websockets.asyncio.server.serve(
        handle_connection, "127.0.0.1", 0
    ) as server:
        port = server.sockets[0].getsockname()[1]
        url = f"ws://127.0.0.1:{port}"
        async with websockets.connect(url) as ws:
            await asyncio.wait_for(ws.recv(), timeout=30)  # consume initial prompt
            yield url, ws


@contextlib.asynccontextmanager
async def _server() -> AsyncIterator[str]:
    """Spin up a real ws_server and yield only the URL."""
    async with websockets.asyncio.server.serve(
        handle_connection, "127.0.0.1", 0
    ) as server:
        port = server.sockets[0].getsockname()[1]
        yield f"ws://127.0.0.1:{port}"


# ---------------------------------------------------------------------------
# Fake WebSocket for unit tests (no network required)
# ---------------------------------------------------------------------------

class _FakeWS:
    """Minimal fake that lets GameSession send/recv without a real socket."""

    def __init__(self, incoming: list[str]) -> None:
        self._in: asyncio.Queue[str] = asyncio.Queue()
        self.sent: list[str] = []
        self.remote_address = ("127.0.0.1", 9999)
        for msg in incoming:
            self._in.put_nowait(msg)

    async def send(self, msg: str) -> None:
        self.sent.append(msg)

    async def recv(self) -> str:
        return await self._in.get()

    def __aiter__(self) -> "_FakeWS":
        return self

    async def __anext__(self) -> str:
        try:
            return self._in.get_nowait()
        except asyncio.QueueEmpty:
            raise StopAsyncIteration

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Unit tests — GameSession with fake WebSocket
# ---------------------------------------------------------------------------

@pytest.mark.slow
async def test_session_start_sends_prompt() -> None:
    """start() should send at least one message containing the shell prompt."""
    fake = _FakeWS([])
    session = GameSession(ws=fake)
    await session.start()
    await session.teardown()

    assert fake.sent, "start() must send at least one message"
    assert "\x1b[" in fake.sent[-1], "Last message from start() should be ANSI prompt"


@pytest.mark.slow
async def test_session_ls_returns_listing() -> None:
    """Sending 'ls' should produce output containing known home-dir entries."""
    cmd = json.dumps({"type": "input", "data": "ls"})
    fake = _FakeWS([cmd])
    session = GameSession(ws=fake)
    await session.start()
    sent_before = len(fake.sent)

    await session.run()
    await session.teardown()

    combined = "".join(fake.sent[sent_before:])
    assert "evidence" in combined or "games" in combined, (
        f"ls output missing expected dirs; got: {combined!r}"
    )


@pytest.mark.slow
async def test_session_empty_input_returns_prompt() -> None:
    """Sending an empty line should echo back the prompt."""
    cmd = json.dumps({"type": "input", "data": ""})
    fake = _FakeWS([cmd])
    session = GameSession(ws=fake)
    await session.start()
    sent_before = len(fake.sent)

    await session.run()
    await session.teardown()

    new_msgs = fake.sent[sent_before:]
    assert new_msgs, "Empty input should still produce a response"
    assert "\x1b[" in "".join(new_msgs)


@pytest.mark.slow
async def test_session_exit_returns_goodbye() -> None:
    """Sending 'exit' should send a goodbye message and terminate run()."""
    cmd = json.dumps({"type": "input", "data": "exit"})
    fake = _FakeWS([cmd])
    session = GameSession(ws=fake)
    await session.start()
    sent_before = len(fake.sent)

    await session.run()
    await session.teardown()

    combined = "".join(fake.sent[sent_before:])
    assert "goodbye" in combined.lower(), (
        f"exit did not send goodbye; got: {combined!r}"
    )


@pytest.mark.slow
async def test_session_resize_no_crash() -> None:
    """A resize message should be handled silently without crashing."""
    resize = json.dumps({"type": "resize", "cols": 80, "rows": 24})
    ls = json.dumps({"type": "input", "data": "ls"})
    fake = _FakeWS([resize, ls])
    session = GameSession(ws=fake)
    await session.start()
    await session.run()
    await session.teardown()

    combined = "".join(fake.sent)
    assert "evidence" in combined or "games" in combined


@pytest.mark.slow
async def test_session_heat_side_channel() -> None:
    """nmap should not crash the session; if it emits heat_update it's well-formed."""
    cmd = json.dumps({"type": "input", "data": "nmap 10.13.37.1"})
    fake = _FakeWS([cmd])
    session = GameSession(ws=fake)
    await session.start()
    sent_before = len(fake.sent)

    await session.run()
    await session.teardown()

    new_msgs = fake.sent[sent_before:]
    heat_event = _find_event(new_msgs, "heat_update")
    if heat_event is not None:
        assert "heat" in heat_event.get("payload", {}), (
            f"heat_update payload missing 'heat' key: {heat_event}"
        )


@pytest.mark.slow
async def test_session_unknown_command() -> None:
    """An unknown command should return 'command not found', not raise."""
    cmd = json.dumps({"type": "input", "data": "frobnicate"})
    fake = _FakeWS([cmd])
    session = GameSession(ws=fake)
    await session.start()
    sent_before = len(fake.sent)

    await session.run()
    await session.teardown()

    combined = "".join(fake.sent[sent_before:])
    assert "not found" in combined or "frobnicate" in combined


def test_drain_buf_clears_buffer() -> None:
    """_drain_buf() should return content once then empty the buffer."""
    import asyncio

    async def _run() -> None:
        fake = _FakeWS([])
        session = GameSession(ws=fake)
        session._buf = io.StringIO()
        session._buf.write("hello world")

        first = session._drain_buf()
        second = session._drain_buf()

        assert first == "hello world"
        assert second == ""

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Integration tests — real server + real WebSocket on loopback
#
# Each test owns its own server+connection so there's no cross-test event-
# loop sharing (avoids pytest-asyncio module-scope fixture footgun).
# ---------------------------------------------------------------------------

@pytest.mark.slow
async def test_integration_connect_sends_ansi_prompt() -> None:
    """Fresh connection should receive an ANSI-styled prompt immediately."""
    async with _server() as url:
        async with websockets.connect(url) as ws:
            prompt = await asyncio.wait_for(ws.recv(), timeout=30)
    assert "\x1b[" in prompt, f"Expected ANSI prompt, got: {prompt!r}"
    assert "user" in prompt, f"Prompt should contain 'user', got: {prompt!r}"


@pytest.mark.slow
async def test_integration_ls() -> None:
    """ls should return the home directory listing over a real WebSocket."""
    async with _server_and_client() as (_, ws):
        await ws.send(json.dumps({"type": "input", "data": "ls"}))
        msgs = await _collect(ws, n=5, timeout=30)

    combined = "".join(msgs)
    assert "evidence" in combined or "games" in combined or "notes" in combined, (
        f"ls response missing home dir contents: {combined!r}"
    )


@pytest.mark.slow
async def test_integration_pwd() -> None:
    """pwd should report /home/user."""
    async with _server_and_client() as (_, ws):
        await ws.send(json.dumps({"type": "input", "data": "pwd"}))
        msgs = await _collect(ws, n=3, timeout=30)

    assert "/home/user" in "".join(msgs), f"pwd output: {''.join(msgs)!r}"


@pytest.mark.slow
async def test_integration_unknown_command_error() -> None:
    """An unknown command should produce 'command not found', not a crash."""
    async with _server_and_client() as (_, ws):
        await ws.send(json.dumps({"type": "input", "data": "frobnicate"}))
        msgs = await _collect(ws, n=3, timeout=30)

    combined = "".join(msgs)
    assert "not found" in combined or "frobnicate" in combined, (
        f"Unknown command response: {combined!r}"
    )


@pytest.mark.slow
async def test_integration_resize_then_command() -> None:
    """Resize followed by a command should work without error."""
    async with _server_and_client() as (_, ws):
        await ws.send(json.dumps({"type": "resize", "cols": 100, "rows": 30}))
        await ws.send(json.dumps({"type": "input", "data": "pwd"}))
        msgs = await _collect(ws, n=3, timeout=30)

    assert "/home/user" in "".join(msgs)


@pytest.mark.slow
async def test_integration_session_cap() -> None:
    """When the session cap is reached, new connections receive a rejection message."""
    import browser_deploy.server.ws_server as srv

    original_cap = srv.HZ_MAX_SESSIONS
    try:
        async with _server() as url:
            # Force the cap to 0 so any new connection is immediately over limit
            srv.HZ_MAX_SESSIONS = 0
            async with websockets.connect(url) as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
            assert "capacity" in msg.lower(), (
                f"Cap rejection message should mention capacity: {msg!r}"
            )
    finally:
        srv.HZ_MAX_SESSIONS = original_cap


@pytest.mark.slow
async def test_integration_side_channel_json_parseable() -> None:
    """Any JSON messages received alongside command output must be valid events."""
    async with _server_and_client() as (_, ws):
        await ws.send(json.dumps({"type": "input", "data": "ls"}))
        msgs = await _collect(ws, n=5, timeout=30)

    for m in msgs:
        if m.startswith("{"):
            obj = json.loads(m)  # raises AssertionError if malformed
            assert obj.get("type") == "event", f"Unexpected JSON shape: {obj}"
            assert "name" in obj
            assert "payload" in obj
