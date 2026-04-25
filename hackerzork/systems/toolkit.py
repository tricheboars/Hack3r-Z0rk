"""Toolkit — package install state, bandwidth, wallet, and poison engine."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from hackerzork.systems.events import EventBus
    from hackerzork.systems.virtual_fs import VirtualFS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASELINE_COMMANDS: frozenset[str] = frozenset(
    [
        # filesystem
        "ls", "cd", "cat", "pwd", "mkdir", "rm", "cp", "mv", "chmod",
        "touch", "find", "grep", "wc", "head", "tail", "stat", "ln",
        "file", "xxd", "strings", "recover",
        # network (always installed — gating these is tedious)
        "ssh", "ping", "traceroute", "tracert", "curl", "nc", "netcat",
        # system
        "whoami", "uname", "ps", "top", "man", "history", "clear",
        "env", "export", "alias", "echo", "date",
        # package managers (always available — gpg requires apt install gpg)
        "apt", "shadow",
        # shell builtins
        "exit", "quit",
    ]
)

_SHADOW_SOURCE_PATTERN = "shadow://"  # triggers shadow_enabled when written to sources.list.d

_KIT_NAMES: frozenset[str] = frozenset(["ghost", "breaker", "oracle"])

_DPKG_STATUS_PATH = "/var/lib/dpkg/status"
_BANDWIDTH_LOG_PATH = "/var/cache/apt/bandwidth.log"
_WALLET_PATH = "/home/user/.burner_wallet"
_SOURCES_LIST_D_PREFIX = "/etc/apt/sources.list.d/"

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Package:
    name: str
    provides: list[str]
    version: str
    repo: str
    kit: str | None
    depends: list[str]
    size_kb: int
    cost_btc: float
    signer: str
    poison_chance: float
    summary: str
    unlocks_story: list[str]


@dataclass
class InstalledPackage:
    pkg: Package
    installed_at: float
    poisoned: bool = False
    poison_vector: str | None = None
    verified: bool = False


@dataclass
class InstallResult:
    success: bool
    message: str
    poisoned: bool = False
    commands_unlocked: list[str] = field(default_factory=list)


@dataclass
class VerifyResult:
    ok: bool
    signer: str
    warning: str | None = None


# ---------------------------------------------------------------------------
# Toolkit
# ---------------------------------------------------------------------------

_POISON_VECTORS: list[str] = ["heat_leak", "ip_leak", "wrong_output", "hidden_exfil"]


class Toolkit:
    def __init__(self, fs: Any, events: Any | None = None) -> None:
        self._fs = fs
        self._events = events
        self.installed: dict[str, InstalledPackage] = {}
        self.catalog: dict[str, Package] = {}
        self.bandwidth_remaining_kb: int = 50_000
        self.wallet_btc: float = 0.015
        self.shadow_enabled: bool = False
        self._committed_kit: str | None = None
        self._kit_discount: bool = False

    # -------------------------------------------------------------------------
    # Catalog loading
    # -------------------------------------------------------------------------

    def load_catalog(self, path: Path) -> None:
        """Load all package YAMLs from data/packages/ (apt/ and shadow/)."""
        for yaml_file in sorted(path.glob("**/*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text())
                pkg = _pkg_from_dict(data)
                self.catalog[pkg.name] = pkg
            except Exception:
                pass
        self._sync_vfs()

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def is_installed(self, command_name: str) -> bool:
        """Return True if the command is in the baseline or provided by an installed package."""
        if command_name in _BASELINE_COMMANDS:
            return True
        for ip in self.installed.values():
            if command_name in ip.pkg.provides:
                return True
        return False

    def available_commands(self) -> set[str]:
        cmds: set[str] = set(_BASELINE_COMMANDS)
        for ip in self.installed.values():
            cmds.update(ip.pkg.provides)
        return cmds

    def get_installed(self, pkg_name: str) -> InstalledPackage | None:
        return self.installed.get(pkg_name)

    # -------------------------------------------------------------------------
    # Install
    # -------------------------------------------------------------------------

    def install(
        self,
        pkg_name: str,
        repo: str = "apt",
        skynet_escalation: float = 0.0,
        verified: bool = False,
    ) -> InstallResult:
        pkg = self.catalog.get(pkg_name)
        if pkg is None:
            return InstallResult(success=False, message=f"E: Unable to locate package {pkg_name}")

        if pkg.repo != repo:
            if repo == "shadow" and pkg.repo == "apt":
                return InstallResult(
                    success=False,
                    message=f"E: Package '{pkg_name}' is not in the shadow repo. Try: apt install {pkg_name}",
                )
            if repo == "apt" and pkg.repo == "shadow":
                return InstallResult(
                    success=False,
                    message=f"E: Package '{pkg_name}' is not in the apt repo. Try: shadow pull {pkg_name}",
                )

        if pkg_name in self.installed:
            return InstallResult(
                success=False,
                message=f"{pkg_name} is already the newest version ({pkg.version}).",
            )

        if repo == "shadow" and not self.shadow_enabled:
            return InstallResult(
                success=False,
                message="E: The shadow repository is not configured.\n"
                "Hint: edit /etc/apt/sources.list.d/ to add a shadow source.",
            )

        # Dependency resolution
        dep_results = self._resolve_deps(pkg, repo, skynet_escalation)
        if not dep_results.success:
            return dep_results

        # Cost checks
        effective_size = pkg.size_kb
        if pkg.cost_btc > 0:
            effective_cost = self._effective_btc_cost(pkg)
            if self.wallet_btc < effective_cost:
                return InstallResult(
                    success=False,
                    message=f"E: Insufficient funds. Need {effective_cost:.4f} BTC, have {self.wallet_btc:.4f} BTC.",
                )
            self.wallet_btc -= effective_cost
            self.wallet_btc = round(self.wallet_btc, 6)
            if self.wallet_btc <= 0:
                self._emit("wallet_depleted", balance=self.wallet_btc)

        if self.bandwidth_remaining_kb < effective_size:
            return InstallResult(
                success=False,
                message=f"E: Insufficient bandwidth. Need {effective_size} kB, have {self.bandwidth_remaining_kb} kB.",
            )
        self.bandwidth_remaining_kb -= effective_size
        if self.bandwidth_remaining_kb <= 0:
            self._emit("bandwidth_depleted", remaining_kb=self.bandwidth_remaining_kb)

        # Poison roll
        poisoned, vector = self._roll_poison(pkg, skynet_escalation, verified)

        ip = InstalledPackage(
            pkg=pkg,
            installed_at=time.time(),
            poisoned=poisoned,
            poison_vector=vector if poisoned else None,
            verified=verified,
        )
        self.installed[pkg_name] = ip

        # Story flags
        for flag in pkg.unlocks_story:
            self._emit("story_flag_set", flag=flag)

        self._emit(
            "package_installed",
            name=pkg_name,
            repo=pkg.repo,
            kit=pkg.kit,
            poisoned=poisoned,
            verified=verified,
        )

        self._sync_vfs()

        lines = dep_results.message.splitlines() if dep_results.message else []
        lines.append(
            f"Setting up {pkg_name} ({pkg.version}) ..."
        )
        lines.append(f"Successfully installed {pkg_name} {pkg.version}.")
        if poisoned:
            self._emit("package_poisoned", name=pkg_name, vector=vector)

        return InstallResult(
            success=True,
            message="\n".join(lines),
            poisoned=poisoned,
            commands_unlocked=list(pkg.provides),
        )

    def _resolve_deps(
        self, pkg: Package, repo: str, skynet_escalation: float
    ) -> InstallResult:
        """Install dependencies first. Returns failure if any dep can't install."""
        lines: list[str] = []
        for dep_name in pkg.depends:
            if dep_name in self.installed:
                continue
            dep = self.catalog.get(dep_name)
            if dep is None:
                return InstallResult(
                    success=False,
                    message=f"E: Dependency '{dep_name}' not found in catalog.",
                )
            # Install dep with its own repo (deps inherit the package's repo-type
            # unless they're mainline, in which case apt is fine)
            dep_repo = dep.repo
            result = self.install(dep_name, repo=dep_repo, skynet_escalation=skynet_escalation)
            if not result.success:
                return InstallResult(
                    success=False,
                    message=f"E: Failed to install dependency '{dep_name}': {result.message}",
                )
            lines.append(result.message)
        return InstallResult(success=True, message="\n".join(lines))

    def _roll_poison(
        self, pkg: Package, skynet_escalation: float, verified: bool
    ) -> tuple[bool, str | None]:
        if pkg.poison_chance <= 0:
            return False, None
        effective = (
            pkg.poison_chance
            * (1 + skynet_escalation * 0.5)
            * (2.0 if not verified else 1.0)
        )
        if random.random() < effective:
            return True, random.choice(_POISON_VECTORS)
        return False, None

    def _effective_btc_cost(self, pkg: Package) -> float:
        if (
            self._kit_discount
            and self._committed_kit is not None
            and pkg.kit == self._committed_kit
        ):
            return round(pkg.cost_btc * 0.75, 6)
        return pkg.cost_btc

    # -------------------------------------------------------------------------
    # Remove
    # -------------------------------------------------------------------------

    def remove(self, pkg_name: str) -> InstallResult:
        if pkg_name not in self.installed:
            return InstallResult(
                success=False, message=f"E: Package '{pkg_name}' is not installed."
            )

        # Check reverse deps
        dependents = [
            name
            for name, ip in self.installed.items()
            if pkg_name in ip.pkg.depends and name != pkg_name
        ]
        if dependents:
            return InstallResult(
                success=False,
                message=(
                    f"E: Package '{pkg_name}' cannot be removed — "
                    f"other packages depend on it: {', '.join(dependents)}\n"
                    f"Use 'apt remove {' '.join(dependents)} {pkg_name}' to remove all."
                ),
            )

        del self.installed[pkg_name]
        self._emit("package_removed", name=pkg_name)
        self._sync_vfs()
        return InstallResult(
            success=True,
            message=f"Removing {pkg_name} ...\nSuccessfully removed {pkg_name}.",
        )

    # -------------------------------------------------------------------------
    # Verify
    # -------------------------------------------------------------------------

    def verify(self, pkg_name: str) -> VerifyResult:
        if not self.is_installed("gpg"):
            return VerifyResult(ok=False, signer="", warning="gpg is not installed. Run: apt install gpg")

        ip = self.installed.get(pkg_name)
        if ip is None:
            return VerifyResult(ok=False, signer="", warning=f"Package '{pkg_name}' is not installed.")

        pkg = ip.pkg
        if pkg.signer == "UNSIGNED":
            return VerifyResult(
                ok=False,
                signer="UNSIGNED",
                warning=f"WARNING: Package '{pkg_name}' has no signature.",
            )

        if ip.poisoned:
            return VerifyResult(
                ok=False,
                signer=pkg.signer,
                warning=f"ALERT: Signature mismatch — package '{pkg_name}' may be tampered.",
            )

        ip.verified = True
        self._emit("package_verified", name=pkg_name, ok=True, signer=pkg.signer)
        return VerifyResult(ok=True, signer=pkg.signer)

    # -------------------------------------------------------------------------
    # Poison (called by meta engine)
    # -------------------------------------------------------------------------

    def poison(self, pkg_name: str, vector: str) -> None:
        ip = self.installed.get(pkg_name)
        if ip is None:
            return
        ip.poisoned = True
        ip.poison_vector = vector
        self._emit("package_poisoned", name=pkg_name, vector=vector)

    # -------------------------------------------------------------------------
    # Shadow commit (kit archetype)
    # -------------------------------------------------------------------------

    def commit_kit(self, kit: str) -> InstallResult:
        if kit not in _KIT_NAMES:
            return InstallResult(
                success=False,
                message=f"E: Unknown kit '{kit}'. Valid kits: ghost, breaker, oracle.",
            )
        if self._committed_kit is not None:
            return InstallResult(
                success=False,
                message=f"Already committed to kit '{self._committed_kit}'. No going back.",
            )
        self._committed_kit = kit
        self._kit_discount = True
        self._emit("kit_committed", kit=kit)
        return InstallResult(
            success=True,
            message=(
                f"Committed to {kit.upper()}KIT.\n"
                f"25% discount applied to all {kit} packages.\n"
                f"[identity crystallised]"
            ),
        )

    # -------------------------------------------------------------------------
    # Shadow unlock watcher
    # -------------------------------------------------------------------------

    def check_shadow_source(self, path: str, content: str) -> None:
        """Call this whenever the VFS writes to /etc/apt/sources.list.d/."""
        if not path.startswith(_SOURCES_LIST_D_PREFIX):
            return
        if _SHADOW_SOURCE_PATTERN in content and not self.shadow_enabled:
            self.shadow_enabled = True
            url = _extract_shadow_url(content)
            self._emit("shadow_unlocked", source_url=url)

    # -------------------------------------------------------------------------
    # Bandwidth / wallet helpers
    # -------------------------------------------------------------------------

    def consume_bandwidth(self, kb: int, reason: str = "") -> bool:
        if self.bandwidth_remaining_kb < kb:
            return False
        self.bandwidth_remaining_kb -= kb
        if self.bandwidth_remaining_kb <= 0:
            self._emit("bandwidth_depleted", remaining_kb=self.bandwidth_remaining_kb)
        self._sync_bandwidth_log()
        return True

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "bandwidth_remaining_kb": self.bandwidth_remaining_kb,
            "wallet_btc": self.wallet_btc,
            "shadow_enabled": self.shadow_enabled,
            "committed_kit": self._committed_kit,
            "kit_discount": self._kit_discount,
            "installed": {
                name: {
                    "pkg_name": ip.pkg.name,
                    "installed_at": ip.installed_at,
                    "poisoned": ip.poisoned,
                    "poison_vector": ip.poison_vector,
                    "verified": ip.verified,
                }
                for name, ip in self.installed.items()
            },
        }

    def load_state(self, state: dict) -> None:
        self.bandwidth_remaining_kb = int(state.get("bandwidth_remaining_kb", 50_000))
        self.wallet_btc = float(state.get("wallet_btc", 0.015))
        self.shadow_enabled = bool(state.get("shadow_enabled", False))
        self._committed_kit = state.get("committed_kit")
        self._kit_discount = bool(state.get("kit_discount", False))
        for name, entry in state.get("installed", {}).items():
            pkg = self.catalog.get(entry["pkg_name"])
            if pkg is None:
                continue
            self.installed[name] = InstalledPackage(
                pkg=pkg,
                installed_at=float(entry.get("installed_at", 0.0)),
                poisoned=bool(entry.get("poisoned", False)),
                poison_vector=entry.get("poison_vector"),
                verified=bool(entry.get("verified", False)),
            )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _emit(self, event_name: str, **data: object) -> None:
        if self._events is not None:
            self._events.emit(event_name, **data)

    def _sync_vfs(self) -> None:
        """Mirror installed state into VFS diegetic files."""
        if self._fs is None:
            return
        try:
            self._sync_dpkg_status()
            self._sync_bandwidth_log()
            self._sync_wallet()
        except Exception:
            pass

    def _sync_dpkg_status(self) -> None:
        lines: list[str] = []
        for ip in self.installed.values():
            pkg = ip.pkg
            lines.append(f"Package: {pkg.name}")
            lines.append(f"Status: install ok installed")
            lines.append(f"Version: {pkg.version}")
            lines.append(f"Maintainer: {pkg.signer}")
            lines.append(f"Description: {pkg.summary}")
            lines.append("")
        content = "\n".join(lines)
        self._fs_write(_DPKG_STATUS_PATH, content)

    def _sync_bandwidth_log(self) -> None:
        content = (
            f"# /var/cache/apt/bandwidth.log\n"
            f"remaining_kb={self.bandwidth_remaining_kb}\n"
            f"used_kb={50_000 - self.bandwidth_remaining_kb}\n"
        )
        self._fs_write(_BANDWIDTH_LOG_PATH, content)

    def _sync_wallet(self) -> None:
        content = (
            f"# burner wallet — handle with care\n"
            f"balance={self.wallet_btc:.6f} BTC\n"
        )
        self._fs_write(_WALLET_PATH, content)

    def _fs_write(self, path: str, content: str) -> None:
        try:
            parent = str(Path(path).parent)
            try:
                self._fs.mkdir(parent, parents=True)
            except Exception:
                pass
            self._fs.write_file(path, content)
        except Exception:
            pass

    def _sync_usr_bin(self, pkg: Package) -> None:
        for cmd in pkg.provides:
            fake_bin_path = f"/usr/bin/{cmd}"
            content = f"#!/bin/sh\n# {pkg.summary}\necho '{cmd}: not directly executable in HackerOS'\n"
            self._fs_write(fake_bin_path, content)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pkg_from_dict(data: dict) -> Package:
    return Package(
        name=data["name"],
        provides=list(data.get("provides", [])),
        version=str(data.get("version", "0.0")),
        repo=data.get("repo", "apt"),
        kit=data.get("kit"),
        depends=list(data.get("depends", [])),
        size_kb=int(data.get("size_kb", 0)),
        cost_btc=float(data.get("cost_btc", 0.0)),
        signer=str(data.get("signer", "UNSIGNED")),
        poison_chance=float(data.get("poison_chance", 0.0)),
        summary=str(data.get("summary", "")),
        unlocks_story=list(data.get("unlocks_story", [])),
    )


def _extract_shadow_url(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if _SHADOW_SOURCE_PATTERN in line:
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
            return line
    return ""
