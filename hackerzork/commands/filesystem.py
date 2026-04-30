"""Filesystem commands: ls, cd, cat, pwd, mkdir, rm, cp, mv, chmod, ln, stat,
touch, file, xxd, strings, wc, head, tail, grep, find, recover, more, less."""
from __future__ import annotations

import fnmatch
import re
from datetime import datetime

from hackerzork.engine.command_registry import CommandContext, register_command
from hackerzork.systems.virtual_fs import (
    FSEntry,
    FSError,
    FSExistsError,
    FSIsADirectoryError,
    FSNotADirectoryError,
    FSNotFoundError,
)

_CAT = "filesystem"


# ---------------------------------------------------------------------------
# Path / flag helpers
# ---------------------------------------------------------------------------


def _cwd(ctx: CommandContext) -> str:
    return ctx.env.get("CWD", "/home/user")


def _resolve(ctx: CommandContext, path: str) -> str:
    """Resolve a path to absolute using the shell env's CWD."""
    if not path:
        return _cwd(ctx)

    home = ctx.env.get("HOME", "/home/user")
    cwd = _cwd(ctx)

    if path == "~":
        return home
    if path.startswith("~/"):
        path = home + path[1:]

    if not path.startswith("/"):
        path = cwd.rstrip("/") + "/" + path

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


def _parse_flags(args: list[str]) -> tuple[set[str], list[str]]:
    """Split args into (boolean_flags, positional_args).

    Short flags (-la) are expanded into individual chars.
    Long flags (--shred) stored as the word after --.
    Numeric-only shorts (-10) treated as positional.
    """
    flags: set[str] = set()
    positional: list[str] = []
    after_dashdash = False
    for a in args:
        if after_dashdash:
            positional.append(a)
        elif a == "--":
            after_dashdash = True
        elif a.startswith("--") and len(a) > 2:
            flags.add(a[2:])
        elif a.startswith("-") and len(a) > 1 and not a[1:].isdigit():
            for ch in a[1:]:
                flags.add(ch)
        else:
            positional.append(a)
    return flags, positional


def _parse_n_flag(args: list[str], default: int) -> tuple[int, list[str]]:
    """Extract -n N or -N from args. Returns (count, remaining_positionals)."""
    n = default
    positional: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-n" and i + 1 < len(args):
            try:
                n = int(args[i + 1])
                i += 2
                continue
            except ValueError:
                pass
        elif a.startswith("-") and len(a) > 1 and a[1:].isdigit():
            n = int(a[1:])
        elif not a.startswith("-"):
            positional.append(a)
        i += 1
    return n, positional


def _apply_symbolic_chmod(mode_str: str, current_octal: str) -> str:
    """Apply a symbolic chmod expression like 'u+x,go-w' to a 3-digit octal string."""
    s = current_octal.zfill(3)[-3:]
    u_d, g_d, o_d = int(s[0]), int(s[1]), int(s[2])
    bits = [
        bool(u_d & 4), bool(u_d & 2), bool(u_d & 1),
        bool(g_d & 4), bool(g_d & 2), bool(g_d & 1),
        bool(o_d & 4), bool(o_d & 2), bool(o_d & 1),
    ]

    who_map = {"u": [0, 1, 2], "g": [3, 4, 5], "o": [6, 7, 8]}
    perm_off = {"r": 0, "w": 1, "x": 2}

    for clause in mode_str.split(","):
        m = re.match(r"^([ugoa]*)([+\-=])([rwx]*)$", clause.strip())
        if not m:
            continue
        who_str, op, what_str = m.group(1), m.group(2), m.group(3)

        if not who_str or "a" in who_str:
            groups = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
        else:
            seen: set[str] = set()
            groups = []
            for ch in who_str:
                if ch in who_map and ch not in seen:
                    groups.append(who_map[ch])
                    seen.add(ch)

        for group in groups:
            if op == "=":
                for idx in group:
                    bits[idx] = False
            for ch in what_str:
                if ch in perm_off:
                    idx = group[perm_off[ch]]
                    if op in ("+", "="):
                        bits[idx] = True
                    elif op == "-":
                        bits[idx] = False

    u = (4 if bits[0] else 0) | (2 if bits[1] else 0) | (1 if bits[2] else 0)
    g = (4 if bits[3] else 0) | (2 if bits[4] else 0) | (1 if bits[5] else 0)
    o = (4 if bits[6] else 0) | (2 if bits[7] else 0) | (1 if bits[8] else 0)
    return f"{u}{g}{o}"


def _extract_strings(content: str, min_len: int = 4) -> list[str]:
    return re.findall(r"[ -~]{" + str(min_len) + r",}", content)


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%b %d %H:%M")


def _fmt_long(entry: FSEntry, name: str) -> str:
    type_char = "l" if entry.is_symlink else "d" if entry.is_dir else "-"
    date = _fmt_date(entry.modified)
    if entry.is_symlink:
        display = f"{name} -> {entry.link_target}"
    elif entry.is_dir:
        display = name + "/"
    else:
        display = name
    return f"{type_char}{entry.permissions}  {entry.owner}  {entry.group}  {entry.size:>8}  {date}  {display}"


