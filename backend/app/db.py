from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def _database_url() -> str:
    # Render Postgres URL should be provided as DATABASE_URL in production.
    return os.getenv("DATABASE_URL", "sqlite:///./financegame.db")


DATABASE_URL = _database_url()


class Base(DeclarativeBase):
    pass


class GameSessionModel(Base):
    __tablename__ = "game_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    player_name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cash: Mapped[float] = mapped_column(Float, nullable=False, default=1800.0)
    tax_reserve: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    debt: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stress: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    day_logs: Mapped[list["GameDayLogModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class GameDayLogModel(Base):
    __tablename__ = "game_day_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.session_id"), nullable=False, index=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_income: Mapped[float] = mapped_column(Float, nullable=False)
    platform_fees: Mapped[float] = mapped_column(Float, nullable=False)
    variable_costs: Mapped[float] = mapped_column(Float, nullable=False)
    household_costs: Mapped[float] = mapped_column(Float, nullable=False)
    tax_reserve: Mapped[float] = mapped_column(Float, nullable=False)
    event_title: Mapped[str] = mapped_column(String(120), nullable=False)
    event_text: Mapped[str] = mapped_column(String(255), nullable=False)
    event_cash_impact: Mapped[float] = mapped_column(Float, nullable=False)
    end_cash: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    session: Mapped[GameSessionModel] = relationship(back_populates="day_logs")


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
