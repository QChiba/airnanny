"""Switches: heater, auto mode and night mode."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_HEAT_TARGET, HEATER_OFF, temp_to_api
from .entity import AtmeexEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        entity
        for dev_id in coordinator.data
        for entity in (
            AtmeexHeaterSwitch(coordinator, dev_id),
            AtmeexModeSwitch(coordinator, dev_id, "u_auto", "AutoNanny", "mdi:fan-auto"),
            AtmeexModeSwitch(coordinator, dev_id, "u_night", "Night mode", "mdi:weather-night"),
        )
    )


class AtmeexModeSwitch(AtmeexEntity, SwitchEntity):
    """Both modes overwrite u_fan_speed and leave it low when switched off, so restore it."""

    def __init__(self, coordinator, dev_id: int, field: str, name: str, icon: str) -> None:
        super().__init__(coordinator, dev_id, field)
        self._field = field
        self._attr_name = name
        self._attr_icon = icon

    @property
    def is_on(self) -> bool | None:
        return self.settings.get(self._field)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(**{self._field: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        params: dict[str, Any] = {self._field: False}
        other = "u_night" if self._field == "u_auto" else "u_auto"
        speed = self.coordinator.manual_speed.get(self.dev_id)
        if speed is not None and not self.settings.get(other):
            params["u_fan_speed"] = speed
        await self._set(**params)


class AtmeexHeaterSwitch(AtmeexEntity, SwitchEntity):
    """Heater on/off; switching on uses the Heater temperature slider's value."""

    _attr_name = "Heater"
    _attr_icon = "mdi:radiator"

    def __init__(self, coordinator, dev_id: int) -> None:
        super().__init__(coordinator, dev_id, "heater_switch")

    @property
    def is_on(self) -> bool | None:
        t = self.settings.get("u_temp_room")
        return None if t is None else t != HEATER_OFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        target = self.coordinator.heat_target.get(self.dev_id, DEFAULT_HEAT_TARGET)
        await self._set(u_temp_room=temp_to_api(target))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(u_temp_room=HEATER_OFF)
