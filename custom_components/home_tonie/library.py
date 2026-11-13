"""Figurenbibliothek: UID- und Spotify-URI-Normalisierung, Figurensuche."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re

from homeassistant.config_entries import ConfigEntry

from .const import CONF_MEDIA_URI, CONF_MODE, CONF_UID, SUBENTRY_FIGURE

_SPOTIFY_TYPES = "album|playlist|track|artist|show|episode|audiobook"
_SPOTIFY_RE = re.compile(
    rf"^(?:spotify:(?P<t1>{_SPOTIFY_TYPES}):"
    rf"|https?://open\.spotify\.com/(?:intl-[A-Za-z]+/)?(?P<t2>{_SPOTIFY_TYPES})/)"
    r"(?P<id>[A-Za-z0-9]{22})/?(?:[?#].*)?$",
    re.IGNORECASE,
)
_MA_TYPES = {"show": "podcast", "episode": "podcast_episode"}


class InvalidMediaUri(ValueError):
    """Die Medien-URI ist keine gültige Spotify-URI oder -URL."""


def normalize_uid(raw: str) -> str:
    """UID in Grossbuchstaben, alle Nicht-Hex-Zeichen entfernt."""
    return re.sub(r"[^0-9A-Fa-f]", "", raw).upper()


def normalize_spotify_uri(raw: str) -> str:
    """Spotify-URL oder -URI in die Form `spotify:<typ>:<id>` bringen."""
    match = _SPOTIFY_RE.match(raw.strip())
    if not match:
        raise InvalidMediaUri(raw)
    return f"spotify:{(match['t1'] or match['t2']).lower()}:{match['id']}"


def to_ma_media(uri: str) -> tuple[str, str]:
    """`spotify:<typ>:<id>` in `(media_id, media_type)` für Music Assistant."""
    _, spotify_type, spotify_id = normalize_spotify_uri(uri).split(":")
    ma_type = _MA_TYPES.get(spotify_type, spotify_type)
    return f"spotify://{ma_type}/{spotify_id}", ma_type


@dataclass(frozen=True)
class Figure:
    """Eine Figur mit zugeordnetem Medium."""

    subentry_id: str
    name: str
    uid: str
    media_uri: str
    mode: str


class FigureLibrary:
    """Sucht Figuren anhand ihrer (normalisierten) UID."""

    def __init__(self, figures: Iterable[Figure] = ()) -> None:
        self._by_uid: dict[str, Figure] = {}
        self.replace(figures)

    def lookup(self, uid: str) -> Figure | None:
        """Figur zur UID finden, unabhängig von der Schreibweise."""
        key = normalize_uid(uid)
        return self._by_uid.get(key) if key else None

    def replace(self, figures: Iterable[Figure]) -> None:
        """Alle Figuren ersetzen."""
        self._by_uid = {normalize_uid(f.uid): f for f in figures}

    @staticmethod
    def figures_from_entry(entry: ConfigEntry) -> list[Figure]:
        """Alle Figuren-Subentries eines Config Entries lesen."""
        return [
            Figure(
                subentry_id=sub.subentry_id,
                name=sub.data.get("name", sub.title),
                uid=sub.data[CONF_UID],
                media_uri=sub.data[CONF_MEDIA_URI],
                mode=sub.data[CONF_MODE],
            )
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_FIGURE
        ]
