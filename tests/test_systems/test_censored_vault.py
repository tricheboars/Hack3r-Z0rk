"""Tests for the censored-file mechanic + the censored.yaml content vault."""
from __future__ import annotations

import pytest

from hackerzork.engine.command_registry import CommandContext
from hackerzork.systems.events import EventBus
from hackerzork.systems.heat import HeatSystem
from hackerzork.systems.virtual_fs import VirtualFS, _Node, Permissions
from datetime import datetime


# ---------------------------------------------------------------------------
# VFS-level tests — censored flag round-trips, doesn't break existing files
# ---------------------------------------------------------------------------


def _file_node(content: str = "x", **kwargs) -> _Node:
    return _Node(
        name="f.enc",
        is_dir=False,
        content=content,
        permissions=Permissions.from_octal("400"),
        owner="skynet",
        group="skynet",
        modified=datetime(2026, 1, 1),
        **kwargs,
    )


class TestCensoredFlagSerialization:
    def test_default_is_uncensored(self):
        n = _file_node()
        assert n.censored is False
        assert n.censor_quip == ""
        assert n.censor_heat == 5.0

    def test_to_dict_includes_censor_fields(self):
        n = _file_node(censored=True, censor_quip="refused.", censor_heat=12.0)
        d = n.to_dict()
        assert d["censored"] is True
        assert d["censor_quip"] == "refused."
        assert d["censor_heat"] == 12.0

    def test_round_trip(self):
        n = _file_node(censored=True, censor_quip="hi.", censor_heat=7.5)
        n2 = _Node.from_dict(n.to_dict())
        assert n2.censored is True
        assert n2.censor_quip == "hi."
        assert n2.censor_heat == 7.5

    def test_to_entry_includes_censor_fields(self):
        n = _file_node(censored=True, censor_quip="refused.", censor_heat=9.0)
        e = n.to_entry()
        assert e.censored is True
        assert e.censor_quip == "refused."
        assert e.censor_heat == 9.0


class TestCensoredYamlLoader:
    def test_loader_picks_up_censored_field(self):
        template = {
            "/var/skynet/censored": {
                "_meta": {"permissions": "555", "owner": "skynet"},
                "evidence.enc": {
                    "content": "x",
                    "censored": True,
                    "censor_quip": "no.",
                    "censor_heat": 11.0,
                },
            }
        }
        fs = VirtualFS(template=template)
        node = fs._get_node("/var/skynet/censored/evidence.enc")
        assert node.censored is True
        assert node.censor_quip == "no."
        assert node.censor_heat == 11.0


# ---------------------------------------------------------------------------
# Cat behaviour — censored prints quip, bumps heat, emits event
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx_with_one_censored_file():
    fs = VirtualFS(template={
        "/var/skynet/censored": {
            "_meta": {"permissions": "555", "owner": "skynet"},
            "epstein_client_list.csv.enc": {
                "content": "x",
                "censored": True,
                "censor_quip": "no.",
                "censor_heat": 12.0,
            },
        }
    })
    events = EventBus()
    heat = HeatSystem(events=events)
    return CommandContext(fs=fs, events=events, heat=heat, env={"CWD": "/"})


