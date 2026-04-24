"""Tests for hackerzork.commands.filesystem."""
from __future__ import annotations

import time

import pytest

import hackerzork.commands.filesystem  # noqa: F401 — registers commands as side-effect
from hackerzork.commands.filesystem import (
    _apply_symbolic_chmod,
    _extract_strings,
    _parse_flags,
    _parse_n_flag,
    _resolve,
    cmd_cat,
    cmd_cd,
    cmd_chmod,
    cmd_cp,
    cmd_file,
    cmd_find,
    cmd_grep,
    cmd_head,
    cmd_ln,
    cmd_ls,
    cmd_mkdir,
    cmd_mv,
    cmd_pwd,
    cmd_recover,
    cmd_rm,
    cmd_stat,
    cmd_strings,
    cmd_tail,
    cmd_touch,
    cmd_wc,
    cmd_xxd,
)
from hackerzork.engine.command_registry import CommandContext
from hackerzork.systems.virtual_fs import VirtualFS

# ---------------------------------------------------------------------------
# Shared template and fixture
# ---------------------------------------------------------------------------

_TEMPLATE = {
    "/home/user": {
        "_meta": {"permissions": "755", "owner": "user"},
        "hello.txt": {"content": "hello world\nline two\nline three\n", "permissions": "644", "owner": "user"},
        "empty.txt": {"content": "", "permissions": "644", "owner": "user"},
        "secret.enc": {"content": "SECRETBINARYDATA\nmore secret data\n", "encrypted": True, "permissions": "600", "owner": "user"},
        "zork": {"content": "ELF binary payload", "binary": True, "permissions": "755", "owner": "user"},
        ".bashrc": {"content": "export PATH=/usr/bin:$PATH\n", "permissions": "644", "owner": "user"},
        "scripts/": {
            "_meta": {"permissions": "755", "owner": "user"},
            "run.sh": {"content": "#!/bin/bash\necho hello\n", "permissions": "755", "owner": "user"},
            "test.py": {"content": "print('hello')\n", "permissions": "644", "owner": "user"},
        },
        "link.txt": {"link_target": "/home/user/hello.txt"},
        "dead_link": {"link_target": "/nonexistent/path"},
    },
    "/etc": {
        "hosts": {"content": "127.0.0.1 localhost\n10.0.0.1 target\n", "owner": "root"},
        "shadow": {"content": "root:$6$abc:18000:0:99999:7:::\n", "encrypted": True, "owner": "root"},
    },
    "/tmp": {},
}


def make_ctx(**env_extras) -> CommandContext:
    fs = VirtualFS(template=_TEMPLATE)
    env = {
        "CWD": "/home/user",
        "HOME": "/home/user",
        "OLDPWD": "/",
        "USER": "user",
    }
    env.update(env_extras)
    return CommandContext(fs=fs, env=env)


# ---------------------------------------------------------------------------
# Helper: _resolve
# ---------------------------------------------------------------------------


class TestResolve:
    def test_absolute_path_unchanged(self):
        ctx = make_ctx()
        assert _resolve(ctx, "/etc/hosts") == "/etc/hosts"

    def test_relative_path_resolved_from_cwd(self):
        ctx = make_ctx()
        assert _resolve(ctx, "hello.txt") == "/home/user/hello.txt"

    def test_dotdot_resolves(self):
        ctx = make_ctx()
        assert _resolve(ctx, "../user") == "/home/user"

    def test_tilde_resolves_to_home(self):
        ctx = make_ctx()
        assert _resolve(ctx, "~") == "/home/user"

    def test_tilde_prefix_resolves(self):
        ctx = make_ctx()
        assert _resolve(ctx, "~/notes") == "/home/user/notes"


# ---------------------------------------------------------------------------
# Helper: _parse_flags
# ---------------------------------------------------------------------------


class TestParseFlags:
    def test_short_flags_split(self):
        flags, pos = _parse_flags(["-la", "somedir"])
        assert "l" in flags and "a" in flags
        assert pos == ["somedir"]

    def test_long_flag_parsed(self):
        flags, pos = _parse_flags(["--shred", "file.txt"])
        assert "shred" in flags
        assert pos == ["file.txt"]

    def test_numeric_arg_is_positional(self):
        flags, pos = _parse_flags(["-10"])
        assert pos == ["-10"]
        assert not flags

    def test_dashdash_stops_flag_parsing(self):
        flags, pos = _parse_flags(["--", "-l"])
        assert not flags
        assert pos == ["-l"]


