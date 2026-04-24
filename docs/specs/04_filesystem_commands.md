# Spec: Filesystem Commands

## Module: `hackerzork/commands/filesystem.py`

### Purpose
Implement every Unix filesystem command the player uses. These are the primary interface between the player and `VirtualFS`. Commands register via `@register_command` and receive a `CommandContext` with `ctx.fs` pointing at the live `VirtualFS`.

### Category
All commands in this file use `category="filesystem"`.

---

## Commands

### `pwd`
Print working directory.
- Reads `ctx.env["CWD"]`
- Returns the path string

### `cd [path]`
Change working directory.
- No args → cd to `/home/user`
- `cd -` → go to previous dir (`ctx.env["OLDPWD"]`)
- Resolves relative paths against current `CWD`
- Validates target exists and is a directory
- Updates `ctx.env["CWD"]` and `ctx.env["OLDPWD"]`
- Error: `bash: cd: <path>: No such file or directory`
- Error: `bash: cd: <path>: Not a directory`

### `ls [-la] [-R] [path]`
List directory contents.

Flags:
- `-l` — long format: permissions, owner, group, size, date, name
- `-a` — show hidden files (names starting with `.`)
- `-R` — recursive listing
- Flags can be combined: `-la`, `-al`, `-lR`, etc.

Long format per entry:
```
<perms>  <owner>  <group>  <size>  <date>  <name>
```

Special rendering:
- Symlinks: `lrwxrwxrwx ... name -> target` (broken symlinks still show the target)
- Directories: append `/` to name in short format
- No args → list current `CWD`

### `cat [-n] [file...]`
Concatenate and print file contents.

- `-n` — number output lines
- Multiple files → concatenate with no separator
- Encrypted files (`FSEntry.encrypted == True`): print `[ENCRYPTED — binary content]` followed by `VirtualFS.render_hex(content)`
- Binary files (`FSEntry.binary == True`): print `bash: cat: <file>: Binary file (use xxd to inspect)`
- Directories → `bash: cat: <path>: Is a directory`

### `head [-n N] [file]`
Print first N lines (default 10).

- `-n N` or `-N` for short form
- Encrypted/binary files get same treatment as `cat`

### `tail [-n N] [file]`
Print last N lines (default 10).

- `-n N` or `-N` for short form

### `wc [-l] [-w] [-c] [file]`
Word/line/byte count.

- `-l` lines only, `-w` words only, `-c` bytes only
- No flags → print `<lines> <words> <bytes> <filename>`
- Encrypted/binary files are still countable (bytes = len content)

### `mkdir [-p] <dir>`
Create directory.

- `-p` — create parent directories as needed, no error if exists
- Without `-p`: error if parent missing or dir exists

### `touch <file...>`
Create empty files or update timestamps.

- File exists → update `modified` timestamp to now
- File doesn't exist → create empty file, permissions `644`, owned by player

### `rm [-r] [-f] [--shred] <path...>`
Remove files/directories.

- Default → sends to trash (recoverable)
- `-r` / `--recursive` — allow directories
- `-f` / `--force` — suppress errors for missing files
- `--shred` → permanent delete (bypasses trash), prints `shredding...` message

### `cp [-r] <src> <dst>`
Copy file or directory.

- `-r` — recursive (required for directories)
- `dst` is an existing directory → copy into it
- `dst` doesn't exist → create as copy

### `mv <src> <dst>`
Move/rename file or directory.

- `dst` is an existing directory → move into it
- `dst` doesn't exist → rename

### `chmod <mode> <path>`
Change file permissions.

- Accepts octal (`755`, `644`) or symbolic (`u+x`, `go-w`, `a+r`)
- Symbolic: `[ugoa][+-=][rwx]` with multiple groups comma-separated

### `ln -s <target> <link>`
Create symbolic link.

- Only `-s` (symbolic) supported; hard links not implemented
- Error if `-s` not specified: `ln: hard links not supported — use ln -s`

### `stat <path>`
Display file status.

```
  File: <name>
  Size: <bytes>
  Type: <regular file|directory|symbolic link>
Perms: <mode string>  (<octal>)
Owner: <owner>  Group: <group>
 Mtime: <ISO timestamp>
```

For symlinks: also show `  Link: <target>` and `[BROKEN]` if target doesn't exist.

### `file <path>`
Determine file type.

Returns one of:
- `<path>: directory`
- `<path>: ASCII text`
- `<path>: symbolic link to <target>`
- `<path>: encrypted data`
- `<path>: ELF 64-bit executable` (when `binary=True`)
- `<path>: empty`

### `xxd <path>`
Hex dump of any file (including encrypted/binary).

- Always shows raw hex — ignores encrypted/binary flags
- Uses `VirtualFS.render_hex(content)` for output

### `strings [-n N] <path>`
Extract printable strings from a file.

- `-n N` — minimum string length (default 4)
- Works on encrypted and binary files (extracts readable substrings)
- One string per line

### `grep [-r] [-i] [-n] [-v] [-l] <pattern> [path...]`
Search for pattern in file(s).

Flags:
- `-r` / `--recursive` — recurse into directories
- `-i` — case-insensitive
- `-n` — show line numbers
- `-v` — invert match (print non-matching lines)
- `-l` — print only filenames that match

Output format (with path): `<file>:<line_no>:<line>` (when `-n`)
Output format (without `-n`): `<file>:<line>`
When searching a single file (no path prefix), omit filename.

- Encrypted/binary files → skip with message `grep: <file>: binary file matches` (when match found)
- Invalid regex → fall back to literal string search

### `find [path] [-name <glob>] [-type <f|d>] [-newer <file>]`
Search for files.

- No path → search from CWD
- `-name` — glob pattern (`*.py`, `*.enc`)
- `-type f` — files only, `-type d` — dirs only
- `-newer <file>` — files modified more recently than `<file>`
- Output: one path per line

### `recover [path]`
Restore a file from trash.

- No args → list trash contents with original paths
- With path → restore to original location
- Error if original parent directory no longer exists
- Prints: `recovered: <path>`

---

## Flag Parsing Helper

The module provides a private `_parse_flags(args, valid_short, valid_long)` helper that splits a raw arg list into `(flags: set[str], positional: list[str])`. This avoids duplicating flag logic across every command.

---

## Error String Conventions

Match real bash output exactly where possible:

| Situation | Output |
|-----------|--------|
| File not found | `bash: <cmd>: <path>: No such file or directory` |
| Not a directory | `bash: <cmd>: <path>: Not a directory` |
| Is a directory | `bash: <cmd>: <path>: Is a directory` |
| Permission denied | `bash: <cmd>: <path>: Permission denied` |
| Missing operand | `bash: <cmd>: missing operand` |
| Command not found | (handled by shell, not command) |

---

## Event Emissions

| Command | Event | Data |
|---------|-------|------|
| `cat` (encrypted file) | `encrypted_file_accessed` | `path`, `filename` |
| `rm --shred` | `file_shredded` | `path` |
| `find` | `filesystem_searched` | `pattern`, `results_count` |
| `grep` | `content_searched` | `pattern`, `path` |

---

## Tests: `tests/test_commands/test_filesystem.py`

Test structure mirrors commands: one class per command.
- Use a fresh `VirtualFS` seeded with known content for each test
- Build `CommandContext` with `fs=<fresh_fs>` and `env={"CWD": "/home/user", "HOME": "/home/user"}`
- Assert return value strings match expected output
- Test flag combinations
- Test error paths (missing file, wrong type, permission denied)
- Test encrypted file rendering in `cat` and `xxd`
- Test symlink display in `ls`
- Test trash flow: `rm` → `recover`
