"""Tests für den PlayerAdapter."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.home_tonie.player import PlayerAdapter, PlayerError, PlayerSnapshot

ENTITY = "media_player.kinderzimmer"


def _adapter(hass: HomeAssistant) -> PlayerAdapter:
    return PlayerAdapter(hass, ENTITY, "anna")


async def test_play_calls_music_assistant_with_username(hass):
    calls = async_mock_service(hass, "music_assistant", "play_media")
    hass.states.async_set(ENTITY, "idle")
    await _adapter(hass).play("spotify:album:4aawyAB9vmqN3uQ7FjRGTy")
    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": ENTITY,
        "media_id": "spotify://album/4aawyAB9vmqN3uQ7FjRGTy",
        "media_type": "album",
        "enqueue": "replace",
        "username": "anna",
    }


@pytest.mark.parametrize("method,service", [
    ("resume", "media_play"),
    ("pause", "media_pause"),
    ("next_track", "media_next_track"),
    ("previous_track", "media_previous_track"),
])
async def test_transport_services(hass, method, service):
    calls = async_mock_service(hass, "media_player", service)
    hass.states.async_set(ENTITY, "playing")
    await getattr(_adapter(hass), method)()
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": ENTITY}


@pytest.mark.parametrize("given,expected", [(1.4, 1.0), (-0.1, 0.0), (0.5, 0.5)])
async def test_set_volume_clamps(hass, given, expected):
    calls = async_mock_service(hass, "media_player", "volume_set")
    hass.states.async_set(ENTITY, "playing")
    await _adapter(hass).set_volume(given)
    assert calls[0].data == {"entity_id": ENTITY, "volume_level": expected}


async def test_snapshot_and_volume_read_state(hass):
    hass.states.async_set(
        ENTITY, "paused", {"volume_level": 0.3, "media_content_id": "spotify://track/abc"}
    )
    adapter = _adapter(hass)
    assert adapter.is_available() is True
    assert adapter.snapshot() == PlayerSnapshot("paused", "spotify://track/abc")
    assert adapter.get_volume() == 0.3


async def test_snapshot_without_attributes(hass):
    hass.states.async_set(ENTITY, "idle")
    adapter = _adapter(hass)
    assert adapter.snapshot() == PlayerSnapshot("idle", None)
    assert adapter.get_volume() is None


async def test_unavailable_player_raises(hass):
    play = async_mock_service(hass, "music_assistant", "play_media")
    pause = async_mock_service(hass, "media_player", "media_pause")
    vol = async_mock_service(hass, "media_player", "volume_set")
    hass.states.async_set(ENTITY, "unavailable")
    adapter = _adapter(hass)
    assert adapter.is_available() is False
    with pytest.raises(PlayerError):
        await adapter.play("spotify:album:4aawyAB9vmqN3uQ7FjRGTy")
    with pytest.raises(PlayerError):
        await adapter.pause()
    with pytest.raises(PlayerError):
        await adapter.set_volume(0.5)
    assert not play and not pause and not vol


async def test_missing_entity_raises(hass):
    async_mock_service(hass, "music_assistant", "play_media")
    adapter = _adapter(hass)
    assert adapter.is_available() is False
    assert adapter.get_volume() is None
    assert adapter.snapshot() == PlayerSnapshot(None, None)
    with pytest.raises(PlayerError):
        await adapter.play("spotify:album:4aawyAB9vmqN3uQ7FjRGTy")
    with pytest.raises(PlayerError):
        await adapter.resume()


async def test_service_not_found_becomes_player_error(hass):
    hass.states.async_set(ENTITY, "idle")
    with pytest.raises(PlayerError):
        await _adapter(hass).play("spotify:album:4aawyAB9vmqN3uQ7FjRGTy")


async def test_service_error_becomes_player_error(hass):
    async def _fail(call):
        raise HomeAssistantError("boom")

    hass.services.async_register("media_player", "media_pause", _fail)
    hass.states.async_set(ENTITY, "playing")
    with pytest.raises(PlayerError):
        await _adapter(hass).pause()
