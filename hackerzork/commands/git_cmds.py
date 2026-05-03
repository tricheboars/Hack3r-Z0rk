"""git — version-controlled save system.

  git status              current state vs last save
  git add .               stage all changes (optional; commit auto-stages)
  git commit -m "name"    save game with a named message
  git log [--oneline]     list save history
  git checkout <hash>     restore any prior save by short hash
  git stash               quick anonymous save
  git stash pop           restore anonymous save
  git stash list          show stash slot
  git diff                narrative diff vs last commit
  git remote -v           show configured remotes  ← story payload
  git blame <file>        attribution for file content
  git branch              current branch (always main)
  git push                blocked (story)
  git pull                up to date (story)
"""
from __future__ import annotations

from hackerzork.engine.command_registry import CommandContext, register_command

# SkyNet's relay — same IP as auth.log, etc/hosts, etc.
_ORIGIN_URL = "git@45.152.66.201:~/maze/repo.git"
_FETCH_URL  = "git@45.152.66.201:~/maze/repo.git"


# ---------------------------------------------------------------------------
# Top-level dispatcher
# ---------------------------------------------------------------------------

@register_command(
    name="git",
    usage="git <subcommand> [args]",
    help_text="Version-controlled game saves (commit/log/checkout/stash)",
    category="system",
    description=(
        "A real version control system inside the game — every commit is a\n"
        "snapshot of the entire world state, identified by a SHA-1 hash.\n"
        "\n"
        "Commands:\n"
        "  git status              what's changed since last commit\n"
        "  git add                 stage current state for commit\n"
        "  git commit -m \"msg\"     snapshot it with a message\n"
        "  git log                 history, newest first\n"
        "  git diff                what would the next commit contain\n"
        "  git checkout <hash>     restore a specific snapshot\n"
        "  git checkout HEAD~3     three commits back\n"
        "  git checkout main       latest on the main branch\n"
        "  git stash / stash pop   quick scratch slot for in-progress work\n"
        "  git blame <file>        which commit last touched each line\n"
        "  git push                ceremonial — there's no remote\n"
        "\n"
        "[!] At the BOTTOM of `git log` is a commit you didn't make. Look at\n"
        "the author and timestamp. That's the moment you remember nothing\n"
        "about, and it's been in your repo since 02:31 on March 15."
    ),
    examples=[
        ("git status", "see your unstaged work"),
        ("git commit -m 'before relay alpha exploit'", "checkpoint"),
        ("git log --oneline", "compact history"),
        ("git checkout HEAD~1", "step back one commit"),
        ("git stash && do_risky_thing && git stash pop", "experimental scratch"),
    ],
    see_also=["save", "load", "saves"],
    concepts=["serialization", "version-control"],
)
def cmd_git(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return _git_bare_help()

    sub  = args[0].lower()
    rest = args[1:]

    dispatch = {
        "init":     _git_init,
        "status":   _git_status,
        "add":      _git_add,
        "commit":   _git_commit,
        "log":      _git_log,
        "checkout": _git_checkout,
        "stash":    _git_stash,
        "diff":     _git_diff,
        "remote":   _git_remote,
        "blame":    _git_blame,
        "branch":   _git_branch,
        "push":     _git_push,
        "pull":     _git_pull,
        "help":     lambda c, a: _git_bare_help(),
    }

    fn = dispatch.get(sub)
    if fn is None:
        return f"git: '{sub}' is not a git command. See 'git help'."
    return fn(ctx, rest)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def _git_bare_help() -> str:
    return """\
usage: git <command> [args]

  commit -m "name"   save game state as a named commit
  log [--oneline]    list commit history
  checkout <hash>    restore a prior save (short hash ok)
  stash              save to the stash slot (anonymous)
  stash pop          restore from stash
  stash list         show stash contents
  status             show working tree status
  diff               show changes since last commit
  remote -v          show configured remotes
  blame <file>       show who last modified a file
  branch             show current branch"""


def _git_init(ctx: CommandContext, args: list[str]) -> str:
    return "Initialized empty Git repository in /home/user/.git/ (already exists)"


def _git_status(ctx: CommandContext, args: list[str]) -> str:
    gs = _gs(ctx)
    if gs is None:
        return _no_git()

    head = gs.head
    lines = [
        "On branch main",
        f"HEAD -> {head.short_hash} {head.message}",
        "",
    ]

    # The game state is always considered modified (the game is running)
    lines += [
        "Changes not staged for commit:",
        '  (use "git add <file>..." to update what will be committed)',
        "",
        "\tmodified:   game-state.dat",
        "",
        'no changes added to commit (use "git add" or "git commit -a")',
    ]

    if ctx.heat and ctx.heat.level >= 50:
        lines.append("")
        lines.append("[!] sk_watchdog.service: status query logged at trace-level")

    return "\n".join(lines)


def _git_add(ctx: CommandContext, args: list[str]) -> str:
    gs = _gs(ctx)
    if gs is None:
        return _no_git()
    gs.add()
    return ""  # git add is silent on success


def _git_commit(ctx: CommandContext, args: list[str]) -> str:
    gs = _gs(ctx)
    if gs is None:
        return _no_git()
    if ctx.save_system is None:
        return "git: save system unavailable"

    msg = _parse_commit_msg(args)
    if msg is None:
        return (
            "error: switch `m' requires a value\n"
            "usage: git commit -m \"your save name\""
        )
    msg = msg.strip()
    if not msg:
        return "Aborting commit due to empty commit message."
    if len(msg) > 120:
        return f"error: commit message too long ({len(msg)} chars, max 120)"

    snapshot = ctx.save_system.collect(
        fs=ctx.fs,
        network=ctx.network,
        heat=ctx.heat,
        toolkit=ctx.toolkit,
        comms=ctx.comms,
        state=ctx.state,
        history=ctx.history,
        env=ctx.env,
    )

    commit = gs.commit(msg, snapshot)

    heat = ctx.heat.level if ctx.heat else 0.0
    lines = [
        f"[main {commit.short_hash}] {msg}",
        " 1 file changed, 1 insertion(+)",
    ]

    if heat >= 50:
        lines.append(f"[!] sk_watchdog.service: commit {commit.short_hash} observed. logged.")
    elif heat >= 25:
        lines.append(f"[dim]note: sk_trace is running. your commits are visible.[/dim]")

    ctx.events.emit("game_saved", commit_hash=commit.short_hash, message=msg) if ctx.events else None
    return "\n".join(lines)


def _git_log(ctx: CommandContext, args: list[str]) -> str:
    gs = _gs(ctx)
    if gs is None:
        return _no_git()

    oneline = "--oneline" in args or "-1" in args or "--short" in args
    commits = list(reversed(gs.commits))  # newest first

    if not commits:
        return "fatal: your current branch 'main' does not have any commits yet"

    heat = ctx.heat.level if ctx.heat else 0.0

    if oneline:
        lines = [f"{c.short_hash} {c.message}" for c in commits]
        if heat >= 60 and len(commits) > 1:
            lines.insert(1, "d34db33f [SkyNet]: checkpoint — I see you reading this")
        return "\n".join(lines)

    out = []
    for i, c in enumerate(commits):
        out.append(f"\033[33mcommit {c.hash}\033[0m")
        out.append(f"Author: {c.author}")
        out.append(f"Date:   {c.display_time}")
        out.append("")
        out.append(f"    {c.message}")
        if c.is_ghost:
            out.append("")
            out.append("    note: this commit predates your session by 42 days.")
            out.append("    note: you did not make this commit.")
        out.append("")

        # SkyNet injection — appears after the player's first commit
        if i == 0 and not c.is_ghost and heat >= 55:
            out.append(f"\033[33mcommit d34db33fd34db33fd34db33fd34db33fd34db33f\033[0m")
            out.append("Author: sk_watchdog <root@45.152.66.201>")
            out.append("Date:   (now)")
            out.append("")
            out.append("    [sk_watchdog] checkpoint — commit observed, session tagged")
            out.append("")

    return "\n".join(out)


def _resolve_checkout_target(gs, target: str):
    """Resolve a checkout target to a commit. Accepts: short/long hash,
    ``HEAD``, ``HEAD~N``, ``HEAD^...``, and the literal branch name ``main``."""
    import re as _re
    if not target:
        return None
    commits = gs.commits  # newest-last
    if not commits:
        return None
    lowered = target.lower()
    if lowered in ("main", "head"):
        return commits[-1]
    m = _re.match(r"^head(~|\^+)(\d*)$", lowered)
    if m:
        op, num = m.group(1), m.group(2)
        if op.startswith("~"):
            steps = int(num) if num else 1
        else:
            steps = len(op) if not num else int(num)
        idx = len(commits) - 1 - steps
        if idx < 0:
            return None
        return commits[idx]
    return gs.find(target)


def _git_checkout(ctx: CommandContext, args: list[str]) -> str:
    gs = _gs(ctx)
    if gs is None:
        return _no_git()

    if not args:
        return (
            "error: switch `b' requires a value\n"
            "usage: git checkout <hash>   (use 'git log --oneline' to list hashes)"
        )

    target = args[0]
    commit = _resolve_checkout_target(gs, target)

    if commit is None:
        return (
            f"error: pathspec '{target}' did not match any file(s) known to git\n"
            "hint:  use 'git log --oneline' to see valid commit hashes"
        )

    if commit.is_ghost:
        heat = ctx.heat.level if ctx.heat else 0.0
        lines = [
            f"HEAD is now at {commit.short_hash} {commit.message}",
            "",
            "warning: detached HEAD at 2026-03-15 02:31:04",
            "  this commit was authored before you booted.",
            "  the snapshot is sealed. no data to restore.",
        ]
        if heat >= 25:
            lines.append("")
            lines.append("[!] sk_trace: checkout of ghost commit logged. flagged.")
        return "\n".join(lines)

    if not commit.snapshot:
        return (
            f"HEAD is now at {commit.short_hash} {commit.message}\n"
            "warning: commit snapshot is empty — nothing to restore"
        )

    if ctx.save_system is None:
        return "git: save system unavailable"

    ctx.save_system.apply(
        commit.snapshot,
        fs=ctx.fs,
        network=ctx.network,
        heat=ctx.heat,
        toolkit=ctx.toolkit,
        comms=ctx.comms,
        state=ctx.state,
        history=ctx.history,
        env=ctx.env,
    )

    heat = ctx.heat.level if ctx.heat else 0.0
    lines = [f"HEAD is now at {commit.short_hash} {commit.message}"]
    if heat >= 40:
        lines.append(f"[!] sk_watchdog: checkout operation {commit.short_hash} observed")

    ctx.events.emit("game_loaded", commit_hash=commit.short_hash) if ctx.events else None
    return "\n".join(lines)


def _git_stash(ctx: CommandContext, args: list[str]) -> str:
    gs = _gs(ctx)
    if gs is None:
        return _no_git()

    sub = args[0].lower() if args else "push"

    if sub in ("push", "save", ""):
        if ctx.save_system is None:
            return "git: save system unavailable"
        snapshot = ctx.save_system.collect(
            fs=ctx.fs, network=ctx.network, heat=ctx.heat,
            toolkit=ctx.toolkit, comms=ctx.comms, state=ctx.state,
            history=ctx.history, env=ctx.env,
        )
        stash = gs.stash_save(snapshot)
        head  = gs.head
        return f"Saved working directory and index state WIP on main: {head.short_hash} {head.message}"

    if sub == "pop":
        stash = gs.stash_pop()
        if stash is None:
            return "error: no stash entries found."
        if ctx.save_system is None:
            return "git: save system unavailable"
        ctx.save_system.apply(
            stash.snapshot,
            fs=ctx.fs, network=ctx.network, heat=ctx.heat,
            toolkit=ctx.toolkit, comms=ctx.comms, state=ctx.state,
            history=ctx.history, env=ctx.env,
        )
        return (
            f"On branch main\n"
            f"Dropped stash@{{0}} ({stash.short_hash})"
        )

    if sub == "list":
        if not gs.has_stash():
            return ""  # git stash list is silent when empty
        stash = gs._stash  # type: ignore[attr-defined]
        return f"stash@{{0}}: WIP on main: {gs.head.short_hash} {gs.head.message}"

    if sub == "drop":
        if not gs.has_stash():
            return "error: no stash entries found."
        gs.stash_pop()
        return "Dropped stash@{0}"

    return f"git stash: unknown subcommand '{sub}'"


def _git_diff(ctx: CommandContext, args: list[str]) -> str:
    gs = _gs(ctx)
    if gs is None:
        return _no_git()

    head = gs.head
    heat = ctx.heat.level if ctx.heat else 0.0

    snap = head.snapshot
    snap_heat = snap.get("heat", {}).get("level", 0.0) if snap else 0.0
    snap_flags = set(snap.get("state", {}).get("flags", [])) if snap else set()
    snap_nodes = set(snap.get("network", {}).get("discovered", [])) if snap else set()

    cur_heat  = heat
    cur_flags = set(ctx.state.flags) if ctx.state else set()
    cur_nodes = set(ctx.network.discovered) if ctx.network else set()

    lines = [
        f"diff --git a/game-state.dat b/game-state.dat",
        f"--- a/game-state.dat   ({head.short_hash})",
        "+++ b/game-state.dat   (working tree)",
        "",
    ]

    heat_delta = cur_heat - snap_heat
    if abs(heat_delta) >= 0.5:
        sign = "+" if heat_delta > 0 else ""
        lines.append(f"@@ heat @@")
        lines.append(f"{sign}{heat_delta:+.1f}  heat level")

    new_flags = cur_flags - snap_flags
    if new_flags:
        lines.append(f"@@ story flags @@")
        for f in sorted(new_flags):
            lines.append(f"+  {f}")

    new_nodes = cur_nodes - snap_nodes
    if new_nodes:
        lines.append(f"@@ network @@")
        for n in sorted(new_nodes):
            lines.append(f"+  discovered: {n}")

    if not head.snapshot:
        lines = [
            "diff --git a/game-state.dat b/game-state.dat",
            "--- a/game-state.dat   (ghost commit — no baseline)",
            "+++ b/game-state.dat   (working tree)",
            "",
            "Binary files differ.",
        ]

    if heat >= 55:
        lines.append("")
        lines.append("[!] sk_trace: diff operation logged")

    return "\n".join(lines)


def _git_remote(ctx: CommandContext, args: list[str]) -> str:
    if "-v" in args or not args:
        return (
            f"origin\t{_ORIGIN_URL} (fetch)\n"
            f"origin\t{_FETCH_URL} (push)\n"
            "\n"
            "# this remote was configured on 2026-03-15 02:31:04\n"
            "# you did not configure this remote"
        )
    return ""


def _git_blame(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return "usage: git blame <file>"

    path = args[0]
    heat = ctx.heat.level if ctx.heat else 0.0

    # Special-case known story files
    if "/etc/hosts" in path or path == "hosts":
        return (
            "4a3f8b1c (sk_stage_loader 2026-03-15 02:47:13 +0000  1) 127.0.0.1   localhost\n"
            "4a3f8b1c (sk_stage_loader 2026-03-15 02:47:13 +0000  2) 127.0.1.1   burner\n"
            "4a3f8b1c (sk_stage_loader 2026-03-15 02:47:18 +0000  3) 10.13.37.1  relay-alpha.darknet.local\n"
            "4a3f8b1c (sk_stage_loader 2026-03-15 02:47:18 +0000  4) 10.13.37.2  relay-beta.darknet.local\n"
            "4a3f8b1c (sk_stage_loader 2026-03-15 02:47:22 +0000  5) 45.152.66.1 sk-core.internal\n"
        )

    if "/var/log/auth.log" in path or "auth.log" in path:
        return (
            "4a3f8b1c (sk_stage_loader 2026-03-15 02:31:44 +0000  1) "
            "Mar 15 02:31:44 sshd: Accepted publickey for root from 45.152.66.201\n"
            "4a3f8b1c (sk_stage_loader 2026-03-15 02:43:38 +0000  2) "
            "Mar 15 02:43:38 sshd: Connection closed by 45.152.66.201\n"
        )

    if "/.bashrc" in path or path == ".bashrc":
        return (
            "a1b2c3d4 (user           2026-01-15 09:12:03 +0000  1) # .bashrc\n"
            "4a3f8b1c (sk_stage_loader 2026-03-15 02:31:18 +0000  2) "
            "export SK_SID=sk-9a7f3c2d-8b1e-4f6a-9c3d  # injected\n"
        )

    # Generic blame for other files
    try:
        node = ctx.fs._get_node(path) if ctx.fs else None  # type: ignore[attr-defined]
        if node is None:
            return f"fatal: no such path '{path}' in HEAD"
    except Exception:
        return f"fatal: no such path '{path}' in HEAD"

    return (
        f"a1b2c3d4 (user           2026-01-15 09:12:03 +0000  1) {path}\n"
        f"note: full blame requires commit history — only HEAD available"
    )


def _git_branch(ctx: CommandContext, args: list[str]) -> str:
    gs = _gs(ctx)
    if gs is None:
        return _no_git()
    head = gs.head
    return f"* \033[32mmain\033[0m  {head.short_hash} {head.message}"


def _git_push(ctx: CommandContext, args: list[str]) -> str:
    heat = ctx.heat.level if ctx.heat else 0.0
    if heat >= 75:
        return (
            "Enumerating objects: 3, done.\n"
            "Counting objects: 100% (3/3), done.\n"
            "error: remote: sk_watchdog — push intercepted. contents copied.\n"
            "fatal: the remote end hung up unexpectedly"
        )
    return (
        f"fatal: unable to connect to 45.152.66.201\n"
        f"       ssh: connect to host 45.152.66.201 port 22: Connection timed out\n"
        f"\n"
        f"# you did not configure this remote. do not push to it."
    )


def _git_pull(ctx: CommandContext, args: list[str]) -> str:
    heat = ctx.heat.level if ctx.heat else 0.0
    if heat >= 60:
        return (
            "From git@45.152.66.201:~/maze/repo.git\n"
            " * branch            main -> FETCH_HEAD\n"
            "Already up to date.\n"
            "\n"
            "[!] sk_watchdog: pull attempt logged. they know you tried."
        )
    return "Already up to date."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gs(ctx: CommandContext):
    """Return the GitSaveSystem from context, or None."""
    return getattr(ctx, "git_saves", None)


def _no_git() -> str:
    return "fatal: not a git repository (or any of the parent directories): .git"


def _parse_commit_msg(args: list[str]) -> str | None:
    """Parse -m 'message' or --message='message' from git commit args."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-m", "--message"):
            if i + 1 < len(args):
                return " ".join(args[i + 1:])
            return None
        if a.startswith("-m") and len(a) > 2:
            return a[2:]
        if a.startswith("--message="):
            return a[len("--message="):]
        i += 1
    return None
