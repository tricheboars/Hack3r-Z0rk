"""Tests for hackerzork/commands/system.py."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import hackerzork.commands.system  # ensure commands register
from hackerzork.engine.command_registry import CommandContext, CommandRegistry, DEFAULT_REGISTRY
from hackerzork.commands.system import (
    _OS_NAME,
    _OS_VERSION,
    _MACHINE,
    _KERNEL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    user: str = "user",
    hostname: str = "hackerzork",
    extra_env: dict | None = None,
    history_entries: list[str] | None = None,
    registry: CommandRegistry | None = None,
) -> CommandContext:
    env: dict[str, str] = {"USER": user, "HOSTNAME": hostname, "HOME": "/home/user", "CWD": "/home/user"}
    if extra_env:
        env.update(extra_env)

    hist = None
    if history_entries is not None:
        hist = MagicMock()
        hist.get_all.return_value = list(history_entries)

    return CommandContext(
        env=env,
        history=hist,
        registry=registry or DEFAULT_REGISTRY,
    )


def _run(cmd_name: str, ctx: CommandContext, args: list[str]) -> str:
    handler = DEFAULT_REGISTRY.get(cmd_name)
    assert handler is not None, f"Command '{cmd_name}' not registered"
    return handler(ctx, args)


# ---------------------------------------------------------------------------
# whoami
# ---------------------------------------------------------------------------


class TestWhoami:
    def test_default_user(self):
        ctx = _make_ctx()
        assert _run("whoami", ctx, []) == "user"

    def test_custom_user(self):
        ctx = _make_ctx(user="r00t")
        assert _run("whoami", ctx, []) == "r00t"

    def test_env_override(self):
        ctx = _make_ctx(extra_env={"USER": "ghost"})
        assert _run("whoami", ctx, []) == "ghost"


# ---------------------------------------------------------------------------
# uname
# ---------------------------------------------------------------------------


class TestUname:
    def test_no_args_returns_all(self):
        ctx = _make_ctx()
        out = _run("uname", ctx, [])
        assert _OS_NAME in out
        assert _OS_VERSION in out
        assert _MACHINE in out

    def test_dash_a_returns_all(self):
        ctx = _make_ctx()
        out = _run("uname", ctx, ["-a"])
        assert _OS_NAME in out
        assert _OS_VERSION in out
        assert "GNU/Linux" in out

    def test_dash_s_kernel_name(self):
        ctx = _make_ctx()
        out = _run("uname", ctx, ["-s"])
        assert out == _OS_NAME

    def test_dash_r_release(self):
        ctx = _make_ctx()
        out = _run("uname", ctx, ["-r"])
        assert out == _OS_VERSION

    def test_dash_m_machine(self):
        ctx = _make_ctx()
        out = _run("uname", ctx, ["-m"])
        assert out == _MACHINE

    def test_dash_n_hostname(self):
        ctx = _make_ctx(hostname="myhackbox")
        out = _run("uname", ctx, ["-n"])
        assert out == "myhackbox"

    def test_combined_flags(self):
        ctx = _make_ctx()
        out = _run("uname", ctx, ["-sr"])
        assert _OS_NAME in out
        assert _OS_VERSION in out


# ---------------------------------------------------------------------------
# ps
# ---------------------------------------------------------------------------


class TestPs:
    def test_no_args_shows_header(self):
        ctx = _make_ctx()
        out = _run("ps", ctx, [])
        assert "PID" in out
        assert "COMMAND" in out

    def test_shows_bash(self):
        ctx = _make_ctx()
        out = _run("ps", ctx, [])
        assert "bash" in out

    def test_shows_skynet_processes(self):
        ctx = _make_ctx()
        out = _run("ps", ctx, [])
        assert "sk_watchdog" in out
        assert "sk_comms" in out
        assert "sk_uplink" in out

    def test_skynet_ip_in_output(self):
        ctx = _make_ctx()
        out = _run("ps", ctx, [])
        # Same IP as /var/log/auth.log intrusion
        assert "45.152.66.201" in out

    def test_aux_flag(self):
        ctx = _make_ctx()
        out = _run("ps", ctx, ["aux"])
        assert "PID" in out
        assert "%CPU" in out

    def test_pid_1_is_init(self):
        ctx = _make_ctx()
        out = _run("ps", ctx, [])
        assert "/sbin/init" in out

    def test_narrow_format(self):
        ctx = _make_ctx()
        out = _run("ps", ctx, ["-e"])
        assert "PID" in out
        assert "CMD" in out

    def test_grep_pattern(self):
        ctx = _make_ctx()
        out = _run("ps", ctx, ["aux", "grep", "sk_"])
        assert "sk_watchdog" in out
        assert "/sbin/init" not in out

    def test_grep_no_match(self):
        ctx = _make_ctx()
        out = _run("ps", ctx, ["aux", "grep", "zzznothingxxx"])
        lines = [l for l in out.splitlines() if l.strip() and "PID" not in l]
        assert len(lines) == 0


# ---------------------------------------------------------------------------
# top
# ---------------------------------------------------------------------------


class TestTop:
    def test_shows_header(self):
        ctx = _make_ctx()
        out = _run("top", ctx, [])
        assert "Linux" in out or "6.6.6" in out
        assert "Tasks:" in out
        assert "Cpu" in out
        assert "Mem:" in out

    def test_shows_process_table(self):
        ctx = _make_ctx()
        out = _run("top", ctx, [])
        assert "PID" in out
        assert "COMMAND" in out

    def test_skynet_in_top(self):
        ctx = _make_ctx()
        out = _run("top", ctx, [])
        assert "sk_watchdog" in out
        assert "sk_comms" in out

    def test_pid_column_present(self):
        ctx = _make_ctx()
        out = _run("top", ctx, [])
        # PID 891 should appear
        assert "891" in out

    def test_load_average_present(self):
        ctx = _make_ctx()
        out = _run("top", ctx, [])
        assert "load average" in out


# ---------------------------------------------------------------------------
# man
# ---------------------------------------------------------------------------


class TestMan:
    def test_no_args(self):
        ctx = _make_ctx()
        out = _run("man", ctx, [])
        assert "manual" in out.lower() or "want" in out.lower()

    def test_known_command(self):
        ctx = _make_ctx()
        out = _run("man", ctx, ["ls"])
        assert "ls" in out.lower()

    def test_unknown_command(self):
        ctx = _make_ctx()
        out = _run("man", ctx, ["zzznothingxxx"])
        assert "No manual entry" in out

    def test_uses_ctx_registry(self):
        # Build a custom registry with a fake command
        reg = CommandRegistry()
        reg.register("fake_cmd", lambda ctx, args: "", usage="fake_cmd", help_text="Fake command")
        ctx = _make_ctx(registry=reg)
        out = _run("man", ctx, ["fake_cmd"])
        assert "fake_cmd" in out
        assert "Fake command" in out

    def test_falls_back_to_default_registry(self):
        ctx = _make_ctx()
        ctx.registry = None
        # whoami is in DEFAULT_REGISTRY
        out = _run("man", ctx, ["whoami"])
        assert "whoami" in out.lower()

    def test_man_for_system_commands(self):
        ctx = _make_ctx()
        for cmd in ["whoami", "uname", "ps", "top", "date", "echo", "env", "export", "alias", "clear"]:
            out = _run("man", ctx, [cmd])
            assert cmd in out.lower(), f"man {cmd} didn't mention '{cmd}'"


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


class TestHistory:
    def test_empty_history(self):
        ctx = _make_ctx(history_entries=[])
        out = _run("history", ctx, [])
        # No VFS, no session entries → empty output (gap only appears with prior history)
        assert out == ""

    def test_shows_entries(self):
        ctx = _make_ctx(history_entries=["ls", "cd /tmp", "cat file.txt"])
        out = _run("history", ctx, [])
        assert "ls" in out
        assert "cd /tmp" in out
        assert "cat file.txt" in out

    def test_numbered_output(self):
        ctx = _make_ctx(history_entries=["ls", "pwd"])
        out = _run("history", ctx, [])
        # Without VFS, there's no prior history → no gap → just the 2 session entries
        lines = [l for l in out.strip().splitlines() if l.strip()]
        assert len(lines) == 2
        assert lines[0].strip().split()[0].isdigit()

    def test_limit_argument(self):
        ctx = _make_ctx(history_entries=["a", "b", "c", "d", "e"])
        out = _run("history", ctx, ["3"])
        lines = [l for l in out.strip().splitlines() if l.strip()]
        assert len(lines) == 3
        assert "c" in out
        assert "d" in out
        assert "e" in out

    def test_invalid_limit(self):
        ctx = _make_ctx(history_entries=["ls"])
        out = _run("history", ctx, ["abc"])
        assert "numeric" in out.lower()

    def test_env_fallback(self):
        ctx = _make_ctx()  # no history object
        ctx.env["HISTORY"] = "cmd1\ncmd2\ncmd3"
        out = _run("history", ctx, [])
        assert "cmd1" in out
        assert "cmd3" in out


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_returns_ansi_clear(self):
        ctx = _make_ctx()
        out = _run("clear", ctx, [])
        assert "\033[2J" in out

    def test_home_cursor(self):
        ctx = _make_ctx()
        out = _run("clear", ctx, [])
        assert "\033[H" in out


# ---------------------------------------------------------------------------
# env
# ---------------------------------------------------------------------------


class TestEnv:
    def test_shows_env_vars(self):
        ctx = _make_ctx(extra_env={"FOO": "bar", "BAZ": "qux"})
        out = _run("env", ctx, [])
        assert "FOO=bar" in out
        assert "BAZ=qux" in out

    def test_empty_env(self):
        # env now always injects _SK_SID — it's a system-level variable
        ctx = CommandContext(env={})
        out = _run("env", ctx, [])
        assert "_SK_SID" in out

    def test_sorted_output(self):
        ctx = _make_ctx(extra_env={"ZZZ": "1", "AAA": "2"})
        out = _run("env", ctx, [])
        lines = out.strip().splitlines()
        keys = [l.split("=")[0] for l in lines]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


class TestExport:
    def test_set_new_var(self):
        ctx = _make_ctx()
        _run("export", ctx, ["MYVAR=hello"])
        assert ctx.env.get("MYVAR") == "hello"

    def test_set_multiple_vars(self):
        ctx = _make_ctx()
        _run("export", ctx, ["A=1", "B=2"])
        assert ctx.env.get("A") == "1"
        assert ctx.env.get("B") == "2"

    def test_override_existing(self):
        ctx = _make_ctx()
        ctx.env["X"] = "old"
        _run("export", ctx, ["X=new"])
        assert ctx.env.get("X") == "new"

    def test_no_args_prints_env(self):
        ctx = _make_ctx(extra_env={"MYVAR": "hello"})
        out = _run("export", ctx, [])
        assert "MYVAR=hello" in out

    def test_invalid_identifier(self):
        ctx = _make_ctx()
        out = _run("export", ctx, ["123BAD=value"])
        assert "not a valid identifier" in out

    def test_value_with_equals(self):
        ctx = _make_ctx()
        _run("export", ctx, ["URL=http://example.com/path?a=b"])
        assert ctx.env.get("URL") == "http://example.com/path?a=b"


# ---------------------------------------------------------------------------
# alias
# ---------------------------------------------------------------------------


class TestAlias:
    def test_no_aliases_empty(self):
        ctx = _make_ctx()
        out = _run("alias", ctx, [])
        assert out == ""

    def test_set_alias(self):
        ctx = _make_ctx()
        _run("alias", ctx, ["ll=ls -la"])
        assert ctx.env.get("ALIAS_ll") == "ls -la"

    def test_set_alias_with_quotes(self):
        ctx = _make_ctx()
        _run("alias", ctx, ["la='ls -la'"])
        assert ctx.env.get("ALIAS_la") == "ls -la"

    def test_show_all_aliases(self):
        ctx = _make_ctx(extra_env={"ALIAS_ll": "ls -la", "ALIAS_la": "ls -A"})
        out = _run("alias", ctx, [])
        assert "alias ll='ls -la'" in out
        assert "alias la='ls -A'" in out

    def test_show_specific_alias(self):
        ctx = _make_ctx(extra_env={"ALIAS_ll": "ls -la"})
        out = _run("alias", ctx, ["ll"])
        assert "alias ll='ls -la'" in out

    def test_missing_alias(self):
        ctx = _make_ctx()
        out = _run("alias", ctx, ["nosuchname"])
        assert "not found" in out


# ---------------------------------------------------------------------------
# echo
# ---------------------------------------------------------------------------


class TestEcho:
    def test_basic(self):
        ctx = _make_ctx()
        assert _run("echo", ctx, ["hello", "world"]) == "hello world"

    def test_empty(self):
        ctx = _make_ctx()
        assert _run("echo", ctx, []) == ""

    def test_single_word(self):
        ctx = _make_ctx()
        assert _run("echo", ctx, ["hello"]) == "hello"

    def test_dash_e_newline(self):
        ctx = _make_ctx()
        out = _run("echo", ctx, ["-e", "line1\\nline2"])
        assert "line1\nline2" in out

    def test_dash_e_tab(self):
        ctx = _make_ctx()
        out = _run("echo", ctx, ["-e", "a\\tb"])
        assert "a\tb" in out

    def test_dash_n_no_trailing_newline(self):
        # -n just returns text without appending — same as normal (shell adds newline)
        ctx = _make_ctx()
        out = _run("echo", ctx, ["-n", "hello"])
        assert out == "hello"

    def test_special_chars_no_e(self):
        ctx = _make_ctx()
        out = _run("echo", ctx, ["\\n"])
        assert out == "\\n"  # not interpreted without -e


# ---------------------------------------------------------------------------
# date
# ---------------------------------------------------------------------------


class TestDate:
    def test_returns_string(self):
        ctx = _make_ctx()
        out = _run("date", ctx, [])
        assert len(out) > 5

    def test_contains_year(self):
        from datetime import datetime
        ctx = _make_ctx()
        out = _run("date", ctx, [])
        assert str(datetime.now().year) in out

    def test_format_year(self):
        from datetime import datetime
        ctx = _make_ctx()
        out = _run("date", ctx, ["+%Y"])
        assert out == str(datetime.now().year)

    def test_format_custom(self):
        ctx = _make_ctx()
        out = _run("date", ctx, ["+%Y-%m-%d"])
        # Should match YYYY-MM-DD pattern
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", out)

    def test_epoch_seconds(self):
        import time
        ctx = _make_ctx()
        out = _run("date", ctx, ["+%s"])
        assert out.isdigit()
        assert abs(int(out) - int(time.time())) < 5


# ---------------------------------------------------------------------------
# df
# ---------------------------------------------------------------------------


class TestDf:
    def test_shows_filesystem_header(self):
        ctx = _make_ctx()
        out = _run("df", ctx, [])
        assert "Filesystem" in out
        assert "Mounted on" in out

    def test_shows_root_mount(self):
        ctx = _make_ctx()
        out = _run("df", ctx, [])
        assert "/" in out
        assert "/dev/sda1" in out

    def test_human_readable(self):
        ctx = _make_ctx()
        out = _run("df", ctx, ["-h"])
        assert "G" in out or "M" in out

    def test_toolkit_bandwidth_entry(self):
        from unittest.mock import MagicMock
        tk = MagicMock()
        tk.bandwidth_remaining_kb = 40_000
        ctx = _make_ctx()
        ctx.toolkit = tk
        out = _run("df", ctx, [])
        assert "shadow" in out or "bw" in out


# ---------------------------------------------------------------------------
# du
# ---------------------------------------------------------------------------


class TestDu:
    def test_summarize_file(self):
        from unittest.mock import MagicMock
        fs = MagicMock()
        node = MagicMock()
        node.is_dir = False
        node.content = "hello world"
        node.children = {}
        fs._get_node.return_value = node
        ctx = CommandContext(fs=fs, env={"CWD": "/home/user", "HOME": "/home/user"})
        out = _run("du", ctx, ["-s", "/home/user/test.txt"])
        assert "test.txt" in out

    def test_missing_path(self):
        from unittest.mock import MagicMock
        fs = MagicMock()
        fs._get_node.side_effect = Exception("not found")
        ctx = CommandContext(fs=fs, env={"CWD": "/home/user", "HOME": "/home/user"})
        out = _run("du", ctx, ["/no/such/path"])
        assert "cannot access" in out or "no/such/path" in out

    def test_no_fs(self):
        ctx = CommandContext(env={"CWD": "/home/user"})
        out = _run("du", ctx, [])
        assert "not available" in out


# ---------------------------------------------------------------------------
# free
# ---------------------------------------------------------------------------


class TestFree:
    def test_shows_mem_line(self):
        ctx = _make_ctx()
        out = _run("free", ctx, [])
        assert "Mem:" in out
        assert "Swap:" in out

    def test_human_readable(self):
        ctx = _make_ctx()
        out = _run("free", ctx, ["-h"])
        assert "Gi" in out or "Mi" in out


# ---------------------------------------------------------------------------
# lscpu
# ---------------------------------------------------------------------------


class TestLscpu:
    def test_shows_architecture(self):
        ctx = _make_ctx()
        out = _run("lscpu", ctx, [])
        assert "x86_64" in out

    def test_shows_cpu_model(self):
        ctx = _make_ctx()
        out = _run("lscpu", ctx, [])
        assert "Intel" in out or "CPU" in out

    def test_shows_cores(self):
        ctx = _make_ctx()
        out = _run("lscpu", ctx, [])
        assert "Core(s)" in out


# ---------------------------------------------------------------------------
# lsblk
# ---------------------------------------------------------------------------


class TestLsblk:
    def test_shows_sda(self):
        ctx = _make_ctx()
        out = _run("lsblk", ctx, [])
        assert "sda" in out

    def test_shows_mount(self):
        ctx = _make_ctx()
        out = _run("lsblk", ctx, [])
        assert "/" in out

    def test_shows_disk_type(self):
        ctx = _make_ctx()
        out = _run("lsblk", ctx, [])
        assert "disk" in out


# ---------------------------------------------------------------------------
# id
# ---------------------------------------------------------------------------


class TestId:
    def test_default_user(self):
        ctx = _make_ctx()
        out = _run("id", ctx, [])
        assert "uid=1000(user)" in out
        assert "gid=1000(user)" in out

    def test_custom_user(self):
        ctx = _make_ctx(user="ghost")
        out = _run("id", ctx, [])
        assert "ghost" in out

    def test_shows_groups(self):
        ctx = _make_ctx()
        out = _run("id", ctx, [])
        assert "groups=" in out
        assert "sudo" in out


# ---------------------------------------------------------------------------
# groups
# ---------------------------------------------------------------------------


class TestGroups:
    def test_shows_current_user(self):
        ctx = _make_ctx()
        out = _run("groups", ctx, [])
        assert "user" in out

    def test_shows_sudo(self):
        ctx = _make_ctx()
        out = _run("groups", ctx, [])
        assert "sudo" in out


# ---------------------------------------------------------------------------
# kill
# ---------------------------------------------------------------------------


class TestKill:
    def test_no_args(self):
        ctx = _make_ctx()
        out = _run("kill", ctx, [])
        assert "Usage" in out

    def test_nonexistent_pid(self):
        ctx = _make_ctx()
        out = _run("kill", ctx, ["99999"])
        assert "No such process" in out

    def test_kill_skynet_pid(self):
        ctx = _make_ctx()
        out = _run("kill", ctx, ["891"])
        assert "Killed" in out or "sk_watchdog" in out

    def test_kill_skynet_adds_heat(self):
        heat = MagicMock()
        ctx = _make_ctx()
        ctx.heat = heat
        _run("kill", ctx, ["891"])
        heat.add_heat.assert_called()

    def test_kill_skynet_emits_event(self):
        events = MagicMock()
        ctx = _make_ctx()
        ctx.events = events
        _run("kill", ctx, ["891"])
        calls = [c.args[0] for c in events.emit.call_args_list]
        assert "skynet_process_killed" in calls

    def test_kill_root_process_denied(self):
        ctx = _make_ctx()
        out = _run("kill", ctx, ["183"])  # sshd
        assert "not permitted" in out.lower()

    def test_kill_skynet_respawns(self):
        ctx = _make_ctx()
        _run("kill", ctx, ["891"])
        # The process should respawn (removed from killed set)
        from hackerzork.commands.system import _killed_pids
        assert 891 not in _killed_pids(ctx)

    def test_kill_invalid_pid(self):
        ctx = _make_ctx()
        out = _run("kill", ctx, ["notapid"])
        assert "arguments must be" in out or "notapid" in out


# ---------------------------------------------------------------------------
# killall
# ---------------------------------------------------------------------------


class TestKillall:
    def test_no_args(self):
        ctx = _make_ctx()
        out = _run("killall", ctx, [])
        assert "Usage" in out

    def test_unknown_process(self):
        ctx = _make_ctx()
        out = _run("killall", ctx, ["zzznoproc"])
        assert "no process found" in out

    def test_kill_skynet_by_name(self):
        ctx = _make_ctx()
        out = _run("killall", ctx, ["sk_watchdog"])
        assert "Killed" in out or "sk_watchdog" in out

    def test_kill_root_process_denied(self):
        ctx = _make_ctx()
        out = _run("killall", ctx, ["nginx"])
        assert "not permitted" in out.lower()


# ---------------------------------------------------------------------------
# pstree
# ---------------------------------------------------------------------------


class TestPstree:
    def test_shows_init(self):
        ctx = _make_ctx()
        out = _run("pstree", ctx, [])
        assert "init" in out

    def test_shows_skynet(self):
        ctx = _make_ctx()
        out = _run("pstree", ctx, [])
        assert "sk_watchdog" in out

    def test_pid_flag(self):
        ctx = _make_ctx()
        out = _run("pstree", ctx, ["-p"])
        assert "891" in out
        assert "892" in out


# ---------------------------------------------------------------------------
# htop
# ---------------------------------------------------------------------------


class TestHtop:
    def test_shows_header(self):
        ctx = _make_ctx()
        out = _run("htop", ctx, [])
        assert "Linux" in out or "6.6.6" in out

    def test_shows_note(self):
        ctx = _make_ctx()
        out = _run("htop", ctx, [])
        assert "snapshot" in out.lower() or "interactive" in out.lower()

    def test_shows_skynet(self):
        ctx = _make_ctx()
        out = _run("htop", ctx, [])
        assert "sk_watchdog" in out


# ---------------------------------------------------------------------------
# passwd
# ---------------------------------------------------------------------------


class TestPasswd:
    def test_shows_locked_message(self):
        ctx = _make_ctx()
        out = _run("passwd", ctx, [])
        assert "Authentication token manipulation error" in out

    def test_mentions_user(self):
        ctx = _make_ctx(user="ghost")
        out = _run("passwd", ctx, [])
        assert "ghost" in out


# ---------------------------------------------------------------------------
# Root-required stubs
# ---------------------------------------------------------------------------


class TestRootRequired:
    def test_useradd(self):
        ctx = _make_ctx()
        out = _run("useradd", ctx, ["newuser"])
        assert "Permission denied" in out or "root" in out.lower()

    def test_userdel(self):
        ctx = _make_ctx()
        out = _run("userdel", ctx, ["user"])
        assert "Permission denied" in out or "root" in out.lower()

    def test_usermod(self):
        ctx = _make_ctx()
        out = _run("usermod", ctx, ["-aG", "sudo", "user"])
        assert "Permission denied" in out or "root" in out.lower()

    def test_groupadd(self):
        ctx = _make_ctx()
        out = _run("groupadd", ctx, ["hackers"])
        assert "Permission denied" in out or "root" in out.lower()

    def test_groupdel(self):
        ctx = _make_ctx()
        out = _run("groupdel", ctx, ["hackers"])
        assert "Permission denied" in out or "root" in out.lower()


# ---------------------------------------------------------------------------
# Killed PIDs filter in ps/top
# ---------------------------------------------------------------------------


class TestKilledFilter:
    def test_killed_pid_absent_from_ps(self):
        ctx = _make_ctx()
        ctx.env["_KILLED_PIDS"] = "891"
        out = _run("ps", ctx, [])
        # sk_watchdog (891) should not appear
        assert "sk_watchdog" not in out

    def test_killed_pid_absent_from_top(self):
        ctx = _make_ctx()
        ctx.env["_KILLED_PIDS"] = "891"
        out = _run("top", ctx, [])
        assert "sk_watchdog" not in out

    def test_non_killed_still_visible(self):
        ctx = _make_ctx()
        ctx.env["_KILLED_PIDS"] = "891"
        out = _run("ps", ctx, [])
        assert "sk_comms" in out  # 892 not killed
