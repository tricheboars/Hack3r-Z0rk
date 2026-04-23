"""H@ck3r-Z0rk — Entry point."""
from __future__ import annotations

import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hackerzork",
        description="H@ck3r-Z0rk — A cyberpunk hacking text adventure",
    )
    parser.add_argument(
        "--no-audio", action="store_true", help="Disable audio playback"
    )
    parser.add_argument(
        "--no-effects", action="store_true", help="Disable visual effects"
    )
    parser.add_argument(
        "--no-meta", action="store_true", help="Disable fourth-wall effects"
    )
    parser.add_argument(
        "--load", type=str, default=None, help="Load a save file"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Late import so arg parsing is fast
    from hackerzork.game import Game

    game = Game(
        audio_enabled=not args.no_audio,
        effects_enabled=not args.no_effects,
        meta_enabled=not args.no_meta,
        debug=args.debug,
        save_file=args.load,
    )

    try:
        game.run()
    except KeyboardInterrupt:
        game.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
