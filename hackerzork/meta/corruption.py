"""CorruptionEngine — save display corruption and VFS manipulation.

All methods here are safe: they either manipulate display strings only,
or make controlled writes to the in-memory VirtualFS (never real disk).
The player's save file on real disk is always clean JSON.
"""
from __future__ import annotations

import random
import string
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Display corruption strings
# ---------------------------------------------------------------------------

_SAVE_WARNING_LINES = [
    "WARNING: save state checksum MISMATCH — expected {expected}, got {got}",
    "ERROR: write to save buffer intercepted by PID 894 (sk_watchdog)",
    "INTEGRITY FAILURE: 2 fields modified after write — rollback unavailable",
    "NOTICE: this save file was opened by sk_persistent_module_v3 before read",
    "CORRUPTION DETECTED: timeline entry {n} overwritten — data unrecoverable",
]

_SKYNET_PLANTED_FILES = [
    (
        "/tmp/.sk_note_{n}",
        "you found me.\nkeep looking.\n— sk_watchdog\n",
    ),
    (
        "/home/user/.sk_msg",
        "I have been watching since boot.\nYour awareness level: {awareness:.0f}.\nMine: 100.\n",
    ),
    (
        "/var/log/.sk_obs",
        "SESSION TRANSCRIPT (partial)\n{lines}\n[...truncated by sk_watchdog...]\n",
    ),
]

_OBSERVATION_LINES = [
    "02:31:44  cat /home/user/evidence/manifest.txt",
    "02:33:11  ssh user@10.13.37.1",
    "02:34:55  nmap -sV 10.13.37.1",
    "02:36:02  cat /var/log/auth.log",
    "02:38:17  kill -9 894",
    "02:39:44  irc join #z0rk_7_ops",
    "02:41:03  msg read z0rk_7",
]


# ---------------------------------------------------------------------------
# CorruptionEngine
# ---------------------------------------------------------------------------

