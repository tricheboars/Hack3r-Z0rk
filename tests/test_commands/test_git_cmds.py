"""Tests for hackerzork/commands/git_cmds.py."""
from __future__ import annotations

import hackerzork.commands.git_cmds  # register commands
from hackerzork.engine.command_registry import CommandContext, DEFAULT_REGISTRY
from hackerzork.systems.git_saves import GitSaveSystem
from hackerzork.systems.save_load import SaveSystem


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _FS:
    def to_dict(self): return {"type": "dir", "name": "/", "children": {}}
    def from_dict(self, d): pass
    def _get_node(self, path): return None

class _Net:
    discovered: list = []
    def to_dict(self): return {"discovered": [], "compromised": [], "nodes": {}}
    def load_state(self, d): pass

class _Heat:
    level = 5.0
    def to_dict(self): return {"level": 5.0, "decay_rate": 0.1, "current_threshold": "safe", "burn_count": 0, "stealth_modifiers": {}}
    def load_state(self, d): pass

class _Toolkit:
    def to_dict(self): return {"bandwidth_remaining_kb": 50000, "wallet_btc": 0.015, "shadow_enabled": False, "committed_kit": None, "kit_discount": False, "installed": {}}
    def load_state(self, d): pass

class _Comms:
    def to_dict(self): return {"player_handle": "anon", "story_flags": [], "channels": {}, "dm_threads": {}, "extra_contacts": {}}
    def load_state(self, d): pass

class _State:
    flags: list = []
    def to_dict(self): return {"flags": [], "chapter": 0, "timeline": []}
    def load_state(self, d): pass

class _History:
    def get_all(self): return []
    def add(self, cmd): pass

class _Events:
    def emit(self, *args, **kwargs): pass


def _ctx(heat_level: float = 5.0, with_git: bool = True) -> CommandContext:
    h = _Heat()
    h.level = heat_level
    return CommandContext(
        fs=_FS(),
        network=_Net(),
        heat=h,
        toolkit=_Toolkit(),
        comms=_Comms(),
        state=_State(),
        history=_History(),
        save_system=SaveSystem(),
        git_saves=GitSaveSystem() if with_git else None,
        events=_Events(),
        env={"USER": "user"},
    )


def _run(name: str, args: list[str], ctx: CommandContext) -> str:
    handler = DEFAULT_REGISTRY.get(name)
    assert handler is not None
    return handler(ctx, args)


# ---------------------------------------------------------------------------
# No git system
# ---------------------------------------------------------------------------

class TestNoGit:
    def test_status_no_git(self):
        ctx = _ctx(with_git=False)
        out = _run("git", ["status"], ctx)
        assert "not a git repository" in out

    def test_commit_no_git(self):
        ctx = _ctx(with_git=False)
        out = _run("git", ["commit", "-m", "test"], ctx)
        assert "not a git repository" in out

    def test_log_no_git(self):
        ctx = _ctx(with_git=False)
        out = _run("git", ["log"], ctx)
        assert "not a git repository" in out


# ---------------------------------------------------------------------------
# Bare git / help
# ---------------------------------------------------------------------------

class TestBareHelp:
    def test_no_args_shows_help(self):
        out = _run("git", [], _ctx())
        assert "commit" in out
        assert "log" in out
        assert "checkout" in out

    def test_unknown_subcommand(self):
        out = _run("git", ["flurble"], _ctx())
        assert "not a git command" in out

    def test_git_help(self):
        out = _run("git", ["help"], _ctx())
        assert "commit" in out


# ---------------------------------------------------------------------------
# git init
# ---------------------------------------------------------------------------

class TestGitInit:
    def test_init_always_works(self):
        out = _run("git", ["init"], _ctx())
        assert ".git" in out


# ---------------------------------------------------------------------------
# git status
# ---------------------------------------------------------------------------

