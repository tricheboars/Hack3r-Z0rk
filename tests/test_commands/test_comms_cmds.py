"""Tests for hackerzork/commands/comms_cmds.py."""
from __future__ import annotations

import pytest

import hackerzork.commands.comms_cmds  # register commands
from hackerzork.engine.command_registry import CommandContext, DEFAULT_REGISTRY
from hackerzork.systems.comms import CommsSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHANNELS = {
    "#main": {
        "topic": "main channel",
        "participants": ["alice", "bob"],
        "history": [
            {"timestamp": "2026-01-01 00:00", "sender": "alice", "content": "hello world"},
        ],
        "triggers": [
            {"keywords": ["relay"], "responder": "alice", "response": "careful with that"},
        ],
        "requires_flag": None,
    },
    "#vip": {
        "topic": "vip only",
        "participants": [],
        "history": [],
        "triggers": [],
        "requires_flag": "vip_pass",
    },
}

_CONTACTS = {
    "alice": {
        "alias": "Alice",
        "status": "ONLINE",
        "key_fingerprint": "AA:BB:CC",
        "notes": "test",
    },
}

_DMS = {
    "alice": {
        "messages": [
            {"timestamp": "2026-01-01 00:00", "sender": "alice", "content": "dm message", "encrypted": True},
        ]
    }
}


def _ctx(with_heat: bool = False) -> CommandContext:
    comms = CommsSystem()
    comms.load_from_dicts(channels=_CHANNELS, contacts=_CONTACTS, dms=_DMS)

    heat = None
    if with_heat:
        class FakeHeat:
            def add_heat(self, v: float) -> None:
                pass
        heat = FakeHeat()

    return CommandContext(comms=comms, heat=heat)


def _run(name: str, args: list[str], ctx: CommandContext | None = None) -> str:
    if ctx is None:
        ctx = _ctx()
    handler = DEFAULT_REGISTRY.get(name)
    assert handler is not None, f"Command not registered: {name}"
    return handler(ctx, args)


def _ctx_no_comms() -> CommandContext:
    return CommandContext(comms=None)


# ---------------------------------------------------------------------------
# irc — no comms
# ---------------------------------------------------------------------------

class TestIrcNoComms:
    def test_returns_error_when_comms_none(self):
        out = _run("irc", [], _ctx_no_comms())
        assert "offline" in out.lower() or "comms" in out.lower()


# ---------------------------------------------------------------------------
# irc — no args (status)
# ---------------------------------------------------------------------------

class TestIrcStatus:
    def test_no_channels_joined(self):
        out = _run("irc", [])
        assert "Not in any" in out or "irc list" in out

    def test_shows_joined_channels(self):
        ctx = _ctx()
        ctx.comms.join_channel("#main")
        out = _run("irc", [], ctx)
        assert "#main" in out


# ---------------------------------------------------------------------------
# irc list
# ---------------------------------------------------------------------------

class TestIrcList:
    def test_shows_open_channels(self):
        out = _run("irc", ["list"])
        assert "#main" in out

    def test_hides_locked_channels(self):
        out = _run("irc", ["list"])
        assert "#vip" not in out

    def test_shows_locked_with_flag(self):
        ctx = _ctx()
        ctx.comms.set_flag("vip_pass")
        out = _run("irc", ["list"], ctx)
        assert "#vip" in out


# ---------------------------------------------------------------------------
# irc join
# ---------------------------------------------------------------------------

class TestIrcJoin:
    def test_join_open_channel(self):
        out = _run("irc", ["join", "#main"])
        assert "Joined" in out

    def test_join_missing_arg(self):
        out = _run("irc", ["join"])
        assert "Usage" in out

    def test_join_locked_channel(self):
        out = _run("irc", ["join", "#vip"])
        assert "access denied" in out

    def test_join_nonexistent(self):
        out = _run("irc", ["join", "#nope"])
        assert "No such" in out


# ---------------------------------------------------------------------------
# irc part / leave
# ---------------------------------------------------------------------------