# ---------------------------------------------------------------------------
# ls internals
# ---------------------------------------------------------------------------


def _ls_dir_lines(ctx: CommandContext, path: str, show_all: bool, long_fmt: bool) -> list[str]:
    entries = ctx.fs.list_dir(path)
    visible = [e for e in entries if show_all or not e.name.startswith(".")]
    visible.sort(key=lambda e: e.name.lstrip(".").lower())

    if long_fmt:
        total = sum(e.size for e in visible)
        lines: list[str] = [f"total {total}"]
        lines.extend(_fmt_long(e, e.name) for e in visible)
        return lines

    names: list[str] = []
    for e in visible:
        if e.is_dir:
            names.append(e.name + "/")
        elif e.is_symlink:
            names.append(e.name + "@")
        else:
            names.append(e.name)
    return ["  ".join(names)] if names else []


def _ls_recursive(ctx: CommandContext, path: str, show_all: bool, long_fmt: bool) -> list[str]:
    out = [path + ":"]
    out.extend(_ls_dir_lines(ctx, path, show_all, long_fmt))

    try:
        entries = ctx.fs.list_dir(path)
    except FSError:
        return out

    for e in sorted(entries, key=lambda x: x.name):
        if e.is_dir and (show_all or not e.name.startswith(".")):
            subpath = path.rstrip("/") + "/" + e.name
            out.append("")
            try:
                out.extend(_ls_recursive(ctx, subpath, show_all, long_fmt))
            except FSError:
                pass
    return out


# ---------------------------------------------------------------------------
# grep internals
# ---------------------------------------------------------------------------


def _grep_file_lines(
    content: str,
    match_fn,
    *,
    invert: bool,
    show_numbers: bool,
    prefix: str,
) -> list[str]:
    out: list[str] = []
    for i, line in enumerate(content.splitlines(), 1):
        hit = match_fn(line)
        if invert:
            hit = not hit
        if hit:
            out.append(f"{prefix}{i}:{line}" if show_numbers else f"{prefix}{line}")
    return out


def _grep_node(
    ctx: CommandContext,
    path: str,
    display: str,
    match_fn,
    results: list[str],
    *,
    invert: bool,
    show_numbers: bool,
    filenames_only: bool,
    recursive: bool,
    show_path: bool,
) -> None:
    node = ctx.fs._get_node(path)

    if node.is_dir:
        if recursive:
            for name in list(node.children):
                child_path = path.rstrip("/") + "/" + name
                child_display = display.rstrip("/") + "/" + name
                try:
                    _grep_node(
                        ctx, child_path, child_display, match_fn, results,
                        invert=invert, show_numbers=show_numbers,
                        filenames_only=filenames_only, recursive=True,
                        show_path=True,
                    )
                except FSError:
                    pass
        return

    if node.encrypted or node.binary:
        if not invert and any(match_fn(line) for line in node.content.splitlines()):
            results.append(f"grep: {display}: binary file matches")
        return

    prefix = (display + ":") if show_path else ""
    matched_lines = _grep_file_lines(
        node.content, match_fn, invert=invert, show_numbers=show_numbers, prefix=prefix
    )
    if filenames_only:
        if matched_lines:
            results.append(display)
    else:
        results.extend(matched_lines)


# ---------------------------------------------------------------------------
# find internals
# ---------------------------------------------------------------------------


def _find_walk(
    ctx: CommandContext,
    path: str,
    display: str,
    name_pattern: str | None,
    type_filter: str | None,
    newer_time: datetime | None,
    results: list[str],
) -> None:
    node = ctx.fs._get_node(path)
    if not node.is_dir:
        return

    for name, child in node.children.items():
        child_path = path.rstrip("/") + "/" + name
        child_display = display.rstrip("/") + "/" + name

        type_ok = (
            type_filter is None
            or (type_filter == "f" and not child.is_dir)
            or (type_filter == "d" and child.is_dir)
        )
        name_ok = name_pattern is None or fnmatch.fnmatch(name, name_pattern)
        newer_ok = newer_time is None or child.modified > newer_time

        if type_ok and name_ok and newer_ok:
            results.append(child_display)

        if child.is_dir:
            try:
                _find_walk(ctx, child_path, child_display, name_pattern, type_filter, newer_time, results)
            except FSError:
                pass


# ---------------------------------------------------------------------------
# pwd
# ---------------------------------------------------------------------------


@register_command(
    name="pwd",
    usage="pwd",
    help_text="Print working directory",
    category=_CAT,
)
def cmd_pwd(ctx: CommandContext, args: list[str]) -> str:
    return _cwd(ctx)


# ---------------------------------------------------------------------------
# cd
# ---------------------------------------------------------------------------


