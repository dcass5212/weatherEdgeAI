from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Market


def test_database_model_creation() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        market = Market(
            source="mock",
            source_market_id="model-test-1",
            question="Will New York City get more than 1 inch of rain on May 5?",
            category="weather",
        )
        db.add(market)
        db.commit()
        db.refresh(market)

        assert market.id is not None
        assert market.active is True
        assert market.closed is False
