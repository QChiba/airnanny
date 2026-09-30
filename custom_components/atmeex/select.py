"""Select: air intake mode (damper position, plus supply air valve)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DAMPER_OPEN
from .entity import AtmeexEntity

# running modes: option index equals the u_damp_pos value
DAMPER_OPTIONS = ["Fresh air", "Mixed", "Recirculation"]
# fan off with the damper open, so outside air flows in passively (the app's "supply air valve")
SUPPLY_VALVE = "Supply air valve"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(AtmeexAirIntake(coordinator, dev_id) for dev_id in coordinator.data)


class AtmeexAirIntake(AtmeexEntity, SelectEntity):
    _attr_name = "Air intake"
    _attr_icon = "mdi:valve"
    _attr_options = [*DAMPER_OPTIONS, SUPPLY_VALVE]

    def __init__(self, coordinator, dev_id: int) -> None:
        super().__init__(coordinator, dev_id, "u_damp_pos")

    @property
    def current_option(self) -> str | None:
        damper = self.settings.get("u_damp_pos")
        if not self.settings.get("u_pwr_on") and damper == DAMPER_OPEN:
            return SUPPLY_VALVE
        return DAMPER_OPTIONS[damper] if isinstance(damper, int) and 0 <= damper < len(DAMPER_OPTIONS) else None

    async def async_select_option(self, option: str) -> None:
        if option == SUPPLY_VALVE:
            await self._set(u_pwr_on=False, u_damp_pos=DAMPER_OPEN)
        else:
            # choosing a running mode also starts the fan, otherwise "Fresh air" while off would be the valve mode
            await self._set(u_pwr_on=True, u_damp_pos=DAMPER_OPTIONS.index(option))
