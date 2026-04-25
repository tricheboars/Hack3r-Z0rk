#!/usr/bin/env bash
# Build HackerZork.app — run from project root with the venv active.
# Usage: ./build_app.sh
set -euo pipefail

APP_NAME="HackerZork"
BUNDLE="dist/${APP_NAME}.app"

# ── 1. Ensure PyInstaller is present ────────────────────────────────────────
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# ── 2. Clean previous build ─────────────────────────────────────────────────
rm -rf "build" "dist"

# ── 3. Run PyInstaller ───────────────────────────────────────────────────────
echo "Building with PyInstaller..."
pyinstaller HackerZork.spec

# ── 4. Create the .app bundle structure ─────────────────────────────────────
echo "Creating ${APP_NAME}.app..."
mkdir -p "${BUNDLE}/Contents/MacOS"
mkdir -p "${BUNDLE}/Contents/Resources"

# Copy the entire PyInstaller onedir bundle inside the .app
cp -r "dist/${APP_NAME}/" "${BUNDLE}/Contents/MacOS/game/"

# ── 5. Write Info.plist ──────────────────────────────────────────────────────
cat > "${BUNDLE}/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>H@ck3r-Z0rk</string>
    <key>CFBundleIdentifier</key>
    <string>com.hackerzork.app</string>
    <key>CFBundleVersion</key>
    <string>0.1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundleExecutable</key>
    <string>launch</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# ── 6. Write the Terminal launcher script ───────────────────────────────────
# macOS executes this when the user double-clicks the .app.
# It opens a new Terminal window and runs the game inside it.
LAUNCHER="${BUNDLE}/Contents/MacOS/launch"
cat > "${LAUNCHER}" <<'LAUNCHER_SCRIPT'
#!/usr/bin/env bash
# Resolve the game binary path relative to this script's location.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GAME="${SCRIPT_DIR}/game/HackerZork"

# Open a new Terminal window and run the game.
osascript <<EOF
tell application "Terminal"
    activate
    set w to do script "exec '${GAME}'"
    set custom title of w to "H@ck3r-Z0rk"
end tell
EOF
LAUNCHER_SCRIPT
chmod +x "${LAUNCHER}"

# ── 7. Done ──────────────────────────────────────────────────────────────────
echo ""
echo "✓ Built: ${BUNDLE}"
echo ""
echo "To run:  open ${BUNDLE}"
echo "  or drag HackerZork.app from dist/ to your Applications folder."
