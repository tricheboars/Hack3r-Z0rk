"""Tutorial command + auto-advance engine."""
from __future__ import annotations

import pytest

from hackerzork.engine.command_registry import CommandContext
from hackerzork.systems.events import EventBus
from hackerzork.systems.state import GameState
from hackerzork.commands.tutorial import (
    STEPS,
    TutorialEngine,
    cmd_tutorial,
)


@pytest.fixture()
def setup():
    events = EventBus()
    state = GameState(events=events)
    eng = TutorialEngine(state=state, events=events)
    ctx = CommandContext(state=state, events=events, tutorial=eng)
    return ctx, state, events, eng


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestStartStatusReset:
    def test_status_when_inactive(self, setup):
        ctx, *_ = setup
        out = cmd_tutorial(ctx, [])
        assert "tutorial start" in out.lower()

    def test_start_sets_step_1(self, setup):
        ctx, state, *_ = setup
        out = cmd_tutorial(ctx, ["start"])
        assert state.tutorial_step == 1
        assert "step 1" in out.lower()

    def test_status_shows_current_step(self, setup):
        ctx, state, *_ = setup
        cmd_tutorial(ctx, ["start"])
        out = cmd_tutorial(ctx, ["status"])
        assert "step 1" in out.lower()

    def test_reset_clears_progress(self, setup):
        ctx, state, *_ = setup
        cmd_tutorial(ctx, ["start"])
        cmd_tutorial(ctx, ["reset"])
        assert state.tutorial_step == 0


# ---------------------------------------------------------------------------
# Skip
# ---------------------------------------------------------------------------

class TestSkip:
    def test_skip_advances_step(self, setup):
        ctx, state, *_ = setup
        cmd_tutorial(ctx, ["start"])
        cmd_tutorial(ctx, ["skip"])
        assert state.tutorial_step == 2

    def test_next_alias(self, setup):
        ctx, state, *_ = setup
        cmd_tutorial(ctx, ["start"])
        cmd_tutorial(ctx, ["next"])
        assert state.tutorial_step == 2


# ---------------------------------------------------------------------------
# Auto-advance via event bus
# ---------------------------------------------------------------------------

class TestAutoAdvance:
    def _emit_command(self, events, raw: str) -> None:
        cmd_name = raw.split()[0] if raw else ""
        events.emit("command_entered", cmd=cmd_name, raw_input=raw)

    def test_step_1_advances_on_ls_la(self, setup):
        ctx, state, events, eng = setup
        cmd_tutorial(ctx, ["start"])
        self._emit_command(events, "ls -la")
        assert state.tutorial_step == 2
        # Pending message queued for the shell
        assert eng.pending_message != ""

    def test_consume_pending_clears_it(self, setup):
        ctx, state, events, eng = setup
        cmd_tutorial(ctx, ["start"])
        self._emit_command(events, "ls -la")
        msg = eng.consume_pending()
        assert msg != ""
        assert eng.consume_pending() == ""

    def test_pipe_step_recognizes_pipe_input(self, setup):
        ctx, state, events, eng = setup
        # Jump to the pipe step (step 5)
        state.tutorial_step = 5
        self._emit_command(events, "ps aux | grep sk_")
        assert state.tutorial_step == 6

    def test_redirect_step_recognizes_redirect(self, setup):
        ctx, state, events, eng = setup
        state.tutorial_step = 6  # redirect step
        self._emit_command(events, "echo hi > /home/user/notes/leads.txt")
        assert state.tutorial_step == 7

    def test_chmod_step_only_advances_for_lockdown_modes(self, setup):
        ctx, state, events, eng = setup
        state.tutorial_step = 7   # chmod step
        # Wrong mode — shouldn't advance
        self._emit_command(events, "chmod 644 /tmp/x")
        assert state.tutorial_step == 7
        # 700 — should advance
        self._emit_command(events, "chmod 700 /tmp/x")
        assert state.tutorial_step == 8

    def test_nmap_sv_step_requires_sv_flag(self, setup):
        ctx, state, events, eng = setup
        state.tutorial_step = 9   # -sV step
        self._emit_command(events, "nmap 10.13.37.1")
        assert state.tutorial_step == 9   # bare nmap doesn't satisfy
        self._emit_command(events, "nmap -sV 10.13.37.1")
        assert state.tutorial_step == 10

    def test_completing_last_step_marks_done(self, setup):
        ctx, state, events, eng = setup
        state.tutorial_step = len(STEPS)   # last step
        self._emit_command(events, "exploit -p 80 -e CVE-XXX 10.13.37.1")
        # State goes to -1 (done)
        assert state.tutorial_step == -1


# ---------------------------------------------------------------------------
# Persistence via GameState serialization
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_tutorial_step_round_trips_through_save(self):
        s = GameState()
        s.tutorial_step = 4
        snap = s.to_dict()

        restored = GameState()
        restored.load_state(snap)
        assert restored.tutorial_step == 4

    def test_done_state_round_trips(self):
        s = GameState()
        s.tutorial_step = -1
        restored = GameState()
        restored.load_state(s.to_dict())
        assert restored.tutorial_step == -1


# ---------------------------------------------------------------------------
# Unknown subcommand
# ---------------------------------------------------------------------------

class TestUnknownSub:
    def test_unknown_subcommand_returns_usage(self, setup):
        ctx, *_ = setup
        out = cmd_tutorial(ctx, ["nope"])
        assert "unknown" in out.lower() or "usage" in out.lower()
