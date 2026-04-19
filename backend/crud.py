"""CRUD operations for portfolio persistence."""

import json
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.database import Base, engine
from sqlalchemy import Column, DateTime, Float, Integer, String, Text


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    total_capital = Column(Float, default=1_000_000)
    leverage = Column(Float, default=1.0)
    tickers_weights_json = Column(Text, default="{}")
    start_date = Column(String, default="")
    end_date = Column(String, default="")
    view_ticker = Column(String, default="")
    view_relative = Column(String, default="")
    view_return = Column(Float, default=0.02)
    view_confidence = Column(Float, default=0.3)
    max_weight_pct = Column(Integer, default=40)
    mc_paths = Column(Integer, default=10_000)
    lang = Column(String, default="en-US")
    backtest_enabled = Column(Integer, default=0)
    test_ratio = Column(Float, default=0.20)
    market = Column(String, default="us")
    created_at = Column(DateTime, default=datetime.utcnow)


# Ensure tables are created on import
Base.metadata.create_all(bind=engine)


def create_portfolio(db: Session, data: Dict[str, Any]) -> Portfolio:
    record = Portfolio(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_all_portfolios(db: Session) -> List[Portfolio]:
    return db.query(Portfolio).order_by(Portfolio.created_at.desc()).all()
