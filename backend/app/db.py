from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, text
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
    memberships: Mapped[list["StudentClassMembershipModel"]] = relationship(
        back_populates="classroom",
        cascade="all, delete-orphan",
    )


class StudentProfileModel(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Student")
    first_name: Mapped[str] = mapped_column(String(80), nullable=False, default="Student")
    last_name: Mapped[str] = mapped_column(String(80), nullable=False, default="User")
    school_email: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    memberships: Mapped[list["StudentClassMembershipModel"]] = relationship(
        back_populates="student",
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
    student_id: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
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


class StudentClassMembershipModel(Base):
    __tablename__ = "student_class_memberships"
    __table_args__ = (
        UniqueConstraint("student_id_fk", "classroom_id", name="uq_student_class_membership"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id_fk: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), nullable=False, index=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    student: Mapped[StudentProfileModel] = relationship(back_populates="memberships")
    classroom: Mapped[ClassroomModel] = relationship(back_populates="memberships")


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


class StrategySessionModel(Base):
    __tablename__ = "strategy_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    player_name: Mapped[str] = mapped_column(String(120), nullable=False)
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    assignment_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    total_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    optimal_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_offers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    current_day_brief: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    decisions: Mapped[list["StrategyDecisionModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class StrategyDecisionModel(Base):
    __tablename__ = "strategy_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("strategy_sessions.session_id"), nullable=False, index=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    chosen_offer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chosen_offer_title: Mapped[str] = mapped_column(String(160), nullable=False)
    chosen_profit: Mapped[float] = mapped_column(Float, nullable=False)
    optimal_profit: Mapped[float] = mapped_column(Float, nullable=False)
    offers_json: Mapped[str] = mapped_column(Text, nullable=False)
    day_brief: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    session: Mapped[StrategySessionModel] = relationship(back_populates="decisions")


class DeletedEntityModel(Base):
    __tablename__ = "deleted_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="teacher")
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _runtime_migrate()


def _runtime_migrate() -> None:
    # Lightweight migration for existing sqlite deployments without Alembic.
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        profile_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(student_profiles)")).fetchall()}
        if profile_cols:
            if "first_name" not in profile_cols:
                conn.execute(text("ALTER TABLE student_profiles ADD COLUMN first_name VARCHAR(80) NOT NULL DEFAULT 'Student'"))
            if "last_name" not in profile_cols:
                conn.execute(text("ALTER TABLE student_profiles ADD COLUMN last_name VARCHAR(80) NOT NULL DEFAULT 'User'"))
            if "school_email" not in profile_cols:
                conn.execute(text("ALTER TABLE student_profiles ADD COLUMN school_email VARCHAR(160) NOT NULL DEFAULT ''"))
                conn.execute(
                    text(
                        "UPDATE student_profiles "
                        "SET school_email = lower(replace(student_id, ' ', '')) || '@student.local' "
                        "WHERE school_email = '' OR school_email IS NULL"
                    )
                )
            if "is_active" not in profile_cols:
                conn.execute(text("ALTER TABLE student_profiles ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
            conn.execute(
                text(
                    "UPDATE student_profiles "
                    "SET first_name = CASE "
                    "WHEN first_name IS NULL OR first_name = '' THEN substr(display_name, 1, instr(display_name || ' ', ' ') - 1) "
                    "ELSE first_name END"
                )
            )
            conn.execute(
                text(
                    "UPDATE student_profiles "
                    "SET last_name = CASE "
                    "WHEN last_name IS NULL OR last_name = '' THEN trim(substr(display_name || ' User', instr(display_name || ' ', ' ') + 1)) "
                    "ELSE last_name END"
                )
            )
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_student_profiles_school_email ON student_profiles (school_email)")
            )

        membership_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(student_class_memberships)")).fetchall()}
        if membership_cols and "status" not in membership_cols:
            conn.execute(
                text("ALTER TABLE student_class_memberships ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'active'")
            )
        session_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(game_sessions)")).fetchall()}
        if session_cols and "student_id" not in session_cols:
            conn.execute(text("ALTER TABLE game_sessions ADD COLUMN student_id VARCHAR(24)"))
