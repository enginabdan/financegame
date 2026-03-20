from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class NewGameRequest(BaseModel):
    city: str = "Charlotte, NC"
    player_name: str = "Player"


class StudentJoinAssignmentRequest(BaseModel):
    player_name: str = "Player"
    class_code: str = Field(min_length=4, max_length=24)
    assignment_code: str = Field(min_length=4, max_length=24)


class DayAllocation(BaseModel):
    gig_hours: int = Field(ge=0, le=12)
    delivery_hours: int = Field(ge=0, le=12)
    marketplace_hours: int = Field(ge=0, le=12)
    insurance_choice: Literal["none", "basic", "family"] = "basic"
    car_action: Literal["keep", "maintain", "replace"] = "keep"
    emergency_fund_contribution: float = Field(default=0.0, ge=0.0, le=300.0)


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
    class_code: Optional[str] = None
    assignment_code: Optional[str] = None


class AdvanceDayResponse(BaseModel):
    state: GameState
    result: DailyResult
    score: int


class CreateClassroomRequest(BaseModel):
    class_name: str = Field(min_length=2, max_length=120)


class ClassroomSummary(BaseModel):
    class_code: str
    class_name: str
    assignment_count: int
    active_assignment_count: int
    created_at: datetime


class CreateAssignmentRequest(BaseModel):
    class_code: str = Field(min_length=4, max_length=24)
    title: str = Field(min_length=2, max_length=120)
    city: str = "Charlotte, NC"
    start_cash: float = Field(default=1800.0, ge=200, le=10000)
    duration_days: int = Field(default=30, ge=7, le=90)


class AssignmentSummary(BaseModel):
    assignment_code: str
    class_code: str
    title: str
    city: str
    start_cash: float
    duration_days: int
    is_active: bool
    enrolled_sessions: int
    created_at: datetime


class TeacherSessionSummary(BaseModel):
    session_id: str
    player_name: str
    city: str
    status: str
    day: int
    cash: float
    stress: int
    score: int
    class_code: Optional[str] = None
    assignment_code: Optional[str] = None
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
