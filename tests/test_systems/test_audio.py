"""Tests for hackerzork/audio/ — mixer, ambient, sfx, reactive.

All tests run with audio disabled (no pygame required).
The contract under test: the API is callable, state is tracked correctly,
and missing sound files / absent pygame never raise exceptions.
"""
from __future__ import annotations

import pytest

from hackerzork.audio.mixer import AudioMixer, _heat_state
from hackerzork.audio.ambient import AmbientManager, AMBIENT_TRACKS
from hackerzork.audio.sfx import SFXTrigger, SFX_MAP
from hackerzork.audio.reactive import ReactiveAudio, heat_to_state, REACTIVE_TRACKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mixer() -> AudioMixer:
    """Return a disabled mixer — no pygame, no crash."""
    return AudioMixer(enabled=False)


# ---------------------------------------------------------------------------
# AudioMixer — init and basic state
# ---------------------------------------------------------------------------

class TestAudioMixerInit:
    def test_disabled_mixer_not_initialized(self):
        m = _mixer()
        assert not m.is_initialized
        assert m.enabled is False

    def test_enabled_flag_respected(self):
        m = AudioMixer(enabled=False)
        assert m.enabled is False

    def test_default_reactive_state(self):
        m = _mixer()
        assert m.reactive_state == "safe"

    def test_no_current_ambient_on_init(self):
        m = _mixer()
        assert m.current_ambient is None

    def test_no_current_music_on_init(self):
        m = _mixer()
        assert m.current_music is None


# ---------------------------------------------------------------------------
# AudioMixer — volume controls (state only, no pygame)
# ---------------------------------------------------------------------------

class TestAudioMixerVolume:
    def test_set_master_volume(self):
        m = _mixer()
        m.set_master_volume(0.5)
        assert m._master_volume == 0.5

    def test_master_volume_clamped_low(self):
        m = _mixer()
        m.set_master_volume(-1.0)
        assert m._master_volume == 0.0

    def test_master_volume_clamped_high(self):
        m = _mixer()
        m.set_master_volume(99.0)
        assert m._master_volume == 1.0

    def test_set_layer_volume_ambient(self):
        m = _mixer()
        m.set_layer_volume("ambient", 0.3)
        from hackerzork.audio.mixer import _LAYER_AMBIENT
        assert m._layer_volumes[_LAYER_AMBIENT] == pytest.approx(0.3)

    def test_set_layer_volume_unknown_layer_no_crash(self):
        m = _mixer()
        m.set_layer_volume("nonexistent", 0.5)  # should not raise

    def test_layer_volume_clamped(self):
        m = _mixer()
        m.set_layer_volume("music", 2.0)
        from hackerzork.audio.mixer import _LAYER_MUSIC
        assert m._layer_volumes[_LAYER_MUSIC] == 1.0

    def test_mute_sets_flag(self):
        m = _mixer()
        m.mute()
        assert m._muted is True

    def test_unmute_clears_flag(self):
        m = _mixer()
        m.mute()
        m.unmute()
        assert m._muted is False


# ---------------------------------------------------------------------------
# AudioMixer — no-op calls on disabled mixer
# ---------------------------------------------------------------------------

class TestAudioMixerDisabledNoCrash:
    def test_set_ambient_no_crash(self):
        m = _mixer()
        m.set_ambient("ambient_default")

    def test_stop_ambient_no_crash(self):
        m = _mixer()
        m.stop_ambient()

    def test_play_sfx_no_crash(self):
        m = _mixer()
        m.play_sfx("sfx_key_click")

    def test_play_diegetic_no_crash(self):
        m = _mixer()
        m.play_diegetic("sfx_terminal_beep")

    def test_set_reactive_state_no_crash(self):
        m = _mixer()
        m.set_reactive_state(75.0)

    def test_play_music_no_crash(self):
        m = _mixer()
        m.play_music("boss_track")

    def test_stop_music_no_crash(self):
        m = _mixer()
        m.stop_music()

    def test_corrupt_audio_no_crash(self):
        m = _mixer()
        m.corrupt_audio()

    def test_shutdown_no_crash(self):
        m = _mixer()
        m.shutdown()

    def test_double_shutdown_no_crash(self):
        m = _mixer()
        m.shutdown()
        m.shutdown()


