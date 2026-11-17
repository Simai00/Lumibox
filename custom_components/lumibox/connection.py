"""Verbindungsstatus einer Box, abgeleitet aus den ESPHome-Entitäten ihres Geräts."""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

ESPHOME_PLATFORM = "esphome"


def is_device_entity(unique_id: str) -> bool:
    """True für Entitäten der Box-Firmware, False für die ESPHome-Dashboard-Entität.

    Die Dashboard-Update-Entität hat die reine MAC als unique_id und bleibt nach einem
    erwarteten Verbindungsabbruch verfügbar. Native unique_ids sind v1/v2
    "{mac}-{typ}-{name}" oder v3 "{mac}/{geraet}/{typ}/{name}", enthalten also "-" oder "/".
    """
    return "-" in unique_id or "/" in unique_id


class BoxConnection:
    """Verbunden = mindestens eine ESPHome-Entität des Geräts ist nicht `unavailable`.

    Nutzt nur öffentliche Schnittstellen (Entity-Registry und States).
    """

    def __init__(self, hass: HomeAssistant, esphome_device_id: str) -> None:
        self._hass = hass
        self._device_id = esphome_device_id
        self._listeners: list[Callable[[], None]] = []
        self._entity_ids: frozenset[str] = frozenset()
        self._connected = False
        self._unsub_states: CALLBACK_TYPE | None = None
        self._unsub_registry: CALLBACK_TYPE | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        """Listener anmelden; wird nur bei einem Wechsel von `connected` gerufen."""
        self._listeners.append(cb)

        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    async def async_start(self) -> None:
        """Entitäten des Geräts ermitteln und Änderungen verfolgen."""
        self._unsub_registry = self._hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_registry_update
        )
        self._retrack()
        self._connected = self._compute()

    async def async_stop(self) -> None:
        """Alle Listener abmelden."""
        if self._unsub_registry is not None:
            self._unsub_registry()
            self._unsub_registry = None
        if self._unsub_states is not None:
            self._unsub_states()
            self._unsub_states = None
        self._entity_ids = frozenset()
        self._listeners.clear()

    def _esphome_entity_ids(self) -> frozenset[str]:
        registry = er.async_get(self._hass)
        return frozenset(
            entry.entity_id
            for entry in er.async_entries_for_device(registry, self._device_id)
            if entry.platform == ESPHOME_PLATFORM and is_device_entity(entry.unique_id)
        )

    def _compute(self) -> bool:
        for entity_id in self._entity_ids:
            state = self._hass.states.get(entity_id)
            if state is not None and state.state != STATE_UNAVAILABLE:
                return True
        return False

    def _retrack(self) -> None:
        """State-Tracking auf die aktuellen ESPHome-Entitäten des Geräts umstellen."""
        entity_ids = self._esphome_entity_ids()
        if entity_ids == self._entity_ids and self._unsub_states is not None:
            return
        if self._unsub_states is not None:
            self._unsub_states()
            self._unsub_states = None
        self._entity_ids = entity_ids
        if entity_ids:
            self._unsub_states = async_track_state_change_event(
                self._hass, list(entity_ids), self._handle_state_change
            )

    @callback
    def _update(self) -> None:
        connected = self._compute()
        if connected == self._connected:
            return
        self._connected = connected
        for cb in list(self._listeners):
            cb()

    @callback
    def _handle_state_change(self, event: Event) -> None:
        self._update()

    @callback
    def _handle_registry_update(self, event: Event) -> None:
        self._retrack()
        self._update()
