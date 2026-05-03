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


# ---------------------------------------------------------------------------
# Regression tests — bugs found during post-ship review
# ---------------------------------------------------------------------------


class TestCensoredFileTamperRefusals:
    """rm/cp/mv on a censored file must refuse + spike heat instead of letting
    the player nuke or leak the vault."""

    @pytest.fixture
    def game(self):
        from hackerzork.game import Game
        g = Game(audio_enabled=False, effects_enabled=False, meta_enabled=True)
        g.boot()
        return g

    def test_rm_refuses_and_keeps_file(self, game):
        path = "/var/skynet/censored/epstein_client_list.csv.enc"
        before = game._heat.level
        out = game._shell.execute(f"rm {path}")
        assert "SkyNet has flagged" in out
        assert game._fs.file_exists(path)
        assert game._heat.level - before == pytest.approx(15.0)

    def test_rm_force_still_refuses(self, game):
        path = "/var/skynet/censored/epstein_client_list.csv.enc"
        out = game._shell.execute(f"rm -f {path}")
        assert "SkyNet has flagged" in out
        assert game._fs.file_exists(path)

    def test_cp_refuses(self, game):
        path = "/var/skynet/censored/epstein_client_list.csv.enc"
        out = game._shell.execute(f"cp {path} /tmp/leak.enc")
        assert "SkyNet has flagged" in out
        assert not game._fs.file_exists("/tmp/leak.enc")

    def test_mv_refuses(self, game):
        path = "/var/skynet/censored/epstein_client_list.csv.enc"
        out = game._shell.execute(f"mv {path} /tmp/moved.enc")
        assert "SkyNet has flagged" in out
        assert game._fs.file_exists(path)
        assert not game._fs.file_exists("/tmp/moved.enc")

    def test_rm_emits_tamper_event(self, game):
        seen = []
        game._events.on(
            "censored_file_tampered",
            lambda e: seen.append(e.data.get("action", "")),
        )
        game._shell.execute(
            "rm /var/skynet/censored/epstein_client_list.csv.enc"
        )
        assert seen == ["rm"]


class TestHeadTailGrepRespectCensorship:
    """head/tail/grep must show the censor quip — not leak placeholder content."""

    @pytest.fixture
    def game(self):
        from hackerzork.game import Game
        g = Game(audio_enabled=False, effects_enabled=False, meta_enabled=True)
        g.boot()
        return g

    def test_head_shows_censor_quip(self, game):
        out = game._shell.execute(
            "head /var/skynet/censored/epstein_client_list.csv.enc"
        )
        assert "[CENSORED" in out
        assert "Decryption refused" in out
        assert "[encrypted; 14 rows" not in out  # no placeholder leak

    def test_head_bumps_heat(self, game):
        before = game._heat.level
        game._shell.execute(
            "head /var/skynet/censored/epstein_client_list.csv.enc"
        )
        assert game._heat.level - before == pytest.approx(12.0)

    def test_tail_shows_censor_quip(self, game):
        out = game._shell.execute(
            "tail /var/skynet/censored/epstein_client_list.csv.enc"
        )
        assert "[CENSORED" in out
        assert "[encrypted; 14 rows" not in out

    def test_grep_refuses_loudly(self, game):
        out = game._shell.execute(
            "grep list /var/skynet/censored/epstein_client_list.csv.enc"
        )
        assert "censored" in out.lower()
        assert "skynet" in out.lower()

    def test_grep_recursive_marks_each_censored_hit(self, game):
        out = game._shell.execute("grep -r yacht /var/skynet/censored")
        # Several censored files should contribute refusal lines
        assert out.count("censored — SkyNet refused") >= 5


