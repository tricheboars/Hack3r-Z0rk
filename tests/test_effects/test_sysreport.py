"""Tests for hackerzork/effects/sysreport.py — the first-boot orientation panel."""
from __future__ import annotations

import io

from rich.console import Console

from hackerzork.effects.sysreport import _threat_bar, render_sysreport


def _render(report) -> str:
    buf = io.StringIO()
    Console(file=buf, width=120, force_terminal=False, color_system=None).print(report)
    return buf.getvalue()


class TestThreatBar:
    def test_label_thresholds(self):
        assert _threat_bar(0)[2] == "NOMINAL"
        assert _threat_bar(24.9)[2] == "NOMINAL"
        assert _threat_bar(25)[2] == "WATCHED"
        assert _threat_bar(50)[2] == "ACTIVE"
        assert _threat_bar(75)[2] == "BURN-IMMINENT"
        assert _threat_bar(100)[2] == "BURN-IMMINENT"

    def test_color_thresholds(self):
        assert _threat_bar(0)[1] == "green"
        assert _threat_bar(30)[1] == "yellow"
        assert _threat_bar(60)[1] == "red"
        assert _threat_bar(95)[1] == "bright_red"

    def test_bar_fill_proportional(self):
        assert _threat_bar(0)[0] == "░" * 10
        assert _threat_bar(100)[0] == "█" * 10
        assert _threat_bar(50)[0].count("█") == 5

    def test_bar_clamps_negative_and_overflow(self):
        assert _threat_bar(-10)[0] == "░" * 10
        assert _threat_bar(250)[0] == "█" * 10


class TestRenderSysreport:
    def test_orientation_keywords_present(self):
        out = _render(render_sysreport())
        assert "help" in out
        assert "tutorial" in out
        assert "hint" in out
        assert "learn" in out

    def test_default_contact_awaiting(self):
        out = _render(render_sysreport())
        assert "awaiting signal" in out

    def test_contact_named_when_provided(self):
        out = _render(render_sysreport(contact="Z0RK-7  ·  [ secure ]"))
        assert "Z0RK-7" in out
        assert "awaiting signal" not in out

    def test_heat_value_displayed(self):
        out = _render(render_sysreport(heat=42))
        assert "42 / 100" in out
        assert "WATCHED" in out

    def test_heat_zero_shows_nominal(self):
        out = _render(render_sysreport(heat=0))
        assert "NOMINAL" in out
        assert "00 / 100" in out

    def test_heat_high_shows_burn_imminent(self):
        out = _render(render_sysreport(heat=92))
        assert "BURN-IMMINENT" in out

    def test_evidence_default_singular(self):
        out = _render(render_sysreport())
        assert "1 sealed container" in out
        assert "encrypted" in out

    def test_evidence_custom_string(self):
        out = _render(render_sysreport(evidence="3 dead-drop fragments"))
        assert "3 dead-drop fragments" in out

    def test_footer_contains_breach_timestamp(self):
        out = _render(render_sysreport())
        assert "02:31" in out
        assert "45.152.66.201" in out

    def test_panel_frame_renders(self):
        out = _render(render_sysreport())
        assert "╔" in out
        assert "╚" in out
