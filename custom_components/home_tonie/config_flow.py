"""Config Flow der Home-Tonie-Integration (Haupteintrag und Subentries)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.selector import (
    DeviceSelector,
    DeviceSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    ColorRGBSelector,
)

from .const import (
    CONF_COLOR,
    CONF_DEFAULT_COLOR,
    DEFAULT_BOX_COLOR,
    CONF_ESPHOME_DEVICE_ID,
    CONF_MA_USERNAME,
    CONF_MAX_VOLUME,
    CONF_MEDIA_URI,
    CONF_MODE,
    CONF_PLAYER_ENTITY_ID,
    CONF_UID,
    CONF_VOLUME_STEP,
    DEFAULT_MAX_VOLUME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
    MODE_RESTART,
    SUBENTRY_BOX,
    SUBENTRY_FIGURE,
)
from .library import InvalidMediaUri, normalize_spotify_uri, normalize_uid

MA_DOMAIN = "music_assistant"
ESPHOME_DOMAIN = "esphome"

BOX_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): TextSelector(),
        vol.Required(CONF_ESPHOME_DEVICE_ID): DeviceSelector(
            DeviceSelectorConfig(filter={"integration": ESPHOME_DOMAIN})
        ),
        vol.Required(CONF_PLAYER_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(filter={"domain": "media_player", "integration": MA_DOMAIN})
        ),
        vol.Required(CONF_MA_USERNAME): TextSelector(),
        vol.Required(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): NumberSelector(
            NumberSelectorConfig(
                min=5, max=100, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="%"
            )
        ),
        vol.Required(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): NumberSelector(
            NumberSelectorConfig(
                min=1, max=10, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="%"
            )
        ),
        vol.Required(CONF_DEFAULT_COLOR, default=list(DEFAULT_BOX_COLOR)): ColorRGBSelector(),
    }
)

FIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Required(CONF_UID): TextSelector(),
        vol.Required(CONF_MEDIA_URI): TextSelector(),
        vol.Required(CONF_MODE, default=MODE_RESTART): SelectSelector(
            SelectSelectorConfig(
                options=[MODE_RESTART], mode=SelectSelectorMode.DROPDOWN, translation_key=CONF_MODE
            )
        ),
        vol.Optional(CONF_COLOR): ColorRGBSelector(),
    }
)


class HomeTonieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Legt den einzigen Haupteintrag an."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Unterstützte Subentry-Typen: Box und Figur."""
        return {SUBENTRY_BOX: BoxSubentryFlow, SUBENTRY_FIGURE: FigureSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einrichtung bestätigen lassen."""
        if user_input is not None:
            return self.async_create_entry(title="Home Tonie", data={})
        return self.async_show_form(step_id="user")


class _HomeTonieSubentryFlow(ConfigSubentryFlow):
    """Gemeinsame Helfer für Box- und Figur-Flows."""

    def _is_reconfigure(self) -> bool:
        return self.source == SOURCE_RECONFIGURE

    def _other_subentries(self, subentry_type: str) -> list[ConfigSubentry]:
        """Andere Subentries desselben Typs; beim Reconfigure ohne das eigene."""
        own_id = self._get_reconfigure_subentry().subentry_id if self._is_reconfigure() else None
        return [
            sub
            for sub in self._get_entry().subentries.values()
            if sub.subentry_type == subentry_type and sub.subentry_id != own_id
        ]

    def _finish(self, title: str, data: dict[str, Any]) -> SubentryFlowResult:
        """Neues Subentry anlegen oder das bearbeitete aktualisieren."""
        if self._is_reconfigure():
            return self.async_update_and_abort(
                self._get_entry(), self._get_reconfigure_subentry(), title=title, data=data
            )
        return self.async_create_entry(title=title, data=data)


class BoxSubentryFlow(_HomeTonieSubentryFlow):
    """Box hinzufügen oder bearbeiten."""

    def __init__(self) -> None:
        super().__init__()
        self._pending: dict[str, Any] | None = None
        self._shared_boxes = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Neue Box."""
        if not _has_ma_players(self.hass):
            return self.async_abort(reason="no_ma_players")
        return await self._async_step_form("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Bestehende Box bearbeiten."""
        return await self._async_step_form("reconfigure", user_input)

    async def _async_step_form(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = self._build_data(user_input)
            others = self._other_subentries(SUBENTRY_BOX)
            if not data[CONF_MA_USERNAME]:
                errors[CONF_MA_USERNAME] = "invalid_username"
            elif any(
                sub.data.get(CONF_ESPHOME_DEVICE_ID) == data[CONF_ESPHOME_DEVICE_ID]
                for sub in others
            ):
                errors[CONF_ESPHOME_DEVICE_ID] = "device_in_use"
            else:
                shared = [
                    sub.title
                    for sub in others
                    if str(sub.data.get(CONF_MA_USERNAME, "")).casefold()
                    == data[CONF_MA_USERNAME].casefold()
                ]
                if shared:
                    self._pending = data
                    self._shared_boxes = ", ".join(shared)
                    return await self.async_step_confirm_shared_user()
                return self._finish(data[CONF_NAME], data)

        if user_input is not None:
            suggested: dict[str, Any] = user_input
        elif self._is_reconfigure():
            suggested = dict(self._get_reconfigure_subentry().data)
        else:
            suggested = {}
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(BOX_SCHEMA, suggested),
            errors=errors,
        )

    async def async_step_confirm_shared_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Warnen, dass Boxen mit gleichem MA-Benutzer nicht gleichzeitig spielen können."""
        assert self._pending is not None
        if user_input is not None:
            return self._finish(self._pending[CONF_NAME], self._pending)
        return self.async_show_form(
            step_id="confirm_shared_user",
            description_placeholders={
                "boxes": self._shared_boxes,
                "username": self._pending[CONF_MA_USERNAME],
            },
        )

    def _build_data(self, user_input: dict[str, Any]) -> dict[str, Any]:
        device_id = user_input[CONF_ESPHOME_DEVICE_ID]
        name = str(user_input.get(CONF_NAME) or "").strip() or _device_name(self.hass, device_id)
        return {
            CONF_NAME: name,
            CONF_ESPHOME_DEVICE_ID: device_id,
            CONF_PLAYER_ENTITY_ID: user_input[CONF_PLAYER_ENTITY_ID],
            CONF_MA_USERNAME: str(user_input[CONF_MA_USERNAME]).strip(),
            CONF_MAX_VOLUME: int(user_input[CONF_MAX_VOLUME]),
            CONF_VOLUME_STEP: int(user_input[CONF_VOLUME_STEP]),
            CONF_DEFAULT_COLOR: _rgb(user_input.get(CONF_DEFAULT_COLOR)) or list(DEFAULT_BOX_COLOR),
        }


class FigureSubentryFlow(_HomeTonieSubentryFlow):
    """Figur hinzufügen oder bearbeiten."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Neue Figur; UID mit dem zuletzt gemeldeten unbekannten Tag vorbelegt."""
        return await self._async_step_form("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Bestehende Figur bearbeiten."""
        return await self._async_step_form("reconfigure", user_input)

    async def _async_step_form(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip()
            uid = normalize_uid(str(user_input[CONF_UID]))
            if not uid:
                errors[CONF_UID] = "invalid_uid"
            elif any(
                normalize_uid(str(sub.data.get(CONF_UID, ""))) == uid
                for sub in self._other_subentries(SUBENTRY_FIGURE)
            ):
                errors[CONF_UID] = "uid_exists"
            try:
                media_uri = normalize_spotify_uri(str(user_input[CONF_MEDIA_URI]))
            except InvalidMediaUri:
                errors[CONF_MEDIA_URI] = "invalid_media_uri"
            if not errors:
                self._forget_unknown_uid(uid)
                data: dict[str, Any] = {
                    CONF_NAME: name,
                    CONF_UID: uid,
                    CONF_MEDIA_URI: media_uri,
                    CONF_MODE: user_input[CONF_MODE],
                }
                if (color := _rgb(user_input.get(CONF_COLOR))) is not None:
                    data[CONF_COLOR] = color
                return self._finish(name, data)

        if user_input is not None:
            suggested: dict[str, Any] = user_input
        elif self._is_reconfigure():
            suggested = dict(self._get_reconfigure_subentry().data)
        else:
            runtime = getattr(self._get_entry(), "runtime_data", None)
            last_uid = getattr(runtime, "last_unknown_uid", None)
            library = getattr(runtime, "library", None)
            if last_uid and library is not None and library.lookup(last_uid) is not None:
                last_uid = None  # inzwischen als Figur angelegt
            suggested = {CONF_UID: last_uid} if last_uid else {}
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(FIGURE_SCHEMA, suggested),
            errors=errors,
        )

    def _forget_unknown_uid(self, uid: str) -> None:
        """Wird das zuletzt unbekannte Tag angelegt: Vorbelegung und Hinweise entfernen."""
        entry = self._get_entry()
        runtime = getattr(entry, "runtime_data", None)
        last_uid = getattr(runtime, "last_unknown_uid", None)
        if not last_uid or normalize_uid(str(last_uid)) != uid:
            return
        runtime.last_unknown_uid = None
        for sub in entry.subentries.values():
            if sub.subentry_type == SUBENTRY_BOX:
                persistent_notification.async_dismiss(
                    self.hass, f"home_tonie_unknown_{sub.subentry_id}"
                )


def _has_ma_players(hass: HomeAssistant) -> bool:
    """Gibt es mindestens einen `media_player` der Integration Music Assistant?"""
    return any(
        ent.domain == "media_player" and ent.platform == MA_DOMAIN
        for ent in er.async_get(hass).entities.values()
    )


def _device_name(hass: HomeAssistant, device_id: str) -> str:
    """Anzeigename eines Geräts aus der Geräte-Registry."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return "Home Tonie"
    return device.name_by_user or device.name or "Home Tonie"


def _rgb(value: Any) -> list[int] | None:
    """Farbwähler-Wert als [r, g, b] (0–255); leer oder ungültig: None."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return [max(0, min(255, int(v))) for v in value]
    return None
