"""Sliders: fan speed, heater temperature and humidifier stage."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_HEAT_TARGET, FAN_SPEEDS, HEATER_OFF, HUMIDIFIER_STAGES, temp_to_api
from .entity import AtmeexEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        entity
        for dev_id in coordinator.data
        for entity in (
            AtmeexFanSpeed(coordinator, dev_id),
            AtmeexHeaterTarget(coordinator, dev_id),
            AtmeexHumidifier(coordinator, dev_id),
        )
    )


class AtmeexFanSpeed(AtmeexEntity, NumberEntity):
    _attr_name = "Fan speed"
    _attr_icon = "mdi:fan"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 1
    _attr_native_max_value = FAN_SPEEDS
    _attr_native_step = 1

    def __init__(self, coordinator, dev_id: int) -> None:
        super().__init__(coordinator, dev_id, "fan_speed")

    @property
    def native_value(self) -> int | None:
        speed = self.settings.get("u_fan_speed")
        return None if speed is None else speed + 1

    async def async_set_native_value(self, value: float) -> None:
        await self._set(u_fan_speed=int(value) - 1)


class AtmeexHeaterTarget(AtmeexEntity, NumberEntity, RestoreEntity):
    """Heater target 10.0..30.0 °C; the Heater switch turns heating on and off.

    While the heater is off the cloud keeps no target, so the last one is remembered
    (and restored across restarts) and used when the heater is switched back on.
    """

    _attr_name = "Heater temperature"
    _attr_icon = "mdi:thermometer"
    _attr_mode = NumberMode.SLIDER
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 10.0
    _attr_native_max_value = 30.0
    _attr_native_step = 0.5

    def __init__(self, coordinator, dev_id: int) -> None:
        super().__init__(coordinator, dev_id, "heater")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.dev_id in self.coordinator.heat_target:
            return
        last = await self.async_get_last_state()
        try:
            value = float(last.state) if last else None
        except ValueError:
            value = None
        if value is not None and 10.0 <= value <= 30.0:
            self.coordinator.heat_target[self.dev_id] = value

    @property
    def native_value(self) -> float:
        return self.coordinator.heat_target.get(self.dev_id, DEFAULT_HEAT_TARGET)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.heat_target[self.dev_id] = value
        if self.settings.get("u_temp_room", HEATER_OFF) != HEATER_OFF:
            await self._set(u_temp_room=temp_to_api(value))
        else:
            self.async_write_ha_state()


class AtmeexHumidifier(AtmeexEntity, NumberEntity):
    """Humidifier stage 0..3, 0 = off."""

    _attr_name = "Humidifier"
    _attr_icon = "mdi:air-humidifier"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_max_value = HUMIDIFIER_STAGES
    _attr_native_step = 1

    def __init__(self, coordinator, dev_id: int) -> None:
        super().__init__(coordinator, dev_id, "humidifier")

    @property
    def native_value(self) -> int | None:
        return self.settings.get("u_hum_stg")

    async def async_set_native_value(self, value: float) -> None:
        await self._set(u_hum_stg=int(value))

