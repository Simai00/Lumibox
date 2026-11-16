"""Lumibox-Integration: Setup, Event-Routing und Hot-Update der Figuren."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback

from .box import BoxConfig, BoxController
from .const import (
    CONF_DEFAULT_COLOR,
    DEFAULT_BOX_COLOR,
    CONF_ESPHOME_DEVICE_ID,
    CONF_MA_USERNAME,
    CONF_MAX_VOLUME,
    CONF_PLAYER_ENTITY_ID,
    CONF_VOLUME_STEP,
    DEFAULT_MAX_VOLUME,
    DEFAULT_VOLUME_STEP,
    EVENT_TYPE,
    SUBENTRY_BOX,
)
from .led import LedAdapter
from .library import FigureLibrary, parse_rgb
from .player import PlayerAdapter

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


@dataclass
class LumiboxData:
    """Laufzeitdaten des Haupteintrags."""

    library: FigureLibrary
    controllers: dict[str, BoxController]
    last_unknown_uid: str | None = None


type LumiboxConfigEntry = ConfigEntry[LumiboxData]


def _box_snapshot(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    """Stand der Box-Subentries (subentry_id → Kopie der Daten)."""
    return {
        sub.subentry_id: dict(sub.data)
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_BOX
    }


def _box_config(subentry_id: str, title: str, data: Mapping[str, Any]) -> BoxConfig:
    return BoxConfig(
        subentry_id=subentry_id,
        name=data.get("name", title),
        esphome_device_id=data[CONF_ESPHOME_DEVICE_ID],
        player_entity_id=data[CONF_PLAYER_ENTITY_ID],
        ma_username=data[CONF_MA_USERNAME],
        max_volume=int(data.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME)),
        volume_step=int(data.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)),
        default_color=parse_rgb(data.get(CONF_DEFAULT_COLOR)) or DEFAULT_BOX_COLOR,
    )


async def async_setup_entry(hass: HomeAssistant, entry: LumiboxConfigEntry) -> bool:
    """Haupteintrag einrichten: Bibliothek, Controller pro Box, Event-Listener."""
    library = FigureLibrary(FigureLibrary.figures_from_entry(entry))
    data = LumiboxData(library=library, controllers={})

    @callback
    def _on_unknown_tag(uid: str) -> None:
        data.last_unknown_uid = uid

    for sub in entry.subentries.values():
        if sub.subentry_type != SUBENTRY_BOX:
            continue
        config = _box_config(sub.subentry_id, sub.title, sub.data)
        data.controllers[config.esphome_device_id] = BoxController(
            hass,
            config,
            library,
            PlayerAdapter(hass, config.player_entity_id, config.ma_username),
            LedAdapter(hass, config.esphome_device_id),
            on_unknown_tag=_on_unknown_tag,
        )
    entry.runtime_data = data

    async def _dispatch(controller: BoxController, event_data: Mapping[str, Any]) -> None:
        try:
            await controller.handle_event(event_data)
        except Exception:  # noqa: BLE001 - Fehler einer Box dürfen nie nach oben durchschlagen
            _LOGGER.exception(
                "Fehler beim Verarbeiten von %s für Box %s", dict(event_data), controller.config.name
            )

    # Laufende Ereignis-Tasks; beim Unload werden sie vor dem Shutdown abgewartet.
    inflight: set[asyncio.Task[None]] = set()

    @callback
    def _on_event(event: Event) -> None:
        device_id = event.data.get("device_id")
        controller = data.controllers.get(device_id) if isinstance(device_id, str) else None
        if controller is None:
            _LOGGER.debug("Ereignis von unbekanntem Gerät %r ignoriert: %s", device_id, event.data)
            return
        task = entry.async_create_task(
            hass,
            _dispatch(controller, dict(event.data)),
            f"lumibox Ereignis {controller.config.name}",
        )
        if not task.done():
            inflight.add(task)
            task.add_done_callback(inflight.discard)

    async def _async_shutdown() -> None:
        """Nach dem Abmelden des Listeners laufende Ereignisse abwarten, dann Controller stoppen.

        Sonst könnte ein Ereignis, das noch auf den Box-Lock wartet, nach dem Shutdown
        einen Entprell-Timer starten oder Wiedergabe auslösen.
        """
        if inflight:
            await asyncio.wait(set(inflight))
        for controller in data.controllers.values():
            controller.async_shutdown()

    # on_unload-Callbacks laufen in umgekehrter Reihenfolge: erst Listener abmelden, dann Shutdown.
    entry.async_on_unload(_async_shutdown)
    entry.async_on_unload(hass.bus.async_listen(EVENT_TYPE, _on_event))
    entry.async_on_unload(
        entry.add_update_listener(partial(_async_update_listener, _box_snapshot(entry)))
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    boxes_at_setup: dict[str, dict[str, Any]], hass: HomeAssistant, entry: LumiboxConfigEntry
) -> None:
    """Box-Änderungen → Reload; nur Figuren geändert → Bibliothek ersetzen."""
    if _box_snapshot(entry) != boxes_at_setup:
        _LOGGER.debug("Box-Konfiguration geändert, lade Lumibox neu")
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return
    entry.runtime_data.library.replace(FigureLibrary.figures_from_entry(entry))


async def async_unload_entry(hass: HomeAssistant, entry: LumiboxConfigEntry) -> bool:
    """Haupteintrag entladen; Listener und Controller-Shutdown laufen über async_on_unload."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

