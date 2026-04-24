"""Command history — readline integration and VFS persistence."""
from __future__ import annotations

import readline
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackerzork.systems.virtual_fs import VirtualFS

_HISTORY_PATH = "/home/user/.bash_history"
_MAX_ENTRIES = 1000


class CommandHistory:
    def __init__(self, fs: VirtualFS | None = None) -> None:
        self._fs = fs
        self._entries: list[str] = []
        readline.set_history_length(_MAX_ENTRIES)

    def add(self, cmd: str) -> None:
        cmd = cmd.strip()
        if not cmd:
            return
        self._entries.append(cmd)
        if len(self._entries) > _MAX_ENTRIES:
            self._entries = self._entries[-_MAX_ENTRIES:]
        readline.add_history(cmd)

    def load_from_fs(self) -> None:
        if self._fs is None:
            return
        try:
            content = self._fs.read_file(_HISTORY_PATH)
            lines = [ln for ln in content.splitlines() if ln.strip()]
            self._entries = lines[-_MAX_ENTRIES:]
            readline.clear_history()
            for line in self._entries:
                readline.add_history(line)
        except Exception:
            pass

    def save_to_fs(self) -> None:
        if self._fs is None or not self._entries:
            return
        try:
            content = "\n".join(self._entries) + "\n"
            self._fs.write_file(_HISTORY_PATH, content)
        except Exception:
            pass

    def get_all(self) -> list[str]:
        return list(self._entries)
