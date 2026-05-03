"""learn command — concept page lookup and rendering."""
from __future__ import annotations

import pathlib

import pytest

from hackerzork.engine.command_registry import CommandContext
from hackerzork.commands.learn import cmd_learn, _DATA_DIR, _topics


@pytest.fixture()
def ctx() -> CommandContext:
    return CommandContext()


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class TestIndex:
    def test_no_args_lists_topics(self, ctx):
        out = cmd_learn(ctx, [])
        assert "concept" in out.lower() or "topic" in out.lower()

    def test_index_includes_known_topics(self, ctx):
        out = cmd_learn(ctx, [])
        # These ship with the project
        for t in ("pipes", "permissions", "cves", "ssh-keys"):
            assert t in out, f"topic {t!r} missing from index"


# ---------------------------------------------------------------------------
# Topic lookup
# ---------------------------------------------------------------------------

class TestTopicLookup:
    def test_pipes_page_renders(self, ctx):
        out = cmd_learn(ctx, ["pipes"])
        assert "PIPES" in out or "pipe" in out.lower()
        assert "stdout" in out.lower()

    def test_permissions_page_mentions_octal(self, ctx):
        out = cmd_learn(ctx, ["permissions"])
        assert "octal" in out.lower() or "rwx" in out.lower()
        assert "700" in out and "644" in out

    def test_cves_page_mentions_format(self, ctx):
        out = cmd_learn(ctx, ["cves"])
        assert "CVE" in out
        assert "cvss" in out.lower() or "version" in out.lower()


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

class TestUnknownTopic:
    def test_unknown_returns_helpful_error(self, ctx):
        out = cmd_learn(ctx, ["definitely-not-a-topic"])
        assert "no topic" in out.lower() or "available" in out.lower()

    def test_underscore_to_hyphen_normalization(self, ctx):
        # ssh_keys → ssh-keys
        out = cmd_learn(ctx, ["ssh_keys"])
        assert "SSH" in out or "ssh" in out

    def test_case_insensitive_topic(self, ctx):
        out = cmd_learn(ctx, ["PIPES"])
        assert "stdout" in out.lower()


# ---------------------------------------------------------------------------
# Data integrity — every shipped topic loads
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    def test_data_dir_exists(self):
        assert _DATA_DIR.exists()

    def test_at_least_one_topic_shipped(self):
        topics = _topics()
        assert len(topics) > 0

    def test_every_shipped_topic_renders(self, ctx):
        for t in _topics():
            out = cmd_learn(ctx, [t])
            assert out.strip()  # non-empty
            assert "no topic" not in out.lower()
