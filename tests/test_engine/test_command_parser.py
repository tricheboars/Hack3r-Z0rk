"""Tests for hackerzork.engine.command_parser and command_registry."""
from __future__ import annotations

import pytest

from hackerzork.engine.command_parser import (
    ParseError,
    Redirect,
    TokenType,
    parse,
    parse_one,
    tokenize,
)
from hackerzork.engine.command_registry import (
    CommandContext,
    CommandRegistry,
    register_command,
)


# ---------------------------------------------------------------------------
# Parser — simple commands & basics
# ---------------------------------------------------------------------------


class TestSimpleCommands:
    def test_single_command(self):
        cmd = parse_one("ls")
        assert cmd is not None
        assert cmd.name == "ls"
        assert cmd.args == []
        assert cmd.flags == {}
        assert cmd.pipe_to is None
        assert cmd.redirect is None

    def test_command_with_arg(self):
        cmd = parse_one("cat /etc/passwd")
        assert cmd.name == "cat"
        assert cmd.args == ["/etc/passwd"]

    def test_command_with_multiple_args(self):
        cmd = parse_one("cp src.txt dest.txt")
        assert cmd.name == "cp"
        assert cmd.args == ["src.txt", "dest.txt"]

    def test_raw_preserved(self):
        cmd = parse_one("ls -la /tmp")
        assert cmd.raw == "ls -la /tmp"


class TestEmptyAndWhitespace:
    def test_empty_string(self):
        assert parse("") == []
        assert parse_one("") is None

    def test_whitespace_only(self):
        assert parse("   ") == []
        assert parse_one("\t  \n") is None

    def test_extra_whitespace_collapses(self):
        cmd = parse_one("  ls   -l   /tmp  ")
        assert cmd.name == "ls"
        assert cmd.flags == {"l": True}
        assert cmd.args == ["/tmp"]

    def test_tabs_separate_tokens(self):
        cmd = parse_one("ls\t-l")
        assert cmd.name == "ls"
        assert cmd.flags == {"l": True}


# ---------------------------------------------------------------------------
# Parser — flags
# ---------------------------------------------------------------------------


class TestFlags:
    def test_short_flag(self):
        cmd = parse_one("ls -l")
        assert cmd.flags == {"l": True}
        assert cmd.args == []

    def test_long_flag(self):
        cmd = parse_one("ls --verbose")
        assert cmd.flags == {"verbose": True}
        assert cmd.args == []

    def test_long_flag_with_value(self):
        cmd = parse_one("nmap --port=80 host")
        assert cmd.flags == {"port": "80"}
        assert cmd.args == ["host"]

    def test_short_flag_bundling(self):
        cmd = parse_one("ls -la")
        assert cmd.flags == {"l": True, "a": True}

    def test_short_flag_with_separate_value_stays_positional(self):
        # Spec choice: -p 80 leaves "80" as a positional; the handler decides
        # whether to consume the next arg.
        cmd = parse_one("nmap -p 80 host")
        assert cmd.flags == {"p": True}
        assert cmd.args == ["80", "host"]

    def test_double_dash_ends_flags(self):
        cmd = parse_one("rm -- --weird-name")
        assert cmd.args == ["--weird-name"]
        assert cmd.flags == {}

    def test_negative_number_is_arg(self):
        cmd = parse_one("echo -3.14")
        assert cmd.args == ["-3.14"]
        assert cmd.flags == {}

    def test_lone_dash_is_arg(self):
        cmd = parse_one("cat -")
        assert cmd.args == ["-"]
        assert cmd.flags == {}


# ---------------------------------------------------------------------------
# Parser — quoting & escaping
# ---------------------------------------------------------------------------


class TestQuoting:
    def test_double_quoted_string(self):
        cmd = parse_one('echo "hello world"')
        assert cmd.args == ["hello world"]

    def test_single_quoted_string(self):
        cmd = parse_one("echo 'hello world'")
        assert cmd.args == ["hello world"]

    def test_quoted_pipe_is_literal(self):
        cmd = parse_one('echo "pipe | not a pipe"')
        assert cmd.args == ["pipe | not a pipe"]
        assert cmd.pipe_to is None

    def test_quoted_redirect_is_literal(self):
        cmd = parse_one('echo "a > b"')
        assert cmd.args == ["a > b"]
        assert cmd.redirect is None

    def test_concatenated_quoted_segments(self):
        # "foo"bar'baz' -> single word "foobarbaz"
        cmd = parse_one("""echo "foo"bar'baz'""")
        assert cmd.args == ["foobarbaz"]

    def test_unclosed_double_quote_raises(self):
        with pytest.raises(ParseError):
            parse('echo "hello')

    def test_unclosed_single_quote_raises(self):
        with pytest.raises(ParseError):
            parse("echo 'hello")


