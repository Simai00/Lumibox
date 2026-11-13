"""Tests für die Subentry-Flows (Box und Figur)."""

from types import SimpleNamespace

from homeassistant.components import persistent_notification
from homeassistant.components.persistent_notification import (
    _async_get_or_create_notifications,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
    SUBENTRY_BOX,
    SUBENTRY_FIGURE,
)

LINK = "https://open.spotify.com/intl-de/album/4aawyAB9vmqN3uQ7FjRGTy?si=abc"
URI = "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"


async def _start(hass, entry, subentry_type, source=SOURCE_USER, subentry_id=None):
    context = {"source": source}
    if subentry_id is not None:
        context["subentry_id"] = subentry_id
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, subentry_type), context=context
    )


async def _configure(hass, result, user_input):
    return await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)


def _subentries(entry, subentry_type):
    return [s for s in entry.subentries.values() if s.subentry_type == subentry_type]


def _suggested(result, key):
    for marker in result["data_schema"].schema:
        if marker == key:
            return (marker.description or {}).get("suggested_value")
    raise KeyError(key)


# --- Box ---------------------------------------------------------------------


async def test_add_box(hass, loaded_entry, esphome_device, ma_player):
    result = await _start(hass, loaded_entry, SUBENTRY_BOX)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await _configure(
        hass,
        result,
        {
            CONF_ESPHOME_DEVICE_ID: esphome_device.id,
            CONF_PLAYER_ENTITY_ID: ma_player.entity_id,
            CONF_MA_USERNAME: " anna ",
            CONF_MAX_VOLUME: 40.0,
            CONF_VOLUME_STEP: 3.0,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Tonie Anna"
    (box,) = _subentries(loaded_entry, SUBENTRY_BOX)
    assert box.title == "Home Tonie Anna"
    assert dict(box.data) == {
        "name": "Home Tonie Anna",
        CONF_ESPHOME_DEVICE_ID: esphome_device.id,
        CONF_PLAYER_ENTITY_ID: "media_player.kinderzimmer",
        CONF_MA_USERNAME: "anna",
        CONF_MAX_VOLUME: 40,
        CONF_VOLUME_STEP: 3,
    }
    assert type(box.data[CONF_MAX_VOLUME]) is int
    assert type(box.data[CONF_VOLUME_STEP]) is int


async def test_add_box_uses_given_name(hass, loaded_entry, esphome_device, ma_player):
    result = await _start(hass, loaded_entry, SUBENTRY_BOX)
    result = await _configure(
        hass,
        result,
        {
            "name": "Anna",
            CONF_ESPHOME_DEVICE_ID: esphome_device.id,
            CONF_PLAYER_ENTITY_ID: ma_player.entity_id,
            CONF_MA_USERNAME: "anna",
            CONF_MAX_VOLUME: 55,
            CONF_VOLUME_STEP: 5,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (box,) = _subentries(loaded_entry, SUBENTRY_BOX)
    assert box.title == "Anna"
    assert box.data["name"] == "Anna"
    assert box.data[CONF_MAX_VOLUME] == 55
    assert box.data[CONF_VOLUME_STEP] == 5


async def test_add_box_aborts_without_ma_players(hass, loaded_entry):
    result = await _start(hass, loaded_entry, SUBENTRY_BOX)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_ma_players"


async def test_box_device_in_use(hass, loaded_entry_with_box, esphome_device, ma_player):
    result = await _start(hass, loaded_entry_with_box, SUBENTRY_BOX)
    result = await _configure(
        hass,
        result,
        {
            "name": "Zweite",
            CONF_ESPHOME_DEVICE_ID: esphome_device.id,
            CONF_PLAYER_ENTITY_ID: ma_player.entity_id,
            CONF_MA_USERNAME: "ben",
            CONF_MAX_VOLUME: 40,
            CONF_VOLUME_STEP: 3,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"esphome_device_id": "device_in_use"}
    assert len(_subentries(loaded_entry_with_box, SUBENTRY_BOX)) == 1


async def test_box_shared_username_requires_confirmation(
    hass, loaded_entry_with_box, other_device, ma_player
):
    result = await _start(hass, loaded_entry_with_box, SUBENTRY_BOX)
    result = await _configure(
        hass,
        result,
        {
            "name": "Ben",
            CONF_ESPHOME_DEVICE_ID: other_device.id,
            CONF_PLAYER_ENTITY_ID: ma_player.entity_id,
            CONF_MA_USERNAME: "anna",
            CONF_MAX_VOLUME: 40,
            CONF_VOLUME_STEP: 3,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_shared_user"
    assert result["description_placeholders"]["boxes"] == "Anna"
    assert len(_subentries(loaded_entry_with_box, SUBENTRY_BOX)) == 1

    result = await _configure(hass, result, {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    boxes = {b.title: b for b in _subentries(loaded_entry_with_box, SUBENTRY_BOX)}
    assert set(boxes) == {"Anna", "Ben"}
    assert boxes["Ben"].data[CONF_ESPHOME_DEVICE_ID] == other_device.id
    assert boxes["Ben"].data[CONF_MA_USERNAME] == "anna"


async def test_reconfigure_box_keeps_own_device(hass, loaded_entry_with_box, esphome_device, ma_player):
    (box,) = _subentries(loaded_entry_with_box, SUBENTRY_BOX)
    result = await _start(
        hass, loaded_entry_with_box, SUBENTRY_BOX, SOURCE_RECONFIGURE, box.subentry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert _suggested(result, CONF_MA_USERNAME) == "anna"

    result = await _configure(
        hass,
        result,
        {
            "name": "Anna",
            CONF_ESPHOME_DEVICE_ID: esphome_device.id,
            CONF_PLAYER_ENTITY_ID: ma_player.entity_id,
            CONF_MA_USERNAME: "anna",
            CONF_MAX_VOLUME: 60.0,
            CONF_VOLUME_STEP: 2.0,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    box = loaded_entry_with_box.subentries[box.subentry_id]
    assert box.data[CONF_MAX_VOLUME] == 60
    assert type(box.data[CONF_MAX_VOLUME]) is int
    assert box.data[CONF_VOLUME_STEP] == 2


# --- Figur -------------------------------------------------------------------


async def test_add_figure_normalizes(hass, loaded_entry):
    result = await _start(hass, loaded_entry, SUBENTRY_FIGURE)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await _configure(
        hass,
        result,
        {"name": "Bobo", CONF_UID: "04-a1-b2-c3", CONF_MEDIA_URI: LINK, CONF_MODE: "restart"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bobo"
    (fig,) = _subentries(loaded_entry, SUBENTRY_FIGURE)
    assert fig.title == "Bobo"
    assert dict(fig.data) == {
        "name": "Bobo",
        CONF_UID: "04A1B2C3",
        CONF_MEDIA_URI: URI,
        CONF_MODE: "restart",
    }


async def test_figure_invalid_link(hass, loaded_entry):
    result = await _start(hass, loaded_entry, SUBENTRY_FIGURE)
    result = await _configure(
        hass,
        result,
        {
            "name": "Bobo",
            CONF_UID: "04A1B2C3",
            CONF_MEDIA_URI: "https://spotify.link/abc123",
            CONF_MODE: "restart",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"media_uri": "invalid_media_uri"}
    assert _subentries(loaded_entry, SUBENTRY_FIGURE) == []


async def test_figure_invalid_uid(hass, loaded_entry):
    result = await _start(hass, loaded_entry, SUBENTRY_FIGURE)
    result = await _configure(
        hass,
        result,
        {"name": "Bobo", CONF_UID: "--::", CONF_MEDIA_URI: URI, CONF_MODE: "restart"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"uid": "invalid_uid"}


async def test_figure_duplicate_uid(hass, loaded_entry_with_figure):
    result = await _start(hass, loaded_entry_with_figure, SUBENTRY_FIGURE)
    result = await _configure(
        hass,
        result,
        {"name": "Kopie", CONF_UID: "04:A1:B2:C3", CONF_MEDIA_URI: URI, CONF_MODE: "restart"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"uid": "uid_exists"}
    assert len(_subentries(loaded_entry_with_figure, SUBENTRY_FIGURE)) == 1


async def test_reconfigure_figure_keeps_own_uid(hass, loaded_entry_with_figure):
    (fig,) = _subentries(loaded_entry_with_figure, SUBENTRY_FIGURE)
    result = await _start(
        hass, loaded_entry_with_figure, SUBENTRY_FIGURE, SOURCE_RECONFIGURE, fig.subentry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert _suggested(result, CONF_UID) == "04A1B2C3"

    result = await _configure(
        hass,
        result,
        {
            "name": "Bobo Siebenschläfer",
            CONF_UID: "04a1b2c3",
            CONF_MEDIA_URI: "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
            CONF_MODE: "restart",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    fig = loaded_entry_with_figure.subentries[fig.subentry_id]
    assert fig.title == "Bobo Siebenschläfer"
    assert dict(fig.data) == {
        "name": "Bobo Siebenschläfer",
        CONF_UID: "04A1B2C3",
        CONF_MEDIA_URI: "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
        CONF_MODE: "restart",
    }


async def test_figure_uid_prefilled(hass, loaded_entry):
    loaded_entry.runtime_data = SimpleNamespace(last_unknown_uid="FFEE")
    result = await _start(hass, loaded_entry, SUBENTRY_FIGURE)
    assert result["type"] is FlowResultType.FORM
    assert _suggested(result, CONF_UID) == "FFEE"


async def test_figure_without_runtime_data_has_no_prefill(hass, loaded_entry):
    result = await _start(hass, loaded_entry, SUBENTRY_FIGURE)
    assert _suggested(result, CONF_UID) is None


# --- Nachträge aus dem Abschluss-Review --------------------------------------


async def test_box_empty_username(hass, loaded_entry, esphome_device, ma_player):
    result = await _start(hass, loaded_entry, SUBENTRY_BOX)
    result = await _configure(
        hass,
        result,
        {
            CONF_ESPHOME_DEVICE_ID: esphome_device.id,
            CONF_PLAYER_ENTITY_ID: ma_player.entity_id,
            CONF_MA_USERNAME: "   ",
            CONF_MAX_VOLUME: 40,
            CONF_VOLUME_STEP: 3,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MA_USERNAME: "invalid_username"}
    assert not _subentries(loaded_entry, SUBENTRY_BOX)


async def test_reconfigure_box_empty_username(
    hass, loaded_entry_with_box, esphome_device, ma_player
):
    (box,) = _subentries(loaded_entry_with_box, SUBENTRY_BOX)
    result = await _start(
        hass, loaded_entry_with_box, SUBENTRY_BOX, SOURCE_RECONFIGURE, box.subentry_id
    )
    result = await _configure(
        hass,
        result,
        {
            "name": "Anna",
            CONF_ESPHOME_DEVICE_ID: esphome_device.id,
            CONF_PLAYER_ENTITY_ID: ma_player.entity_id,
            CONF_MA_USERNAME: " ",
            CONF_MAX_VOLUME: 40,
            CONF_VOLUME_STEP: 3,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MA_USERNAME: "invalid_username"}
    assert loaded_entry_with_box.subentries[box.subentry_id].data[CONF_MA_USERNAME] == "anna"


async def test_figure_known_uid_not_prefilled(hass, loaded_entry_with_figure):
    loaded_entry_with_figure.runtime_data.last_unknown_uid = "04A1B2C3"
    result = await _start(hass, loaded_entry_with_figure, SUBENTRY_FIGURE)
    assert _suggested(result, CONF_UID) is None


async def test_figure_created_clears_unknown_uid_and_notifications(
    hass, loaded_entry_with_box
):
    (box,) = _subentries(loaded_entry_with_box, SUBENTRY_BOX)
    notification_id = f"home_tonie_unknown_{box.subentry_id}"
    persistent_notification.async_create(hass, "Neue Figur", notification_id=notification_id)
    loaded_entry_with_box.runtime_data.last_unknown_uid = "FFEE"

    result = await _start(hass, loaded_entry_with_box, SUBENTRY_FIGURE)
    assert _suggested(result, CONF_UID) == "FFEE"
    result = await _configure(
        hass,
        result,
        {"name": "Neu", CONF_UID: "ff:ee", CONF_MEDIA_URI: URI, CONF_MODE: "restart"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry_with_box.runtime_data.last_unknown_uid is None
    assert notification_id not in _async_get_or_create_notifications(hass)


async def test_figure_with_other_uid_keeps_unknown_uid(hass, loaded_entry_with_box):
    (box,) = _subentries(loaded_entry_with_box, SUBENTRY_BOX)
    notification_id = f"home_tonie_unknown_{box.subentry_id}"
    persistent_notification.async_create(hass, "Neue Figur", notification_id=notification_id)
    loaded_entry_with_box.runtime_data.last_unknown_uid = "FFEE"

    result = await _start(hass, loaded_entry_with_box, SUBENTRY_FIGURE)
    result = await _configure(
        hass,
        result,
        {"name": "Neu", CONF_UID: "AABB", CONF_MEDIA_URI: URI, CONF_MODE: "restart"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry_with_box.runtime_data.last_unknown_uid == "FFEE"
    assert notification_id in _async_get_or_create_notifications(hass)


async def test_figure_created_without_runtime_data(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Home Tonie", data={})
    entry.add_to_hass(hass)
    result = await _start(hass, entry, SUBENTRY_FIGURE)
    assert _suggested(result, CONF_UID) is None
    result = await _configure(
        hass,
        result,
        {"name": "Neu", CONF_UID: "FFEE", CONF_MEDIA_URI: URI, CONF_MODE: "restart"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(_subentries(entry, SUBENTRY_FIGURE)) == 1
