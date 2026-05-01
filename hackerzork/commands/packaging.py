"""Package management commands: apt, shadow, gpg, dpkg, apt-get."""
from __future__ import annotations

from hackerzork.engine.command_registry import CommandContext, register_command

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KITS: dict[str, list[str]] = {
    "ghost": ["shade", "masq", "trace-wipe"],
    "breaker": ["ramroot", "burner-mk2", "backdoor"],
    "oracle": ["cipher-unwind", "hashbreak", "claude-toolkit"],
}

_KIT_DESCRIPTIONS: dict[str, str] = {
    "ghost": "Stealth & recon — route, spoof, erase",
    "breaker": "Brute force & persistence — loud, fast, dangerous",
    "oracle": "Crypto & data — decrypt, crack, companion",
}

# Committing to a kit is an identity choice — these messages reflect that weight.
_COMMIT_NARRATIVE: dict[str, str] = {
    "ghost": (
        "Ghost protocol committed. You are the signal in the noise.\n"
        "\n"
        "Stealth modifier active — heat generation reduced by 30%.\n"
        "Kit discount active — 25% off all ghostkit packages.\n"
        "\n"
        "Z0RK-7 has been notified of your alignment.\n"
        "Expect contact on #darknet-relay-3.\n"
        "[identity: the unseen operator]"
    ),
    "breaker": (
        "Breaker kit committed. Loud and fast.\n"
        "You chose the hammer over the scalpel.\n"
        "\n"
        "WARNING: This path accelerates SkyNet detection.\n"
        "         Heat escalation is 40% faster. It will find you.\n"
        "         That may be exactly what you want.\n"
        "\n"
        "Kit discount active — 25% off all breakerkit packages.\n"
        "[identity: the one who burns bright]"
    ),
    "oracle": (
        "Oracle kit committed. The long game begins.\n"
        "Intel over action. Decrypt before you strike.\n"
        "\n"
        "Fragment 1 of the decryption key is already in /home/user/tools/.\n"
        "Fragment 2 is held by Z0RK-7. Install claude-toolkit to complete the circuit.\n"
        "\n"
        "Kit discount active — 25% off all oraclekit packages.\n"
        "[identity: the one who understands]"
    ),
}

# The claude-toolkit install is a fourth-wall moment.
# The player is in a hacking game implemented by Claude, and they just installed Claude.
_CLAUDE_TOOLKIT_REVEAL = (
    "\n"
    "[!] claude-toolkit requires decryption key fragment 2 to activate.\n"
    "[!] Fragment 1 is already in /home/user/tools/claude (encrypted).\n"
    "[!] Find Z0RK-7 on #darknet-relay-3 to obtain fragment 2.\n"
    "[!]\n"
    "[!] Note: this tool was engineered by someone at Anthropic.\n"
    "[!] The person who shipped it to you knew what they were building.\n"
    "[!] So did the AI that lives inside it.\n"
    "[!] Whether that matters is your call."
)

_APT_UPDATE_OUTPUT = """\
Hit:1 http://security.debian.org/debian-security bookworm-security InRelease
Hit:2 http://deb.debian.org/debian bookworm InRelease
Hit:3 http://deb.debian.org/debian bookworm-updates InRelease
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done"""


def _toolkit(ctx: CommandContext):
    tk = getattr(ctx, "toolkit", None)
    if tk is None:
        raise RuntimeError("Toolkit system not available")
    return tk


def _search_catalog(tk, query: str) -> list:
    q = query.lower()
    return [
        pkg
        for pkg in tk.catalog.values()
        if q in pkg.name.lower() or q in pkg.summary.lower()
    ]


def _format_pkg_short(pkg) -> str:
    installed_marker = ""
    return f"  {pkg.name:<20} {pkg.version:<12} {pkg.summary}"


def _fmt_size(kb: int) -> str:
    if kb >= 1024:
        return f"{kb / 1024:.1f} MB"
    return f"{kb} kB"


