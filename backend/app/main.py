from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Generator, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .db import SessionLocal, init_db
from .engine import FinanceGameEngine
from .repository import GameRepository
from .schemas import (
    AdvanceDayRequest,
    AdvanceDayResponse,
    AssignmentRubricRow,
    AssignmentSummary,
    ClassroomSummary,
    CreateAssignmentRequest,
    CreateClassroomRequest,
    DailyResult,
    GameState,
    NewGameRequest,
    StudentJoinAssignmentRequest,
    TeacherDayLog,
    TeacherOverviewResponse,
    TeacherSessionSummary,
)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

app = FastAPI(title="Hustle & Home API", version="0.3.0")
engine = FinanceGameEngine()

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:4173,http://localhost:4173").split(",")
TEACHER_API_KEY = os.getenv("TEACHER_API_KEY", "")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _require_teacher_key(x_teacher_key: Optional[str]) -> None:
    if not TEACHER_API_KEY:
        raise HTTPException(status_code=503, detail="Teacher API key not configured")
    if x_teacher_key != TEACHER_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid teacher key")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/new-game", response_model=GameState)
def new_game(req: NewGameRequest, db: Session = Depends(get_db)) -> GameState:
    session_id = str(uuid.uuid4())
    state = GameState(session_id=session_id, player_name=req.player_name, city=req.city)
    repo = GameRepository(db)
    repo.create_session(state)
    return state


@app.post("/api/student/join-assignment", response_model=GameState)
def join_assignment(req: StudentJoinAssignmentRequest, db: Session = Depends(get_db)) -> GameState:
    repo = GameRepository(db)
    session_id = str(uuid.uuid4())
    try:
        return repo.create_session_from_assignment(
            player_name=req.player_name,
            class_code=req.class_code,
            assignment_code=req.assignment_code,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/advance-day", response_model=AdvanceDayResponse)
def advance_day(req: AdvanceDayRequest, db: Session = Depends(get_db)) -> AdvanceDayResponse:
    repo = GameRepository(db)
    state = repo.get_state(req.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    if state.status != "active":
        raise HTTPException(status_code=400, detail=f"Game already {state.status}")

    total_hours = req.allocation.gig_hours + req.allocation.delivery_hours + req.allocation.marketplace_hours
    if total_hours > 14:
        raise HTTPException(status_code=400, detail="Total daily hours cannot exceed 14")

    result_data = engine.run_day(state, req.allocation)
    result = DailyResult(**result_data)
    score = engine.score(state)
    repo.update_state_and_log(state=state, score=score, result=result)

    return AdvanceDayResponse(state=state, result=result, score=score)


@app.post("/api/teacher/classes", response_model=ClassroomSummary)
def create_classroom(
    req: CreateClassroomRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ClassroomSummary:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    return repo.create_classroom(class_name=req.class_name)


@app.get("/api/teacher/classes", response_model=list[ClassroomSummary])
def list_classes(
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[ClassroomSummary]:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    return repo.list_classrooms()


@app.post("/api/teacher/assignments", response_model=AssignmentSummary)
def create_assignment(
    req: CreateAssignmentRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> AssignmentSummary:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.create_assignment(
            class_code=req.class_code,
            title=req.title,
            city=req.city,
            start_cash=req.start_cash,
            duration_days=req.duration_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/teacher/assignments", response_model=list[AssignmentSummary])
def list_assignments(
    class_code: str | None = None,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[AssignmentSummary]:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    return repo.list_assignments(class_code=class_code)


@app.get("/api/teacher/assignments/{assignment_code}/rubric", response_model=list[AssignmentRubricRow])
def assignment_rubric(
    assignment_code: str,
    limit: int = 200,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[AssignmentRubricRow]:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    safe_limit = max(1, min(limit, 400))
    return repo.assignment_rubric(assignment_code=assignment_code, limit=safe_limit)


@app.get("/api/teacher/overview", response_model=TeacherOverviewResponse)
def teacher_overview(
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> TeacherOverviewResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    return repo.teacher_overview()


@app.get("/api/teacher/sessions", response_model=list[TeacherSessionSummary])
def teacher_sessions(
    limit: int = 50,
    class_code: str | None = None,
    assignment_code: str | None = None,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[TeacherSessionSummary]:
    _require_teacher_key(x_teacher_key)
    safe_limit = max(1, min(limit, 200))
    repo = GameRepository(db)
    return repo.teacher_sessions(
        limit=safe_limit,
        class_code=class_code,
        assignment_code=assignment_code,
    )


@app.get("/api/teacher/sessions/{session_id}/logs", response_model=list[TeacherDayLog])
def teacher_session_logs(
    session_id: str,
    limit: int = 30,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[TeacherDayLog]:
    _require_teacher_key(x_teacher_key)
    safe_limit = max(1, min(limit, 90))
    repo = GameRepository(db)
    return repo.teacher_session_logs(session_id=session_id, limit=safe_limit)
