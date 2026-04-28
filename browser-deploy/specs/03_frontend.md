# Spec 03 — Frontend (`index.html` + `term.js`)

## Purpose

A single self-contained HTML page that renders a full-screen terminal emulator
connected to the game server over WebSocket. No build step, no npm — just
vanilla JS + xterm.js loaded from CDN.

## Files

- `frontend/index.html` — the page
- `frontend/term.js` — all WebSocket + xterm.js logic

## Libraries (CDN)

```html
<!-- xterm.js terminal emulator -->
<script src="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.3.0/lib/xterm.js"></script>
<link  href="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.3.0/css/xterm.css" rel="stylesheet" />

<!-- xterm addons -->
<script src="https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.10.0/lib/addon-fit.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@xterm/addon-web-links@0.11.0/lib/addon-web-links.js"></script>
```

## Visual Design

- Full-screen terminal, no chrome/UI around it
- Black background (#020d02) matching the website
- Green phosphor text (#00ff41)
- Cursor: block, blinking
- Font: `'Share Tech Mono', 'Courier New', monospace` (Google Fonts)
- xterm.js theme:
  ```js
  {
    background: '#020d02',
    foreground: '#00ff41',
    cursor:     '#00ff41',
    cursorAccent: '#020d02',
    black:   '#020d02',  green:   '#00ff41',
    red:     '#ff2222',  yellow:  '#ffb700',
    blue:    '#0055ff',  magenta: '#cc44ff',
    cyan:    '#00ffff',  white:   '#d0ffd0',
    brightBlack:   '#1a3d1a',  brightGreen:   '#00ff41',
    brightRed:     '#ff4444',  brightYellow:  '#ffd700',
    brightBlue:    '#4488ff',  brightMagenta: '#ee66ff',
    brightCyan:    '#44ffff',  brightWhite:   '#ffffff',
  }
  ```

## Behavior

### Connection

1. On page load, open WebSocket to `ws://` or `wss://` (auto-detect from
   `window.location.protocol`)
2. Show "Connecting..." in the terminal while handshake completes
3. On open: terminal becomes interactive
4. On close: show reconnect button
5. On error: show error message

### Input handling

- All keystrokes → collect into a line buffer
- Send the line to the server on Enter
- Handle Backspace locally (delete from buffer, send BS to xterm)
- Do NOT send individual keypresses — send complete lines
- Tab key: send `\t` to server (server handles completion) OR implement
  local tab-complete later

### Output handling

```js
ws.onmessage = (event) => {
  const msg = event.data;
  if (msg.startsWith('{')) {
    handleSideChannelEvent(JSON.parse(msg));
  } else {
    term.write(msg);   // xterm.js handles ANSI natively
  }
};
```

### Side-channel events

```js
function handleSideChannelEvent(evt) {
  switch (evt.name) {
    case 'skynet_alert':   triggerSkyNetAlert(evt.payload); break;
    case 'audio_cue':      playAudioCue(evt.payload.sound); break;
    case 'glitch':         triggerGlitch(evt.payload.duration_ms); break;
    case 'heat_update':    updateHeatDisplay(evt.payload.heat); break;
  }
}
```

### HUD overlay (optional — implement last)

A subtle overlay in the top-right corner showing:
```
HEAT: 47.3 ░░░░░███████░░░░░
SESSION: 00:14:22
```
Updated via `heat_update` side-channel events.

### Glitch effect

On `glitch` event, briefly apply a CSS class that distorts the terminal:
```css
.glitch-active {
  animation: crt-glitch 0.1s steps(2) forwards;
  filter: hue-rotate(90deg) brightness(1.5);
}
```

### Audio

Web Audio API — ambient drone loop + SFX on events.
Use `AudioContext` with oscillators for ambient drone (no files needed).
SFX clips can be base64-encoded data URIs embedded in the JS.
Keep this minimal for initial build — can expand later.

### Resize handling

```js
const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);
window.addEventListener('resize', () => fitAddon.fit());
fitAddon.fit();
// Send terminal size to server after fit
ws.send(JSON.stringify({type: 'resize', cols: term.cols, rows: term.rows}));
```

## index.html structure

```html
<!DOCTYPE html>
<html>
<head>
  <title>H@CK3R-Z0RK // TERMINAL</title>
  <!-- Google Font, xterm.js CSS -->
  <style>/* full-screen black, terminal fills viewport */</style>
</head>
<body>
  <div id="terminal"></div>
  <!-- optional HUD overlay -->
  <div id="hud" class="hud-overlay"></div>
  <!-- scripts -->
  <script src="...xterm.js CDN..."></script>
  <script src="term.js"></script>
</body>
</html>
```

## Notes for Claude Code

- Keep `term.js` as vanilla ES2020 (no modules, no bundler)
- The WebSocket URL should be configurable via a `data-ws-url` attribute on
  `<div id="terminal">` so it works in both dev (localhost) and prod
- Test in Chrome and Firefox before declaring done
