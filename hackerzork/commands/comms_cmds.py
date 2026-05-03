"""Communications commands — IRC channels, encrypted DMs, contact management.

Commands: irc, msg, contacts
"""
from __future__ import annotations

from hackerzork.engine.command_registry import CommandContext, register_command


def _require_comms(ctx: CommandContext) -> str | None:
    """Return an error string if comms is unavailable, else None."""
    if ctx.comms is None:
        return "[comms] Communications system offline."
    return None


# ---------------------------------------------------------------------------
# irc
# ---------------------------------------------------------------------------

_IRC_USAGE = """irc <subcommand> [args]

Subcommands:
  list                  List available channels
  join  <#channel>      Join a channel
  part  <#channel>      Leave a channel
  read  <#channel> [-n N]  Read last N messages (default 20)
  post  <#channel> <msg>   Post a message
  who   <#channel>      List channel users
  nick  <handle>        Set your IRC handle"""


@register_command(
    name="irc",
    usage="irc <subcommand> [args]",
    help_text="IRC-style channel chat — list, join, read, write, nick",
    category="comms",
    description=(
        "IRC = Internet Relay Chat (1988). Channels are public-by-default text\n"
        "rooms named with a leading '#'. The protocol predates the web and is\n"
        "still where infosec, kernel, and a lot of FOSS coordination happens.\n"
        "\n"
        "Subcommands:\n"
        "  irc                       list channels you're currently in\n"
        "  irc list                  every channel known to the server\n"
        "  irc join <#chan>          join a channel\n"
        "  irc part <#chan>          leave\n"
        "  irc read <#chan> [n]      last N messages (default 10)\n"
        "  irc write <#chan> <msg>   say something\n"
        "  irc nick <handle>         change your handle\n"
        "\n"
        "Some channels are GATED behind story flags — they exist but you can't\n"
        "join until the right thing has happened in the world. #z0rk_7_ops is\n"
        "the obvious example; you need shadow_unlocked first."
    ),
    examples=[
        ("irc list", "discover channels"),
        ("irc join #underground", "join the public underground channel"),
        ("irc read #underground 30", "scrollback the last 30 messages"),
        ("irc write #underground 'looking for relay-alpha tips'", "post"),
    ],
    see_also=["msg", "contacts"],
    concepts=["comms"],
)
def cmd_irc(ctx: CommandContext, args: list[str]) -> str:
    err = _require_comms(ctx)
    if err:
        return err

    if not args:
        return _irc_status(ctx)

    sub = args[0].lower()

    if sub == "list":
        return ctx.comms.list_channels()

    if sub in ("join",):
        if len(args) < 2:
            return "Usage: irc join <#channel>"
        return ctx.comms.join_channel(args[1])

    if sub in ("part", "leave"):
        if len(args) < 2:
            return "Usage: irc part <#channel>"
        return ctx.comms.leave_channel(args[1])

    if sub == "read":
        if len(args) < 2:
            return "Usage: irc read <#channel> [-n N]"
        channel = args[1]
        limit = 20
        if "-n" in args:
            idx = args.index("-n")
            if idx + 1 < len(args):
                try:
                    limit = int(args[idx + 1])
                except ValueError:
                    pass
        return ctx.comms.read_channel(channel, limit=limit)

    if sub == "post":
        if len(args) < 3:
            return "Usage: irc post <#channel> <message>"
        channel = args[1]
        message = " ".join(args[2:])
        echo, npc_reply = ctx.comms.post_message(channel, message)
        if ctx.heat:
            ctx.heat.add_heat(1.0)
        lines = [echo]
        if npc_reply:
            lines.append(npc_reply)
        return "\n".join(lines)

    if sub == "who":
        if len(args) < 2:
            return "Usage: irc who <#channel>"
        return ctx.comms.who(args[1])

    if sub == "nick":
        if len(args) < 2:
            return "Usage: irc nick <handle>"
        return ctx.comms.set_nick(args[1])

    if sub in ("help", "--help", "-h"):
        return _IRC_USAGE

    return f"Unknown irc subcommand: {sub}\n\n{_IRC_USAGE}"


def _irc_status(ctx: CommandContext) -> str:
    joined = [
        name for name, ch in ctx.comms.channels.items() if ch.joined
    ]
    if not joined:
        return "Not in any channels. Use: irc list"
    lines = ["Joined channels:"]
    for name in sorted(joined):
        ch = ctx.comms.channels[name]
        unread = f" [{ch.unread} unread]" if ch.unread else ""
        lines.append(f"  {name}{unread}  —  {ch.topic}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# msg
# ---------------------------------------------------------------------------

_MSG_USAGE = """msg <subcommand> [args]

Subcommands:
  list               List DM threads
  read  <handle>     Read DM thread with handle
  send  <handle> <message>  Send encrypted DM"""


@register_command(
    name="msg",
    usage="msg <subcommand> [args]",
    help_text="Send and receive encrypted direct messages.",
    category="comms",
)
def cmd_msg(ctx: CommandContext, args: list[str]) -> str:
    err = _require_comms(ctx)
    if err:
        return err

    if not args:
        return ctx.comms.list_dms()

    sub = args[0].lower()

    if sub == "list":
        return ctx.comms.list_dms()

    if sub == "read":
        if len(args) < 2:
            return "Usage: msg read <handle>"
        return ctx.comms.read_dm(args[1])

    if sub == "send":
        if len(args) < 3:
            return "Usage: msg send <handle> <message>"
        handle = args[1]
        message = " ".join(args[2:])
        if ctx.heat:
            ctx.heat.add_heat(0.5)
        return ctx.comms.send_dm(handle, message)

    if sub in ("help", "--help", "-h"):
        return _MSG_USAGE

    return f"Unknown msg subcommand: {sub}\n\n{_MSG_USAGE}"


# ---------------------------------------------------------------------------
# contacts
# ---------------------------------------------------------------------------

_CONTACTS_USAGE = """contacts <subcommand> [args]

Subcommands:
  list              List all contacts
  info  <handle>    Show contact details
  add   <handle>    Add a new contact"""


@register_command(
    name="contacts",
    usage="contacts [subcommand] [args]",
    help_text="Manage your contacts list — handles, keys, status.",
    category="comms",
)
def cmd_contacts(ctx: CommandContext, args: list[str]) -> str:
    err = _require_comms(ctx)
    if err:
        return err

    if not args or args[0].lower() == "list":
        return ctx.comms.list_contacts()

    sub = args[0].lower()

    if sub == "info":
        if len(args) < 2:
            return "Usage: contacts info <handle>"
        return ctx.comms.contact_info(args[1])

    if sub == "add":
        if len(args) < 2:
            return "Usage: contacts add <handle>"
        return ctx.comms.add_contact(args[1])

    if sub in ("help", "--help", "-h"):
        return _CONTACTS_USAGE

    return f"Unknown contacts subcommand: {sub}\n\n{_CONTACTS_USAGE}"
