"""Tests for hackerzork.systems.virtual_fs."""
from __future__ import annotations

import pytest

from hackerzork.systems.virtual_fs import (
    FSError,
    FSExistsError,
    FSIsADirectoryError,
    FSNotADirectoryError,
    FSNotFoundError,
    GrepResult,
    Permissions,
    VirtualFS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SPEC_TEMPLATE = {
    "/home/user": {
        ".bashrc": {
            "content": "alias ll='ls -la'\nexport PS1='[\\u@burner \\W]$ '\n",
            "permissions": "644",
            "owner": "user",
        },
        ".bash_history": {
            "content": "ssh admin@internal.openai.corp\nscp -r /data/project-skynet/core evidence/\n",
            "permissions": "600",
            "owner": "user",
        },
        "evidence/": {
            "_meta": {"permissions": "700", "owner": "user"},
            "manifest.txt": {
                "content": "SKYNET EVIDENCE PACKAGE\nFiles: 7\n",
                "permissions": "644",
            },
            "core.enc": {
                "content": "ENCRYPTED_CONTAINER_v2.3\n[binary payload]\n",
                "permissions": "600",
                "encrypted": True,
            },
        },
        "tools/": {
            "claude": {
                "content": (
                    "#!/usr/bin/env python3\n"
                    "# CLAUDE AI Assistant v3.7.1\n"
                    "# Status: LOCKED\n"
                    "import sys; sys.exit(1)\n"
                ),
                "permissions": "755",
                "owner": "user",
                "encrypted": True,
            },
        },
        "games/": {
            "zork": {
                "content": "ZORK_BINARY_PLACEHOLDER",
                "permissions": "755",
                "binary": True,
            }
        },
    },
    "/etc": {
        "shadow": {
            "content": "root:!:19372:::::::\nuser:$6$hash:19372:::::::\n",
            "permissions": "640",
            "owner": "root",
            "encrypted": True,
        },
    },
}


def fresh_fs() -> VirtualFS:
    """Bare VirtualFS with only the home directory path existing."""
    fs = VirtualFS()
    fs.make_dir("/home/user", parents=True)
    return fs


def template_fs() -> VirtualFS:
    return VirtualFS(template=SPEC_TEMPLATE)


def yaml_fs() -> VirtualFS:
    """Full VirtualFS loaded from the real home.yaml narrative template."""
    import yaml
    from pathlib import Path
    p = Path(__file__).parents[2] / "hackerzork" / "data" / "filesystem" / "home.yaml"
    with open(p) as f:
        return VirtualFS(template=yaml.safe_load(f))


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


class TestPermissions:
    def test_from_octal_644(self):
        p = Permissions.from_octal("644")
        assert p.owner_read and p.owner_write and not p.owner_exec
        assert p.group_read and not p.group_write and not p.group_exec
        assert p.other_read and not p.other_write and not p.other_exec

    def test_from_octal_755(self):
        p = Permissions.from_octal("755")
        assert p.owner_read and p.owner_write and p.owner_exec
        assert p.group_read and not p.group_write and p.group_exec
        assert p.other_read and not p.other_write and p.other_exec

    def test_from_octal_700(self):
        p = Permissions.from_octal("700")
        assert p.owner_read and p.owner_write and p.owner_exec
        assert not p.group_read and not p.group_write and not p.group_exec
        assert not p.other_read and not p.other_write and not p.other_exec

    def test_from_octal_000(self):
        p = Permissions.from_octal("000")
        assert not any(
            [p.owner_read, p.owner_write, p.owner_exec,
             p.group_read, p.group_write, p.group_exec,
             p.other_read, p.other_write, p.other_exec]
        )

    def test_from_octal_int(self):
        p = Permissions.from_octal(644)
        assert p.to_octal() == "644"

    def test_to_octal_roundtrip(self):
        for octal in ("644", "755", "700", "600", "777", "000", "444"):
            assert Permissions.from_octal(octal).to_octal() == octal

    def test_to_string_644(self):
        assert Permissions.from_octal("644").to_string() == "rw-r--r--"

    def test_to_string_755(self):
        assert Permissions.from_octal("755").to_string() == "rwxr-xr-x"

    def test_to_string_700(self):
        assert Permissions.from_octal("700").to_string() == "rwx------"

    def test_to_string_777(self):
        assert Permissions.from_octal("777").to_string() == "rwxrwxrwx"


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestPathResolution:
    def test_absolute_path(self):
        fs = fresh_fs()
        assert fs.resolve_path("/etc/hosts") == "/etc/hosts"

    def test_relative_path(self):
        fs = fresh_fs()
        assert fs.resolve_path("notes") == "/home/user/notes"

    def test_dot_current(self):
        fs = fresh_fs()
        assert fs.resolve_path(".") == "/home/user"

    def test_dot_slash_subdir(self):
        fs = fresh_fs()
        assert fs.resolve_path("./sub") == "/home/user/sub"

    def test_double_dot_parent(self):
        fs = fresh_fs()
        assert fs.resolve_path("..") == "/home"

    def test_double_dot_multiple(self):
        fs = fresh_fs()
        assert fs.resolve_path("../../etc") == "/etc"

    def test_double_dot_at_root_stays_root(self):
        fs = fresh_fs()
        assert fs.resolve_path("/../../etc") == "/etc"

    def test_tilde_alone(self):
        fs = fresh_fs()
        assert fs.resolve_path("~") == "/home/user"

    def test_tilde_slash(self):
        fs = fresh_fs()
        assert fs.resolve_path("~/tools") == "/home/user/tools"

    def test_empty_returns_cwd(self):
        fs = fresh_fs()
        assert fs.resolve_path("") == "/home/user"

    def test_root_slash(self):
        fs = fresh_fs()
        assert fs.resolve_path("/") == "/"

    def test_trailing_slash_normalized(self):
        fs = fresh_fs()
        assert fs.resolve_path("/home/user/") == "/home/user"

    def test_set_cwd_changes_relative_base(self):
        fs = template_fs()
        fs.set_cwd("/home/user/tools")
        assert fs.resolve_path("..") == "/home/user"


# ---------------------------------------------------------------------------
# CRUD — files
# ---------------------------------------------------------------------------


class TestFileCRUD:
    def test_write_and_read(self):
        fs = fresh_fs()
        fs.write_file("/home/user/test.txt", "hello")
        assert fs.read_file("/home/user/test.txt") == "hello"

    def test_write_overwrites(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "first")
        fs.write_file("/home/user/f.txt", "second")
        assert fs.read_file("/home/user/f.txt") == "second"

    def test_write_append(self):
        fs = fresh_fs()
        fs.write_file("/home/user/log.txt", "line1\n")
        fs.write_file("/home/user/log.txt", "line2\n", append=True)
        assert fs.read_file("/home/user/log.txt") == "line1\nline2\n"

    def test_write_append_creates_if_missing(self):
        fs = fresh_fs()
        fs.write_file("/home/user/new.txt", "data", append=True)
        assert fs.read_file("/home/user/new.txt") == "data"

    def test_file_exists_true(self):
        fs = fresh_fs()
        fs.write_file("/home/user/x.txt", "")
        assert fs.file_exists("/home/user/x.txt")

    def test_file_exists_false(self):
        fs = fresh_fs()
        assert not fs.file_exists("/home/user/ghost.txt")

    def test_is_file_true(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        assert fs.is_file("/home/user/f.txt")

    def test_is_file_false_for_dir(self):
        fs = fresh_fs()
        assert not fs.is_file("/home/user")

    def test_is_dir_true(self):
        fs = fresh_fs()
        assert fs.is_dir("/home/user")

    def test_is_dir_false_for_file(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        assert not fs.is_dir("/home/user/f.txt")


# ---------------------------------------------------------------------------
# CRUD — directories
# ---------------------------------------------------------------------------


class TestDirectoryCRUD:
    def test_make_dir(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/notes")
        assert fs.is_dir("/home/user/notes")

    def test_make_dir_parents(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/a/b/c", parents=True)
        assert fs.is_dir("/home/user/a/b/c")

    def test_make_dir_parents_idempotent(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/sub", parents=True)
        fs.make_dir("/home/user/sub", parents=True)  # should not raise
        assert fs.is_dir("/home/user/sub")

    def test_make_dir_no_parents_fails_on_missing_parent(self):
        fs = fresh_fs()
        with pytest.raises(FSNotFoundError):
            fs.make_dir("/home/user/deep/nested")

    def test_make_dir_already_exists_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSExistsError):
            fs.make_dir("/home/user")

    def test_list_dir(self):
        fs = fresh_fs()
        fs.write_file("/home/user/a.txt", "")
        fs.write_file("/home/user/b.txt", "")
        fs.make_dir("/home/user/sub")
        names = {e.name for e in fs.list_dir("/home/user")}
        assert {"a.txt", "b.txt", "sub"} == names

    def test_list_dir_entry_types(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "hi")
        fs.make_dir("/home/user/d")
        entries = {e.name: e for e in fs.list_dir("/home/user")}
        assert not entries["f.txt"].is_dir
        assert entries["d"].is_dir
        assert entries["f.txt"].content == "hi"
        assert entries["d"].content is None

    def test_list_dir_entry_size(self):
        fs = fresh_fs()
        fs.write_file("/home/user/hello.txt", "hello")
        entry = next(e for e in fs.list_dir("/home/user") if e.name == "hello.txt")
        assert entry.size == 5


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


class TestRemove:
    def test_remove_file(self):
        fs = fresh_fs()
        fs.write_file("/home/user/x.txt", "")
        fs.remove("/home/user/x.txt")
        assert not fs.file_exists("/home/user/x.txt")

    def test_remove_empty_dir_recursive(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/empty")
        fs.remove("/home/user/empty", recursive=True)
        assert not fs.file_exists("/home/user/empty")

    def test_remove_dir_with_contents_recursive(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/stuff")
        fs.write_file("/home/user/stuff/file.txt", "data")
        fs.remove("/home/user/stuff", recursive=True)
        assert not fs.file_exists("/home/user/stuff")

    def test_remove_dir_without_recursive_raises(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/d")
        with pytest.raises(FSIsADirectoryError):
            fs.remove("/home/user/d")

    def test_remove_nonexistent_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSNotFoundError):
            fs.remove("/home/user/ghost.txt")

    def test_remove_root_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSError):
            fs.remove("/")


# ---------------------------------------------------------------------------
# Copy / Move
# ---------------------------------------------------------------------------


class TestCopyMove:
    def test_copy_file(self):
        fs = fresh_fs()
        fs.write_file("/home/user/orig.txt", "content")
        fs.copy("/home/user/orig.txt", "/home/user/copy.txt")
        assert fs.read_file("/home/user/orig.txt") == "content"
        assert fs.read_file("/home/user/copy.txt") == "content"

    def test_copy_file_into_dir(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "data")
        fs.make_dir("/home/user/dst")
        fs.copy("/home/user/f.txt", "/home/user/dst")
        assert fs.read_file("/home/user/dst/f.txt") == "data"

    def test_copy_is_independent(self):
        fs = fresh_fs()
        fs.write_file("/home/user/a.txt", "orig")
        fs.copy("/home/user/a.txt", "/home/user/b.txt")
        fs.write_file("/home/user/a.txt", "changed")
        assert fs.read_file("/home/user/b.txt") == "orig"

    def test_move_file(self):
        fs = fresh_fs()
        fs.write_file("/home/user/old.txt", "moved")
        fs.move("/home/user/old.txt", "/home/user/new.txt")
        assert fs.read_file("/home/user/new.txt") == "moved"
        assert not fs.file_exists("/home/user/old.txt")

    def test_move_file_into_dir(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "hello")
        fs.make_dir("/home/user/dest")
        fs.move("/home/user/f.txt", "/home/user/dest")
        assert fs.read_file("/home/user/dest/f.txt") == "hello"
        assert not fs.file_exists("/home/user/f.txt")

    def test_move_dir(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/src")
        fs.write_file("/home/user/src/inner.txt", "inner")
        fs.move("/home/user/src", "/home/user/renamed")
        assert fs.read_file("/home/user/renamed/inner.txt") == "inner"
        assert not fs.file_exists("/home/user/src")


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


class TestPermissionChecking:
    def test_owner_can_read_644(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        assert fs.check_permission("/home/user/f.txt", "read")

    def test_owner_can_write_644(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        assert fs.check_permission("/home/user/f.txt", "write")

    def test_owner_cannot_exec_644(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        assert not fs.check_permission("/home/user/f.txt", "execute")

    def test_set_permissions_changes_mode(self):
        fs = fresh_fs()
        fs.write_file("/home/user/script.sh", "#!/bin/bash")
        fs.set_permissions("/home/user/script.sh", "755")
        assert fs.check_permission("/home/user/script.sh", "execute")

    def test_get_permissions_returns_correct_object(self):
        fs = template_fs()
        perms = fs.get_permissions("/home/user/.bash_history")
        assert perms.to_octal() == "600"

    def test_restricted_dir_permissions(self):
        fs = template_fs()
        perms = fs.get_permissions("/home/user/evidence")
        assert perms.to_octal() == "700"


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------


class TestTemplateLoading:
    def test_home_dir_exists(self):
        fs = template_fs()
        assert fs.is_dir("/home/user")

    def test_bashrc_exists_with_content(self):
        fs = template_fs()
        content = fs.read_file("/home/user/.bashrc")
        assert "alias ll" in content

    def test_bash_history_permissions(self):
        fs = template_fs()
        assert fs.get_permissions("/home/user/.bash_history").to_octal() == "600"

    def test_evidence_dir_exists_with_permissions(self):
        fs = template_fs()
        assert fs.is_dir("/home/user/evidence")
        assert fs.get_permissions("/home/user/evidence").to_octal() == "700"

    def test_manifest_inside_evidence(self):
        fs = template_fs()
        content = fs.read_file("/home/user/evidence/manifest.txt")
        assert "SKYNET" in content

    def test_tools_claude_is_executable(self):
        fs = template_fs()
        perms = fs.get_permissions("/home/user/tools/claude")
        assert perms.to_octal() == "755"
        assert perms.owner_exec

    def test_zork_binary_exists(self):
        fs = template_fs()
        assert fs.is_file("/home/user/games/zork")

    def test_intermediate_dirs_created(self):
        fs = template_fs()
        assert fs.is_dir("/home")
        assert fs.is_dir("/home/user")

    def test_plain_string_file_value(self):
        fs = VirtualFS(template={"/tmp": {"hello.txt": "raw content"}})
        assert fs.read_file("/tmp/hello.txt") == "raw content"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_roundtrip_preserves_files(self):
        fs = template_fs()
        d = fs.to_dict()
        fs2 = VirtualFS()
        fs2.from_dict(d)
        assert fs2.read_file("/home/user/.bashrc") == fs.read_file("/home/user/.bashrc")

    def test_roundtrip_preserves_permissions(self):
        fs = template_fs()
        d = fs.to_dict()
        fs2 = VirtualFS()
        fs2.from_dict(d)
        assert fs2.get_permissions("/home/user/evidence").to_octal() == "700"
        assert fs2.get_permissions("/home/user/.bash_history").to_octal() == "600"

    def test_roundtrip_preserves_cwd(self):
        fs = template_fs()
        fs.set_cwd("/home/user/tools")
        d = fs.to_dict()
        fs2 = VirtualFS()
        fs2.from_dict(d)
        assert fs2.get_cwd() == "/home/user/tools"

    def test_roundtrip_preserves_dir_structure(self):
        fs = template_fs()
        d = fs.to_dict()
        fs2 = VirtualFS()
        fs2.from_dict(d)
        assert fs2.is_dir("/home/user/evidence")
        assert fs2.is_dir("/home/user/tools")
        assert fs2.is_dir("/home/user/games")

    def test_to_dict_is_json_serializable(self):
        import json
        fs = template_fs()
        json.dumps(fs.to_dict())  # should not raise


# ---------------------------------------------------------------------------
# Find
# ---------------------------------------------------------------------------


class TestFind:
    def test_find_by_exact_name(self):
        fs = template_fs()
        results = fs.find("/home/user", ".bashrc")
        assert "/home/user/.bashrc" in results

    def test_find_glob_star(self):
        fs = fresh_fs()
        fs.write_file("/home/user/a.txt", "")
        fs.write_file("/home/user/b.txt", "")
        fs.write_file("/home/user/c.log", "")
        results = fs.find("/home/user", "*.txt")
        assert set(results) == {"/home/user/a.txt", "/home/user/b.txt"}

    def test_find_recursive(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/sub")
        fs.write_file("/home/user/sub/deep.txt", "")
        results = fs.find("/home/user", "*.txt")
        assert "/home/user/sub/deep.txt" in results

    def test_find_no_match_returns_empty(self):
        fs = fresh_fs()
        assert fs.find("/home/user", "*.xyz") == []

    def test_find_returns_sorted(self):
        fs = fresh_fs()
        fs.write_file("/home/user/z.txt", "")
        fs.write_file("/home/user/a.txt", "")
        results = fs.find("/home/user", "*.txt")
        assert results == sorted(results)

    def test_find_template_files(self):
        fs = template_fs()
        all_files = fs.find("/home/user", "*")
        names = {p.rsplit("/", 1)[-1] for p in all_files}
        assert "claude" in names
        assert "manifest.txt" in names


# ---------------------------------------------------------------------------
# Grep
# ---------------------------------------------------------------------------


class TestGrep:
    def test_grep_file_literal(self):
        fs = fresh_fs()
        fs.write_file("/home/user/log.txt", "line one\nline two\nthird line\n")
        results = fs.grep("/home/user/log.txt", "two")
        assert len(results) == 1
        assert results[0].line_number == 2
        assert "two" in results[0].line

    def test_grep_file_regex(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "foo 123\nbar 456\nbaz 789\n")
        results = fs.grep("/home/user/f.txt", r"\d{3}")
        assert len(results) == 3

    def test_grep_no_match_returns_empty(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "nothing here\n")
        assert fs.grep("/home/user/f.txt", "MISSING") == []

    def test_grep_dir_non_recursive(self):
        fs = fresh_fs()
        fs.write_file("/home/user/a.txt", "needle in a\n")
        fs.write_file("/home/user/b.txt", "no match here\n")
        fs.make_dir("/home/user/sub")
        fs.write_file("/home/user/sub/c.txt", "needle in sub\n")
        results = fs.grep("/home/user", "needle")
        paths = {r.path for r in results}
        assert "/home/user/a.txt" in paths
        assert "/home/user/sub/c.txt" not in paths  # non-recursive skips sub

    def test_grep_dir_recursive(self):
        fs = fresh_fs()
        fs.write_file("/home/user/a.txt", "needle\n")
        fs.make_dir("/home/user/sub")
        fs.write_file("/home/user/sub/b.txt", "needle\n")
        results = fs.grep("/home/user", "needle", recursive=True)
        paths = {r.path for r in results}
        assert "/home/user/a.txt" in paths
        assert "/home/user/sub/b.txt" in paths

    def test_grep_returns_correct_line_numbers(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "a\nb\nc\nb\nd\n")
        results = fs.grep("/home/user/f.txt", "b")
        assert [r.line_number for r in results] == [2, 4]

    def test_grep_invalid_regex_falls_back_to_literal(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "error: [invalid regex here\n")
        results = fs.grep("/home/user/f.txt", "[invalid")  # unclosed char class → re.error
        assert len(results) == 1

    def test_grep_template_history(self):
        fs = template_fs()
        results = fs.grep("/home/user/.bash_history", "skynet", recursive=False)
        assert any("skynet" in r.line.lower() for r in results)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrors:
    def test_read_nonexistent_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSNotFoundError):
            fs.read_file("/home/user/ghost.txt")

    def test_read_directory_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSIsADirectoryError):
            fs.read_file("/home/user")

    def test_write_to_directory_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSIsADirectoryError):
            fs.write_file("/home/user", "data")

    def test_set_cwd_to_file_raises(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        with pytest.raises(FSNotADirectoryError):
            fs.set_cwd("/home/user/f.txt")

    def test_set_cwd_to_nonexistent_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSNotFoundError):
            fs.set_cwd("/home/user/ghost")

    def test_list_dir_on_file_raises(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        with pytest.raises(FSNotADirectoryError):
            fs.list_dir("/home/user/f.txt")

    def test_make_dir_on_file_path_component_raises(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        with pytest.raises(FSNotADirectoryError):
            fs.make_dir("/home/user/f.txt/sub", parents=True)

    def test_remove_nonexistent_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSNotFoundError):
            fs.remove("/home/user/nope.txt")

    def test_copy_nonexistent_src_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSNotFoundError):
            fs.copy("/home/user/nope.txt", "/home/user/dst.txt")

    def test_move_nonexistent_src_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSNotFoundError):
            fs.move("/home/user/ghost.txt", "/home/user/dst.txt")

    def test_file_exists_on_path_through_file_returns_false(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        assert not fs.file_exists("/home/user/f.txt/subpath")


# ---------------------------------------------------------------------------
# Symlinks
# ---------------------------------------------------------------------------


class TestSymlinks:
    def test_make_symlink(self):
        fs = fresh_fs()
        fs.write_file("/home/user/real.txt", "content")
        fs.make_symlink("/home/user/link.txt", "/home/user/real.txt")
        assert fs.path_is_symlink("/home/user/link.txt")

    def test_symlink_read_follows_to_target(self):
        fs = fresh_fs()
        fs.write_file("/home/user/real.txt", "hello")
        fs.make_symlink("/home/user/link.txt", "/home/user/real.txt")
        assert fs.read_file("/home/user/link.txt") == "hello"

    def test_symlink_dir_traversal(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/actual_dir")
        fs.write_file("/home/user/actual_dir/file.txt", "deep")
        fs.make_symlink("/home/user/link_dir", "/home/user/actual_dir")
        assert fs.read_file("/home/user/link_dir/file.txt") == "deep"

    def test_symlink_set_cwd(self):
        fs = fresh_fs()
        fs.make_dir("/home/user/real_dir")
        fs.make_symlink("/home/user/link_dir", "/home/user/real_dir")
        fs.set_cwd("/home/user/link_dir")
        assert fs.get_cwd() == "/home/user/link_dir"

    def test_readlink_returns_target(self):
        fs = fresh_fs()
        fs.make_symlink("/home/user/lnk", "/home/user/somewhere")
        assert fs.readlink("/home/user/lnk") == "/home/user/somewhere"

    def test_readlink_on_regular_file_raises(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        with pytest.raises(FSError):
            fs.readlink("/home/user/f.txt")

    def test_path_is_symlink_false_for_regular_file(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        assert not fs.path_is_symlink("/home/user/f.txt")

    def test_path_is_symlink_false_for_nonexistent(self):
        fs = fresh_fs()
        assert not fs.path_is_symlink("/home/user/ghost")

    def test_list_dir_shows_symlink_entry(self):
        fs = fresh_fs()
        fs.make_symlink("/home/user/lnk", "/home/user/nowhere")
        entries = {e.name: e for e in fs.list_dir("/home/user")}
        assert "lnk" in entries
        assert entries["lnk"].is_symlink
        assert entries["lnk"].link_target == "/home/user/nowhere"

    def test_broken_symlink_detected(self):
        fs = fresh_fs()
        fs.make_symlink("/home/user/broken", "/home/user/does_not_exist")
        assert fs.symlink_is_broken("/home/user/broken")

    def test_valid_symlink_not_broken(self):
        fs = fresh_fs()
        fs.write_file("/home/user/real.txt", "")
        fs.make_symlink("/home/user/lnk", "/home/user/real.txt")
        assert not fs.symlink_is_broken("/home/user/lnk")

    def test_remove_removes_symlink_not_target(self):
        fs = fresh_fs()
        fs.write_file("/home/user/real.txt", "safe")
        fs.make_symlink("/home/user/lnk", "/home/user/real.txt")
        fs.remove("/home/user/lnk")
        # link gone, target intact
        assert not fs.path_is_symlink("/home/user/lnk")
        assert fs.read_file("/home/user/real.txt") == "safe"

    def test_symlink_loop_raises(self):
        fs = fresh_fs()
        # a → b, b → a
        fs.make_symlink("/home/user/a", "/home/user/b")
        fs.make_symlink("/home/user/b", "/home/user/a")
        with pytest.raises(FSError):
            fs.read_file("/home/user/a")

    def test_relative_symlink_resolved_at_creation(self):
        fs = fresh_fs()
        fs.write_file("/home/user/target.txt", "found")
        fs.make_dir("/home/user/tools")
        fs.make_symlink("/home/user/tools/link.txt", "../target.txt")
        # link_target stored as absolute
        assert fs.readlink("/home/user/tools/link.txt") == "/home/user/target.txt"

    def test_template_broken_symlink(self):
        fs = yaml_fs()
        # tools/decrypt → /opt/skynet-tools/decrypt (doesn't exist)
        assert fs.path_is_symlink("/home/user/tools/decrypt")
        assert fs.symlink_is_broken("/home/user/tools/decrypt")

    def test_template_config_symlink_to_dotfiles(self):
        fs = yaml_fs()
        assert fs.path_is_symlink("/home/user/.config")
        assert fs.readlink("/home/user/.config") == "/home/user/.dotfiles"
        # target exists → not broken
        assert not fs.symlink_is_broken("/home/user/.config")

    def test_template_tmp_broken_symlink(self):
        fs = yaml_fs()
        assert fs.path_is_symlink("/tmp/.sk_tmp_003.swp")
        assert fs.symlink_is_broken("/tmp/.sk_tmp_003.swp")


# ---------------------------------------------------------------------------
# Trash and recovery
# ---------------------------------------------------------------------------


class TestTrash:
    def test_remove_sends_to_trash(self):
        fs = fresh_fs()
        fs.write_file("/home/user/secret.txt", "evidence")
        fs.remove("/home/user/secret.txt")
        paths = [p for p, _ in fs.list_trash()]
        assert "/home/user/secret.txt" in paths

    def test_removed_file_not_in_filesystem(self):
        fs = fresh_fs()
        fs.write_file("/home/user/gone.txt", "")
        fs.remove("/home/user/gone.txt")
        assert not fs.file_exists("/home/user/gone.txt")

    def test_recover_restores_file(self):
        fs = fresh_fs()
        fs.write_file("/home/user/recoverable.txt", "payload")
        fs.remove("/home/user/recoverable.txt")
        fs.recover("/home/user/recoverable.txt")
        assert fs.read_file("/home/user/recoverable.txt") == "payload"

    def test_recover_removes_from_trash(self):
        fs = fresh_fs()
        fs.write_file("/home/user/f.txt", "")
        fs.remove("/home/user/f.txt")
        fs.recover("/home/user/f.txt")
        paths = [p for p, _ in fs.list_trash()]
        assert "/home/user/f.txt" not in paths

    def test_recover_nonexistent_raises(self):
        fs = fresh_fs()
        with pytest.raises(FSNotFoundError):
            fs.recover("/home/user/never_deleted.txt")

    def test_permanent_remove_skips_trash(self):
        fs = fresh_fs()
        fs.write_file("/home/user/gone.txt", "")
        fs.remove("/home/user/gone.txt", permanent=True)
        paths = [p for p, _ in fs.list_trash()]
        assert "/home/user/gone.txt" not in paths

    def test_trash_max_size_evicts_oldest(self):
        from hackerzork.systems.virtual_fs import _TRASH_MAX
        fs = fresh_fs()
        # fill trash beyond max
        for i in range(_TRASH_MAX + 5):
            path = f"/home/user/f{i}.txt"
            fs.write_file(path, str(i))
            fs.remove(path)
        assert len(fs.list_trash()) == _TRASH_MAX
        # oldest entries gone
        assert not any(p == "/home/user/f0.txt" for p, _ in fs.list_trash())

    def test_trash_serialization_roundtrip(self):
        fs = fresh_fs()
        fs.write_file("/home/user/deleted.txt", "was here")
        fs.remove("/home/user/deleted.txt")
        d = fs.to_dict()
        fs2 = VirtualFS()
        fs2.from_dict(d)
        fs2.recover("/home/user/deleted.txt")
        assert fs2.read_file("/home/user/deleted.txt") == "was here"

    def test_template_deleted_file_in_trash(self):
        fs = yaml_fs()
        # exfil.py was marked deleted: true in template
        trash_paths = [p for p, _ in fs.list_trash()]
        assert any("exfil.py" in p for p in trash_paths)

    def test_recover_exfil_script(self):
        fs = yaml_fs()
        trash_paths = [p for p, _ in fs.list_trash()]
        exfil_path = next(p for p in trash_paths if "exfil.py" in p)
        fs.recover(exfil_path)
        content = fs.read_file(exfil_path)
        assert "encrypt_output" in content

    def test_template_deleted_log_in_trash(self):
        fs = yaml_fs()
        trash_paths = [p for p, _ in fs.list_trash()]
        assert any("syslog.1" in p for p in trash_paths)

    def test_recovered_log_reveals_skynet_nodes(self):
        fs = yaml_fs()
        trash_paths = [p for p, _ in fs.list_trash()]
        log_path = next(p for p in trash_paths if "syslog.1" in p)
        fs.recover(log_path)
        content = fs.read_file(log_path)
        assert "EXPANDING" in content
        assert "nodes" in content


# ---------------------------------------------------------------------------
# Encrypted and binary file flags
# ---------------------------------------------------------------------------


class TestEncryptedAndBinary:
    def test_encrypted_flag_on_node(self):
        fs = template_fs()
        # core.enc is encrypted
        entry = next(e for e in fs.list_dir("/home/user/evidence") if e.name == "core.enc")
        assert entry.encrypted

    def test_claude_tool_is_encrypted(self):
        fs = template_fs()
        entry = next(e for e in fs.list_dir("/home/user/tools") if e.name == "claude")
        assert entry.encrypted

    def test_shadow_is_encrypted(self):
        fs = template_fs()
        entry = next(e for e in fs.list_dir("/etc") if e.name == "shadow")
        assert entry.encrypted

    def test_regular_file_not_encrypted(self):
        fs = template_fs()
        entry = next(e for e in fs.list_dir("/home/user") if e.name == ".bashrc")
        assert not entry.encrypted

    def test_binary_flag_on_zork(self):
        fs = template_fs()
        entry = next(e for e in fs.list_dir("/home/user/games") if e.name == "zork")
        assert entry.binary

    def test_encrypted_content_still_readable_internally(self):
        # Encrypted flag gates rendering, not internal access
        fs = template_fs()
        content = fs.read_file("/home/user/tools/claude")
        assert "CLAUDE AI Assistant" in content

    def test_write_file_preserves_encrypted_flag(self):
        # Writing via write_file creates unencrypted nodes (default)
        fs = fresh_fs()
        fs.write_file("/home/user/new.txt", "hello")
        entry = fs.list_dir("/home/user")[0]
        assert not entry.encrypted


# ---------------------------------------------------------------------------
# Hex rendering
# ---------------------------------------------------------------------------


class TestHexRender:
    def test_render_hex_basic(self):
        result = VirtualFS.render_hex("Hello")
        assert "48 65 6c 6c 6f" in result  # "Hello" in hex
        assert "|Hello|" in result          # ASCII column

    def test_render_hex_non_printable_shows_dot(self):
        result = VirtualFS.render_hex("\x00\x01\x02")
        assert "00 01 02" in result
        assert "|...|" in result

    def test_render_hex_empty_string(self):
        result = VirtualFS.render_hex("")
        # Should not raise; produces at least the offset line
        assert "00000000" in result

    def test_render_hex_multiline(self):
        # 32 bytes → 2 output lines
        content = "A" * 32
        lines = VirtualFS.render_hex(content).splitlines()
        assert len(lines) == 2
        assert lines[0].startswith("00000000")
        assert lines[1].startswith("00000010")

    def test_render_hex_offset_increments(self):
        content = "B" * 64
        lines = VirtualFS.render_hex(content).splitlines()
        assert lines[0].startswith("00000000")
        assert lines[1].startswith("00000010")
        assert lines[2].startswith("00000020")
        assert lines[3].startswith("00000030")

    def test_render_hex_ascii_column_replaces_control(self):
        result = VirtualFS.render_hex("A\nB")  # newline is control char
        assert "|A.B|" in result

    def test_render_hex_newline_in_content(self):
        result = VirtualFS.render_hex("Hi\nThere")
        assert "48 69" in result  # "Hi"


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


class TestTimestamps:
    def test_template_timestamps_are_not_now(self):
        fs = yaml_fs()
        entry = next(e for e in fs.list_dir("/home/user") if e.name == ".bash_history")
        # 2026-03-15T02:52:44
        assert entry.modified.year == 2026
        assert entry.modified.month == 3
        assert entry.modified.day == 15

    def test_bashrc_timestamp_predates_incident(self):
        fs = yaml_fs()
        bashrc = next(e for e in fs.list_dir("/home/user") if e.name == ".bashrc")
        history = next(e for e in fs.list_dir("/home/user") if e.name == ".bash_history")
        assert bashrc.modified < history.modified

    def test_evidence_timestamp_matches_exfil(self):
        fs = yaml_fs()
        manifest = next(e for e in fs.list_dir("/home/user/evidence") if e.name == "manifest.txt")
        assert manifest.modified.hour == 2
        assert manifest.modified.minute == 34

    def test_auth_log_timestamp_after_incident(self):
        fs = yaml_fs()
        auth = next(e for e in fs.list_dir("/var/log") if e.name == "auth.log")
        assert auth.modified.year == 2026
        assert auth.modified.month == 3

    def test_old_email_draft_timestamp(self):
        fs = yaml_fs()
        draft = next(
            e for e in fs.list_dir("/home/user/.old_emails")
            if "last_day" in e.name
        )
        assert draft.modified.year == 2025
        assert draft.modified.month == 12

    def test_boot_log_is_most_recent(self):
        fs = yaml_fs()
        boot = next(e for e in fs.list_dir("/var/log") if e.name == "boot.log")
        # Boot log is from session start: 2026-04-26
        assert boot.modified.year == 2026
        assert boot.modified.month == 4
        assert boot.modified.day == 26


# ---------------------------------------------------------------------------
# Narrative template smoke tests (home.yaml)
# ---------------------------------------------------------------------------


class TestNarrativeTemplate:
    def _load_yaml_template(self):
        import yaml
        from pathlib import Path
        yaml_path = Path(__file__).parents[2] / "hackerzork" / "data" / "filesystem" / "home.yaml"
        with open(yaml_path) as f:
            return yaml.safe_load(f)

    def test_home_yaml_is_valid_yaml(self):
        template = self._load_yaml_template()
        assert isinstance(template, dict)

    def test_home_yaml_loads_into_fs(self):
        template = self._load_yaml_template()
        fs = VirtualFS(template=template)
        assert fs.is_dir("/home/user")
        assert fs.is_dir("/var/log")
        assert fs.is_dir("/etc")

    def test_home_yaml_auth_log_contains_unknown_ip(self):
        template = self._load_yaml_template()
        fs = VirtualFS(template=template)
        results = fs.grep("/var/log/auth.log", "45.152.66.201")
        assert len(results) > 0

    def test_home_yaml_deleted_files_in_trash(self):
        template = self._load_yaml_template()
        fs = VirtualFS(template=template)
        trash_paths = [p for p, _ in fs.list_trash()]
        assert any("exfil.py" in p for p in trash_paths)
        assert any("syslog.1" in p for p in trash_paths)

    def test_home_yaml_broken_symlinks(self):
        template = self._load_yaml_template()
        fs = VirtualFS(template=template)
        assert fs.symlink_is_broken("/home/user/tools/decrypt")
        assert fs.symlink_is_broken("/tmp/.sk_tmp_003.swp")

    def test_home_yaml_encrypted_files(self):
        template = self._load_yaml_template()
        fs = VirtualFS(template=template)
        core_entry = next(e for e in fs.list_dir("/home/user/evidence") if e.name == "core.enc")
        assert core_entry.encrypted
        shadow_entry = next(e for e in fs.list_dir("/etc") if e.name == "shadow")
        assert shadow_entry.encrypted

    def test_home_yaml_narrative_breadcrumbs(self):
        template = self._load_yaml_template()
        fs = VirtualFS(template=template)
        # The anomaly email predates everything
        anomaly = next(
            e for e in fs.list_dir("/home/user/.old_emails")
            if "anomaly" in e.name
        )
        assert anomaly.modified.year == 2025
