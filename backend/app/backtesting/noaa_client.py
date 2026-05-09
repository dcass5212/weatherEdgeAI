"""NOAA/NCEI observed-weather client.

This client is intentionally credential-gated and read-only. It fetches daily
precipitation observations for outcome resolution, while tests can inject an
httpx transport so no live NOAA request is needed.
"""

from typing import Any

import httpx

from app.config import settings


class NoaaCdoClient:
    def __init__(
        self,
        base_url: str = settings.NOAA_CDO_BASE_URL,
        token: str | None = settings.NOAA_CDO_TOKEN,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.transport = transport

    async def fetch_daily_precipitation(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        if not self.token:
            raise ValueError("NOAA_CDO_TOKEN is required to resolve outcomes with noaa_cdo_daily")

        async with httpx.AsyncClient(base_url=self.base_url, transport=self.transport) as client:
            response = await client.get(
                "/data",
                headers={"token": self.token},
                params={
                    "datasetid": "GHCND",
                    "datatypeid": "PRCP",
                    "startdate": start_date,
                    "enddate": end_date,
                    "units": "metric",
                    "limit": 1000,
                    "extent": _extent(latitude, longitude),
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError("NOAA CDO response was not a JSON object")

        return {
            "source": "noaa_cdo_daily",
            "precipitation_unit": "mm",
            "request": {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "extent": _extent(latitude, longitude),
            },
            "results": payload.get("results", []),
            "provider_payload": payload,
        }


def _extent(latitude: float, longitude: float, radius_degrees: float = 0.25) -> str:
    min_latitude = round(latitude - radius_degrees, 4)
    min_longitude = round(longitude - radius_degrees, 4)
    max_latitude = round(latitude + radius_degrees, 4)
    max_longitude = round(longitude + radius_degrees, 4)
    return f"{min_latitude},{min_longitude},{max_latitude},{max_longitude}"