# ---------------------------------------------------------------------------
# AudioMixer — reactive state tracking (disabled mixer still tracks state)
# ---------------------------------------------------------------------------

class TestAudioMixerReactiveState:
    def test_safe_at_zero_heat(self):
        m = _mixer()
        m.set_reactive_state(0.0)
        assert m.reactive_state == "safe"

    def test_monitored_at_25(self):
        m = _mixer()
        m.set_reactive_state(25.0)
        assert m.reactive_state == "monitored"

    def test_active_response_at_50(self):
        m = _mixer()
        m.set_reactive_state(50.0)
        assert m.reactive_state == "active_response"

    def test_hunted_at_75(self):
        m = _mixer()
        m.set_reactive_state(75.0)
        assert m.reactive_state == "hunted"

    def test_critical_at_90(self):
        m = _mixer()
        m.set_reactive_state(90.0)
        assert m.reactive_state == "critical"

    def test_state_does_not_regress_without_change(self):
        m = _mixer()
        m.set_reactive_state(50.0)
        m.set_reactive_state(50.0)
        assert m.reactive_state == "active_response"


# ---------------------------------------------------------------------------
# _heat_state helper
# ---------------------------------------------------------------------------

class TestHeatState:
    def test_zero_is_safe(self):
        assert _heat_state(0.0) == "safe"

    def test_24_is_safe(self):
        assert _heat_state(24.9) == "safe"

    def test_25_is_monitored(self):
        assert _heat_state(25.0) == "monitored"

    def test_50_is_active_response(self):
        assert _heat_state(50.0) == "active_response"

    def test_75_is_hunted(self):
        assert _heat_state(75.0) == "hunted"

    def test_90_is_critical(self):
        assert _heat_state(90.0) == "critical"

    def test_100_is_critical(self):
        assert _heat_state(100.0) == "critical"


# ---------------------------------------------------------------------------
# AmbientManager
# ---------------------------------------------------------------------------

class TestAmbientManager:
    def test_default_context_on_init(self):
        m = _mixer()
        am = AmbientManager(m)
        assert am.current_context == "default"

    def test_set_context_changes_state(self):
        m = _mixer()
        am = AmbientManager(m)
        am.set_context("shadow")
        assert am.current_context == "shadow"

    def test_set_same_context_no_change(self):
        m = _mixer()
        am = AmbientManager(m)
        am.set_context("default")
        assert am.current_context == "default"  # no double-transition

    def test_notify_flag_triggers_shadow(self):
        m = _mixer()
        am = AmbientManager(m)
        am.notify_flag("shadow_unlocked")
        assert am.current_context == "shadow"

    def test_notify_flag_triggers_oracle(self):
        m = _mixer()
        am = AmbientManager(m)
        am.notify_flag("kit_committed_oracle")
        assert am.current_context == "oracle"

    def test_notify_unknown_flag_no_crash(self):
        m = _mixer()
        am = AmbientManager(m)
        am.notify_flag("nonexistent_flag")

    def test_all_track_keys_in_catalogue(self):
        for key in ["default", "connected", "shadow", "oracle", "compromised", "critical"]:
            assert key in AMBIENT_TRACKS

    def test_context_switch_no_crash_disabled_mixer(self):
        m = _mixer()
        am = AmbientManager(m)
        for ctx in AMBIENT_TRACKS:
            am.set_context(ctx)
        # Should not raise


# ---------------------------------------------------------------------------
# SFXTrigger
# ---------------------------------------------------------------------------

