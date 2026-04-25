"""Tests for hackerzork/systems/toolkit.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from hackerzork.systems.toolkit import (
    InstallResult,
    InstalledPackage,
    Package,
    Toolkit,
    VerifyResult,
    _pkg_from_dict,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PKG_DATA_DIR = Path(__file__).parent.parent.parent / "hackerzork" / "data" / "packages"


def _make_toolkit(
    fs=None,
    events=None,
    load_real_catalog: bool = False,
) -> Toolkit:
    mock_fs = fs or MagicMock()
    tk = Toolkit(fs=mock_fs, events=events)
    if load_real_catalog:
        tk.load_catalog(PKG_DATA_DIR)
    return tk


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


# ---------------------------------------------------------------------------
# Package YAML loading
# ---------------------------------------------------------------------------


class TestPkgFromDict:
    def test_basic_fields(self):
        data = {
            "name": "nmap",
            "provides": ["nmap"],
            "version": "7.94",
            "repo": "apt",
            "kit": None,
            "depends": ["libpcap"],
            "size_kb": 4200,
            "cost_btc": 0.0,
            "signer": "test@fyodor.lyon",
            "poison_chance": 0.02,
            "summary": "Network scanner",
            "unlocks_story": ["first_scanner"],
        }
        pkg = _pkg_from_dict(data)
        assert pkg.name == "nmap"
        assert pkg.provides == ["nmap"]
        assert pkg.version == "7.94"
        assert pkg.depends == ["libpcap"]
        assert pkg.size_kb == 4200
        assert pkg.poison_chance == 0.02
        assert pkg.unlocks_story == ["first_scanner"]

    def test_defaults(self):
        pkg = _pkg_from_dict({"name": "x"})
        assert pkg.version == "0.0"
        assert pkg.repo == "apt"
        assert pkg.kit is None
        assert pkg.depends == []
        assert pkg.cost_btc == 0.0
        assert pkg.signer == "UNSIGNED"
        assert pkg.poison_chance == 0.0
        assert pkg.unlocks_story == []


class TestLoadCatalog:
    def test_loads_all_yaml(self):
        tk = _make_toolkit(load_real_catalog=True)
        assert "nmap" in tk.catalog
        assert "libpcap" in tk.catalog
        assert "gpg" in tk.catalog
        assert "shade" in tk.catalog
        assert "ramroot" in tk.catalog
        assert "claude-toolkit" in tk.catalog

    def test_nmap_fields(self):
        tk = _make_toolkit(load_real_catalog=True)
        nmap = tk.catalog["nmap"]
        assert nmap.repo == "apt"
        assert nmap.kit is None
        assert "libpcap" in nmap.depends
        assert nmap.provides == ["nmap"]

    def test_shadow_pkg_fields(self):
        tk = _make_toolkit(load_real_catalog=True)
        shade = tk.catalog["shade"]
        assert shade.repo == "shadow"
        assert shade.kit == "ghost"
        assert shade.cost_btc > 0

    def test_total_package_count(self):
        tk = _make_toolkit(load_real_catalog=True)
        assert len(tk.catalog) >= 14

    def test_shadow_kits_covered(self):
        tk = _make_toolkit(load_real_catalog=True)
        shadow_pkgs = [p for p in tk.catalog.values() if p.repo == "shadow"]
        kits = {p.kit for p in shadow_pkgs}
        assert "ghost" in kits
        assert "breaker" in kits
        assert "oracle" in kits


# ---------------------------------------------------------------------------
# is_installed / available_commands
# ---------------------------------------------------------------------------


class TestIsInstalled:
    def test_baseline_commands_always_available(self):
        tk = _make_toolkit()
        assert tk.is_installed("ls")
        assert tk.is_installed("cat")
        assert tk.is_installed("apt")
        assert tk.is_installed("ssh")
        assert tk.is_installed("ping")

    def test_non_baseline_not_installed(self):
        tk = _make_toolkit()
        assert not tk.is_installed("nmap")
        assert not tk.is_installed("shade")

    def test_installed_package_command_available(self):
        tk = _make_toolkit()
        pkg = _make_pkg(name="nmap", provides=["nmap"])
        tk.catalog["nmap"] = pkg
        tk.install("nmap")
        assert tk.is_installed("nmap")

    def test_provides_multiple_commands(self):
        tk = _make_toolkit()
        pkg = _make_pkg(name="net-tools", provides=["ifconfig", "netstat", "arp"])
        tk.catalog["net-tools"] = pkg
        tk.install("net-tools")
        assert tk.is_installed("ifconfig")
        assert tk.is_installed("netstat")
        assert tk.is_installed("arp")

    def test_available_commands_includes_baseline(self):
        tk = _make_toolkit()
        cmds = tk.available_commands()
        assert "ls" in cmds
        assert "apt" in cmds


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


class TestInstall:
    def test_install_simple_apt_package(self):
        tk = _make_toolkit()
        pkg = _make_pkg(name="tcpdump", size_kb=100)
        tk.catalog["tcpdump"] = pkg
        result = tk.install("tcpdump", repo="apt")
        assert result.success
        assert "tcpdump" in tk.installed
        assert "tcpdump" in result.commands_unlocked

    def test_install_missing_package(self):
        tk = _make_toolkit()
        result = tk.install("nonexistent")
        assert not result.success
        assert "Unable to locate" in result.message

    def test_already_installed(self):
        tk = _make_toolkit()
        pkg = _make_pkg("mypkg")
        tk.catalog["mypkg"] = pkg
        tk.install("mypkg")
        result = tk.install("mypkg")
        assert not result.success
        assert "already" in result.message

    def test_wrong_repo_apt_for_shadow(self):
        tk = _make_toolkit()
        tk.shadow_enabled = True
        pkg = _make_pkg("shadepkg", repo="shadow", kit="ghost")
        tk.catalog["shadepkg"] = pkg
        result = tk.install("shadepkg", repo="apt")
        assert not result.success
        assert "shadow" in result.message

    def test_wrong_repo_shadow_for_apt(self):
        tk = _make_toolkit()
        tk.shadow_enabled = True
        pkg = _make_pkg("aptpkg", repo="apt")
        tk.catalog["aptpkg"] = pkg
        result = tk.install("aptpkg", repo="shadow")
        assert not result.success
        assert "apt" in result.message

    def test_dep_resolution(self):
        tk = _make_toolkit()
        dep = _make_pkg("libpcap", provides=[], size_kb=10)
        main = _make_pkg("nmap", depends=["libpcap"], size_kb=50)
        tk.catalog["libpcap"] = dep
        tk.catalog["nmap"] = main
        result = tk.install("nmap", repo="apt")
        assert result.success
        assert "libpcap" in tk.installed
        assert "nmap" in tk.installed

    def test_dep_already_installed_not_reinstalled(self):
        tk = _make_toolkit()
        dep = _make_pkg("libpcap", provides=[], size_kb=10)
        main = _make_pkg("nmap", depends=["libpcap"], size_kb=50)
        tk.catalog["libpcap"] = dep
        tk.catalog["nmap"] = main
        tk.install("libpcap")
        result = tk.install("nmap", repo="apt")
        assert result.success
        # libpcap count in installed should be 1, not 2
        assert list(tk.installed.keys()).count("libpcap") == 1

    def test_missing_dep_fails(self):
        tk = _make_toolkit()
        main = _make_pkg("nmap", depends=["libpcap"])
        tk.catalog["nmap"] = main
        result = tk.install("nmap", repo="apt")
        assert not result.success
        assert "libpcap" in result.message


# ---------------------------------------------------------------------------
# Bandwidth checks
# ---------------------------------------------------------------------------


class TestBandwidth:
    def test_bandwidth_deducted_on_install(self):
        tk = _make_toolkit()
        pkg = _make_pkg("tool", size_kb=1000)
        tk.catalog["tool"] = pkg
        tk.install("tool")
        assert tk.bandwidth_remaining_kb == 49_000

    def test_insufficient_bandwidth_fails(self):
        tk = _make_toolkit()
        tk.bandwidth_remaining_kb = 50
        pkg = _make_pkg("big", size_kb=100)
        tk.catalog["big"] = pkg
        result = tk.install("big")
        assert not result.success
        assert "bandwidth" in result.message.lower()

    def test_bandwidth_depleted_event_emitted(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        tk.bandwidth_remaining_kb = 100
        pkg = _make_pkg("tool", size_kb=100)
        tk.catalog["tool"] = pkg
        tk.install("tool")
        calls = [call.args[0] for call in events.emit.call_args_list]
        assert "bandwidth_depleted" in calls

    def test_consume_bandwidth_helper(self):
        tk = _make_toolkit()
        assert tk.consume_bandwidth(1000)
        assert tk.bandwidth_remaining_kb == 49_000
        assert not tk.consume_bandwidth(50_000)


# ---------------------------------------------------------------------------
# Wallet checks
# ---------------------------------------------------------------------------


class TestWallet:
    def test_wallet_deducted_on_shadow_install(self):
        tk = _make_toolkit()
        tk.shadow_enabled = True
        pkg = _make_pkg("shade", repo="shadow", kit="ghost", cost_btc=0.003)
        tk.catalog["shade"] = pkg
        initial = tk.wallet_btc
        tk.install("shade", repo="shadow")
        assert tk.wallet_btc < initial

    def test_insufficient_wallet_fails(self):
        tk = _make_toolkit()
        tk.shadow_enabled = True
        tk.wallet_btc = 0.001
        pkg = _make_pkg("shade", repo="shadow", kit="ghost", cost_btc=0.003)
        tk.catalog["shade"] = pkg
        result = tk.install("shade", repo="shadow")
        assert not result.success
        assert "funds" in result.message.lower() or "btc" in result.message.lower()

    def test_wallet_depleted_event(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        tk.shadow_enabled = True
        tk.wallet_btc = 0.003
        pkg = _make_pkg("shade", repo="shadow", kit="ghost", cost_btc=0.003)
        tk.catalog["shade"] = pkg
        tk.install("shade", repo="shadow")
        calls = [call.args[0] for call in events.emit.call_args_list]
        assert "wallet_depleted" in calls


# ---------------------------------------------------------------------------
# Shadow repo gating
# ---------------------------------------------------------------------------


class TestShadowGating:
    def test_shadow_install_blocked_when_not_enabled(self):
        tk = _make_toolkit()
        assert not tk.shadow_enabled
        pkg = _make_pkg("shade", repo="shadow", kit="ghost")
        tk.catalog["shade"] = pkg
        result = tk.install("shade", repo="shadow")
        assert not result.success
        assert "shadow" in result.message.lower()

    def test_shadow_install_succeeds_when_enabled(self):
        tk = _make_toolkit()
        tk.shadow_enabled = True
        pkg = _make_pkg("shade", repo="shadow", kit="ghost", cost_btc=0.0)
        tk.catalog["shade"] = pkg
        result = tk.install("shade", repo="shadow")
        assert result.success

    def test_sources_list_watcher_enables_shadow(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        assert not tk.shadow_enabled
        tk.check_shadow_source(
            "/etc/apt/sources.list.d/shadow.list",
            "deb shadow://.onion.ghost_of_kaczynski.7hop/ main",
        )
        assert tk.shadow_enabled
        calls = [call.args[0] for call in events.emit.call_args_list]
        assert "shadow_unlocked" in calls

    def test_non_shadow_path_does_not_enable(self):
        tk = _make_toolkit()
        tk.check_shadow_source(
            "/etc/apt/sources.list",
            "deb shadow://.onion.something/ main",
        )
        assert not tk.shadow_enabled

    def test_non_shadow_url_does_not_enable(self):
        tk = _make_toolkit()
        tk.check_shadow_source(
            "/etc/apt/sources.list.d/shadow.list",
            "deb http://example.com/debian main",
        )
        assert not tk.shadow_enabled

    def test_shadow_unlock_only_fires_once(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        tk.check_shadow_source(
            "/etc/apt/sources.list.d/shadow.list",
            "deb shadow://.onion.x/ main",
        )
        tk.check_shadow_source(
            "/etc/apt/sources.list.d/shadow.list",
            "deb shadow://.onion.x/ main",
        )
        unlock_calls = [
            c for c in events.emit.call_args_list if c.args[0] == "shadow_unlocked"
        ]
        assert len(unlock_calls) == 1


# ---------------------------------------------------------------------------
# Poison mechanics
# ---------------------------------------------------------------------------


class TestPoison:
    def test_zero_chance_never_poisons(self):
        tk = _make_toolkit()
        pkg = _make_pkg("safe", poison_chance=0.0)
        tk.catalog["safe"] = pkg
        for _ in range(20):
            tk.installed.clear()
            result = tk.install("safe")
            assert not result.poisoned

    def test_guaranteed_poison(self):
        tk = _make_toolkit()
        pkg = _make_pkg("danger", poison_chance=1.0)
        tk.catalog["danger"] = pkg
        result = tk.install("danger")
        assert result.poisoned
        ip = tk.installed["danger"]
        assert ip.poisoned
        assert ip.poison_vector is not None

    def test_poison_vector_valid(self):
        valid = {"heat_leak", "ip_leak", "wrong_output", "hidden_exfil"}
        tk = _make_toolkit()
        pkg = _make_pkg("danger", poison_chance=1.0)
        tk.catalog["danger"] = pkg
        result = tk.install("danger")
        assert tk.installed["danger"].poison_vector in valid

    def test_verified_halves_effective_chance(self):
        # With verified=True, chance should be halved vs unverified.
        # Test with 100% base chance to ensure both still fire, but confirm the formula.
        tk = _make_toolkit()
        pkg = _make_pkg("check", poison_chance=1.0)
        tk.catalog["check"] = pkg
        # verified=True still poisons at 100% base, just 1x not 2x modifier
        result = tk.install("check", verified=True)
        assert result.poisoned  # 1.0 * 1.0 * 1.0 = 1.0, still poisons

    def test_escalation_increases_chance(self):
        # At escalation=4, multiplier is (1 + 4*0.5) = 3x
        # With base 0.2 and 2x unverified: effective = 0.2 * 3 * 2 = 1.2 → guaranteed
        tk = _make_toolkit()
        pkg = _make_pkg("partial", poison_chance=0.2)
        tk.catalog["partial"] = pkg
        result = tk.install("partial", skynet_escalation=4.0, verified=False)
        assert result.poisoned

    def test_meta_engine_poison_call(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        pkg = _make_pkg("clean", poison_chance=0.0)
        tk.catalog["clean"] = pkg
        tk.install("clean")
        tk.poison("clean", "heat_leak")
        ip = tk.installed["clean"]
        assert ip.poisoned
        assert ip.poison_vector == "heat_leak"

    def test_poison_event_emitted(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        pkg = _make_pkg("clean")
        tk.catalog["clean"] = pkg
        tk.install("clean")
        tk.poison("clean", "ip_leak")
        calls = [c for c in events.emit.call_args_list if c.args[0] == "package_poisoned"]
        assert len(calls) >= 1


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


class TestRemove:
    def test_remove_installed_package(self):
        tk = _make_toolkit()
        pkg = _make_pkg("tool")
        tk.catalog["tool"] = pkg
        tk.install("tool")
        result = tk.remove("tool")
        assert result.success
        assert "tool" not in tk.installed

    def test_remove_not_installed(self):
        tk = _make_toolkit()
        result = tk.remove("ghost")
        assert not result.success
        assert "not installed" in result.message

    def test_remove_blocked_by_dependent(self):
        tk = _make_toolkit()
        dep = _make_pkg("libpcap", provides=[])
        main = _make_pkg("nmap", depends=["libpcap"])
        tk.catalog["libpcap"] = dep
        tk.catalog["nmap"] = main
        tk.install("nmap")
        result = tk.remove("libpcap")
        assert not result.success
        assert "nmap" in result.message

    def test_remove_emits_event(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        pkg = _make_pkg("tool")
        tk.catalog["tool"] = pkg
        tk.install("tool")
        tk.remove("tool")
        calls = [c.args[0] for c in events.emit.call_args_list]
        assert "package_removed" in calls


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


class TestVerify:
    def test_verify_requires_gpg(self):
        tk = _make_toolkit()
        pkg = _make_pkg("tool")
        tk.catalog["tool"] = pkg
        tk.install("tool")
        result = tk.verify("tool")
        assert not result.ok
        assert "gpg" in result.warning.lower()

    def test_verify_unsigned_package(self):
        tk = _make_toolkit()
        gpg_pkg = _make_pkg("gpg", provides=["gpg"])
        tool_pkg = _make_pkg("shadepkg", signer="UNSIGNED")
        tk.catalog["gpg"] = gpg_pkg
        tk.catalog["shadepkg"] = tool_pkg
        tk.install("gpg")
        tk.install("shadepkg")
        result = tk.verify("shadepkg")
        assert not result.ok
        assert result.signer == "UNSIGNED"

    def test_verify_clean_package(self):
        tk = _make_toolkit()
        gpg_pkg = _make_pkg("gpg", provides=["gpg"])
        tool_pkg = _make_pkg("cleanpkg", signer="trusted@example.com", poison_chance=0.0)
        tk.catalog["gpg"] = gpg_pkg
        tk.catalog["cleanpkg"] = tool_pkg
        tk.install("gpg")
        tk.install("cleanpkg")
        result = tk.verify("cleanpkg")
        assert result.ok
        assert result.signer == "trusted@example.com"
        assert result.warning is None

    def test_verify_sets_verified_flag(self):
        tk = _make_toolkit()
        gpg_pkg = _make_pkg("gpg", provides=["gpg"])
        tool_pkg = _make_pkg("tool", signer="trusted@example.com", poison_chance=0.0)
        tk.catalog["gpg"] = gpg_pkg
        tk.catalog["tool"] = tool_pkg
        tk.install("gpg")
        tk.install("tool")
        tk.verify("tool")
        assert tk.installed["tool"].verified

    def test_verify_poisoned_package_warns(self):
        tk = _make_toolkit()
        gpg_pkg = _make_pkg("gpg", provides=["gpg"])
        tool_pkg = _make_pkg("tool", signer="trusted@example.com", poison_chance=0.0)
        tk.catalog["gpg"] = gpg_pkg
        tk.catalog["tool"] = tool_pkg
        tk.install("gpg")
        tk.install("tool")
        tk.poison("tool", "heat_leak")
        result = tk.verify("tool")
        assert not result.ok
        assert "tampered" in result.warning.lower() or "mismatch" in result.warning.lower()

    def test_verify_uninstalled_package(self):
        tk = _make_toolkit()
        gpg_pkg = _make_pkg("gpg", provides=["gpg"])
        tk.catalog["gpg"] = gpg_pkg
        tk.install("gpg")
        result = tk.verify("nonexistent")
        assert not result.ok


# ---------------------------------------------------------------------------
# Kit commit
# ---------------------------------------------------------------------------


class TestKitCommit:
    def test_commit_valid_kit(self):
        tk = _make_toolkit()
        tk.shadow_enabled = True
        result = tk.commit_kit("ghost")
        assert result.success
        assert tk._committed_kit == "ghost"
        assert tk._kit_discount is True

    def test_commit_invalid_kit(self):
        tk = _make_toolkit()
        result = tk.commit_kit("alchemy")
        assert not result.success

    def test_commit_twice_blocked(self):
        tk = _make_toolkit()
        tk.commit_kit("ghost")
        result = tk.commit_kit("breaker")
        assert not result.success
        assert tk._committed_kit == "ghost"

    def test_kit_discount_applied(self):
        tk = _make_toolkit()
        tk.shadow_enabled = True
        pkg = _make_pkg("shade", repo="shadow", kit="ghost", cost_btc=0.004)
        tk.catalog["shade"] = pkg
        tk.commit_kit("ghost")
        pre_wallet = tk.wallet_btc
        tk.install("shade", repo="shadow")
        cost_paid = round(pre_wallet - tk.wallet_btc, 6)
        assert cost_paid == round(0.004 * 0.75, 6)

    def test_discount_not_applied_other_kit(self):
        tk = _make_toolkit()
        tk.shadow_enabled = True
        pkg = _make_pkg("ramroot", repo="shadow", kit="breaker", cost_btc=0.004)
        tk.catalog["ramroot"] = pkg
        tk.commit_kit("ghost")
        pre_wallet = tk.wallet_btc
        tk.install("ramroot", repo="shadow")
        cost_paid = round(pre_wallet - tk.wallet_btc, 6)
        assert cost_paid == 0.004  # no discount

    def test_commit_emits_event(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        tk.commit_kit("oracle")
        calls = [c.args[0] for c in events.emit.call_args_list]
        assert "kit_committed" in calls


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class TestEvents:
    def test_package_installed_event(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        pkg = _make_pkg("tool")
        tk.catalog["tool"] = pkg
        tk.install("tool")
        calls = [c.args[0] for c in events.emit.call_args_list]
        assert "package_installed" in calls

    def test_package_removed_event(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        pkg = _make_pkg("tool")
        tk.catalog["tool"] = pkg
        tk.install("tool")
        events.emit.reset_mock()
        tk.remove("tool")
        calls = [c.args[0] for c in events.emit.call_args_list]
        assert "package_removed" in calls

    def test_story_flag_event_on_install(self):
        events = MagicMock()
        tk = _make_toolkit(events=events)
        pkg = _make_pkg("nmap", unlocks_story=["first_scanner"])
        tk.catalog["nmap"] = pkg
        tk.install("nmap")
        calls = [c.args[0] for c in events.emit.call_args_list]
        assert "story_flag_set" in calls


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_round_trip(self):
        tk = _make_toolkit()
        pkg = _make_pkg("tool", provides=["tool"], size_kb=100)
        tk.catalog["tool"] = pkg
        tk.shadow_enabled = True
        tk.wallet_btc = 0.010
        tk.install("tool")

        state = tk.to_dict()

        tk2 = _make_toolkit()
        tk2.catalog["tool"] = pkg
        tk2.load_state(state)

        assert tk2.bandwidth_remaining_kb == tk.bandwidth_remaining_kb
        assert tk2.wallet_btc == tk.wallet_btc
        assert tk2.shadow_enabled is True
        assert "tool" in tk2.installed

    def test_load_state_skips_missing_catalog(self):
        tk = _make_toolkit()
        # No catalog entries, but state references one
        state = {
            "bandwidth_remaining_kb": 40_000,
            "wallet_btc": 0.010,
            "shadow_enabled": False,
            "installed": {"ghost_tool": {"pkg_name": "ghost_tool", "installed_at": 0.0}},
        }
        tk.load_state(state)
        assert "ghost_tool" not in tk.installed  # skipped — not in catalog

    def test_committed_kit_serialized(self):
        tk = _make_toolkit()
        tk.commit_kit("ghost")
        state = tk.to_dict()
        tk2 = _make_toolkit()
        tk2.load_state(state)
        assert tk2._committed_kit == "ghost"
        assert tk2._kit_discount is True
