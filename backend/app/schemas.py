from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class NewGameRequest(BaseModel):
    city: str = "Charlotte, NC"
    player_name: str = "Player"


class StudentJoinAssignmentRequest(BaseModel):
    student_id: str = Field(min_length=6, max_length=24)
    player_name: str = "Player"
    class_code: str = Field(min_length=4, max_length=24)
    assignment_code: str = Field(min_length=4, max_length=24)


class StudentRegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    school_email: str = Field(min_length=5, max_length=160)


class StudentProfileSummary(BaseModel):
    student_id: str
    first_name: str
    last_name: str
    school_email: str
    is_active: bool = True
    created_at: datetime


class StudentClassJoinRequest(BaseModel):
    student_id: str = Field(min_length=6, max_length=24)
    class_code: str = Field(min_length=4, max_length=24)


class StudentClassSummary(BaseModel):
    class_code: str
    class_name: str
    status: Literal["active", "inactive"] = "active"
    joined_at: datetime


class StudentTurnInRequest(BaseModel):
    student_id: str = Field(min_length=6, max_length=24)
    session_id: str = Field(min_length=6, max_length=80)


class StudentAssignmentOption(BaseModel):
    assignment_code: str
    title: str
    city: str
    start_cash: float
    duration_days: int


class StudentClassAssignmentsResponse(BaseModel):
    class_code: str
    class_name: str
    assignments: list[StudentAssignmentOption] = Field(default_factory=list)


class TeacherClassStudentRow(BaseModel):
    student_id: str
    first_name: str
    last_name: str
    school_email: str
    status: Literal["active", "inactive"] = "active"
    joined_at: datetime


class TeacherClassStudentUpdateRequest(BaseModel):
    status: Literal["active", "inactive"]


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
    duration_days: int = 30
    class_code: Optional[str] = None
    assignment_code: Optional[str] = None


class AdvanceDayResponse(BaseModel):
    state: GameState
    result: DailyResult
    score: int


class CreateClassroomRequest(BaseModel):
    class_name: str = Field(min_length=2, max_length=120)


class UpdateClassroomRequest(BaseModel):
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


class UpdateAssignmentRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    city: str | None = None
    start_cash: float | None = Field(default=None, ge=200, le=10000)
    duration_days: int | None = Field(default=None, ge=7, le=90)
    is_active: bool | None = None


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


class AssignmentRubricRow(BaseModel):
    session_id: str
    player_name: str
    day: int
    cash: float
    debt: float
    stress: int
    score: int
    letter_grade: Literal["A", "B", "C", "D", "F"]
    performance_band: str
    status: str
    updated_at: datetime


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


class UpdateTeacherSessionRequest(BaseModel):
    player_name: str | None = Field(default=None, min_length=1, max_length=120)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    status: Literal["active", "completed", "failed"] | None = None
    day: int | None = Field(default=None, ge=1, le=120)
    cash: float | None = Field(default=None, ge=-50000, le=500000)
    tax_reserve: float | None = Field(default=None, ge=0, le=100000)
    debt: float | None = Field(default=None, ge=0, le=100000)
    stress: int | None = Field(default=None, ge=0, le=100)
    score: int | None = Field(default=None, ge=0, le=100)


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


class StrategyStartRequest(BaseModel):
    player_name: str = "Student"
    total_days: int = Field(default=30, ge=7, le=45)
    assignment_minutes: int = Field(default=60, ge=20, le=120)


class StrategyOffer(BaseModel):
    offer_id: str
    title: str
    text: str
    channel: str
    time_hours: float
    miles: float
    cash_in: float
    cash_out: float
    risk: Literal["low", "medium", "high"] = "medium"


class StrategyPublicState(BaseModel):
    session_id: str
    player_name: str
    current_day: int
    total_days: int
    assignment_minutes: int
    status: Literal["active", "completed"] = "active"
    total_profit: float
    selected_count: int
    offers: list[StrategyOffer] = Field(default_factory=list)
    day_brief: str = ""


class StrategyChooseRequest(BaseModel):
    session_id: str
    offer_id: str


class StrategyChooseResponse(BaseModel):
    state: StrategyPublicState
    chosen_offer_title: str
    chosen_profit: float
    running_profit: float


class StrategyResultResponse(BaseModel):
    session_id: str
    player_name: str
    total_days: int
    student_profit: float
    optimal_profit: float
    success_percentage: float
    status: Literal["active", "completed"]


class StrategyLeaderboardRow(BaseModel):
    session_id: str
    player_name: str
    current_day: int
    total_days: int
    total_profit: float
    optimal_profit: float
    success_percentage: float
    status: Literal["active", "completed"]
    updated_at: datetime


class StrategyOfferReview(BaseModel):
    offer_id: str
    title: str
    channel: str
    cash_in: float
    cash_out: float
    expected_profit: float
    risk: Literal["low", "medium", "high"] = "medium"


class StrategyDecisionReview(BaseModel):
    id: int
    day: int
    chosen_offer_id: str
    chosen_offer_title: str
    chosen_profit: float
    optimal_profit: float
    gap_to_optimal: float
    day_brief: str
    offers: list[StrategyOfferReview] = Field(default_factory=list)
    created_at: datetime


class StrategySessionReview(BaseModel):
    session_id: str
    player_name: str
    current_day: int
    total_days: int
    assignment_minutes: int
    status: Literal["active", "completed"]
    total_profit: float
    optimal_profit: float
    success_percentage: float
    selected_count: int
    created_at: datetime
    updated_at: datetime
    decisions: list[StrategyDecisionReview] = Field(default_factory=list)


class ActionResponse(BaseModel):
    ok: bool = True
    message: str


class DeletedEntitySummary(BaseModel):
    id: int
    entity_type: str
    entity_key: str
    deleted_at: datetime


class BulkDeleteRequest(BaseModel):
    ids: list[str] = Field(default_factory=list, min_length=1, max_length=500)


class BulkArchiveRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, min_length=1, max_length=500)


class PurgeOlderRequest(BaseModel):
    days: int = Field(ge=1, le=3650)


class AuditEventSummary(BaseModel):
    id: int
    actor: str
    action: str
    target_type: str
    target_key: str
    created_at: datetime


class TeacherRiskAlert(BaseModel):
    session_id: str
    player_name: str
    class_code: str | None = None
    assignment_code: str | None = None
    status: str
    day: int
    cash: float
    debt: float
    stress: int
    score: int
    risk_score: int
    risk_level: Literal["low", "medium", "high", "critical"]
    reasons: list[str] = Field(default_factory=list)
