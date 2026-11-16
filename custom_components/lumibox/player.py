"""Adapter für den Music-Assistant-Player (media_player-Entität)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .library import InvalidMediaUri, to_ma_media


class PlayerError(Exception):
    """Player nicht verfügbar oder Service-Aufruf fehlgeschlagen."""


@dataclass(frozen=True)
class PlayerSnapshot:
    """Momentaufnahme des Player-Zustands."""

    state: str | None
    media_content_id: str | None


class PlayerAdapter:
    """Steuert einen Music-Assistant-Player über HA-Services."""

    def __init__(self, hass: HomeAssistant, entity_id: str, ma_username: str) -> None:
        self._hass = hass
        self._entity_id = entity_id
        self._ma_username = ma_username

    def is_available(self) -> bool:
        state = self._hass.states.get(self._entity_id)
        return state is not None and state.state != STATE_UNAVAILABLE

    def snapshot(self) -> PlayerSnapshot:
        state = self._hass.states.get(self._entity_id)
        if state is None:
            return PlayerSnapshot(None, None)
        return PlayerSnapshot(state.state, state.attributes.get("media_content_id"))

    def get_volume(self) -> float | None:
        state = self._hass.states.get(self._entity_id)
        if state is None:
            return None
        volume = state.attributes.get("volume_level")
        return None if volume is None else float(volume)

    async def play(self, media_uri: str, start_item: str | None = None) -> None:
        """Figur abspielen; mit ``start_item`` ab diesem Titel (URI/ID laut MA)."""
        try:
            media_id, media_type = to_ma_media(media_uri)
        except InvalidMediaUri as err:
            raise PlayerError(f"Ungültige Medien-URI: {media_uri!r}") from err
        data: dict[str, Any] = {
            "media_id": media_id,
            "media_type": media_type,
            "enqueue": "replace",
            "username": self._ma_username,
        }
        if start_item is not None:
            data["start_item"] = start_item
        await self._call("music_assistant", "play_media", data)

    async def resume(self) -> None:
        await self._call("media_player", "media_play")

    async def pause(self) -> None:
        await self._call("media_player", "media_pause")

    async def next_track(self) -> None:
        await self._call("media_player", "media_next_track")

    async def previous_track(self) -> None:
        await self._call("media_player", "media_previous_track")

    async def set_volume(self, volume: float) -> None:
        await self._call(
            "media_player", "volume_set", {"volume_level": min(1.0, max(0.0, volume))}
        )

    async def _call(self, domain: str, service: str, data: dict[str, Any] | None = None) -> None:
        if not self.is_available():
            raise PlayerError(f"Player {self._entity_id} nicht verfügbar")
        try:
            await self._hass.services.async_call(
                domain,
                service,
                {"entity_id": self._entity_id, **(data or {})},
                blocking=True,
            )
        except HomeAssistantError as err:
            raise PlayerError(f"{domain}.{service} fehlgeschlagen: {err}") from err
