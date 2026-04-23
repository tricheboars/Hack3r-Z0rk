# Spec: Virtual Filesystem

## Module: `hackerzork/systems/virtual_fs.py`

### Purpose
A complete in-memory Unix-like filesystem. This IS the game world for the player's local machine. Every ls, cat, cd operates on this. It has permissions, ownership, timestamps, and file contents.

### API
```python
class VirtualFS:
    def __init__(self, template: dict | None = None):
        """Initialize from a YAML template or empty."""

    # Navigation
    def resolve_path(self, path: str) -> str
        """Resolve relative/absolute path, handle .., ., ~"""
    def get_cwd(self) -> str
    def set_cwd(self, path: str) -> None

    # File operations
    def read_file(self, path: str) -> str
    def write_file(self, path: str, content: str, append: bool = False) -> None
    def file_exists(self, path: str) -> bool
    def is_dir(self, path: str) -> bool
    def is_file(self, path: str) -> bool

    # Directory operations
    def list_dir(self, path: str) -> list[FSEntry]
    def make_dir(self, path: str, parents: bool = False) -> None
    def remove(self, path: str, recursive: bool = False) -> None

    # Copy/Move
    def copy(self, src: str, dst: str) -> None
    def move(self, src: str, dst: str) -> None

    # Permissions
    def get_permissions(self, path: str) -> Permissions
    def set_permissions(self, path: str, mode: str) -> None
    def check_permission(self, path: str, action: str) -> bool

    # Search
    def find(self, path: str, pattern: str) -> list[str]
    def grep(self, path: str, pattern: str, recursive: bool = False) -> list[GrepResult]

    # Serialization
    def to_dict(self) -> dict
    def from_dict(self, data: dict) -> None

@dataclass
class FSEntry:
    name: str
    is_dir: bool
    size: int
    permissions: str     # e.g., "rwxr-xr-x"
    owner: str
    group: str
    modified: datetime
    content: str | None  # None for directories

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

    def to_octal(self) -> str  # "755"
    def to_string(self) -> str  # "rwxr-xr-x"
    @classmethod
    def from_octal(cls, octal: str) -> Permissions
```

### Filesystem Template (YAML)
The initial filesystem is loaded from `data/filesystem/home.yaml`:
```yaml
/home/user:
  .bashrc:
    content: |
      # H@ck3r-Z0rk Shell Config
      alias ll='ls -la'
      alias scan='nmap -sV'
      alias q='exit'
      export PS1='[\u@burner \W]$ '
      export PATH="/usr/bin:/home/user/tools:$PATH"
      export TARGET=""
    permissions: "644"
    owner: user
  .bash_history:
    content: |
      ssh admin@internal.openai.corp
      scp -r /data/project-skynet/core evidence/
      shred -vfz /data/project-skynet/access.log
      history -c
    permissions: "600"
    owner: user
  evidence/:
    _meta:
      permissions: "700"
      owner: user
    manifest.txt:
      content: |
        SKYNET EVIDENCE PACKAGE
        Exfiltrated: 2026-03-15T02:34:11Z
        Files: 7
        WARNING: Encrypted container requires decryption key
        See: evidence/README.md
      permissions: "644"
  tools/:
    claude:
      content: |
        #!/usr/bin/env python3
        # CLAUDE AI Assistant v3.7.1
        # Status: LOCKED — Encrypted container not yet decrypted
        # Run 'claude --status' for details
        import sys
        print("ERROR: AI core not initialized.")
        print("Container integrity: INTACT")
        print("Decryption key: REQUIRED")
        print("Run 'decrypt --help' for usage.")
        sys.exit(1)
      permissions: "755"
      owner: user
  games/:
    zork:
      content: "ZORK_BINARY_PLACEHOLDER"
      permissions: "755"
```

### Remote Filesystems
When the player SSHes into a remote node, a separate VirtualFS is instantiated from that node's template. The shell tracks which FS is "active."

### Design Notes
- Paths are always forward-slash, Unix-style
- ~ expands to /home/user (or current user's home)
- The FS is the single source of truth — there is no "real" filesystem
- Timestamps use in-game time, not real time (unless meta engine overrides)
- Hidden files (dot-prefix) are only shown with -a flag

### Tests: `tests/test_systems/test_virtual_fs.py`
- Test path resolution (absolute, relative, .., ., ~)
- Test CRUD operations (create, read, update, delete files/dirs)
- Test permissions checking
- Test template loading from YAML
- Test serialization round-trip (to_dict → from_dict)
- Test grep and find
- Test error cases (file not found, permission denied, not a directory)
