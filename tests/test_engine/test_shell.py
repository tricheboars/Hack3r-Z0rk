"""Tests for hackerzork.engine.shell."""
from __future__ import annotations

import pytest

import hackerzork.commands.filesystem  # noqa: F401 — registers commands
from hackerzork.engine.command_registry import (
    CommandContext,
    CommandRegistry,
    register_command,
)
from hackerzork.engine.shell import Shell, _collect_pipeline, _reconstruct_args
from hackerzork.engine.command_parser import parse
from hackerzork.systems.virtual_fs import VirtualFS

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEMPLATE = {
    "/home/user": {
        "_meta": {"permissions": "755", "owner": "user"},
        "hello.txt": {
            "content": "hello world\nfoo bar\nbaz\n",
            "permissions": "644",
            "owner": "user",
        },
        "notes/": {
            "_meta": {"permissions": "755", "owner": "user"},
        },
    },
    "/tmp": {},
}


def _make_registry() -> CommandRegistry:
    """Fresh registry pre-loaded with a handful of test commands."""
    reg = CommandRegistry()

    @register_command(name="echo", usage="echo [text]", category="misc", registry=reg)
    def cmd_echo(ctx: CommandContext, args: list[str]) -> str:
        return " ".join(args)

    @register_command(name="upper", usage="upper", category="misc", registry=reg)
    def cmd_upper(ctx: CommandContext, args: list[str]) -> str:
        stdin = ctx.env.get("STDIN", " ".join(args))
        return stdin.upper()

    @register_command(name="first", usage="first", category="misc", registry=reg)
    def cmd_first(ctx: CommandContext, args: list[str]) -> str:
        stdin = ctx.env.get("STDIN", " ".join(args))
        return stdin.splitlines()[0] if stdin.splitlines() else ""

    @register_command(name="greet", usage="greet", category="misc", registry=reg)
    def cmd_greet(ctx: CommandContext, args: list[str]) -> str:
        return "hello"

    @register_command(name="bye", usage="bye", category="misc", registry=reg)
    def cmd_bye(ctx: CommandContext, args: list[str]) -> str:
        return "goodbye"

    return reg


def _make_shell(reg: CommandRegistry | None = None) -> tuple[Shell, CommandContext]:
    fs = VirtualFS(template=_TEMPLATE)
    env = {
        "USER": "user",
        "HOME": "/home/user",
        "CWD": "/home/user",
        "GREETING": "hi there",
    }
    ctx = CommandContext(fs=fs, env=env)
    registry = reg or _make_registry()
    shell = Shell(ctx=ctx, registry=registry)
    return shell, ctx


# ---------------------------------------------------------------------------
# execute() — basic dispatch
# ---------------------------------------------------------------------------


class TestExecuteBasic:
    def test_empty_input_returns_empty(self):
        shell, _ = _make_shell()
        assert shell.execute("") == ""
        assert shell.execute("   ") == ""

    def test_known_command_dispatches(self):
        shell, _ = _make_shell()
        assert shell.execute("echo hello world") == "hello world"

    def test_command_not_found(self):
        shell, _ = _make_shell()
        result = shell.execute("notacommand")
        assert "command not found" in result
        assert "notacommand" in result

    def test_single_flag_passed_to_command(self):
        # The filesystem ls command is registered via the side-effect import
        fs_reg = CommandRegistry()

        @register_command(name="flagtest", registry=fs_reg)
        def cmd_flagtest(ctx: CommandContext, args: list[str]) -> str:
            return ",".join(args)

        shell, _ = _make_shell(reg=fs_reg)
        result = shell.execute("flagtest -la /tmp")
        assert "-" in result  # flag was reconstructed


# ---------------------------------------------------------------------------
# execute() — environment variable expansion
# ---------------------------------------------------------------------------


class TestEnvExpansion:
    def test_dollar_var_expanded(self):
        shell, _ = _make_shell()
        result = shell.execute("echo $GREETING")
        assert result == "hi there"

    def test_braces_var_expanded(self):
        shell, _ = _make_shell()
        result = shell.execute("echo ${GREETING}")
        assert result == "hi there"

    def test_undefined_var_is_empty(self):
        shell, _ = _make_shell()
        result = shell.execute("echo $UNDEFINED_VAR_XYZ")
        assert result == ""


# ---------------------------------------------------------------------------
# execute() — chained commands (;)
# ---------------------------------------------------------------------------


class TestChaining:
    def test_semicolon_runs_both(self):
        shell, _ = _make_shell()
        result = shell.execute("greet; bye")
        assert "hello" in result
        assert "goodbye" in result

    def test_semicolon_output_joined(self):
        shell, _ = _make_shell()
        result = shell.execute("echo a; echo b")
        lines = result.splitlines()
        assert "a" in lines
        assert "b" in lines