class TestIrcPart:
    def test_part_after_join(self):
        ctx = _ctx()
        ctx.comms.join_channel("#main")
        out = _run("irc", ["part", "#main"], ctx)
        assert "Left" in out

    def test_leave_alias(self):
        ctx = _ctx()
        ctx.comms.join_channel("#main")
        out = _run("irc", ["leave", "#main"], ctx)
        assert "Left" in out

    def test_part_missing_arg(self):
        out = _run("irc", ["part"])
        assert "Usage" in out

    def test_part_not_joined(self):
        out = _run("irc", ["part", "#main"])
        assert "Not in" in out


# ---------------------------------------------------------------------------
# irc read
# ---------------------------------------------------------------------------

class TestIrcRead:
    def test_read_missing_arg(self):
        out = _run("irc", ["read"])
        assert "Usage" in out

    def test_read_not_joined(self):
        out = _run("irc", ["read", "#main"])
        assert "Not in" in out

    def test_read_after_join(self):
        ctx = _ctx()
        ctx.comms.join_channel("#main")
        out = _run("irc", ["read", "#main"], ctx)
        assert "alice" in out
        assert "hello world" in out

    def test_read_with_n_flag(self):
        ctx = _ctx()
        ctx.comms.join_channel("#main")
        out = _run("irc", ["read", "#main", "-n", "1"], ctx)
        assert "hello world" in out  # only 1 message in channel anyway


# ---------------------------------------------------------------------------
# irc post
# ---------------------------------------------------------------------------

class TestIrcPost:
    def test_post_missing_args(self):
        out = _run("irc", ["post"])
        assert "Usage" in out

    def test_post_missing_message(self):
        out = _run("irc", ["post", "#main"])
        assert "Usage" in out

    def test_post_not_joined(self):
        out = _run("irc", ["post", "#main", "hello"])
        assert "Not in" in out

    def test_post_success(self):
        ctx = _ctx()
        ctx.comms.join_channel("#main")
        out = _run("irc", ["post", "#main", "hello", "world"], ctx)
        assert "hello world" in out

    def test_post_triggers_npc(self):
        ctx = _ctx()
        ctx.comms.join_channel("#main")
        out = _run("irc", ["post", "#main", "what about relay"], ctx)
        assert "careful with that" in out

    def test_post_adds_heat(self):
        heats = []

        class TrackHeat:
            def add_heat(self, v: float) -> None:
                heats.append(v)

        ctx = _ctx()
        ctx.heat = TrackHeat()
        ctx.comms.join_channel("#main")
        _run("irc", ["post", "#main", "msg"], ctx)
        assert len(heats) == 1
        assert heats[0] > 0


# ---------------------------------------------------------------------------
# irc who
# ---------------------------------------------------------------------------

class TestIrcWho:
    def test_who_missing_arg(self):
        out = _run("irc", ["who"])
        assert "Usage" in out

    def test_who_not_joined(self):
        out = _run("irc", ["who", "#main"])
        assert "Not in" in out

    def test_who_after_join(self):
        ctx = _ctx()
        ctx.comms.join_channel("#main")
        out = _run("irc", ["who", "#main"], ctx)
        assert "alice" in out
        assert "bob" in out


# ---------------------------------------------------------------------------
# irc nick
# ---------------------------------------------------------------------------

class TestIrcNick:
    def test_nick_missing_arg(self):
        out = _run("irc", ["nick"])
        assert "Usage" in out

    def test_nick_change(self):
        ctx = _ctx()
        out = _run("irc", ["nick", "hax0r"], ctx)
        assert "hax0r" in out
        assert ctx.comms.player_handle == "hax0r"


# ---------------------------------------------------------------------------
# irc unknown subcommand
# ---------------------------------------------------------------------------

class TestIrcUnknown:
    def test_unknown_subcommand(self):
        out = _run("irc", ["badcmd"])
        assert "Unknown" in out or "irc" in out.lower()

    def test_help_subcommand(self):
        out = _run("irc", ["help"])
        assert "list" in out
        assert "join" in out


# ---------------------------------------------------------------------------
# msg — no comms
# ---------------------------------------------------------------------------

class TestMsgNoComms:
    def test_returns_error(self):
        out = _run("msg", [], _ctx_no_comms())
        assert "offline" in out.lower() or "comms" in out.lower()


