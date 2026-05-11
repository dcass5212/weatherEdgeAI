import pytest

from app.weather.geocoding import (
    FixtureGeocoder,
    GeocodedLocation,
    OpenMeteoGeocoder,
    resolve_location,
    resolve_location_for_market,
)


def test_fixture_geocoder_resolves_known_city() -> None:
    location = resolve_location("NYC")

    assert location is not None
    assert location.name == "New York City"
    assert location.latitude == 40.7128
    assert location.longitude == -74.006
    assert location.source == "fixture"


def test_fixture_geocoder_resolves_public_precipitation_demo_cities() -> None:
    london = resolve_location("London")
    hong_kong = resolve_location("Hong Kong")

    assert london is not None
    assert london.latitude == 51.5072
    assert hong_kong is not None
    assert hong_kong.longitude == 114.1694


def test_fixture_geocoder_returns_none_for_unknown_location() -> None:
    location = FixtureGeocoder().geocode("Springfield")

    assert location is None


@pytest.mark.anyio
async def test_resolve_location_for_market_prefers_fixture_before_external() -> None:
    class FailingExternalGeocoder:
        async def geocode(self, location_name: str):
            raise AssertionError("fixture matches should not call external geocoding")

    location = await resolve_location_for_market(
        "Chicago",
        provider="open_meteo",
        external_geocoder=FailingExternalGeocoder(),
    )

    assert location is not None
    assert location.name == "Chicago"
    assert location.source == "fixture"


@pytest.mark.anyio
async def test_open_meteo_geocoder_normalizes_first_result() -> None:
    class FakeClient:
        async def search(self, location_name: str, count: int = 1) -> dict:
            assert location_name == "Boston"
            return {
                "results": [
                    {
                        "name": "Boston",
                        "admin1": "Massachusetts",
                        "country": "United States",
                        "latitude": "42.3584",
                        "longitude": "-71.0598",
                    }
                ]
            }

    location = await OpenMeteoGeocoder(client=FakeClient()).geocode("Boston")

    assert location is not None
    assert location.name == "Boston, Massachusetts, United States"
    assert location.latitude == 42.3584
    assert location.longitude == -71.0598
    assert location.source == "open_meteo_geocoding"


@pytest.mark.anyio
async def test_open_meteo_geocoder_returns_none_without_results() -> None:
    class FakeClient:
        async def search(self, location_name: str, count: int = 1) -> dict:
            return {"results": []}

    location = await OpenMeteoGeocoder(client=FakeClient()).geocode("Not a real place")

    assert location is None


@pytest.mark.anyio
async def test_resolve_location_for_market_uses_external_provider_when_enabled() -> None:
    class FakeExternalGeocoder:
        async def geocode(self, location_name: str):
            assert location_name == "Boston"
            return GeocodedLocation(
                name="Boston",
                latitude=42.3584,
                longitude=-71.0598,
                source="open_meteo_geocoding",
            )

    location = await resolve_location_for_market(
        "Boston",
        provider="open_meteo",
        external_geocoder=FakeExternalGeocoder(),
    )

    assert location is not None
    assert location.name == "Boston"
    assert location.source == "open_meteo_geocoding"
