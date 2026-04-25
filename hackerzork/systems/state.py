"""Game state machine — story flags, chapter tracking, event timeline.

GameState is the single source of truth for narrative progression. Commands
and systems write flags here; other systems read flags from here. The comms
channel lock system, meta engine, and save/load all depend on this.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Story event record
# ---------------------------------------------------------------------------

@dataclass
class StoryEvent:
    name: str
    timestamp_real: float
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Named story flags — used in comms channel locks, meta triggers, etc.
# ---------------------------------------------------------------------------

FLAG_SHADOW_UNLOCKED       = "shadow_unlocked"
FLAG_SURVEILLANCE_SEEN     = "surveillance_seen"
FLAG_RELAY_ALPHA_PWNED     = "relay_alpha_compromised"
FLAG_Z0RK7_CONTACT         = "z0rk7_contact_established"
FLAG_KIT_COMMITTED         = "kit_committed"
FLAG_EVIDENCE_DECRYPTED    = "evidence_decrypted"
FLAG_SKYNET_CORE_LOCATED   = "skynet_core_located"
FLAG_INTRO_COMPLETE        = "intro_complete"


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------

class GameState:
    """Tracks all story flags, the current chapter, and the event timeline."""

    def __init__(self, events: Any = None) -> None:
        self.flags: set[str] = set()
        self.chapter: int = 0
        self.timeline: list[StoryEvent] = []
        self._events = events

    # ------------------------------------------------------------------
    # Flag management
    # ------------------------------------------------------------------

    def set_flag(self, flag: str) -> None:
        if flag not in self.flags:
            self.flags.add(flag)
            if self._events:
                self._events.emit("flag_set", flag=flag)

    def has_flag(self, flag: str) -> bool:
        return flag in self.flags

    def clear_flag(self, flag: str) -> None:
        self.flags.discard(flag)

    def set_flags(self, *flags: str) -> None:
        for f in flags:
            self.set_flag(f)

    # ------------------------------------------------------------------
    # Story events / timeline
    # ------------------------------------------------------------------

    def fire_event(self, event_name: str, **metadata: Any) -> None:
        self.timeline.append(
            StoryEvent(
                name=event_name,
                timestamp_real=time.time(),
                metadata=metadata,
            )
        )
        if self._events:
            self._events.emit("story_event", event_name=event_name, **metadata)

    def has_event(self, event_name: str) -> bool:
        return any(e.name == event_name for e in self.timeline)

    def last_event(self, event_name: str) -> StoryEvent | None:
        for ev in reversed(self.timeline):
            if ev.name == event_name:
                return ev
        return None

    def events_named(self, event_name: str) -> list[StoryEvent]:
        return [e for e in self.timeline if e.name == event_name]

    # ------------------------------------------------------------------
    # Chapter advancement
    # ------------------------------------------------------------------

    def advance_chapter(self) -> int:
        self.chapter += 1
        self.fire_event(f"chapter_{self.chapter}_start")
        return self.chapter

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "flags": sorted(self.flags),
            "chapter": self.chapter,
            "timeline": [
                {
                    "name": e.name,
                    "timestamp_real": e.timestamp_real,
                    "metadata": e.metadata,
                }
                for e in self.timeline
            ],
        }

    def load_state(self, state: dict) -> None:
        self.flags = set(state.get("flags", []))
        self.chapter = int(state.get("chapter", 0))
        self.timeline = [
            StoryEvent(
                name=e["name"],
                timestamp_real=float(e.get("timestamp_real", 0.0)),
                metadata=dict(e.get("metadata", {})),
            )
            for e in state.get("timeline", [])
        ]

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def summary(self) -> str:
        lines = [
            f"Chapter:   {self.chapter}",
            f"Flags:     {len(self.flags)} set",
            f"Events:    {len(self.timeline)} fired",
        ]
        if self.flags:
            lines.append("  " + ", ".join(sorted(self.flags)))
        return "\n".join(lines)