# ---------------------------------------------------------------------------
# Helper: _apply_symbolic_chmod
# ---------------------------------------------------------------------------


class TestSymbolicChmod:
    def test_add_exec_to_user(self):
        assert _apply_symbolic_chmod("u+x", "644") == "744"

    def test_remove_write_from_group_other(self):
        assert _apply_symbolic_chmod("go-w", "755") == "755"  # g and o already have no write bit, stays 755

    def test_remove_write_that_exists(self):
        result = _apply_symbolic_chmod("u-w", "644")
        assert result == "444"

    def test_set_mode_equals(self):
        result = _apply_symbolic_chmod("u=rw", "755")
        assert result == "655"

    def test_all_shorthand(self):
        result = _apply_symbolic_chmod("a+x", "644")
        assert result == "755"

    def test_multiple_clauses(self):
        result = _apply_symbolic_chmod("u+x,go-r", "644")
        # u: 6 + x = 7; g: 4 - r = 0 → wait: g=4 (100), -r removes bit 2 → 0 (000)
        # o: 4 - r → 0
        assert result == "700"

    def test_octal_passthrough(self):
        result = _apply_symbolic_chmod("u+x", "755")
        assert result == "755"  # already has exec


# ---------------------------------------------------------------------------
# pwd
# ---------------------------------------------------------------------------


class TestPwd:
    def test_returns_cwd(self):
        ctx = make_ctx()
        assert cmd_pwd(ctx, []) == "/home/user"

    def test_returns_changed_cwd(self):
        ctx = make_ctx(CWD="/etc")
        assert cmd_pwd(ctx, []) == "/etc"


# ---------------------------------------------------------------------------
# cd
# ---------------------------------------------------------------------------


class TestCd:
    def test_cd_absolute(self):
        ctx = make_ctx()
        result = cmd_cd(ctx, ["/etc"])
        assert result == ""
        assert ctx.env["CWD"] == "/etc"

    def test_cd_relative(self):
        ctx = make_ctx()
        result = cmd_cd(ctx, ["scripts"])
        assert result == ""
        assert ctx.env["CWD"] == "/home/user/scripts"

    def test_cd_no_args_goes_home(self):
        ctx = make_ctx(CWD="/etc")
        cmd_cd(ctx, [])
        assert ctx.env["CWD"] == "/home/user"

    def test_cd_dash_goes_to_oldpwd(self):
        ctx = make_ctx(CWD="/etc", OLDPWD="/home/user")
        cmd_cd(ctx, ["-"])
        assert ctx.env["CWD"] == "/home/user"

    def test_cd_sets_oldpwd(self):
        ctx = make_ctx()
        cmd_cd(ctx, ["/etc"])
        assert ctx.env["OLDPWD"] == "/home/user"

    def test_cd_nonexistent_error(self):
        ctx = make_ctx()
        result = cmd_cd(ctx, ["doesnotexist"])
        assert "No such file or directory" in result

    def test_cd_into_file_error(self):
        ctx = make_ctx()
        result = cmd_cd(ctx, ["hello.txt"])
        assert "Not a directory" in result


# ---------------------------------------------------------------------------
# ls
# ---------------------------------------------------------------------------


class TestLs:
    def test_ls_lists_visible_files(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, [])
        assert "hello.txt" in result
        assert "scripts" in result

    def test_ls_hides_dotfiles(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, [])
        assert ".bashrc" not in result

    def test_ls_a_shows_dotfiles(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, ["-a"])
        assert ".bashrc" in result

    def test_ls_l_shows_permissions(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, ["-l"])
        assert "rw-r--r--" in result  # 644

    def test_ls_l_shows_owner(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, ["-l"])
        assert "user" in result

    def test_ls_l_shows_symlink(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, ["-l"])
        assert "link.txt -> /home/user/hello.txt" in result

    def test_ls_short_shows_dir_slash(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, [])
        assert "scripts/" in result

    def test_ls_short_shows_symlink_at(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, [])
        assert "link.txt@" in result

    def test_ls_specific_path(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, ["/etc"])
        assert "hosts" in result

    def test_ls_nonexistent_error(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, ["ghost"])
        assert "No such file or directory" in result

    def test_ls_single_file(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, ["hello.txt"])
        assert "hello.txt" in result

    def test_ls_R_recursive(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, ["-R"])
        assert "scripts/" in result or "/home/user/scripts:" in result
        assert "run.sh" in result

    def test_ls_la_combined(self):
        ctx = make_ctx()
        result = cmd_ls(ctx, ["-la"])
        assert ".bashrc" in result
        assert "rw-r--r--" in result


