# Audio Guide — H@ck3r-Z0rk

This is the living reference for every sound and music asset in the game.
Use it to:

- decide what format/spec a file needs before sourcing it
- track what's been submitted and where it stands (inventory at the bottom)
- know how we test a track before it lands in `hackerzork/data/`

Keep this file up to date — when Patrick drops a track, the file goes in
`hackerzork/data/sounds/` or `hackerzork/data/music/` and a row gets added
to the inventory table with a status.

---

## Format spec — the short version

| Category | Format | Sample rate | Bit depth | Channels | Bitrate | Typical length |
|---|---|---|---|---|---|---|
| Diegetic SFX (one-shots) | **.wav** | 44.1 kHz | 16-bit | mono | n/a | < 2 s |
| Ambient drones (loops) | **.ogg** Vorbis | 44.1 kHz | 16-bit | stereo | 128–160 kbps | 30 s – 3 min |
| Music / EDM (triggered) | **.ogg** Vorbis | 44.1 kHz | 16-bit | stereo | ~192 kbps | 1 – 5 min |
| Boot / system beeps | **.wav** | 44.1 kHz | 16-bit | mono | n/a | < 3 s |

**Hard rules**

- All files **44.1 kHz**. Don't mix sample rates — `pygame.mixer` initializes
  at one rate and resampling on the fly is ugly.
- All files **16-bit**. Not 24-bit, not float32.
- **No `.mp3`.** Pygame technically supports it but MP3 looping is flaky and
  licensing is murkier than Vorbis. Convert before submitting (see cheat
  sheet below).
- Loopable tracks need **clean, click-free loop points**. See testing below.

---

## Categories in detail

The spec in `docs/specs/06_audio.md` defines four layers. This guide maps
each layer to the files we need.

### Layer 1 — Ambient drones

Continuous loops that set the emotional tone. One per reactive state.
All stereo `.ogg`.

| State | Feel | Triggered by |
|---|---|---|
| `ambient_safe` | Calm dark room, distant hum | default / heat < 25 |
| `ambient_monitored` | Subtle tension, low pulse | heat 25–49 |
| `ambient_active` | Pulsing bass, faster | heat 50–74 |
| `ambient_hunted` | Rhythmic urgency, alarm tail | heat 75–89 |
| `ambient_critical` | Full alarm, heartbeat bass | heat 90+ |

These should all **loop seamlessly** and be in the same key / tempo family
so crossfades don't clash.

### Layer 2 — Diegetic SFX

Short one-shots, `.wav`, triggered by player actions. Table copied from
the audio spec so submissions can be checked off here:

| Filename | Action |
|---|---|
| `keystroke.wav` | Mechanical key click — very short (~50 ms) |
| `terminal_beep.wav` | Soft beep on command execute |
| `error_buzz.wav` | Short harsh buzz on bad input |
| `modem_dial.wav` | Modem / dial-up for scan start |
| `data_chime.wav` | Data received chime on scan complete |
| `tension_build.wav` | Short build-up under exploit attempt |
| `breach.wav` | Bass drop on successful exploit |
| `reject_buzz.wav` | Harsh rejection on failed exploit |
| `ssh_connect.wav` | Connection established tone |
| `notify_ping.wav` | IRC / message notification |
| `warn_siren_low.wav` | Heat threshold warning (25) |
| `warn_siren_mid.wav` | Heat threshold warning (50) |
| `warn_siren_high.wav` | Heat threshold warning (75+) |
| `glitch_short.wav` | SkyNet micro-intervention |
| `glitch_long.wav` | SkyNet major intervention |
| `post_beep.wav` | POST beep |
| `drive_spin.wav` | Drive spin-up for boot |

### Layer 3 — Reactive

No dedicated files — this layer is built by crossfading between the
ambient drones above based on heat level. Implemented in
`hackerzork/audio/reactive.py`.

### Layer 4 — Music

Full tracks, `.ogg`, triggered by story/event beats. We'll add one row
per track as they're scored:

| Filename | When it plays |
|---|---|
| `_tbd` | boss / major exploit drop |
| `_tbd` | SkyNet reveal |
| `_tbd` | end-sequence |

---

## Naming convention

- `snake_case.ext`, lowercase only
- Descriptive over clever: `modem_dial.wav`, not `old_school_hack_sound.wav`
- Variants get a numeric suffix: `keystroke_01.wav`, `keystroke_02.wav` — the
  mixer will pick at random to avoid audible repetition
- Prefix music with `music_`: `music_breach_drop.ogg`
- Prefix ambient with `ambient_`: `ambient_hunted.ogg`

---

## Licensing

Stick to **CC0** (public domain) or **CC-BY** (attribution required) so we
can distribute the game. Avoid CC-BY-SA (viral) and CC-NC (blocks any
commercial distribution, even future).

For every CC-BY track, record the attribution in `data/music/CREDITS.md`
(or `data/sounds/CREDITS.md`) when we add the inventory row.

**Good sources:**