class TestGitStatus:
    def test_status_shows_branch(self):
        out = _run("git", ["status"], _ctx())
        assert "On branch main" in out

    def test_status_shows_modified_state(self):
        out = _run("git", ["status"], _ctx())
        assert "modified" in out

    def test_status_high_heat_warning(self):
        out = _run("git", ["status"], _ctx(heat_level=60.0))
        assert "sk_watchdog" in out

    def test_status_low_heat_no_warning(self):
        out = _run("git", ["status"], _ctx(heat_level=5.0))
        assert "sk_watchdog" not in out


# ---------------------------------------------------------------------------
# git add
# ---------------------------------------------------------------------------

class TestGitAdd:
    def test_add_silent(self):
        ctx = _ctx()
        out = _run("git", ["add", "."], ctx)
        assert out == ""

    def test_add_sets_staged(self):
        ctx = _ctx()
        _run("git", ["add", "."], ctx)
        assert ctx.git_saves.staged is True


# ---------------------------------------------------------------------------
# git commit
# ---------------------------------------------------------------------------

class TestGitCommit:
    def test_commit_creates_entry(self):
        ctx = _ctx()
        out = _run("git", ["commit", "-m", "my save"], ctx)
        assert "my save" in out
        assert len(ctx.git_saves.player_commits()) == 1

    def test_commit_short_hash_in_output(self):
        ctx = _ctx()
        out = _run("git", ["commit", "-m", "checkpoint"], ctx)
        commit = ctx.git_saves.player_commits()[0]
        assert commit.short_hash in out

    def test_commit_no_message_error(self):
        ctx = _ctx()
        out = _run("git", ["commit", "-m"], ctx)
        assert "requires a value" in out or "usage" in out

    def test_commit_empty_message_error(self):
        ctx = _ctx()
        out = _run("git", ["commit", "-m", ""], ctx)
        assert "empty" in out

    def test_commit_message_too_long(self):
        ctx = _ctx()
        out = _run("git", ["commit", "-m", "x" * 121], ctx)
        assert "too long" in out

    def test_commit_double_dash_message(self):
        ctx = _ctx()
        out = _run("git", ["commit", "--message=named"], ctx)
        assert "named" in out

    def test_commit_high_heat_skynet_note(self):
        ctx = _ctx(heat_level=55.0)
        out = _run("git", ["commit", "-m", "test"], ctx)
        assert "sk_watchdog" in out

    def test_commit_medium_heat_trace_note(self):
        ctx = _ctx(heat_level=30.0)
        out = _run("git", ["commit", "-m", "test"], ctx)
        assert "sk_trace" in out

    def test_commit_no_save_system(self):
        ctx = _ctx()
        ctx.save_system = None
        out = _run("git", ["commit", "-m", "test"], ctx)
        assert "unavailable" in out


# ---------------------------------------------------------------------------
# git log
# ---------------------------------------------------------------------------

class TestGitLog:
    def test_log_always_shows_ghost(self):
        out = _run("git", ["log"], _ctx())
        assert "sk_stage_loader" in out

    def test_log_ghost_note(self):
        out = _run("git", ["log"], _ctx())
        assert "you did not make this commit" in out

    def test_log_oneline(self):
        ctx = _ctx()
        _run("git", ["commit", "-m", "save1"], ctx)
        out = _run("git", ["log", "--oneline"], ctx)
        assert "save1" in out
        assert "\n" in out  # multiple lines

    def test_log_oneline_shows_ghost(self):
        out = _run("git", ["log", "--oneline"], _ctx())
        assert "sk_stage_loader" in out

    def test_log_high_heat_ghost_injection(self):
        ctx = _ctx(heat_level=65.0)
        _run("git", ["commit", "-m", "first"], ctx)
        out = _run("git", ["log", "--oneline"], ctx)
        assert "d34db33f" in out

    def test_log_low_heat_no_injection(self):
        ctx = _ctx(heat_level=5.0)
        _run("git", ["commit", "-m", "first"], ctx)
        out = _run("git", ["log", "--oneline"], ctx)
        assert "d34db33f" not in out

    def test_log_player_commits_appear(self):
        ctx = _ctx()
        _run("git", ["commit", "-m", "alpha"], ctx)
        _run("git", ["commit", "-m", "beta"], ctx)
        out = _run("git", ["log"], ctx)
        assert "alpha" in out
        assert "beta" in out


