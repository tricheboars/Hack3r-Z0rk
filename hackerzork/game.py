"""H@ck3r-Z0rk — Game orchestrator."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GameConfig:
    """Global game configuration."""

    audio_enabled: bool = True
    effects_enabled: bool = True
    meta_enabled: bool = True
    debug: bool = False
    save_file: str | None = None


class Game:
    """Main game class — orchestrates all systems.

    This is the top-level object that initializes and connects:
    - Event bus (inter-system communication)
    - Virtual filesystem (player's OS)
    - Network simulation (the internet to hack)
    - Heat system (trace/exposure tracking)
    - Command parser & registry
    - Shell (the REPL)
    - Audio mixer
    - Effects engine
    - Meta engine (SkyNet)
    - Comms system (IRC + DMs)
    - Save/load
    """

    def __init__(
        self,
        audio_enabled: bool = True,
        effects_enabled: bool = True,
        meta_enabled: bool = True,
        debug: bool = False,
        save_file: str | None = None,
    ) -> None:
        self.config = GameConfig(
            audio_enabled=audio_enabled,
            effects_enabled=effects_enabled,
            meta_enabled=meta_enabled,
            debug=debug,
            save_file=save_file,
        )

        # Systems will be initialized in boot()
        self._booted = False

    def boot(self) -> None:
        """Initialize all game systems in dependency order.

        Order matters:
        1. Event bus (everything depends on this)
        2. State machine
        3. Virtual filesystem
        4. Network simulation
        5. Heat system
        6. Comms system
        7. Command registry + parser
        8. Audio mixer
        9. Effects engine
        10. Meta engine (SkyNet — needs everything else)
        11. Shell (needs commands registered)
        """
        # TODO: Initialize each system
        # TODO: Load save file if provided
        # TODO: Register all commands
        # TODO: Wire up event listeners
        self._booted = True

    def run(self) -> None:
        """Main game loop."""
        if not self._booted:
            self.boot()

        # TODO: Play boot sequence animation
        # TODO: Start shell REPL
        print("H@ck3r-Z0rk v0.1.0 — Engine scaffolding")
        print("Game systems not yet implemented.")
        print("Run 'claude code' sessions to build each module.")
        print("See docs/specs/ for module specifications.")
        print("See CLAUDE.md for architecture guide.")

    def shutdown(self) -> None:
        """Clean shutdown of all systems."""
        # TODO: Save state
        # TODO: Stop audio
        # TODO: Cleanup
        pass
