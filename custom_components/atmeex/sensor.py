"""Sensors from the device's reported condition."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfRatio, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AtmeexEntity


def _tenths(key: str) -> Callable[[dict], float | None]:
    return lambda c: None if c.get(key) is None else c[key] / 10


def _yes_no(key: str) -> Callable[[dict], str | None]:
    return lambda c: None if c.get(key) is None else ("Yes" if c[key] else "No")


def _actual_speed(c: dict) -> int | None:
    if c.get("fan_speed") is None:
        return None
    return c["fan_speed"] + 1 if c.get("pwr_on") else 0


@dataclass(frozen=True, kw_only=True)
class AtmeexSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]


SENSORS = (
    AtmeexSensorDescription(
        key="co2",
        name="CO2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get("co2_ppm"),
    ),
    AtmeexSensorDescription(
        key="room_temperature",
        name="Room temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_tenths("temp_room"),
    ),
    AtmeexSensorDescription(
        key="inlet_temperature",
        name="Inlet air temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_tenths("temp_in"),
    ),
    AtmeexSensorDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get("hum_room"),
    ),
    AtmeexSensorDescription(
        key="actual_fan_speed",
        name="Actual fan speed",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_actual_speed,
    ),
    AtmeexSensorDescription(
        key="no_water",
        name="Water tank empty",
        icon="mdi:water-alert",
        device_class=SensorDeviceClass.ENUM,
        options=["Yes", "No"],
        value_fn=_yes_no("no_water"),
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(AtmeexSensor(coordinator, dev_id, desc) for dev_id in coordinator.data for desc in SENSORS)


class AtmeexSensor(AtmeexEntity, SensorEntity):
    entity_description: AtmeexSensorDescription

    def __init__(self, coordinator, dev_id: int, description: AtmeexSensorDescription) -> None:
        super().__init__(coordinator, dev_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.condition)