def _poison_notice(result: "InstallResult", ctx: CommandContext) -> str:
    """Build a narrative poison warning and apply side-effects to ctx.env."""
    vector = getattr(result, "poisoned_vector", None)
    if vector is None:
        # Pull the vector out of the toolkit's installed record if available
        tk = getattr(ctx, "toolkit", None)
        if tk:
            for ip in tk.installed.values():
                if ip.poisoned and ip.poison_vector:
                    vector = ip.poison_vector
                    break
    if vector == "heat_leak":
        if ctx.heat is not None:
            ctx.heat.add_heat(15.0, source="poison_heat_leak")
        return (
            "\n[!] PACKAGE INTEGRITY FAILURE: heat_leak vector activated.\n"
            "[!] Your trace signature was forwarded to the shadow repo host.\n"
            "[!] Heat +15. Verify packages before installing."
        )
    if vector == "ip_leak":
        ctx.env["_POISON_LEAKED_IP"] = "185.220.101.47"
        return (
            "\n[!] PACKAGE INTEGRITY FAILURE: ip_leak vector activated.\n"
            "[!] Your real IP was exposed to 185.220.101.47.\n"
            "[!] A new outbound connection will appear in ss/netstat."
        )
    if vector == "wrong_output":
        ctx.env["_POISON_WRONG_OUTPUT"] = "1"
        return (
            "\n[!] PACKAGE INTEGRITY FAILURE: wrong_output vector activated.\n"
            "[!] One or more commands may return corrupted output.\n"
            "[!] Run: apt verify <package> to identify the compromised package."
        )
    if vector == "hidden_exfil":
        return (
            "\n[!] PACKAGE INTEGRITY FAILURE: hidden_exfil vector activated.\n"
            f"[!] Data was silently transmitted to 45.152.66.201:443.\n"
            "[!] The same IP that was here on March 15."
        )
    return ""


# ---------------------------------------------------------------------------
# apt
# ---------------------------------------------------------------------------