class TestCatHeatCapPreventsBurnCascade:
    """`cat *.enc` on the full vault must not insta-burn the player twice
    (the bug that motivated the heat cap)."""

    @pytest.fixture
    def game(self):
        from hackerzork.game import Game
        g = Game(audio_enabled=False, effects_enabled=False, meta_enabled=True)
        g.boot()
        return g

    def test_glob_cat_caps_heat_at_30(self, game):
        game._shell.execute("cat /var/skynet/censored/*.enc | wc -l")
        # One command should not exceed the cap
        assert game._heat.level <= 30.5

    def test_glob_cat_does_not_trigger_identity_burn(self, game):
        game._shell.execute("cat /var/skynet/censored/*.enc | wc -l")
        # If burn fired, awareness would be at 100. Cap should keep it well below.
        assert game._skynet.awareness < 30.0

    def test_glob_cat_emits_one_event_not_per_file(self, game):
        events_seen: list[int] = []
        game._events.on(
            "censored_file_accessed",
            lambda e: events_seen.append(e.data.get("count", 1)),
        )
        game._shell.execute("cat /var/skynet/censored/*.enc | wc -l")
        # Exactly one event, with count > 1 (it batched many)
        assert len(events_seen) == 1
        assert events_seen[0] > 10

    def test_single_cat_still_full_cost(self, game):
        before = game._heat.level
        game._shell.execute(
            "cat /var/skynet/censored/PROJECT_GENESIS.md.enc"
        )
        # Single file should still cost the file's actual censor_heat (15)
        assert game._heat.level - before == pytest.approx(15.0)


