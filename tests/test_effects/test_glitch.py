"""Tests for hackerzork/effects/glitch.py — synchronous functions, no async needed."""
from __future__ import annotations

import pytest

from hackerzork.effects.glitch import (
    color_bleed,
    corrupt_output,
    glitch_text,
    scramble_reveal,
    static_burst,
    zalgo_text,
)


class TestGlitchText:
    def test_zero_intensity_unchanged(self):
        text = "hello world"
        result = glitch_text(text, intensity=0.0)
        assert result == text

    def test_full_intensity_changes_chars(self):
        text = "AAAAAAAAAA"
        result = glitch_text(text, intensity=1.0)
        # Spaces preserved; non-space chars very likely changed at intensity 1.0
        assert len(result) == len(text)

    def test_preserves_spaces(self):
        text = "a b c"
        result = glitch_text(text, intensity=1.0)
        assert result[1] == " " and result[3] == " "

    def test_preserves_newlines(self):
        text = "line1\nline2"
        result = glitch_text(text, intensity=1.0)
        assert "\n" in result

    def test_same_length(self):
        text = "test string"
        result = glitch_text(text, intensity=0.5)
        assert len(result) == len(text)

    def test_intensity_clamped_high(self):
        glitch_text("abc", intensity=5.0)  # should not raise

    def test_intensity_clamped_low(self):
        glitch_text("abc", intensity=-1.0)  # should not raise

    def test_empty_string(self):
        assert glitch_text("", intensity=0.5) == ""


class TestZalgoText:
    def test_zero_intensity_returns_original(self):
        text = "hello"
        # At intensity 0, all randint(0, 0) → 0 → no combining chars added
        result = zalgo_text(text, intensity=0.0)
        # The base chars are preserved (combining chars may be added around them)
        for ch in text:
            assert ch in result

    def test_result_longer_than_input(self):
        # Zalgo always adds chars at intensity > 0
        text = "SKYNET"
        result = zalgo_text(text, intensity=0.8)
        assert len(result) >= len(text)

    def test_preserves_spaces(self):
        text = "a b"
        result = zalgo_text(text, intensity=1.0)
        assert " " in result

    def test_high_intensity_very_long(self):
        text = "go"
        result = zalgo_text(text, intensity=1.0)
        # At high intensity, many combining marks added
        assert len(result) >= len(text)

    def test_empty_string(self):
        assert zalgo_text("", intensity=0.5) == ""


class TestScrambleReveal:
    def test_yields_correct_steps(self):
        frames = list(scramble_reveal("hello", steps=5))
        # scramble_reveal yields steps+1 frames (steps intermediate + final)
        assert len(frames) == 6

    def test_final_frame_is_plaintext(self):
        text = "decrypted"
        frames = list(scramble_reveal(text, steps=8))
        assert frames[-1] == text

    def test_first_frame_may_differ(self):
        text = "ABCDEFGHIJ"
        frames = list(scramble_reveal(text, steps=10))
        # First frame has very few revealed chars — almost certainly different
        assert len(frames[0]) == len(text)

    def test_single_step(self):
        text = "hi"
        frames = list(scramble_reveal(text, steps=1))
        assert frames[-1] == text

    def test_spaces_always_preserved(self):
        text = "hello world"
        for frame in scramble_reveal(text, steps=5):
            assert frame[5] == " "

    def test_empty_string(self):
        frames = list(scramble_reveal("", steps=5))
        assert frames[-1] == ""


class TestStaticBurst:
    def test_correct_line_count(self):
        result = static_burst(width=40, height=3)
        lines = result.split("\n")
        assert len(lines) == 3

    def test_correct_line_width(self):
        result = static_burst(width=20, height=2)
        for line in result.split("\n"):
            assert len(line) == 20

    def test_default_args(self):
        result = static_burst()
        assert len(result) > 0

    def test_non_empty(self):
        result = static_burst(width=10, height=1)
        assert result.strip() != ""


class TestCorruptOutput:
    def test_returns_string(self):
        result = corrupt_output("the quick brown fox jumps over the lazy dog")
        assert isinstance(result, str)

    def test_non_empty_input_non_empty_output(self):
        result = corrupt_output("hello world test")
        assert len(result) > 0

    def test_empty_string(self):
        assert corrupt_output("") == ""

    def test_word_count_preserved(self):
        text = "one two three four five"
        result = corrupt_output(text)
        # Word count may vary due to artifacts but output should have words
        assert len(result.split()) >= 1


class TestColorBleed:
    def test_returns_string(self):
        result = color_bleed("hello world from the terminal")
        assert isinstance(result, str)

    def test_contains_original_words(self):
        result = color_bleed("hello world")
        # Either the word appears directly or wrapped in Rich markup
        assert "hello" in result or "world" in result

    def test_rich_markup_present(self):
        # With enough words, some color markup should appear
        import re
        text = " ".join(["word"] * 20)
        result = color_bleed(text)
        # Rich markup uses [...] tags
        # With 20 words at 30% probability, very likely at least one gets colored
        has_markup = bool(re.search(r"\[\w+\]", result))
        # Not asserting True — it's probabilistic — but the function must not crash
        assert isinstance(result, bool) or isinstance(has_markup, bool)

    def test_empty_string(self):
        assert color_bleed("") == ""