@register_command(
    name="cd",
    usage="cd [path]",
    help_text="Change working directory",
    category=_CAT,
)
def cmd_cd(ctx: CommandContext, args: list[str]) -> str:
    old = _cwd(ctx)

    if not args:
        target = ctx.env.get("HOME", "/home/user")
    elif args[0] == "-":
        target = ctx.env.get("OLDPWD", old)
    else:
        target = _resolve(ctx, args[0])

    try:
        ctx.fs.set_cwd(target)
    except FSNotFoundError:
        label = args[0] if args else target
        return f"bash: cd: {label}: No such file or directory"
    except FSNotADirectoryError:
        label = args[0] if args else target
        return f"bash: cd: {label}: Not a directory"

    ctx.env["OLDPWD"] = old
    ctx.env["CWD"] = target
    return ""


# ---------------------------------------------------------------------------
# ls
# ---------------------------------------------------------------------------


@register_command(
    name="ls",
    usage="ls [-laR] [path]",
    help_text="List directory contents",
    category=_CAT,
    aliases=["dir"],
)
def cmd_ls(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    show_all = "a" in flags
    long_fmt = "l" in flags
    recursive = "R" in flags

    path = _resolve(ctx, positional[0]) if positional else _cwd(ctx)
    label = positional[0] if positional else path

    try:
        node = ctx.fs._get_node(path)
    except FSNotFoundError:
        return f"ls: cannot access '{label}': No such file or directory"
    except FSError as e:
        return f"ls: {e}"

    if not node.is_dir:
        entry = node.to_entry()
        return _fmt_long(entry, entry.name) if long_fmt else entry.name

    if recursive:
        return "\n".join(_ls_recursive(ctx, path, show_all, long_fmt))

    return "\n".join(_ls_dir_lines(ctx, path, show_all, long_fmt))


# ---------------------------------------------------------------------------
# cat
# ---------------------------------------------------------------------------


@register_command(
    name="cat",
    usage="cat [-n] [file...]",
    help_text="Concatenate and print file contents",
    category=_CAT,
)
def cmd_cat(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    number_lines = "n" in flags

    if not positional:
        return ""

    parts: list[str] = []
    for path_str in positional:
        path = _resolve(ctx, path_str)
        try:
            node = ctx.fs._get_node(path)
            if node.is_dir:
                parts.append(f"bash: cat: {path_str}: Is a directory")
                continue
            if node.binary:
                parts.append(f"bash: cat: {path_str}: Binary file (use xxd to inspect)")
                continue
            if node.encrypted:
                parts.append("[ENCRYPTED — binary content]")
                parts.append(ctx.fs.render_hex(node.content))
                if ctx.events:
                    ctx.events.emit("encrypted_file_accessed", path=path, filename=node.name)
                continue
            content = node.content
            if number_lines:
                content = "\n".join(
                    f"{i:>6}  {line}" for i, line in enumerate(content.splitlines(), 1)
                )
            parts.append(content)
            if ctx.events:
                ctx.events.emit(
                    "file_read",
                    path=str(path),
                    name=node.name,
                    content=node.content,
                    modified=node.modified.isoformat() if node.modified else "",
                    owner=node.owner or "user",
                    encrypted=False,
                )
        except FSNotFoundError:
            parts.append(f"bash: cat: {path_str}: No such file or directory")
        except FSError as e:
            parts.append(f"bash: cat: {path_str}: {e}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# head / tail
# ---------------------------------------------------------------------------


@register_command(
    name="head",
    usage="head [-n N] [file]",
    help_text="Print first N lines of a file (default 10)",
    category=_CAT,
)
def cmd_head(ctx: CommandContext, args: list[str]) -> str:
    n, positional = _parse_n_flag(args, default=10)
    if not positional:
        return ""
    path = _resolve(ctx, positional[0])
    try:
        node = ctx.fs._get_node(path)
        if node.is_dir:
            return f"bash: head: {positional[0]}: Is a directory"
        if node.binary:
            return f"bash: head: {positional[0]}: Binary file (use xxd to inspect)"
        if node.encrypted:
            return "[ENCRYPTED — binary content]\n" + ctx.fs.render_hex(node.content)
        return "\n".join(node.content.splitlines()[:n])
    except FSNotFoundError:
        return f"bash: head: {positional[0]}: No such file or directory"
    except FSError as e:
        return f"bash: head: {positional[0]}: {e}"


@register_command(
    name="tail",
    usage="tail [-n N] [file]",
    help_text="Print last N lines of a file (default 10)",
    category=_CAT,
)
def cmd_tail(ctx: CommandContext, args: list[str]) -> str:
    n, positional = _parse_n_flag(args, default=10)
    if not positional:
        return ""
    path = _resolve(ctx, positional[0])
    try:
        node = ctx.fs._get_node(path)
        if node.is_dir:
            return f"bash: tail: {positional[0]}: Is a directory"
        if node.binary:
            return f"bash: tail: {positional[0]}: Binary file (use xxd to inspect)"
        if node.encrypted:
            return "[ENCRYPTED — binary content]\n" + ctx.fs.render_hex(node.content)
        lines = node.content.splitlines()
        return "\n".join(lines[-n:] if n > 0 else [])
    except FSNotFoundError:
        return f"bash: tail: {positional[0]}: No such file or directory"
    except FSError as e:
        return f"bash: tail: {positional[0]}: {e}"


# ---------------------------------------------------------------------------
# wc
# ---------------------------------------------------------------------------


@register_command(
    name="wc",
    usage="wc [-l] [-w] [-c] [file]",
    help_text="Count lines, words, and bytes in a file",
    category=_CAT,
)
def cmd_wc(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    if not positional:
        return ""
    path = _resolve(ctx, positional[0])
    try:
        node = ctx.fs._get_node(path)
        if node.is_dir:
            return f"bash: wc: {positional[0]}: Is a directory"
        content = node.content or ""
        line_count = len(content.splitlines())
        word_count = len(content.split())
        byte_count = len(content.encode())
        if "l" in flags:
            return f"{line_count} {positional[0]}"
        if "w" in flags:
            return f"{word_count} {positional[0]}"
        if "c" in flags:
            return f"{byte_count} {positional[0]}"
        return f"{line_count} {word_count} {byte_count} {positional[0]}"
    except FSNotFoundError:
        return f"bash: wc: {positional[0]}: No such file or directory"
    except FSError as e:
        return f"bash: wc: {positional[0]}: {e}"


# ---------------------------------------------------------------------------
# mkdir
# ---------------------------------------------------------------------------


@register_command(
    name="mkdir",
    usage="mkdir [-p] <dir...>",
    help_text="Create directories",
    category=_CAT,
)
def cmd_mkdir(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    parents = "p" in flags

    if not positional:
        return "bash: mkdir: missing operand"

    errors: list[str] = []
    for path_str in positional:
        path = _resolve(ctx, path_str)
        try:
            ctx.fs.make_dir(path, parents=parents)
        except FSExistsError:
            if not parents:
                errors.append(f"mkdir: cannot create directory '{path_str}': File exists")
        except FSNotFoundError:
            errors.append(
                f"mkdir: cannot create directory '{path_str}': No such file or directory"
            )
        except FSError as e:
            errors.append(f"mkdir: {e}")

    return "\n".join(errors)


# ---------------------------------------------------------------------------
# touch
# ---------------------------------------------------------------------------


@register_command(
    name="touch",
    usage="touch <file...>",
    help_text="Create empty files or update timestamps",
    category=_CAT,
)
def cmd_touch(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    if not positional:
        return "bash: touch: missing file operand"

    errors: list[str] = []
    for path_str in positional:
        path = _resolve(ctx, path_str)
        try:
            node = ctx.fs._get_node(path)
            node.modified = datetime.now()
        except FSNotFoundError:
            try:
                ctx.fs.write_file(path, "")
            except FSError as e:
                errors.append(f"touch: {path_str}: {e}")
        except FSError as e:
            errors.append(f"touch: {path_str}: {e}")

    return "\n".join(errors)


# ---------------------------------------------------------------------------
# rm
# ---------------------------------------------------------------------------


@register_command(
    name="rm",
    usage="rm [-r] [-f] [--shred] <path...>",
    help_text="Remove files (recoverable by default; --shred to destroy permanently)",
    category=_CAT,
)
def cmd_rm(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    recursive = "r" in flags or "recursive" in flags
    force = "f" in flags or "force" in flags
    shred = "shred" in flags

    if not positional:
        return "bash: rm: missing operand"

    out: list[str] = []
    for path_str in positional:
        path = _resolve(ctx, path_str)
        try:
            ctx.fs.remove(path, recursive=recursive, permanent=shred)
            if shred:
                out.append(f"shredding {path_str}...")
                if ctx.events:
                    ctx.events.emit("file_shredded", path=path)
        except FSNotFoundError:
            if not force:
                out.append(f"bash: rm: cannot remove '{path_str}': No such file or directory")
        except FSIsADirectoryError:
            out.append(f"bash: rm: cannot remove '{path_str}': Is a directory")
        except FSError as e:
            out.append(f"bash: rm: {path_str}: {e}")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# cp
# ---------------------------------------------------------------------------


@register_command(
    name="cp",
    usage="cp [-r] <src> <dst>",
    help_text="Copy files or directories",
    category=_CAT,
)
def cmd_cp(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    if len(positional) < 2:
        return "bash: cp: missing operand"

    src = _resolve(ctx, positional[0])
    dst = _resolve(ctx, positional[1])
    try:
        ctx.fs.copy(src, dst)
        return ""
    except FSNotFoundError as e:
        return f"bash: cp: {e}"
    except FSIsADirectoryError:
        return f"bash: cp: omitting directory '{positional[0]}' — use -r"
    except FSError as e:
        return f"bash: cp: {e}"


# ---------------------------------------------------------------------------
# mv
# ---------------------------------------------------------------------------


@register_command(
    name="mv",
    usage="mv <src> <dst>",
    help_text="Move or rename files",
    category=_CAT,
)
def cmd_mv(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    if len(positional) < 2:
        return "bash: mv: missing operand"

    src = _resolve(ctx, positional[0])
    dst = _resolve(ctx, positional[1])
    try:
        ctx.fs.move(src, dst)
        return ""
    except FSNotFoundError as e:
        return f"bash: mv: {e}"
    except FSError as e:
        return f"bash: mv: {e}"


# ---------------------------------------------------------------------------
# chmod
# ---------------------------------------------------------------------------


@register_command(
    name="chmod",
    usage="chmod <mode> <path>",
    help_text="Change file permissions (octal or symbolic)",
    category=_CAT,
)
def cmd_chmod(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    if len(positional) < 2:
        return "bash: chmod: missing operand"

    mode_str, path_str = positional[0], positional[1]
    path = _resolve(ctx, path_str)
    try:
        node = ctx.fs._get_node(path)
        if re.match(r"^[0-7]{1,4}$", mode_str):
            ctx.fs.set_permissions(path, mode_str)
        else:
            current = node.permissions.to_octal()
            ctx.fs.set_permissions(path, _apply_symbolic_chmod(mode_str, current))
        return ""
    except FSNotFoundError:
        return f"chmod: cannot access '{path_str}': No such file or directory"
    except FSError as e:
        return f"chmod: {e}"


# ---------------------------------------------------------------------------
# ln
# ---------------------------------------------------------------------------


@register_command(
    name="ln",
    usage="ln -s <target> <link>",
    help_text="Create a symbolic link",
    category=_CAT,
)
def cmd_ln(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    if "s" not in flags:
        return "ln: hard links not supported — use ln -s"
    if len(positional) < 2:
        return "bash: ln: missing operand"

    target = positional[0]
    link_path = _resolve(ctx, positional[1])
    try:
        ctx.fs.make_symlink(link_path, target)
        return ""
    except FSError as e:
        return f"ln: {e}"


# ---------------------------------------------------------------------------
# stat
# ---------------------------------------------------------------------------


@register_command(
    name="stat",
    usage="stat <path>",
    help_text="Display file status",
    category=_CAT,
)
def cmd_stat(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    if not positional:
        return "bash: stat: missing operand"

    path = _resolve(ctx, positional[0])
    try:
        node = ctx.fs._get_node(path, follow_symlinks=False)
        entry = node.to_entry()

        type_str = (
            "symbolic link" if entry.is_symlink
            else "directory" if entry.is_dir
            else "regular file"
        )
        type_char = "l" if entry.is_symlink else "d" if entry.is_dir else "-"
        octal = node.permissions.to_octal()

        lines = [
            f"  File: {entry.name}",
            f"  Size: {entry.size}",
            f"  Type: {type_str}",
            f"Perms: {type_char}{entry.permissions}  ({octal})",
            f"Owner: {entry.owner}  Group: {entry.group}",
            f" Mtime: {entry.modified.isoformat()}",
        ]
        if entry.is_symlink:
            broken = ctx.fs.symlink_is_broken(path)
            link_line = f"  Link: {entry.link_target}"
            if broken:
                link_line += " [BROKEN]"
            lines.append(link_line)

        return "\n".join(lines)
    except FSNotFoundError:
        return f"stat: cannot stat '{positional[0]}': No such file or directory"
    except FSError as e:
        return f"stat: {e}"


# ---------------------------------------------------------------------------
# file
# ---------------------------------------------------------------------------


@register_command(
    name="file",
    usage="file <path...>",
    help_text="Determine file type",
    category=_CAT,
)
def cmd_file(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    if not positional:
        return "bash: file: missing operand"

    results: list[str] = []
    for path_str in positional:
        path = _resolve(ctx, path_str)
        try:
            node = ctx.fs._get_node(path, follow_symlinks=False)
            if node.is_symlink:
                results.append(f"{path_str}: symbolic link to {node.link_target}")
            elif node.is_dir:
                results.append(f"{path_str}: directory")
            elif node.encrypted:
                results.append(f"{path_str}: encrypted data")
            elif node.binary:
                results.append(f"{path_str}: ELF 64-bit executable")
            elif not node.content:
                results.append(f"{path_str}: empty")
            else:
                results.append(f"{path_str}: ASCII text")
        except FSNotFoundError:
            results.append(f"file: {path_str}: No such file or directory")
        except FSError as e:
            results.append(f"file: {e}")

    return "\n".join(results)


# ---------------------------------------------------------------------------
# xxd
# ---------------------------------------------------------------------------


@register_command(
    name="xxd",
    usage="xxd <path>",
    help_text="Hex dump of a file",
    category=_CAT,
)
def cmd_xxd(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    if not positional:
        return "bash: xxd: missing operand"

    path = _resolve(ctx, positional[0])
    try:
        node = ctx.fs._get_node(path)
        if node.is_dir:
            return f"xxd: {positional[0]}: Is a directory"
        return ctx.fs.render_hex(node.content)
    except FSNotFoundError:
        return f"xxd: {positional[0]}: No such file or directory"
    except FSError as e:
        return f"xxd: {e}"


# ---------------------------------------------------------------------------
# strings
# ---------------------------------------------------------------------------


@register_command(
    name="strings",
    usage="strings [-n N] <path>",
    help_text="Extract printable strings from a file",
    category=_CAT,
)
def cmd_strings(ctx: CommandContext, args: list[str]) -> str:
    n, positional = _parse_n_flag(args, default=4)
    if not positional:
        return "bash: strings: missing operand"

    path = _resolve(ctx, positional[0])
    try:
        node = ctx.fs._get_node(path)
        if node.is_dir:
            return f"strings: {positional[0]}: Is a directory"
        found = _extract_strings(node.content, min_len=n)
        return "\n".join(found)
    except FSNotFoundError:
        return f"strings: {positional[0]}: No such file or directory"
    except FSError as e:
        return f"strings: {e}"


# ---------------------------------------------------------------------------
# grep
# ---------------------------------------------------------------------------


@register_command(
    name="grep",
    usage="grep [-rinvl] <pattern> [path...]",
    help_text="Search for a pattern in files",
    category=_CAT,
    aliases=["egrep"],
)
def cmd_grep(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)
    if not positional:
        return "bash: grep: missing pattern"

    pattern_str = positional[0]
    raw_paths = positional[1:] if len(positional) > 1 else []

    case_insensitive = "i" in flags
    show_numbers = "n" in flags
    invert = "v" in flags
    filenames_only = "l" in flags
    recursive = "r" in flags

    re_flags = re.IGNORECASE if case_insensitive else 0
    try:
        regex = re.compile(pattern_str, re_flags)

        def match_fn(line: str) -> bool:
            return bool(regex.search(line))
    except re.error:
        if case_insensitive:
            def match_fn(line: str) -> bool:  # type: ignore[misc]
                return pattern_str.lower() in line.lower()
        else:
            def match_fn(line: str) -> bool:  # type: ignore[misc]
                return pattern_str in line

    stdin = ctx.env.get("STDIN", "")
    if not raw_paths and stdin:
        # Input from a pipe — search the piped text directly
        lines = stdin.splitlines()
        results: list[str] = []
        for i, line in enumerate(lines, 1):
            matched = match_fn(line)
            if invert:
                matched = not matched
            if matched:
                prefix = f"{i}:" if show_numbers else ""
                results.append(f"{prefix}{line}")
        if ctx.events:
            ctx.events.emit("content_searched", pattern=pattern_str, path="<stdin>")
        return "\n".join(results)

    if not raw_paths:
        raw_paths = [_cwd(ctx)]

    results = []
    multiple = len(raw_paths) > 1 or recursive

    for path_str in raw_paths:
        path = _resolve(ctx, path_str)
        try:
            _grep_node(
                ctx, path, path_str, match_fn, results,
                invert=invert, show_numbers=show_numbers,
                filenames_only=filenames_only, recursive=recursive,
                show_path=multiple,
            )
        except FSNotFoundError:
            results.append(f"grep: {path_str}: No such file or directory")
        except FSError as e:
            results.append(f"grep: {e}")

    if ctx.events:
        ctx.events.emit("content_searched", pattern=pattern_str, path=str(raw_paths))

    return "\n".join(results)


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------


@register_command(
    name="find",
    usage="find [path] [-name <glob>] [-type <f|d>] [-newer <file>]",
    help_text="Search the filesystem for files matching criteria",
    category=_CAT,
)
def cmd_find(ctx: CommandContext, args: list[str]) -> str:
    name_pattern: str | None = None
    type_filter: str | None = None
    newer_ref: str | None = None
    start_paths: list[str] = []

    i = 0
    while i < len(args):
        a = args[i]
        if a == "-name" and i + 1 < len(args):
            name_pattern = args[i + 1]
            i += 2
        elif a == "-type" and i + 1 < len(args):
            type_filter = args[i + 1]
            i += 2
        elif a == "-newer" and i + 1 < len(args):
            newer_ref = args[i + 1]
            i += 2
        else:
            start_paths.append(a)
            i += 1

    search_path = _resolve(ctx, start_paths[0]) if start_paths else _cwd(ctx)

    newer_time: datetime | None = None
    if newer_ref:
        ref_path = _resolve(ctx, newer_ref)
        try:
            newer_time = ctx.fs._get_node(ref_path).modified
        except FSError:
            return f"find: '{newer_ref}': No such file or directory"

    results: list[str] = []
    try:
        _find_walk(ctx, search_path, search_path, name_pattern, type_filter, newer_time, results)
    except FSNotFoundError:
        return f"find: '{search_path}': No such file or directory"
    except FSError as e:
        return f"find: {e}"

    if ctx.events:
        ctx.events.emit("filesystem_searched", pattern=name_pattern, results_count=len(results))

    return "\n".join(sorted(results))


# ---------------------------------------------------------------------------
# recover
# ---------------------------------------------------------------------------


@register_command(
    name="recover",
    usage="recover [path]",
    help_text="Restore a deleted file from trash",
    category=_CAT,
)
def cmd_recover(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)

    if not positional:
        trash = ctx.fs.list_trash()
        if not trash:
            return "trash is empty"
        lines = ["Recoverable files:"]
        for orig_path, entry in trash:
            lines.append(f"  {orig_path}  ({entry.size} bytes)")
        return "\n".join(lines)

    path_str = positional[0]
    if not path_str.startswith("/"):
        path_str = _resolve(ctx, path_str)

    try:
        ctx.fs.recover(path_str)
        return f"recovered: {path_str}"
    except FSNotFoundError:
        return f"recover: nothing recoverable at '{path_str}'"
    except FSError as e:
        return f"recover: {e}"


# ---------------------------------------------------------------------------
# more / less
# ---------------------------------------------------------------------------


@register_command(
    name="more",
    usage="more [file...]",
    help_text="Page through file contents (non-interactive)",
    category=_CAT,
    aliases=["less"],
)
def cmd_more(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)

    stdin = ctx.env.get("STDIN", "")
    if not positional and stdin:
        return stdin + "\n(END)"

    if not positional:
        return ""

    parts: list[str] = []
    for path_str in positional:
        path = _resolve(ctx, path_str)
        try:
            node = ctx.fs._get_node(path)
            if node.is_dir:
                parts.append(f"more: {path_str}: Is a directory")
                continue
            if node.binary:
                parts.append(f"more: {path_str}: Binary file (use xxd to inspect)")
                continue
            if node.encrypted:
                parts.append("[ENCRYPTED — binary content]")
                parts.append(ctx.fs.render_hex(node.content))
                continue
            content = node.content
            if len(positional) > 1:
                parts.append(f":::::::::::::::\n{path_str}\n:::::::::::::::")
            parts.append(content)
        except FSNotFoundError:
            parts.append(f"more: {path_str}: No such file or directory")
        except FSError as e:
            parts.append(f"more: {path_str}: {e}")

    out = "\n".join(parts)
    return out + "\n(END)" if out else ""


# ---------------------------------------------------------------------------
# nano / vi / vim  — cosmetic interactive-style editor
# ---------------------------------------------------------------------------

def _nano_chrome(path_str: str, content: str, editor: str = "nano") -> str:
    """Render a fake editor view with header + content + keybinding footer."""
    # Truncate path display to avoid wrapping
    display_path = path_str if len(path_str) <= 50 else "…" + path_str[-47:]
    width = 78

    if editor == "nano":
        header = f"  GNU nano 7.2{' ' * (width - 12 - len(display_path))}{display_path}"
        footer1 = "^G Help       ^O Write Out  ^W Where Is   ^K Cut        ^C Location"
        footer2 = "^X Exit       ^R Read File  ^\\ Replace    ^U Paste      ^J Justify"
        sep = "─" * width
        lines = [
            f"\033[7m{header}\033[0m",   # reverse-video header
            "",
            content.rstrip("\n") if content else "",
            "",
            sep,
            f"\033[7m {footer1} \033[0m",
            f"\033[7m {footer2} \033[0m",
        ]
    else:
        # vi/vim chrome
        lines_count = len(content.splitlines()) if content else 0
        header = f"\033[7m {display_path}{' ' * max(0, width - len(display_path) - 1)}\033[0m"
        footer = f'"{display_path}"  {lines_count}L  --  :w<Enter> write  :q!<Enter> quit  :%s/old/new/g replace'
        lines = [
            header,
            content.rstrip("\n") if content else "",
            f'\033[2m{"~"}\033[0m',
            f"\033[7m {footer} \033[0m",
        ]

    note = (
        "\n\033[33m[!] Full interactive editing not available in this terminal.\033[0m\n"
        "\033[2m    To write:   echo \"text\" > " + path_str + "\033[0m\n"
        "\033[2m    To append:  echo \"text\" >> " + path_str + "\033[0m\n"
        "\033[2m    To replace: sed -i 's/old/new/g' " + path_str + "\033[0m"
    )
    return "\n".join(lines) + note


@register_command(
    name="nano",
    usage="nano [file]",
    help_text="Edit a file (cosmetic view — use echo/sed to write)",
    category="filesystem",
)
def cmd_nano(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    if not positional:
        return "nano: no filename given\nUsage: nano <file>"
    path = _resolve(ctx, positional[0])
    try:
        node = ctx.fs._get_node(path)
        if node.is_dir:
            return f"nano: {positional[0]}: Is a directory"
        if node.encrypted:
            return f"nano: {positional[0]}: File is encrypted — cannot open in editor"
        content = node.content or ""
    except FSNotFoundError:
        content = ""  # new file — nano creates it
    except FSError as e:
        return f"nano: {positional[0]}: {e}"
    return _nano_chrome(positional[0], content, editor="nano")


@register_command(
    name="vi",
    usage="vi [file]",
    help_text="Edit a file with vi (cosmetic view — use echo/sed to write)",
    category="filesystem",
    aliases=["vim"],
)
def cmd_vi(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    if not positional:
        return "vi: no filename given\nUsage: vi <file>"
    path = _resolve(ctx, positional[0])
    try:
        node = ctx.fs._get_node(path)
        if node.is_dir:
            return f"vi: {positional[0]}: Is a directory"
        if node.encrypted:
            return f"vi: {positional[0]}: File is encrypted"
        content = node.content or ""
    except FSNotFoundError:
        content = ""
    except FSError as e:
        return f"vi: {positional[0]}: {e}"
    return _nano_chrome(positional[0], content, editor="vi")


# ---------------------------------------------------------------------------
# sed
# ---------------------------------------------------------------------------

@register_command(
    name="sed",
    usage="sed [-i] [-n] 's/PATTERN/REPLACEMENT/[g]' [file...]",
    help_text="Stream editor — substitute, delete, or print lines",
    category="filesystem",
)
def cmd_sed(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return "Usage: sed [-i] [-n] 's/PAT/REPL/[g]' [file...]"

    in_place = False
    silent = False
    expression: str | None = None
    files: list[str] = []

    i = 0
    while i < len(args):
        a = args[i]
        if a == "-i":
            in_place = True
        elif a == "-n":
            silent = True
        elif a in ("-e", "--expression") and i + 1 < len(args):
            expression = args[i + 1]
            i += 1
        elif expression is None and (a.startswith("s/") or a.startswith("s|")
                                      or a.startswith("/") or a[0:1].isdigit()
                                      or a.startswith("y/")):
            expression = a
        else:
            files.append(a)
        i += 1

    if expression is None:
        return "sed: no script command"

    # Parse the expression
    def _apply_expr(text: str, expr: str) -> tuple[str, list[str]]:
        """Apply one sed expression to text. Returns (new_text, output_lines)."""
        lines = text.split("\n")
        out_lines: list[str] = []

        # s/pattern/replacement/[g][i][p]
        sub_m = re.match(r"^s([/|,!])(.+)\1(.*)\1([gip]*)$", expr)
        if sub_m:
            delim, pat, repl, flags_str = sub_m.groups()
            count = 0 if "g" in flags_str else 1
            re_flags = re.IGNORECASE if "i" in flags_str else 0
            try:
                new_lines = [re.sub(pat, repl, ln, count=count, flags=re_flags) for ln in lines]
            except re.error as e:
                return text, [f"sed: -e expression #1: {e}"]
            if not silent or "p" in flags_str:
                out_lines = new_lines
            return "\n".join(new_lines), out_lines

        # /pattern/d  — delete matching lines
        del_m = re.match(r"^/(.+)/d$", expr)
        if del_m:
            pat = del_m.group(1)
            try:
                new_lines = [ln for ln in lines if not re.search(pat, ln)]
            except re.error as e:
                return text, [f"sed: {e}"]
            return "\n".join(new_lines), new_lines if not silent else []

        # /pattern/p  — print matching lines
        print_m = re.match(r"^/(.+)/p$", expr)
        if print_m:
            pat = print_m.group(1)
            try:
                matched = [ln for ln in lines if re.search(pat, ln)]
            except re.error as e:
                return text, [f"sed: {e}"]
            all_out = (lines if not silent else []) + matched
            return text, all_out

        # Np  — print line N (1-indexed)
        line_p = re.match(r"^(\d+)p$", expr)
        if line_p:
            n = int(line_p.group(1)) - 1
            out_lines = [lines[n]] if 0 <= n < len(lines) else []
            return text, (lines if not silent else []) + out_lines

        return text, [f"sed: unknown command: {expr!r}"]

    # Read from stdin if no files
    stdin = ctx.env.get("STDIN", "")
    if not files and stdin:
        _, out = _apply_expr(stdin, expression)
        return "\n".join(out)

    if not files:
        return "sed: no input files"

    results: list[str] = []
    for path_str in files:
        path = _resolve(ctx, path_str)
        try:
            node = ctx.fs._get_node(path)
            if node.is_dir:
                results.append(f"sed: {path_str}: Is a directory")
                continue
            text = node.content or ""
        except FSNotFoundError:
            results.append(f"sed: {path_str}: No such file or directory")
            continue
        except FSError as e:
            results.append(f"sed: {path_str}: {e}")
            continue

        new_text, out = _apply_expr(text, expression)

        if in_place:
            try:
                ctx.fs.write_file(path, new_text)
            except FSError as e:
                results.append(f"sed: {path_str}: {e}")
        else:
            results.extend(out)

    return "\n".join(results)


# ---------------------------------------------------------------------------
# tee
# ---------------------------------------------------------------------------

@register_command(
    name="tee",
    usage="tee [-a] <file>",
    help_text="Read stdin and write to file and stdout simultaneously",
    category="filesystem",
)
def cmd_tee(ctx: CommandContext, args: list[str]) -> str:
    _, positional = _parse_flags(args)
    append = "-a" in args

    stdin = ctx.env.get("STDIN", "")
    if not stdin:
        return ""

    if not positional:
        return stdin  # no file — just pass through

    errors: list[str] = []
    for path_str in positional:
        path = _resolve(ctx, path_str)
        try:
            ctx.fs.write_file(path, stdin, append=append)
        except FSError as e:
            errors.append(f"tee: {path_str}: {e}")

    return (stdin + "\n" + "\n".join(errors)).rstrip("\n") if errors else stdin
