"""Tests for hackerzork/effects/animations.py — async, instant via speed_multiplier=0."""
from __future__ import annotations

import pytest
import hackerzork.effects as fx
from hackerzork.effects import set_console, null_console
from hackerzork.effects.animations import (
    boot_sequence,
    breach_animation,
    connection_animation,
    progress_bar,
    scan_animation,
    shutdown_sequence,
    spinner,
)


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


class TestBootSequence:
    async def test_completes_without_error(self):
        await boot_sequence()

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await boot_sequence()

    async def test_runs_twice_no_crash(self):
        await boot_sequence()
        await boot_sequence()


class TestProgressBar:
    async def test_hack_style(self):
        await progress_bar("Injecting payload", duration=0.5, style="hack")

    async def test_download_style(self):
        await progress_bar("Downloading exploit", duration=0.5, style="download")

    async def test_decrypt_style(self):
        await progress_bar("Decrypting key", duration=0.5, style="decrypt")

    async def test_upload_style(self):
        await progress_bar("Uploading exfil", duration=0.5, style="upload")

    async def test_unknown_style_falls_back(self):
        # Unknown style should fall back to hack without raising
        await progress_bar("Test", duration=0.1, style="nonexistent")

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await progress_bar("Should skip", duration=999.0)

    async def test_zero_width(self):
        await progress_bar("Zero", duration=0.1, width=0)

    async def test_narrow_width(self):
        await progress_bar("Narrow", duration=0.1, width=5)


class TestSpinner:
    async def test_completes_without_error(self):
        await spinner("Processing...", duration=0.5)

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await spinner("Should skip", duration=999.0)

    async def test_empty_label(self):
        await spinner("", duration=0.1)

    async def test_zero_duration(self):
        await spinner("Instant", duration=0.0)


class TestConnectionAnimation:
    async def test_completes_without_error(self):
        await connection_animation("10.13.37.1")

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await connection_animation("192.168.1.1")

    async def test_various_targets(self):
        for target in ["10.0.0.1", "relay-alpha.darknet.local", "localhost"]:
            await connection_animation(target)


class TestBreachAnimation:
    async def test_completes_without_error(self):
        await breach_animation()

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await breach_animation()

    async def test_runs_twice_no_crash(self):
        await breach_animation()
        await breach_animation()


class TestShutdownSequence:
    async def test_completes_without_error(self):
        await shutdown_sequence()

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await shutdown_sequence()


class TestScanAnimation:
    async def test_completes_without_error(self):
        await scan_animation("10.13.37.1")

    async def test_zero_ports_found(self):
        await scan_animation("10.0.0.1", ports_found=0)

    async def test_max_ports_found(self):
        await scan_animation("10.0.0.1", ports_found=8)

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await scan_animation("10.0.0.1", ports_found=5)

    async def test_various_targets(self):
        for target in ["10.13.37.1", "relay.darknet.local", "192.168.0.1"]:
            await scan_animation(target, ports_found=2)
