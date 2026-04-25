# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for H@ck3r-Z0rk."""

from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "hackerzork" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # All game data — fonts, sounds, YAML, ASCII art
        (str(ROOT / "hackerzork" / "data"), "hackerzork/data"),
    ],
    hiddenimports=[
        # pygame sub-modules PyInstaller often misses
        "pygame",
        "pygame.mixer",
        "pygame.mixer_music",
        "pygame.font",
        "pygame.image",
        "pygame.time",
        "pygame.event",
        "pygame.display",
        "pygame._sdl2",
        # rich internals
        "rich",
        "rich.console",
        "rich.text",
        "rich.markup",
        "rich.style",
        "rich.theme",
        "rich.segment",
        "rich.color",
        "rich.progress",
        "rich.live",
        "rich.panel",
        "rich.table",
        "rich.syntax",
        "rich.traceback",
        # pyfiglet
        "pyfiglet",
        "pyfiglet.fonts",
        # yaml
        "yaml",
        # textual (only imported if TUI widgets used)
        "textual",
        # hackerzork package itself — ensure all sub-packages collected
        "hackerzork",
        "hackerzork.engine",
        "hackerzork.systems",
        "hackerzork.commands",
        "hackerzork.effects",
        "hackerzork.audio",
        "hackerzork.meta",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dev / test deps — keep the bundle lean
        "pytest",
        "mypy",
        "ruff",
        "IPython",
        "matplotlib",
        "numpy",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir — no single-file extraction lag
    name="HackerZork",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # upx can break pygame binaries on macOS
    console=True,            # terminal game — must be True
    disable_windowed_traceback=False,
    argv_emulation=False,    # macOS: don't intercept Open Document events
    target_arch=None,        # native arch (arm64 on Apple Silicon)
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HackerZork",
)
