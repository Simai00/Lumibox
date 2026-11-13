"""Gemeinsame Fixtures für die Tests."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_tonie.box import BoxConfig, BoxController
from custom_components.home_tonie.const import (
    CONF_ESPHOME_DEVICE_ID,
    CONF_MA_USERNAME,
    CONF_MAX_VOLUME,
    CONF_MEDIA_URI,
    CONF_MODE,
    CONF_PLAYER_ENTITY_ID,
    CONF_UID,
    CONF_VOLUME_STEP,
    DOMAIN,
    MODE_RESTART,
    SUBENTRY_BOX,
    SUBENTRY_FIGURE,
)
from custom_components.home_tonie.library import Figure, FigureLibrary

from .fakes import FakeLed, FakePlayer

BOBO = Figure("fig_bobo", "Bobo", "04A1B2C3", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", MODE_RESTART)
FEUERWEHR = Figure(
    "fig_feuerwehr", "Feuerwehr", "04B7C8D9", "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", MODE_RESTART
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Custom Integrations in allen Tests aktivieren."""
    yield


@dataclass
class Box:
    """Bündelt Controller und Fakes für Tests."""

    ctrl: BoxController
    player: FakePlayer
    led: FakeLed
    unknown_uids: list[str] = field(default_factory=list)


@pytest.fixture
async def box(hass):
    """BoxController mit FakePlayer (Lautstärke 0.8), FakeLed und zwei Figuren."""
    config = BoxConfig(
        subentry_id="box_anna",
        name="Anna",
        esphome_device_id="dev_anna",
        player_entity_id="media_player.kinderzimmer",
        ma_username="anna",
        max_volume=40,
        volume_step=3,
    )
    player = FakePlayer(volume=0.8)
    led = FakeLed()
    unknown: list[str] = []
    ctrl = BoxController(
        hass, config, FigureLibrary([BOBO, FEUERWEHR]), player, led, on_unknown_tag=unknown.append
    )
    yield Box(ctrl, player, led, unknown)
    ctrl.async_shutdown()


def _esphome_device(hass, mac: str, device_name: str, name: str) -> dr.DeviceEntry:
    """ESPHome-Config-Entry plus Gerät in der Geräte-Registry anlegen."""
    esphome_entry = MockConfigEntry(domain="esphome", data={"device_name": device_name})
    esphome_entry.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=esphome_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        name=name,
    )


@pytest.fixture
def esphome_device(hass) -> dr.DeviceEntry:
    """ESPHome-Gerät „Home Tonie Anna“."""
    return _esphome_device(hass, "aa:bb:cc:dd:ee:01", "home-tonie-anna", "Home Tonie Anna")


@pytest.fixture
def other_device(hass) -> dr.DeviceEntry:
    """Zweites ESPHome-Gerät „Home Tonie Ben“."""
    return _esphome_device(hass, "aa:bb:cc:dd:ee:02", "home-tonie-ben", "Home Tonie Ben")


@pytest.fixture
def ma_player(hass) -> er.RegistryEntry:
    """Music-Assistant-Player `media_player.kinderzimmer` in der Entity-Registry."""
    return er.async_get(hass).async_get_or_create(
        "media_player", "music_assistant", "uid1", suggested_object_id="kinderzimmer"
    )


async def _load_entry(hass, subentries: list[ConfigSubentryData]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="Home Tonie", data={}, subentries_data=subentries
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def loaded_entry(hass) -> MockConfigEntry:
    """Geladener Haupteintrag ohne Subentries."""
    return await _load_entry(hass, [])


@pytest.fixture
async def loaded_entry_with_box(hass, esphome_device) -> MockConfigEntry:
    """Geladener Haupteintrag mit Box „Anna“ auf `esphome_device`."""
    return await _load_entry(
        hass,
        [
            ConfigSubentryData(
                subentry_type=SUBENTRY_BOX,
                title="Anna",
                unique_id=None,
                data={
                    "name": "Anna",
                    CONF_ESPHOME_DEVICE_ID: esphome_device.id,
                    CONF_PLAYER_ENTITY_ID: "media_player.kinderzimmer",
                    CONF_MA_USERNAME: "anna",
                    CONF_MAX_VOLUME: 40,
                    CONF_VOLUME_STEP: 3,
                },
            )
        ],
    )


@pytest.fixture
async def loaded_entry_with_figure(hass) -> MockConfigEntry:
    """Geladener Haupteintrag mit Figur „Bobo“ (UID 04A1B2C3)."""
    return await _load_entry(
        hass,
        [
            ConfigSubentryData(
                subentry_type=SUBENTRY_FIGURE,
                title=BOBO.name,
                unique_id=None,
                data={
                    "name": BOBO.name,
                    CONF_UID: BOBO.uid,
                    CONF_MEDIA_URI: BOBO.media_uri,
                    CONF_MODE: MODE_RESTART,
                },
            )
        ],
    )
