"""Select: air intake (damper)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AtmeexEntity

# option index equals the API value
DAMPER_OPTIONS = ["Fresh air", "Mixed", "Recirculation"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        AtmeexSelect(coordinator, dev_id, "u_damp_pos", "Air intake", "mdi:valve", DAMPER_OPTIONS)
        for dev_id in coordinator.data
    )


class AtmeexSelect(AtmeexEntity, SelectEntity):
    def __init__(self, coordinator, dev_id: int, field: str, name: str, icon: str, options: list[str]) -> None:
        super().__init__(coordinator, dev_id, field)
        self._field = field
        self._attr_name = name
        self._attr_icon = icon
        self._attr_options = options

    @property
    def current_option(self) -> str | None:
        v = self.settings.get(self._field)
        return self.options[v] if isinstance(v, int) and 0 <= v < len(self.options) else None

    async def async_select_option(self, option: str) -> None:
        await self._set(**{self._field: self.options.index(option)})
