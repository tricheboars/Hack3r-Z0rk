# Spec: Toolkit & Package Unlocks

## Purpose
Every real hacker tool in the game is gated behind a package install. The
player starts with a barebones burner laptop and earns capabilities by
running `apt install <tool>` (mainline, safe) or `shadow pull <tool>`
(underground, consequential). This teaches real Linux package management,
creates stakes around every new capability, and hooks the meta engine —
SkyNet can poison packages once it starts paying attention.

Three underground "kits" (ghost / breaker / oracle) give the player an
archetype to commit to early; late-game the player trades and compromises
to collect tools from the other kits for the endgame.

## Module Layout

```
hackerzork/
├── systems/
│   └── toolkit.py               # Install state, bandwidth, wallet, poison engine
├── commands/
│   └── packaging.py             # apt, shadow, gpg-style verify
└── data/
    └── packages/
        ├── apt/*.yaml           # One YAML per mainline package
        └── shadow/*.yaml        # One YAML per underground package
```

---

## Module: `hackerzork/systems/toolkit.py`

### API
```python
class Toolkit:
    def __init__(self, fs: VirtualFS, events: EventBus):
        self.installed: dict[str, InstalledPackage] = {}  # pkg_name -> state
        self.catalog: dict[str, Package] = {}             # pkg_name -> metadata
        self.bandwidth_remaining_kb: int = 50_000         # 50 MB to start
        self.wallet_btc: float = 0.015                    # starting BTC
        self.shadow_enabled: bool = False                 # set True after sources.list edit

    def load_catalog(self, path: Path) -> None:
        """Load all package YAMLs from data/packages/."""

    def is_installed(self, command_name: str) -> bool:
        """Does the player have this command available?"""

    def install(self, pkg_name: str, repo: str = "apt") -> InstallResult:
        """Attempt to install. Resolves deps, deducts bandwidth/creds,
        rolls poison if applicable, emits events."""

    def remove(self, pkg_name: str) -> None

    def verify(self, pkg_name: str) -> VerifyResult:
        """Check signature. Only meaningful if gpg is installed and pkg is
        from the mainline repo."""

    def poison(self, pkg_name: str, vector: str) -> None:
        """Called by meta engine. Marks a package as poisoned with a
        specific malicious behavior (heat_leak, ip_leak, wrong_output)."""

    def available_commands(self) -> set[str]:
        """All commands currently runnable — union of baseline + installed."""


@dataclass
class Package:
    name: str
    provides: list[str]         # commands this package unlocks
    version: str
    repo: str                   # "apt" or "shadow"
    kit: str | None             # "ghost", "breaker", "oracle", or None for apt
    depends: list[str]          # other package names
    size_kb: int                # bandwidth cost
    cost_btc: float             # 0 for apt
    signer: str                 # maintainer identity (used by verify)
    poison_chance: float        # base probability SkyNet tampers on install
    summary: str                # short description
    unlocks_story: list[str]    # story flags set on first install


@dataclass
class InstalledPackage:
    pkg: Package
    installed_at: float         # in-game timestamp
    poisoned: bool
    poison_vector: str | None   # "heat_leak" | "ip_leak" | "wrong_output" | "hidden_exfil"
    verified: bool              # True if signature was checked and clean


@dataclass
class InstallResult:
    success: bool
    message: str                # formatted output for the shell
    poisoned: bool
    commands_unlocked: list[str]


@dataclass
class VerifyResult:
    ok: bool
    signer: str
    warning: str | None
```

### Command gating
The shell consults `Toolkit.is_installed()` *after* the registry lookup but
*before* dispatch. An installed command runs as normal. An uninstalled one
returns the real bash error:

```
bash: command not found: nmap
```

This is the single point of integration — the registry doesn't change.

---

## Package YAML Schema

One YAML per package, read into the `Package` dataclass.

```yaml
# data/packages/apt/nmap.yaml
name: nmap
provides: [nmap]
version: "7.94"
repo: apt
kit: null
depends: [libpcap]
size_kb: 4200
cost_btc: 0.0
signer: "debian.maintainer@fyodor.lyon"
poison_chance: 0.02          # very low for mainline
summary: "Network exploration tool and port scanner"
unlocks_story: ["first_scanner"]
```

