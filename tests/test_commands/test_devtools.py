"""Tests for hackerzork.commands.devtools (hz_debug console)."""
from __future__ import annotations

import pytest

import hackerzork.commands.devtools  # noqa: F401 — registers commands
import hackerzork.commands.devtools as devtools_mod
from hackerzork.commands.devtools import cmd_hz_debug, _DEBUG_KEY
from hackerzork.engine.command_registry import CommandContext
from hackerzork.systems.heat import HeatSystem
from hackerzork.systems.network import Firewall, NetworkNode, NetworkSim, Port
from hackerzork.systems.state import GameState
from hackerzork.systems.virtual_fs import VirtualFS

_FS_TEMPLATE = {
    "/home/user": {"_meta": {"permissions": "755", "owner": "user"}},
    "/etc": {
        "shadow": {
            "content": "root:!:19372:::::::\n",
            "permissions": "640",
            "owner": "root",
        }
    },
    "/tmp": {},
}


def _make_ctx(*, with_heat: bool = True, with_state: bool = True) -> CommandContext:
    fs = VirtualFS(template=_FS_TEMPLATE)
    net = NetworkSim()

    # Add a test node
    node = NetworkNode(
        id="node_t", name="Test", ip="10.0.0.99", hostname="test.local",
        ports=[Port(number=80, service="http", version="1.0", vuln="CVE-test")],
        firewall=Firewall(enabled=False),
        difficulty=1, heat_modifier=1.0, loot=[], connections=[],
    )
    net.add_node(node)

    heat = HeatSystem() if with_heat else None
    state = GameState() if with_state else None
    env = {"CWD": "/home/user", "HOME": "/home/user", "USER": "user"}
    return CommandContext(fs=fs, network=net, env=env, heat=heat, state=state)


def _reset_unlock() -> None:
    """Reset the module-level unlock state between tests."""
    devtools_mod._set_unlocked(False)


@pytest.fixture(autouse=True)
def reset_unlock():
    _reset_unlock()
    yield
    _reset_unlock()


def _run(ctx: CommandContext, args: list[str]) -> str:
    return cmd_hz_debug(ctx, args)


# ---------------------------------------------------------------------------
# Auth / unlock
# ---------------------------------------------------------------------------


class TestAuth:
    def test_wrong_key_looks_like_not_found(self):
        ctx = _make_ctx()
        out = _run(ctx, ["wrongkey"])
        assert "not found" in out.lower()

    def test_no_args_locked(self):
        ctx = _make_ctx()
        out = _run(ctx, [])
        assert "not found" in out.lower()

    def test_correct_key_unlocks_and_shows_banner(self):
        ctx = _make_ctx()
        out = _run(ctx, [_DEBUG_KEY])
        assert "DEV CONSOLE" in out or "hz_debug" in out.lower()

    def test_stays_unlocked_after_first_unlock(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])  # unlock
        # Now can run without key
        out = _run(ctx, ["help"])
        assert "subcommand" in out.lower()

    def test_key_accepted_again_when_already_unlocked(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, [_DEBUG_KEY, "help"])
        assert "subcommand" in out.lower()


# ---------------------------------------------------------------------------
# heat subcommand
# ---------------------------------------------------------------------------


class TestHeat:
    def test_heat_show(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["heat"])
        assert "level" in out.lower()
        assert "threshold" in out.lower()

    def test_heat_set(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        _run(ctx, ["heat", "set", "50"])
        assert abs(ctx.heat.level - 50.0) < 0.01

    def test_heat_set_clamps_to_100(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        _run(ctx, ["heat", "set", "999"])
        assert ctx.heat.level <= 100.0

    def test_heat_set_invalid(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["heat", "set", "notanumber"])
        assert "invalid" in out.lower()


# ---------------------------------------------------------------------------
# node subcommand
# ---------------------------------------------------------------------------


class TestNode:
    def test_node_info(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["node", "10.0.0.99"])
        assert "hostname" in out.lower()
        assert "test.local" in out

    def test_node_missing(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["node"])
        assert "ip" in out.lower() or "missing" in out.lower() or "<ip>" in out

    def test_node_not_found(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["node", "9.9.9.9"])
        assert "no node" in out.lower()

    def test_node_compromise(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        _run(ctx, ["node", "10.0.0.99", "compromise"])
        assert "10.0.0.99" in ctx.network.compromised

    def test_node_reset(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        ctx.network.compromise_node("10.0.0.99")
        _run(ctx, ["node", "10.0.0.99", "reset"])
        assert "10.0.0.99" not in ctx.network.compromised


# ---------------------------------------------------------------------------
# unlock subcommand
# ---------------------------------------------------------------------------


class TestUnlock:
    def test_unlock_known_feature(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["unlock", "shadow"])
        assert "unlocked" in out.lower() or "shadow" in out

    def test_unlock_sets_flag(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        _run(ctx, ["unlock", "shadow"])
        assert ctx.state.has_flag("shadow_unlocked")

    def test_unlock_unknown(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["unlock", "notreal"])
        assert "unknown" in out.lower()

    def test_unlock_no_args_shows_list(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["unlock"])
        assert "shadow" in out


# ---------------------------------------------------------------------------
# scan subcommand
# ---------------------------------------------------------------------------


class TestScan:
    def test_scan_discovers_node(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        assert "10.0.0.99" not in ctx.network.discovered
        _run(ctx, ["scan", "10.0.0.99"])
        assert "10.0.0.99" in ctx.network.discovered

    def test_scan_missing_ip(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["scan"])
        assert "<ip>" in out.lower() or "scan <ip>" in out.lower()

    def test_scan_unknown_ip(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["scan", "9.9.9.9"])
        assert "no node" in out.lower()


# ---------------------------------------------------------------------------
# flag subcommand
# ---------------------------------------------------------------------------


class TestFlag:
    def test_flag_set(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        _run(ctx, ["flag", "my_test_flag"])
        assert ctx.state.has_flag("my_test_flag")

    def test_flag_clear(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        ctx.state.set_flag("my_test_flag")
        _run(ctx, ["flag", "my_test_flag", "clear"])
        assert not ctx.state.has_flag("my_test_flag")

    def test_flag_list(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        ctx.state.set_flag("visible_flag")
        out = _run(ctx, ["flag"])
        assert "visible_flag" in out


# ---------------------------------------------------------------------------
# state subcommand
# ---------------------------------------------------------------------------


class TestState:
    def test_state_shows_sections(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["state"])
        assert "Heat" in out
        assert "Network" in out
        assert "Flags" in out


# ---------------------------------------------------------------------------
# reset subcommand
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_heat(self):
        ctx = _make_ctx()
        ctx.heat.level = 75.0
        _run(ctx, [_DEBUG_KEY])
        _run(ctx, ["reset", "heat"])
        assert ctx.heat.level == 0.0

    def test_reset_unknown(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["reset", "unknown"])
        assert "unknown" in out.lower()


# ---------------------------------------------------------------------------
# Unknown subcommand
# ---------------------------------------------------------------------------


class TestUnknownSubcmd:
    def test_unknown_subcommand(self):
        ctx = _make_ctx()
        _run(ctx, [_DEBUG_KEY])
        out = _run(ctx, ["doesnotexist"])
        assert "unknown" in out.lower()
