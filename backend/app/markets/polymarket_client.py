"""Read-only Polymarket-style public data client.

This client is intentionally limited to public market-data requests. It does
not handle credentials, signing, order placement, or account state.
"""

import httpx

from app.config import settings


class PolymarketClient:
    def __init__(
        self,
        gamma_base_url: str = settings.POLYMARKET_GAMMA_BASE_URL,
        clob_base_url: str = settings.POLYMARKET_CLOB_BASE_URL,
    ) -> None:
        self.gamma_base_url = gamma_base_url.rstrip("/")
        self.clob_base_url = clob_base_url.rstrip("/")

    async def fetch_active_events(self) -> list[dict]:
        async with httpx.AsyncClient(base_url=self.gamma_base_url, timeout=20.0) as client:
            response = await client.get(
                "/events",
                params={"active": "true", "closed": "false", "limit": "200"},
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("events", [])

    async def fetch_market(self, market_id: str) -> dict:
        async with httpx.AsyncClient(base_url=self.gamma_base_url, timeout=20.0) as client:
            response = await client.get(f"/markets/{market_id}")
            response.raise_for_status()
            data = response.json()
            return data.get("market", data) if isinstance(data, dict) else {}

    async def fetch_market_prices(self, condition_id: str) -> dict:
        async with httpx.AsyncClient(base_url=self.clob_base_url, timeout=20.0) as client:
            response = await client.get(f"/prices/{condition_id}")
            response.raise_for_status()
            return response.json()
