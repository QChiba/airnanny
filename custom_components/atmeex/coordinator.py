"""Polling coordinator for Atmeex devices."""
from __future__ import annotations

import logging
import time
from datetime import datetime

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

# the device applies u_time_zone from each command it gets and falls back to UTC when a
# command lacks it; resend at most this often when its clock is found on the wrong zone
TZ_RESYNC_SECONDS = 600
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _clock_offset_hours(condition: dict) -> int | None:
    """Device clock offset from UTC: its local "time" vs. the cloud's UTC "created_at"."""
    try:
        device = datetime.strptime(condition["time"], _TIME_FORMAT)
        received = datetime.strptime(condition["created_at"], _TIME_FORMAT)
    except (KeyError, TypeError, ValueError):
        return None
    return round((device - received).total_seconds() / 3600)


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
        self._tz_resynced: dict[int, float] = {}

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
            await self._resync_time_zone(dev_id, dev)
        return devices

    async def _resync_time_zone(self, dev_id: int, dev: dict) -> None:
        """Commands from the app (or a reboot) put the device clock back on UTC; restore it."""
        tz = (dev.get("settings") or {}).get("u_time_zone")
        offset = _clock_offset_hours(dev.get("condition") or {})
        if tz is None or offset is None or offset == tz or dev.get("online") is False:
            return
        if time.monotonic() - self._tz_resynced.get(dev_id, -TZ_RESYNC_SECONDS) < TZ_RESYNC_SECONDS:
            return
        self._tz_resynced[dev_id] = time.monotonic()
        _LOGGER.info("%s clock is on UTC%+d instead of UTC%+d, resending time zone", dev.get("name"), offset, tz)
        try:
            await self.api.set_params(dev_id, {"u_time_zone": tz})
        except AtmeexApiError as err:
            _LOGGER.warning("Could not resend time zone to %s: %s", dev.get("name"), err)

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
        # without it the device resets its clock to UTC, shifting the night mode window
        tz = (self.data.get(dev_id, {}).get("settings") or {}).get("u_time_zone")
        if tz is not None:
            params.setdefault("u_time_zone", tz)
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
