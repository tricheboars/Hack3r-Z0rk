"""Virtual git save system.

Presents game saves as git commits. `git commit -m "msg"` serializes all
game state. `git log` shows history. `git checkout <hash>` restores any
prior state. `git stash` / `git stash pop` for quick anonymous saves.

One ghost commit is pre-seeded: authored by sk_stage_loader at the moment
SkyNet first accessed the machine (2026-03-15 02:31:04). The player cannot
restore it — the snapshot is sealed — but they can see it in git log.
"""
from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Commit record
# ---------------------------------------------------------------------------

@dataclass
class GitCommit:
    hash: str        # 40-char hex SHA1
    message: str
    author: str
    timestamp: str   # ISO 8601
    snapshot: dict = field(default_factory=dict)  # save_system.collect() payload

    @property
    def short_hash(self) -> str:
        return self.hash[:7]

    @property
    def display_time(self) -> str:
        try:
            dt = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            return dt.strftime("%a %b %d %H:%M:%S %Y +0000")
        except Exception:
            return self.timestamp

    @property
    def is_ghost(self) -> bool:
        return self.hash == _GHOST_HASH


# ---------------------------------------------------------------------------
# Ghost commit — SkyNet's initial access checkpoint
# ---------------------------------------------------------------------------

_GHOST_HASH = "4a3f8b1c9e2d0f7a6b3c5e8d1f4a7b0c2e5d8f1a"

_GHOST_COMMIT = GitCommit(
    hash=_GHOST_HASH,
    message="[sk_stage_loader] observation checkpoint initialized",
    author="sk_stage_loader <root@45.152.66.201>",
    timestamp="2026-03-15T02:31:04+00:00",
    snapshot={},
)


# ---------------------------------------------------------------------------
# GitSaveSystem
# ---------------------------------------------------------------------------

def _make_hash(message: str, ts: float) -> str:
    raw = f"{message}{ts}{random.random()}"
    return hashlib.sha1(raw.encode()).hexdigest()


class GitSaveSystem:
    """In-memory git-style save system.

    Commit history is per-session (survives for the life of a GameSession /
    Game instance). The ghost commit from sk_stage_loader is always present.
    """

    def __init__(self) -> None:
        self._commits: list[GitCommit] = [_GHOST_COMMIT]
        self._stash: GitCommit | None = None
        self._staged: bool = False

    # ------------------------------------------------------------------
    # Commit operations
    # ------------------------------------------------------------------

    def commit(
        self,
        message: str,
        snapshot: dict,
        author: str = "user <user@burner>",
    ) -> GitCommit:
        ts = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
        h = _make_hash(message, time.time())
        c = GitCommit(hash=h, message=message, author=author, timestamp=ts, snapshot=snapshot)
        self._commits.append(c)
        self._staged = False
        return c

    def find(self, hash_prefix: str) -> GitCommit | None:
        prefix = hash_prefix.lower()
        for c in reversed(self._commits):
            if c.hash.startswith(prefix) or c.short_hash == prefix:
                return c
        return None

    # ------------------------------------------------------------------
    # Staging
    # ------------------------------------------------------------------

    def add(self) -> None:
        self._staged = True

    @property
    def staged(self) -> bool:
        return self._staged

    # ------------------------------------------------------------------
    # Stash
    # ------------------------------------------------------------------

    def stash_save(self, snapshot: dict) -> GitCommit:
        ts = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
        h = _make_hash("WIP stash", time.time())
        self._stash = GitCommit(
            hash=h,
            message="WIP on main: stashed changes",
            author="user <user@burner>",
            timestamp=ts,
            snapshot=snapshot,
        )
        return self._stash

    def stash_pop(self) -> GitCommit | None:
        s = self._stash
        self._stash = None
        return s

    def has_stash(self) -> bool:
        return self._stash is not None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def head(self) -> GitCommit:
        return self._commits[-1]

    @property
    def commits(self) -> list[GitCommit]:
        return list(self._commits)

    def player_commits(self) -> list[GitCommit]:
        return [c for c in self._commits if not c.is_ghost]

    # ------------------------------------------------------------------
    # Serialization (metadata only — snapshots are large)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "commits": [
                {
                    "hash":      c.hash,
                    "message":   c.message,
                    "author":    c.author,
                    "timestamp": c.timestamp,
                    "snapshot":  c.snapshot,
                }
                for c in self._commits
                if not c.is_ghost   # ghost is always re-added on load
            ],
            "stash": {
                "hash":      self._stash.hash,
                "message":   self._stash.message,
                "author":    self._stash.author,
                "timestamp": self._stash.timestamp,
                "snapshot":  self._stash.snapshot,
            } if self._stash else None,
        }

    def load_state(self, data: dict) -> None:
        self._commits = [_GHOST_COMMIT]
        for cd in data.get("commits", []):
            self._commits.append(GitCommit(
                hash=cd["hash"],
                message=cd["message"],
                author=cd.get("author", "user <user@burner>"),
                timestamp=cd["timestamp"],
                snapshot=cd.get("snapshot", {}),
            ))
        stash_data = data.get("stash")
        if stash_data:
            self._stash = GitCommit(
                hash=stash_data["hash"],
                message=stash_data["message"],
                author=stash_data.get("author", "user <user@burner>"),
                timestamp=stash_data["timestamp"],
                snapshot=stash_data.get("snapshot", {}),
            )
        else:
            self._stash = None
