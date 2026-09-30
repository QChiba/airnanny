"""Config flow: sign in with email+password or phone+SMS code."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import AtmeexApi, AtmeexApiError, AtmeexAuthError
from .const import CONF_ACCESS_TOKEN, CONF_LOGIN, CONF_REFRESH_TOKEN, DOMAIN

CONF_PHONE = "phone"
CONF_CODE = "code"


class AtmeexConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._phone = ""

    def _api(self) -> AtmeexApi:
        return AtmeexApi(async_get_clientsession(self.hass))

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["email", "phone"])

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_user()

    async def async_step_email(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api = self._api()
            try:
                await api.signin_email(user_input[CONF_EMAIL].strip(), user_input[CONF_PASSWORD])
            except AtmeexAuthError:
                errors["base"] = "invalid_auth"
            except AtmeexApiError:
                errors["base"] = "cannot_connect"
            else:
                return await self._finish(user_input[CONF_EMAIL].strip(), api)
        return self.async_show_form(
            step_id="email",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
                    vol.Required(CONF_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                }
            ),
            errors=errors,
        )

    async def async_step_phone(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._phone = user_input[CONF_PHONE].strip()
            try:
                await self._api().request_sms(self._phone)
            except AtmeexAuthError:
                errors["base"] = "invalid_phone"
            except AtmeexApiError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_sms()
        return self.async_show_form(
            step_id="phone",
            data_schema=vol.Schema(
                {vol.Required(CONF_PHONE): TextSelector(TextSelectorConfig(type=TextSelectorType.TEL))}
            ),
            errors=errors,
        )

    async def async_step_sms(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api = self._api()
            try:
                await api.signin_phone(self._phone, user_input[CONF_CODE].strip())
            except AtmeexAuthError:
                errors["base"] = "invalid_auth"
            except AtmeexApiError:
                errors["base"] = "cannot_connect"
            else:
                return await self._finish(self._phone, api)
        return self.async_show_form(
            step_id="sms",
            data_schema=vol.Schema({vol.Required(CONF_CODE): str}),
            description_placeholders={"phone": self._phone},
            errors=errors,
        )

    async def _finish(self, login: str, api: AtmeexApi) -> ConfigFlowResult:
        await self.async_set_unique_id(login.lower())
        data = {CONF_LOGIN: login, CONF_ACCESS_TOKEN: api.access_token, CONF_REFRESH_TOKEN: api.refresh_token}
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=login, data=data)
