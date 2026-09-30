"""Binary sensors: fan throttling, connectivity."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
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
            AtmeexThrottled(coordinator, dev_id),
            AtmeexOnline(coordinator, dev_id),
        )
    )


class AtmeexThrottled(AtmeexEntity, BinarySensorEntity):
    """On when the device runs the fan slower than set, on its own, for over a minute."""

    _attr_name = "Fan throttled"
    _attr_icon = "mdi:fan-alert"

    def __init__(self, coordinator, dev_id: int) -> None:
        super().__init__(coordinator, dev_id, "throttled")

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_throttled(self.dev_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s, c = self.settings, self.condition
        return {
            "set_fan_speed": None if s.get("u_fan_speed") is None else s["u_fan_speed"] + 1,
            "actual_fan_speed": None if c.get("fan_speed") is None else c["fan_speed"] + 1,
            "inlet_temperature": None if c.get("temp_in") is None else c["temp_in"] / 10,
        }


class AtmeexOnline(AtmeexEntity, BinarySensorEntity):
    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, dev_id: int) -> None:
        super().__init__(coordinator, dev_id, "online")

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.dev_id in self.coordinator.data

    @property
    def is_on(self) -> bool:
        return self.device.get("online") is not False