# ---------------------------------------------------------------------------
# msg list
# ---------------------------------------------------------------------------

class TestMsgList:
    def test_no_args_lists_dms(self):
        out = _run("msg", [])
        assert "alice" in out

    def test_list_subcommand(self):
        out = _run("msg", ["list"])
        assert "alice" in out


# ---------------------------------------------------------------------------
# msg read
# ---------------------------------------------------------------------------

class TestMsgRead:
    def test_read_missing_arg(self):
        out = _run("msg", ["read"])
        assert "Usage" in out

    def test_read_existing_thread(self):
        out = _run("msg", ["read", "alice"])
        assert "alice" in out
        assert "dm message" in out

    def test_read_missing_thread(self):
        out = _run("msg", ["read", "nobody"])
        assert "No DM" in out


# ---------------------------------------------------------------------------
# msg send
# ---------------------------------------------------------------------------

class TestMsgSend:
    def test_send_missing_args(self):
        out = _run("msg", ["send"])
        assert "Usage" in out

    def test_send_missing_message(self):
        out = _run("msg", ["send", "alice"])
        assert "Usage" in out

    def test_send_to_known_contact(self):
        ctx = _ctx()
        out = _run("msg", ["send", "alice", "hello", "there"], ctx)
        assert "sent" in out.lower() or "Encrypted" in out

    def test_send_to_unknown(self):
        out = _run("msg", ["send", "ghost", "hi"])
        assert "Unknown contact" in out

    def test_send_adds_heat(self):
        heats = []

        class TrackHeat:
            def add_heat(self, v: float) -> None:
                heats.append(v)

        ctx = _ctx()
        ctx.heat = TrackHeat()
        _run("msg", ["send", "alice", "hello"], ctx)
        assert len(heats) == 1


# ---------------------------------------------------------------------------
# msg unknown
# ---------------------------------------------------------------------------

class TestMsgUnknown:
    def test_unknown_subcommand(self):
        out = _run("msg", ["badcmd"])
        assert "Unknown" in out or "msg" in out.lower()

    def test_help(self):
        out = _run("msg", ["help"])
        assert "list" in out
        assert "send" in out


# ---------------------------------------------------------------------------
# contacts — no comms
# ---------------------------------------------------------------------------

class TestContactsNoComms:
    def test_returns_error(self):
        out = _run("contacts", [], _ctx_no_comms())
        assert "offline" in out.lower() or "comms" in out.lower()


# ---------------------------------------------------------------------------
# contacts list
# ---------------------------------------------------------------------------

class TestContactsList:
    def test_no_args_lists_contacts(self):
        out = _run("contacts", [])
        assert "alice" in out

    def test_list_subcommand(self):
        out = _run("contacts", ["list"])
        assert "alice" in out


# ---------------------------------------------------------------------------
# contacts info
# ---------------------------------------------------------------------------

class TestContactsInfo:
    def test_info_missing_arg(self):
        out = _run("contacts", ["info"])
        assert "Usage" in out

    def test_info_known_contact(self):
        out = _run("contacts", ["info", "alice"])
        assert "Alice" in out
        assert "AA:BB:CC" in out

    def test_info_unknown(self):
        out = _run("contacts", ["info", "nobody"])
        assert "No contact" in out


# ---------------------------------------------------------------------------
# contacts add
# ---------------------------------------------------------------------------

class TestContactsAdd:
    def test_add_missing_arg(self):
        out = _run("contacts", ["add"])
        assert "Usage" in out

    def test_add_new(self):
        ctx = _ctx()
        out = _run("contacts", ["add", "new_person"], ctx)
        assert "new_person" in out
        assert "new_person" in ctx.comms.contacts

    def test_add_existing(self):
        out = _run("contacts", ["add", "alice"])
        assert "already exists" in out


# ---------------------------------------------------------------------------
# contacts unknown
# ---------------------------------------------------------------------------

class TestContactsUnknown:
    def test_unknown_subcommand(self):
        out = _run("contacts", ["xyz"])
        assert "Unknown" in out or "contacts" in out.lower()

    def test_help(self):
        out = _run("contacts", ["help"])
        assert "info" in out
        assert "add" in out