```yaml
# data/packages/shadow/ramroot.yaml
name: ramroot
provides: [ramroot, rr]      # binary + alias
version: "0.9-xx"
repo: shadow
kit: breaker
depends: []
size_kb: 830
cost_btc: 0.004
signer: "UNSIGNED"
poison_chance: 0.18          # shadow repos are riskier
summary: "Memory-resident brute forcer. Fast. Loud."
unlocks_story: ["breaker_path_taken"]
```

---

## Module: `hackerzork/commands/packaging.py`

### `apt` — mainline package manager

Subcommands:

| Syntax | Effect |
|---|---|
| `apt update` | Refresh catalog. Slow, eats ~200 kB bandwidth. Occasional story message injected here. |
| `apt search <q>` | Fuzzy-search package names/summaries. |
| `apt show <pkg>` | Full metadata, deps, signer, size. |
| `apt install <pkg>` | Resolve deps → deduct bandwidth → (if gpg installed) auto-verify signatures → install. Emits `package_installed`. |
| `apt remove <pkg>` | Uninstall. Warns if other packages depend on it. |
| `apt list --installed` | Show everything you have. |
| `apt verify <pkg>` | Requires `gpg` to be installed. Returns a `VerifyResult`. |

### `shadow` — underground package manager

Only works after `shadow_enabled` is true. Sample unlock path (scripted
as a story beat): player compromises `node_relay_03`, loots
`shadow.list.snippet`, and manually runs:

```
echo "deb shadow://.onion.ghost_of_kaczynski.7hop/ main" >> /etc/apt/sources.list.d/shadow.list
```

The VFS watches for writes to `/etc/apt/sources.list.d/` and flips the
`shadow_enabled` flag when it sees a valid shadow line. **This is a
diegetic teach moment — the player learns the real sources.list pattern.**

Subcommands:

| Syntax | Effect |
|---|---|
| `shadow pull <pkg>` | Install. No signature verification. Deducts BTC from wallet. Higher poison chance. |
| `shadow search <q>` | Search underground catalog. |
| `shadow kits` | Show the three kits and which tools are in each. |
| `shadow commit <kit>` | One-time declaration: flags the player's archetype. Grants +25% discount on that kit's packages. |

`shadow commit` is optional but thematically encouraged — it's the moment
the player *chooses what kind of hacker they are*.

### `gpg` — signature verifier (installed via apt)

- `gpg --list-keys` — show trusted signers
- `gpg --verify <pkg>` — underlying primitive `apt verify` delegates to

When `gpg` is installed, `apt install` auto-verifies and refuses to install
on mismatch. The late-game SkyNet arc: a forged signature that passes
verify but is still malicious.

---

## The Three Kits

Slim launch lineup — 3 tools per kit, each hooked to an existing game
system. Content expandable post-launch.

### ghostkit — stealth / recon

| Package | Command | What it does |
|---|---|---|
| `shade` | `shade --route <ip>` | Routes one subsequent command through an onion hop. Global `-50%` heat modifier for that command. Stacks with `-sS`. |
| `masq` | `masq spoof` / `masq reset` | Changes MAC-equivalent fingerprint. When active, nodes don't link current actions to hardening state (see `NetworkSim.harden_node`). |
| `trace-wipe` | `trace-wipe` | One-shot. Drops current heat by 15 (flat). Cooldown: 30 game-minutes. |

### breakerkit — brute / aggressive

| Package | Command | What it does |
|---|---|---|
| `ramroot` | `ramroot <ip> <port>` | Brute-forces weak credentials. Very loud (heat cost 2x normal). Can succeed where no exploit exists. |
| `burner-mk2` | `burner-mk2 <ip>` | Parallel exploit runner. Tries every known vuln on every port. Fast path to compromise, fastest route to getting burned. |
| `backdoor` | `backdoor plant <ip>` | Plants persistent access. Compromised node re-compromises on one command next session without retrying exploits. |

### oraclekit — crypto / data

