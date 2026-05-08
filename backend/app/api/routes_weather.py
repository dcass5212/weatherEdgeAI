import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import ParsedMarket, WeatherForecastSnapshot
from app.db.repositories import latest_forecast_snapshot
from app.db.session import get_db
from app.weather.forecast_service import fetch_forecast_for_parsed_market
from app.weather.schemas import WeatherForecastSnapshotRead


router = APIRouter(prefix="/weather", tags=["weather"])


@router.post("/forecast/{parsed_market_id}", response_model=WeatherForecastSnapshotRead)
async def create_forecast(parsed_market_id: int, db: Session = Depends(get_db)) -> WeatherForecastSnapshot:
    parsed_market = db.get(ParsedMarket, parsed_market_id)
    if parsed_market is None:
        raise HTTPException(status_code=404, detail="Parsed market not found")

    try:
        forecast = await fetch_forecast_for_parsed_market(parsed_market)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Open-Meteo request failed: {exc}") from exc

    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    return forecast


@router.get("/forecast/{parsed_market_id}/latest", response_model=WeatherForecastSnapshotRead)
def get_latest_forecast(parsed_market_id: int, db: Session = Depends(get_db)) -> WeatherForecastSnapshot:
    forecast = latest_forecast_snapshot(db, parsed_market_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail="Forecast snapshot not found")
    return forecast
