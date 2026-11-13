"""Tests für den LedAdapter."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.home_tonie.const import LED_OFF, LED_PLAYING, LED_VOLUME
from custom_components.home_tonie.led import LedAdapter, esphome_node_name


@pytest.fixture
def esphome_device(hass: HomeAssistant):
    entry = MockConfigEntry(domain="esphome", data={"device_name": "home-tonie-anna"})
    entry.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("esphome", "home-tonie-anna")},
    )


async def test_node_name_resolved(hass, esphome_device):
    assert esphome_node_name(hass, esphome_device.id) == "home-tonie-anna"


async def test_node_name_unknown_device(hass):
    assert esphome_node_name(hass, "does-not-exist") is None


async def test_show_calls_node_specific_action(hass, esphome_device):
    calls = async_mock_service(hass, "esphome", "home_tonie_anna_set_led")
    await LedAdapter(hass, esphome_device.id).show(LED_VOLUME, 75)
    await hass.async_block_till_done()
    assert calls[0].data == {"mode": "volume", "level": 75}


async def test_missing_action_warns_once(hass, esphome_device, caplog):
    led = LedAdapter(hass, esphome_device.id)
    await led.show(LED_PLAYING)
    await led.show(LED_OFF)
    assert caplog.text.count("set_led") == 1


async def test_unknown_device_does_not_raise(hass, caplog):
    led = LedAdapter(hass, "does-not-exist")
    await led.show(LED_OFF)
    await led.show(LED_OFF)
    assert caplog.text.count("does-not-exist") == 1
