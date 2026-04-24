"""In-memory Unix-like virtual filesystem."""
from __future__ import annotations

import copy
import fnmatch
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FSError(Exception):
    """Base filesystem exception."""


class FSNotFoundError(FSError):
    """Path does not exist."""


class FSPermissionError(FSError):
    """Permission denied."""


class FSExistsError(FSError):
    """Path already exists."""


class FSNotADirectoryError(FSError):
    """Expected a directory but got a file."""


class FSIsADirectoryError(FSError):
    """Expected a file but got a directory."""


class FSSymlinkLoopError(FSError):
    """Circular symlink chain detected."""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

_DEFAULT_FILE_PERMS = "644"
_DEFAULT_DIR_PERMS = "755"
_DEFAULT_USER = "user"
_TRASH_MAX = 50


@dataclass
class Permissions:
    owner_read: bool
    owner_write: bool
    owner_exec: bool
    group_read: bool
    group_write: bool
    group_exec: bool
    other_read: bool
    other_write: bool
    other_exec: bool

    def to_octal(self) -> str:
        def _b(r: bool, w: bool, x: bool) -> int:
            return (4 if r else 0) | (2 if w else 0) | (1 if x else 0)

        return (
            str(_b(self.owner_read, self.owner_write, self.owner_exec))
            + str(_b(self.group_read, self.group_write, self.group_exec))
            + str(_b(self.other_read, self.other_write, self.other_exec))
        )

    def to_string(self) -> str:
        def _c(flag: bool, ch: str) -> str:
            return ch if flag else "-"

        return (
            _c(self.owner_read, "r")
            + _c(self.owner_write, "w")
            + _c(self.owner_exec, "x")
            + _c(self.group_read, "r")
            + _c(self.group_write, "w")
            + _c(self.group_exec, "x")
            + _c(self.other_read, "r")
            + _c(self.other_write, "w")
            + _c(self.other_exec, "x")
        )

    @classmethod
    def from_octal(cls, octal: str | int) -> Permissions:
        s = str(octal).zfill(3)[-3:]
        u, g, o = int(s[0]), int(s[1]), int(s[2])
        return cls(
            owner_read=bool(u & 4),
            owner_write=bool(u & 2),
            owner_exec=bool(u & 1),
            group_read=bool(g & 4),
            group_write=bool(g & 2),
            group_exec=bool(g & 1),
            other_read=bool(o & 4),
            other_write=bool(o & 2),
            other_exec=bool(o & 1),
        )


@dataclass
class FSEntry:
    name: str
    is_dir: bool
    size: int
    permissions: str  # "rwxr-xr-x"
    owner: str
    group: str
    modified: datetime
    content: str | None  # None for directories
    encrypted: bool = False
    binary: bool = False
    is_symlink: bool = False
    link_target: str = ""


@dataclass
class GrepResult:
    path: str
    line_number: int
    line: str


