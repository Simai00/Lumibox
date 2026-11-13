"""Test-Doubles für PlayerAdapter und LedAdapter."""

from __future__ import annotations

from custom_components.home_tonie.player import PlayerError, PlayerSnapshot


class FakePlayer:
    """Spiegelt die Schnittstelle von PlayerAdapter und zeichnet Aufrufe auf."""

    def __init__(
        self,
        state: str | None = "idle",
        media_content_id: str | None = None,
        volume: float | None = 0.8,
        available: bool = True,
    ) -> None:
        self.state = state
        self.media_content_id = media_content_id
        self.volume = volume
        self.available = available
        self.calls: list[tuple] = []

    def is_available(self) -> bool:
        return self.available

    def snapshot(self) -> PlayerSnapshot:
        if not self.available:
            return PlayerSnapshot("unavailable", self.media_content_id)
        return PlayerSnapshot(self.state, self.media_content_id)

    def get_volume(self) -> float | None:
        return self.volume if self.available else None

    def _check(self) -> None:
        if not self.available:
            raise PlayerError("FakePlayer nicht verfügbar")

    async def play(self, media_uri: str) -> None:
        self._check()
        self.calls.append(("play", media_uri))
        self.state = "playing"
        self.media_content_id = media_uri

    async def resume(self) -> None:
        self._check()
        self.calls.append(("resume",))
        self.state = "playing"

    async def pause(self) -> None:
        self._check()
        self.calls.append(("pause",))
        self.state = "paused"

    async def next_track(self) -> None:
        self._check()
        self.calls.append(("next_track",))

    async def previous_track(self) -> None:
        self._check()
        self.calls.append(("previous_track",))

    async def set_volume(self, volume: float) -> None:
        self._check()
        self.calls.append(("set_volume", volume))
        self.volume = volume


class FakeLed:
    """Spiegelt LedAdapter und zeichnet angezeigte Modi auf."""

    def __init__(self) -> None:
        self.shows: list[tuple[str, int]] = []

    async def show(self, mode: str, level: int = 0) -> None:
        self.shows.append((mode, level))
