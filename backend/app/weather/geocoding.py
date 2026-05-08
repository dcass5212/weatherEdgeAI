"""Geocoding for parsed weather markets.

Forecast APIs need latitude and longitude, but tests and local demos should not
depend on a live geocoding provider. This module keeps fixture geocoding as the
default and provides an optional Open-Meteo provider behind the same adapter.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


@dataclass(frozen=True)
class GeocodedLocation:
    name: str
    latitude: float
    longitude: float
    source: str = "fixture"


FIXTURE_LOCATIONS = {
    "chicago": GeocodedLocation(name="Chicago", latitude=41.8781, longitude=-87.6298),
    "new york": GeocodedLocation(name="New York City", latitude=40.7128, longitude=-74.0060),
    "new york city": GeocodedLocation(name="New York City", latitude=40.7128, longitude=-74.0060),
    "nyc": GeocodedLocation(name="New York City", latitude=40.7128, longitude=-74.0060),
}


class FixtureGeocoder:
    """Offline geocoder used by local development and tests."""

    def geocode(self, location_name: str) -> GeocodedLocation | None:
        normalized = location_name.strip().lower()
        return FIXTURE_LOCATIONS.get(normalized)


class OpenMeteoGeocodingClient:
    """Read-only public geocoding client for broader location coverage."""

    def __init__(self, base_url: str = settings.OPEN_METEO_GEOCODING_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def search(self, location_name: str, count: int = 1) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get(
                "/search",
                params={"name": location_name, "count": count, "language": "en", "format": "json"},
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}


class OpenMeteoGeocoder:
    """External geocoder used when GEOCODING_PROVIDER opts in."""

    def __init__(self, client: OpenMeteoGeocodingClient | None = None) -> None:
        self.client = client or OpenMeteoGeocodingClient()

    async def geocode(self, location_name: str) -> GeocodedLocation | None:
        raw = await self.client.search(location_name)
        results = raw.get("results")
        if not isinstance(results, list) or not results:
            return None

        first = results[0]
        if not isinstance(first, dict):
            return None

        latitude = _as_float(first.get("latitude"))
        longitude = _as_float(first.get("longitude"))
        name = first.get("name")
        if latitude is None or longitude is None or not isinstance(name, str) or not name.strip():
            return None

        admin1 = first.get("admin1")
        country = first.get("country")
        display_parts = [name.strip()]
        for value in (admin1, country):
            if isinstance(value, str) and value.strip() and value.strip() not in display_parts:
                display_parts.append(value.strip())

        return GeocodedLocation(
            name=", ".join(display_parts),
            latitude=latitude,
            longitude=longitude,
            source="open_meteo_geocoding",
        )


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_location(location_name: str, geocoder: FixtureGeocoder | None = None) -> GeocodedLocation | None:
    resolver = geocoder or FixtureGeocoder()
    return resolver.geocode(location_name)


async def resolve_location_for_market(
    location_name: str,
    provider: str | None = None,
    fixture_geocoder: FixtureGeocoder | None = None,
    external_geocoder: OpenMeteoGeocoder | None = None,
) -> GeocodedLocation | None:
    fixture_location = resolve_location(location_name, geocoder=fixture_geocoder)
    if fixture_location is not None:
        return fixture_location

    selected_provider = (provider or settings.GEOCODING_PROVIDER).strip().lower()
    if selected_provider not in {"open_meteo", "fixture_open_meteo"}:
        return None

    return await (external_geocoder or OpenMeteoGeocoder()).geocode(location_name)