class TestEscaping:
    def test_backslash_escapes_space(self):
        cmd = parse_one("echo hello\\ world")
        assert cmd.args == ["hello world"]

    def test_backslash_escapes_quote_inside_double_quotes(self):
        cmd = parse_one('echo "a\\"b"')
        assert cmd.args == ['a"b']

    def test_backslash_escapes_dollar_inside_double_quotes(self):
        cmd = parse_one('echo "\\$HOME"', env={"HOME": "/root"})
        assert cmd.args == ["$HOME"]


# ---------------------------------------------------------------------------
# Parser — environment variable expansion
# ---------------------------------------------------------------------------


class TestEnvVarExpansion:
    def test_basic_expansion(self):
        cmd = parse_one("echo $HOME", env={"HOME": "/home/user"})
        assert cmd.args == ["/home/user"]

    def test_braced_expansion(self):
        cmd = parse_one("echo ${USER}", env={"USER": "neo"})
        assert cmd.args == ["neo"]

    def test_undefined_is_empty(self):
        cmd = parse_one("echo $MISSING tail", env={})
        assert cmd.args == ["", "tail"]

    def test_expansion_inside_double_quotes(self):
        cmd = parse_one('echo "user is $USER"', env={"USER": "neo"})
        assert cmd.args == ["user is neo"]

    def test_no_expansion_inside_single_quotes(self):
        cmd = parse_one("echo '$USER'", env={"USER": "neo"})
        assert cmd.args == ["$USER"]

    def test_target_var_in_arg_position(self):
        cmd = parse_one("nmap $TARGET", env={"TARGET": "10.0.0.1"})
        assert cmd.name == "nmap"
        assert cmd.args == ["10.0.0.1"]

    def test_unclosed_brace_raises(self):
        with pytest.raises(ParseError):
            parse("echo ${BAD")


# ---------------------------------------------------------------------------
# Parser — pipes & redirection
# ---------------------------------------------------------------------------


class TestPipes:
    def test_simple_pipe(self):
        cmd = parse_one("cat /etc/passwd | grep root")
        assert cmd.name == "cat"
        assert cmd.args == ["/etc/passwd"]
        assert cmd.pipe_to is not None
        assert cmd.pipe_to.name == "grep"
        assert cmd.pipe_to.args == ["root"]
        assert cmd.pipe_to.pipe_to is None

    def test_three_stage_pipe(self):
        cmd = parse_one("cat f | grep x | wc -l")
        assert cmd.name == "cat"
        assert cmd.pipe_to.name == "grep"
        assert cmd.pipe_to.pipe_to.name == "wc"
        assert cmd.pipe_to.pipe_to.flags == {"l": True}

    def test_pipe_without_spaces(self):
        cmd = parse_one("cat foo|grep bar")
        assert cmd.name == "cat"
        assert cmd.pipe_to.name == "grep"

    def test_empty_pipe_segment_raises(self):
        with pytest.raises(ParseError):
            parse("cat | | grep")


class TestRedirection:
    def test_redirect_overwrite(self):
        cmd = parse_one("nmap 10.0.0.1 > scan.txt")
        assert cmd.name == "nmap"
        assert cmd.args == ["10.0.0.1"]
        assert cmd.redirect == Redirect(target="scan.txt", append=False)

    def test_redirect_append(self):
        cmd = parse_one("echo data >> log.txt")
        assert cmd.args == ["data"]
        assert cmd.redirect == Redirect(target="log.txt", append=True)

    def test_redirect_missing_target_raises(self):
        with pytest.raises(ParseError):
            parse("echo hi >")

    def test_redirect_attaches_to_last_pipe_segment(self):
        cmd = parse_one("cat foo | grep bar > out.txt")
        assert cmd.redirect is None
        assert cmd.pipe_to.redirect == Redirect(target="out.txt", append=False)


# ---------------------------------------------------------------------------
# Parser — chaining
# ---------------------------------------------------------------------------