class TestSFXTrigger:
    def test_trigger_known_event_no_crash(self):
        m = _mixer()
        sfx = SFXTrigger(m)
        sfx.trigger("keystroke")

    def test_trigger_unknown_event_no_crash(self):
        m = _mixer()
        sfx = SFXTrigger(m)
        sfx.trigger("totally_made_up_event")

    def test_on_event_handler_no_crash(self):
        m = _mixer()
        sfx = SFXTrigger(m)
        sfx.on_event("command_execute")

    def test_sfx_map_covers_key_events(self):
        required = [
            "keystroke", "command_execute", "command_error",
            "scan_start", "scan_complete", "ssh_connect",
            "exploit_success", "exploit_fail",
            "package_installed", "kit_committed",
            "surveillance_discovered", "surveillance_alert",
            "skynet_process_killed", "boot_start",
        ]
        for ev in required:
            assert ev in SFX_MAP, f"Missing SFX mapping for event: {ev}"

    def test_bind_events_no_crash_with_mock(self):
        m = _mixer()
        sfx = SFXTrigger(m)

        class MockEvents:
            def on(self, name, handler):
                pass

        sfx.bind_events(MockEvents())

    def test_all_sfx_values_are_strings(self):
        for k, v in SFX_MAP.items():
            assert isinstance(v, str), f"SFX_MAP[{k!r}] is not a string"


# ---------------------------------------------------------------------------
# ReactiveAudio
# ---------------------------------------------------------------------------

class TestReactiveAudio:
    def test_default_state_safe(self):
        m = _mixer()
        ra = ReactiveAudio(m)
        assert ra.current_state == "safe"

    def test_heat_changes_state(self):
        m = _mixer()
        ra = ReactiveAudio(m)
        ra.on_heat_changed(heat=30.0)
        assert ra.current_state == "monitored"

    def test_heat_threshold_crossed_handler(self):
        m = _mixer()
        ra = ReactiveAudio(m)
        ra.on_heat_threshold_crossed(level=75.0)
        assert ra.current_state == "hunted"

    def test_bind_events_no_crash(self):
        m = _mixer()
        ra = ReactiveAudio(m)

        class MockEvents:
            def on(self, name, handler):
                pass

        ra.bind_events(MockEvents())

    def test_all_reactive_states_in_tracks(self):
        for state in ["safe", "monitored", "active_response", "hunted", "critical"]:
            assert state in REACTIVE_TRACKS

    def test_heat_to_state_boundaries(self):
        assert heat_to_state(0.0)  == "safe"
        assert heat_to_state(25.0) == "monitored"
        assert heat_to_state(50.0) == "active_response"
        assert heat_to_state(75.0) == "hunted"
        assert heat_to_state(90.0) == "critical"


# ---------------------------------------------------------------------------
# Integration: mixer + reactive + sfx round-trip (all disabled)
# ---------------------------------------------------------------------------

class TestAudioIntegration:
    def test_full_heat_escalation_no_crash(self):
        m = _mixer()
        ra = ReactiveAudio(m)
        sfx = SFXTrigger(m)

        for heat in [0, 25, 50, 75, 90, 100]:
            ra.on_heat_changed(heat=float(heat))
            sfx.trigger("heat_monitored")

    def test_ambient_context_switch_with_sfx(self):
        m = _mixer()
        am = AmbientManager(m)
        sfx = SFXTrigger(m)

        am.set_context("shadow")
        sfx.trigger("shadow_unlocked")
        am.notify_flag("shadow_unlocked")

    def test_corrupt_audio_during_reactive(self):
        m = _mixer()
        ra = ReactiveAudio(m)
        ra.on_heat_changed(heat=90.0)
        m.corrupt_audio()

    def test_mute_during_reactive_no_crash(self):
        m = _mixer()
        ra = ReactiveAudio(m)
        m.mute()
        ra.on_heat_changed(heat=50.0)
        m.unmute()

    def test_shutdown_cleans_up(self):
        m = _mixer()
        m.set_ambient("ambient_default")
        m.shutdown()
        assert not m.is_initialized
