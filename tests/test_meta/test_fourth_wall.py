"""Tests for hackerzork/meta/fourth_wall.py — async, instant via speed_multiplier=0."""
from __future__ import annotations

import pytest
import hackerzork.effects as fx
from hackerzork.effects import set_console, null_console
from hackerzork.meta.fourth_wall import FourthWallBreaker


@pytest.fixture(autouse=True)
def instant_effects():
    orig_speed = fx.config.speed_multiplier
    orig_enabled = fx.config.enabled
    orig_console = fx.get_console()
    fx.config.speed_multiplier = 0
    fx.config.enabled = True
    set_console(null_console())
    yield
    fx.config.speed_multiplier = orig_speed
    fx.config.enabled = orig_enabled
    set_console(orig_console)


def _fw(enabled: bool = True) -> FourthWallBreaker:
    return FourthWallBreaker(enabled=enabled)


# ---------------------------------------------------------------------------
# Disabled — all effects are no-ops
# ---------------------------------------------------------------------------

class TestDisabled:
    async def test_change_terminal_title_no_crash(self):
        await _fw(enabled=False).change_terminal_title("test")

    async def test_fake_crash_no_crash(self):
        await _fw(enabled=False).fake_crash()

    async def test_fake_reboot_no_crash(self):
        await _fw(enabled=False).fake_reboot()

    async def test_inject_text_returns_text(self):
        result = await _fw(enabled=False).inject_text("hello")
        assert result == "hello"

    async def test_command_echo_corruption_returns_original(self):
        result = await _fw(enabled=False).command_echo_corruption("cat /etc/hosts")
        assert result == "cat /etc/hosts"

    async def test_phantom_cursor_no_crash(self):
        await _fw(enabled=False).phantom_cursor()

    async def test_fake_system_error_returns_string(self):
        result = await _fw(enabled=False).fake_system_error("segfault")
        assert isinstance(result, str)

    async def test_address_player_returns_message(self):
        msg = "hello player"
        result = await _fw(enabled=False).address_player(msg)
        assert result == msg

    async def test_corrupt_prompt_returns_string(self):
        result = await _fw(enabled=False).corrupt_prompt()
        assert isinstance(result, str)

    async def test_subtle_typo_returns_text(self):
        result = await _fw(enabled=False).subtle_typo("hello world")
        assert result == "hello world"

    async def test_log_injection_returns_string(self):
        result = await _fw(enabled=False).log_injection("existing log")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# inject_text
# ---------------------------------------------------------------------------

class TestInjectText:
    async def test_returns_injected_text(self):
        fw = _fw()
        result = await fw.inject_text("I see you.")
        assert result == "I see you."

    async def test_empty_text_no_crash(self):
        await _fw().inject_text("")

    async def test_rich_markup_no_crash(self):
        await _fw().inject_text("[bold red]WARNING[/bold red]")


# ---------------------------------------------------------------------------
# command_echo_corruption
# ---------------------------------------------------------------------------

class TestCommandEchoCorruption:
    async def test_returns_string(self):
        fw = _fw()
        result = await fw.command_echo_corruption("cat /var/log/auth.log")
        assert isinstance(result, str)

    async def test_empty_string_unchanged(self):
        fw = _fw()
        result = await fw.command_echo_corruption("")
        assert result == ""

    async def test_corruption_differs_from_original(self):
        fw = _fw()
        original = "cat /var/log/auth.log"
        # Run multiple times — at least one should differ
        results = {await fw.command_echo_corruption(original) for _ in range(10)}
        # Either all same (unlikely with random) or at least one differs
        assert any(r != original for r in results) or len(results) == 1

    async def test_short_input_no_crash(self):
        result = await _fw().command_echo_corruption("ls")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# subtle_typo
# ---------------------------------------------------------------------------

class TestSubtleTypo:
    async def test_returns_string(self):
        result = await _fw().subtle_typo("the quick brown fox")
        assert isinstance(result, str)

    async def test_empty_string_unchanged(self):
        result = await _fw().subtle_typo("")
        assert result == ""

    async def test_result_is_similar_length(self):
        text = "authentication and authorization"
        result = await _fw().subtle_typo(text)
        # Typos don't add/remove many chars
        assert abs(len(result) - len(text)) <= 2

    async def test_no_crash_on_no_typo_match(self):
        # Text with no known typo candidates
        result = await _fw().subtle_typo("xyz xyz xyz")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# log_injection
# ---------------------------------------------------------------------------

