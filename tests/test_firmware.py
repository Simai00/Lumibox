"""Tests für die Firmware-Versionsprüfung und den Reparatur-Hinweis."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.lumibox.const import DOMAIN, MIN_FIRMWARE_VERSION
from custom_components.lumibox.firmware import is_outdated, parse_firmware_version
from custom_components.lumibox.repairs import async_create_fix_flow

from .conftest import _esphome_device, _load_entry, _box_subentry


@pytest.mark.parametrize(
    ("sw", "expected"),
    [
        ("0.2.0 (ESPHome 2026.10.0)", "0.2.0"),
        ("dev (ESPHome 2026.10.0)", "dev"),
        ("0.2.0-beta.1 (ESPHome 2026.10.0)", "0.2.0-beta.1"),
        ("2026.10.0", None),
        ("2026.10.0 (Nov 1 2026, 10:00:00)", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_firmware_version(sw, expected):
    assert parse_firmware_version(sw) == expected


@pytest.mark.parametrize(
    ("sw", "expected"),
    [
        (None, None),
        ("2026.10.0", True),
        ("0.1.0 (ESPHome 2026.10.0)", True),
        ("0.2.0 (ESPHome 2026.10.0)", False),
        ("0.10.0 (ESPHome 2026.10.0)", False),
        ("1.0.0 (ESPHome 2026.10.0)", False),
        ("0.2.0-beta.1 (ESPHome 2026.10.0)", True),
        ("0.3.0-beta.1 (ESPHome 2026.10.0)", False),
        ("dev (ESPHome 2026.10.0)", False),
        (" (ESPHome 2026.10.0)", True),
    ],
)
def test_is_outdated_cases(sw, expected):
    assert is_outdated(sw) is expected


def _issue(hass, subentry_id):
    return ir.async_get(hass).async_get_issue(DOMAIN, f"firmware_outdated_{subentry_id}")


def _set_sw(hass, device_id, sw):
    dr.async_get(hass).async_update_device(device_id, sw_version=sw)


async def _box_with_sw(hass, sw):
    device = _esphome_device(hass, "aa:bb:cc:dd:ee:21", "lumibox-anna", "Lumibox Anna")
    if sw is not None:
        _set_sw(hass, device.id, sw)
    entry = await _load_entry(hass, [_box_subentry("Anna", device.id, "media_player.k", "anna")])
    sub = next(iter(entry.subentries.values()))
    return entry, sub, device


async def test_issue_created_for_old_firmware(hass):
    entry, sub, device = await _box_with_sw(hass, "2026.10.0")
    issue = _issue(hass, sub.subentry_id)
    assert issue is not None
    assert issue.is_fixable
    assert issue.data == {"device_id": device.id}
    assert issue.translation_key == "firmware_outdated"
    assert issue.translation_placeholders == {
        "box": "Anna",
        "current": "unbekannt",
        "required": MIN_FIRMWARE_VERSION,
    }


async def test_issue_shows_current_version(hass):
    _, sub, _ = await _box_with_sw(hass, "0.1.0 (ESPHome 2026.10.0)")
    assert _issue(hass, sub.subentry_id).translation_placeholders["current"] == "0.1.0"


async def test_issue_removed_after_registry_update(hass):
    entry, sub, device = await _box_with_sw(hass, "2026.10.0")
    assert _issue(hass, sub.subentry_id) is not None
    _set_sw(hass, device.id, "0.2.0 (ESPHome x)")
    await hass.async_block_till_done()
    assert _issue(hass, sub.subentry_id) is None


async def test_issue_created_after_registry_update(hass):
    entry, sub, device = await _box_with_sw(hass, "0.2.0 (ESPHome x)")
    assert _issue(hass, sub.subentry_id) is None
    _set_sw(hass, device.id, "0.1.0 (ESPHome x)")
    await hass.async_block_till_done()
    assert _issue(hass, sub.subentry_id) is not None


async def test_no_issue_when_sw_version_none(hass):
    _, sub, _ = await _box_with_sw(hass, None)
    assert _issue(hass, sub.subentry_id) is None


async def test_stale_issue_removed_on_setup(hass):
    ir.async_create_issue(
        hass, DOMAIN, "firmware_outdated_gone", is_fixable=True,
        severity=ir.IssueSeverity.WARNING, translation_key="firmware_outdated",
        translation_placeholders={"box": "x", "current": "y", "required": "z"},
    )
    await _box_with_sw(hass, "0.2.0 (ESPHome x)")
    assert _issue(hass, "gone") is None


async def test_unload_removes_listener(hass):
    entry, sub, device = await _box_with_sw(hass, "0.2.0 (ESPHome x)")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    _set_sw(hass, device.id, "0.1.0 (ESPHome x)")
    await hass.async_block_till_done()
    assert _issue(hass, sub.subentry_id) is None


def _update_entity(hass, device, state):
    reg = er.async_get(hass)
    ent = reg.async_get_or_create(
        "update",
        "esphome",
        "upd1",
        config_entry=hass.config_entries.async_entries("esphome")[0],
        device_id=device.id,
    )
    hass.states.async_set(ent.entity_id, state)
    return ent


async def _start_flow(hass, device):
    flow = await async_create_fix_flow(hass, "firmware_outdated_x", {"device_id": device.id})
    flow.hass = hass
    flow.handler = DOMAIN
    flow.flow_id = "test"
    return flow


async def test_fix_flow_installs_update(hass, esphome_device):
    ent = _update_entity(hass, esphome_device, "on")
    calls = async_mock_service(hass, "update", "install")
    flow = await _start_flow(hass, esphome_device)
    result = await flow.async_step_init()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == ent.entity_id


async def test_fix_flow_aborts_without_update_entity(hass, esphome_device):
    calls = async_mock_service(hass, "update", "install")
    flow = await _start_flow(hass, esphome_device)
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_update"
    assert not calls


async def test_fix_flow_aborts_when_no_update_available(hass, esphome_device):
    _update_entity(hass, esphome_device, "off")
    calls = async_mock_service(hass, "update", "install")
    flow = await _start_flow(hass, esphome_device)
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_update"
    assert not calls
