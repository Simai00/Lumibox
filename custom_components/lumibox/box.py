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
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_BOX_COLOR,
    LED_ERROR,
    LED_HOLD,
    LED_LOADING,
    LED_OFF,
    LED_PAUSED,
    LED_PLAYING,
    LED_UNKNOWN,
    LED_VOLUME,
    REMOVAL_DEBOUNCE_S,
    RESUME_MAX_AGE_S,
)
from .library import Figure, FigureLibrary, normalize_uid
from .player import PlayerError

if TYPE_CHECKING:
    from .player import PlayerSnapshot

_LOGGER = logging.getLogger(__name__)

STATE_PLAYING = "playing"


class Player(Protocol):
    """Schnittstelle von PlayerAdapter, die der Controller nutzt."""

    def is_available(self) -> bool: ...
    def snapshot(self) -> PlayerSnapshot: ...
    def get_volume(self) -> float | None: ...
    async def play(self, media_uri: str, start_item: str | None = None) -> None: ...
    async def pause(self) -> None: ...
    async def next_track(self) -> None: ...
    async def previous_track(self) -> None: ...
    async def set_volume(self, volume: float) -> None: ...


class Led(Protocol):
    """Schnittstelle von LedAdapter."""

    async def show(
        self, mode: str, level: int = 0, color: tuple[int, int, int] = (0, 0, 0)
    ) -> None: ...


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
    default_color: tuple[int, int, int] = DEFAULT_BOX_COLOR


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
        # media_content_id (aktueller Titel) und Zeitpunkt der letzten Pause durch die Box.
        self._snapshot_at_removal: str | None = None
        self._paused_at: datetime | None = None
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
        handlers = {
            "play_pause": self.play_pause,
            "next": self.next_track,
            "prev": self.previous_track,
        }
        if action in handlers:
            await handlers[action]()
            return
        if action in ("rotate_cw", "rotate_ccw"):
            await self.rotate(1 if action == "rotate_cw" else -1)
            return
        _LOGGER.debug("Unbekannte Aktion %r von Box %s ignoriert", action, self._config.name)

    async def tag_on(self, uid: str) -> None:
        """Figur aufgelegt (Spec 6.2 tag_on)."""
        norm = normalize_uid(uid)
        if not norm:
            _LOGGER.debug("tag_on ohne gültige UID (%r) ignoriert", uid)
            return
        _LOGGER.debug("Box %s: tag_on %s empfangen", self._config.name, norm)
        async with self._lock:
            # Eine bereits ausgelöste, aber noch wartende Abnahme ist damit überholt.
            self._tag_seq += 1
            _LOGGER.debug(
                "Box %s: tag_on %s verarbeitet (Zustand %s, Abnahme wartend: %s)",
                self._config.name,
                norm,
                self._state,
                self._pending_off_uid,
            )
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
            # Player unverändert lassen, aber die LED nachziehen (z. B. nach Box-Neustart).
            _LOGGER.debug("Doppeltes tag_on für %s, LED aktualisiert", figure.name)
            if self._state is BoxState.PLAYING:
                await self._led.show(LED_PLAYING, color=self._color_for(figure))
            elif self._state is BoxState.PAUSED_BY_BOX:
                await self._led.show(LED_HOLD)
            return

        await self._start(figure)

    async def tag_off(self, uid: str) -> None:
        """Figur abgenommen: Entprellung starten (Spec 6.2 tag_off)."""
        norm = normalize_uid(uid)
        _LOGGER.debug("Box %s: tag_off %s empfangen", self._config.name, norm)
        async with self._lock:
            _LOGGER.debug(
                "Box %s: tag_off %s verarbeitet (Zustand %s), Entprellung startet",
                self._config.name,
                norm,
                self._state,
            )
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

    # --- Taster und Encoder (Spec 6.3) -----------------------------------

    def _controls_active(self) -> bool:
        """Taster/Encoder wirken nur mit Figur und nicht während des Ladens."""
        return self._current_figure is not None and self._state in (
            BoxState.PLAYING,
            BoxState.PAUSED_BY_BOX,
        )

    async def _control_failed(self, what: str, err: PlayerError) -> None:
        _LOGGER.warning("Box %s: %s fehlgeschlagen: %s", self._config.name, what, err)
        await self._led.show(LED_ERROR)

    async def play_pause(self) -> None:
        """Taster: zwischen Pause und Wiedergabe wechseln."""
        async with self._lock:
            if not self._controls_active():
                return
            figure = self._current_figure
            try:
                if self._state is BoxState.PLAYING:
                    content_id = self._player.snapshot().media_content_id
                    await self._player.pause()
                    self._remember_pause(content_id)
                    await self._led.show(LED_HOLD)
                    self._set(BoxState.PAUSED_BY_BOX, figure)
                else:
                    await self._cap_volume()
                    await self._play_figure(figure, self._snapshot_at_removal)
                    await self._led.show(LED_PLAYING, color=self._color_for(figure))
                    self._set(BoxState.PLAYING, figure)
            except PlayerError as err:
                await self._control_failed("Play/Pause", err)

    async def next_track(self) -> None:
        """Taster: nächster Titel."""
        async with self._lock:
            if not self._controls_active():
                return
            try:
                await self._player.next_track()
            except PlayerError as err:
                await self._control_failed("Nächster Titel", err)

    async def previous_track(self) -> None:
        """Taster: vorheriger Titel."""
        async with self._lock:
            if not self._controls_active():
                return
            try:
                await self._player.previous_track()
            except PlayerError as err:
                await self._control_failed("Vorheriger Titel", err)

    async def rotate(self, direction: int) -> None:
        """Encoder: Lautstärke um volume_step ändern (+1 lauter, -1 leiser)."""
        async with self._lock:
            if not self._controls_active():
                return
            try:
                volume = self._player.get_volume()
                base = 0 if volume is None else round(volume * 100)
                step = self._config.volume_step * (1 if direction > 0 else -1)
                max_volume = self._config.max_volume
                new = max(0, min(max_volume, base + step))
                await self._player.set_volume(new / 100)
                level = round(new / max_volume * 100) if max_volume else 0
                await self._led.show(LED_VOLUME, level)
            except PlayerError as err:
                await self._control_failed("Lautstärke", err)

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
            f"lumibox Abnahme {self._config.name}",
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
        if figure is None and uid is not None:
            # Z. B. nach einem HA-Neustart: Der Controller kennt keine Figur, Music
            # Assistant spielt aber noch. Eine bekannte Figur wird dann trotzdem angehalten.
            known = self._library.lookup(uid)
            if known is not None and self._player.snapshot().state == STATE_PLAYING:
                figure = known
        if figure is None or uid is None or normalize_uid(figure.uid) != uid:
            await self._led.show(LED_OFF)
            return
        try:
            snapshot = self._player.snapshot()
            _LOGGER.debug(
                "Box %s: Abnahme von %s, pausiere (Player %s, Inhalt %s)",
                self._config.name,
                figure.name,
                snapshot.state,
                snapshot.media_content_id,
            )
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
        self._remember_pause(self._content_id_for_resume(snapshot.media_content_id))
        self._last_figure = figure
        await self._led.show(LED_PAUSED)
        self._set(BoxState.REMOVED, None)

    async def _handle_unknown(self, uid: str) -> None:
        figure = self._current_figure
        if figure is not None:
            # Die bisherige Figur ist noch aktiv (Abnahme lag im Lock-Fenster): anhalten.
            await self._pause_current(figure)
        self._last_unknown_uid = uid
        persistent_notification.async_create(
            self._hass,
            f"Neue Figur auf Box {self._config.name} erkannt (UID {uid}). "
            "Unter Einstellungen → Lumibox → Figur hinzufügen anlegen, "
            "die UID ist vorausgefüllt.",
            title="Lumibox",
            notification_id=f"lumibox_unknown_{self._config.subentry_id}",
        )
        await self._led.show(LED_UNKNOWN)
        self._set(BoxState.IDLE, None)
        if self._on_unknown_tag is not None:
            try:
                self._on_unknown_tag(uid)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Fehler in on_unknown_tag der Box %s", self._config.name)

    async def _pause_current(self, figure: Figure) -> None:
        """Aktive Figur anhalten und für ein späteres Fortsetzen merken; Aufrufer hält den Lock."""
        if self._state is BoxState.PAUSED_BY_BOX:
            self._last_figure = figure
            self._remember_pause(
                self._content_id_for_resume(self._player.snapshot().media_content_id)
            )
            return
        self._last_figure = figure
        self._snapshot_at_removal = None
        try:
            snapshot = self._player.snapshot()
            await self._player.pause()
        except PlayerError as err:
            _LOGGER.warning(
                "Box %s: Pause von %s fehlgeschlagen: %s", self._config.name, figure.name, err
            )
            return
        self._remember_pause(snapshot.media_content_id)

    def _remember_pause(self, content_id: str | None) -> None:
        """Titel und Zeitpunkt einer Pause durch die Box merken (Spec 6.2)."""
        self._snapshot_at_removal = content_id
        self._paused_at = dt_util.utcnow()

    def _content_id_for_resume(self, current: str | None) -> str | None:
        """Nach einer Pause per Taster den damals gemerkten Titel behalten.

        Music Assistant setzt einen pausierten Player nach kurzer Zeit auf ``idle``
        und meldet dann ggf. keinen Inhalt mehr.
        """
        if self._state is BoxState.PAUSED_BY_BOX and self._snapshot_at_removal is not None:
            return self._snapshot_at_removal
        return current

    def _resume_item(self, figure: Figure) -> str | None:
        """Titel zum Fortsetzen, falls dieselbe Figur innerhalb der Frist zurückkommt."""
        if (
            figure != self._last_figure
            or self._snapshot_at_removal is None
            or self._paused_at is None
        ):
            return None
        age = (dt_util.utcnow() - self._paused_at).total_seconds()
        if age > RESUME_MAX_AGE_S:
            return None
        return self._snapshot_at_removal

    async def _play_figure(self, figure: Figure, start_item: str | None) -> None:
        """Figur abspielen, mit ``start_item`` ab dem gemerkten Titel.

        Fortsetzen geht über ``play_media`` statt ``media_play``, weil Letzteres mit
        Music Assistant und Sonos nicht zuverlässig weiterspielt. Scheitert der Start
        beim gemerkten Titel, wird die Figur einmal von vorn gestartet.
        """
        if start_item is None:
            _LOGGER.debug("Box %s: Neustart von %s", self._config.name, figure.name)
            await self._player.play(figure.media_uri)
            return
        _LOGGER.debug(
            "Box %s: Fortsetzen von %s ab %s", self._config.name, figure.name, start_item
        )
        try:
            await self._player.play(figure.media_uri, start_item=start_item)
        except PlayerError as err:
            _LOGGER.debug(
                "Box %s: Fortsetzen ab %s fehlgeschlagen (%s), Neustart von %s",
                self._config.name,
                start_item,
                err,
                figure.name,
            )
            await self._player.play(figure.media_uri)

    async def _start(self, figure: Figure) -> None:
        """Figur abspielen: weiterspielen oder neu starten (Spec 6.2 Schritte 3–6)."""
        self._set(self._state, figure)
        try:
            snapshot = self._player.snapshot()
            _LOGGER.debug(
                "Box %s: Start %s (Player %s, Inhalt %s, gemerkt %s, letzte Figur %s)",
                self._config.name,
                figure.name,
                snapshot.state,
                snapshot.media_content_id,
                self._snapshot_at_removal,
                self._last_figure.name if self._last_figure else None,
            )
            start_item = self._resume_item(figure)
            self._set(BoxState.LOADING, figure)
            await self._led.show(LED_LOADING)
            await self._cap_volume()
            await self._play_figure(figure, start_item)
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
        except Exception:  # noqa: BLE001 - z. B. vol.Invalid nach geändertem MA-Schema
            _LOGGER.exception(
                "Box %s: Unerwarteter Fehler beim Abspielen von %s",
                self._config.name,
                figure.name,
            )
            await self._led.show(LED_ERROR)
            self._set(BoxState.IDLE, None)
            return
        after = self._player.snapshot()
        _LOGGER.debug(
            "Box %s: %s gestartet (Player %s, Inhalt %s)",
            self._config.name,
            figure.name,
            after.state,
            after.media_content_id,
        )
        await self._led.show(LED_PLAYING, color=self._color_for(figure))
        self._set(BoxState.PLAYING, figure)

    def _color_for(self, figure: Figure) -> tuple[int, int, int]:
        """LED-Farbe einer Figur: eigene Farbe, sonst die Standardfarbe der Box."""
        return figure.color or self._config.default_color

    async def _cap_volume(self) -> None:
        """Lautstärke auf höchstens max_volume senken."""
        limit = self._config.max_volume / 100
        volume = self._player.get_volume()
        if volume is not None and volume > limit:
            await self._player.set_volume(limit)
