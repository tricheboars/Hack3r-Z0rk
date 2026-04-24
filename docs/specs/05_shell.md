# Spec: Shell REPL

## Module: `hackerzork/engine/shell.py`

### Purpose
The main interactive loop. Reads input, parses it, dispatches to commands, handles pipes and redirection, and writes output to the terminal. This is the glue layer between the player and all game systems.

---

## Class: `Shell`

```python
class Shell:
    def __init__(self, ctx: CommandContext, registry: CommandRegistry) -> None

    async def run(self) -> None          # main REPL loop (asyncio)
    def execute(self, raw: str) -> str   # parse + dispatch one input line
    def _prompt(self) -> str            # build the PS1 prompt string
    def _handle_pipe(self, cmds: list[ParsedCommand]) -> str
    def _handle_redirect(self, result: str, redir: Redirect) -> str
```

### Prompt Format
```
[user@hackerzork <cwd>]$ 
```
- `user` = `ctx.env.get("USER", "user")`
- `cwd` = last component of `CWD`, or `~` when CWD == HOME
- Color via Rich markup if output supports it

### REPL Loop

1. Display prompt
2. Read input (readline, with arrow-key history)
3. Strip and check for empty → loop
4. Pass to `execute()`
5. Print result
6. Loop

### `execute(raw: str) -> str`

1. Expand environment variables (`$VAR`, `${VAR}`)
2. Parse via `CommandParser`
3. If parse returns None (empty) → return `""`
4. If chained (`;` or `&&`) → execute each, join with newlines
5. If piped → `_handle_pipe()`
6. Otherwise → dispatch single command
7. If redirect → `_handle_redirect()`
8. Emit `command_entered` event: `cmd=<name>`, `raw_input=raw`

### Pipe Handling
- Execute first command, pass stdout as stdin to next
- Commands that accept stdin: `grep`, `wc`, `head`, `tail`, `cat`
- Stdin injected as first positional arg with special marker, or via `ctx.env["STDIN"]`
- Each stage's output becomes the next stage's input

### Redirection
- `>` — write result to VFS file (create or overwrite)
- `>>` — append to VFS file
- Errors writing to VFS are returned as error strings (no crash)

### Command Not Found
```
bash: <name>: command not found
```

### Exit / Quit
- `exit` or `quit` → clean shutdown, emit `game_exit` event
- `Ctrl+C` → emit `keyboard_interrupt`, print `^C` and new prompt
- `Ctrl+D` → same as exit

---

## Module: `hackerzork/engine/tab_complete.py`

### Purpose
Tab completion engine. Plugs into readline.

### Behavior
- If partial matches a command name → complete to command
- If after a known command → complete filesystem paths from CWD
- Path completion: match entries in the VFS directory
- Cycle through candidates on repeated Tab

```python
class TabCompleter:
    def __init__(self, registry: CommandRegistry, fs: VirtualFS, env: dict) -> None
    def complete(self, text: str, state: int) -> str | None
    def _command_completions(self, partial: str) -> list[str]
    def _path_completions(self, partial: str, cwd: str) -> list[str]
```

---

## Module: `hackerzork/engine/history.py`

### Purpose
Command history — arrow keys and Ctrl+R search.

### Behavior
- Up/Down arrows cycle through history
- Ctrl+R → reverse search mode
- History persisted to VFS at `/home/user/.bash_history` (append on exit)
- `history` command (in `commands/system.py`) reads from this
- Max 1000 entries in memory

```python
class CommandHistory:
    def __init__(self, fs: VirtualFS | None = None) -> None
    def add(self, cmd: str) -> None
    def load_from_fs(self) -> None    # reads .bash_history from VFS
    def save_to_fs(self) -> None      # writes .bash_history to VFS
    def get_all(self) -> list[str]
```

---

## Tests: `tests/test_engine/test_shell.py`

- Test `execute()` with known commands → correct output
- Test env var expansion in input
- Test pipe: `cat file | grep pattern`
- Test redirect: `echo hello > /tmp/out.txt` then `cat /tmp/out.txt`
- Test command not found → correct error string
- Test empty input → empty string
- Test chained commands: `cmd1; cmd2`
