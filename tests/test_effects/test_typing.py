"""Tests for hackerzork/effects/typing.py — async, instant via speed_multiplier=0."""
from __future__ import annotations

import pytest
import hackerzork.effects as fx
from hackerzork.effects import set_console, null_console
from hackerzork.effects.typing import (
    dramatic_pause,
    redacted_text,
    reveal_redacted,
    typewriter,
    typewriter_fast,
)


@pytest.fixture(autouse=True)
def instant_effects():
    """Set speed=0 and redirect output for all typing tests."""
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


class TestTypewriter:
    async def test_completes_without_error(self):
        await typewriter("hello world")

    async def test_empty_string(self):
        await typewriter("")

    async def test_custom_speed_no_crash(self):
        await typewriter("test", speed=0.001)

    async def test_multiline(self):
        await typewriter("line1\nline2\nline3")


class TestTypewriterFast:
    async def test_completes(self):
        await typewriter_fast("fast output text")

    async def test_empty(self):
        await typewriter_fast("")


class TestDramaticPause:
    async def test_instant_at_zero_speed(self):
        # speed_multiplier=0 → returns immediately
        await dramatic_pause(1.0)

    async def test_disabled_returns_immediately(self):
        fx.config.enabled = False
        await dramatic_pause(5.0)  # would be very slow if not skipped

    async def test_zero_seconds(self):
        await dramatic_pause(0.0)


class TestRedactedText:
    async def test_returns_string(self):
        result = await redacted_text("the quick brown fox")
        assert isinstance(result, str)

    async def test_zero_redact_pct_unchanged(self):
        text = "the quick brown fox jumps"
        result = await redacted_text(text, redact_pct=0.0)
        assert result == text

    async def test_full_redact_all_long_words(self):
        text = "hello world testing"
        result = await redacted_text(text, redact_pct=1.0)
        # All 3-char+ words should be [REDACTED]
        assert "[REDACTED]" in result

    async def test_short_words_not_redacted(self):
        # Words shorter than 3 chars never get redacted
        text = "hi I am"
        result = await redacted_text(text, redact_pct=1.0)
        assert "hi" in result
        assert "I" in result

    async def test_empty_string(self):
        result = await redacted_text("", redact_pct=0.5)
        assert result == ""

    async def test_word_count_preserved(self):
        text = "one two three four five"
        result = await redacted_text(text, redact_pct=0.5)
        assert len(result.split()) == len(text.split())


class TestRevealRedacted:
    async def test_completes_without_error(self):
        original = "the quick brown fox"
        redacted = "the [REDACTED] brown fox"
        await reveal_redacted(original, redacted)

    async def test_disabled_no_crash(self):
        fx.config.enabled = False
        await reveal_redacted("hello world", "[REDACTED] world")

    async def test_no_redacted_words(self):
        await reveal_redacted("hello world", "hello world")
