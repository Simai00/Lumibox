"""Tests für den BoxController: Figur auflegen und abnehmen."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.components.persistent_notification import (
    _async_get_or_create_notifications,
)
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

from custom_components.home_tonie.box import BoxState

BOBO_URI = "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"
FEUERWEHR_URI = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"


async def _advance(hass, seconds: float) -> None:
    # _exact: async_fire_time_changed schlägt pauschal 0,5 s auf, was die
    # Prüfungen innerhalb der 1-s-Entprellung verfälschen würde.
    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_known_figure_plays_and_caps_volume(hass, box):
    await box.ctrl.tag_on("04-A1-B2-C3")
    assert ("set_volume", 0.4) in box.player.calls
    assert ("play", BOBO_URI) in box.player.calls
    assert box.player.calls.index(("set_volume", 0.4)) < box.player.calls.index(("play", BOBO_URI))
    assert box.led.shows == [("loading", 0), ("playing", 0)]
    assert box.ctrl.state is BoxState.PLAYING and box.ctrl.current_figure.name == "Bobo"


async def test_volume_below_max_is_not_changed(hass, box):
    box.player.volume = 0.2
    await box.ctrl.tag_on("04A1B2C3")
    assert not [c for c in box.player.calls if c[0] == "set_volume"]
    assert box.player.calls == [("play", BOBO_URI)]


async def test_removal_pauses_after_debounce(hass, box):
    await box.ctrl.tag_on("04A1B2C3")
    box.led.shows.clear()
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 0.5)
    assert ("pause",) not in box.player.calls
    assert box.ctrl.state is BoxState.PLAYING
    await _advance(hass, 1.1)
    assert box.player.calls[-1] == ("pause",)
    assert box.led.shows == [("paused", 0)]
    assert box.ctrl.state is BoxState.REMOVED
    assert box.ctrl.current_figure is None


async def test_flicker_within_debounce_is_ignored(hass, box):
    await box.ctrl.tag_on("04A1B2C3")
    calls_before = list(box.player.calls)
    shows_before = list(box.led.shows)
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 0.5)
    await box.ctrl.tag_on("04A1B2C3")
    await _advance(hass, 1.1)
    assert box.player.calls == calls_before
    assert box.led.shows == shows_before
    assert box.ctrl.state is BoxState.PLAYING
    assert box.ctrl.current_figure.name == "Bobo"


async def test_same_figure_resumes(hass, box):
    await box.ctrl.tag_on("04A1B2C3")
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 1.1)
    assert box.player.state == "paused"
    box.player.calls.clear()
    box.led.shows.clear()
    box.player.volume = 0.6  # Eltern haben aufgedreht
    await box.ctrl.tag_on("04A1B2C3")
    assert box.player.calls == [("set_volume", 0.4), ("resume",)]
    assert box.led.shows == [("playing", 0)]
    assert box.ctrl.state is BoxState.PLAYING
    assert box.ctrl.current_figure.name == "Bobo"


async def test_same_figure_restarts_if_player_changed(hass, box):
    await box.ctrl.tag_on("04A1B2C3")
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 1.1)
    box.player.media_content_id = "spotify://track/somethingElse"
    box.player.calls.clear()
    await box.ctrl.tag_on("04A1B2C3")
    assert ("play", BOBO_URI) in box.player.calls
    assert ("resume",) not in box.player.calls
    assert box.ctrl.state is BoxState.PLAYING


async def test_same_figure_restarts_if_player_not_paused(hass, box):
    await box.ctrl.tag_on("04A1B2C3")
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 1.1)
    box.player.state = "idle"
    box.player.calls.clear()
    await box.ctrl.tag_on("04A1B2C3")
    assert ("play", BOBO_URI) in box.player.calls
    assert ("resume",) not in box.player.calls


async def test_other_figure_starts_fresh(hass, box):
    await box.ctrl.tag_on("04A1B2C3")
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 1.1)
    box.player.calls.clear()
    await box.ctrl.tag_on("04B7C8D9")
    assert ("play", FEUERWEHR_URI) in box.player.calls
    assert ("resume",) not in box.player.calls
    assert box.ctrl.current_figure.name == "Feuerwehr"
    assert box.ctrl.state is BoxState.PLAYING


async def test_quick_swap_does_not_pause_new_figure(hass, box):
    await box.ctrl.tag_on("04A1B2C3")
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 0.3)
    await box.ctrl.tag_on("04B7C8D9")
    await _advance(hass, 1.1)
    play_b = box.player.calls.index(("play", FEUERWEHR_URI))
    assert ("pause",) not in box.player.calls[play_b:]
    assert ("pause",) not in box.player.calls
    assert box.ctrl.state is BoxState.PLAYING
    assert box.ctrl.current_figure.name == "Feuerwehr"


async def test_quick_swap_then_back_restarts(hass, box):
    """Nach einem schnellen Wechsel A→B→A wird A neu gestartet (kein Snapshot)."""
    await box.ctrl.tag_on("04A1B2C3")
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 0.3)
    await box.ctrl.tag_on("04B7C8D9")
    await box.ctrl.tag_off("04B7C8D9")
    await _advance(hass, 1.1)
    box.player.calls.clear()
    await box.ctrl.tag_on("04A1B2C3")
    assert ("play", BOBO_URI) in box.player.calls


async def test_quick_swap_to_unknown_pauses_old_figure(hass, box):
    """Wechsel auf ein unbekanntes Tag während der Entprellung: alte Figur wird angehalten."""
    await box.ctrl.tag_on("04A1B2C3")
    box.led.shows.clear()
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 0.3)
    await box.ctrl.tag_on("FFEE")
    assert box.player.calls[-1] == ("pause",)
    assert box.led.shows == [("paused", 0), ("unknown", 0)]
    assert box.ctrl.state is BoxState.IDLE
    assert box.ctrl.current_figure is None


async def test_unknown_figure_notifies(hass, box):
    await box.ctrl.tag_on("ff:ee")
    assert box.ctrl.last_unknown_uid == "FFEE"
    notifications = _async_get_or_create_notifications(hass)
    note = notifications["home_tonie_unknown_box_anna"]
    assert note["message"] == (
        "Neue Figur auf Box Anna erkannt (UID FFEE). Unter Einstellungen → Home Tonie → "
        "Figur hinzufügen anlegen, die UID ist vorausgefüllt."
    )
    assert box.led.shows == [("unknown", 0)]
    assert not [c for c in box.player.calls if c[0] == "play"]
    assert box.ctrl.state is BoxState.IDLE
    assert box.ctrl.current_figure is None
    assert box.unknown_uids == ["FFEE"]


async def test_unknown_tag_off_only_turns_led_off(hass, box):
    await box.ctrl.tag_on("FFEE")
    box.led.shows.clear()
    await box.ctrl.tag_off("FFEE")
    assert box.led.shows == []
    await _advance(hass, 1.1)
    assert box.led.shows == [("off", 0)]
    assert ("pause",) not in box.player.calls
    assert box.ctrl.state is BoxState.IDLE


async def test_player_error_on_play_sets_error(hass, box, caplog):
    box.player.available = False
    await box.ctrl.tag_on("04A1B2C3")
    assert box.led.shows[-1] == ("error", 0)
    assert box.ctrl.state is BoxState.IDLE
    assert box.ctrl.current_figure is None
    assert not box.player.calls
    assert "Bobo" in caplog.text


async def test_player_error_on_removal_does_not_raise(hass, box):
    await box.ctrl.tag_on("04A1B2C3")
    box.player.available = False
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 1.1)
    assert box.led.shows[-1] == ("error", 0)
    assert box.ctrl.state is BoxState.IDLE
    assert box.ctrl.current_figure is None
    # Player wieder da: nächstes Auflegen spielt normal.
    box.player.available = True
    box.player.calls.clear()
    await box.ctrl.tag_on("04A1B2C3")
    assert box.player.calls[-1] == ("play", BOBO_URI)
    assert box.led.shows[-1] == ("playing", 0)
    assert box.ctrl.state is BoxState.PLAYING


async def test_handle_event_dispatches_tags(hass, box):
    await box.ctrl.handle_event({"action": "tag_on", "uid": "04A1B2C3", "device_id": "dev_anna"})
    assert box.ctrl.state is BoxState.PLAYING
    await box.ctrl.handle_event({"action": "tag_off", "uid": "04A1B2C3"})
    await _advance(hass, 1.1)
    assert box.ctrl.state is BoxState.REMOVED
    await box.ctrl.handle_event({"action": "tag_on"})  # ohne UID: ignoriert
    await box.ctrl.handle_event({"action": "bogus"})
    assert box.ctrl.state is BoxState.REMOVED


async def test_listeners_notified(hass, box):
    count = 0

    def listener() -> None:
        nonlocal count
        count += 1

    def broken() -> None:
        raise RuntimeError("kaputt")

    box.ctrl.add_listener(broken)
    unsub = box.ctrl.add_listener(listener)
    await box.ctrl.tag_on("04A1B2C3")
    after_on = count
    assert after_on > 0
    await box.ctrl.tag_off("04A1B2C3")
    await _advance(hass, 1.1)
    after_off = count
    assert after_off > after_on
    await box.ctrl.tag_on("FFEE")
    assert count > after_off
    unsub()
    before = count
    await box.ctrl.tag_on("04B7C8D9")
    assert count == before


async def test_shutdown_cancels_debounce(hass, box):
    await box.ctrl.tag_on("04A1B2C3")
    await box.ctrl.tag_off("04A1B2C3")
    box.ctrl.async_shutdown()
    await _advance(hass, 1.1)
    assert ("pause",) not in box.player.calls


async def _fire_removal_with_slow_pause(hass, box) -> asyncio.Event:
    """A spielt, wird abgenommen; die Entprellung läuft ab, pause() hängt am Gate."""
    await box.ctrl.tag_on("04A1B2C3")
    await box.ctrl.tag_off("04A1B2C3")
    gate = asyncio.Event()
    box.player.pause_gate = gate
    # Kein async_block_till_done: Die Abnahme-Task hängt bewusst in pause().
    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=1.1))
    for _ in range(5):
        await asyncio.sleep(0)
    return gate


async def test_same_figure_back_during_slow_pause_resumes(hass, box):
    """Race (a): A kommt zurück, während pause() nach der Entprellung noch läuft."""
    gate = await _fire_removal_with_slow_pause(hass, box)
    tag_on = asyncio.create_task(box.ctrl.tag_on("04A1B2C3"))
    for _ in range(5):
        await asyncio.sleep(0)
    gate.set()
    await tag_on
    await hass.async_block_till_done()
    assert box.player.calls[-2:] == [("pause",), ("resume",)]
    assert box.led.shows[-1] == ("playing", 0)
    assert box.ctrl.state is BoxState.PLAYING
    assert box.ctrl.current_figure.name == "Bobo"


async def test_other_figure_during_slow_pause_keeps_playing(hass, box):
    """Race (b): B wird aufgelegt, während pause(A) noch läuft."""
    gate = await _fire_removal_with_slow_pause(hass, box)
    tag_on = asyncio.create_task(box.ctrl.tag_on("04B7C8D9"))
    for _ in range(5):
        await asyncio.sleep(0)
    gate.set()
    await tag_on
    await hass.async_block_till_done()
    assert box.player.calls[-1] == ("play", FEUERWEHR_URI)
    assert box.player.calls.index(("pause",)) < box.player.calls.index(("play", FEUERWEHR_URI))
    assert box.led.shows[-1] == ("playing", 0)
    assert box.ctrl.state is BoxState.PLAYING
    assert box.ctrl.current_figure.name == "Feuerwehr"


async def test_tag_on_queued_before_removal_task_wins(hass, box):
    """tag_on(A) steht vor der Abnahme-Task am Lock: Abnahme ist überholt, A spielt weiter."""
    await box.ctrl.tag_on("04A1B2C3")
    await box.ctrl.tag_off("04A1B2C3")
    calls_before = list(box.player.calls)
    async with box.ctrl._lock:  # Lock halten, damit beide warten müssen
        tag_on = asyncio.create_task(box.ctrl.tag_on("04A1B2C3"))
        await asyncio.sleep(0)  # tag_on wartet zuerst am Lock
        async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=1.1))
        for _ in range(5):
            await asyncio.sleep(0)
    await tag_on
    await hass.async_block_till_done()
    assert box.player.calls == calls_before  # kein pause, kein zweites play
    assert box.ctrl.state is BoxState.PLAYING
    assert box.ctrl.current_figure.name == "Bobo"


async def test_shutdown_cancels_running_removal(hass, box):
    gate = await _fire_removal_with_slow_pause(hass, box)
    box.ctrl.async_shutdown()
    await asyncio.sleep(0)
    gate.set()
    await hass.async_block_till_done()
    assert box.ctrl.state is BoxState.PLAYING  # Abnahme wurde abgebrochen
