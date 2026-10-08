"""Minimal async client for the Atmeex cloud API."""
from __future__ import annotations

import asyncio
import base64
import json
import time
from collections.abc import Callable
from typing import Any

import aiohttp

from .const import API_BASE, TOKEN_REFRESH_MARGIN_SECONDS

HEADERS = {"accept": "application/json", "user-agent": "okhttp/3.14.9"}


class AtmeexApiError(Exception):
    """Cloud unreachable or returned an error."""


class AtmeexAuthError(AtmeexApiError):
    """Credentials or session rejected."""


def _token_expiry(token: str) -> float | None:
    """The access token is a JWT; return its exp claim, or None if it can't be read."""
    try:
        payload = token.split(".")[1]
        return float(json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["exp"])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


class AtmeexApi:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str = "",
        refresh_token: str = "",
        on_tokens: Callable[[str, str], None] | None = None,
    ) -> None:
        self._session = session
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._on_tokens = on_tokens
        # refresh tokens are single-use, so concurrent refreshes would invalidate each other
        self._refresh_lock = asyncio.Lock()

    async def _raw(self, method: str, path: str, body: Any = None, token: str | None = None) -> tuple[int, Any]:
        headers = dict(HEADERS)
        if token:
            headers["authorization"] = f"Bearer {token}"
        try:
            async with self._session.request(
                method, API_BASE + path, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except ValueError:
                    data = await resp.text()
                return resp.status, data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AtmeexApiError(f"{method} {path}: {err}") from err

    def _set_tokens(self, data: dict) -> None:
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        if self._on_tokens:
            self._on_tokens(self.access_token, self.refresh_token)

    async def _signin(self, body: dict) -> None:
        status, data = await self._raw("POST", "/auth/signin", body)
        # only a 4xx means the credentials or refresh token were rejected; anything else is worth retrying
        if status >= 500 or status == 429:
            raise AtmeexApiError(f"sign-in failed: HTTP {status}")
        if status >= 400:
            raise AtmeexAuthError(f"sign-in rejected: HTTP {status}")
        if not isinstance(data, dict) or "access_token" not in data:
            raise AtmeexApiError(f"sign-in returned no token: HTTP {status}")
        self._set_tokens(data)

    async def _refresh(self, stale_token: str) -> None:
        """Swap the refresh token for new tokens, unless another call already replaced stale_token."""
        async with self._refresh_lock:
            if self.access_token != stale_token:
                return
            await self._signin({"grant_type": "refresh_token", "refresh_token": self.refresh_token})

    def _expires_soon(self) -> bool:
        exp = _token_expiry(self.access_token)
        return exp is not None and exp - time.time() < TOKEN_REFRESH_MARGIN_SECONDS

    async def _call(self, method: str, path: str, body: Any = None) -> Any:
        if self._expires_soon():
            try:
                await self._refresh(self.access_token)
            except AtmeexAuthError:
                raise
            except AtmeexApiError:
                pass  # the token may still be good for a few minutes; a 401 below retries the refresh
        token = self.access_token
        status, data = await self._raw(method, path, body, token)
        if status == 401:
            await self._refresh(token)
            status, data = await self._raw(method, path, body, self.access_token)
        if status == 401:
            raise AtmeexAuthError("session rejected after token refresh")
        if status >= 400:
            raise AtmeexApiError(f"{method} {path}: HTTP {status} {data}")
        return data

    async def signin_email(self, email: str, password: str) -> None:
        await self._signin({"grant_type": "basic", "email": email, "password": password})

    async def request_sms(self, phone: str) -> None:
        status, data = await self._raw("POST", "/auth/signup", {"grant_type": "phone_code", "phone": phone})
        if status >= 400:
            raise AtmeexAuthError(f"SMS request rejected: HTTP {status} {data}")

    async def signin_phone(self, phone: str, code: str) -> None:
        await self._signin({"grant_type": "phone_code", "phone": phone, "phone_code": code})

    async def get_devices(self) -> dict[int, dict]:
        """Return devices by id. The list omits live condition, so each device is fetched too."""
        devices = {}
        for item in await self._call("GET", "/devices"):
            detail = await self._call("GET", f"/devices/{item['id']}")
            devices[item["id"]] = {**item, **detail}
        return devices

    async def set_params(self, device_id: int, params: dict) -> dict:
        """Write settings; the response is the updated device."""
        return await self._call("PUT", f"/devices/{device_id}/params", params)
