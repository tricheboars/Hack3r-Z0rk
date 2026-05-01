"""Main shell REPL — reads input, dispatches commands, writes output."""
from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

from rich.console import Console

from hackerzork.engine.command_parser import ParseError, ParsedCommand, Redirect, parse
from hackerzork.engine.command_registry import CommandContext, CommandRegistry
from hackerzork.engine.prompt import NerdPrompt

if TYPE_CHECKING:
    from hackerzork.engine.history import CommandHistory


class Shell:
    def __init__(
        self,
        ctx: CommandContext,
        registry: CommandRegistry,
        history: CommandHistory | None = None,
        console: Console | None = None,
    ) -> None:
        self._ctx = ctx
        self._registry = registry
        self._history = history
        self._console = console or Console(highlight=False, markup=False)
        self._running = False
        self._click_fn: Callable[[], None] | None = None
        self._nerd_prompt = NerdPrompt(
            env=self._ctx.env,
            fs=getattr(self._ctx, "fs", None),
            heat=getattr(self._ctx, "heat", None),
        )

    def set_click_sound(self, fn: Callable[[], None] | None) -> None:
        """Wire a per-keystroke click callback. Pass None to disable."""
        self._click_fn = fn

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    async def run(self) -> None:
        """Main async REPL loop."""
        self._running = True
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                if self._click_fn is not None:
                    raw = await loop.run_in_executor(None, self._read_with_clicks)
                else:
                    raw = await loop.run_in_executor(None, input, self._prompt())
            except EOFError:
                # Ctrl+D — treat as exit
                self._console.print("")
                self._running = False
                break
            except KeyboardInterrupt:
                self._console.print("^C")
                if self._ctx.events:
                    self._ctx.events.emit("keyboard_interrupt")
                continue

            raw = raw.strip()
            if not raw:
                continue

            if raw in ("exit", "quit"):
                self._running = False
                if self._ctx.events:
                    self._ctx.events.emit("game_exit")
                break

            if self._history is not None:
                self._history.add(raw)

            result = self.execute(raw)
            if result:
                self._console.print(result)

            # SkyNet observes every command — may fire a fourth-wall effect
            if self._ctx.skynet is not None:
                await self._ctx.skynet.maybe_intervene()

        if self._history is not None:
            self._history.save_to_fs()

    def execute(self, raw: str) -> str:
        """Parse and dispatch one input line. Returns the output string."""
        raw = raw.strip()
        if not raw:
            return ""

        try:
            cmds = parse(raw, env=self._ctx.env)
        except ParseError as exc:
            return f"bash: syntax error: {exc}"

        if not cmds:
            return ""

        if self._ctx.events:
            self._ctx.events.emit(
                "command_entered",
                cmd=cmds[0].name,
                raw_input=raw,
            )

        outputs: list[str] = []
        for stmt in cmds:
            pipeline = _collect_pipeline(stmt)
            redirect = pipeline[-1].redirect

            if len(pipeline) > 1:
                result = self._handle_pipe(pipeline)
            else:
                result = self._dispatch_single(pipeline[0])

            if redirect:
                result = self._handle_redirect(result, redirect)

            if result:
                outputs.append(result)

        return "\n".join(outputs)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _read_with_clicks(self) -> str:
        """Blocking line reader that fires _click_fn on every character typed.

        Uses readline's callback interface so tab-completion and history
        (installed by TabCompleter) keep working. Falls back to plain input()
        if the callback API is unavailable (e.g. libedit on some macOS builds).
        """
        import select

        try:
            import readline as rl
        except ImportError:
            return input(self._prompt())

        if not hasattr(rl, "callback_handler_install"):
            return input(self._prompt())

        result: list[str] = []
        done = False

        def _handler(text: str | None) -> None:
            nonlocal done
            result.append(text if text is not None else "")
            done = True

        prev_len = 0
        try:
            rl.callback_handler_install(self._prompt(), _handler)
            while not done:
                try:
                    ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                except (ValueError, OSError):
                    break
                if ready:
                    rl.callback_read_char()
                    cur_len = len(rl.get_line_buffer())
                    if cur_len > prev_len and self._click_fn is not None:
                        self._click_fn()
                    prev_len = cur_len
        except KeyboardInterrupt:
            print("^C")
            try:
                rl.callback_handler_remove()
            except Exception:
                pass
            raise
        except EOFError:
            try:
                rl.callback_handler_remove()
            except Exception:
                pass
            raise
        finally:
            try:
                rl.callback_handler_remove()
            except Exception:
                pass

        return result[0] if result else ""

    def _prompt(self) -> str:
        return self._nerd_prompt.render()

    def _handle_pipe(self, cmds: list[ParsedCommand]) -> str:
        stdin = ""
        for cmd in cmds:
            old_env = self._ctx.env
            self._ctx.env = {**old_env, "STDIN": stdin} if stdin else dict(old_env)
            try:
                stdin = self._dispatch_single(cmd)
            finally:
                self._ctx.env = old_env
        return stdin

    def _handle_redirect(self, result: str, redir: Redirect) -> str:
        try:
            path = self._ctx.fs.resolve_path(redir.target)
            self._ctx.fs.write_file(path, result, append=redir.append)
            # Notify toolkit whenever something is written to /etc/apt/sources.list.d/
            # so it can detect when the shadow repo has been configured.
            if self._ctx.toolkit is not None:
                self._ctx.toolkit.check_shadow_source(path, result)
            return ""
        except Exception as exc:
            return f"bash: {redir.target}: {exc}"

    def _dispatch_single(self, cmd: ParsedCommand) -> str:
        handler = self._registry.get(cmd.name)
        if handler is None:
            return f"bash: {cmd.name}: command not found"
        args = _reconstruct_args(cmd)
        try:
            return handler(self._ctx, args)
        except Exception as exc:
            return f"bash: {cmd.name}: {exc}"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _collect_pipeline(cmd: ParsedCommand) -> list[ParsedCommand]:
    """Walk pipe_to chain and return all stages as a flat list."""
    stages: list[ParsedCommand] = []
    cur: ParsedCommand | None = cmd
    while cur is not None:
        stages.append(cur)
        cur = cur.pipe_to
    return stages


def _reconstruct_args(cmd: ParsedCommand) -> list[str]:
    """Rebuild a flat argv list from a ParsedCommand for use by command handlers.

    Handlers receive their raw args (flags included) and do their own parsing,
    so we reconstruct the flag tokens here before appending positional args.
    """
    short: list[str] = []
    result: list[str] = []

    for name, val in cmd.flags.items():
        if len(name) == 1:
            if isinstance(val, bool) and val:
                short.append(name)
            elif isinstance(val, str):
                result.append(f"-{name}={val}")
        else:
            if isinstance(val, bool) and val:
                result.append(f"--{name}")
            elif isinstance(val, str):
                result.append(f"--{name}={val}")

    if short:
        result.insert(0, "-" + "".join(sorted(short)))

    result.extend(cmd.args)
    return result