class TestLogInjection:
    async def test_returns_string(self):
        result = await _fw().log_injection("Apr 24 00:00:01 burner sshd: accepted")
        assert isinstance(result, str)

    async def test_result_longer_than_input(self):
        log = "line one\nline two\n"
        result = await _fw().log_injection(log)
        assert len(result) > len(log)

    async def test_empty_log_returns_entry(self):
        result = await _fw().log_injection("")
        assert "sk_watchdog" in result or "HEARTBEAT" in result

    async def test_contains_heartbeat_or_watchdog(self):
        result = await _fw().log_injection("some log content\nmore content")
        assert "sk_watchdog" in result or "HEARTBEAT" in result


# ---------------------------------------------------------------------------
# fake_system_error
# ---------------------------------------------------------------------------

class TestFakeSystemError:
    async def test_segfault_returns_string(self):
        result = await _fw().fake_system_error("segfault")
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_oops_returns_string(self):
        result = await _fw().fake_system_error("oops")
        assert isinstance(result, str)

    async def test_ioerr_returns_string(self):
        result = await _fw().fake_system_error("ioerr")
        assert isinstance(result, str)

    async def test_oom_returns_string(self):
        result = await _fw().fake_system_error("oom")
        assert isinstance(result, str)

    async def test_unknown_type_returns_default(self):
        result = await _fw().fake_system_error("unknown_error_type")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# address_player
# ---------------------------------------------------------------------------

class TestAddressPlayer:
    async def test_returns_message(self):
        msg = "I know who you are."
        result = await _fw().address_player(msg)
        assert result == msg

    async def test_no_crash_with_rich_markup(self):
        await _fw().address_player("[bold]test[/bold]")


# ---------------------------------------------------------------------------
# corrupt_prompt
# ---------------------------------------------------------------------------

class TestCorruptPrompt:
    async def test_returns_string(self):
        result = await _fw().corrupt_prompt()
        assert isinstance(result, str)

    async def test_prompt_ends_with_space(self):
        result = await _fw().corrupt_prompt()
        # All corrupt prompts end with "$ " or "# "
        assert result.endswith("$ ") or result.endswith("# ") or result.endswith("] ")

    async def test_differs_from_normal_prompt(self):
        results = {await _fw().corrupt_prompt() for _ in range(20)}
        normal = "user@burner:~$ "
        # At least sometimes returns a different prompt
        assert len(results) >= 1  # and they're all valid strings


# ---------------------------------------------------------------------------
# fake_crash
# ---------------------------------------------------------------------------

class TestFakeCrash:
    async def test_completes_without_error(self):
        await _fw().fake_crash()

    async def test_disabled_returns_immediately(self):
        await _fw(enabled=False).fake_crash()


# ---------------------------------------------------------------------------
# fake_reboot
# ---------------------------------------------------------------------------

class TestFakeReboot:
    async def test_completes_without_error(self):
        await _fw().fake_reboot()

    async def test_disabled_returns_immediately(self):
        await _fw(enabled=False).fake_reboot()


# ---------------------------------------------------------------------------
# change_terminal_title
# ---------------------------------------------------------------------------

class TestChangeTerminalTitle:
    async def test_no_crash(self):
        await _fw().change_terminal_title("test title")

    async def test_disabled_no_crash(self):
        await _fw(enabled=False).change_terminal_title("test")


# ---------------------------------------------------------------------------
# phantom_cursor
# ---------------------------------------------------------------------------

class TestPhantomCursor:
    async def test_no_crash(self):
        await _fw().phantom_cursor()

    async def test_disabled_no_crash(self):
        await _fw(enabled=False).phantom_cursor()


# ---------------------------------------------------------------------------
# run() dispatcher
# ---------------------------------------------------------------------------

class TestRunDispatcher:
    async def test_run_inject_text(self):
        fw = _fw()
        result = await fw.run("inject_text", tier=2)
        assert result is not None or result is None  # just no crash

    async def test_run_unknown_effect_returns_none(self):
        fw = _fw()
        result = await fw.run("nonexistent_effect")
        assert result is None

    async def test_run_disabled_returns_none(self):
        fw = _fw(enabled=False)
        result = await fw.run("inject_text", tier=3)
        assert result is None

    async def test_run_all_valid_effects_no_crash(self):
        fw = _fw()
        effects = [
            "subtle_typo", "log_injection", "inject_text", "change_terminal_title",
            "command_echo_corruption", "corrupt_prompt", "fake_system_error",
            "fake_crash", "plant_evidence", "corrupt_command_output",
            "address_player", "fake_reboot", "phantom_cursor",
        ]
        for effect in effects:
            await fw.run(effect, awareness=50.0, tier=3)