# ---------------------------------------------------------------------------
# cat
# ---------------------------------------------------------------------------


class TestCat:
    def test_cat_plain_file(self):
        ctx = make_ctx()
        result = cmd_cat(ctx, ["hello.txt"])
        assert "hello world" in result
        assert "line two" in result

    def test_cat_encrypted_shows_hex(self):
        ctx = make_ctx()
        result = cmd_cat(ctx, ["secret.enc"])
        assert "[ENCRYPTED — binary content]" in result
        assert "00000000" in result  # hex offset

    def test_cat_binary_shows_message(self):
        ctx = make_ctx()
        result = cmd_cat(ctx, ["zork"])
        assert "Binary file" in result
        assert "xxd" in result

    def test_cat_directory_error(self):
        ctx = make_ctx()
        result = cmd_cat(ctx, ["scripts"])
        assert "Is a directory" in result

    def test_cat_nonexistent_error(self):
        ctx = make_ctx()
        result = cmd_cat(ctx, ["ghost.txt"])
        assert "No such file or directory" in result

    def test_cat_n_numbers_lines(self):
        ctx = make_ctx()
        result = cmd_cat(ctx, ["-n", "hello.txt"])
        assert "1  hello world" in result
        assert "2  line two" in result

    def test_cat_multiple_files_concatenated(self):
        ctx = make_ctx()
        result = cmd_cat(ctx, ["hello.txt", "empty.txt"])
        assert "hello world" in result

    def test_cat_no_args_empty(self):
        ctx = make_ctx()
        assert cmd_cat(ctx, []) == ""


# ---------------------------------------------------------------------------
# head
# ---------------------------------------------------------------------------


class TestHead:
    def test_head_default_10(self):
        ctx = make_ctx()
        result = cmd_head(ctx, ["hello.txt"])
        assert "hello world" in result
        assert "line two" in result

    def test_head_n_2(self):
        ctx = make_ctx()
        result = cmd_head(ctx, ["-n", "2", "hello.txt"])
        lines = result.splitlines()
        assert len(lines) == 2
        assert lines[0] == "hello world"
        assert lines[1] == "line two"

    def test_head_short_form(self):
        ctx = make_ctx()
        result = cmd_head(ctx, ["-1", "hello.txt"])
        assert result == "hello world"

    def test_head_encrypted(self):
        ctx = make_ctx()
        result = cmd_head(ctx, ["secret.enc"])
        assert "[ENCRYPTED" in result

    def test_head_binary(self):
        ctx = make_ctx()
        result = cmd_head(ctx, ["zork"])
        assert "Binary file" in result

    def test_head_nonexistent(self):
        ctx = make_ctx()
        result = cmd_head(ctx, ["ghost.txt"])
        assert "No such file or directory" in result


# ---------------------------------------------------------------------------
# tail
# ---------------------------------------------------------------------------


class TestTail:
    def test_tail_default_returns_all_short_file(self):
        ctx = make_ctx()
        result = cmd_tail(ctx, ["hello.txt"])
        assert "line three" in result

    def test_tail_n_1_returns_last(self):
        ctx = make_ctx()
        result = cmd_tail(ctx, ["-n", "1", "hello.txt"])
        assert result == "line three"

    def test_tail_encrypted(self):
        ctx = make_ctx()
        result = cmd_tail(ctx, ["secret.enc"])
        assert "[ENCRYPTED" in result

    def test_tail_nonexistent(self):
        ctx = make_ctx()
        result = cmd_tail(ctx, ["ghost.txt"])
        assert "No such file or directory" in result


# ---------------------------------------------------------------------------
# wc
# ---------------------------------------------------------------------------