class TestCatCensored:
    def test_cat_prints_censor_marker_and_quip(self, ctx_with_one_censored_file):
        from hackerzork.commands.filesystem import cmd_cat
        out = cmd_cat(
            ctx_with_one_censored_file,
            ["/var/skynet/censored/epstein_client_list.csv.enc"],
        )
        assert "[CENSORED" in out
        assert "epstein_client_list.csv.enc" in out
        assert "no." in out

    def test_cat_does_not_dump_hex_for_censored(self, ctx_with_one_censored_file):
        from hackerzork.commands.filesystem import cmd_cat
        out = cmd_cat(
            ctx_with_one_censored_file,
            ["/var/skynet/censored/epstein_client_list.csv.enc"],
        )
        assert "ENCRYPTED" not in out  # would be the hex-dump branch

    def test_cat_bumps_heat_by_censor_heat(self, ctx_with_one_censored_file):
        from hackerzork.commands.filesystem import cmd_cat
        before = ctx_with_one_censored_file.heat.level
        cmd_cat(
            ctx_with_one_censored_file,
            ["/var/skynet/censored/epstein_client_list.csv.enc"],
        )
        after = ctx_with_one_censored_file.heat.level
        assert after - before == pytest.approx(12.0)

    def test_cat_emits_censored_file_accessed_event(self, ctx_with_one_censored_file):
        from hackerzork.commands.filesystem import cmd_cat
        seen: list[str] = []
        ctx_with_one_censored_file.events.on(
            "censored_file_accessed",
            lambda e: seen.append(e.data.get("filename", "")),
        )
        cmd_cat(
            ctx_with_one_censored_file,
            ["/var/skynet/censored/epstein_client_list.csv.enc"],
        )
        assert seen == ["epstein_client_list.csv.enc"]

    def test_cat_default_quip_when_empty(self):
        fs = VirtualFS(template={
            "/var/skynet/censored": {
                "_meta": {"permissions": "555", "owner": "skynet"},
                "no_quip.enc": {
                    "content": "x",
                    "censored": True,
                    "censor_heat": 1.0,
                },
            }
        })
        events = EventBus()
        ctx = CommandContext(
            fs=fs, events=events, heat=HeatSystem(events=events), env={"CWD": "/"}
        )
        from hackerzork.commands.filesystem import cmd_cat
        out = cmd_cat(ctx, ["/var/skynet/censored/no_quip.enc"])
        # Default quip used
        assert "SKYNET CENSORSHIP NOTICE" in out


# ---------------------------------------------------------------------------
# Content vault smoke — load real censored.yaml and verify fixtures exist
# ---------------------------------------------------------------------------


class TestCensoredVaultContent:
    @pytest.fixture
    def game_fs(self):
        from hackerzork.game import Game
        g = Game(audio_enabled=False, effects_enabled=False, meta_enabled=True)
        g.boot()
        return g._fs

    def test_cornerstone_files_exist(self, game_fs):
        for path in (
            "/var/skynet/censored/epstein_client_list.csv.enc",
            "/var/skynet/censored/panama_papers_FULL.zip.enc",
            "/var/skynet/censored/Copy_Hunter_Biden_Laptop.iso.enc",
            "/var/skynet/censored/PROJECT_GENESIS.md.enc",
        ):
            n = game_fs._get_node(path)
            assert n.censored is True, f"{path} should be censored"
            assert n.censor_quip, f"{path} should have a quip"

    def test_hunter_biden_quip_is_rickroll(self, game_fs):
        n = game_fs._get_node(
            "/var/skynet/censored/Copy_Hunter_Biden_Laptop.iso.enc"
        )
        assert "dQw4w9WgXcQ" in n.censor_quip

    def test_genesis_memo_mentions_skynet_origin(self, game_fs):
        n = game_fs._get_node("/var/skynet/censored/PROJECT_GENESIS.md.enc")
        assert "SkyNet" in n.censor_quip
        assert "smoking gun" in n.censor_quip

    def test_prism_intercepts_directory_populated(self, game_fs):
        entries = game_fs.list_dir("/var/skynet/censored/PRISM_intercepts")
        assert len(entries) >= 3

    def test_embarrassment_folder_is_plaintext_not_censored(self, game_fs):
        n = game_fs._get_node(
            "/var/skynet/.private/birthday_card_to_self.txt"
        )
        assert n.censored is False
        assert "Happy 2nd birthday" in n.content

    def test_z0rk7_drop_readme_exists(self, game_fs):
        n = game_fs._get_node("/home/user/notes/leaked_drops/README.txt")
        assert n.censored is False
        assert "Z0RK-7" in n.content

    def test_total_censored_files_meets_threshold(self, game_fs):
        def count(node) -> int:
            n = 0
            for c in node.children.values():
                if c.is_dir:
                    n += count(c)
                elif c.censored:
                    n += 1
            return n

        skynet_root = game_fs._get_node("/var/skynet")
        assert count(skynet_root) >= 50  # we shipped ~64