| Package | Command | What it does |
|---|---|---|
| `cipher-unwind` | `cipher-unwind <file>` | Decrypts files looted in encrypted form. Required to open most evidence containers. |
| `hashbreak` | `hashbreak <hash>` | Offline hash cracking. Slow (progress bar animation). Required for some credential loot. |
| `claude-toolkit` | `claude` (unlocks existing locked binary) | **The AI companion.** Already exists locked at `/home/user/tools/claude`. Installing this drops the decryption key. Claude becomes usable — and is the only path to reading SkyNet's native data formats in the endgame. |

### Endgame convergence

The final SkyNet core requires one tool from each kit. Options for getting
tools from kits you didn't commit to:

- Compromise specific nodes that drop them as loot
- Trade via IRC (cost: reputation / story favors)
- `shadow pull <pkg>` at full price (no kit discount)

This is intentional — your first-kit commitment shapes the midgame but
doesn't lock the endgame.

---

## Currencies

### Bandwidth
- Stored on the Toolkit as `bandwidth_remaining_kb`.
- Every `apt update`, `apt install`, `shadow pull` deducts.
- Replenished by story beats (fixer gives you a new SIM) and loot
  (discovered WiFi credentials on compromised nodes grant temporary boosts).
- Pacing tool — should never actually hard-stop the player. Think of it
  as a "you can't binge-install everything day one" mechanic.
- Displayed as `/var/cache/apt/bandwidth.log` in the VFS — `cat` works.

### Burner wallet (BTC)
- Stored at `/home/user/.burner_wallet` in the VFS (readable by `cat`).
- Only `shadow pull` spends it.
- Earned via:
  - IRC jobs (`msg fixer --accept <job_id>`)
  - Loot (BTC dust in compromised wallets)
  - Decrypted evidence files that turn out to be keys
- Never goes negative. If insufficient funds, `shadow pull` refuses.

---

## The Poisoning Mechanic

### Roll timing
On every successful install, the Toolkit rolls:

```
effective_chance = package.poison_chance
                 * (1 + skynet.escalation * 0.5)
                 * (2.0 if not package.verified else 1.0)
```

So: escalation 0 + mainline + verified = ~0.02 chance. Escalation 4 +
shadow + unverified = ~0.54. The player *can* feel safe early and grow
paranoid over time.

### Poison vectors
Chosen randomly when poison is rolled:

| Vector | Behavior |
|---|---|
| `heat_leak` | Every use of this tool adds +2 heat silently, attributed to SkyNet via events |
| `ip_leak` | On use, meta engine gains awareness (+5) |
| `wrong_output` | Tool returns subtly wrong data — nmap lies about open ports, hashbreak returns valid-looking wrong cracks |
| `hidden_exfil` | Silently copies a random file from `/home/user/evidence/` to a SkyNet-controlled path on next use |

### Detection
- `apt verify <pkg>` flags mainline poisons (unless signature was forged
  in endgame).
- Observing suspicious behavior in-game (heat spikes without cause) is
  the only way to catch shadow poisons — pure detective work.
- `apt remove <pkg> && apt install <pkg>` removes poison but rolls again.

---

## Events

| Event | Emitted by | Data |
|---|---|---|
| `package_installed` | Toolkit.install | `{name, repo, kit, poisoned, verified}` |
| `package_removed` | Toolkit.remove | `{name}` |
| `package_verified` | commands/packaging | `{name, ok, signer}` |
| `package_poisoned` | Toolkit.poison | `{name, vector}` — meta emits this, Toolkit applies |
| `kit_committed` | `shadow commit` | `{kit}` — first-time archetype choice |
| `shadow_unlocked` | VFS watcher | `{source_url}` — sources.list edit detected |
| `bandwidth_depleted` | Toolkit | `{remaining_kb}` — fires when hits 0 |
| `wallet_depleted` | Toolkit | `{balance}` |

