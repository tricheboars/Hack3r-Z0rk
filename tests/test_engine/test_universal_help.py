"""Universal --help interception in the shell."""
from __future__ import annotations

import pytest

from hackerzork.engine.command_registry import CommandContext, CommandRegistry
from hackerzork.engine.shell import Shell


@pytest.fixture()
def shell():
    reg = CommandRegistry()
    reg.register(
        "myls",
        lambda ctx, args: f"args={args}",
        usage="myls [-l]",
        help_text="my fake ls",
        category="filesystem",
    )
    # A command that uses -h itself — we must NOT intercept this one
    reg.register(
        "myfree",
        lambda ctx, args: f"free args={args}",
        usage="myfree [-h]",
        help_text="memory tool",
        category="system",
    )
    ctx = CommandContext(registry=reg)
    return Shell(ctx=ctx, registry=reg)


class TestUniversalHelp:
    def test_double_dash_help_intercepted(self, shell):
        out = shell.execute("myls --help")
        # Should be the brief help, not args output
        assert "myls" in out
        assert "my fake ls" in out
        assert "man myls" in out

    def test_dash_h_NOT_intercepted(self, shell):
        # -h is left alone for commands like du / df / free
        out = shell.execute("myfree -h")
        assert "free args=['-h']" in out

    def test_help_with_other_args_still_intercepts(self, shell):
        out = shell.execute("myls /tmp --help")
        assert "myls" in out
        assert "man myls" in out
        # The actual handler should NOT have run (no 'args=' in output)
        assert "args=" not in out
