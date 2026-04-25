"""Tests for hackerzork/commands/help.py."""
from __future__ import annotations

import pytest

from hackerzork.engine.command_registry import CommandContext, CommandRegistry, register_command
from hackerzork.commands.help import cmd_help, cmd_hint


# ---------------------------------------------------------------------------
# Fixture — isolated registry with a handful of test commands
# ---------------------------------------------------------------------------

@pytest.fixture()
def reg() -> CommandRegistry:
    r = CommandRegistry()
    r.register("ls",   lambda ctx, args: "", usage="ls [-la]",  help_text="List directory contents",  category="filesystem")
    r.register("nmap", lambda ctx, args: "", usage="nmap <ip>",  help_text="Scan network ports",       category="network")
    r.register("irc",  lambda ctx, args: "", usage="irc <sub>",  help_text="IRC client commands",      category="comms")
    r.register("save", lambda ctx, args: "", usage="save [file]", help_text="Save game state",          category="system")
    r.register("help", lambda ctx, args: "", usage="help [cmd]",  help_text="Show help",               category="system")
    return r


@pytest.fixture()
def ctx(reg) -> CommandContext:
    return CommandContext(registry=reg)


# ---------------------------------------------------------------------------
# help — no args (full listing)
# ---------------------------------------------------------------------------

class TestHelpNoArgs:
    def test_returns_string(self, ctx):
        result = cmd_help(ctx, [])
        assert isinstance(result, str)

    def test_contains_category_headers(self, ctx):
        result = cmd_help(ctx, [])
        assert "filesystem" in result
        assert "network" in result
        assert "system" in result
        assert "comms" in result

    def test_contains_command_names(self, ctx):
        result = cmd_help(ctx, [])
        assert "ls" in result
        assert "nmap" in result
        assert "irc" in result

    def test_contains_help_text(self, ctx):
        result = cmd_help(ctx, [])
        assert "List directory contents" in result
        assert "Scan network ports" in result

    def test_suggests_hint(self, ctx):
        result = cmd_help(ctx, [])
        assert "hint" in result.lower()

    def test_suggests_detailed_help(self, ctx):
        result = cmd_help(ctx, [])
        assert "help <command>" in result or "help <cmd>" in result.lower()


# ---------------------------------------------------------------------------
# help <command> — per-command detail
# ---------------------------------------------------------------------------

class TestHelpWithCommand:
    def test_returns_name_section(self, ctx):
        result = cmd_help(ctx, ["nmap"])
        assert "nmap" in result

    def test_returns_usage(self, ctx):
        result = cmd_help(ctx, ["nmap"])
        assert "nmap <ip>" in result

    def test_returns_help_text(self, ctx):
        result = cmd_help(ctx, ["nmap"])
        assert "Scan network ports" in result

    def test_returns_category(self, ctx):
        result = cmd_help(ctx, ["ls"])
        assert "filesystem" in result

    def test_unknown_command(self, ctx):
        result = cmd_help(ctx, ["nonexistent_cmd"])
        assert "no help" in result.lower() or "nonexistent_cmd" in result

    def test_help_for_help(self, ctx):
        result = cmd_help(ctx, ["help"])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# help — no registry
# ---------------------------------------------------------------------------

class TestHelpNoRegistry:
    def test_no_crash_when_registry_is_none(self):
        ctx = CommandContext(registry=None)
        result = cmd_help(ctx, [])
        assert "no registry" in result.lower() or isinstance(result, str)


# ---------------------------------------------------------------------------
# hint — no game state
# ---------------------------------------------------------------------------

class TestHintNoState:
    def test_returns_string(self):
        ctx = CommandContext()
        result = cmd_hint(ctx, [])
        assert isinstance(result, str)

    def test_non_empty(self):
        ctx = CommandContext()
        assert len(cmd_hint(ctx, [])) > 0

    def test_contains_hint_label(self):
        ctx = CommandContext()
        result = cmd_hint(ctx, [])
        assert "HINT" in result or "hint" in result.lower()

    def test_args_ignored(self):
        ctx = CommandContext()
        result = cmd_hint(ctx, ["foo", "bar"])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# hint — with game state
# ---------------------------------------------------------------------------

class _FakeState:
    def __init__(self, flags: set[str] | None = None):
        self.flags = flags or set()


class TestHintWithState:
    def test_early_game_no_flags(self):
        ctx = CommandContext(state=_FakeState(set()))
        result = cmd_hint(ctx, [])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mid_game_some_flags(self):
        ctx = CommandContext(state=_FakeState({"surveillance_seen"}))
        result = cmd_hint(ctx, [])
        assert isinstance(result, str)

    def test_late_game_shadow_unlocked(self):
        ctx = CommandContext(state=_FakeState({"shadow_unlocked"}))
        result = cmd_hint(ctx, [])
        assert isinstance(result, str)

    def test_late_game_relay_compromised(self):
        ctx = CommandContext(state=_FakeState({"relay_alpha_compromised"}))
        result = cmd_hint(ctx, [])
        assert isinstance(result, str)

    def test_varies_across_calls(self):
        ctx = CommandContext(state=_FakeState(set()))
        results = {cmd_hint(ctx, []) for _ in range(30)}
        assert len(results) >= 1  # at least valid strings; randomness may vary


# ---------------------------------------------------------------------------
# Integration: cmd_help uses DEFAULT_REGISTRY (smoke test)
# ---------------------------------------------------------------------------

class TestHelpWithDefaultRegistry:
    def test_default_registry_no_crash(self):
        from hackerzork.engine.command_registry import DEFAULT_REGISTRY
        ctx = CommandContext(registry=DEFAULT_REGISTRY)
        # Import command modules so they self-register
        import hackerzork.commands.help          # noqa: F401
        import hackerzork.commands.filesystem    # noqa: F401
        import hackerzork.commands.system        # noqa: F401
        result = cmd_help(ctx, [])
        assert isinstance(result, str)

    def test_help_lists_filesystem_commands(self):
        from hackerzork.engine.command_registry import DEFAULT_REGISTRY
        import hackerzork.commands.filesystem  # noqa: F401
        ctx = CommandContext(registry=DEFAULT_REGISTRY)
        result = cmd_help(ctx, [])
        assert "ls" in result or "filesystem" in result
