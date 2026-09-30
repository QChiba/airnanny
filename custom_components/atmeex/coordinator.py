"""Polling coordinator for Atmeex devices."""
from __future__ import annotations

import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AtmeexApi, AtmeexApiError, AtmeexAuthError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    HEATER_OFF,
    SCAN_INTERVAL,
    THROTTLE_GRACE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class AtmeexCoordinator(DataUpdateCoordinator[dict[int, dict]]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = AtmeexApi(
            async_get_clientsession(hass),
            entry.data[CONF_ACCESS_TOKEN],
            entry.data[CONF_REFRESH_TOKEN],
            self._save_tokens,
        )
        # fan speed chosen by the user outside auto/night mode; those modes overwrite u_fan_speed
        self.manual_speed: dict[int, int] = {}
        # last heater target in °C; the cloud forgets it when the heater is off (u_temp_room=-1000)
        self.heat_target: dict[int, float] = {}
        # damper position while running; powering off closes the damper (like the remote's power button)
        self.running_damper: dict[int, int] = {}
        self._throttled_since: dict[int, float | None] = {}

    def _save_tokens(self, access: str, refresh: str) -> None:
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_ACCESS_TOKEN: access, CONF_REFRESH_TOKEN: refresh},
        )

    async def _async_update_data(self) -> dict[int, dict]:
        try:
            devices = await self.api.get_devices()
        except AtmeexAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AtmeexApiError as err:
            raise UpdateFailed(str(err)) from err
        for dev_id, dev in devices.items():
            self._track(dev_id, dev)
        return devices

    def _track(self, dev_id: int, dev: dict) -> None:
        s = dev.get("settings") or {}
        c = dev.get("condition") or {}
        if not s.get("u_auto") and not s.get("u_night") and s.get("u_fan_speed") is not None:
            self.manual_speed[dev_id] = s["u_fan_speed"]
        if s.get("u_pwr_on") and s.get("u_damp_pos") is not None:
            self.running_damper[dev_id] = s["u_damp_pos"]
        if s.get("u_temp_room") not in (None, HEATER_OFF):
            self.heat_target[dev_id] = s["u_temp_room"] / 10
        throttled = (
            bool(c.get("pwr_on"))
            and c.get("fan_speed") is not None
            and s.get("u_fan_speed") is not None
            and c["fan_speed"] < s["u_fan_speed"]
        )
        if not throttled:
            self._throttled_since[dev_id] = None
        elif self._throttled_since.get(dev_id) is None:
            self._throttled_since[dev_id] = time.monotonic()

    def is_throttled(self, dev_id: int) -> bool:
        since = self._throttled_since.get(dev_id)
        return since is not None and time.monotonic() - since >= THROTTLE_GRACE_SECONDS

    async def async_set_params(self, dev_id: int, **params) -> None:
        try:
            resp = await self.api.set_params(dev_id, params)
        except AtmeexAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("Atmeex session expired, please re-authenticate") from err
        except AtmeexApiError as err:
            raise HomeAssistantError(f"Atmeex cloud error: {err}") from err
        dev = self.data[dev_id]
        settings = resp.get("settings") if isinstance(resp, dict) else None
        dev = {**dev, "settings": {**dev.get("settings", {}), **(settings or params)}}
        self._track(dev_id, dev)
        self.async_set_updated_data({**self.data, dev_id: dev})
