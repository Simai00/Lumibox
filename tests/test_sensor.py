"""Tests für die Sensoren „Aktuelle Figur“ und „Letzter unbekannter Tag“."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

from custom_components.lumibox.const import DOMAIN, EVENT_TYPE


def _entity_id(hass, subentry_id: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{subentry_id}_{key}")
    assert entity_id is not None, key
    return entity_id


async def _fire(hass, device_id, action, uid):
    hass.bus.async_fire(EVENT_TYPE, {"device_id": device_id, "action": action, "uid": uid})
    await hass.async_block_till_done()


async def test_sensors_registered_per_box(hass, two_boxes_entry):
    boxes = two_boxes_entry
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    for name in ("Anna", "Ben"):
        sub_id = boxes.box_subentry(name).subentry_id
        for key, label in (("current_figure", "Current figure"), ("last_unknown_tag", "Last unknown tag")):
            entity_id = _entity_id(hass, sub_id, key)
            entry = ent_reg.async_get(entity_id)
            assert entry.config_subentry_id == sub_id
            device = dev_reg.async_get(entry.device_id)
            assert device.identifiers == {(DOMAIN, sub_id)}
            assert device.name == f"Lumibox {name}"
            assert device.config_subentry_id == sub_id
            assert entry.translation_key == key
            state = hass.states.get(entity_id)
            assert state.state == ("none" if key == "current_figure" else STATE_UNKNOWN)
            assert state.attributes["friendly_name"] == f"Lumibox {name} {label}"


async def test_current_figure_follows_box(hass, two_boxes_entry):
    boxes = two_boxes_entry
    sub_id = boxes.box_subentry("Anna").subentry_id
    current = _entity_id(hass, sub_id, "current_figure")

    await _fire(hass, boxes.dev_anna, "tag_on", "04A1B2C3")
    assert hass.states.get(current).state == "Bobo"

    await _fire(hass, boxes.dev_anna, "tag_off", "04A1B2C3")
    # Während der Entprellung bleibt die Figur angezeigt.
    assert hass.states.get(current).state == "Bobo"
    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=1.1))
    await hass.async_block_till_done()
    assert hass.states.get(current).state == "none"


async def test_last_unknown_tag(hass, two_boxes_entry):
    boxes = two_boxes_entry
    anna = boxes.box_subentry("Anna").subentry_id
    ben = boxes.box_subentry("Ben").subentry_id

    await _fire(hass, boxes.dev_anna, "tag_on", "FF:EE")

    assert hass.states.get(_entity_id(hass, anna, "last_unknown_tag")).state == "FFEE"
    assert hass.states.get(_entity_id(hass, anna, "current_figure")).state == "none"
    assert hass.states.get(_entity_id(hass, ben, "last_unknown_tag")).state == STATE_UNKNOWN


async def test_sensors_unavailable_after_unload(hass, two_boxes_entry):
    boxes = two_boxes_entry
    sub_id = boxes.box_subentry("Anna").subentry_id
    current = _entity_id(hass, sub_id, "current_figure")
    assert await hass.config_entries.async_unload(boxes.entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(current).state == STATE_UNAVAILABLE
