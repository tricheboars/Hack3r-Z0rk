"""SFX trigger table — maps game events to sound effect names.

Sound files live in data/sounds/<name>.wav (16-bit/44.1kHz — see AUDIO_GUIDE.md).
Every trigger goes through AudioMixer.play_sfx() which degrades gracefully on
missing files, so adding entries here is always safe.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackerzork.audio.mixer import AudioMixer

# ---------------------------------------------------------------------------
# SFX catalogue
# ---------------------------------------------------------------------------

# event_name → sound_file_stem
# Short files (<1s) for terminal feedback; longer files for narrative moments.

SFX_MAP: dict[str, str] = {
    # Terminal / shell
    "keystroke":            "sfx_key_click",
    "command_execute":      "sfx_terminal_beep",
    "command_error":        "sfx_error_buzz",
    "tab_complete":         "sfx_tab_complete",
    "history_recall":       "sfx_key_click",

    # Network / hacking
    "scan_start":           "sfx_modem_dial",
    "scan_complete":        "sfx_data_chime",
    "ssh_connect":          "sfx_connection_tone",
    "ssh_disconnect":       "sfx_disconnect_tone",
    "exploit_attempt":      "sfx_tension_build",
    "exploit_success":      "sfx_breach",
    "exploit_fail":         "sfx_reject_buzz",
    "curl_response":        "sfx_data_chime",

    # Package / toolkit
    "package_installed":    "sfx_install_complete",
    "package_poisoned":     "sfx_poison_sting",
    "kit_committed":        "sfx_identity_lock",
    "shadow_unlocked":      "sfx_shadow_unlock",

    # Heat / surveillance
    "heat_monitored":       "sfx_warning_low",
    "heat_active_response": "sfx_warning_mid",
    "heat_hunted":          "sfx_warning_high",
    "heat_critical":        "sfx_alarm",
    "surveillance_alert":   "sfx_surveillance_ping",

    # SkyNet / meta
    "skynet_process_killed": "sfx_process_kill",
    "skynet_intervention":   "sfx_glitch_burst",
    "fourth_wall_break":     "sfx_static_burst",
    "glitch_burst":          "sfx_glitch_burst",
    "process_kill":          "sfx_process_kill",
    "surveillance_discovered": "sfx_surveillance_ping",

    # Boot
    "boot_start":           "sfx_boot_beep",
    "boot_complete":        "sfx_boot_ready",

    # IRC / comms
    "message_received":     "sfx_notify_ping",
    "message_sent":         "sfx_key_click",
}


class SFXTrigger:
    """Thin wrapper that maps event names to mixer.play_sfx() calls."""

    def __init__(self, mixer: "AudioMixer") -> None:
        self._mixer = mixer

    def trigger(self, event: str, volume: float = 1.0) -> None:
        """Play the SFX for an event. Silent if unmapped or file missing."""
        sound = SFX_MAP.get(event)
        if sound:
            self._mixer.play_sfx(sound, volume=volume)

    def on_event(self, event: str, **kwargs: object) -> None:
        """EventBus-compatible handler — pass directly to events.on()."""
        self.trigger(event)

    def bind_events(self, events: object) -> None:
        """Register all mapped events on an EventBus instance."""
        for event_name in SFX_MAP:
            try:
                events.on(event_name, self.on_event)
            except Exception:
                pass
