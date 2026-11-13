"""Gemeinsame Fixtures für die Tests."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from custom_components.home_tonie.box import BoxConfig, BoxController
from custom_components.home_tonie.const import MODE_RESTART
from custom_components.home_tonie.library import Figure, FigureLibrary

from .fakes import FakeLed, FakePlayer

BOBO = Figure("fig_bobo", "Bobo", "04A1B2C3", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", MODE_RESTART)
FEUERWEHR = Figure(
    "fig_feuerwehr", "Feuerwehr", "04B7C8D9", "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", MODE_RESTART
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Custom Integrations in allen Tests aktivieren."""
    yield


@dataclass
class Box:
    """Bündelt Controller und Fakes für Tests."""

    ctrl: BoxController
    player: FakePlayer
    led: FakeLed
    unknown_uids: list[str] = field(default_factory=list)


@pytest.fixture
async def box(hass):
    """BoxController mit FakePlayer (Lautstärke 0.8), FakeLed und zwei Figuren."""
    config = BoxConfig(
        subentry_id="box_anna",
        name="Anna",
        esphome_device_id="dev_anna",
        player_entity_id="media_player.kinderzimmer",
        ma_username="anna",
        max_volume=40,
        volume_step=3,
    )
    player = FakePlayer(volume=0.8)
    led = FakeLed()
    unknown: list[str] = []
    ctrl = BoxController(
        hass, config, FigureLibrary([BOBO, FEUERWEHR]), player, led, on_unknown_tag=unknown.append
    )
    yield Box(ctrl, player, led, unknown)
    ctrl.async_shutdown()
