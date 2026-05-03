"""tutorial command — guided multi-step walkthrough.

The tutorial is a stateful, event-driven concept tour. Each step teaches one
idea (looking around, pipes, redirects, permissions, port scanning, CVEs)
and watches the event bus. When the player actually performs the step's
target action, the tutorial auto-advances and the next step's lesson appears
on the next prompt.

Tutorial state lives on ``GameState.tutorial_step``:
  0   not started
  N   on step N (1-indexed)
  -1  completed

State persists across save/load via GameState.to_dict / load_state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hackerzork.engine.command_registry import CommandContext, register_command


# ---------------------------------------------------------------------------
# Step definition
# ---------------------------------------------------------------------------

@dataclass
class TutorialStep:
    title: str
    teach: str          # multi-line lesson text
    goal: str           # one-line "do this"
    # Predicate that returns True when the step's goal has been satisfied.
    # Receives the command name + argv from a `command_entered` event.
    check: Callable[[str, list[str]], bool]


# ---------------------------------------------------------------------------
# Predicate helpers
# ---------------------------------------------------------------------------

def _ls_long_or_all(cmd: str, argv: list[str]) -> bool:
    if cmd != "ls":
        return False
    long_flags = {"-l", "-la", "-al", "-a", "-A", "-lh", "-lah"}
    return any(a in long_flags for a in argv)


def _cat_path(target: str) -> Callable[[str, list[str]], bool]:
    def check(cmd: str, argv: list[str]) -> bool:
        if cmd != "cat":
            return False
        # Allow either absolute or the basename match for tilde / relative use
        return any(a == target or a.endswith(target.split("/")[-1]) for a in argv)
    return check


def _recover_anything(cmd: str, argv: list[str]) -> bool:
    return cmd == "recover" and len(argv) >= 1


def _pipe_with_grep(cmd: str, argv: list[str]) -> bool:
    # `command_entered` carries the FIRST stage's name only; we need to detect
    # pipes via the raw input (passed as argv[-1]==... won't work here).
    # We look at the raw input via a sentinel set in tutorial.observe().
    return False  # handled specially in observe()


def _redirect_to_home(cmd: str, argv: list[str]) -> bool:
    return False  # handled specially in observe()


def _chmod_lockdown(cmd: str, argv: list[str]) -> bool:
    if cmd != "chmod":
        return False
    locked = {"600", "700", "0600", "0700"}
    return any(a in locked for a in argv)


def _nmap_any(cmd: str, argv: list[str]) -> bool:
    return cmd == "nmap" and any(not a.startswith("-") for a in argv)


def _nmap_sv(cmd: str, argv: list[str]) -> bool:
    return cmd == "nmap" and "-sV" in argv


def _exploit_cmd(cmd: str, argv: list[str]) -> bool:
    return cmd == "exploit" and "-p" in argv and "-e" in argv


# ---------------------------------------------------------------------------
# The tour
# ---------------------------------------------------------------------------

STEPS: list[TutorialStep] = [
    TutorialStep(
        title="Wake up. Look around.",
        teach=(
            "You just booted a laptop that was sealed for 42 days.\n"
            "Step one of any incident response: see what's on the box.\n"
            "\n"
            "Files starting with '.' are HIDDEN by Unix convention — that's where\n"
            "shells store config, ssh keys, history, and other state. `ls` skips\n"
            "them by default; `-a` shows them. `-l` switches to long format\n"
            "(perms / owner / size / modified)."
        ),
        goal="Run:  ls -la",
        check=_ls_long_or_all,
    ),
    TutorialStep(
        title="Read the field notes you left yourself.",
        teach=(
            "The evidence/ folder you set up before disappearing has a README.\n"
            "Past-you wrote it for present-you. `cat` prints a file to the screen."
        ),
        goal="Run:  cat evidence/README.md",
        check=_cat_path("/home/user/evidence/README.md"),
    ),
    TutorialStep(
        title="Check the auth log.",
        teach=(
            "/var/log/auth.log records every login attempt. If someone got in\n"
            "while you were away, it's recorded here unless they wiped it.\n"
            "Look for unfamiliar IPs and timestamps that contradict the boot log."
        ),
        goal="Run:  cat /var/log/auth.log",
        check=_cat_path("/var/log/auth.log"),
    ),
    TutorialStep(
        title="Recover what they tried to delete.",
        teach=(
            "When you `rm` a file, the directory entry is unlinked but the\n"
            "data sits on disk until something else overwrites the blocks.\n"
            "Forensic tools (and this shell's trash) recover from that state.\n"
            "\n"
            "An attacker in a hurry rarely shreds — they `rm` and run. List\n"
            "what's recoverable with bare `recover`, then restore by path."
        ),
        goal="Run:  recover           (then)  recover /home/user/tools/exfil.py",
        check=_recover_anything,
    ),
    TutorialStep(
        title="Compose tools with PIPES.",
        teach=(
            "The pipe `|` connects one program's stdout to the next program's\n"
            "stdin. This is the Unix philosophy: small tools, glued together.\n"
            "\n"
            "    ps aux | grep sk_     # list all processes, keep only sk_*\n"
            "\n"
            "ps lists processes; grep filters lines matching a pattern.\n"
            "Together they answer 'is SkyNet watching me right now?'"
        ),
        goal="Run:  ps aux | grep sk_",
        check=_pipe_with_grep,
    ),
    TutorialStep(
        title="REDIRECT output into a file.",
        teach=(
            "  >  writes stdout to a file (overwrite)\n"
            "  >> appends instead\n"
            "\n"
            "    echo 'lead: 45.152.66.201' > notes/leads.txt\n"
            "    date >> notes/leads.txt\n"
            "\n"
            "Anything that prints to stdout can be redirected — including the\n"
            "output of `cat`, `grep`, `find`. This is how you build evidence."
        ),
        goal="Run:  echo 'lead: 45.152.66.201' > notes/leads.txt",
        check=_redirect_to_home,
    ),
    TutorialStep(
        title="Lock down a sensitive file.",
        teach=(
            "Unix permissions are three triplets — owner / group / other —\n"
            "each a sum of read=4, write=2, execute=1. So 700 = full access\n"
            "for you, NOTHING for anyone else. Use it on secrets.\n"
            "\n"
            "ssh refuses to use a private key that is group/world-readable;\n"
            "660 keys won't authenticate. 600 always does."
        ),
        goal="Run:  chmod 700 notes/leads.txt        (or any 600/700 chmod)",
        check=_chmod_lockdown,
    ),
    TutorialStep(
        title="Scan the network.",
        teach=(
            "nmap probes a target's TCP/UDP ports and tells you what's\n"
            "listening. You already know one IP from the auth.log:\n"
            "45.152.66.201 SSHed in on March 15. The relay node 10.13.37.1\n"
            "is the first hop into the underground network."
        ),
        goal="Run:  nmap 10.13.37.1",
        check=_nmap_any,
    ),
    TutorialStep(
        title="Fingerprint the SERVICES — that's where CVEs live.",
        teach=(
            "A bare nmap tells you 'tcp/22 is open'. -sV makes nmap speak the\n"
            "actual protocol and parse the banner — now you know it's\n"
            "'OpenSSH 8.9'. Versions are how you look up CVEs.\n"
            "\n"
            "Slower than -sS, louder, but vastly more useful."
        ),
        goal="Run:  nmap -sV 10.13.37.1",
        check=_nmap_sv,
    ),
    TutorialStep(
        title="Exploit a known vulnerability.",
        teach=(
            "Every CVE is a specific bug. If the version on the wire matches a\n"
            "vulnerable version, you can use the published exploit:\n"
            "\n"
            "    exploit -p PORT -e CVE-XXXX-YYYY <target>\n"
            "\n"
            "The previous step gave you a port and a CVE on relay-alpha.\n"
            "Try one. (Failed exploits add MORE heat than successful ones.)"
        ),
        goal="Run:  exploit -p PORT -e CVE TARGET   (use what nmap -sV found)",
        check=_exploit_cmd,
    ),
]


_FINAL_TEXT = (
    "[bold green][TUTORIAL COMPLETE][/bold green]\n"
    "\n"
    "You now know the loop: look around → recover → enumerate → exploit.\n"
    "\n"
    "Where to go next:\n"
    "  [cyan]hint[/cyan]                 — story-aware nudge if you're stuck\n"
    "  [cyan]learn pipes[/cyan]          — concept page on shell pipelines\n"
    "  [cyan]learn cves[/cyan]           — what CVEs are and how to read them\n"
    "  [cyan]learn permissions[/cyan]    — Unix mode bits, deeply\n"
    "  [cyan]man <command>[/cyan]        — every command has one\n"
    "  [cyan]<command> --help[/cyan]     — quick usage block\n"
    "  [cyan]irc list[/cyan]             — there are people in there\n"
    "  [cyan]msg list[/cyan]             — and someone is trying to reach you"
)


# ---------------------------------------------------------------------------
# Engine — wired into the shell at boot
# ---------------------------------------------------------------------------

class TutorialEngine:
    """Subscribes to command_entered, advances tutorial step, queues messages."""

    def __init__(self, state: Any, events: Any = None) -> None:
        self.state = state
        self._events = events
        self.pending_message: str = ""
        if events is not None:
            events.on("command_entered", self._on_command)

    # --- public ---------------------------------------------------------

    def is_active(self) -> bool:
        return self.state is not None and getattr(self.state, "tutorial_step", 0) >= 1

    def is_done(self) -> bool:
        return self.state is not None and getattr(self.state, "tutorial_step", 0) == -1

    def current(self) -> TutorialStep | None:
        if not self.is_active():
            return None
        idx = self.state.tutorial_step - 1
        if idx >= len(STEPS):
            return None
        return STEPS[idx]

    def start(self) -> str:
        if self.state is None:
            return "[tutorial] No game state available."
        self.state.tutorial_step = 1
        return self._render(STEPS[0], step_num=1)

    def reset(self) -> str:
        if self.state is not None:
            self.state.tutorial_step = 0
            self.pending_message = ""
        return "[tutorial] Reset. Run 'tutorial start' to begin again."

    def skip(self) -> str:
        if not self.is_active():
            return "[tutorial] Not active. Run 'tutorial start'."
        self._advance(reason="skipped")
        cur = self.current()
        if cur is None:
            return self._finish()
        return self._render(cur, step_num=self.state.tutorial_step)

    def show(self) -> str:
        if self.is_done():
            return _FINAL_TEXT
        cur = self.current()
        if cur is None:
            return (
                "[tutorial] Not active.\n"
                "  tutorial start    — begin the walkthrough\n"
                "  tutorial status   — current step\n"
                "  tutorial skip     — jump to the next step\n"
                "  tutorial reset    — back to the beginning"
            )
        return self._render(cur, step_num=self.state.tutorial_step)

    def consume_pending(self) -> str:
        msg = self.pending_message
        self.pending_message = ""
        return msg

    # --- internal -------------------------------------------------------

    def _on_command(self, event: Any) -> None:
        if not self.is_active():
            return
        cur = self.current()
        if cur is None:
            return
        cmd = event.data.get("cmd", "")
        raw = event.data.get("raw_input", "")
        argv = raw.split() if raw else []

        # Special handling for predicates that need to look at the RAW input
        # (pipes and redirects don't show up in the cmd name alone).
        idx = self.state.tutorial_step - 1
        satisfied = False
        if idx == 4:                       # PIPES
            satisfied = ("|" in raw) and ("grep" in argv)
        elif idx == 5:                     # REDIRECTS
            satisfied = (">" in raw or ">>" in raw) and (
                "/home/user" in raw or "notes/" in raw or "~/" in raw
            )
        else:
            try:
                satisfied = cur.check(cmd, argv)
            except Exception:
                satisfied = False

        if satisfied:
            self._advance(reason="completed")
            nxt = self.current()
            if nxt is None:
                self.pending_message = self._finish()
            else:
                self.pending_message = (
                    "\n[bold green][✓] Step "
                    f"{self.state.tutorial_step - 1} complete.[/bold green]\n\n"
                    + self._render(nxt, step_num=self.state.tutorial_step)
                )

    def _advance(self, *, reason: str) -> None:
        if self.state is None:
            return
        if self.state.tutorial_step >= len(STEPS):
            self._finish()
            return
        self.state.tutorial_step += 1

    def _finish(self) -> str:
        if self.state is not None:
            self.state.tutorial_step = -1
        return _FINAL_TEXT

    def _render(self, step: TutorialStep, *, step_num: int) -> str:
        total = len(STEPS)
        return (
            f"[bold cyan]── TUTORIAL  step {step_num}/{total} "
            f"─ {step.title} ──[/bold cyan]\n\n"
            f"{step.teach}\n\n"
            f"[bold yellow]>>[/bold yellow] {step.goal}\n"
            f"[dim]   (skip with: tutorial skip   |   stop with: tutorial reset)[/dim]"
        )


# ---------------------------------------------------------------------------
# Command handler
# ---------------------------------------------------------------------------

@register_command(
    name="tutorial",
    usage="tutorial [start|status|next|skip|reset]",
    help_text="Guided multi-step walkthrough teaching shell + hacking concepts",
    category="system",
    description=(
        "A stateful, event-driven concept tour. Each step teaches one idea\n"
        "(looking around, pipes, redirects, permissions, port scanning, CVEs)\n"
        "and watches your shell. When you actually perform the step's goal,\n"
        "the next lesson appears automatically.\n"
        "\n"
        "Subcommands:\n"
        "  tutorial               show the current step (or how to start)\n"
        "  tutorial start         begin from step 1\n"
        "  tutorial status        same as bare 'tutorial'\n"
        "  tutorial skip          jump past the current step\n"
        "  tutorial reset         back to inactive\n"
        "\n"
        "Tutorial progress is saved with `save` / `git commit`. Resuming a\n"
        "save resumes the tutorial wherever you left it."
    ),
    examples=[
        ("tutorial start", "kick off the walkthrough"),
        ("tutorial", "see the current step"),
        ("tutorial skip", "you already know this one"),
    ],
    see_also=["man", "learn", "hint", "help"],
    concepts=["documentation"],
)
def cmd_tutorial(ctx: CommandContext, args: list[str]) -> str:
    eng = _engine(ctx)
    if eng is None:
        return "[tutorial] Tutorial engine not available."

    sub = args[0].lower() if args else "status"
    if sub == "start":
        return eng.start()
    if sub in ("status", "show"):
        return eng.show()
    if sub == "skip" or sub == "next":
        return eng.skip()
    if sub == "reset" or sub == "stop":
        return eng.reset()
    return f"tutorial: unknown subcommand '{sub}'\nUsage: tutorial [start|status|skip|reset]"


def _engine(ctx: CommandContext) -> TutorialEngine | None:
    """Locate the live TutorialEngine attached to ctx (set up by Game.boot)."""
    eng = getattr(ctx, "tutorial", None)
    if eng is not None:
        return eng
    # Fallback: if state + events exist but no engine was bound, build one.
    if ctx.state is not None:
        eng = TutorialEngine(state=ctx.state, events=ctx.events)
        try:
            ctx.tutorial = eng  # type: ignore[attr-defined]
        except Exception:
            pass
        return eng
    return None