class TestDecryptKeyDropAndCommand:
    """First-PRISM-read drops decrypt_key.bin into trash; recover + decrypt
    then unlocks the late-game vault read with heavy heat cost."""

    @pytest.fixture
    def game(self):
        from hackerzork.game import Game
        g = Game(audio_enabled=False, effects_enabled=False, meta_enabled=True)
        g.boot()
        return g

    def test_decrypt_with_no_key_fails(self, game):
        out = game._shell.execute(
            "decrypt /var/skynet/censored/epstein_client_list.csv.enc"
        )
        assert "no decryption key" in out
        assert "/home/user/decrypt_key.bin" in out

    def test_first_prism_read_drops_key_in_trash(self, game):
        assert not game._state.has_flag("prism_decrypt_key_dropped")
        game._shell.execute(
            "cat /var/skynet/censored/PRISM_intercepts/intercept_player_session.eml.enc"
        )
        assert game._state.has_flag("prism_decrypt_key_dropped")
        trash_paths = [p for p, _ in game._fs.list_trash()]
        assert "/home/user/decrypt_key.bin" in trash_paths

    def test_key_drop_is_one_shot(self, game):
        # Read three different PRISM files
        for f in (
            "intercept_player_session.eml.enc",
            "intercept_2026-04-26_0914.eml.enc",
            "intercept_metadata_dump_partial.json.enc",
        ):
            game._shell.execute(f"cat /var/skynet/censored/PRISM_intercepts/{f}")
        # Only one decrypt_key.bin should ever exist in trash
        trash_paths = [p for p, _ in game._fs.list_trash()]
        assert trash_paths.count("/home/user/decrypt_key.bin") == 1

    def test_non_prism_censored_read_does_not_drop_key(self, game):
        game._shell.execute(
            "cat /var/skynet/censored/epstein_client_list.csv.enc"
        )
        assert not game._state.has_flag("prism_decrypt_key_dropped")
        trash_paths = [p for p, _ in game._fs.list_trash()]
        assert "/home/user/decrypt_key.bin" not in trash_paths

    def test_recover_and_decrypt_succeeds(self, game):
        game._shell.execute(
            "cat /var/skynet/censored/PRISM_intercepts/intercept_player_session.eml.enc"
        )
        game._shell.execute("recover decrypt_key.bin")
        assert game._fs.file_exists("/home/user/decrypt_key.bin")
        out = game._shell.execute(
            "decrypt /var/skynet/censored/PROJECT_GENESIS.md.enc"
        )
        assert "[DECRYPTED" in out
        assert "PROJECT_GENESIS" in out
        # The genesis memo body should be visible after decrypt
        assert "smoking gun" in out

    def test_decrypt_costs_20_heat_per_file(self, game):
        game._shell.execute(
            "cat /var/skynet/censored/PRISM_intercepts/intercept_player_session.eml.enc"
        )
        game._shell.execute("recover decrypt_key.bin")
        before = game._heat.level
        game._shell.execute(
            "decrypt /var/skynet/censored/area51_inventory.txt.enc"
        )
        # 20 from decrypt, plus the cat that read PRISM (heat 8)
        assert game._heat.level - before == pytest.approx(20.0)

    def test_first_decrypt_fires_skynet_bark_exactly_once(self, game):
        game._shell.execute(
            "cat /var/skynet/censored/PRISM_intercepts/intercept_player_session.eml.enc"
        )
        game._shell.execute("recover decrypt_key.bin")
        out1 = game._shell.execute(
            "decrypt /var/skynet/censored/area51_inventory.txt.enc"
        )
        out2 = game._shell.execute(
            "decrypt /var/skynet/censored/flat_earth_society_full_member_roster.csv.enc"
        )
        assert "you broke the seal" in out1
        assert "you broke the seal" not in out2
        assert game._state.has_flag("first_decrypt_fired")

    def test_decrypt_non_censored_is_a_friendly_no_op(self, game):
        game._shell.execute(
            "cat /var/skynet/censored/PRISM_intercepts/intercept_player_session.eml.enc"
        )
        game._shell.execute("recover decrypt_key.bin")
        out = game._shell.execute("decrypt /home/user/.bashrc")
        assert "not encrypted" in out
        # No heat penalty for accidentally decrypting a plaintext file
        before = game._heat.level
        game._shell.execute("decrypt /home/user/.bashrc")
        assert game._heat.level == pytest.approx(before)

    def test_decrypt_missing_file(self, game):
        game._shell.execute(
            "cat /var/skynet/censored/PRISM_intercepts/intercept_player_session.eml.enc"
        )
        game._shell.execute("recover decrypt_key.bin")
        out = game._shell.execute("decrypt /nope/missing.enc")
        assert "No such file" in out

    def test_decrypt_emits_event(self, game):
        game._shell.execute(
            "cat /var/skynet/censored/PRISM_intercepts/intercept_player_session.eml.enc"
        )
        game._shell.execute("recover decrypt_key.bin")
        seen = []
        game._events.on(
            "censored_file_decrypted",
            lambda e: seen.append(e.data.get("filename", "")),
        )
        game._shell.execute(
            "decrypt /var/skynet/censored/PROJECT_GENESIS.md.enc"
        )
        assert seen == ["PROJECT_GENESIS.md.enc"]

    def test_decrypt_flag_persists_through_save_load(self, game):
        # Trigger key drop + decrypt
        game._shell.execute(
            "cat /var/skynet/censored/PRISM_intercepts/intercept_player_session.eml.enc"
        )
        game._shell.execute("recover decrypt_key.bin")
        game._shell.execute(
            "decrypt /var/skynet/censored/area51_inventory.txt.enc"
        )
        assert game._state.has_flag("prism_decrypt_key_dropped")
        assert game._state.has_flag("first_decrypt_fired")

        save_data = game._save.collect(
            fs=game._fs, network=game._network, heat=game._heat,
            toolkit=game._toolkit, comms=game._comms, state=game._state,
            history=game._history, env=game._env,
        )

        from hackerzork.game import Game
        g2 = Game(audio_enabled=False, effects_enabled=False, meta_enabled=True)
        g2.boot()
        g2._save.apply(
            save_data, fs=g2._fs, network=g2._network, heat=g2._heat,
            toolkit=g2._toolkit, comms=g2._comms, state=g2._state,
            history=g2._history, env=g2._env,
        )
        assert g2._state.has_flag("prism_decrypt_key_dropped")
        assert g2._state.has_flag("first_decrypt_fired")
        # Decrypt key still in /home/user
        assert g2._fs.file_exists("/home/user/decrypt_key.bin")
        # And second decrypt should NOT fire the bark (flag preserved)
        out = g2._shell.execute(
            "decrypt /var/skynet/censored/clinton_arkancide_log.xlsx.enc"
        )
        assert "you broke the seal" not in out

    def test_decrypt_key_drop_via_head_or_tail(self, game):
        # Player using head on a PRISM file should also trigger key drop
        assert not game._state.has_flag("prism_decrypt_key_dropped")
        game._shell.execute(
            "head /var/skynet/censored/PRISM_intercepts/intercept_player_session.eml.enc"
        )
        assert game._state.has_flag("prism_decrypt_key_dropped")

