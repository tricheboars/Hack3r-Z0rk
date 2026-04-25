"""Tests for hackerzork/commands/packaging.py."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import hackerzork.commands.packaging  # ensure commands register
from hackerzork.engine.command_registry import CommandContext, DEFAULT_REGISTRY
from hackerzork.systems.toolkit import Package, InstalledPackage, Toolkit
import time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pkg(
    name="testpkg",
    provides=None,
    version="1.0",
    repo="apt",
    kit=None,
    depends=None,
    size_kb=100,
    cost_btc=0.0,
    signer="test@example.com",
    poison_chance=0.0,
    summary="A test package",
    unlocks_story=None,
) -> Package:
    return Package(
        name=name,
        provides=provides or [name],
        version=version,
        repo=repo,
        kit=kit,
        depends=depends or [],
        size_kb=size_kb,
        cost_btc=cost_btc,
        signer=signer,
        poison_chance=poison_chance,
        summary=summary,
        unlocks_story=unlocks_story or [],
    )


def _make_ctx(shadow_enabled: bool = False, wallet: float = 0.015) -> CommandContext:
    mock_fs = MagicMock()
    # make write_file and mkdir silent
    mock_fs.write_file = MagicMock()
    mock_fs.mkdir = MagicMock()
    mock_fs.read_file = MagicMock(return_value="")

    tk = Toolkit(fs=mock_fs)
    tk.shadow_enabled = shadow_enabled
    tk.wallet_btc = wallet

    # Add a few packages to the catalog
    pkgs = [
        _make_pkg("nmap", depends=["libpcap"]),
        _make_pkg("libpcap", provides=[], size_kb=50),
        _make_pkg("gpg", provides=["gpg"]),
        _make_pkg("net-tools", provides=["ifconfig", "netstat", "arp"]),
        _make_pkg("shade", repo="shadow", kit="ghost", cost_btc=0.003, signer="UNSIGNED"),
        _make_pkg("masq", repo="shadow", kit="ghost", cost_btc=0.002, signer="UNSIGNED"),
        _make_pkg("ramroot", repo="shadow", kit="breaker", cost_btc=0.004, signer="UNSIGNED"),
        _make_pkg(
            "cipher-unwind", repo="shadow", kit="oracle", cost_btc=0.003, signer="UNSIGNED"
        ),
    ]
    for pkg in pkgs:
        tk.catalog[pkg.name] = pkg

    ctx = CommandContext(
        fs=mock_fs,
        events=MagicMock(),
        toolkit=tk,
    )
    return ctx


def _run(cmd_name: str, ctx: CommandContext, args: list[str]) -> str:
    handler = DEFAULT_REGISTRY.get(cmd_name)
    assert handler is not None, f"Command '{cmd_name}' not registered"
    return handler(ctx, args)


# ---------------------------------------------------------------------------
# apt — basic
# ---------------------------------------------------------------------------


class TestAptBasic:
    def test_no_args_shows_usage(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, [])
        assert "apt" in out
        assert "update" in out

    def test_unknown_subcommand(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["frob"])
        assert "Invalid operation" in out or "frob" in out


class TestAptUpdate:
    def test_update_consumes_bandwidth(self):
        ctx = _make_ctx()
        before = ctx.toolkit.bandwidth_remaining_kb
        _run("apt", ctx, ["update"])
        assert ctx.toolkit.bandwidth_remaining_kb == before - 200

    def test_update_output_looks_real(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["update"])
        assert "InRelease" in out
        assert "Done" in out

    def test_update_fails_on_no_bandwidth(self):
        ctx = _make_ctx()
        ctx.toolkit.bandwidth_remaining_kb = 10
        out = _run("apt", ctx, ["update"])
        assert "bandwidth" in out.lower() or "exhausted" in out.lower()


class TestAptSearch:
    def test_search_finds_package(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["search", "nmap"])
        assert "nmap" in out

    def test_search_no_results(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["search", "zzznothingxxx"])
        assert "No results" in out or "zzznothingxxx" in out

    def test_search_no_query(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["search"])
        assert "Usage" in out or "search" in out

    def test_search_shadow_excluded(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["search", "shade"])
        # shade is a shadow package — it should not appear as a listed result
        # (the no-results message may echo the query, but not list the package with version)
        assert "shade/" not in out


class TestAptShow:
    def test_show_existing_package(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["show", "nmap"])
        assert "Package: nmap" in out
        assert "Version" in out
        assert "Description" in out

    def test_show_missing_package(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["show", "zzzghost"])
        assert "Unable to locate" in out or "N:" in out

    def test_show_installed_marker(self):
        ctx = _make_ctx()
        # install libpcap first (dep), then nmap
        ctx.toolkit.install("libpcap", repo="apt")
        ctx.toolkit.install("nmap", repo="apt")
        out = _run("apt", ctx, ["show", "nmap"])
        assert "installed" in out.lower()


class TestAptInstall:
    def test_install_simple(self):
        ctx = _make_ctx()
        # libpcap has no deps
        out = _run("apt", ctx, ["install", "libpcap"])
        assert "libpcap" in ctx.toolkit.installed
        assert "Successfully installed" in out or "libpcap" in out

    def test_install_resolves_deps(self):
        ctx = _make_ctx()
        _run("apt", ctx, ["install", "nmap"])
        assert "libpcap" in ctx.toolkit.installed
        assert "nmap" in ctx.toolkit.installed

    def test_install_missing_package(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["install", "ghost_tool"])
        assert "Unable to locate" in out or "E:" in out

    def test_install_multiple(self):
        ctx = _make_ctx()
        _run("apt", ctx, ["install", "libpcap", "gpg"])
        assert "libpcap" in ctx.toolkit.installed
        assert "gpg" in ctx.toolkit.installed

    def test_install_no_args(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["install"])
        assert "Usage" in out


class TestAptRemove:
    def test_remove_installed(self):
        ctx = _make_ctx()
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("apt", ctx, ["remove", "libpcap"])
        assert "libpcap" not in ctx.toolkit.installed
        assert "removed" in out.lower() or "Removing" in out

    def test_remove_with_dependent_fails(self):
        ctx = _make_ctx()
        _run("apt", ctx, ["install", "nmap"])
        out = _run("apt", ctx, ["remove", "libpcap"])
        assert "nmap" in out  # mentions the dependent

    def test_remove_not_installed(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["remove", "ghost_tool"])
        assert "not installed" in out.lower() or "E:" in out

    def test_remove_no_args(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["remove"])
        assert "Usage" in out


class TestAptList:
    def test_list_installed_empty(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["list", "--installed"])
        assert "Done" in out

    def test_list_installed_shows_installed(self):
        ctx = _make_ctx()
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("apt", ctx, ["list", "--installed"])
        assert "libpcap" in out

    def test_list_all(self):
        ctx = _make_ctx()
        out = _run("apt", ctx, ["list"])
        # Should include at least the apt packages in catalog
        assert "nmap" in out or "libpcap" in out


class TestAptVerify:
    def test_verify_without_gpg(self):
        ctx = _make_ctx()
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("apt", ctx, ["verify", "libpcap"])
        assert "gpg" in out.lower()

    def test_verify_with_gpg_clean(self):
        ctx = _make_ctx()
        ctx.toolkit.install("gpg", repo="apt")
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("apt", ctx, ["verify", "libpcap"])
        assert "Good signature" in out or "valid" in out.lower()

    def test_verify_no_args(self):
        ctx = _make_ctx()
        ctx.toolkit.install("gpg", repo="apt")
        out = _run("apt", ctx, ["verify"])
        assert "Usage" in out


# ---------------------------------------------------------------------------
# shadow
# ---------------------------------------------------------------------------


class TestShadowBasic:
    def test_no_args_shows_usage_or_status(self):
        ctx = _make_ctx()
        out = _run("shadow", ctx, [])
        assert "shadow" in out.lower()

    def test_unknown_subcommand(self):
        ctx = _make_ctx()
        out = _run("shadow", ctx, ["frob"])
        assert "Unknown" in out or "frob" in out


class TestShadowPull:
    def test_pull_blocked_when_not_enabled(self):
        ctx = _make_ctx(shadow_enabled=False)
        out = _run("shadow", ctx, ["pull", "shade"])
        assert "not configured" in out.lower() or "shadow" in out.lower()

    def test_pull_succeeds_when_enabled(self):
        ctx = _make_ctx(shadow_enabled=True)
        out = _run("shadow", ctx, ["pull", "shade"])
        assert "shade" in ctx.toolkit.installed or "shade" in out

    def test_pull_deducts_btc(self):
        ctx = _make_ctx(shadow_enabled=True, wallet=0.015)
        before = ctx.toolkit.wallet_btc
        _run("shadow", ctx, ["pull", "shade"])
        assert ctx.toolkit.wallet_btc < before

    def test_pull_missing_package(self):
        ctx = _make_ctx(shadow_enabled=True)
        out = _run("shadow", ctx, ["pull", "unknownpkg"])
        assert "E:" in out or "Unable to locate" in out or "not in" in out

    def test_pull_no_args(self):
        ctx = _make_ctx(shadow_enabled=True)
        out = _run("shadow", ctx, ["pull"])
        assert "Usage" in out


class TestShadowSearch:
    def test_search_blocked_when_not_enabled(self):
        ctx = _make_ctx(shadow_enabled=False)
        out = _run("shadow", ctx, ["search", "shade"])
        assert "not configured" in out.lower()

    def test_search_finds_shadow_pkg(self):
        ctx = _make_ctx(shadow_enabled=True)
        out = _run("shadow", ctx, ["search", "shade"])
        assert "shade" in out

    def test_search_no_results(self):
        ctx = _make_ctx(shadow_enabled=True)
        out = _run("shadow", ctx, ["search", "zzznothingxxx"])
        assert "No results" in out or "zzznothingxxx" in out


class TestShadowKits:
    def test_kits_shows_three_kits(self):
        ctx = _make_ctx(shadow_enabled=True)
        out = _run("shadow", ctx, ["kits"])
        assert "GHOST" in out.upper() or "ghost" in out.lower()
        assert "BREAKER" in out.upper() or "breaker" in out.lower()
        assert "ORACLE" in out.upper() or "oracle" in out.lower()

    def test_kits_shows_committed(self):
        ctx = _make_ctx(shadow_enabled=True)
        ctx.toolkit.commit_kit("ghost")
        out = _run("shadow", ctx, ["kits"])
        assert "COMMITTED" in out or "committed" in out.lower()


class TestShadowCommit:
    def test_commit_blocked_when_not_enabled(self):
        ctx = _make_ctx(shadow_enabled=False)
        out = _run("shadow", ctx, ["commit", "ghost"])
        assert "not configured" in out.lower()

    def test_commit_valid_kit(self):
        ctx = _make_ctx(shadow_enabled=True)
        out = _run("shadow", ctx, ["commit", "ghost"])
        assert "ghost" in out.lower()
        assert ctx.toolkit._committed_kit == "ghost"

    def test_commit_invalid_kit(self):
        ctx = _make_ctx(shadow_enabled=True)
        out = _run("shadow", ctx, ["commit", "alchemy"])
        assert "Unknown kit" in out or "alchemy" in out

    def test_commit_twice_blocked(self):
        ctx = _make_ctx(shadow_enabled=True)
        _run("shadow", ctx, ["commit", "ghost"])
        out = _run("shadow", ctx, ["commit", "breaker"])
        assert ctx.toolkit._committed_kit == "ghost"

    def test_commit_no_args(self):
        ctx = _make_ctx(shadow_enabled=True)
        out = _run("shadow", ctx, ["commit"])
        assert "Usage" in out or "kit" in out.lower()


# ---------------------------------------------------------------------------
# gpg
# ---------------------------------------------------------------------------


class TestGpg:
    def test_gpg_not_installed_error(self):
        ctx = _make_ctx()
        out = _run("gpg", ctx, [])
        assert "command not found" in out or "apt install gpg" in out

    def test_gpg_no_args_after_install(self):
        ctx = _make_ctx()
        ctx.toolkit.install("gpg", repo="apt")
        out = _run("gpg", ctx, [])
        assert "gpg" in out.lower()
        assert "GnuPG" in out or "gnupg" in out.lower()

    def test_gpg_list_keys_empty(self):
        ctx = _make_ctx()
        ctx.toolkit.install("gpg", repo="apt")
        out = _run("gpg", ctx, ["--list-keys"])
        assert "pub" in out

    def test_gpg_list_keys_with_installed_packages(self):
        ctx = _make_ctx()
        ctx.toolkit.install("gpg", repo="apt")
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("gpg", ctx, ["--list-keys"])
        assert "test@example.com" in out

    def test_gpg_verify_clean(self):
        ctx = _make_ctx()
        ctx.toolkit.install("gpg", repo="apt")
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("gpg", ctx, ["--verify", "libpcap"])
        assert "Good signature" in out

    def test_gpg_verify_unsigned(self):
        ctx = _make_ctx(shadow_enabled=True)
        ctx.toolkit.install("gpg", repo="apt")
        ctx.toolkit.install("shade", repo="shadow")
        out = _run("gpg", ctx, ["--verify", "shade"])
        assert "UNSIGNED" in out or "no signature" in out.lower() or "WARNING" in out

    def test_gpg_verify_no_pkg(self):
        ctx = _make_ctx()
        ctx.toolkit.install("gpg", repo="apt")
        out = _run("gpg", ctx, ["--verify"])
        assert "Usage" in out

    def test_gpg_unknown_option(self):
        ctx = _make_ctx()
        ctx.toolkit.install("gpg", repo="apt")
        out = _run("gpg", ctx, ["--encrypt"])
        assert "unrecognised" in out or "option" in out


# ---------------------------------------------------------------------------
# dpkg
# ---------------------------------------------------------------------------


class TestDpkg:
    def test_list_no_packages(self):
        ctx = _make_ctx()
        out = _run("dpkg", ctx, ["-l"])
        assert "Name" in out or "dpkg" in out.lower()

    def test_list_shows_installed(self):
        ctx = _make_ctx()
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("dpkg", ctx, ["-l"])
        assert "libpcap" in out

    def test_list_long_flag(self):
        ctx = _make_ctx()
        ctx.toolkit.install("gpg", repo="apt")
        out = _run("dpkg", ctx, ["--list"])
        assert "gpg" in out

    def test_status_installed(self):
        ctx = _make_ctx()
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("dpkg", ctx, ["-s", "libpcap"])
        assert "install ok installed" in out
        assert "libpcap" in out

    def test_status_not_installed(self):
        ctx = _make_ctx()
        out = _run("dpkg", ctx, ["-s", "ghost_tool"])
        assert "not installed" in out.lower()

    def test_get_selections(self):
        ctx = _make_ctx()
        ctx.toolkit.install("libpcap", repo="apt")
        ctx.toolkit.install("gpg", repo="apt")
        out = _run("dpkg", ctx, ["--get-selections"])
        assert "libpcap" in out
        assert "gpg" in out
        assert "install" in out

    def test_get_selections_empty(self):
        ctx = _make_ctx()
        out = _run("dpkg", ctx, ["--get-selections"])
        assert "no packages" in out.lower() or out.strip() == ""

    def test_no_args_shows_usage_or_list(self):
        ctx = _make_ctx()
        out = _run("dpkg", ctx, [])
        assert out  # produces some output

    def test_list_header_columns(self):
        ctx = _make_ctx()
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("dpkg", ctx, ["-l"])
        assert "Architecture" in out or "amd64" in out

    def test_status_shows_version(self):
        ctx = _make_ctx()
        ctx.toolkit.install("libpcap", repo="apt")
        out = _run("dpkg", ctx, ["-s", "libpcap"])
        assert "Version" in out
        assert "1.0" in out


# ---------------------------------------------------------------------------
# apt-get
# ---------------------------------------------------------------------------


class TestAptGet:
    def test_no_args_shows_usage(self):
        ctx = _make_ctx()
        out = _run("apt-get", ctx, [])
        assert "apt" in out.lower()

    def test_update_delegates_to_apt(self):
        ctx = _make_ctx()
        before = ctx.toolkit.bandwidth_remaining_kb
        out = _run("apt-get", ctx, ["update"])
        assert ctx.toolkit.bandwidth_remaining_kb == before - 200
        assert "InRelease" in out or "Done" in out

    def test_install_delegates_to_apt(self):
        ctx = _make_ctx()
        _run("apt-get", ctx, ["install", "libpcap"])
        assert "libpcap" in ctx.toolkit.installed

    def test_remove_delegates_to_apt(self):
        ctx = _make_ctx()
        ctx.toolkit.install("libpcap", repo="apt")
        _run("apt-get", ctx, ["remove", "libpcap"])
        assert "libpcap" not in ctx.toolkit.installed

    def test_invalid_subcommand(self):
        ctx = _make_ctx()
        out = _run("apt-get", ctx, ["frob"])
        assert "Invalid operation" in out or "frob" in out
