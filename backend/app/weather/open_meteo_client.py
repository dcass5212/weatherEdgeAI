import httpx

from app.config import settings


class OpenMeteoClient:
    def __init__(self, base_url: str = settings.OPEN_METEO_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
    ) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            # TODO: Normalize forecast output into internal weather snapshot schemas.
            response = await client.get(
                "/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "start_date": start_date,
                    "end_date": end_date,
                    "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
                    "timezone": "auto",
                },
            )
            response.raise_for_status()
            return response.json()


class OpenMeteoArchiveClient:
    def __init__(self, base_url: str = settings.OPEN_METEO_ARCHIVE_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def fetch_daily_observations(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
    ) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.get(
                "/archive",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "start_date": start_date,
                    "end_date": end_date,
                    "daily": "precipitation_sum",
                    "timezone": "auto",
                },
            )
            response.raise_for_status()
            return response.json()
