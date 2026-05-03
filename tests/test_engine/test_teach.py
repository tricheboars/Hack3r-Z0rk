"""First-use teaching footer engine."""
from __future__ import annotations

from hackerzork.engine.teach import TeachEngine


# ---------------------------------------------------------------------------
# Fake state with the same has_flag / set_flag interface
# ---------------------------------------------------------------------------

class _FakeState:
    def __init__(self):
        self.flags: set[str] = set()

    def has_flag(self, flag: str) -> bool:
        return flag in self.flags

    def set_flag(self, flag: str) -> None:
        self.flags.add(flag)


class TestTeachFiresOnce:
    def test_chmod_first_use_emits_footer(self):
        eng = TeachEngine(state=_FakeState())
        out = eng.maybe_footer("chmod", ["700", "/tmp/x"])
        assert "octal" in out.lower() or "rwx" in out.lower()
        assert "[ ? ]" in out

    def test_chmod_second_use_silent(self):
        st = _FakeState()
        eng = TeachEngine(state=st)
        first  = eng.maybe_footer("chmod", ["700", "/tmp/x"])
        second = eng.maybe_footer("chmod", ["700", "/tmp/x"])
        assert first   != ""
        assert second  == ""

    def test_persists_via_state_flag(self):
        st = _FakeState()
        eng = TeachEngine(state=st)
        eng.maybe_footer("chmod", ["700", "/tmp/x"])
        assert "taught_chmod" in st.flags


class TestPredicates:
    def test_nmap_sv_specific_footer(self):
        eng = TeachEngine(state=_FakeState())
        out = eng.maybe_footer("nmap", ["-sV", "10.0.0.1"])
        # -sV-specific message
        assert "version" in out.lower()

    def test_plain_nmap_uses_general_footer(self):
        eng = TeachEngine(state=_FakeState())
        out = eng.maybe_footer("nmap", ["10.0.0.1"])
        # General nmap message — mentions ports/SYN/scan
        assert "scan" in out.lower() or "port" in out.lower()

    def test_unknown_command_no_footer(self):
        eng = TeachEngine(state=_FakeState())
        assert eng.maybe_footer("notacommand", []) == ""


class TestNoStateFallback:
    def test_works_without_state(self):
        # In tests / minimal harnesses no GameState exists. Engine should
        # still fire-once via in-memory fallback.
        eng = TeachEngine(state=None)
        first  = eng.maybe_footer("chmod", ["700", "/tmp/x"])
        second = eng.maybe_footer("chmod", ["700", "/tmp/x"])
        assert first != ""
        assert second == ""
