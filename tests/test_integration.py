"""Tests für Verdrahtung, Event-Routing und Hot-Update der Figuren."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, ConfigSubentry
from homeassistant.core import ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

from custom_components.lumibox.box import BoxState
from custom_components.lumibox.const import (
    CONF_DEFAULT_COLOR,
    CONF_MAX_VOLUME,
    CONF_MEDIA_URI,
    CONF_MODE,
    CONF_UID,
    DOMAIN,
    EVENT_TYPE,
    MODE_RESTART,
    SUBENTRY_FIGURE,
)

BOBO_MEDIA = "spotify://album/4aawyAB9vmqN3uQ7FjRGTy"
FEUERWEHR_MEDIA = "spotify://playlist/37i9dQZF1DXcBWIGoYBM5M"
NEW_URI = "spotify:album:1A2GTWGtFfWp7KSQTwWOyo"
NEW_MEDIA = "spotify://album/1A2GTWGtFfWp7KSQTwWOyo"


async def _fire(hass, data):
    hass.bus.async_fire(EVENT_TYPE, data)
    await hass.async_block_till_done()


async def _tag_on(hass, device_id, uid):
    await _fire(hass, {"device_id": device_id, "action": "tag_on", "uid": uid})


async def _remove(hass, device_id, uid):
    """Figur abnehmen und die Entprellung ablaufen lassen."""
    await _fire(hass, {"device_id": device_id, "action": "tag_off", "uid": uid})
    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=1.1))
    await hass.async_block_till_done()


def _sensor_state(hass, subentry_id, key):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{subentry_id}_{key}")
    assert entity_id is not None
    return hass.states.get(entity_id).state


async def test_event_routed_to_correct_box(hass, two_boxes_entry):
    boxes = two_boxes_entry
    await _tag_on(hass, boxes.dev_anna, "04-A1-B2-C3")

    assert len(boxes.play) == 1
    assert boxes.play[-1].data["entity_id"] == "media_player.anna"
    assert boxes.play[-1].data["username"] == "anna"
    assert boxes.play[-1].data["media_id"] == BOBO_MEDIA
    controllers = boxes.entry.runtime_data.controllers
    assert controllers[boxes.dev_anna].state is BoxState.PLAYING
    # Box Ben unberührt
    assert controllers[boxes.dev_ben].state is BoxState.IDLE
    assert boxes.led["ben"] == []
    ben = boxes.box_subentry("Ben").subentry_id
    assert _sensor_state(hass, ben, "current_figure") == "none"
    anna = boxes.box_subentry("Anna").subentry_id
    assert _sensor_state(hass, anna, "current_figure") == "Bobo"


async def test_two_boxes_independent(hass, two_boxes_entry):
    boxes = two_boxes_entry
    await _tag_on(hass, boxes.dev_anna, "04A1B2C3")
    await _tag_on(hass, boxes.dev_ben, "04:B7:C8:D9")

    assert [(c.data["entity_id"], c.data["username"], c.data["media_id"]) for c in boxes.play] == [
        ("media_player.anna", "anna", BOBO_MEDIA),
        ("media_player.ben", "ben", FEUERWEHR_MEDIA),
    ]

    await _remove(hass, boxes.dev_anna, "04A1B2C3")

    pauses = boxes.media_player["media_pause"]
    assert [c.data["entity_id"] for c in pauses] == ["media_player.anna"]
    controllers = boxes.entry.runtime_data.controllers
    assert controllers[boxes.dev_anna].state is BoxState.REMOVED
    assert controllers[boxes.dev_ben].state is BoxState.PLAYING
    assert controllers[boxes.dev_ben].current_figure.name == "Feuerwehr"


async def test_foreign_and_malformed_events_ignored(hass, two_boxes_entry, caplog):
    boxes = two_boxes_entry
    caplog.set_level(logging.DEBUG, logger="custom_components.lumibox")
    for data in (
        {"device_id": "fremdes_geraet", "action": "tag_on", "uid": "04A1B2C3"},
        {"action": "tag_on", "uid": "04A1B2C3"},
        {"device_id": None, "action": "tag_on", "uid": "04A1B2C3"},
        {"device_id": boxes.dev_anna},
        {"device_id": boxes.dev_anna, "action": "tag_on"},
        {"device_id": boxes.dev_anna, "action": "tag_on", "uid": ""},
        {"device_id": boxes.dev_anna, "action": "tag_on", "uid": 1234},
        {"device_id": boxes.dev_anna, "action": "tag_off"},
        {"device_id": boxes.dev_anna, "action": "explode"},
    ):
        await _fire(hass, data)

    assert boxes.all_calls() == []
    controllers = boxes.entry.runtime_data.controllers
    assert all(c.state is BoxState.IDLE for c in controllers.values())
    assert "fremdes_geraet" in caplog.text
    assert "Traceback" not in caplog.text


async def test_adapter_exception_is_logged_not_raised(hass, two_boxes_entry, caplog):
    boxes = two_boxes_entry
    ctrl = boxes.entry.runtime_data.controllers[boxes.dev_anna]
    with patch.object(ctrl, "handle_event", side_effect=RuntimeError("kaputt")):
        await _tag_on(hass, boxes.dev_anna, "04A1B2C3")
    assert "kaputt" in caplog.text
    assert boxes.entry.state is ConfigEntryState.LOADED

    # Die Box arbeitet danach normal weiter.
    await _tag_on(hass, boxes.dev_anna, "04A1B2C3")
    assert [c.data["entity_id"] for c in boxes.play] == ["media_player.anna"]


async def test_adding_figure_does_not_reset_playing_box(hass, two_boxes_entry):
    boxes = two_boxes_entry
    entry = boxes.entry
    await _tag_on(hass, boxes.dev_anna, "04A1B2C3")
    data = entry.runtime_data
    ctrl = data.controllers[boxes.dev_anna]
    assert ctrl.state is BoxState.PLAYING

    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data={"name": "Neu", CONF_UID: "04C1D2E3", CONF_MEDIA_URI: NEW_URI, CONF_MODE: MODE_RESTART},
            subentry_type=SUBENTRY_FIGURE,
            title="Neu",
            unique_id=None,
        ),
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is data
    assert entry.runtime_data.controllers[boxes.dev_anna] is ctrl
    assert ctrl.state is BoxState.PLAYING
    assert ctrl.current_figure.name == "Bobo"

    await _remove(hass, boxes.dev_anna, "04A1B2C3")
    assert [c.data["entity_id"] for c in boxes.media_player["media_pause"]] == ["media_player.anna"]
    assert ctrl.state is BoxState.REMOVED

    # Die neue Figur ist sofort abspielbar.
    await _tag_on(hass, boxes.dev_anna, "04-C1-D2-E3")
    assert boxes.play[-1].data["media_id"] == NEW_MEDIA
    assert boxes.play[-1].data["entity_id"] == "media_player.anna"
    assert ctrl.current_figure.name == "Neu"


async def test_box_change_reloads(hass, two_boxes_entry):
    boxes = two_boxes_entry
    entry = boxes.entry
    old = entry.runtime_data.controllers[boxes.dev_anna]
    assert old.config.max_volume == 40

    sub = boxes.box_subentry("Anna")
    hass.config_entries.async_update_subentry(
        entry, sub, data={**sub.data, CONF_MAX_VOLUME: 20}
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    new = entry.runtime_data.controllers[boxes.dev_anna]
    assert new is not old
    assert new.config.max_volume == 20

    # Neuer Wert wirksam: Lautstärke 0.3 wird beim Auflegen auf 0.2 begrenzt.
    await _tag_on(hass, boxes.dev_anna, "04A1B2C3")
    volume = boxes.media_player["volume_set"]
    assert [(c.data["entity_id"], c.data["volume_level"]) for c in volume] == [
        ("media_player.anna", 0.2)
    ]
    assert len(boxes.play) == 1


async def test_removing_box_reloads(hass, two_boxes_entry):
    boxes = two_boxes_entry
    entry = boxes.entry
    hass.config_entries.async_remove_subentry(entry, boxes.box_subentry("Ben").subentry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert set(entry.runtime_data.controllers) == {boxes.dev_anna}
    await _tag_on(hass, boxes.dev_ben, "04A1B2C3")
    assert boxes.play == []


async def test_unknown_tag_prefills_flow(hass, two_boxes_entry):
    boxes = two_boxes_entry
    await _tag_on(hass, boxes.dev_ben, "FF:EE")

    assert boxes.entry.runtime_data.last_unknown_uid == "FFEE"
    assert boxes.play == []

    result = await hass.config_entries.subentries.async_init(
        (boxes.entry.entry_id, SUBENTRY_FIGURE), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    suggested = next(
        (m.description or {}).get("suggested_value")
        for m in result["data_schema"].schema
        if m == CONF_UID
    )
    assert suggested == "FFEE"


async def test_uid_spelling_end_to_end(hass, two_boxes_entry):
    boxes = two_boxes_entry
    entry = boxes.entry
    bobo = next(s for s in entry.subentries.values() if s.title == "Bobo")
    hass.config_entries.async_remove_subentry(entry, bobo.subentry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_FIGURE), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Bobo neu", CONF_UID: "04:a1:b2:c3", CONF_MEDIA_URI: NEW_URI, CONF_MODE: MODE_RESTART},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    await _tag_on(hass, boxes.dev_anna, "04-A1-B2-C3")
    assert [(c.data["entity_id"], c.data["media_id"]) for c in boxes.play] == [
        ("media_player.anna", NEW_MEDIA)
    ]


async def test_unload_cleans_up(hass, two_boxes_entry):
    boxes = two_boxes_entry
    entry = boxes.entry
    # Abnahme mit laufender Entprellung: Unload darf keinen Timer zurücklassen.
    await _tag_on(hass, boxes.dev_anna, "04A1B2C3")
    await _fire(hass, {"device_id": boxes.dev_anna, "action": "tag_off", "uid": "04A1B2C3"})
    calls_before = len(boxes.all_calls())

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    await _tag_on(hass, boxes.dev_ben, "04B7C8D9")
    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    assert len(boxes.all_calls()) == calls_before
    assert boxes.media_player["media_pause"] == []


async def test_unload_waits_for_inflight_events(hass, two_boxes_entry):
    """Ereignisse, die beim Unload noch auf den Box-Lock warten, laufen vor dem Shutdown ab."""
    boxes = two_boxes_entry
    entry = boxes.entry
    await _tag_on(hass, boxes.dev_anna, "04A1B2C3")
    ctrl = entry.runtime_data.controllers[boxes.dev_anna]

    gate = asyncio.Event()
    paused: list[ServiceCall] = []

    async def slow_pause(call: ServiceCall) -> None:
        await gate.wait()
        paused.append(call)

    hass.services.async_register("media_player", "media_pause", slow_pause)

    # Abnahme läuft und hält den Lock, solange media_pause hängt.
    hass.bus.async_fire(EVENT_TYPE, {"device_id": boxes.dev_anna, "action": "tag_off", "uid": "04A1B2C3"})
    await asyncio.sleep(0)
    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=1.1))
    for _ in range(5):
        await asyncio.sleep(0)
    # Diese Ereignisse warten auf den Lock.
    for action in ("tag_on", "tag_off"):
        hass.bus.async_fire(
            EVENT_TYPE, {"device_id": boxes.dev_anna, "action": action, "uid": "04A1B2C3"}
        )
    await asyncio.sleep(0)

    unload = hass.async_create_task(hass.config_entries.async_unload(entry.entry_id))
    for _ in range(5):
        await asyncio.sleep(0)
    gate.set()
    assert await unload
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # Die laufende Abnahme wurde nicht abgebrochen, sondern hat pausiert.
    assert [c.data["entity_id"] for c in paused] == ["media_player.anna"]
    # Kein Entprell-Timer darf das Unload überleben (sonst meldet die Testumgebung
    # einen lingering timer); der Controller hat nichts mehr ausstehend.
    assert ctrl._cancel_debounce is None


async def test_box_without_default_color_key_uses_purple(hass, two_boxes_entry):
    boxes = two_boxes_entry
    await _tag_on(hass, boxes.dev_anna, "04-A1-B2-C3")
    playing = [c.data for c in boxes.led["anna"] if c.data["mode"] == "playing"]
    assert playing[-1] == {"mode": "playing", "level": 0, "r": 128, "g": 0, "b": 255}


async def test_two_boxes_own_default_color(hass, two_boxes_entry):
    boxes = two_boxes_entry
    entry = boxes.entry
    for name, color in (("Anna", [0, 255, 0]), ("Ben", [0, 0, 255])):
        sub = boxes.box_subentry(name)
        hass.config_entries.async_update_subentry(
            entry, sub, data={**sub.data, CONF_DEFAULT_COLOR: color}
        )
        await hass.async_block_till_done()
    await _tag_on(hass, boxes.dev_anna, "04-A1-B2-C3")
    await _tag_on(hass, boxes.dev_ben, "04-A1-B2-C3")
    anna = [c.data for c in boxes.led["anna"] if c.data["mode"] == "playing"][-1]
    ben = [c.data for c in boxes.led["ben"] if c.data["mode"] == "playing"][-1]
    assert (anna["r"], anna["g"], anna["b"]) == (0, 255, 0)
    assert (ben["r"], ben["g"], ben["b"]) == (0, 0, 255)
