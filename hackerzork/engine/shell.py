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

            expanded = self._expand_aliases(raw)

            if expanded in ("exit", "quit", "logout"):
                self._running = False
                if self._ctx.events:
                    self._ctx.events.emit("game_exit")
                break

            if self._history is not None:
                self._history.add(raw)

            result = self.execute(expanded, _already_expanded=True)
            if result:
                self._console.print(result)

            # SkyNet observes every command — may fire a fourth-wall effect
            if self._ctx.skynet is not None:
                await self._ctx.skynet.maybe_intervene()

        if self._history is not None:
            self._history.save_to_fs()

    def execute(self, raw: str, *, _already_expanded: bool = False) -> str:
        """Parse and dispatch one input line. Returns the output string."""
        raw = raw.strip()
        if not raw:
            return ""

        if not _already_expanded:
            raw = self._expand_aliases(raw)

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

    def _expand_aliases(self, raw: str) -> str:
        """Expand the leading word of each ``;``/``&&``/``||``-separated statement.

        Mirrors bash: ``alias ll='ls -la'`` then typing ``ll /tmp`` becomes
        ``ls -la /tmp``. Recursive expansion is bounded (max 16 hops) to keep a
        cycle from looping forever.
        """
        env = self._ctx.env
        if not env or not any(k.startswith("ALIAS_") for k in env):
            return raw

        aliases = {k[6:]: v for k, v in env.items() if k.startswith("ALIAS_")}

        # Split on top-level separators while leaving them in place.
        out: list[str] = []
        i = 0
        n = len(raw)
        start = 0
        while i < n:
            ch = raw[i]
            if ch in ("'", '"'):
                # Skip quoted span — separators inside are literal.
                end = raw.find(ch, i + 1)
                if end == -1:
                    break
                i = end + 1
                continue
            two = raw[i : i + 2]
            if ch == ";" or two in ("&&", "||"):
                out.append(self._expand_first_word(raw[start:i], aliases))
                sep_len = 2 if two in ("&&", "||") else 1
                out.append(raw[i : i + sep_len])
                i += sep_len
                start = i
                continue
            i += 1
        out.append(self._expand_first_word(raw[start:], aliases))
        return "".join(out)

    @staticmethod
    def _expand_first_word(segment: str, aliases: dict[str, str]) -> str:
        leading = len(segment) - len(segment.lstrip())
        body = segment[leading:]
        if not body:
            return segment
        head, _, tail = body.partition(" ")
        seen: set[str] = set()
        while head in aliases and head not in seen:
            seen.add(head)
            replacement = aliases[head]
            new_head, _, extra = replacement.partition(" ")
            head = new_head
            tail = (extra + (" " + tail if tail else "")).strip()
            if len(seen) >= 16:
                break
        rebuilt = head + (" " + tail if tail else "")
        return segment[:leading] + rebuilt

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
    """Return the raw token list for a ParsedCommand.

    Each handler does its own flag parsing, so we hand back the original tokens
    in the order the user typed them — preserving single-dash long flags like
    ``find -name '*.txt'`` instead of bundling them into ``-aemn``.
    """
    return list(cmd.argv)