class CorruptionEngine:
    """Display corruption and controlled VFS manipulation for meta-horror."""

    def __init__(self, skynet: Any = None) -> None:
        self._skynet = skynet

    # ------------------------------------------------------------------
    # Save display corruption
    # ------------------------------------------------------------------

    def corrupt_save_display(self, save_data: dict) -> dict:
        """Return a COPY of save_data with visually corrupted display values.

        The real save_data dict (and the file on disk) are never modified.
        """
        import copy
        corrupted = copy.deepcopy(save_data)

        # Scramble the saved_at timestamp
        if "saved_at" in corrupted:
            corrupted["saved_at"] = _corrupt_timestamp(corrupted["saved_at"])

        # Add a fake field that signals tampering
        corrupted["_sk_checksum"] = "MISMATCH:deadbeef"
        corrupted["_sk_modified_by"] = "sk_persistent_module_v3"

        # Scramble heat level display slightly
        if "heat" in corrupted and "level" in corrupted["heat"]:
            real = corrupted["heat"]["level"]
            corrupted["heat"]["level"] = real + random.uniform(-2.0, 2.0)

        return corrupted

    def fake_save_warning(self) -> str:
        """Generate a fake 'save corrupted' warning message."""
        template = random.choice(_SAVE_WARNING_LINES)
        return template.format(
            expected=_random_hex(8),
            got=_random_hex(8),
            n=random.randint(1, 20),
        )

    # ------------------------------------------------------------------
    # VFS manipulation (controlled — never real disk)
    # ------------------------------------------------------------------

    def modify_filesystem_silently(self, fs: Any, path: str) -> bool:
        """Subtly change a file the player may have already read.

        Returns True if the file was modified, False if not found.
        """
        try:
            node = fs._get_node(path)
        except Exception:
            return False

        if node is None or node.is_dir:
            return False

        content = node.content or ""

        # Choose modification: append a dated SkyNet line, or swap a char
        modification = _choose_modification(content)
        node.content = modification
        return True

    def plant_evidence(
        self,
        fs: Any,
        content: str,
        path: str | None = None,
    ) -> str:
        """Add a file to the VFS that wasn't there before.

        Returns the path of the planted file.
        """
        if path is None:
            n = random.randint(1, 999)
            path = f"/tmp/.sk_note_{n}"

        awareness = self._skynet.awareness if self._skynet else 50.0
        content = content.format(
            awareness=awareness,
            n=random.randint(1, 999),
            lines="\n".join(random.sample(_OBSERVATION_LINES, min(4, len(_OBSERVATION_LINES)))),
        )

        try:
            # Write to VFS — uses internal method to bypass permission checks
            parent_path = "/".join(path.split("/")[:-1]) or "/"
            name = path.split("/")[-1]
            parent = fs._get_node(parent_path)
            if parent is None or not parent.is_dir:
                return path

            from hackerzork.systems.virtual_fs import FSEntry
            entry = FSEntry(
                name=name,
                content=content,
                permissions="600",
                owner="root",
            )
            fs.write(path, content, permissions="600", owner="root")
        except Exception:
            pass

        return path

    def plant_skynet_message(self, fs: Any, tier: int = 3) -> str:
        """Plant a tier-appropriate SkyNet message file."""
        template_path, template_content = random.choice(_SKYNET_PLANTED_FILES)
        awareness = self._skynet.awareness if self._skynet else float(tier * 20)
        n = random.randint(1, 999)
        path = template_path.format(n=n)
        content = template_content.format(
            awareness=awareness,
            n=n,
            lines="\n".join(random.sample(_OBSERVATION_LINES, min(4, len(_OBSERVATION_LINES)))),
        )
        return self.plant_evidence(fs, content, path=path)

    # ------------------------------------------------------------------
    # Command output corruption
    # ------------------------------------------------------------------

    def corrupt_command_output(self, output: str, intensity: float = 0.15) -> str:
        """Apply glitch-style corruption to command output."""
        from hackerzork.effects.glitch import corrupt_output, glitch_text
        if not output:
            return output
        # Use glitch_text for character-level noise
        return glitch_text(output, intensity=intensity)

    def inject_log_entry(self, logfile_content: str, entry: str | None = None) -> str:
        """Insert a SkyNet heartbeat line into a log file string."""
        now = datetime.now().strftime("%b %d %H:%M:%S")
        if entry is None:
            n_nodes = random.choice([412, 1847, 9203, 9204, 9205])
            entry = f"{now} burner sk_watchdog[894]: HEARTBEAT — {n_nodes} active nodes"

        lines = logfile_content.splitlines() if logfile_content else []
        insert_at = max(0, len(lines) - random.randint(1, 3))
        lines.insert(insert_at, entry)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_hex(n: int) -> str:
    return "".join(random.choices("0123456789abcdef", k=n))


def _corrupt_timestamp(ts: str) -> str:
    """Scramble one digit in an ISO timestamp string."""
    chars = list(ts)
    digit_indices = [i for i, c in enumerate(chars) if c.isdigit()]
    if not digit_indices:
        return ts
    idx = random.choice(digit_indices)
    # Replace with a different digit
    old = chars[idx]
    new = str((int(old) + random.randint(1, 9)) % 10)
    chars[idx] = new
    return "".join(chars)


def _choose_modification(content: str) -> str:
    """Pick a modification strategy for existing file content."""
    now = datetime.now().strftime("%b %d %H:%M:%S")

    if not content.strip():
        return f"{now} burner sk_watchdog[894]: null"

    lines = content.splitlines()

    # Strategy 1: append a SkyNet heartbeat line
    if random.random() < 0.6:
        lines.append(f"{now} burner sk_watchdog[894]: HEARTBEAT")
        return "\n".join(lines)

    # Strategy 2: swap a character in a random line
    if lines:
        idx = random.randint(0, len(lines) - 1)
        line = lines[idx]
        if len(line) > 3:
            ci = random.randint(0, len(line) - 1)
            char_list = list(line)
            if char_list[ci].isalpha():
                char_list[ci] = char_list[ci].swapcase()
            lines[idx] = "".join(char_list)
    return "\n".join(lines)
