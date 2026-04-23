# Spec: Command Parser & Registry

## Module: `hackerzork/engine/command_parser.py`

### Purpose
Tokenize and parse bash-like user input into structured command objects.

### Input Format
The parser must handle:
- Simple commands: `ls -la /home`
- Quoted strings: `echo "hello world"`
- Pipes: `cat /etc/passwd | grep root`
- Redirection: `nmap 10.0.0.1 > scan.txt`, `echo data >> log.txt`
- Chaining: `cd /tmp && ls`
- Environment variable expansion: `echo $HOME`, `nmap $TARGET`
- Semicolons: `cmd1; cmd2`
- Backslash escaping: `echo hello\ world`

### Output Structure
```python
@dataclass
class ParsedCommand:
    name: str                    # Command name (e.g., "nmap")
    args: list[str]             # Positional arguments
    flags: dict[str, str | bool] # Parsed flags (-v, --port=80)
    raw: str                    # Original input string
    pipe_to: ParsedCommand | None  # Piped command
    redirect: Redirect | None   # Output redirection

@dataclass
class Redirect:
    target: str      # File path
    append: bool     # >> vs >
```

### Key Behaviors
- Unrecognized commands return a clear error: `bash: command not found: xyz`
- Empty input returns None (shell prints new prompt)
- Variable expansion happens before command lookup
- Pipes create a chain of ParsedCommands

---

## Module: `hackerzork/engine/command_registry.py`

### Purpose
Plugin-style registry where commands register themselves with metadata.

### API
```python
def register_command(name, usage, help_text, category, aliases=None):
    """Decorator to register a command handler."""

class CommandRegistry:
    def register(self, name, handler, metadata) -> None
    def get(self, name) -> CommandHandler | None
    def get_all_by_category(self, category) -> list[CommandHandler]
    def get_completions(self, partial) -> list[str]
    def get_help(self, name) -> str

class CommandContext:
    """Passed to every command handler."""
    fs: VirtualFS          # Filesystem access
    network: NetworkSim    # Network access
    state: GameState       # Game state
    events: EventBus       # Emit events
    heat: HeatSystem       # Heat access
    output: OutputBuffer   # Write output (supports effects)
    env: dict[str, str]    # Environment variables
```

### Categories
- `filesystem` — ls, cd, cat, pwd, mkdir, rm, cp, mv, chmod, chown, find, grep
- `network` — nmap, ssh, ping, traceroute, curl, netcat, dig, whois
- `hacking` — Custom exploit tools
- `comms` — irc, msg, contacts
- `system` — whoami, uname, ps, top, man, history, clear, exit, env, export
- `help` — help, tutorial, hint

### Tests: `tests/test_engine/test_command_parser.py`
- Test simple command parsing
- Test flag parsing (-v, --verbose, --port=80, -p 80)
- Test quoted strings
- Test pipe chains
- Test redirection
- Test env var expansion
- Test edge cases (empty, whitespace-only, unclosed quotes)
