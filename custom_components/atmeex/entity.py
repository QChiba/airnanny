"""Base entity for Atmeex devices."""
from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AtmeexCoordinator


class AtmeexEntity(CoordinatorEntity[AtmeexCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AtmeexCoordinator, dev_id: int, key: str) -> None:
        super().__init__(coordinator)
        self.dev_id = dev_id
        self._attr_unique_id = f"{dev_id}_{key}"
        dev = coordinator.data[dev_id]
        mac = (dev.get("mac") or "")[:17].lower()  # API appends an extra ":0"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(dev_id))},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
            name=dev.get("name"),
            manufacturer="Atmeex",
            model=f"AirNanny {dev.get('model')}",
            sw_version=dev.get("fw_ver"),
        )

    @property
    def device(self) -> dict:
        return self.coordinator.data.get(self.dev_id) or {}

    @property
    def settings(self) -> dict:
        return self.device.get("settings") or {}

    @property
    def condition(self) -> dict:
        return self.device.get("condition") or {}

    @property
    def available(self) -> bool:
        return super().available and self.dev_id in self.coordinator.data and self.device.get("online") is not False

    async def _set(self, **params) -> None:
        await self.coordinator.async_set_params(self.dev_id, **params)