class TestChaining:
    def test_semicolon_chain(self):
        cmds = parse("cd /tmp; ls")
        assert len(cmds) == 2
        assert cmds[0].name == "cd"
        assert cmds[0].args == ["/tmp"]
        assert cmds[1].name == "ls"

    def test_and_chain(self):
        cmds = parse("cd /tmp && ls")
        assert [c.name for c in cmds] == ["cd", "ls"]

    def test_mixed_chain(self):
        cmds = parse("a; b && c")
        assert [c.name for c in cmds] == ["a", "b", "c"]

    def test_trailing_separator_ok(self):
        cmds = parse("ls;")
        assert len(cmds) == 1
        assert cmds[0].name == "ls"

    def test_each_statement_has_own_raw(self):
        cmds = parse("cd /tmp; ls -la")
        assert cmds[0].raw == "cd /tmp"
        assert cmds[1].raw == "ls -la"


# ---------------------------------------------------------------------------
# Tokenizer — direct
# ---------------------------------------------------------------------------


class TestTokenizer:
    def test_words_only(self):
        toks = tokenize("ls -l /tmp")
        assert [t.type for t in toks] == [TokenType.WORD] * 3
        assert [t.value for t in toks] == ["ls", "-l", "/tmp"]

    def test_operators(self):
        toks = tokenize("a | b > c >> d ; e && f")
        types = [t.type for t in toks]
        assert TokenType.PIPE in types
        assert TokenType.REDIRECT in types
        assert TokenType.REDIRECT_APPEND in types
        assert TokenType.SEMICOLON in types
        assert TokenType.AND in types

    def test_bare_ampersand_raises(self):
        with pytest.raises(ParseError):
            tokenize("foo &")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_register_and_get(self):
        reg = CommandRegistry()

        def fn(ctx, args):
            return "ok"

        reg.register("foo", fn, usage="foo", help_text="say ok", category="test")
        h = reg.get("foo")
        assert h is not None
        assert h.name == "foo"
        assert h.category == "test"
        assert h(CommandContext(), []) == "ok"

    def test_unknown_returns_none(self):
        reg = CommandRegistry()
        assert reg.get("nope") is None

    def test_aliases_resolve_to_primary(self):
        reg = CommandRegistry()
        reg.register("list", lambda c, a: "x", aliases=["ls", "dir"])
        assert reg.get("ls").name == "list"
        assert reg.get("dir").name == "list"

    def test_get_all_by_category(self):
        reg = CommandRegistry()
        reg.register("ls", lambda c, a: "", category="filesystem")
        reg.register("nmap", lambda c, a: "", category="network")
        reg.register("cat", lambda c, a: "", category="filesystem")
        names = sorted(h.name for h in reg.get_all_by_category("filesystem"))
        assert names == ["cat", "ls"]

    def test_completions_match_prefix(self):
        reg = CommandRegistry()
        for n in ("ls", "ln", "lsof", "cat", "cd"):
            reg.register(n, lambda c, a: "")
        assert reg.get_completions("l") == ["ln", "ls", "lsof"]
        assert reg.get_completions("c") == ["cat", "cd"]
        assert reg.get_completions("xyz") == []

    def test_completions_include_aliases(self):
        reg = CommandRegistry()
        reg.register("list", lambda c, a: "", aliases=["ls"])
        assert set(reg.get_completions("l")) == {"list", "ls"}

    def test_decorator_registers_handler(self):
        reg = CommandRegistry()

        @register_command(
            "hello",
            usage="hello",
            help_text="says hi",
            category="test",
            registry=reg,
        )
        def hi(ctx, args):
            return "hi"

        h = reg.get("hello")
        assert h is not None
        assert h(CommandContext(), []) == "hi"
        assert h.help_text == "says hi"

    def test_get_help_includes_metadata(self):
        reg = CommandRegistry()
        reg.register(
            "nmap",
            lambda c, a: "",
            usage="nmap [-p PORT] target",
            help_text="Network scanner",
            category="network",
            aliases=["scan"],
        )
        text = reg.get_help("nmap")
        assert "nmap" in text
        assert "Network scanner" in text
        assert "scan" in text
        assert "network" in text

    def test_get_help_unknown(self):
        reg = CommandRegistry()
        assert "no help" in reg.get_help("ghost").lower()

    def test_contains(self):
        reg = CommandRegistry()
        reg.register("foo", lambda c, a: "", aliases=["f"])
        assert "foo" in reg
        assert "f" in reg
        assert "bar" not in reg

    def test_context_carries_env(self):
        ctx = CommandContext(env={"USER": "neo"})
        assert ctx.env["USER"] == "neo"
