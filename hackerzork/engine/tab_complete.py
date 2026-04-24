"""Tab completion engine — plugs into readline."""
from __future__ import annotations

import readline
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackerzork.engine.command_registry import CommandRegistry
    from hackerzork.systems.virtual_fs import VirtualFS


class TabCompleter:
    def __init__(
        self,
        registry: CommandRegistry,
        fs: VirtualFS,
        env: dict[str, str],
    ) -> None:
        self._registry = registry
        self._fs = fs
        self._env = env
        self._candidates: list[str] = []

    def install(self) -> None:
        """Register this completer with readline."""
        readline.set_completer(self.complete)
        readline.set_completer_delims(" \t\n;|")
        readline.parse_and_bind("tab: complete")

    def complete(self, text: str, state: int) -> str | None:
        if state == 0:
            line = readline.get_line_buffer()
            # Is the cursor still on the first word? → complete commands
            before = line[: line.rfind(text)] if text and text in line else line[: len(line) - len(text)]
            if not before.strip():
                self._candidates = self._command_completions(text)
            else:
                cwd = self._env.get("CWD", "/home/user")
                self._candidates = self._path_completions(text, cwd)

        return self._candidates[state] if state < len(self._candidates) else None

    def _command_completions(self, partial: str) -> list[str]:
        return self._registry.get_completions(partial)

    def _path_completions(self, partial: str, cwd: str) -> list[str]:
        try:
            if "/" in partial:
                dir_part, _, name_part = partial.rpartition("/")
                dir_path = self._fs.resolve_path(dir_part or "/")
            else:
                dir_path = cwd
                name_part = partial

            entries = self._fs.list_dir(dir_path)
            results: list[str] = []
            for entry in entries:
                if entry.name.startswith(name_part):
                    if "/" in partial:
                        prefix = partial.rpartition("/")[0] + "/"
                        candidate = prefix + entry.name
                    else:
                        candidate = entry.name
                    if entry.is_dir:
                        candidate += "/"
                    results.append(candidate)
            return sorted(results)
        except Exception:
            return []
