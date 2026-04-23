"""Bash-like command parser for the H@ck3r-Z0rk shell.

Tokenizes input into words and operators, then parses them into a chain of
``ParsedCommand`` objects. Handles quoting, escapes, ``$VAR`` expansion,
pipes (``|``), redirection (``>``, ``>>``), and statement chaining
(``;`` and ``&&``).

The parser is intentionally permissive — it leaves command-specific
validation (unknown commands, semantic errors) to the registry and shell.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ParseError(Exception):
    """Raised when input cannot be tokenized or parsed."""


class TokenType(Enum):
    WORD = "word"
    PIPE = "pipe"               # |
    REDIRECT = "redirect"       # >
    REDIRECT_APPEND = "append"  # >>
    SEMICOLON = "semicolon"     # ;
    AND = "and"                 # &&
    OR = "or"                   # ||


@dataclass
class Token:
    type: TokenType
    value: str


@dataclass
class Redirect:
    target: str
    append: bool = False


@dataclass
class ParsedCommand:
    name: str
    args: list[str] = field(default_factory=list)
    flags: dict[str, str | bool] = field(default_factory=dict)
    raw: str = ""
    pipe_to: ParsedCommand | None = None
    redirect: Redirect | None = None


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_OPERATOR_CHARS = "|>;&"


def tokenize(text: str, env: dict[str, str] | None = None) -> list[Token]:
    """Split ``text`` into a list of tokens, expanding env vars as we go."""
    env = env or {}
    tokens: list[Token] = []
    i = 0
    n = len(text)

    while i < n:
        c = text[i]

        if c.isspace():
            i += 1
            continue

        if c == "|":
            if i + 1 < n and text[i + 1] == "|":
                tokens.append(Token(TokenType.OR, "||"))
                i += 2
            else:
                tokens.append(Token(TokenType.PIPE, "|"))
                i += 1
            continue

        if c == ">":
            if i + 1 < n and text[i + 1] == ">":
                tokens.append(Token(TokenType.REDIRECT_APPEND, ">>"))
                i += 2
            else:
                tokens.append(Token(TokenType.REDIRECT, ">"))
                i += 1
            continue

        if c == ";":
            tokens.append(Token(TokenType.SEMICOLON, ";"))
            i += 1
            continue

        if c == "&":
            if i + 1 < n and text[i + 1] == "&":
                tokens.append(Token(TokenType.AND, "&&"))
                i += 2
                continue
            raise ParseError(f"unexpected token '&' at position {i}")

        word, i = _read_word(text, i, env)
        tokens.append(Token(TokenType.WORD, word))

    return tokens


def _read_word(text: str, i: int, env: dict[str, str]) -> tuple[str, int]:
    """Read one word (which may contain quoted segments) starting at ``i``."""
    n = len(text)
    parts: list[str] = []

    while i < n:
        c = text[i]

        if c.isspace() or c in _OPERATOR_CHARS:
            break

        if c == "\\":
            if i + 1 < n:
                parts.append(text[i + 1])
                i += 2
            else:
                parts.append("\\")
                i += 1
            continue

        if c == "'":
            end = text.find("'", i + 1)
            if end == -1:
                raise ParseError("unclosed single quote")
            parts.append(text[i + 1 : end])
            i = end + 1
            continue

        if c == '"':
            i += 1
            sub: list[str] = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n and text[i + 1] in '\\"$`':
                    sub.append(text[i + 1])
                    i += 2
                elif text[i] == "$":
                    val, i = _expand_var(text, i, env)
                    sub.append(val)
                else:
                    sub.append(text[i])
                    i += 1
            if i >= n:
                raise ParseError("unclosed double quote")
            i += 1  # consume closing "
            parts.append("".join(sub))
            continue

        if c == "$":
            val, i = _expand_var(text, i, env)
            parts.append(val)
            continue

        parts.append(c)
        i += 1

    return "".join(parts), i


def _expand_var(text: str, i: int, env: dict[str, str]) -> tuple[str, int]:
    """Expand a ``$VAR`` or ``${VAR}`` reference. Undefined → empty string."""
    n = len(text)
    i += 1  # skip $

    if i >= n:
        return "$", i

    if text[i] == "{":
        end = text.find("}", i + 1)
        if end == -1:
            raise ParseError("unclosed ${")
        name = text[i + 1 : end]
        return env.get(name, ""), end + 1

    if text[i].isalpha() or text[i] == "_":
        j = i + 1
        while j < n and (text[j].isalnum() or text[j] == "_"):
            j += 1
        return env.get(text[i:j], ""), j

    return "$", i


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse(text: str, env: dict[str, str] | None = None) -> list[ParsedCommand]:
    """Parse ``text`` into a list of ``ParsedCommand`` pipelines.

    Each top-level entry is a statement (separated by ``;``, ``&&``, ``||``).
    Pipes inside a statement are linked via ``ParsedCommand.pipe_to``.
    Empty / whitespace-only input returns ``[]``.
    """
    if not text or not text.strip():
        return []

    tokens = tokenize(text, env=env)

    statements: list[list[Token]] = []
    current: list[Token] = []
    for tok in tokens:
        if tok.type in (TokenType.SEMICOLON, TokenType.AND, TokenType.OR):
            if current:
                statements.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        statements.append(current)

    raws = _split_raw(text)
    if len(raws) != len(statements):
        raws = [text.strip()] * len(statements)

    return [_build_pipeline(stmt, raw) for stmt, raw in zip(statements, raws)]


def parse_one(
    text: str, env: dict[str, str] | None = None
) -> ParsedCommand | None:
    """Parse and return only the first pipeline (or ``None`` if empty)."""
    cmds = parse(text, env=env)
    return cmds[0] if cmds else None


def _split_raw(text: str) -> list[str]:
    """Split raw input by top-level ``;``, ``&&``, ``||`` (respecting quotes)."""
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        c = text[i]

        if c == "'":
            end = text.find("'", i + 1)
            if end == -1:
                buf.append(text[i:])
                i = n
                continue
            buf.append(text[i : end + 1])
            i = end + 1
            continue

        if c == '"':
            buf.append(c)
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i : i + 2])
                    i += 2
                else:
                    buf.append(text[i])
                    i += 1
            if i < n:
                buf.append(text[i])
                i += 1
            continue

        if c == "\\" and i + 1 < n:
            buf.append(text[i : i + 2])
            i += 2
            continue

        is_split = (
            c == ";"
            or (c == "&" and i + 1 < n and text[i + 1] == "&")
            or (c == "|" and i + 1 < n and text[i + 1] == "|")
        )
        if is_split:
            piece = "".join(buf).strip()
            if piece:
                parts.append(piece)
            buf = []
            i += 2 if c in "&|" else 1
            continue

        buf.append(c)
        i += 1

    piece = "".join(buf).strip()
    if piece:
        parts.append(piece)
    return parts


def _build_pipeline(tokens: list[Token], raw: str) -> ParsedCommand:
    """Build a ``ParsedCommand`` chain by splitting ``tokens`` on PIPE."""
    segments: list[list[Token]] = []
    current: list[Token] = []
    for tok in tokens:
        if tok.type == TokenType.PIPE:
            segments.append(current)
            current = []
        else:
            current.append(tok)
    segments.append(current)

    if any(not seg for seg in segments):
        raise ParseError("empty command in pipeline")

    head: ParsedCommand | None = None
    tail: ParsedCommand | None = None
    for seg in segments:
        cmd = _build_command(seg, raw)
        if head is None:
            head = cmd
        else:
            assert tail is not None
            tail.pipe_to = cmd
        tail = cmd

    assert head is not None
    return head


def _build_command(tokens: list[Token], raw: str) -> ParsedCommand:
    """Build a single ``ParsedCommand``, extracting any redirection."""
    redirect: Redirect | None = None
    words: list[str] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type in (TokenType.REDIRECT, TokenType.REDIRECT_APPEND):
            if i + 1 >= len(tokens) or tokens[i + 1].type != TokenType.WORD:
                raise ParseError(f"missing target for '{tok.value}'")
            redirect = Redirect(
                target=tokens[i + 1].value,
                append=tok.type == TokenType.REDIRECT_APPEND,
            )
            i += 2
            continue
        if tok.type == TokenType.WORD:
            words.append(tok.value)
            i += 1
            continue
        raise ParseError(f"unexpected token: {tok.value}")

    if not words:
        raise ParseError("empty command")

    args, flags = _parse_args_and_flags(words[1:])
    return ParsedCommand(
        name=words[0],
        args=args,
        flags=flags,
        raw=raw,
        redirect=redirect,
    )


def _parse_args_and_flags(
    words: list[str],
) -> tuple[list[str], dict[str, str | bool]]:
    """Separate flags (``-x``, ``--long``, ``--key=val``) from positional args.

    Bash short-flag bundling: ``-la`` → ``{l: True, a: True}``.
    Short flags taking a separate value (``-p 80``) are NOT auto-consumed —
    the handler decides whether to pull the next positional. This keeps the
    parser command-agnostic.
    """
    args: list[str] = []
    flags: dict[str, str | bool] = {}
    end_of_flags = False

    for word in words:
        if end_of_flags:
            args.append(word)
            continue
        if word == "--":
            end_of_flags = True
            continue
        if word.startswith("--") and len(word) > 2:
            body = word[2:]
            if "=" in body:
                key, _, val = body.partition("=")
                flags[key] = val
            else:
                flags[body] = True
            continue
        if (
            word.startswith("-")
            and len(word) > 1
            and not _looks_like_negative_number(word)
        ):
            body = word[1:]
            if "=" in body:
                key, _, val = body.partition("=")
                flags[key] = val
            else:
                for ch in body:
                    flags[ch] = True
            continue
        args.append(word)

    return args, flags


def _looks_like_negative_number(s: str) -> bool:
    if len(s) < 2 or s[0] != "-":
        return False
    try:
        float(s[1:])
        return True
    except ValueError:
        return False
