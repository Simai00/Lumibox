"""Gemeinsame Fixtures für die Tests."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry, ConfigSubentryData
from homeassistant.core import ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.lumibox.box import BoxConfig, BoxController
from custom_components.lumibox.const import (
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
from custom_components.lumibox.library import Figure, FigureLibrary

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


def add_esphome_entity(hass, device: dr.DeviceEntry, state: str = "on") -> str:
    """ESPHome-Entität am Gerät registrieren und State setzen; liefert die entity_id."""
    entry = er.async_get(hass).async_get_or_create(
        "binary_sensor",
        "esphome",
        f"{device.id}_status",
        device_id=device.id,
        suggested_object_id=f"{device.name.lower().replace(' ', '_')}_status",
    )
    hass.states.async_set(entry.entity_id, state)
    return entry.entity_id


@pytest.fixture
def esphome_device(hass) -> dr.DeviceEntry:
    """ESPHome-Gerät „Lumibox Anna“."""
    return _esphome_device(hass, "aa:bb:cc:dd:ee:01", "lumibox-anna", "Lumibox Anna")


@pytest.fixture
def other_device(hass) -> dr.DeviceEntry:
    """Zweites ESPHome-Gerät „Lumibox Ben“."""
    return _esphome_device(hass, "aa:bb:cc:dd:ee:02", "lumibox-ben", "Lumibox Ben")


@pytest.fixture
def ma_player(hass) -> er.RegistryEntry:
    """Music-Assistant-Player `media_player.kinderzimmer` in der Entity-Registry."""
    return er.async_get(hass).async_get_or_create(
        "media_player", "music_assistant", "uid1", suggested_object_id="kinderzimmer"
    )


async def _load_entry(hass, subentries: list[ConfigSubentryData]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="Lumibox", data={}, subentries_data=subentries
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


def _box_subentry(name: str, device_id: str, player: str, username: str) -> ConfigSubentryData:
    return ConfigSubentryData(
        subentry_type=SUBENTRY_BOX,
        title=name,
        unique_id=None,
        data={
            "name": name,
            CONF_ESPHOME_DEVICE_ID: device_id,
            CONF_PLAYER_ENTITY_ID: player,
            CONF_MA_USERNAME: username,
            CONF_MAX_VOLUME: 40,
            CONF_VOLUME_STEP: 3,
        },
    )


def _figure_subentry(figure: Figure) -> ConfigSubentryData:
    return ConfigSubentryData(
        subentry_type=SUBENTRY_FIGURE,
        title=figure.name,
        unique_id=None,
        data={
            "name": figure.name,
            CONF_UID: figure.uid,
            CONF_MEDIA_URI: figure.media_uri,
            CONF_MODE: MODE_RESTART,
        },
    )


@dataclass
class TwoBoxes:
    """Geladener Haupteintrag mit den Boxen Anna und Ben und gemockten Services."""

    entry: MockConfigEntry
    dev_anna: str
    dev_ben: str
    play: list[ServiceCall]
    media_player: dict[str, list[ServiceCall]]
    led: dict[str, list[ServiceCall]]
    # ESPHome-Entitäten, aus denen die Verbindung der Box abgeleitet wird
    anna_status: str
    ben_status: str

    def box_subentry(self, name: str) -> ConfigSubentry:
        """Box-Subentry anhand des Namens."""
        return next(
            sub
            for sub in self.entry.subentries.values()
            if sub.subentry_type == SUBENTRY_BOX and sub.data["name"] == name
        )

    def all_calls(self) -> list[ServiceCall]:
        """Alle aufgezeichneten Service-Aufrufe (Player und LED)."""
        calls = list(self.play)
        for lst in (*self.media_player.values(), *self.led.values()):
            calls.extend(lst)
        return calls


MEDIA_PLAYER_SERVICES = (
    "media_play",
    "media_pause",
    "media_next_track",
    "media_previous_track",
    "volume_set",
)


@pytest.fixture
async def two_boxes_entry(hass):
    """Boxen Anna (media_player.anna, anna) und Ben (media_player.ben, ben), Figuren Bobo und Feuerwehr."""
    anna = _esphome_device(hass, "aa:bb:cc:dd:ee:11", "lumibox-anna", "Lumibox Anna")
    ben = _esphome_device(hass, "aa:bb:cc:dd:ee:12", "lumibox-ben", "Lumibox Ben")
    anna_status = add_esphome_entity(hass, anna)
    ben_status = add_esphome_entity(hass, ben)
    hass.states.async_set("media_player.anna", "idle", {"volume_level": 0.3})
    hass.states.async_set("media_player.ben", "idle", {"volume_level": 0.3})
    play = async_mock_service(hass, "music_assistant", "play_media")
    media_player = {svc: async_mock_service(hass, "media_player", svc) for svc in MEDIA_PLAYER_SERVICES}
    led = {
        "anna": async_mock_service(hass, "esphome", "lumibox_anna_set_led"),
        "ben": async_mock_service(hass, "esphome", "lumibox_ben_set_led"),
    }
    entry = await _load_entry(
        hass,
        [
            _box_subentry("Anna", anna.id, "media_player.anna", "anna"),
            _box_subentry("Ben", ben.id, "media_player.ben", "ben"),
            _figure_subentry(BOBO),
            _figure_subentry(FEUERWEHR),
        ],
    )
    yield TwoBoxes(entry, anna.id, ben.id, play, media_player, led, anna_status, ben_status)
    if entry.state is ConfigEntryState.LOADED:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