- [freesound.org](https://freesound.org) — filter by CC0 licence
- [Sonniss GameAudioGDC bundles](https://sonniss.com/gameaudiogdc) — huge,
  royalty-free, free download once a year
- [opengameart.org](https://opengameart.org) — mixed licences, check each
- [zapsplat.com](https://zapsplat.com) — free tier, attribution required

---

## Testing a submitted file

When Patrick drops a file, run these checks before accepting it.

### 1. Metadata — is it the right format?

```bash
ffprobe -v quiet -show_streams -of json hackerzork/data/sounds/YOUR_FILE.wav \
  | jq '.streams[0] | {codec_name, sample_rate, channels, bits_per_sample, duration}'
```

Acceptance:

- `codec_name`: `pcm_s16le` for `.wav`, `vorbis` for `.ogg`
- `sample_rate`: `"44100"`
- `channels`: 1 for SFX, 2 for ambient/music
- `bits_per_sample`: 16 (wav only — ogg doesn't report this)

### 2. Levels — is it too loud or too quiet?

We target roughly **-16 LUFS** integrated for music/ambient and peak
**-1 dBFS** for SFX (leaves headroom, no clipping).

```bash
ffmpeg -i hackerzork/data/music/YOUR_FILE.ogg -af ebur128=peak=true -f null - 2>&1 \
  | grep -E 'Integrated|Peak:'
```

### 3. Loop points — does it click at the seam?

Concatenate it to itself twice, listen to the joins:

```bash
ffmpeg -i loop.ogg -filter_complex "[0][0][0]concat=n=3:v=0:a=1" -y /tmp/loop_test.ogg
afplay /tmp/loop_test.ogg   # macOS
```

If there's a pop, the submitter needs to re-export with a zero-crossing
fade at the loop boundary.

### 4. In-game check (once `audio/mixer.py` is built)

```bash
.venv/bin/python -m hackerzork.audio.mixer --preview hackerzork/data/sounds/YOUR_FILE.wav
```

Not yet implemented — will land with session 9.

---

## Conversion cheat sheet

Wrong format? These one-liners normalize most things.

```bash
# MP3 → OGG Vorbis (~192 kbps)
ffmpeg -i in.mp3 -c:a libvorbis -q:a 5 out.ogg

# Anything → 16-bit 44.1 kHz mono WAV (for SFX)
ffmpeg -i in.wav -ac 1 -ar 44100 -sample_fmt s16 out.wav

# Anything → 16-bit 44.1 kHz stereo OGG (for ambient/music)
ffmpeg -i in.flac -ac 2 -ar 44100 -c:a libvorbis -q:a 5 out.ogg

# Trim silence from start and end (useful for SFX)
ffmpeg -i in.wav -af "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_silence=0.05:start_threshold=-50dB,areverse" out.wav

# Normalize loudness to -16 LUFS
ffmpeg -i in.ogg -af loudnorm=I=-16:LRA=11:TP=-1 -c:a libvorbis -q:a 5 out.ogg
```

`-q:a 5` is roughly 160 kbps Vorbis. Use `-q:a 6` (~192 kbps) for music,
`-q:a 4` (~128 kbps) for ambient.

---

## Inventory

Status legend: **pending** = received, not yet reviewed • **accepted** =
passes all checks, in use • **rework** = needs re-export • **wishlist** =
category that still needs a file.

### SFX

| Filename | Category | Status | Licence | Notes |
|---|---|---|---|---|
| `keystroke.wav` | SFX | wishlist | — | short, ~50 ms |
| `terminal_beep.wav` | SFX | wishlist | — | |
| `error_buzz.wav` | SFX | wishlist | — | |
| `modem_dial.wav` | SFX | wishlist | — | ~2 s, dial-up nostalgia |
| `data_chime.wav` | SFX | wishlist | — | |
| `breach.wav` | SFX | wishlist | — | bass-drop adjacent |
| `reject_buzz.wav` | SFX | wishlist | — | |
| `ssh_connect.wav` | SFX | wishlist | — | |
| `notify_ping.wav` | SFX | wishlist | — | |

### Ambient

| Filename | State | Status | Licence | Notes |
|---|---|---|---|---|
| `ambient_safe.ogg` | safe | wishlist | — | stereo, loops |
| `ambient_monitored.ogg` | monitored | wishlist | — | |
| `ambient_active.ogg` | active | wishlist | — | |
| `ambient_hunted.ogg` | hunted | wishlist | — | |
| `ambient_critical.ogg` | critical | wishlist | — | |

### Music

| Filename | Cue | Status | Licence | Notes |
|---|---|---|---|---|
| _(none yet)_ | | | | |

---

## How to submit

1. Drop the file into `hackerzork/data/sounds/` or `hackerzork/data/music/`.
   (These dirs are gitignored for `.wav/.ogg/.mp3` — we don't commit the
   binaries themselves, only this guide's inventory.)
2. Tell me the filename + where you got it (source URL + licence).
3. I'll run the checks above, update the inventory row, and either accept
   or flag it for rework.