# ---------------------------------------------------------------------------
# git checkout
# ---------------------------------------------------------------------------

class TestGitCheckout:
    def test_checkout_no_args_error(self):
        out = _run("git", ["checkout"], _ctx())
        assert "usage" in out or "requires" in out

    def test_checkout_bad_hash_error(self):
        out = _run("git", ["checkout", "deadbeef"], _ctx())
        assert "did not match" in out

    def test_checkout_ghost_commit_sealed(self):
        ctx = _ctx()
        ghost_hash = ctx.git_saves.commits[0].short_hash
        out = _run("git", ["checkout", ghost_hash], ctx)
        assert "sealed" in out or "you did not make this commit" in out.lower() or "no data to restore" in out

    def test_checkout_restores_commit(self):
        ctx = _ctx()
        _run("git", ["commit", "-m", "checkpoint"], ctx)
        commit = ctx.git_saves.player_commits()[0]
        out = _run("git", ["checkout", commit.short_hash], ctx)
        assert commit.short_hash in out

    def test_checkout_high_heat_warning(self):
        ctx = _ctx(heat_level=45.0)
        _run("git", ["commit", "-m", "test"], ctx)
        commit = ctx.git_saves.player_commits()[0]
        out = _run("git", ["checkout", commit.short_hash], ctx)
        assert "sk_watchdog" in out

    def test_checkout_empty_snapshot_warning(self):
        ctx = _ctx()
        # Force a commit with no snapshot by poking the system directly
        from hackerzork.systems.git_saves import GitCommit
        import time
        c = GitCommit(hash="aabbccdd" * 5, message="empty", author="user", timestamp="2026-01-01T00:00:00+00:00", snapshot={})
        ctx.git_saves._commits.append(c)
        out = _run("git", ["checkout", "aabbccd"], ctx)
        assert "snapshot is empty" in out or "nothing to restore" in out


# ---------------------------------------------------------------------------
# git stash
# ---------------------------------------------------------------------------

class TestGitStash:
    def test_stash_saves_state(self):
        ctx = _ctx()
        out = _run("git", ["stash"], ctx)
        assert "Saved working directory" in out
        assert ctx.git_saves.has_stash() is True

    def test_stash_pop_removes_stash(self):
        ctx = _ctx()
        _run("git", ["stash"], ctx)
        out = _run("git", ["stash", "pop"], ctx)
        assert "Dropped" in out
        assert ctx.git_saves.has_stash() is False

    def test_stash_pop_empty(self):
        out = _run("git", ["stash", "pop"], _ctx())
        assert "no stash" in out

    def test_stash_list_empty(self):
        out = _run("git", ["stash", "list"], _ctx())
        assert out == ""

    def test_stash_list_with_stash(self):
        ctx = _ctx()
        _run("git", ["stash"], ctx)
        out = _run("git", ["stash", "list"], ctx)
        assert "stash@{0}" in out

    def test_stash_drop(self):
        ctx = _ctx()
        _run("git", ["stash"], ctx)
        out = _run("git", ["stash", "drop"], ctx)
        assert "Dropped" in out
        assert ctx.git_saves.has_stash() is False

    def test_stash_drop_empty(self):
        out = _run("git", ["stash", "drop"], _ctx())
        assert "no stash" in out

    def test_stash_unknown_subcommand(self):
        out = _run("git", ["stash", "badcmd"], _ctx())
        assert "unknown" in out


# ---------------------------------------------------------------------------
# git diff
# ---------------------------------------------------------------------------

class TestGitDiff:
    def test_diff_shows_header(self):
        out = _run("git", ["diff"], _ctx())
        assert "diff --git" in out

    def test_diff_no_snapshot_binary_note(self):
        out = _run("git", ["diff"], _ctx())
        # Ghost commit has no snapshot so binary diff is shown
        assert "Binary files differ" in out or "game-state.dat" in out

    def test_diff_high_heat_trace_note(self):
        out = _run("git", ["diff"], _ctx(heat_level=60.0))
        assert "sk_trace" in out


