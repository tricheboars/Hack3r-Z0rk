"""Tests for hackerzork/effects/matrix.py — async, instant via speed_multiplier=0."""
from __future__ import annotations

import pytest
import hackerzork.effects as fx
from hackerzork.effects import set_console, null_console
from hackerzork.effects.matrix import (
    binary_rain,
    data_stream,
    decrypt_animation,
    matrix_rain,
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


class TestMatrixRain:
    async def test_completes_without_error(self):
        await matrix_rain(duration=1.0, width=40)

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await matrix_rain(duration=999.0)

    async def test_zero_width(self):
        await matrix_rain(duration=0.5, width=0)

    async def test_short_duration(self):
        await matrix_rain(duration=0.01, width=20)


class TestBinaryRain:
    async def test_completes_without_error(self):
        await binary_rain(duration=1.0)

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await binary_rain(duration=999.0)


class TestDataStream:
    async def test_simple_text(self):
        await data_stream("hello world from the data stream")

    async def test_empty_string(self):
        await data_stream("")

    async def test_disabled(self):
        fx.config.enabled = False
        await data_stream("some text here")

    async def test_short_text(self):
        await data_stream("hi")

    async def test_long_text(self):
        await data_stream(" ".join(["word"] * 50))


class TestDecryptAnimation:
    async def test_basic_decrypt(self):
        await decrypt_animation("XXXX XXXXX", "real plain", duration=0.5)

    async def test_empty_strings(self):
        await decrypt_animation("", "", duration=0.1)

    async def test_disabled(self):
        fx.config.enabled = False
        await decrypt_animation("cipher", "plain", duration=10.0)

    async def test_matching_strings(self):
        await decrypt_animation("hello world", "hello world", duration=0.3)

    async def test_long_text(self):
        cipher = "X" * 100
        plain = "a" * 100
        await decrypt_animation(cipher, plain, duration=0.5)