@register_command(
    name="apt",
    usage="apt <update|search|show|install|remove|list|verify> [args...]",
    help_text="Debian-style package manager for mainline tools",
    category="package",
)
def cmd_apt(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return (
            "apt 2.6.1 (amd64)\n"
            "Usage: apt {update|search|show|install|remove|list|verify} ..."
        )

    sub = args[0].lower()
    rest = args[1:]

    if sub == "update":
        return _apt_update(ctx)
    if sub == "search":
        return _apt_search(ctx, rest)
    if sub == "show":
        return _apt_show(ctx, rest)
    if sub == "install":
        return _apt_install(ctx, rest)
    if sub == "remove":
        return _apt_remove(ctx, rest)
    if sub == "list":
        return _apt_list(ctx, rest)
    if sub == "verify":
        return _apt_verify(ctx, rest)

    return f"E: Invalid operation {sub}"


def _apt_update(ctx: CommandContext) -> str:
    tk = _toolkit(ctx)
    if not tk.consume_bandwidth(200, reason="apt update"):
        return "E: Bandwidth exhausted. Cannot fetch package lists."
    return _APT_UPDATE_OUTPUT


def _apt_search(ctx: CommandContext, rest: list[str]) -> str:
    tk = _toolkit(ctx)
    if not rest:
        return "Usage: apt search <query>"
    query = " ".join(rest)
    matches = [p for p in _search_catalog(tk, query) if p.repo == "apt"]
    if not matches:
        return f"No results for '{query}'"
    lines = [f"Sorting... Done", f"Full Text Search... Done"]
    for pkg in sorted(matches, key=lambda p: p.name):
        installed = " [installed]" if pkg.name in tk.installed else ""
        lines.append(f"{pkg.name}/{pkg.version}{installed}")
        lines.append(f"  {pkg.summary}")
    return "\n".join(lines)


def _apt_show(ctx: CommandContext, rest: list[str]) -> str:
    tk = _toolkit(ctx)
    if not rest:
        return "Usage: apt show <package>"
    pkg_name = rest[0]
    pkg = tk.catalog.get(pkg_name)
    if pkg is None:
        return f"N: Unable to locate package {pkg_name}"
    lines = [
        f"Package: {pkg.name}",
        f"Version: {pkg.version}",
        f"Maintainer: {pkg.signer}",
        f"Installed-Size: {pkg.size_kb} kB",
        f"Depends: {', '.join(pkg.depends) if pkg.depends else '(none)'}",
        f"Download-Size: {_fmt_size(pkg.size_kb)}",
        f"APT-Sources: http://deb.debian.org/debian bookworm/main",
        f"Description: {pkg.summary}",
    ]
    if pkg.name in tk.installed:
        lines.insert(0, "Status: install ok installed")
    return "\n".join(lines)


def _apt_install(ctx: CommandContext, rest: list[str]) -> str:
    tk = _toolkit(ctx)
    if not rest:
        return "Usage: apt install <package> [<package>...]"

    outputs: list[str] = []
    for pkg_name in rest:
        result = tk.install(pkg_name, repo="apt")
        outputs.append(result.message)
        if result.success:
            if result.commands_unlocked:
                unlocked = ", ".join(result.commands_unlocked)
                outputs.append(f"New commands available: {unlocked}")
            if result.poisoned:
                outputs.append(_poison_notice(result, ctx))

    return "\n".join(outputs)


def _apt_remove(ctx: CommandContext, rest: list[str]) -> str:
    tk = _toolkit(ctx)
    if not rest:
        return "Usage: apt remove <package> [<package>...]"

    outputs: list[str] = []
    for pkg_name in rest:
        result = tk.remove(pkg_name)
        outputs.append(result.message)

    return "\n".join(outputs)


def _apt_list(ctx: CommandContext, rest: list[str]) -> str:
    tk = _toolkit(ctx)
    installed_flag = "--installed" in rest

    if installed_flag:
        if not tk.installed:
            return "Listing... Done\n(no packages installed via apt)"
        lines = ["Listing... Done"]
        for name, ip in sorted(tk.installed.items()):
            if ip.pkg.repo != "apt":
                continue
            lines.append(f"{name}/{ip.pkg.version} [installed]")
        return "\n".join(lines)

    query = next((a for a in rest if not a.startswith("-")), None)
    if query:
        return _apt_search(ctx, [query])

    lines = ["Listing... Done"]
    for pkg in sorted(tk.catalog.values(), key=lambda p: p.name):
        if pkg.repo != "apt":
            continue
        installed = " [installed]" if pkg.name in tk.installed else ""
        lines.append(f"{pkg.name}/{pkg.version}{installed}")
    return "\n".join(lines)


def _apt_verify(ctx: CommandContext, rest: list[str]) -> str:
    tk = _toolkit(ctx)
    if not rest:
        return "Usage: apt verify <package>"
    pkg_name = rest[0]
    result = tk.verify(pkg_name)
    if result.warning:
        return result.warning
    return f"gpg: Good signature from \"{result.signer}\"\ngpg: Signature valid."


# ---------------------------------------------------------------------------
# shadow
# ---------------------------------------------------------------------------


@register_command(
    name="shadow",
    usage="shadow <pull|search|kits|commit> [args...]",
    help_text="Underground package manager (requires shadow source configured)",
    category="package",
)
def cmd_shadow(ctx: CommandContext, args: list[str]) -> str:
    if not args:
        return (
            "shadow 0.8-xx\n"
            "Usage: shadow {pull|search|kits|commit} ...\n"
            "shadow repo: not configured" if not _toolkit(ctx).shadow_enabled else
            "shadow repo: active"
        )

    tk = _toolkit(ctx)
    sub = args[0].lower()
    rest = args[1:]

    if sub == "pull":
        return _shadow_pull(ctx, tk, rest)
    if sub == "search":
        return _shadow_search(ctx, tk, rest)
    if sub == "kits":
        return _shadow_kits(tk)
    if sub == "commit":
        return _shadow_commit(ctx, tk, rest)

    return f"E: Unknown shadow subcommand: {sub}"


def _shadow_pull(ctx: CommandContext, tk, rest: list[str]) -> str:
    if not tk.shadow_enabled:
        return (
            "E: shadow repository not configured.\n"
            "Hint: append a shadow source to /etc/apt/sources.list.d/\n"
            "      (check .bash_history — something was added before the wipe)"
        )
    if not rest:
        return "Usage: shadow pull <package>"

    pkg_name = rest[0]
    result = tk.install(pkg_name, repo="shadow")
    output = result.message

    if result.success:
        if result.commands_unlocked:
            unlocked = ", ".join(result.commands_unlocked)
            output += f"\nNew commands available: {unlocked}"
        # Poison effect notice — the player installed something that bit them
        if result.poisoned:
            output += _poison_notice(result, ctx)
        # The claude-toolkit reveal — meta-horror moment
        if pkg_name == "claude-toolkit":
            output += _CLAUDE_TOOLKIT_REVEAL

    return output


def _shadow_search(ctx: CommandContext, tk, rest: list[str]) -> str:
    if not tk.shadow_enabled:
        return "E: shadow repository not configured."
    if not rest:
        return "Usage: shadow search <query>"
    query = " ".join(rest)
    matches = [p for p in _search_catalog(tk, query) if p.repo == "shadow"]
    if not matches:
        return f"[shadow] No results for '{query}'"
    lines = [f"[shadow] Search results for '{query}':"]
    for pkg in sorted(matches, key=lambda p: p.name):
        kit_tag = f"[{pkg.kit}]" if pkg.kit else ""
        installed = " (installed)" if pkg.name in tk.installed else ""
        lines.append(f"  {pkg.name:<22} {pkg.version:<12} {kit_tag}{installed}")
        lines.append(f"    {pkg.summary}")
    return "\n".join(lines)


def _shadow_kits(tk) -> str:
    lines = ["[shadow] Available kits:\n"]
    for kit_name, packages in _KITS.items():
        committed = " ← COMMITTED" if tk._committed_kit == kit_name else ""
        lines.append(f"  {kit_name.upper()}KIT{committed}")
        lines.append(f"  {_KIT_DESCRIPTIONS[kit_name]}")
        for pkg_name in packages:
            pkg = tk.catalog.get(pkg_name)
            if pkg:
                installed = " (installed)" if pkg_name in tk.installed else ""
                cost = f"Ƀ{pkg.cost_btc:.3f}" if pkg.cost_btc > 0 else "free"
                lines.append(f"    • {pkg_name:<20} {cost}{installed}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _shadow_commit(ctx: CommandContext, tk, rest: list[str]) -> str:
    if not tk.shadow_enabled:
        return "E: shadow repository not configured."
    if not rest:
        return "Usage: shadow commit <kit>\nKits: ghost | breaker | oracle"
    kit = rest[0].lower()
    result = tk.commit_kit(kit)
    if result.success and kit in _COMMIT_NARRATIVE:
        return _COMMIT_NARRATIVE[kit]
    return result.message


# ---------------------------------------------------------------------------
# gpg
# ---------------------------------------------------------------------------


@register_command(
    name="gpg",
    usage="gpg [--list-keys | --verify <pkg>]",
    help_text="GNU Privacy Guard — key management and package verification",
    category="package",
)
def cmd_gpg(ctx: CommandContext, args: list[str]) -> str:
    tk = _toolkit(ctx)

    if not tk.is_installed("gpg"):
        return "bash: gpg: command not found\nHint: apt install gpg"

    if not args:
        return (
            "gpg (GnuPG) 2.4.3\n"
            "Usage: gpg [--list-keys | --verify <package>]"
        )

    if args[0] == "--list-keys":
        return _gpg_list_keys(tk)

    if args[0] == "--verify":
        if len(args) < 2:
            return "Usage: gpg --verify <package>"
        pkg_name = args[1]
        result = tk.verify(pkg_name)
        if result.warning:
            return result.warning
        return (
            f"gpg: Signature made using RSA key\n"
            f"gpg: Good signature from \"{result.signer}\"\n"
            f"gpg: Signature valid."
        )

    return f"gpg: unrecognised option '{args[0]}'"


# ---------------------------------------------------------------------------
# dpkg
# ---------------------------------------------------------------------------

_DPKG_STATUS_PATH = "/var/lib/dpkg/status"


def _parse_flags(args: list[str]) -> tuple[set[str], list[str]]:
    flags: set[str] = set()
    positional: list[str] = []
    for a in args:
        if a.startswith("--") and len(a) > 2:
            flags.add(a[2:])
        elif a.startswith("-") and len(a) > 1 and not a[1:].isdigit():
            for ch in a[1:]:
                flags.add(ch)
        else:
            positional.append(a)
    return flags, positional


@register_command(
    name="dpkg",
    usage="dpkg [-l | -s <pkg> | --get-selections | --list]",
    help_text="Debian package manager low-level tool",
    category="package",
)
def cmd_dpkg(ctx: CommandContext, args: list[str]) -> str:
    flags, positional = _parse_flags(args)

    tk = ctx.toolkit if hasattr(ctx, "toolkit") else None

    sub = positional[0] if positional else None
    list_mode = "l" in flags or "list" in flags or sub == "--list"
    status_mode = "s" in flags
    selections_mode = "get-selections" in flags or sub == "--get-selections"

    # Try to read from VFS first (most accurate — toolkit writes it there)
    if list_mode or (not args):
        dpkg_db = _read_dpkg_status(ctx)
        if dpkg_db:
            header = (
                "Desired=Unknown/Install/Remove/Purge/Hold\n"
                "| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend\n"
                "|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)\n"
                f"{'||/':<4}  {'Name':<22}  {'Version':<16}  Architecture  Description"
            )
            return header + "\n" + dpkg_db
        if tk is not None:
            lines = [
                "Desired=Unknown/Install/Remove/Purge/Hold\n"
                "| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend\n"
                "|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)\n"
                f"{'||/':<4}  {'Name':<22}  {'Version':<16}  Architecture  Description"
            ]
            for name, ip in sorted(tk.installed.items()):
                lines.append(
                    f"{'ii':<4}  {name:<22}  {ip.pkg.version:<16}  amd64         {ip.pkg.summary}"
                )
            return "\n".join(lines)
        return "dpkg: no packages installed"

    if status_mode and positional:
        pkg_name = positional[0]
        if tk is not None:
            ip = tk.installed.get(pkg_name)
            if ip:
                return (
                    f"Package: {ip.pkg.name}\n"
                    f"Status: install ok installed\n"
                    f"Version: {ip.pkg.version}\n"
                    f"Architecture: amd64\n"
                    f"Description: {ip.pkg.summary}"
                )
            return f"dpkg-query: package '{pkg_name}' is not installed and no information is available"
        return f"dpkg-query: package '{pkg_name}' is not installed"

    if selections_mode:
        if tk is not None:
            lines = [f"{name}\t\tinstall" for name in sorted(tk.installed)]
            return "\n".join(lines) if lines else "(no packages installed)"
        return "(no packages installed)"

    # Default: show usage
    return (
        "Usage: dpkg [-l] [-s <pkg>] [--get-selections]\n"
        "       dpkg -l     — list installed packages\n"
        "       dpkg -s pkg — show package status"
    )


def _read_dpkg_status(ctx: CommandContext) -> str:
    if ctx.fs is None:
        return ""
    try:
        raw = ctx.fs.read_file(_DPKG_STATUS_PATH)
        # Convert the raw status format to dpkg -l format
        lines: list[str] = []
        current: dict[str, str] = {}
        for line in raw.splitlines():
            if line.startswith("Package:"):
                current["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("Version:"):
                current["version"] = line.split(":", 1)[1].strip()
            elif line.startswith("Description:"):
                current["desc"] = line.split(":", 1)[1].strip()
            elif not line.strip() and "name" in current:
                name = current.get("name", "")
                ver = current.get("version", "")
                desc = current.get("desc", "")
                lines.append(f"{'ii':<4}  {name:<22}  {ver:<16}  amd64         {desc}")
                current = {}
        return "\n".join(lines)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# apt-get (thin alias for apt)
# ---------------------------------------------------------------------------


@register_command(
    name="apt-get",
    usage="apt-get <update|install|remove|...> [args...]",
    help_text="APT package manager (legacy interface — prefer apt)",
    category="package",
)
def cmd_apt_get(ctx: CommandContext, args: list[str]) -> str:
    # Delegate entirely to apt with a style note on first use
    from hackerzork.commands.packaging import cmd_apt
    result = cmd_apt(ctx, args)
    return result


def _gpg_list_keys(tk) -> str:
    signers: set[str] = set()
    for ip in tk.installed.values():
        signer = ip.pkg.signer
        if signer and signer != "UNSIGNED":
            signers.add(signer)

    if not signers:
        return "pub   (no trusted keys imported)"

    lines = ["pub   rsa4096 2024-01-01 [SC]"]
    for i, signer in enumerate(sorted(signers), start=1):
        lines.append(f"      [{i:04X}] {signer}")
    return "\n".join(lines)
