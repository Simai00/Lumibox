"""Tests für den BoxController: Taster und Encoder."""

from __future__ import annotations

import asyncio

from custom_components.lumibox.box import BoxState


BOBO_URI = "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"
TRACK = "spotify://track/3n3Ppam7vgaVa1iaRUc9Lp"


async def _playing(box):
    await box.ctrl.tag_on("04A1B2C3")
    box.player.media_content_id = TRACK
    box.player.calls.clear()
    box.led.shows.clear()


async def test_controls_ignored_without_figure(hass, box):
    for action in ("play_pause", "next", "prev", "rotate_cw", "rotate_ccw"):
        await box.ctrl.handle_event({"action": action})
    assert box.player.calls == []
    assert box.led.shows == []
    assert box.ctrl.state is BoxState.IDLE


async def test_controls_ignored_when_removed(hass, box):
    await _playing(box)
    box.ctrl._set(BoxState.REMOVED, None)
    for action in ("play_pause", "next", "prev", "rotate_cw", "rotate_ccw"):
        await box.ctrl.handle_event({"action": action})
    assert box.player.calls == []
    assert box.led.shows == []


async def test_controls_ignored_while_loading(hass, box):
    await _playing(box)
    box.ctrl._set(BoxState.LOADING, box.ctrl.current_figure)
    for action in ("play_pause", "next", "prev", "rotate_cw", "rotate_ccw"):
        await box.ctrl.handle_event({"action": action})
    assert box.player.calls == []
    assert box.led.shows == []
    assert box.ctrl.state is BoxState.LOADING


async def test_play_pause_toggles(hass, box):
    await _playing(box)
    await box.ctrl.play_pause()
    assert box.player.calls == [("pause",)]
    assert box.led.shows == [("hold", 0)]
    assert box.ctrl.state is BoxState.PAUSED_BY_BOX

    box.player.calls.clear()
    box.led.shows.clear()
    box.player.state = "idle"  # MA lässt pausierte Player nach kurzer Zeit auf idle fallen
    box.player.media_content_id = None
    await box.ctrl.play_pause()
    assert box.player.calls == [("play", BOBO_URI, TRACK)]
    assert box.led.shows == [("playing", 0, (128, 0, 255))]
    assert box.ctrl.state is BoxState.PLAYING


async def test_play_pause_resume_falls_back_to_restart(hass, box):
    await _playing(box)
    await box.ctrl.play_pause()
    box.player.calls.clear()
    box.player.fail_start_item = True
    await box.ctrl.play_pause()
    assert box.player.calls == [("play", BOBO_URI)]
    assert box.ctrl.state is BoxState.PLAYING


async def test_resume_from_pause_caps_volume(hass, box):
    await _playing(box)
    await box.ctrl.play_pause()
    box.player.calls.clear()
    box.player.volume = 0.9
    await box.ctrl.play_pause()
    assert box.player.calls == [("set_volume", 0.4), ("play", BOBO_URI, TRACK)]


async def test_play_pause_player_error(hass, box):
    await _playing(box)
    box.player.available = False
    await box.ctrl.play_pause()
    assert box.led.shows == [("error", 0)]
    assert box.ctrl.state is BoxState.PLAYING


async def test_next_prev(hass, box):
    await _playing(box)
    await box.ctrl.next_track()
    await box.ctrl.previous_track()
    assert box.player.calls == [("next_track",), ("previous_track",)]
    assert box.ctrl.state is BoxState.PLAYING


async def test_next_player_error(hass, box):
    await _playing(box)
    box.player.available = False
    await box.ctrl.next_track()
    await box.ctrl.previous_track()
    assert box.led.shows == [("error", 0), ("error", 0)]
    assert box.ctrl.state is BoxState.PLAYING


async def test_rotate_up_capped_at_max(hass, box):
    await _playing(box)
    box.player.volume = 0.39
    await box.ctrl.rotate(1)
    assert box.player.calls == [("set_volume", 0.40)]
    assert box.led.shows == [("volume", 100)]


async def test_rotate_down_floor_zero(hass, box):
    await _playing(box)
    box.player.volume = 0.02
    await box.ctrl.rotate(-1)
    assert box.player.calls == [("set_volume", 0.0)]
    assert box.led.shows == [("volume", 0)]


async def test_rotate_with_unknown_volume(hass, box):
    await _playing(box)
    box.player.volume = None
    await box.ctrl.rotate(1)
    assert box.player.calls == [("set_volume", 0.03)]
    assert box.led.shows == [("volume", 8)]


async def test_rotate_player_error(hass, box):
    await _playing(box)
    box.player.available = False
    await box.ctrl.rotate(1)
    assert box.led.shows == [("error", 0)]
    assert box.ctrl.state is BoxState.PLAYING


async def test_rotate_works_when_paused_by_box(hass, box):
    await _playing(box)
    await box.ctrl.play_pause()
    box.player.calls.clear()
    box.led.shows.clear()
    box.player.volume = 0.2
    await box.ctrl.rotate(1)
    assert box.player.calls == [("set_volume", 0.23)]
    assert box.led.shows == [("volume", round(23 / 40 * 100))]
    assert box.ctrl.state is BoxState.PAUSED_BY_BOX


async def test_handle_event_dispatch(hass, box):
    await _playing(box)
    box.player.volume = 0.2
    await box.ctrl.handle_event({"action": "rotate_cw"})
    assert box.player.calls == [("set_volume", 0.23)]
    await box.ctrl.handle_event({"action": "rotate_ccw"})
    assert box.player.calls[-1] == ("set_volume", 0.2)
    box.player.calls.clear()
    await box.ctrl.handle_event({"action": "next"})
    await box.ctrl.handle_event({"action": "prev"})
    assert box.player.calls == [("next_track",), ("previous_track",)]
    box.player.calls.clear()
    await box.ctrl.handle_event({"action": "play_pause"})
    assert box.player.calls == [("pause",)]

    box.player.calls.clear()
    box.led.shows.clear()
    await box.ctrl.handle_event({"action": "bogus"})
    await box.ctrl.handle_event({})
    await box.ctrl.handle_event({"action": "tag_on"})
    assert box.player.calls == []
    assert box.led.shows == []


async def test_controls_are_serialised_with_pause(hass, box):
    await _playing(box)
    box.player.volume = 0.2
    box.player.pause_gate = asyncio.Event()
    pause_task = hass.async_create_task(box.ctrl.play_pause())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    rotate_task = hass.async_create_task(box.ctrl.rotate(1))
    for _ in range(5):
        await asyncio.sleep(0)
    # Die Drehung wartet auf den Lock, solange pause() noch läuft.
    assert box.player.calls == []
    assert not rotate_task.done()

    box.player.pause_gate.set()
    await asyncio.gather(pause_task, rotate_task)
    assert box.player.calls == [("pause",), ("set_volume", 0.23)]
    assert box.ctrl.state is BoxState.PAUSED_BY_BOX