@dataclass
class _Node:
    name: str
    is_dir: bool
    content: str
    permissions: Permissions
    owner: str
    group: str
    modified: datetime
    children: dict[str, _Node] = field(default_factory=dict)
    encrypted: bool = False   # cat renders as hex; cleartext in content
    binary: bool = False      # non-text file hint
    is_symlink: bool = False
    link_target: str = ""     # absolute target path (resolved at creation)

    def to_entry(self) -> FSEntry:
        return FSEntry(
            name=self.name,
            is_dir=self.is_dir,
            size=len(self.content.encode()) if self.content else 0,
            permissions=self.permissions.to_string(),
            owner=self.owner,
            group=self.group,
            modified=self.modified,
            content=None if self.is_dir else self.content,
            encrypted=self.encrypted,
            binary=self.binary,
            is_symlink=self.is_symlink,
            link_target=self.link_target,
        )

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "is_dir": self.is_dir,
            "content": self.content,
            "permissions": self.permissions.to_octal(),
            "owner": self.owner,
            "group": self.group,
            "modified": self.modified.isoformat(),
            "encrypted": self.encrypted,
            "binary": self.binary,
            "is_symlink": self.is_symlink,
            "link_target": self.link_target,
        }
        if self.is_dir:
            d["children"] = {k: v.to_dict() for k, v in self.children.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> _Node:
        node = cls(
            name=d["name"],
            is_dir=d["is_dir"],
            content=d.get("content", ""),
            permissions=Permissions.from_octal(d.get("permissions", _DEFAULT_FILE_PERMS)),
            owner=d.get("owner", _DEFAULT_USER),
            group=d.get("group", _DEFAULT_USER),
            modified=datetime.fromisoformat(d["modified"]),
            encrypted=d.get("encrypted", False),
            binary=d.get("binary", False),
            is_symlink=d.get("is_symlink", False),
            link_target=d.get("link_target", ""),
        )
        if node.is_dir:
            for name, child_dict in d.get("children", {}).items():
                node.children[name] = cls.from_dict(child_dict)
        return node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_timestamp(ts: str | None) -> datetime:
    if ts is None:
        return datetime.now()
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.now()


# ---------------------------------------------------------------------------
# VirtualFS
# ---------------------------------------------------------------------------


class VirtualFS:
    def __init__(self, template: dict | None = None) -> None:
        self._root = _Node(
            name="",
            is_dir=True,
            content="",
            permissions=Permissions.from_octal("755"),
            owner="root",
            group="root",
            modified=datetime.now(),
        )
        self._home = "/home/user"
        self._user = _DEFAULT_USER
        self._cwd = self._home

        # Recoverable deleted files: original_path → _Node
        self._trash: dict[str, _Node] = {}
        self._trash_order: list[str] = []

        if template:
            self._load_template(template)

    # --- Navigation ---

    def resolve_path(self, path: str) -> str:
        """Resolve absolute/relative/~/.. path to a canonical absolute path."""
        if not path:
            return self._cwd

        if path == "~":
            return self._home
        if path.startswith("~/"):
            path = self._home + path[1:]

        if not path.startswith("/"):
            path = self._cwd.rstrip("/") + "/" + path

        parts: list[str] = []
        for part in path.split("/"):
            if not part or part == ".":
                continue
            if part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)

        return "/" + "/".join(parts)

    def get_cwd(self) -> str:
        return self._cwd

    def set_cwd(self, path: str) -> None:
        resolved = self.resolve_path(path)
        node = self._get_node(resolved)
        if not node.is_dir:
            raise FSNotADirectoryError(f"not a directory: {resolved}")
        self._cwd = resolved

    # --- File operations ---

    def read_file(self, path: str) -> str:
        node = self._get_node(path)
        if node.is_dir:
            raise FSIsADirectoryError(f"is a directory: {path}")
        return node.content

    def write_file(self, path: str, content: str, append: bool = False) -> None:
        resolved = self.resolve_path(path)
        try:
            node = self._get_node(resolved)
            if node.is_dir:
                raise FSIsADirectoryError(f"is a directory: {path}")
            node.content = (node.content or "") + content if append else content
            node.modified = datetime.now()
        except FSNotFoundError:
            parent, name = self._get_parent(resolved)
            parent.children[name] = _Node(
                name=name,
                is_dir=False,
                content=content,
                permissions=Permissions.from_octal(_DEFAULT_FILE_PERMS),
                owner=self._user,
                group=self._user,
                modified=datetime.now(),
            )

    def file_exists(self, path: str) -> bool:
        try:
            self._get_node(path)
            return True
        except FSError:
            return False

    def is_dir(self, path: str) -> bool:
        try:
            return self._get_node(path).is_dir
        except FSError:
            return False

    def is_file(self, path: str) -> bool:
        try:
            return not self._get_node(path).is_dir
        except FSError:
            return False

    # --- Directory operations ---

    def list_dir(self, path: str) -> list[FSEntry]:
        node = self._get_node(path)
        if not node.is_dir:
            raise FSNotADirectoryError(f"not a directory: {path}")
        return [child.to_entry() for child in node.children.values()]

    def make_dir(self, path: str, parents: bool = False) -> None:
        resolved = self.resolve_path(path)

        if not parents:
            if self.file_exists(resolved):
                raise FSExistsError(f"file exists: {resolved}")
            parent, name = self._get_parent(resolved)
            parent.children[name] = _Node(
                name=name,
                is_dir=True,
                content="",
                permissions=Permissions.from_octal(_DEFAULT_DIR_PERMS),
                owner=self._user,
                group=self._user,
                modified=datetime.now(),
            )
        else:
            node = self._root
            for part in (p for p in resolved.split("/") if p):
                if part not in node.children:
                    node.children[part] = _Node(
                        name=part,
                        is_dir=True,
                        content="",
                        permissions=Permissions.from_octal(_DEFAULT_DIR_PERMS),
                        owner=self._user,
                        group=self._user,
                        modified=datetime.now(),
                    )
                elif not node.children[part].is_dir:
                    raise FSNotADirectoryError(f"not a directory: {part}")
                node = node.children[part]

    def remove(self, path: str, recursive: bool = False, permanent: bool = False) -> None:
        """Remove a path. By default, moves to recoverable trash instead of destroying."""
        resolved = self.resolve_path(path)
        if resolved == "/":
            raise FSError("cannot remove root")

        node = self._get_node(resolved, follow_symlinks=False)
        if node.is_dir and not recursive:
            raise FSIsADirectoryError(f"is a directory: {resolved}")

        parent, name = self._get_parent(resolved)
        node = parent.children.pop(name)

        if not permanent:
            self._send_to_trash(resolved, node)

    # --- Symlinks ---

    def make_symlink(self, link_path: str, target: str) -> None:
        """Create a symbolic link at link_path pointing to target."""
        resolved_link = self.resolve_path(link_path)
        # Resolve relative targets relative to link's parent directory
        if not target.startswith("/"):
            parent_path = resolved_link.rpartition("/")[0] or "/"
            target = self.resolve_path(parent_path + "/" + target)

        parent, name = self._get_parent(resolved_link)
        parent.children[name] = _Node(
            name=name,
            is_dir=False,
            content="",
            permissions=Permissions.from_octal("777"),  # symlinks always 777
            owner=self._user,
            group=self._user,
            modified=datetime.now(),
            is_symlink=True,
            link_target=target,
        )

    def readlink(self, path: str) -> str:
        """Return the target of a symbolic link."""
        node = self._get_node(path, follow_symlinks=False)
        if not node.is_symlink:
            raise FSError(f"not a symbolic link: {path}")
        return node.link_target

    def path_is_symlink(self, path: str) -> bool:
        try:
            return self._get_node(path, follow_symlinks=False).is_symlink
        except FSError:
            return False

    def symlink_is_broken(self, path: str) -> bool:
        """True if path is a symlink whose target does not exist."""
        if not self.path_is_symlink(path):
            return False
        target = self.readlink(path)
        return not self.file_exists(target)

    # --- Trash / recovery ---

    def list_trash(self) -> list[tuple[str, FSEntry]]:
        """Return (original_path, FSEntry) for each recoverable deleted item."""
        return [(path, node.to_entry()) for path, node in self._trash.items()]

    def recover(self, original_path: str) -> None:
        """Restore a deleted item from trash to its original location."""
        if original_path not in self._trash:
            raise FSNotFoundError(f"nothing recoverable at: {original_path}")

        node = self._trash.pop(original_path)
        self._trash_order.remove(original_path)

        parent_path = original_path.rpartition("/")[0] or "/"
        try:
            parent = self._get_node(parent_path)
        except FSNotFoundError:
            self.make_dir(parent_path, parents=True)
            parent = self._get_node(parent_path)

        parent.children[node.name] = node

    # --- Copy / Move ---

    def copy(self, src: str, dst: str) -> None:
        src_resolved = self.resolve_path(src)
        dst_resolved = self.resolve_path(dst)
        src_node = self._get_node(src_resolved)  # follows symlinks

        try:
            dst_node = self._get_node(dst_resolved)
            if dst_node.is_dir:
                dst_resolved = dst_resolved.rstrip("/") + "/" + src_node.name
        except FSNotFoundError:
            pass

        parent, name = self._get_parent(dst_resolved)
        new_node = copy.deepcopy(src_node)
        new_node.name = name
        parent.children[name] = new_node

    def move(self, src: str, dst: str) -> None:
        src_resolved = self.resolve_path(src)
        dst_resolved = self.resolve_path(dst)
        src_node = self._get_node(src_resolved, follow_symlinks=False)  # move the link, not target

        try:
            dst_node = self._get_node(dst_resolved)
            if dst_node.is_dir:
                dst_resolved = dst_resolved.rstrip("/") + "/" + src_node.name
        except FSNotFoundError:
            pass

        src_parent, src_name = self._get_parent(src_resolved)
        dst_parent, dst_name = self._get_parent(dst_resolved)

        node = src_parent.children.pop(src_name)
        node.name = dst_name
        dst_parent.children[dst_name] = node

    # --- Permissions ---

    def get_permissions(self, path: str) -> Permissions:
        return self._get_node(path).permissions

    def set_permissions(self, path: str, mode: str) -> None:
        self._get_node(path).permissions = Permissions.from_octal(mode)

    def check_permission(self, path: str, action: str) -> bool:
        node = self._get_node(path)
        p = node.permissions
        if node.owner == self._user:
            return {"read": p.owner_read, "write": p.owner_write, "execute": p.owner_exec, "exec": p.owner_exec}.get(
                action, False
            )
        return {"read": p.other_read, "write": p.other_write, "execute": p.other_exec, "exec": p.other_exec}.get(
            action, False
        )

    # --- Search ---

    def find(self, path: str, pattern: str) -> list[str]:
        results: list[str] = []
        resolved = self.resolve_path(path)
        self._find_recursive(resolved, self._get_node(resolved), pattern, results)
        return sorted(results)

    def grep(self, path: str, pattern: str, recursive: bool = False) -> list[GrepResult]:
        results: list[GrepResult] = []
        resolved = self.resolve_path(path)
        node = self._get_node(resolved)

        if node.is_dir:
            if recursive:
                self._grep_recursive(resolved, node, pattern, results)
            else:
                for name, child in node.children.items():
                    if not child.is_dir:
                        self._grep_file(resolved.rstrip("/") + "/" + name, child, pattern, results)
        else:
            self._grep_file(resolved, node, pattern, results)

        return results

    # --- Hex rendering ---

    @staticmethod
    def render_hex(content: str) -> str:
        """Render content as a hexdump -C style output."""
        data = content.encode("utf-8", errors="replace")
        lines = []
        for i in range(0, max(len(data), 1), 16):
            chunk = data[i : i + 16]
            left = " ".join(f"{b:02x}" for b in chunk[:8])
            right = " ".join(f"{b:02x}" for b in chunk[8:])
            hex_display = f"{left:<23}  {right:<23}"
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{i:08x}  {hex_display}  |{ascii_part}|")
        return "\n".join(lines)

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {
            "cwd": self._cwd,
            "home": self._home,
            "user": self._user,
            "root": self._root.to_dict(),
            "trash": {path: node.to_dict() for path, node in self._trash.items()},
            "trash_order": list(self._trash_order),
        }

    def from_dict(self, data: dict) -> None:
        self._cwd = data["cwd"]
        self._home = data["home"]
        self._user = data["user"]
        self._root = _Node.from_dict(data["root"])
        self._trash = {path: _Node.from_dict(d) for path, d in data.get("trash", {}).items()}
        self._trash_order = data.get("trash_order", [])

    # --- Internal helpers ---

    def _get_node(
        self,
        path: str,
        *,
        follow_symlinks: bool = True,
        _seen: set[str] | None = None,
    ) -> _Node:
        """Traverse the tree to path.

        follow_symlinks=True  → follows all symlinks (stat semantics)
        follow_symlinks=False → follows intermediate symlinks but returns the
                                 final symlink node itself (lstat semantics)
        """
        resolved = self.resolve_path(path)
        if resolved == "/":
            return self._root

        if _seen is None:
            _seen = set()

        parts = resolved.strip("/").split("/")
        node = self._root

        for idx, part in enumerate(parts):
            if not node.is_dir:
                raise FSNotADirectoryError(f"not a directory in path: {resolved}")
            if part not in node.children:
                raise FSNotFoundError(f"no such file or directory: {resolved}")

            child = node.children[part]
            is_last = idx == len(parts) - 1

            if child.is_symlink and (follow_symlinks or not is_last):
                target = child.link_target
                if target in _seen:
                    raise FSSymlinkLoopError(f"too many levels of symbolic links: {resolved}")
                child = self._get_node(
                    target,
                    follow_symlinks=follow_symlinks,
                    _seen=_seen | {target},
                )

            node = child

        return node

    def _get_parent(self, path: str) -> tuple[_Node, str]:
        resolved = self.resolve_path(path)
        if resolved == "/":
            raise FSError("path has no parent: /")
        parent_path, _, name = resolved.rpartition("/")
        parent = self._get_node(parent_path or "/")
        if not parent.is_dir:
            raise FSNotADirectoryError(f"not a directory: {parent_path or '/'}")
        return parent, name

    def _send_to_trash(self, path: str, node: _Node) -> None:
        if path in self._trash:
            self._trash_order.remove(path)
        self._trash[path] = node
        self._trash_order.append(path)
        if len(self._trash_order) > _TRASH_MAX:
            oldest = self._trash_order.pop(0)
            del self._trash[oldest]

    def _find_recursive(self, current_path: str, node: _Node, pattern: str, results: list[str]) -> None:
        if not node.is_dir:
            return
        for name, child in node.children.items():
            child_path = current_path.rstrip("/") + "/" + name
            if fnmatch.fnmatch(name, pattern):
                results.append(child_path)
            if child.is_dir:
                self._find_recursive(child_path, child, pattern, results)

    def _grep_file(self, path: str, node: _Node, pattern: str, results: list[GrepResult]) -> None:
        try:
            regex = re.compile(pattern)
            use_regex = True
        except re.error:
            use_regex = False

        for i, line in enumerate(node.content.splitlines(), 1):
            match = regex.search(line) if use_regex else pattern in line
            if match:
                results.append(GrepResult(path=path, line_number=i, line=line))

    def _grep_recursive(self, path: str, node: _Node, pattern: str, results: list[GrepResult]) -> None:
        for name, child in node.children.items():
            child_path = path.rstrip("/") + "/" + name
            if child.is_dir:
                self._grep_recursive(child_path, child, pattern, results)
            else:
                self._grep_file(child_path, child, pattern, results)

    def _load_template(self, template: dict) -> None:
        for root_path, contents in template.items():
            self._ensure_dir_path(root_path)
            if isinstance(contents, dict):
                self._load_dir_contents(self._get_node(root_path), contents, current_path=root_path)

    def _ensure_dir_path(self, path: str, owner: str = "root") -> None:
        node = self._root
        for part in (p for p in path.split("/") if p):
            if part not in node.children:
                node.children[part] = _Node(
                    name=part,
                    is_dir=True,
                    content="",
                    permissions=Permissions.from_octal(_DEFAULT_DIR_PERMS),
                    owner=owner,
                    group=owner,
                    modified=datetime.now(),
                )
            node = node.children[part]

    def _load_dir_contents(
        self,
        node: _Node,
        contents: dict,
        default_owner: str = _DEFAULT_USER,
        current_path: str = "",
    ) -> None:
        for name, value in contents.items():
            if name == "_meta":
                if isinstance(value, dict):
                    if "permissions" in value:
                        node.permissions = Permissions.from_octal(str(value["permissions"]))
                    if "timestamp" in value:
                        node.modified = _parse_timestamp(value["timestamp"])
                    owner = value.get("owner", default_owner)
                    node.owner = owner
                    node.group = value.get("group", owner)
                continue

            if name.endswith("/"):
                dir_name = name.rstrip("/")
                meta: dict = value.get("_meta", {}) if isinstance(value, dict) else {}
                owner = meta.get("owner", default_owner)
                child = _Node(
                    name=dir_name,
                    is_dir=True,
                    content="",
                    permissions=Permissions.from_octal(str(meta.get("permissions", _DEFAULT_DIR_PERMS))),
                    owner=owner,
                    group=meta.get("group", owner),
                    modified=_parse_timestamp(meta.get("timestamp")),
                )
                node.children[dir_name] = child
                child_path = current_path.rstrip("/") + "/" + dir_name
                if isinstance(value, dict):
                    self._load_dir_contents(
                        child,
                        {k: v for k, v in value.items() if k != "_meta"},
                        owner,
                        current_path=child_path,
                    )
            else:
                if not isinstance(value, dict):
                    file_node = _Node(
                        name=name,
                        is_dir=False,
                        content=str(value) if value is not None else "",
                        permissions=Permissions.from_octal(_DEFAULT_FILE_PERMS),
                        owner=default_owner,
                        group=default_owner,
                        modified=datetime.now(),
                    )
                    node.children[name] = file_node
                    continue

                # Symlink: indicated by presence of link_target key
                if "link_target" in value:
                    target = value["link_target"]
                    if not target.startswith("/"):
                        target = self.resolve_path(current_path + "/" + target)
                    owner = value.get("owner", default_owner)
                    sym_node = _Node(
                        name=name,
                        is_dir=False,
                        content="",
                        permissions=Permissions.from_octal("777"),
                        owner=owner,
                        group=value.get("group", owner),
                        modified=_parse_timestamp(value.get("timestamp")),
                        is_symlink=True,
                        link_target=target,
                    )
                    deleted = value.get("deleted", False)
                    file_path = current_path.rstrip("/") + "/" + name
                    if deleted:
                        self._send_to_trash(file_path, sym_node)
                    else:
                        node.children[name] = sym_node
                    continue

                # Regular file
                content = value.get("content", "")
                owner = value.get("owner", default_owner)
                file_node = _Node(
                    name=name,
                    is_dir=False,
                    content=content,
                    permissions=Permissions.from_octal(str(value.get("permissions", _DEFAULT_FILE_PERMS))),
                    owner=owner,
                    group=value.get("group", owner),
                    modified=_parse_timestamp(value.get("timestamp")),
                    encrypted=value.get("encrypted", False),
                    binary=value.get("binary", False),
                )
                deleted = value.get("deleted", False)
                file_path = current_path.rstrip("/") + "/" + name
                if deleted:
                    self._send_to_trash(file_path, file_node)
                else:
                    node.children[name] = file_node
