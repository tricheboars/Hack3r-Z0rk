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


_LAST_LOGIN = (
    "[dim]Last login: Fri Mar 15 02:55:41 2026 from 45.152.66.201[/dim]\n"
)


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
        from hackerzork.meta.fourth_wall import FourthWallBreaker
        from hackerzork.meta.skynet import SkyNetEngine
        from hackerzork.systems.comms import CommsSystem
        from hackerzork.systems.events import EventBus
        from hackerzork.systems.heat import HeatSystem
        from hackerzork.systems.network import NetworkSim
        from hackerzork.systems.save_load import SaveSystem
        from hackerzork.systems.state import GameState
        from hackerzork.systems.toolkit import Toolkit
        from hackerzork.systems.virtual_fs import VirtualFS
        import hackerzork.effects as fx

        # Configure visual effects based on game settings
        fx.config.enabled = self.config.effects_enabled
        fx.config.speed_multiplier = 1.0 if self.config.effects_enabled else 0.0

        data_dir = pathlib.Path(__file__).parent / "data"

        # 1. Event bus — everything talks through here
        self._events = EventBus()

        # 2. Virtual filesystem — seeded from home.yaml
        template: dict = {}
        template_path = data_dir / "filesystem" / "home.yaml"
        if template_path.exists():
            with open(template_path) as fh:
                template = yaml.safe_load(fh) or {}
        self._fs = VirtualFS(template=template)

        # 3. Network simulation — load nodes from data/nodes/
        self._network = NetworkSim()
        nodes_dir = data_dir / "nodes"
        if nodes_dir.exists():
            self._network.load_nodes(nodes_dir)

        # 4. Heat system — wired to events
        self._heat = HeatSystem(events=self._events)

        # 5. Toolkit — package install state; catalog loaded from data/packages/
        self._toolkit = Toolkit(fs=self._fs, events=self._events)
        packages_dir = data_dir / "packages"
        if packages_dir.exists():
            self._toolkit.load_catalog(packages_dir)

        # 6. Comms — IRC channels, DMs, contacts
        self._comms = CommsSystem(events=self._events, data_dir=data_dir / "dialogue")
        self._comms.load()

        # 7. Game state machine — story flags, chapter, event timeline
        self._state = GameState(events=self._events)

        # 8. Save system
        save_dir = pathlib.Path.home() / ".hackerzork"
        self._save = SaveSystem(save_dir=save_dir)

        # 8b. Git save system — virtual git history for save/load
        from hackerzork.systems.git_saves import GitSaveSystem
        self._git_saves = GitSaveSystem()

        # 9. Meta engine — SkyNet observation + fourth-wall breaks
        self._fourth_wall = FourthWallBreaker(enabled=self.config.meta_enabled)
        self._skynet = SkyNetEngine(
            fourth_wall=self._fourth_wall,
            enabled=self.config.meta_enabled,
        )
        self._skynet.bind_events(self._events)

        # 10. Audio — optional; failure never crashes the game
        self._audio = None
        if self.config.audio_enabled:
            try:
                from hackerzork.audio import keygen
                from hackerzork.audio.mixer import AudioMixer
                keygen.ensure_sounds(data_dir / "sounds")
                self._audio = AudioMixer(enabled=True)
            except Exception:
                pass

        # 11. Shell environment
        self._env: dict[str, str] = {
            "USER": "user",
            "HOME": "/home/user",
            "CWD": "/home/user",
            "OLDPWD": "/",
            "PATH": "/usr/local/bin:/usr/bin:/bin:/home/user/tools",
            "HOSTNAME": "burner",
            "_SK_SID": "sk-9a7f3c2d-8b1e-4f6a-9c3d-2e7b1a5f4c8e",
        }

        # 12. Command context — bundle passed to every command handler
        self._ctx = CommandContext(
            fs=self._fs,
            network=self._network,
            events=self._events,
            heat=self._heat,
            toolkit=self._toolkit,
            comms=self._comms,
            state=self._state,
            save_system=self._save,
            git_saves=self._git_saves,
            skynet=self._skynet,
            env=self._env,
        )

        # 13. Register all command modules (imports trigger @register_command decorators)
        import hackerzork.commands.filesystem    # noqa: F401
        import hackerzork.commands.network_cmds  # noqa: F401
        import hackerzork.commands.system        # noqa: F401
        import hackerzork.commands.packaging     # noqa: F401
        import hackerzork.commands.comms_cmds    # noqa: F401
        import hackerzork.commands.save_cmds     # noqa: F401
        import hackerzork.commands.hacking       # noqa: F401
        import hackerzork.commands.devtools      # noqa: F401
        import hackerzork.commands.help          # noqa: F401
        import hackerzork.commands.git_cmds     # noqa: F401
        import hackerzork.commands.tutorial      # noqa: F401
        import hackerzork.commands.learn         # noqa: F401

        # 13b. Tutorial engine — subscribes to command_entered events and
        # auto-advances when the player performs each step's goal action.
        from hackerzork.commands.tutorial import TutorialEngine
        self._tutorial = TutorialEngine(state=self._state, events=self._events)
        self._ctx.tutorial = self._tutorial

        # 14. Command history — load persisted history from VFS
        self._history = CommandHistory(fs=self._fs)
        self._history.load_from_fs()
        self._ctx.history = self._history
        self._ctx.registry = DEFAULT_REGISTRY

        # 15. Tab completion
        self._completer = TabCompleter(
            registry=DEFAULT_REGISTRY,
            fs=self._fs,
            env=self._env,
        )
        self._completer.install()

        # 16. Shell REPL
        self._shell = Shell(
            ctx=self._ctx,
            registry=DEFAULT_REGISTRY,
            history=self._history,
        )
        if self._audio is not None:
            self._shell.set_click_sound(
                lambda: self._audio.play_sfx("sfx_key_click")  # type: ignore[union-attr]
            )

        # 17. Wire audio reactive layer to heat events
        if self._audio is not None:
            self._events.on("heat_threshold_crossed", self._on_heat_threshold)
            self._events.on("surveillance_discovered", self._on_surveillance)
            self._events.on("skynet_process_killed", self._on_skynet_kill)

        # 18. Wire story flag propagation
        #     toolkit emits "shadow_unlocked" → set game state flag
        #     game state emits "flag_set"     → sync flag into comms channels
        self._events.on("shadow_unlocked", self._on_shadow_unlocked)
        self._events.on("flag_set", self._on_flag_set)

        # 19. Source the seeded .bashrc so its aliases (ll, scan, q, please) work.
        self._source_bashrc()

        self._booted = True

    def _source_bashrc(self) -> None:
        """Pre-populate aliases and exports from /home/user/.bashrc."""
        try:
            content = self._fs.read_file("/home/user/.bashrc")
        except Exception:
            return
        import re as _re
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = _re.match(r"alias\s+([A-Za-z_][\w-]*)\s*=\s*(.+)$", line)
            if m:
                name, raw_val = m.group(1), m.group(2).strip()
                if (raw_val.startswith("'") and raw_val.endswith("'")) or (
                    raw_val.startswith('"') and raw_val.endswith('"')
                ):
                    raw_val = raw_val[1:-1]
                self._env[f"ALIAS_{name}"] = raw_val
                continue
            m = _re.match(r"export\s+([A-Za-z_]\w*)\s*=\s*(.+)$", line)
            if m:
                key, raw_val = m.group(1), m.group(2).strip()
                if (raw_val.startswith("'") and raw_val.endswith("'")) or (
                    raw_val.startswith('"') and raw_val.endswith('"')
                ):
                    raw_val = raw_val[1:-1]
                # Don't clobber CWD/HOME/USER set up earlier; only pull through
                # what the user might reasonably customize.
                if key not in ("CWD", "HOME", "USER", "HOSTNAME"):
                    self._env[key] = raw_val

    # -------------------------------------------------------------------------
    # Event handlers
    # -------------------------------------------------------------------------

    def _on_heat_threshold(self, event: object) -> None:
        if self._audio is None:
            return
        level = getattr(event, "data", {}).get("level", 0.0)
        self._audio.set_reactive_state(float(level))

    def _on_surveillance(self, event: object) -> None:
        if self._audio is None:
            return
        if getattr(event, "data", {}).get("first"):
            self._audio.play_sfx("surveillance_alert")

    def _on_skynet_kill(self, event: object) -> None:
        if self._audio is None:
            return
        self._audio.play_sfx("process_kill")

    def _on_shadow_unlocked(self, event: object) -> None:
        """Toolkit activated the shadow repo — set the game state flag."""
        self._state.set_flag("shadow_unlocked")

    def _on_flag_set(self, event: object) -> None:
        """A story flag was set — propagate it into the comms channel gating."""
        flag = getattr(event, "data", {}).get("flag", "")
        if flag:
            self._comms.set_flag(flag)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def run(self) -> None:
        """Boot then run the intro sequence and shell REPL."""
        if not self._booted:
            self.boot()
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        """Async entry — font check, boot animation, optional save restore, then shell."""
        import hackerzork.effects as fx
        from rich.console import Console

        con = Console(highlight=False, markup=True)

        # ── Nerd Font detection + auto-install (runs before boot animation) ──
        await self._check_fonts(con)

        # Boot sequence animation
        if self.config.effects_enabled:
            from hackerzork.effects.animations import boot_sequence
            _on_beep  = (lambda: self._audio.play_sfx("sfx_boot_beep"))  if self._audio else None
            _on_ready = (lambda: self._audio.play_sfx("sfx_boot_ready")) if self._audio else None
            await boot_sequence(on_beep=_on_beep, on_ready=_on_ready)

        # Load save file if --load was specified
        if self.config.save_file:
            try:
                save_data = self._save.read(self.config.save_file)
                self._save.apply(
                    save_data,
                    fs=self._fs,
                    network=self._network,
                    heat=self._heat,
                    toolkit=self._toolkit,
                    comms=self._comms,
                    state=self._state,
                    history=self._history,
                    env=self._env,
                )
                summary = self._save.format_load_summary(save_data)
                heat_lvl = self._heat.level if hasattr(self._heat, "level") else 0.0
                con.print(self._save.corrupt_load_display(summary, heat_level=heat_lvl))
            except FileNotFoundError:
                con.print(f"[red]Save file not found: {self.config.save_file}[/red]")
            except Exception as exc:
                con.print(f"[red]Failed to load save: {exc}[/red]")

        # Message of the day — last-login banner + sysreport orientation panel
        from hackerzork.effects.sysreport import render_sysreport
        con.print(_LAST_LOGIN)
        heat_lvl = self._heat.level if hasattr(self._heat, "level") else 0.0
        con.print(render_sysreport(heat=heat_lvl))

        # Hand off to the shell REPL
        await self._shell.run()

    async def _check_fonts(self, con) -> None:
        """Detect Nerd Font support; auto-install if fonts are in data/fonts/."""
        import asyncio
        from hackerzork.engine import fonts as fnt
        from hackerzork.engine import prompt as pmt

        data_dir  = pathlib.Path(__file__).parent / "data"
        cache_dir = pathlib.Path.home() / ".hackerzork" / "fonts"

        loop = asyncio.get_event_loop()
        result, msgs = await loop.run_in_executor(
            None,
            lambda: fnt.ensure_nerd_font(
                data_fonts_dir=data_dir / "fonts",
                cache_dir=cache_dir,
                ask=True,
            ),
        )

        active = (result == fnt.FontResult.active)
        pmt.set_nerd_font_active(active)

        for msg in msgs:
            style = "dim green" if "installed" in msg.lower() else "dim yellow"
            con.print(f"[{style}]{msg}[/{style}]")

        if result == fnt.FontResult.needs_restart:
            con.print(
                f"[dim yellow]  → Set terminal font to '{fnt.FONT_NAME}' "
                f"and restart for full visuals.[/dim yellow]"
            )
        elif result == fnt.FontResult.downloaded:
            con.print(
                f"[dim green]  → Restart your terminal and set font to "
                f"'{fnt.FONT_NAME}' to activate glyphs.[/dim green]"
            )

    def shutdown(self) -> None:
        """Clean shutdown of all systems."""
        if self._booted:
            if hasattr(self, "_history"):
                self._history.save_to_fs()
            if self._audio is not None:
                self._audio.shutdown()
