from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NewGameRequest(BaseModel):
    city: str = "Charlotte, NC"
    player_name: str = "Player"


class DayAllocation(BaseModel):
    gig_hours: int = Field(ge=0, le=12)
    delivery_hours: int = Field(ge=0, le=12)
    marketplace_hours: int = Field(ge=0, le=12)


class AdvanceDayRequest(BaseModel):
    session_id: str
    allocation: DayAllocation


class DailyResult(BaseModel):
    day: int
    gross_income: float
    platform_fees: float
    variable_costs: float
    household_costs: float
    tax_reserve: float
    event_title: str
    event_text: str
    event_cash_impact: float
    end_cash: float


class GameState(BaseModel):
    session_id: str
    player_name: str
    city: str
    day: int = 1
    cash: float = 1800.0
    tax_reserve: float = 0.0
    debt: float = 0.0
    stress: int = 20
    status: Literal["active", "completed", "failed"] = "active"


class AdvanceDayResponse(BaseModel):
    state: GameState
    result: DailyResult
    score: int


class TeacherSessionSummary(BaseModel):
    session_id: str
    player_name: str
    city: str
    status: str
    day: int
    cash: float
    stress: int
    score: int
    updated_at: datetime


class TeacherOverviewResponse(BaseModel):
    total_sessions: int
    active_sessions: int
    completed_sessions: int
    failed_sessions: int
    avg_score: float


class TeacherDayLog(BaseModel):
    day: int
    gross_income: float
    platform_fees: float
    variable_costs: float
    household_costs: float
    tax_reserve: float
    event_title: str
    event_text: str
    event_cash_impact: float
    end_cash: float
    created_at: datetime
