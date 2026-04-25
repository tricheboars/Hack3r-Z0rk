"""IRC-style communications system — channels, encrypted DMs, contacts.

CommsSystem manages in-world chat: pre-seeded channel history, NPC trigger
responses, encrypted DM threads, and a contact list. All content loads from
YAML; no game content is hardcoded here.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IRCMessage:
    timestamp: str
    sender: str
    content: str
    is_system: bool = False


@dataclass
class NpcTrigger:
    keywords: list[str]
    responder: str
    response: str


@dataclass
class IRCChannel:
    name: str
    topic: str
    participants: list[str]
    history: list[IRCMessage]
    triggers: list[NpcTrigger]
    requires_flag: str | None = None
    joined: bool = False
    unread: int = 0


@dataclass
class Contact:
    handle: str
    alias: str
    status: str       # ONLINE | AWAY | OFFLINE | UNKNOWN | BURNED
    key_fingerprint: str
    notes: str = ""


@dataclass
class DMMessage:
    timestamp: str
    sender: str       # handle or "you"
    content: str
    encrypted: bool = True


@dataclass
class DMThread:
    contact_handle: str
    messages: list[DMMessage] = field(default_factory=list)
    unread: int = 0


# ---------------------------------------------------------------------------
# CommsSystem
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data" / "dialogue"

_STATUS_COLOR = {
    "ONLINE":  "green",
    "AWAY":    "yellow",
    "OFFLINE": "dim",
    "UNKNOWN": "dim",
    "BURNED":  "red",
}


class CommsSystem:
    """Manages IRC channels, contacts, and encrypted DMs."""

    def __init__(self, events: Any = None, data_dir: Path | None = None) -> None:
        self._events = events
        self._data_dir = data_dir or _DATA_DIR

        self.channels: dict[str, IRCChannel] = {}
        self.contacts: dict[str, Contact] = {}
        self.dm_threads: dict[str, DMThread] = {}
        self.player_handle: str = "anon"
        self._story_flags: set[str] = set()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        self._load_channels(self._data_dir / "channels.yaml")
        self._load_contacts(self._data_dir / "contacts.yaml")
        self._load_dms(self._data_dir / "dms.yaml")

    def load_from_dicts(
        self,
        channels: dict | None = None,
        contacts: dict | None = None,
        dms: dict | None = None,
    ) -> None:
        """Load from in-memory dicts — used in tests."""
        if channels:
            self._parse_channels(channels)
        if contacts:
            self._parse_contacts(contacts)
        if dms:
            self._parse_dms(dms)

    def _load_channels(self, path: Path) -> None:
        if not path.exists():
            return
        data = yaml.safe_load(path.read_text()) or {}
        self._parse_channels(data)

    def _parse_channels(self, data: dict) -> None:
        for name, raw in data.items():
            history = [
                IRCMessage(
                    timestamp=str(m["timestamp"]),
                    sender=str(m["sender"]),
                    content=str(m["content"]),
                    is_system=bool(m.get("is_system", False)),
                )
                for m in (raw.get("history") or [])
            ]
            triggers = [
                NpcTrigger(
                    keywords=[str(k).lower() for k in t.get("keywords", [])],
                    responder=str(t["responder"]),
                    response=str(t["response"]),
                )
                for t in (raw.get("triggers") or [])
            ]
            self.channels[name] = IRCChannel(
                name=name,
                topic=str(raw.get("topic", "")),
                participants=list(raw.get("participants") or []),
                history=history,
                triggers=triggers,
                requires_flag=raw.get("requires_flag"),
            )

    def _load_contacts(self, path: Path) -> None:
        if not path.exists():
            return
        data = yaml.safe_load(path.read_text()) or {}
        self._parse_contacts(data)

    def _parse_contacts(self, data: dict) -> None:
        for handle, raw in data.items():
            self.contacts[handle] = Contact(
                handle=handle,
                alias=str(raw.get("alias", handle)),
                status=str(raw.get("status", "UNKNOWN")),
                key_fingerprint=str(raw.get("key_fingerprint", "")),
                notes=str(raw.get("notes", "")),
            )

    def _load_dms(self, path: Path) -> None:
        if not path.exists():
            return
        data = yaml.safe_load(path.read_text()) or {}
        self._parse_dms(data)

    def _parse_dms(self, data: dict) -> None:
        for handle, raw in data.items():
            messages = [
                DMMessage(
                    timestamp=str(m["timestamp"]),
                    sender=str(m["sender"]),
                    content=str(m["content"]),
                    encrypted=bool(m.get("encrypted", True)),
                )
                for m in (raw.get("messages") or [])
            ]
            thread = DMThread(
                contact_handle=handle,
                messages=messages,
                unread=len(messages),
            )
            self.dm_threads[handle] = thread

    # ------------------------------------------------------------------
    # Story flags
    # ------------------------------------------------------------------

    def set_flag(self, flag: str) -> None:
        self._story_flags.add(flag)

    def has_flag(self, flag: str) -> bool:
        return flag in self._story_flags

    def _channel_accessible(self, ch: IRCChannel) -> bool:
        if ch.requires_flag is None:
            return True
        return ch.requires_flag in self._story_flags

    # ------------------------------------------------------------------
    # Channel operations
    # ------------------------------------------------------------------

    def list_channels(self) -> str:
        if not self.channels:
            return "No channels available."
        lines = ["Available channels:", ""]
        for name, ch in sorted(self.channels.items()):
            if not self._channel_accessible(ch):
                continue
            joined = "[J]" if ch.joined else "   "
            unread = f" [{ch.unread} unread]" if ch.unread else ""
            parts = len(ch.participants)
            lines.append(f"  {joined} {name:<20} {parts:>2} users  {ch.topic}{unread}")
        return "\n".join(lines)

    def join_channel(self, name: str) -> str:
        ch = self.channels.get(name)
        if ch is None:
            return f"No such channel: {name}"
        if not self._channel_accessible(ch):
            return f"[access denied] {name} — required credentials not present"
        if ch.joined:
            return f"Already in {name}"
        ch.joined = True
        if not name in ch.participants:
            ch.participants.append(self.player_handle)
        if self._events:
            self._events.emit("irc_joined", channel=name)
        return f"Joined {name}  —  {ch.topic}"

    def leave_channel(self, name: str) -> str:
        ch = self.channels.get(name)
        if ch is None:
            return f"No such channel: {name}"
        if not ch.joined:
            return f"Not in {name}"
        ch.joined = False
        if self.player_handle in ch.participants:
            ch.participants.remove(self.player_handle)
        return f"Left {name}"

    def read_channel(self, name: str, limit: int = 20) -> str:
        ch = self.channels.get(name)
        if ch is None:
            return f"No such channel: {name}"
        if not ch.joined:
            return f"Not in {name} — use: irc join {name}"
        if not self._channel_accessible(ch):
            return f"[access denied]"

        ch.unread = 0
        messages = ch.history[-limit:]
        if not messages:
            return f"{name}: no messages."

        lines = [f"[{name}]  topic: {ch.topic}", ""]
        for msg in messages:
            if msg.is_system:
                lines.append(f"  [dim]{msg.timestamp}  {msg.content}[/dim]")
            else:
                lines.append(f"  {msg.timestamp}  <{msg.sender}> {msg.content}")
        return "\n".join(lines)

    def post_message(self, name: str, message: str) -> tuple[str, str | None]:
        """Post to a channel. Returns (echo, npc_response | None)."""
        ch = self.channels.get(name)
        if ch is None:
            return f"No such channel: {name}", None
        if not ch.joined:
            return f"Not in {name} — use: irc join {name}", None
        if not self._channel_accessible(ch):
            return "[access denied]", None

        ts = "2026-04-24 00:00"
        msg = IRCMessage(timestamp=ts, sender=self.player_handle, content=message)
        ch.history.append(msg)

        if self._events:
            self._events.emit("irc_message_posted", channel=name, message=message)

        echo = f"<{self.player_handle}> {message}"

        npc_reply = self._match_trigger(ch, message)
        if npc_reply:
            npc_msg, npc_sender = npc_reply
            ch.history.append(
                IRCMessage(timestamp=ts, sender=npc_sender, content=npc_msg)
            )
            return echo, f"<{npc_sender}> {npc_msg}"

        return echo, None

    def _match_trigger(
        self, ch: IRCChannel, message: str
    ) -> tuple[str, str] | None:
        lowered = message.lower()
        matched = [t for t in ch.triggers if any(k in lowered for k in t.keywords)]
        if not matched:
            return None
        trigger = random.choice(matched)
        return trigger.response, trigger.responder

    def who(self, name: str) -> str:
        ch = self.channels.get(name)
        if ch is None:
            return f"No such channel: {name}"
        if not ch.joined:
            return f"Not in {name}"
        lines = [f"Users in {name}:"]
        for p in sorted(ch.participants):
            contact = self.contacts.get(p)
            status = contact.status if contact else "UNKNOWN"
            color = _STATUS_COLOR.get(status, "dim")
            lines.append(f"  [{color}]{p:<20} {status}[/{color}]")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Contact operations
    # ------------------------------------------------------------------

    def list_contacts(self) -> str:
        if not self.contacts:
            return "No contacts."
        lines = ["Contacts:", ""]
        for handle, c in sorted(self.contacts.items()):
            color = _STATUS_COLOR.get(c.status, "dim")
            lines.append(
                f"  [{color}]{handle:<20} {c.status:<8}[/{color}]  {c.alias}"
            )
        return "\n".join(lines)

    def contact_info(self, handle: str) -> str:
        c = self.contacts.get(handle)
        if c is None:
            return f"No contact: {handle}"
        color = _STATUS_COLOR.get(c.status, "dim")
        lines = [
            f"Handle:      {c.handle}",
            f"Alias:       {c.alias}",
            f"Status:      [{color}]{c.status}[/{color}]",
            f"Key:         {c.key_fingerprint}",
        ]
        if c.notes:
            lines.append(f"Notes:       {c.notes}")
        return "\n".join(lines)

    def add_contact(self, handle: str) -> str:
        if handle in self.contacts:
            return f"Contact already exists: {handle}"
        self.contacts[handle] = Contact(
            handle=handle,
            alias=handle,
            status="UNKNOWN",
            key_fingerprint="(pending pubkey exchange)",
        )
        return f"Contact request sent to {handle}. Awaiting pubkey exchange."

    # ------------------------------------------------------------------
    # DM operations
    # ------------------------------------------------------------------

    def list_dms(self) -> str:
        if not self.dm_threads:
            return "No messages."
        lines = ["Messages:", ""]
        for handle, thread in sorted(self.dm_threads.items()):
            unread = f" [{thread.unread} unread]" if thread.unread else ""
            last = thread.messages[-1] if thread.messages else None
            preview = (last.content[:40] + "...") if last else "(empty)"
            lines.append(f"  {handle:<20}{unread}")
            lines.append(f"    {preview}")
        return "\n".join(lines)

    def read_dm(self, handle: str) -> str:
        thread = self.dm_threads.get(handle)
        if thread is None:
            return f"No DM thread with {handle}"
        contact = self.contacts.get(handle)
        key = contact.key_fingerprint if contact else "(unknown key)"
        thread.unread = 0

        lines = [f"[DM: {handle}]  key: {key}", ""]
        for msg in thread.messages:
            prefix = f"[dim]{msg.timestamp}[/dim]"
            if msg.encrypted:
                lines.append(f"  {prefix}  [dim yellow][ENCRYPTED — decrypting with {handle}.pub][/dim yellow]")
            sender_label = "you" if msg.sender == "you" else f"<{msg.sender}>"
            lines.append(f"  {prefix}  {sender_label}: {msg.content}")
        return "\n".join(lines)

    def send_dm(self, handle: str, message: str) -> str:
        if handle not in self.contacts:
            return f"Unknown contact: {handle}. Use: contacts add {handle}"
        if handle not in self.dm_threads:
            self.dm_threads[handle] = DMThread(contact_handle=handle)

        thread = self.dm_threads[handle]
        thread.messages.append(
            DMMessage(
                timestamp="2026-04-24 00:00",
                sender="you",
                content=message,
                encrypted=True,
            )
        )
        if self._events:
            self._events.emit("dm_sent", recipient=handle)
        return f"[Encrypted message sent to {handle}]"

    # ------------------------------------------------------------------
    # Nick
    # ------------------------------------------------------------------

    def set_nick(self, nick: str) -> str:
        old = self.player_handle
        self.player_handle = nick
        # Update participant lists in joined channels
        for ch in self.channels.values():
            if ch.joined and old in ch.participants:
                ch.participants.remove(old)
                ch.participants.append(nick)
        return f"Handle set to: {nick}"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "player_handle": self.player_handle,
            "story_flags": sorted(self._story_flags),
            "channels": {
                name: {
                    "joined": ch.joined,
                    "unread": ch.unread,
                    "player_messages": [
                        {
                            "timestamp": m.timestamp,
                            "sender": m.sender,
                            "content": m.content,
                            "is_system": m.is_system,
                        }
                        for m in ch.history
                        if m.sender == self.player_handle
                    ],
                }
                for name, ch in self.channels.items()
            },
            "dm_threads": {
                handle: {
                    "unread": t.unread,
                    "sent_messages": [
                        {
                            "timestamp": m.timestamp,
                            "content": m.content,
                            "encrypted": m.encrypted,
                        }
                        for m in t.messages
                        if m.sender == "you"
                    ],
                }
                for handle, t in self.dm_threads.items()
            },
            "extra_contacts": {
                handle: {
                    "alias": c.alias,
                    "status": c.status,
                    "key_fingerprint": c.key_fingerprint,
                    "notes": c.notes,
                }
                for handle, c in self.contacts.items()
            },
        }

    def load_state(self, state: dict) -> None:
        """Merge saved dynamic state on top of freshly YAML-loaded state."""
        self.player_handle = state.get("player_handle", "anon")
        for flag in state.get("story_flags", []):
            self._story_flags.add(flag)

        for name, cstate in state.get("channels", {}).items():
            ch = self.channels.get(name)
            if ch is None:
                continue
            ch.joined = cstate.get("joined", False)
            ch.unread = cstate.get("unread", 0)
            # Re-add player messages not already in history
            existing = {m.content for m in ch.history}
            for m in cstate.get("player_messages", []):
                if m["content"] not in existing:
                    ch.history.append(
                        IRCMessage(
                            timestamp=m["timestamp"],
                            sender=m["sender"],
                            content=m["content"],
                            is_system=m.get("is_system", False),
                        )
                    )

        for handle, tstate in state.get("dm_threads", {}).items():
            if handle not in self.dm_threads:
                self.dm_threads[handle] = DMThread(contact_handle=handle)
            thread = self.dm_threads[handle]
            thread.unread = tstate.get("unread", thread.unread)
            existing = {m.content for m in thread.messages if m.sender == "you"}
            for m in tstate.get("sent_messages", []):
                if m["content"] not in existing:
                    thread.messages.append(
                        DMMessage(
                            timestamp=m["timestamp"],
                            sender="you",
                            content=m["content"],
                            encrypted=m.get("encrypted", True),
                        )
                    )

        for handle, c in state.get("extra_contacts", {}).items():
            if handle not in self.contacts:
                self.contacts[handle] = Contact(
                    handle=handle,
                    alias=c.get("alias", handle),
                    status=c.get("status", "UNKNOWN"),
                    key_fingerprint=c.get("key_fingerprint", ""),
                    notes=c.get("notes", ""),
                )
