"""BoxController: Zustandsautomat einer Box (Spec Abschnitt 6)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any, Protocol

from homeassistant.components import persistent_notification
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    LED_ERROR,
    LED_LOADING,
    LED_OFF,
    LED_PAUSED,
    LED_PLAYING,
    LED_UNKNOWN,
    REMOVAL_DEBOUNCE_S,
)
from .library import Figure, FigureLibrary, normalize_uid
from .player import PlayerError

if TYPE_CHECKING:
    from .player import PlayerSnapshot

_LOGGER = logging.getLogger(__name__)

STATE_PAUSED = "paused"


class Player(Protocol):
    """Schnittstelle von PlayerAdapter, die der Controller nutzt."""

    def is_available(self) -> bool: ...
    def snapshot(self) -> PlayerSnapshot: ...
    def get_volume(self) -> float | None: ...
    async def play(self, media_uri: str) -> None: ...
    async def resume(self) -> None: ...
    async def pause(self) -> None: ...
    async def next_track(self) -> None: ...
    async def previous_track(self) -> None: ...
    async def set_volume(self, volume: float) -> None: ...


class Led(Protocol):
    """Schnittstelle von LedAdapter."""

    async def show(self, mode: str, level: int = 0) -> None: ...


@dataclass(frozen=True)
class BoxConfig:
    """Konfiguration einer Box (aus dem Subentry)."""

    subentry_id: str
    name: str
    esphome_device_id: str
    player_entity_id: str
    ma_username: str
    max_volume: int
    volume_step: int


class BoxState(StrEnum):
    """Zustände einer Box (Spec 6.1)."""

    IDLE = "idle"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED_BY_BOX = "paused_by_box"
    REMOVED = "removed"


class BoxController:
    """Steuert Wiedergabe und LED einer Box anhand der Box-Ereignisse."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: BoxConfig,
        library: FigureLibrary,
        player: Player,
        led: Led,
        on_unknown_tag: Callable[[str], None] | None = None,
    ) -> None:
        self._hass = hass
        self._config = config
        self._library = library
        self._player = player
        self._led = led
        self._on_unknown_tag = on_unknown_tag
        self._listeners: list[Callable[[], None]] = []

        self._state = BoxState.IDLE
        self._current_figure: Figure | None = None
        self._last_figure: Figure | None = None
        self._snapshot_at_removal: str | None = None
        self._last_unknown_uid: str | None = None

        self._pending_off_uid: str | None = None
        self._cancel_debounce: CALLBACK_TYPE | None = None
        self._removal_task: asyncio.Task[None] | None = None
        # Serialisiert alle zustandsändernden Abläufe der Box (auch Task 6: Taster/Encoder).
        self._lock = asyncio.Lock()
        # Zählt tag_on-Ereignisse; eine Abnahme mit veraltetem Stand wird verworfen.
        self._tag_seq = 0

    # --- Öffentliche Eigenschaften -------------------------------------

    @property
    def config(self) -> BoxConfig:
        return self._config

    @property
    def state(self) -> BoxState:
        return self._state

    @property
    def current_figure(self) -> Figure | None:
        return self._current_figure

    @property
    def last_unknown_uid(self) -> str | None:
        return self._last_unknown_uid

    # --- Listener -------------------------------------------------------

    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        """Listener für Zustandsänderungen registrieren; gibt die Abmeldung zurück."""
        self._listeners.append(cb)

        def remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return remove

    def _notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:  # noqa: BLE001 - Listener dürfen den Controller nicht stören
                _LOGGER.exception("Fehler in Listener der Box %s", self._config.name)

    def _set(self, state: BoxState, figure: Figure | None) -> None:
        self._state = state
        self._current_figure = figure
        self._notify()

    # --- Ereignisse -----------------------------------------------------

    async def handle_event(self, data: Mapping[str, Any]) -> None:
        """Ein Box-Ereignis anhand von ``action`` verteilen."""
        action = data.get("action")
        if action in ("tag_on", "tag_off"):
            uid = data.get("uid")
            if not isinstance(uid, str) or not uid:
                _LOGGER.debug("Ereignis %s ohne UID ignoriert", action)
                return
            if action == "tag_on":
                await self.tag_on(uid)
            else:
                await self.tag_off(uid)
            return
        _LOGGER.debug("Unbekannte Aktion %r von Box %s ignoriert", action, self._config.name)

    async def tag_on(self, uid: str) -> None:
        """Figur aufgelegt (Spec 6.2 tag_on)."""
        norm = normalize_uid(uid)
        if not norm:
            _LOGGER.debug("tag_on ohne gültige UID (%r) ignoriert", uid)
            return
        async with self._lock:
            # Eine bereits ausgelöste, aber noch wartende Abnahme ist damit überholt.
            self._tag_seq += 1
            await self._tag_on_locked(norm)

    async def _tag_on_locked(self, norm: str) -> None:
        figure = self._library.lookup(norm)

        if self._cancel_debounce is not None:
            pending_uid = self._pending_off_uid
            self._cancel_timer()
            if pending_uid == norm:
                # Kurzer Lese-Aussetzer: Die Figur war nie wirklich weg.
                return
            if figure is not None:
                # Schneller Wechsel: alte Figur ohne pause() merken, die neue spielt gleich.
                self._last_figure = self._current_figure
                self._snapshot_at_removal = None
                self._current_figure = None
            else:
                # Wechsel auf ein unbekanntes Tag: alte Figur regulär anhalten.
                await self._finish_removal(pending_uid)

        if figure is None:
            await self._handle_unknown(norm)
            return

        if self._current_figure == figure and self._state in (
            BoxState.LOADING,
            BoxState.PLAYING,
            BoxState.PAUSED_BY_BOX,
        ):
            _LOGGER.debug("Doppeltes tag_on für %s ignoriert", figure.name)
            return

        await self._start(figure)

    async def tag_off(self, uid: str) -> None:
        """Figur abgenommen: Entprellung starten (Spec 6.2 tag_off)."""
        norm = normalize_uid(uid)
        async with self._lock:
            if self._cancel_debounce is not None:
                if self._pending_off_uid == norm:
                    return
                # Ein anderes Tag war noch in der Entprellung: jetzt abschliessen.
                pending_uid = self._pending_off_uid
                self._cancel_timer()
                await self._finish_removal(pending_uid)
            self._pending_off_uid = norm
            self._cancel_debounce = async_call_later(
                self._hass, REMOVAL_DEBOUNCE_S, self._debounce_elapsed
            )

    @callback
    def async_shutdown(self) -> None:
        """Entprell-Timer und laufende Abnahme abbrechen (beim Entladen)."""
        self._cancel_timer()
        if self._removal_task is not None and not self._removal_task.done():
            self._removal_task.cancel()
        self._removal_task = None

    # --- Interna --------------------------------------------------------

    def _cancel_timer(self) -> None:
        if self._cancel_debounce is not None:
            self._cancel_debounce()
        self._cancel_debounce = None
        self._pending_off_uid = None

    @callback
    def _debounce_elapsed(self, _now: datetime) -> None:
        uid = self._pending_off_uid
        self._cancel_debounce = None
        self._pending_off_uid = None
        self._removal_task = self._hass.async_create_task(
            self._removal_after_debounce(uid, self._tag_seq),
            f"home_tonie Abnahme {self._config.name}",
        )

    async def _removal_after_debounce(self, uid: str | None, seq: int) -> None:
        """Abnahme nach Ablauf der Entprellung, serialisiert über den Lock."""
        async with self._lock:
            if seq != self._tag_seq:
                # Inzwischen wurde eine Figur aufgelegt: Diese Abnahme ist überholt.
                _LOGGER.debug("Abnahme von %s überholt, ignoriert", uid)
                return
            await self._finish_removal(uid)

    async def _finish_removal(self, uid: str | None) -> None:
        """Abnehmen abschliessen; Aufrufer hält den Lock."""
        figure = self._current_figure
        if figure is None or uid is None or normalize_uid(figure.uid) != uid:
            await self._led.show(LED_OFF)
            return
        try:
            snapshot = self._player.snapshot()
            await self._player.pause()
        except PlayerError as err:
            _LOGGER.warning(
                "Box %s: Pause nach Abnehmen von %s fehlgeschlagen: %s",
                self._config.name,
                figure.name,
                err,
            )
            self._last_figure = figure
            self._snapshot_at_removal = None
            await self._led.show(LED_ERROR)
            self._set(BoxState.IDLE, None)
            return
        self._snapshot_at_removal = snapshot.media_content_id
        self._last_figure = figure
        await self._led.show(LED_PAUSED)
        self._set(BoxState.REMOVED, None)

    async def _handle_unknown(self, uid: str) -> None:
        self._last_unknown_uid = uid
        persistent_notification.async_create(
            self._hass,
            f"Neue Figur auf Box {self._config.name} erkannt (UID {uid}). "
            "Unter Einstellungen → Home Tonie → Figur hinzufügen anlegen, "
            "die UID ist vorausgefüllt.",
            title="Home Tonie",
            notification_id=f"home_tonie_unknown_{self._config.subentry_id}",
        )
        await self._led.show(LED_UNKNOWN)
        self._set(BoxState.IDLE, None)
        if self._on_unknown_tag is not None:
            try:
                self._on_unknown_tag(uid)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Fehler in on_unknown_tag der Box %s", self._config.name)

    async def _start(self, figure: Figure) -> None:
        """Figur abspielen: weiterspielen oder neu starten (Spec 6.2 Schritte 3–6)."""
        self._set(self._state, figure)
        try:
            snapshot = self._player.snapshot()
            if (
                figure == self._last_figure
                and self._snapshot_at_removal is not None
                and snapshot.state == STATE_PAUSED
                and snapshot.media_content_id == self._snapshot_at_removal
            ):
                await self._cap_volume()
                await self._player.resume()
            else:
                self._set(BoxState.LOADING, figure)
                await self._led.show(LED_LOADING)
                await self._cap_volume()
                await self._player.play(figure.media_uri)
        except PlayerError as err:
            _LOGGER.warning(
                "Box %s: Wiedergabe von %s fehlgeschlagen: %s",
                self._config.name,
                figure.name,
                err,
            )
            await self._led.show(LED_ERROR)
            self._set(BoxState.IDLE, None)
            return
        await self._led.show(LED_PLAYING)
        self._set(BoxState.PLAYING, figure)

    async def _cap_volume(self) -> None:
        """Lautstärke auf höchstens max_volume senken."""
        limit = self._config.max_volume / 100
        volume = self._player.get_volume()
        if volume is not None and volume > limit:
            await self._player.set_volume(limit)
