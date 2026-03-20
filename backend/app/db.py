from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def _database_url() -> str:
    # Render/Cloud Run Postgres URL should be provided as DATABASE_URL in production.
    return os.getenv("DATABASE_URL", "sqlite:///./financegame.db")


DATABASE_URL = _database_url()


class Base(DeclarativeBase):
    pass


class ClassroomModel(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    class_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    assignments: Mapped[list["AssignmentModel"]] = relationship(
        back_populates="classroom",
        cascade="all, delete-orphan",
    )


class AssignmentModel(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False, default="Charlotte, NC")
    start_cash: Mapped[float] = mapped_column(Float, nullable=False, default=1800.0)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    classroom: Mapped[ClassroomModel] = relationship(back_populates="assignments")
    enrollments: Mapped[list["AssignmentEnrollmentModel"]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


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
    enrollments: Mapped[list["AssignmentEnrollmentModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AssignmentEnrollmentModel(Base):
    __tablename__ = "assignment_enrollments"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_assignment_enrollment_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.session_id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    assignment: Mapped[AssignmentModel] = relationship(back_populates="enrollments")
    session: Mapped[GameSessionModel] = relationship(back_populates="enrollments")


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
