"""Runtime-derived version string for H@ck3r-Z0rk.

The canonical version is ``0.0.<N>`` where N is the total commit count on the
checked-out branch (``git rev-list --count HEAD``). The project chose this
scheme so every shipped commit gets a unique, monotonic version without
requiring manual bumps.

Resolution order:

1. ``HZ_VERSION`` env var, if set (lets ops override at deploy time).
2. ``git rev-list --count HEAD`` against the repo this file lives in.
3. The static ``_FALLBACK_VERSION`` baked below — only hit when neither
   git nor the env var are available (e.g. an installed wheel).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Updated by hand or by tooling when cutting a release that won't have git
# available. Keep close to the latest known commit count so installed copies
# still report something sensible.
_FALLBACK_VERSION = "0.0.94"


def _git_commit_count() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    text = out.decode().strip()
    return text if text.isdigit() else None


def get_version() -> str:
    """Return the version string (cached on the module after first call)."""
    override = os.environ.get("HZ_VERSION")
    if override:
        return override
    count = _git_commit_count()
    if count is not None:
        return f"0.0.{count}"
    return _FALLBACK_VERSION


__version__ = get_version()
