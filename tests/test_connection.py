"""Tests für den Verbindungs-Sensor und die Verfügbarkeit der Box-Sensoren."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.lumibox.const import DOMAIN

from .conftest import add_esphome_entity


def _entity_id(hass, platform: str, subentry_id: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{subentry_id}_{key}")
    assert entity_id is not None, key
    return entity_id


def _connected(hass, boxes, name: str) -> str:
    return _entity_id(hass, "binary_sensor", boxes.box_subentry(name).subentry_id, "connected")


def _sensors(hass, boxes, name: str) -> list[str]:
    sub_id = boxes.box_subentry(name).subentry_id
    return [_entity_id(hass, "sensor", sub_id, k) for k in ("current_figure", "last_unknown_tag")]


async def test_connected_on_when_esphome_entity_available(hass, two_boxes_entry):
    entity_id = _connected(hass, two_boxes_entry, "Anna")
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == "connectivity"
    assert state.attributes["friendly_name"] == "Lumibox Anna Connected"


async def test_connected_off_and_sensors_unavailable_when_esphome_unavailable(hass, two_boxes_entry):
    boxes = two_boxes_entry
    hass.states.async_set(boxes.anna_status, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    assert hass.states.get(_connected(hass, boxes, "Anna")).state == STATE_OFF
    for entity_id in _sensors(hass, boxes, "Anna"):
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get(_connected(hass, boxes, "Ben")).state == STATE_ON
    for entity_id in _sensors(hass, boxes, "Ben"):
        assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_reconnect_restores_availability(hass, two_boxes_entry):
    boxes = two_boxes_entry
    hass.states.async_set(boxes.anna_status, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    hass.states.async_set(boxes.anna_status, "on")
    await hass.async_block_till_done()

    assert hass.states.get(_connected(hass, boxes, "Anna")).state == STATE_ON
    for entity_id in _sensors(hass, boxes, "Anna"):
        assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_no_esphome_entities_means_disconnected(hass, loaded_entry_with_box, caplog):
    entry = loaded_entry_with_box
    sub = next(iter(entry.subentries.values()))
    entity_id = _entity_id(hass, "binary_sensor", sub.subentry_id, "connected")
    assert hass.states.get(entity_id).state == STATE_OFF
    assert "Traceback" not in caplog.text
    assert "ERROR" not in caplog.text


async def test_new_esphome_entity_is_tracked(hass, loaded_entry_with_box, esphome_device):
    entry = loaded_entry_with_box
    sub = next(iter(entry.subentries.values()))
    entity_id = _entity_id(hass, "binary_sensor", sub.subentry_id, "connected")
    assert hass.states.get(entity_id).state == STATE_OFF

    add_esphome_entity(hass, esphome_device)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_subentry_removal_cleans_up(hass, two_boxes_entry):
    boxes = two_boxes_entry
    entity_id = _connected(hass, boxes, "Anna")
    anna = boxes.box_subentry("Anna")

    hass.config_entries.async_remove_subentry(boxes.entry, anna.subentry_id)
    await hass.async_block_till_done()

    assert boxes.entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id) is None
    assert er.async_get(hass).async_get(entity_id) is None
    # Der State der alten ESPHome-Entität darf keinen Fehler mehr auslösen.
    hass.states.async_set(boxes.anna_status, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get(_connected(hass, boxes, "Ben")).state == STATE_ON


async def test_dashboard_entity_does_not_count_as_connected(hass, loaded_entry_with_box, esphome_device):
    sub = next(iter(loaded_entry_with_box.subentries.values()))
    entity_id = _entity_id(hass, "binary_sensor", sub.subentry_id, "connected")

    # Dashboard-Update-Entität: unique_id ist die reine MAC, bleibt verfügbar.
    add_esphome_entity(hass, esphome_device, unique_id="aabbccddee01")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    add_esphome_entity(hass, esphome_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON
