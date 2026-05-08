from fastapi import FastAPI

from app.api.routes_health import router as health_router
from app.api.routes_backtests import router as backtests_router
from app.api.routes_markets import router as markets_router
from app.api.routes_paper_trades import router as paper_trades_router
from app.api.routes_predictions import router as predictions_router
from app.api.routes_strategy import router as strategy_router
from app.api.routes_weather import router as weather_router
from app.config import settings


app = FastAPI(title=settings.APP_NAME, version="0.1.0")

app.include_router(health_router)
app.include_router(markets_router)
app.include_router(weather_router)
app.include_router(predictions_router)
app.include_router(strategy_router)
app.include_router(paper_trades_router)
app.include_router(backtests_router)