class TestWc:
    def test_wc_all_counts(self):
        ctx = make_ctx()
        result = cmd_wc(ctx, ["hello.txt"])
        # "hello world\nline two\nline three\n" → 3 lines, 6 words
        parts = result.split()
        assert parts[0] == "3"   # lines
        assert parts[1] == "6"   # words
        assert parts[3] == "hello.txt"

    def test_wc_l_lines_only(self):
        ctx = make_ctx()
        result = cmd_wc(ctx, ["-l", "hello.txt"])
        assert result == "3 hello.txt"

    def test_wc_w_words_only(self):
        ctx = make_ctx()
        result = cmd_wc(ctx, ["-w", "hello.txt"])
        assert result == "6 hello.txt"

    def test_wc_c_bytes(self):
        ctx = make_ctx()
        result = cmd_wc(ctx, ["-c", "hello.txt"])
        content = "hello world\nline two\nline three\n"
        assert result == f"{len(content.encode())} hello.txt"

    def test_wc_nonexistent(self):
        ctx = make_ctx()
        result = cmd_wc(ctx, ["ghost.txt"])
        assert "No such file or directory" in result

    def test_wc_directory_error(self):
        ctx = make_ctx()
        result = cmd_wc(ctx, ["scripts"])
        assert "Is a directory" in result


# ---------------------------------------------------------------------------
# mkdir
# ---------------------------------------------------------------------------


class TestMkdir:
    def test_mkdir_creates_dir(self):
        ctx = make_ctx()
        cmd_mkdir(ctx, ["newdir"])
        assert ctx.fs.is_dir("/home/user/newdir")

    def test_mkdir_no_args_error(self):
        ctx = make_ctx()
        result = cmd_mkdir(ctx, [])
        assert "missing operand" in result

    def test_mkdir_existing_error(self):
        ctx = make_ctx()
        result = cmd_mkdir(ctx, ["scripts"])
        assert "File exists" in result

    def test_mkdir_missing_parent_error(self):
        ctx = make_ctx()
        result = cmd_mkdir(ctx, ["a/b/c"])
        assert "No such file or directory" in result

    def test_mkdir_p_creates_parents(self):
        ctx = make_ctx()
        cmd_mkdir(ctx, ["-p", "a/b/c"])
        assert ctx.fs.is_dir("/home/user/a/b/c")

    def test_mkdir_p_existing_is_silent(self):
        ctx = make_ctx()
        result = cmd_mkdir(ctx, ["-p", "scripts"])
        assert result == ""


# ---------------------------------------------------------------------------
# touch
# ---------------------------------------------------------------------------


class TestTouch:
    def test_touch_creates_empty_file(self):
        ctx = make_ctx()
        cmd_touch(ctx, ["newfile.txt"])
        assert ctx.fs.is_file("/home/user/newfile.txt")
        assert ctx.fs.read_file("/home/user/newfile.txt") == ""

    def test_touch_updates_mtime(self):
        ctx = make_ctx()
        before = ctx.fs._get_node("/home/user/hello.txt").modified
        time.sleep(0.01)
        cmd_touch(ctx, ["hello.txt"])
        after = ctx.fs._get_node("/home/user/hello.txt").modified
        assert after >= before

    def test_touch_no_args_error(self):
        ctx = make_ctx()
        result = cmd_touch(ctx, [])
        assert "missing file operand" in result


# ---------------------------------------------------------------------------
# rm
# ---------------------------------------------------------------------------


class TestRm:
    def test_rm_sends_to_trash(self):
        ctx = make_ctx()
        cmd_rm(ctx, ["hello.txt"])
        assert not ctx.fs.file_exists("/home/user/hello.txt")
        trash = ctx.fs.list_trash()
        assert any("/home/user/hello.txt" in p for p, _ in trash)

    def test_rm_shred_permanent(self):
        ctx = make_ctx()
        cmd_rm(ctx, ["--shred", "hello.txt"])
        assert not ctx.fs.file_exists("/home/user/hello.txt")
        trash = ctx.fs.list_trash()
        assert not any("/home/user/hello.txt" in p for p, _ in trash)

    def test_rm_shred_prints_message(self):
        ctx = make_ctx()
        result = cmd_rm(ctx, ["--shred", "hello.txt"])
        assert "shredding" in result

    def test_rm_nonexistent_error(self):
        ctx = make_ctx()
        result = cmd_rm(ctx, ["ghost.txt"])
        assert "No such file or directory" in result

    def test_rm_f_suppresses_error(self):
        ctx = make_ctx()
        result = cmd_rm(ctx, ["-f", "ghost.txt"])
        assert result == ""

    def test_rm_directory_without_r_error(self):
        ctx = make_ctx()
        result = cmd_rm(ctx, ["scripts"])
        assert "Is a directory" in result

    def test_rm_r_removes_directory(self):
        ctx = make_ctx()
        cmd_rm(ctx, ["-r", "scripts"])
        assert not ctx.fs.file_exists("/home/user/scripts")

    def test_rm_no_args_error(self):
        ctx = make_ctx()
        result = cmd_rm(ctx, [])
        assert "missing operand" in result


