"""Thin async HTTP client wrapper around the Azure DevOps REST API."""
from __future__ import annotations

import asyncio
import base64
from typing import Any

import httpx

from src.config import AZURE_BASE_URL, MAX_RETRIES


class AzureAPIError(Exception):
    """Raised for non-retryable Azure DevOps API failures."""


class AzureClient:
    """Minimal async client. One instance per run; close when done."""

    API_VERSION = "7.1"

    def __init__(self, org: str, pat: str, *, timeout: float = 30.0) -> None:
        self.org = org
        self._base = f"{AZURE_BASE_URL}/{org}"
        token = base64.b64encode(f":{pat}".encode()).decode()
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
        )

    async def __aenter__(self) -> "AzureClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, url: str, *, params: dict | None = None, json: dict | None = None
    ) -> dict[str, Any]:
        params = {**(params or {}), "api-version": self.API_VERSION}
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = await self._client.request(method, url, params=params, json=json)
            except httpx.TimeoutException:
                if attempt > 2:
                    raise AzureAPIError(f"Network timeout calling {url}") from None
                continue

            if resp.status_code == 429:
                if attempt > MAX_RETRIES:
                    raise AzureAPIError("Rate limit exceeded after retries")
                retry_after = float(resp.headers.get("Retry-After", 2 ** attempt))
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code == 401:
                raise AzureAPIError("401 Unauthorized — PAT is invalid or expired")
            if resp.status_code == 404:
                raise AzureAPIError(f"404 Not found — {url}")
            if resp.status_code >= 400:
                raise AzureAPIError(f"{resp.status_code} error calling {url}: {resp.text[:200]}")
            return resp.json() if resp.content else {}

    async def get(self, path: str, **kw: Any) -> dict[str, Any]:
        return await self._request("GET", f"{self._base}/{path.lstrip('/')}", **kw)

    async def project_get(self, path: str, project: str, **kw: Any) -> dict[str, Any]:
        return await self._request(
            "GET", f"{self._base}/{project}/{path.lstrip('/')}", **kw
        )

    async def post(self, path: str, *, project: str | None = None, **kw: Any) -> dict[str, Any]:
        base = f"{self._base}/{project}" if project else self._base
        return await self._request("POST", f"{base}/{path.lstrip('/')}", **kw)