# ---------------------------------------------------------------------------
# git remote
# ---------------------------------------------------------------------------

class TestGitRemote:
    def test_remote_v_shows_origin(self):
        out = _run("git", ["remote", "-v"], _ctx())
        assert "45.152.66.201" in out
        assert "origin" in out

    def test_remote_no_args_shows_origin(self):
        out = _run("git", ["remote"], _ctx())
        assert "45.152.66.201" in out

    def test_remote_did_not_configure(self):
        out = _run("git", ["remote", "-v"], _ctx())
        assert "you did not configure this remote" in out


# ---------------------------------------------------------------------------
# git blame
# ---------------------------------------------------------------------------

class TestGitBlame:
    def test_blame_no_args(self):
        out = _run("git", ["blame"], _ctx())
        assert "usage" in out

    def test_blame_etc_hosts(self):
        out = _run("git", ["blame", "/etc/hosts"], _ctx())
        assert "sk_stage_loader" in out
        assert "45.152.66.201" in out or "02:47" in out

    def test_blame_auth_log(self):
        out = _run("git", ["blame", "/var/log/auth.log"], _ctx())
        assert "sk_stage_loader" in out

    def test_blame_bashrc(self):
        out = _run("git", ["blame", "/home/user/.bashrc"], _ctx())
        assert "sk_stage_loader" in out

    def test_blame_unknown_file(self):
        out = _run("git", ["blame", "/nonexistent/file.txt"], _ctx())
        assert "fatal" in out


# ---------------------------------------------------------------------------
# git branch
# ---------------------------------------------------------------------------

class TestGitBranch:
    def test_branch_shows_main(self):
        out = _run("git", ["branch"], _ctx())
        assert "main" in out


# ---------------------------------------------------------------------------
# git push
# ---------------------------------------------------------------------------

class TestGitPush:
    def test_push_connection_refused(self):
        out = _run("git", ["push"], _ctx(heat_level=5.0))
        assert "45.152.66.201" in out
        assert "timed out" in out or "fatal" in out

    def test_push_high_heat_intercepted(self):
        out = _run("git", ["push"], _ctx(heat_level=80.0))
        assert "sk_watchdog" in out or "intercepted" in out

    def test_push_warning_message(self):
        out = _run("git", ["push"], _ctx(heat_level=5.0))
        assert "you did not configure this remote" in out


# ---------------------------------------------------------------------------
# git pull
# ---------------------------------------------------------------------------

class TestGitPull:
    def test_pull_up_to_date(self):
        out = _run("git", ["pull"], _ctx(heat_level=5.0))
        assert "up to date" in out

    def test_pull_high_heat_logged(self):
        out = _run("git", ["pull"], _ctx(heat_level=65.0))
        assert "sk_watchdog" in out or "logged" in out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestParseCommitMsg:
    def test_short_m_flag(self):
        from hackerzork.commands.git_cmds import _parse_commit_msg
        assert _parse_commit_msg(["-m", "hello"]) == "hello"

    def test_short_m_concat(self):
        from hackerzork.commands.git_cmds import _parse_commit_msg
        assert _parse_commit_msg(["-mhello"]) == "hello"

    def test_double_dash_message(self):
        from hackerzork.commands.git_cmds import _parse_commit_msg
        assert _parse_commit_msg(["--message=my msg"]) == "my msg"

    def test_no_m_flag(self):
        from hackerzork.commands.git_cmds import _parse_commit_msg
        assert _parse_commit_msg(["commit", "something"]) is None

    def test_m_without_value(self):
        from hackerzork.commands.git_cmds import _parse_commit_msg
        assert _parse_commit_msg(["-m"]) is None

    def test_multiword_message(self):
        from hackerzork.commands.git_cmds import _parse_commit_msg
        assert _parse_commit_msg(["-m", "save", "point", "one"]) == "save point one"