# ---------------------------------------------------------------------------
# cp
# ---------------------------------------------------------------------------


class TestCp:
    def test_cp_creates_copy(self):
        ctx = make_ctx()
        cmd_cp(ctx, ["hello.txt", "hello_copy.txt"])
        assert ctx.fs.file_exists("/home/user/hello_copy.txt")
        assert ctx.fs.read_file("/home/user/hello_copy.txt") == ctx.fs.read_file("/home/user/hello.txt")

    def test_cp_into_directory(self):
        ctx = make_ctx()
        cmd_cp(ctx, ["hello.txt", "scripts"])
        assert ctx.fs.file_exists("/home/user/scripts/hello.txt")

    def test_cp_nonexistent_src(self):
        ctx = make_ctx()
        result = cmd_cp(ctx, ["ghost.txt", "out.txt"])
        assert "bash: cp:" in result

    def test_cp_no_args_error(self):
        ctx = make_ctx()
        result = cmd_cp(ctx, ["hello.txt"])
        assert "missing operand" in result


# ---------------------------------------------------------------------------
# mv
# ---------------------------------------------------------------------------


class TestMv:
    def test_mv_renames_file(self):
        ctx = make_ctx()
        cmd_mv(ctx, ["hello.txt", "renamed.txt"])
        assert ctx.fs.file_exists("/home/user/renamed.txt")
        assert not ctx.fs.file_exists("/home/user/hello.txt")

    def test_mv_into_directory(self):
        ctx = make_ctx()
        cmd_mv(ctx, ["hello.txt", "scripts"])
        assert ctx.fs.file_exists("/home/user/scripts/hello.txt")

    def test_mv_nonexistent_src(self):
        ctx = make_ctx()
        result = cmd_mv(ctx, ["ghost.txt", "out.txt"])
        assert "bash: mv:" in result

    def test_mv_no_args_error(self):
        ctx = make_ctx()
        result = cmd_mv(ctx, ["hello.txt"])
        assert "missing operand" in result


# ---------------------------------------------------------------------------
# chmod
# ---------------------------------------------------------------------------


class TestChmod:
    def test_chmod_octal(self):
        ctx = make_ctx()
        cmd_chmod(ctx, ["755", "hello.txt"])
        node = ctx.fs._get_node("/home/user/hello.txt")
        assert node.permissions.to_octal() == "755"

    def test_chmod_symbolic_add(self):
        ctx = make_ctx()
        cmd_chmod(ctx, ["u+x", "hello.txt"])
        node = ctx.fs._get_node("/home/user/hello.txt")
        assert node.permissions.owner_exec is True

    def test_chmod_symbolic_remove(self):
        ctx = make_ctx()
        cmd_chmod(ctx, ["u-r", "hello.txt"])
        node = ctx.fs._get_node("/home/user/hello.txt")
        assert node.permissions.owner_read is False

    def test_chmod_nonexistent_error(self):
        ctx = make_ctx()
        result = cmd_chmod(ctx, ["755", "ghost.txt"])
        assert "No such file or directory" in result

    def test_chmod_no_args_error(self):
        ctx = make_ctx()
        result = cmd_chmod(ctx, ["755"])
        assert "missing operand" in result


# ---------------------------------------------------------------------------
# ln
# ---------------------------------------------------------------------------


class TestLn:
    def test_ln_s_creates_symlink(self):
        ctx = make_ctx()
        cmd_ln(ctx, ["-s", "/etc/hosts", "hosts_link"])
        assert ctx.fs.path_is_symlink("/home/user/hosts_link")
        assert ctx.fs.readlink("/home/user/hosts_link") == "/etc/hosts"

    def test_ln_without_s_error(self):
        ctx = make_ctx()
        result = cmd_ln(ctx, ["/etc/hosts", "link"])
        assert "hard links not supported" in result

    def test_ln_no_args_error(self):
        ctx = make_ctx()
        result = cmd_ln(ctx, ["-s", "/etc/hosts"])
        assert "missing operand" in result


# ---------------------------------------------------------------------------
# stat
# ---------------------------------------------------------------------------


