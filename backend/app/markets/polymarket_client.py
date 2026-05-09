"""Read-only Polymarket-style public data client.

This client is intentionally limited to public market-data requests. It does
not handle credentials, signing, order placement, or account state. Its error
type carries retry and rate-limit context so API routes can persist useful
source diagnostics without hiding public-provider instability.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class PublicMarketDataError(httpx.HTTPError):
    endpoint: str
    reason: str
    attempts: int
    status_code: int | None = None
    retryable: bool = False

    def __post_init__(self) -> None:
        status = f" status={self.status_code}" if self.status_code is not None else ""
        super().__init__(f"{self.reason} after {self.attempts} attempt(s) at {self.endpoint}{status}")

    def to_diagnostics(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "reason": self.reason,
            "attempts": self.attempts,
            "status_code": self.status_code,
            "retryable": self.retryable,
        }


class PolymarketClient:
    def __init__(
        self,
        gamma_base_url: str = settings.POLYMARKET_GAMMA_BASE_URL,
        clob_base_url: str = settings.POLYMARKET_CLOB_BASE_URL,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.gamma_base_url = gamma_base_url.rstrip("/")
        self.clob_base_url = clob_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.transport = transport

    async def _get_json(self, base_url: str, endpoint: str, params: dict[str, str] | None = None) -> Any:
        attempts = self.max_retries + 1
        last_network_error: httpx.HTTPError | None = None
        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            for attempt in range(1, attempts + 1):
                try:
                    response = await client.get(endpoint, params=params)
                except httpx.HTTPError as exc:
                    last_network_error = exc
                    if attempt < attempts:
                        continue
                    raise PublicMarketDataError(
                        endpoint=endpoint,
                        reason="network_error",
                        attempts=attempt,
                        retryable=True,
                    ) from exc

                if response.status_code in RETRYABLE_STATUS_CODES and attempt < attempts:
                    continue
                if response.status_code >= 400:
                    reason = "rate_limited" if response.status_code == 429 else "http_status_error"
                    raise PublicMarketDataError(
                        endpoint=endpoint,
                        reason=reason,
                        attempts=attempt,
                        status_code=response.status_code,
                        retryable=response.status_code in RETRYABLE_STATUS_CODES,
                    )

                try:
                    return response.json()
                except ValueError as exc:
                    raise PublicMarketDataError(
                        endpoint=endpoint,
                        reason="malformed_json",
                        attempts=attempt,
                        status_code=response.status_code,
                        retryable=False,
                    ) from exc

        raise PublicMarketDataError(
            endpoint=endpoint,
            reason="network_error" if last_network_error is not None else "request_failed",
            attempts=attempts,
            retryable=True,
        )

    async def fetch_active_events(self) -> list[dict]:
        data = await self._get_json(
            self.gamma_base_url,
            "/events",
            params={"active": "true", "closed": "false", "limit": "200"},
        )
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            events = data.get("events", [])
            return [item for item in events if isinstance(item, dict)] if isinstance(events, list) else []
        raise PublicMarketDataError(endpoint="/events", reason="malformed_payload", attempts=1, retryable=False)

    async def fetch_market(self, market_id: str) -> dict:
        endpoint = f"/markets/{market_id}"
        data = await self._get_json(self.gamma_base_url, endpoint)
        if isinstance(data, dict):
            market = data.get("market", data)
            return market if isinstance(market, dict) else {}
        raise PublicMarketDataError(endpoint=endpoint, reason="malformed_payload", attempts=1, retryable=False)

    async def fetch_market_prices(self, condition_id: str) -> dict:
        endpoint = f"/prices/{condition_id}"
        data = await self._get_json(self.clob_base_url, endpoint)
        if isinstance(data, dict):
            return data
        raise PublicMarketDataError(endpoint=endpoint, reason="malformed_payload", attempts=1, retryable=False)
