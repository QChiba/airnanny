"""Fan entity: breezer power on/off. Speed is the separate Fan speed slider (1..7).

Like the remote's power button, switching off also closes the damper so no outside air
leaks in; switching on reopens it to the position it had before.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DAMPER_CLOSED, DAMPER_OPEN
from .entity import AtmeexEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(AtmeexFan(coordinator, dev_id) for dev_id in coordinator.data)


class AtmeexFan(AtmeexEntity, FanEntity):
    _attr_name = "Fan"
    _attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

    def __init__(self, coordinator, dev_id: int) -> None:
        super().__init__(coordinator, dev_id, "fan")

    @property
    def is_on(self) -> bool | None:
        return self.settings.get("u_pwr_on")

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        damper = self.coordinator.running_damper.get(self.dev_id, DAMPER_OPEN)
        await self._set(u_pwr_on=True, u_damp_pos=damper)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(u_pwr_on=False, u_damp_pos=DAMPER_CLOSED)
