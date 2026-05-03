"""Registry man-page rendering — get_help() with the new educational fields."""
from __future__ import annotations

from hackerzork.engine.command_registry import CommandRegistry


# ---------------------------------------------------------------------------
# Backward compatibility — bare metadata still renders
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_bare_help_still_works(self):
        reg = CommandRegistry()
        reg.register("foo", lambda c, a: "", usage="foo", help_text="does foo", category="x")
        text = reg.get_help("foo")
        assert "foo" in text
        assert "does foo" in text
        assert "x" in text   # category

    def test_unknown_command(self):
        reg = CommandRegistry()
        assert "no help" in reg.get_help("ghost").lower()


# ---------------------------------------------------------------------------
# Full man-page rendering
# ---------------------------------------------------------------------------

class TestRichManPage:
    def setup_method(self):
        self.reg = CommandRegistry()
        self.reg.register(
            "nmap",
            lambda c, a: "",
            usage="nmap [-sV] target",
            help_text="Network scanner",
            category="network",
            description="Scans TCP ports.\nUses SYN by default.",
            examples=[
                ("nmap 10.0.0.1", "default scan"),
                ("nmap -sV 10.0.0.1", "service-version probe"),
            ],
            see_also=["ssh", "exploit"],
            concepts=["port-scanning", "cves"],
        )

    def test_renders_name_section(self):
        text = self.reg.get_help("nmap")
        assert "NAME" in text
        assert "nmap" in text
        assert "Network scanner" in text

    def test_renders_synopsis(self):
        text = self.reg.get_help("nmap")
        assert "SYNOPSIS" in text
        assert "nmap [-sV] target" in text

    def test_renders_description(self):
        text = self.reg.get_help("nmap")
        assert "DESCRIPTION" in text
        assert "Scans TCP ports." in text
        assert "Uses SYN by default." in text

    def test_renders_examples(self):
        text = self.reg.get_help("nmap")
        assert "EXAMPLES" in text
        assert "nmap 10.0.0.1" in text
        assert "default scan" in text
        assert "service-version probe" in text

    def test_renders_see_also(self):
        text = self.reg.get_help("nmap")
        assert "SEE ALSO" in text
        assert "ssh" in text
        assert "exploit" in text

    def test_renders_concepts_as_learn_pointers(self):
        text = self.reg.get_help("nmap")
        assert "LEARN MORE" in text
        assert "learn port-scanning" in text
        assert "learn cves" in text


# ---------------------------------------------------------------------------
# Brief help (--help form)
# ---------------------------------------------------------------------------

class TestBriefHelp:
    def test_brief_help_format(self):
        reg = CommandRegistry()
        reg.register("foo", lambda c, a: "", usage="foo [-x]", help_text="does foo")
        out = reg.get_brief_help("foo")
        assert "foo" in out
        assert "does foo" in out
        assert "foo [-x]" in out
        assert "man foo" in out  # pointer to full page

    def test_brief_help_unknown(self):
        reg = CommandRegistry()
        assert "no help" in reg.get_brief_help("ghost").lower()