# ---------------------------------------------------------------------------
# execute() — pipe handling
# ---------------------------------------------------------------------------


class TestPipes:
    def test_simple_pipe(self):
        shell, _ = _make_shell()
        result = shell.execute("echo hello world | upper")
        assert result == "HELLO WORLD"

    def test_multi_stage_pipe(self):
        shell, _ = _make_shell()
        result = shell.execute("echo line1\nline2 | upper | first")
        # After upper: "LINE1\nLINE2", after first: "LINE1"
        assert result.startswith("LINE1")

    def test_cat_pipe_grep(self):
        """Use real filesystem commands for an end-to-end pipe test."""
        # Register the real filesystem commands in a fresh registry
        # (they're already registered in DEFAULT_REGISTRY via side-effect import)
        from hackerzork.engine.command_registry import DEFAULT_REGISTRY

        fs = VirtualFS(template=_TEMPLATE)
        env = {"USER": "user", "HOME": "/home/user", "CWD": "/home/user"}
        ctx = CommandContext(fs=fs, env=env)
        shell = Shell(ctx=ctx, registry=DEFAULT_REGISTRY)

        result = shell.execute("cat hello.txt | grep hello")
        assert "hello world" in result
        assert "foo bar" not in result


# ---------------------------------------------------------------------------
# execute() — redirection
# ---------------------------------------------------------------------------


class TestRedirection:
    def test_redirect_write(self):
        shell, ctx = _make_shell()
        shell.execute("echo payload > /tmp/out.txt")
        content = ctx.fs.read_file("/tmp/out.txt")
        assert "payload" in content

    def test_redirect_write_returns_empty(self):
        shell, _ = _make_shell()
        result = shell.execute("echo payload > /tmp/out.txt")
        assert result == ""

    def test_redirect_append(self):
        shell, ctx = _make_shell()
        shell.execute("echo line1 > /tmp/app.txt")
        shell.execute("echo line2 >> /tmp/app.txt")
        content = ctx.fs.read_file("/tmp/app.txt")
        assert "line1" in content
        assert "line2" in content

    def test_redirect_then_cat(self):
        from hackerzork.engine.command_registry import DEFAULT_REGISTRY

        fs = VirtualFS(template=_TEMPLATE)
        env = {"USER": "user", "HOME": "/home/user", "CWD": "/home/user"}
        ctx = CommandContext(fs=fs, env=env)
        shell = Shell(ctx=ctx, registry=DEFAULT_REGISTRY)

        # Register echo in DEFAULT_REGISTRY for this test if not present
        if DEFAULT_REGISTRY.get("echo") is None:
            @register_command(name="echo", registry=DEFAULT_REGISTRY)
            def _echo(c: CommandContext, a: list[str]) -> str:
                return " ".join(a)

        shell.execute("echo written > /tmp/redir.txt")
        result = shell.execute("cat /tmp/redir.txt")
        assert "written" in result


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_collect_pipeline_single(self):
        (cmd,) = parse("echo hello")
        stages = _collect_pipeline(cmd)
        assert len(stages) == 1
        assert stages[0].name == "echo"

    def test_collect_pipeline_two(self):
        (cmd,) = parse("echo hello | upper")
        stages = _collect_pipeline(cmd)
        assert len(stages) == 2
        assert stages[0].name == "echo"
        assert stages[1].name == "upper"

    def test_reconstruct_args_short_flags(self):
        (cmd,) = parse("ls -la /tmp")
        args = _reconstruct_args(cmd)
        # Should have a combined short flag and positional
        joined = " ".join(args)
        assert "-" in joined
        assert "l" in joined
        assert "a" in joined
        assert "/tmp" in args

    def test_reconstruct_args_long_flag(self):
        (cmd,) = parse("cmd --verbose --port=80 file.txt")
        args = _reconstruct_args(cmd)
        assert "--verbose" in args
        assert "--port=80" in args
        assert "file.txt" in args

    def test_reconstruct_args_no_flags(self):
        (cmd,) = parse("cat file.txt")
        args = _reconstruct_args(cmd)
        assert args == ["file.txt"]


# ---------------------------------------------------------------------------
# Syntax error handling
# ---------------------------------------------------------------------------


class TestSyntaxErrors:
    def test_unclosed_quote_returns_error(self):
        shell, _ = _make_shell()
        result = shell.execute("echo 'unclosed")
        assert "syntax error" in result or "error" in result.lower()
