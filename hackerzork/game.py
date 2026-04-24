"""H@ck3r-Z0rk — Game orchestrator."""
from __future__ import annotations

import asyncio
import pathlib
from dataclasses import dataclass, field

import yaml


@dataclass
class GameConfig:
    """Global game configuration."""

    audio_enabled: bool = True
    effects_enabled: bool = True
    meta_enabled: bool = True
    debug: bool = False
    save_file: str | None = None


class Game:
    """Main game class — orchestrates all systems."""

    def __init__(
        self,
        audio_enabled: bool = True,
        effects_enabled: bool = True,
        meta_enabled: bool = True,
        debug: bool = False,
        save_file: str | None = None,
    ) -> None:
        self.config = GameConfig(
            audio_enabled=audio_enabled,
            effects_enabled=effects_enabled,
            meta_enabled=meta_enabled,
            debug=debug,
            save_file=save_file,
        )
        self._booted = False

    def boot(self) -> None:
        """Initialize all game systems in dependency order."""
        from hackerzork.engine.command_registry import DEFAULT_REGISTRY, CommandContext
        from hackerzork.engine.history import CommandHistory
        from hackerzork.engine.shell import Shell
        from hackerzork.engine.tab_complete import TabCompleter
        from hackerzork.systems.events import EventBus
        from hackerzork.systems.virtual_fs import VirtualFS

        # 1. Event bus
        self._events = EventBus()

        # 2. Virtual filesystem — load from home.yaml template
        data_dir = pathlib.Path(__file__).parent / "data" / "filesystem"
        template: dict = {}
        template_path = data_dir / "home.yaml"
        if template_path.exists():
            with open(template_path) as fh:
                template = yaml.safe_load(fh) or {}
        self._fs = VirtualFS(template=template)

        # 3. Shared shell environment
        self._env: dict[str, str] = {
            "USER": "user",
            "HOME": "/home/user",
            "CWD": "/home/user",
            "OLDPWD": "/",
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOSTNAME": "hackerzork",
        }

        # 4. Command context — bundle passed to every command handler
        self._ctx = CommandContext(
            fs=self._fs,
            events=self._events,
            env=self._env,
        )

        # 5. Register commands (imports trigger @register_command decorators)
        import hackerzork.commands.filesystem  # noqa: F401

        # 6. History — load from VFS .bash_history
        self._history = CommandHistory(fs=self._fs)
        self._history.load_from_fs()

        # 7. Tab completion
        self._completer = TabCompleter(
            registry=DEFAULT_REGISTRY,
            fs=self._fs,
            env=self._env,
        )
        self._completer.install()

        # 8. Shell REPL
        self._shell = Shell(
            ctx=self._ctx,
            registry=DEFAULT_REGISTRY,
            history=self._history,
        )

        self._booted = True

    def run(self) -> None:
        """Boot then start the shell REPL."""
        if not self._booted:
            self.boot()
        asyncio.run(self._shell.run())

    def shutdown(self) -> None:
        """Clean shutdown of all systems."""
        if self._booted and hasattr(self, "_history"):
            self._history.save_to_fs()
