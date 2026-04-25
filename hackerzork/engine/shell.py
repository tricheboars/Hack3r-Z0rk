"""Main shell REPL — reads input, dispatches commands, writes output."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rich.console import Console

from hackerzork.engine.command_parser import ParseError, ParsedCommand, Redirect, parse
from hackerzork.engine.command_registry import CommandContext, CommandRegistry

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

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    async def run(self) -> None:
        """Main async REPL loop."""
        self._running = True
        loop = asyncio.get_event_loop()

        while self._running:
            try:
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

    def _prompt(self) -> str:
        user = self._ctx.env.get("USER", "user")
        cwd = self._ctx.env.get("CWD", "/home/user")
        home = self._ctx.env.get("HOME", "/home/user")

        if cwd == home:
            display_cwd = "~"
        elif cwd.startswith(home + "/"):
            display_cwd = "~" + cwd[len(home):]
        else:
            display_cwd = cwd

        # Wrap ANSI codes in \001...\002 so readline measures prompt width correctly
        G = "\001\033[32m\002"
        C = "\001\033[36m\002"
        R = "\001\033[0m\002"
        return f"{G}[{user}@hackerzork {C}{display_cwd}{G}]${R} "

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
