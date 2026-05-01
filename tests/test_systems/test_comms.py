"""Tests for hackerzork/systems/comms.py."""
from __future__ import annotations

import pytest

from hackerzork.systems.comms import (
    CommsSystem,
    Contact,
    DMMessage,
    DMThread,
    IRCChannel,
    IRCMessage,
    NpcTrigger,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHANNELS = {
    "#test": {
        "topic": "test channel",
        "participants": ["alice", "bob"],
        "history": [
            {"timestamp": "2026-01-01 00:00", "sender": "alice", "content": "hello"},
            {"timestamp": "2026-01-01 00:01", "sender": "bob", "content": "world", "is_system": False},
        ],
        "triggers": [
            {"keywords": ["trigger", "fire"], "responder": "alice", "response": "triggered!"},
        ],
        "requires_flag": None,
    },
    "#locked": {
        "topic": "secret channel",
        "participants": ["z0rk_7"],
        "history": [],
        "triggers": [],
        "requires_flag": "secret_flag",
    },
}

_CONTACTS = {
    "alice": {
        "alias": "Alice",
        "status": "ONLINE",
        "key_fingerprint": "AA:BB:CC:DD",
        "notes": "test contact",
    },
    "bob": {
        "alias": "Bob",
        "status": "AWAY",
        "key_fingerprint": "EE:FF:00:11",
        "notes": "",
    },
}

_DMS = {
    "alice": {
        "messages": [
            {"timestamp": "2026-01-01 00:00", "sender": "alice", "content": "hey there", "encrypted": True},
        ]
    }
}


def _comms() -> CommsSystem:
    c = CommsSystem()
    c.load_from_dicts(channels=_CHANNELS, contacts=_CONTACTS, dms=_DMS)
    return c


# ---------------------------------------------------------------------------
# Dataclass integrity
# ---------------------------------------------------------------------------

class TestDataClasses:
    def test_irc_message_defaults(self):
        m = IRCMessage(timestamp="now", sender="x", content="hi")
        assert m.is_system is False

    def test_npc_trigger_fields(self):
        t = NpcTrigger(keywords=["a", "b"], responder="bot", response="yes")
        assert "a" in t.keywords

    def test_contact_fields(self):
        c = Contact(handle="x", alias="X", status="ONLINE", key_fingerprint="fp")
        assert c.notes == ""

    def test_dm_message_default_encrypted(self):
        m = DMMessage(timestamp="now", sender="x", content="msg")
        assert m.encrypted is True

    def test_dm_thread_defaults(self):
        t = DMThread(contact_handle="x")
        assert t.messages == []
        assert t.unread == 0


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

class TestLoading:
    def test_channels_loaded(self):
        c = _comms()
        assert "#test" in c.channels
        assert "#locked" in c.channels

    def test_channel_history_parsed(self):
        c = _comms()
        ch = c.channels["#test"]
        assert len(ch.history) == 2
        assert ch.history[0].sender == "alice"

    def test_channel_triggers_parsed(self):
        c = _comms()
        ch = c.channels["#test"]
        assert len(ch.triggers) == 1
        assert ch.triggers[0].responder == "alice"

    def test_contacts_loaded(self):
        c = _comms()
        assert "alice" in c.contacts
        assert c.contacts["alice"].status == "ONLINE"

    def test_dms_loaded(self):
        c = _comms()
        assert "alice" in c.dm_threads
        assert len(c.dm_threads["alice"].messages) == 1

    def test_dm_unread_count_set_on_load(self):
        c = _comms()
        assert c.dm_threads["alice"].unread == 1

    def test_empty_dicts_no_crash(self):
        c = CommsSystem()
        c.load_from_dicts(channels={}, contacts={}, dms={})


# ---------------------------------------------------------------------------
# Story flags
# ---------------------------------------------------------------------------

class TestStoryFlags:
    def test_no_flag_locked_channel_inaccessible(self):
        c = _comms()
        assert not c._channel_accessible(c.channels["#locked"])

    def test_set_flag_unlocks_channel(self):
        c = _comms()
        c.set_flag("secret_flag")
        assert c._channel_accessible(c.channels["#locked"])

    def test_has_flag(self):
        c = _comms()
        c.set_flag("my_flag")
        assert c.has_flag("my_flag")
        assert not c.has_flag("other_flag")

    def test_open_channel_always_accessible(self):
        c = _comms()
        assert c._channel_accessible(c.channels["#test"])


# ---------------------------------------------------------------------------
# Channel operations
# ---------------------------------------------------------------------------

class TestChannelList:
    def test_list_shows_open_channels(self):
        c = _comms()
        out = c.list_channels()
        assert "#test" in out

    def test_list_shows_locked_channels_as_locked(self):
        c = _comms()
        out = c.list_channels()
        # Locked channels are now shown with [LOCKED] marker, not fully hidden
        assert "[LOCKED]" in out
        assert "#locked" in out

    def test_list_shows_locked_after_flag(self):
        c = _comms()
        c.set_flag("secret_flag")
        out = c.list_channels()
        # Once unlocked, channel appears in the accessible section (no LOCKED marker)
        assert "#locked" in out

    def test_list_shows_locked_marker_when_all_locked(self):
        c = CommsSystem()
        c.load_from_dicts(channels={"#x": {"topic": "t", "participants": [], "history": [], "triggers": [], "requires_flag": "nope"}})
        out = c.list_channels()
        # Channel appears as locked, not simply hidden
        assert "[LOCKED]" in out
        assert "#x" in out


class TestJoinLeave:
    def test_join_open_channel(self):
        c = _comms()
        out = c.join_channel("#test")
        assert "Joined" in out
        assert c.channels["#test"].joined is True

    def test_join_already_joined(self):
        c = _comms()
        c.join_channel("#test")
        out = c.join_channel("#test")
        assert "Already" in out

    def test_join_nonexistent(self):
        c = _comms()
        out = c.join_channel("#missing")
        assert "No such" in out

    def test_join_dead_channel_returns_narrative(self):
        c = _comms()
        out = c.join_channel("#darknet-relay-3")
        assert "not found" in out.lower() or "went dark" in out.lower() or "dark" in out.lower()
        assert "ghost_runner" in out or "burned" in out.lower()

    def test_join_dead_ghost_ops(self):
        c = _comms()
        out = c.join_channel("#ghost-ops")
        assert "burned" in out.lower() or "decommissioned" in out.lower()

    def test_join_locked_without_flag(self):
        c = _comms()
        out = c.join_channel("#locked")
        assert "access denied" in out
        assert c.channels["#locked"].joined is False

    def test_join_locked_with_flag(self):
        c = _comms()
        c.set_flag("secret_flag")
        out = c.join_channel("#locked")
        assert "Joined" in out

    def test_leave_channel(self):
        c = _comms()
        c.join_channel("#test")
        out = c.leave_channel("#test")
        assert "Left" in out
        assert c.channels["#test"].joined is False

    def test_leave_not_joined(self):
        c = _comms()
        out = c.leave_channel("#test")
        assert "Not in" in out

    def test_leave_nonexistent(self):
        c = _comms()
        out = c.leave_channel("#ghost")
        assert "No such" in out


class TestReadChannel:
    def test_read_requires_join(self):
        c = _comms()
        out = c.read_channel("#test")
        assert "Not in" in out

    def test_read_after_join(self):
        c = _comms()
        c.join_channel("#test")
        out = c.read_channel("#test")
        assert "alice" in out
        assert "hello" in out

    def test_read_clears_unread(self):
        c = _comms()
        c.join_channel("#test")
        c.channels["#test"].unread = 5
        c.read_channel("#test")
        assert c.channels["#test"].unread == 0

    def test_read_limit(self):
        c = _comms()
        c.join_channel("#test")
        out = c.read_channel("#test", limit=1)
        # Only last 1 message shown
        assert "world" in out

    def test_read_nonexistent(self):
        c = _comms()
        out = c.read_channel("#nope")
        assert "No such" in out

    def test_read_empty_channel(self):
        c = CommsSystem()
        c.load_from_dicts(channels={"#empty": {"topic": "t", "participants": [], "history": [], "triggers": [], "requires_flag": None}})
        c.join_channel("#empty")
        out = c.read_channel("#empty")
        assert "no messages" in out


class TestPostMessage:
    def test_post_requires_join(self):
        c = _comms()
        echo, reply = c.post_message("#test", "hi")
        assert "Not in" in echo
        assert reply is None

    def test_post_adds_to_history(self):
        c = _comms()
        c.join_channel("#test")
        before = len(c.channels["#test"].history)
        c.post_message("#test", "new message")
        assert len(c.channels["#test"].history) == before + 1

    def test_post_echo_contains_message(self):
        c = _comms()
        c.join_channel("#test")
        echo, _ = c.post_message("#test", "hello from me")
        assert "hello from me" in echo

    def test_post_trigger_fires(self):
        c = _comms()
        c.join_channel("#test")
        _, reply = c.post_message("#test", "this should trigger alice")
        assert reply is not None
        assert "triggered!" in reply

    def test_post_no_trigger_when_no_match(self):
        c = _comms()
        c.join_channel("#test")
        _, reply = c.post_message("#test", "nothing relevant here xyz123")
        assert reply is None

    def test_post_nonexistent_channel(self):
        c = _comms()
        echo, reply = c.post_message("#nope", "hi")
        assert "No such" in echo

    def test_trigger_response_added_to_history(self):
        c = _comms()
        c.join_channel("#test")
        before = len(c.channels["#test"].history)
        c.post_message("#test", "trigger this please")
        assert len(c.channels["#test"].history) == before + 2  # post + reply


class TestWho:
    def test_who_requires_join(self):
        c = _comms()
        out = c.who("#test")
        assert "Not in" in out

    def test_who_lists_participants(self):
        c = _comms()
        c.join_channel("#test")
        out = c.who("#test")
        assert "alice" in out
        assert "bob" in out

    def test_who_nonexistent(self):
        c = _comms()
        out = c.who("#nope")
        assert "No such" in out


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

class TestContacts:
    def test_list_contacts(self):
        c = _comms()
        out = c.list_contacts()
        assert "alice" in out
        assert "bob" in out

    def test_list_shows_status(self):
        c = _comms()
        out = c.list_contacts()
        assert "ONLINE" in out
        assert "AWAY" in out

    def test_contact_info(self):
        c = _comms()
        out = c.contact_info("alice")
        assert "Alice" in out
        assert "AA:BB:CC:DD" in out

    def test_contact_info_missing(self):
        c = _comms()
        out = c.contact_info("nobody")
        assert "No contact" in out

    def test_add_new_contact(self):
        c = _comms()
        out = c.add_contact("new_person")
        assert "new_person" in c.contacts
        assert "pending" in c.contacts["new_person"].key_fingerprint

    def test_add_existing_contact(self):
        c = _comms()
        out = c.add_contact("alice")
        assert "already exists" in out

    def test_list_empty_contacts(self):
        c = CommsSystem()
        out = c.list_contacts()
        assert "No contacts" in out


# ---------------------------------------------------------------------------
# DMs
# ---------------------------------------------------------------------------

class TestDMs:
    def test_list_dms(self):
        c = _comms()
        out = c.list_dms()
        assert "alice" in out

    def test_list_dms_empty(self):
        c = CommsSystem()
        out = c.list_dms()
        assert "No messages" in out

    def test_read_dm(self):
        c = _comms()
        out = c.read_dm("alice")
        assert "alice" in out
        assert "hey there" in out

    def test_read_dm_missing(self):
        c = _comms()
        out = c.read_dm("nobody")
        assert "No DM" in out

    def test_read_dm_clears_unread(self):
        c = _comms()
        assert c.dm_threads["alice"].unread == 1
        c.read_dm("alice")
        assert c.dm_threads["alice"].unread == 0

    def test_read_dm_shows_encryption_preamble(self):
        c = _comms()
        out = c.read_dm("alice")
        assert "ENCRYPTED" in out or "decrypting" in out

    def test_send_dm_known_contact(self):
        c = _comms()
        out = c.send_dm("alice", "test message")
        assert "sent" in out.lower() or "Encrypted" in out
        assert len(c.dm_threads["alice"].messages) == 2

    def test_send_dm_unknown_contact(self):
        c = _comms()
        out = c.send_dm("nobody", "hi")
        assert "Unknown contact" in out

    def test_send_dm_creates_thread(self):
        c = _comms()
        c.send_dm("bob", "first message")
        assert "bob" in c.dm_threads

    def test_sent_dm_marked_as_you(self):
        c = _comms()
        c.send_dm("alice", "from me")
        sent = c.dm_threads["alice"].messages[-1]
        assert sent.sender == "you"
        assert sent.encrypted is True


# ---------------------------------------------------------------------------
# Nick
# ---------------------------------------------------------------------------

class TestNick:
    def test_set_nick(self):
        c = _comms()
        c.set_nick("hax0r")
        assert c.player_handle == "hax0r"

    def test_set_nick_updates_joined_channel(self):
        c = _comms()
        c.join_channel("#test")
        c.set_nick("new_handle")
        ch = c.channels["#test"]
        assert "new_handle" in ch.participants
        assert "anon" not in ch.participants

    def test_set_nick_returns_confirmation(self):
        c = _comms()
        out = c.set_nick("stealth_1")
        assert "stealth_1" in out


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_join_emits_event(self):
        received = []

        class MockEvents:
            def emit(self, name, **kwargs):
                received.append((name, kwargs))

        c = CommsSystem(events=MockEvents())
        c.load_from_dicts(channels=_CHANNELS)
        c.join_channel("#test")
        assert any(e[0] == "irc_joined" for e in received)

    def test_post_emits_event(self):
        received = []

        class MockEvents:
            def emit(self, name, **kwargs):
                received.append((name, kwargs))

        c = CommsSystem(events=MockEvents())
        c.load_from_dicts(channels=_CHANNELS)
        c.join_channel("#test")
        c.post_message("#test", "hello")
        assert any(e[0] == "irc_message_posted" for e in received)

    def test_send_dm_emits_event(self):
        received = []

        class MockEvents:
            def emit(self, name, **kwargs):
                received.append((name, kwargs))

        c = CommsSystem(events=MockEvents())
        c.load_from_dicts(contacts=_CONTACTS)
        c.send_dm("alice", "test")
        assert any(e[0] == "dm_sent" for e in received)
