"""Reparatur-Ablauf: Box-Firmware über die ESPHome-Update-Entität aktualisieren."""

from __future__ import annotations

from typing import cast

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


class FirmwareUpdateFlow(RepairsFlow):
    """Bestätigung, dann Update der Box starten."""

    def __init__(self, issue_id: str, device_id: str) -> None:
        self._issue_id = issue_id
        self._device_id = device_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        if user_input is None:
            # Ein Hinweis mit Knopf hat keinen eigenen Beschreibungstext (hassfest);
            # Box, Versionen und Gerät stehen deshalb im Bestätigungsschritt.
            issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self._issue_id)
            return self.async_show_form(
                step_id="confirm",
                description_placeholders=dict(issue.translation_placeholders or {})
                if issue
                else None,
            )
        entity_id = self._update_entity_id()
        if entity_id is None:
            return self.async_abort(reason="no_update")
        # Nicht blockierend: das Update dauert Minuten, der Dialog soll sofort schliessen.
        await self.hass.services.async_call(
            "update", "install", {"entity_id": entity_id}, blocking=False
        )
        # Abbruch statt Eintrag: sonst löscht HA den Hinweis sofort, auch wenn das Update
        # scheitert. Er verschwindet über die sw_version-Prüfung, sobald die neue Firmware läuft.
        return self.async_abort(reason="update_started")

    def _update_entity_id(self) -> str | None:
        """Eigene Update-Entität der Box mit verfügbarem Update (bevorzugt `on`).

        Die ESPHome-Dashboard-Entität hat die reine MAC als unique_id (ohne "-") und
        gehört nicht zur Firmware der Box; sie wird übersprungen. Native unique_ids sind
        v1/v2 "{mac}-{typ}-{name}" oder v3 "{mac}/{geraet}/{typ}/{name}", enthalten also
        "-" oder "/" (die MAC allein hat beides nicht).
        """
        candidates = [
            entry.entity_id
            for entry in er.async_entries_for_device(er.async_get(self.hass), self._device_id)
            if entry.domain == "update"
            and entry.platform == "esphome"
            and ("-" in entry.unique_id or "/" in entry.unique_id)
        ]
        for entity_id in candidates:
            state = self.hass.states.get(entity_id)
            if state is not None and state.state == STATE_ON:
                return entity_id
        return None


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Fix-Flow für `firmware_outdated_*`."""
    return FirmwareUpdateFlow(issue_id, cast(str, (data or {})["device_id"]))
