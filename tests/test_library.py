"""Tests für Figurenbibliothek und Normalisierung."""

import pytest
from homeassistant.config_entries import ConfigSubentryData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_tonie.const import (
    CONF_MEDIA_URI,
    CONF_MODE,
    CONF_UID,
    DOMAIN,
    SUBENTRY_BOX,
    SUBENTRY_FIGURE,
)
from custom_components.home_tonie.library import (
    Figure,
    FigureLibrary,
    InvalidMediaUri,
    normalize_spotify_uri,
    normalize_uid,
    to_ma_media,
)


@pytest.mark.parametrize("raw", ["04-a1-b2-c3", "04:A1:B2:C3", "04 a1 b2 c3", " 04A1B2C3 ", "04_a1.b2,c3"])
def test_normalize_uid(raw):
    assert normalize_uid(raw) == "04A1B2C3"


@pytest.mark.parametrize("raw,expected", [
    ("https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy?si=abc", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"),
    ("https://open.spotify.com/intl-de/playlist/37i9dQZF1DXcBWIGoYBM5M", "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"),
    ("spotify:track:11dFghVXANMlKmJXsNCbNl", "spotify:track:11dFghVXANMlKmJXsNCbNl"),
    ("https://open.spotify.com/audiobook/7iHfbu1YPACw6oZPAFJtqe", "spotify:audiobook:7iHfbu1YPACw6oZPAFJtqe"),
    ("https://open.spotify.com/show/2MAi0BvDc6GTFvKFPXnkCL", "spotify:show:2MAi0BvDc6GTFvKFPXnkCL"),
    ("https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy/", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"),
    ("https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy/?si=x", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"),
    ("HTTPS://Open.Spotify.com/Album/4aawyAB9vmqN3uQ7FjRGTy", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"),
    ("Spotify:ALBUM:4aawyAB9vmqN3uQ7FjRGTy", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"),
])
def test_normalize_spotify_uri(raw, expected):
    assert normalize_spotify_uri(raw) == expected


@pytest.mark.parametrize("raw", ["", "https://example.com/album/x", "spotify:album:", "https://open.spotify.com/user/abc", "spotify:album:zu-kurz"])
def test_normalize_spotify_uri_invalid(raw):
    with pytest.raises(InvalidMediaUri):
        normalize_spotify_uri(raw)


@pytest.mark.parametrize("uri,expected", [
    ("spotify:album:4aawyAB9vmqN3uQ7FjRGTy", ("spotify://album/4aawyAB9vmqN3uQ7FjRGTy", "album")),
    ("spotify:show:2MAi0BvDc6GTFvKFPXnkCL", ("spotify://podcast/2MAi0BvDc6GTFvKFPXnkCL", "podcast")),
    ("spotify:episode:11dFghVXANMlKmJXsNCbNl", ("spotify://podcast_episode/11dFghVXANMlKmJXsNCbNl", "podcast_episode")),
])
def test_to_ma_media(uri, expected):
    assert to_ma_media(uri) == expected


def test_lookup_matches_any_uid_spelling():
    lib = FigureLibrary([Figure("s1", "Bobo", "04A1B2C3", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", "restart")])
    assert lib.lookup("04-a1-b2-c3").name == "Bobo"
    assert lib.lookup("FFFF") is None


@pytest.mark.parametrize("uid", ["", " ", "--", "xyz"])
def test_lookup_empty_uid_returns_none(uid):
    lib = FigureLibrary([Figure("s1", "Leer", "", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", "restart")])
    assert lib.lookup(uid) is None


def test_replace_swaps_figures():
    lib = FigureLibrary([Figure("s1", "Bobo", "04A1", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", "restart")])
    lib.replace([Figure("s2", "Feuerwehr", "04B7", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", "restart")])
    assert lib.lookup("04A1") is None
    assert lib.lookup("04b7").name == "Feuerwehr"


def test_figures_from_entry_filters_figure_subentries():
    entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_FIGURE,
                title="Bobo",
                unique_id=None,
                subentry_id="fig1",
                data={
                    "name": "Bobo",
                    CONF_UID: "04A1B2C3",
                    CONF_MEDIA_URI: "spotify:album:4aawyAB9vmqN3uQ7FjRGTy",
                    CONF_MODE: "restart",
                },
            ),
            ConfigSubentryData(
                subentry_type=SUBENTRY_BOX,
                title="Küche",
                unique_id=None,
                subentry_id="box1",
                data={"name": "Küche"},
            ),
        ],
    )
    assert FigureLibrary.figures_from_entry(entry) == [
        Figure("fig1", "Bobo", "04A1B2C3", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", "restart")
    ]


def test_figures_from_entry_reads_color():
    def fig(sub_id: str, uid: str, **extra) -> ConfigSubentryData:
        return ConfigSubentryData(
            subentry_type=SUBENTRY_FIGURE,
            title=sub_id,
            unique_id=None,
            subentry_id=sub_id,
            data={
                "name": sub_id,
                CONF_UID: uid,
                CONF_MEDIA_URI: "spotify:album:4aawyAB9vmqN3uQ7FjRGTy",
                CONF_MODE: "restart",
                **extra,
            },
        )

    entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[fig("rot", "04AA", color=[255, 0, 0]), fig("ohne", "04BB")],
    )
    figures = {f.subentry_id: f for f in FigureLibrary.figures_from_entry(entry)}
    assert figures["rot"].color == (255, 0, 0)
    assert figures["ohne"].color is None