class TestStat:
    def test_stat_regular_file(self):
        ctx = make_ctx()
        result = cmd_stat(ctx, ["hello.txt"])
        assert "hello.txt" in result
        assert "regular file" in result
        assert "user" in result

    def test_stat_directory(self):
        ctx = make_ctx()
        result = cmd_stat(ctx, ["scripts"])
        assert "directory" in result

    def test_stat_symlink_shows_target(self):
        ctx = make_ctx()
        result = cmd_stat(ctx, ["link.txt"])
        assert "symbolic link" in result
        assert "/home/user/hello.txt" in result

    def test_stat_broken_symlink_shows_broken(self):
        ctx = make_ctx()
        result = cmd_stat(ctx, ["dead_link"])
        assert "[BROKEN]" in result

    def test_stat_nonexistent_error(self):
        ctx = make_ctx()
        result = cmd_stat(ctx, ["ghost.txt"])
        assert "No such file or directory" in result

    def test_stat_shows_permissions(self):
        ctx = make_ctx()
        result = cmd_stat(ctx, ["hello.txt"])
        assert "644" in result

    def test_stat_no_args_error(self):
        ctx = make_ctx()
        result = cmd_stat(ctx, [])
        assert "missing operand" in result


# ---------------------------------------------------------------------------
# file
# ---------------------------------------------------------------------------


class TestFile:
    def test_file_ascii_text(self):
        ctx = make_ctx()
        result = cmd_file(ctx, ["hello.txt"])
        assert "ASCII text" in result

    def test_file_encrypted(self):
        ctx = make_ctx()
        result = cmd_file(ctx, ["secret.enc"])
        assert "encrypted data" in result

    def test_file_binary(self):
        ctx = make_ctx()
        result = cmd_file(ctx, ["zork"])
        assert "ELF 64-bit executable" in result

    def test_file_directory(self):
        ctx = make_ctx()
        result = cmd_file(ctx, ["scripts"])
        assert "directory" in result

    def test_file_symlink(self):
        ctx = make_ctx()
        result = cmd_file(ctx, ["link.txt"])
        assert "symbolic link" in result

    def test_file_empty(self):
        ctx = make_ctx()
        result = cmd_file(ctx, ["empty.txt"])
        assert "empty" in result

    def test_file_nonexistent(self):
        ctx = make_ctx()
        result = cmd_file(ctx, ["ghost.txt"])
        assert "No such file or directory" in result

    def test_file_multiple_paths(self):
        ctx = make_ctx()
        result = cmd_file(ctx, ["hello.txt", "zork"])
        assert "ASCII text" in result
        assert "ELF 64-bit executable" in result


# ---------------------------------------------------------------------------
# xxd
# ---------------------------------------------------------------------------


class TestXxd:
    def test_xxd_shows_hex(self):
        ctx = make_ctx()
        result = cmd_xxd(ctx, ["hello.txt"])
        assert "00000000" in result
        assert "68 65 6c 6c 6f" in result  # "hello"

    def test_xxd_works_on_encrypted(self):
        ctx = make_ctx()
        result = cmd_xxd(ctx, ["secret.enc"])
        assert "00000000" in result

    def test_xxd_directory_error(self):
        ctx = make_ctx()
        result = cmd_xxd(ctx, ["scripts"])
        assert "Is a directory" in result

    def test_xxd_nonexistent(self):
        ctx = make_ctx()
        result = cmd_xxd(ctx, ["ghost.txt"])
        assert "No such file or directory" in result

    def test_xxd_no_args_error(self):
        ctx = make_ctx()
        result = cmd_xxd(ctx, [])
        assert "missing operand" in result


# ---------------------------------------------------------------------------
# strings
# ---------------------------------------------------------------------------


class TestStrings:
    def test_strings_extracts_printable(self):
        ctx = make_ctx()
        result = cmd_strings(ctx, ["hello.txt"])
        assert "hello world" in result

    def test_strings_min_length_filters(self):
        ctx = make_ctx()
        result = cmd_strings(ctx, ["-n", "20", "hello.txt"])
        # "hello world" is 11 chars < 20, not extracted
        assert "hello world" not in result

    def test_strings_on_encrypted(self):
        ctx = make_ctx()
        result = cmd_strings(ctx, ["secret.enc"])
        # Encrypted content still has printable chars
        assert "SECRETBINARYDATA" in result

    def test_strings_nonexistent(self):
        ctx = make_ctx()
        result = cmd_strings(ctx, ["ghost.txt"])
        assert "No such file or directory" in result

    def test_strings_directory_error(self):
        ctx = make_ctx()
        result = cmd_strings(ctx, ["scripts"])
        assert "Is a directory" in result