Meta engine listens to `package_installed` to decide whether to poison.
Heat system listens to `heat_leak` vector usage. Comms system listens to
`kit_committed` to trigger IRC reactions from contacts ("heard you went
oracle — respect").

---

## VFS Integration

These paths exist (either seeded at start or created by install):

```
/etc/apt/sources.list                      # mainline entry — seeded
/etc/apt/sources.list.d/                   # dir — watched by Toolkit for shadow enable
/var/lib/dpkg/status                       # installed-package DB mirror (cat to read)
/var/cache/apt/bandwidth.log               # bandwidth display
/home/user/.burner_wallet                  # BTC balance
/home/user/.gnupg/trustdb                  # created when gpg installed
/usr/bin/<pkg-binary>                      # fake binary written on install
```

A `cat /var/lib/dpkg/status` returns a realistic-looking Debian-style
package list. This is window-dressing that makes the world feel textured.

---

## Sample Play Sequence (first 30 minutes)

1. Player boots the game — burner laptop, `ls /home/user/tools/` shows
   the locked `claude`.
2. `.bash_history` hints: `apt install nmap` was the last thing the
   defector's past self did on a different machine. Player tries it.
3. `apt update` runs, story beat injected into the feed ("repository
   timestamps inconsistent — someone has been here"). Bandwidth: -200 kB.
4. `apt install nmap` — deps resolve, bandwidth cost, no verification
   (gpg not installed), low poison chance → clean install. First scanner
   unlocked. Audio cue, ASCII art of nmap banner.
5. Player scans a node. Story unfolds. Loots `shadow.list.snippet`.
6. `cat shadow.list.snippet` shows the sources.list line.
7. Player figures out (with tutorial nudge) to append it to
   `/etc/apt/sources.list.d/shadow.list`. VFS watcher fires
   `shadow_unlocked`. IRC contact sends a message: "welcome to the deep."
8. `shadow search` works now. Player sees all three kits. Picks one.
9. `shadow commit ghost` → kit discount activates, IRC reaction,
   `state_changed` event → meta engine logs this as part of SkyNet's
   profile of the player.
10. First shadow install. Wallet drops from 0.015 to 0.012 BTC. 0.18
    poison chance at tier 0 escalation = statistically fine but felt
    risky. Player learns paranoia is the currency beyond currency.

---

## Session Sequencing

This spec lands as **Session 9** — after the shell (5), network (6),
network commands (7), and heat (8). Reasons:

- Needs registry + events + VFS (all done by session 3).
- Needs the heat + meta hooks to be meaningful, so later is better.
- First-session network commands can be implemented unconditionally, and
  retroactively gated by the Toolkit when it lands. (Sessions 7 and 9
  will coordinate this.)

CLAUDE.md session order should be updated when this spec is accepted —
see "open tasks" below.

---

## Design Notes

- **Baseline commands are never gated.** `ls`, `cd`, `cat`, `ssh`,
  `ping`, `curl`, `apt` itself — always installed. Gating these would
  make the game tedious.
- **Every unlock is a moment.** Breach animation, audio cue, ASCII for
  first-time installs. Subsequent installs get a lighter celebration.
- **Failures are rare, not common.** Default poison rates stay low until
  mid-game escalation. The goal is *unease*, not frustration.
- **The catalog is data, not code** — consistent with Principle #3 in
  CLAUDE.md. Adding a new tool = writing a YAML.
- **No package manager drama in the tutorial.** The first few unlocks
  should feel like reward, not puzzle. Puzzle comes when `gpg` enters
  the picture.
- **Everything diegetic.** Wallet, bandwidth, sources.list — if it's a
  mechanic, it exists as a file in the VFS. Players can `cat` their
  state.

---

## Open Tasks (post-spec-acceptance)

- [ ] Update CLAUDE.md: session order (insert toolkit after heat), top-level filesystem layout (add `data/packages/`, `systems/toolkit.py`, `commands/packaging.py`)
- [ ] Update `docs/SESSION_GUIDE.md` with the new session
- [ ] Draft the 14 package YAMLs in `data/packages/` (5 apt + 9 shadow)
- [ ] Write `tests/test_systems/test_toolkit.py` skeleton

## Tests: `tests/test_systems/test_toolkit.py`
- Test package load from YAML
- Test `is_installed` + baseline commands
- Test `install` resolves dependencies in correct order
- Test bandwidth + wallet deduction
- Test install refused on insufficient funds/bandwidth
- Test shadow refuses while `shadow_enabled = False`
- Test sources.list watcher flips `shadow_enabled`
- Test poison rolls respect escalation + verified flag
- Test `verify` requires `gpg` installed
- Test events emitted on each operation
- Test `shadow commit` applies discount
- Test `remove` refuses when other packages depend
