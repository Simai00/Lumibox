"""Reparatur-Ablauf: Box-Firmware über die ESPHome-Update-Entität aktualisieren."""

from __future__ import annotations

from typing import cast

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


class FirmwareUpdateFlow(RepairsFlow):
    """Bestätigung, dann Update der Box starten."""

    def __init__(self, device_id: str) -> None:
        self._device_id = device_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="confirm")
        entity_id = self._update_entity_id()
        if entity_id is None:
            return self.async_abort(reason="no_update")
        # Nicht blockierend: das Update dauert Minuten, der Dialog soll sofort schliessen.
        await self.hass.services.async_call(
            "update", "install", {"entity_id": entity_id}, blocking=False
        )
        return self.async_create_entry(data={})

    def _update_entity_id(self) -> str | None:
        """Update-Entität der Box, falls ein Update bereitsteht."""
        for entry in er.async_entries_for_device(er.async_get(self.hass), self._device_id):
            if entry.domain == "update" and entry.platform == "esphome":
                state = self.hass.states.get(entry.entity_id)
                if state is None or state.state != STATE_ON:
                    return None
                return entry.entity_id
        return None


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Fix-Flow für `firmware_outdated_*`."""
    return FirmwareUpdateFlow(cast(str, (data or {})["device_id"]))