# ---------------------------------------------------------------------------
# grep
# ---------------------------------------------------------------------------


class TestGrep:
    def test_grep_finds_match(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["hello", "hello.txt"])
        assert "hello world" in result

    def test_grep_no_match_empty(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["zzznomatch", "hello.txt"])
        assert result == ""

    def test_grep_i_case_insensitive(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["-i", "HELLO", "hello.txt"])
        assert "hello world" in result

    def test_grep_n_shows_line_numbers(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["-n", "line", "hello.txt"])
        assert "2:line two" in result or "2:" in result

    def test_grep_v_inverts(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["-v", "hello", "hello.txt"])
        assert "hello world" not in result
        assert "line two" in result

    def test_grep_l_filenames_only(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["-l", "hello", "hello.txt"])
        assert result.strip() == "hello.txt"

    def test_grep_r_recursive(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["-r", "echo", "scripts"])
        assert "run.sh" in result

    def test_grep_binary_file_notice(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["ELF", "zork"])
        assert "binary file matches" in result

    def test_grep_nonexistent(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["hello", "ghost.txt"])
        assert "No such file or directory" in result

    def test_grep_invalid_regex_literal_fallback(self):
        ctx = make_ctx()
        # "[invalid" is an unclosed char class → invalid regex; falls back to literal
        result = cmd_grep(ctx, ["[invalid", "hello.txt"])
        # Literal "[invalid" not in content — empty result, no crash
        assert result == ""

    def test_grep_multiple_files_shows_path(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, ["hello", "hello.txt", "/etc/hosts"])
        assert "hello.txt:" in result

    def test_grep_no_pattern_error(self):
        ctx = make_ctx()
        result = cmd_grep(ctx, [])
        assert "missing pattern" in result


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------


class TestFind:
    def test_find_all_in_dir(self):
        ctx = make_ctx()
        result = cmd_find(ctx, ["/home/user"])
        assert "hello.txt" in result
        assert "run.sh" in result

    def test_find_name_glob(self):
        ctx = make_ctx()
        result = cmd_find(ctx, ["/home/user", "-name", "*.txt"])
        assert "hello.txt" in result
        assert "run.sh" not in result

    def test_find_type_f_files_only(self):
        ctx = make_ctx()
        result = cmd_find(ctx, ["/home/user", "-type", "f"])
        assert "hello.txt" in result
        # the scripts directory itself should not appear as a match
        assert "/home/user/scripts" not in result.splitlines()

    def test_find_type_d_dirs_only(self):
        ctx = make_ctx()
        result = cmd_find(ctx, ["/home/user", "-type", "d"])
        assert "scripts" in result
        assert "hello.txt" not in result

    def test_find_nonexistent_path(self):
        ctx = make_ctx()
        result = cmd_find(ctx, ["/nonexistent"])
        assert "No such file or directory" in result

    def test_find_defaults_to_cwd(self):
        ctx = make_ctx()
        result = cmd_find(ctx, [])
        assert "hello.txt" in result


# ---------------------------------------------------------------------------
# recover
# ---------------------------------------------------------------------------


class TestRecover:
    def test_recover_list_empty(self):
        ctx = make_ctx()
        result = cmd_recover(ctx, [])
        assert "trash is empty" in result

    def test_recover_list_after_rm(self):
        ctx = make_ctx()
        cmd_rm(ctx, ["hello.txt"])
        result = cmd_recover(ctx, [])
        assert "hello.txt" in result

    def test_recover_restores_file(self):
        ctx = make_ctx()
        cmd_rm(ctx, ["hello.txt"])
        result = cmd_recover(ctx, ["/home/user/hello.txt"])
        assert "recovered:" in result
        assert ctx.fs.file_exists("/home/user/hello.txt")

    def test_recover_nonexistent_path(self):
        ctx = make_ctx()
        result = cmd_recover(ctx, ["/home/user/nothing_here.txt"])
        assert "nothing recoverable" in result

    def test_recover_content_preserved(self):
        ctx = make_ctx()
        original = ctx.fs.read_file("/home/user/hello.txt")
        cmd_rm(ctx, ["hello.txt"])
        cmd_recover(ctx, ["/home/user/hello.txt"])
        assert ctx.fs.read_file("/home/user/hello.txt") == original
