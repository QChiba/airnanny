"""Night mode window start/stop."""
from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AtmeexEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        entity
        for dev_id in coordinator.data
        for entity in (
            AtmeexNightTime(coordinator, dev_id, "u_night_start", "Night mode from"),
            AtmeexNightTime(coordinator, dev_id, "u_night_stop", "Night mode until"),
        )
    )


class AtmeexNightTime(AtmeexEntity, TimeEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, dev_id: int, field: str, name: str) -> None:
        super().__init__(coordinator, dev_id, field)
        self._field = field
        self._attr_name = name

    @property
    def native_value(self) -> time | None:
        v = self.settings.get(self._field)
        try:
            return time.fromisoformat(v) if v else None
        except ValueError:
            return None

    async def async_set_value(self, value: time) -> None:
        await self._set(**{self._field: value.strftime("%H:%M")})
