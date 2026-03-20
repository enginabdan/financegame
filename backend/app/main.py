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
    DailyResult,
    GameState,
    NewGameRequest,
    TeacherDayLog,
    TeacherOverviewResponse,
    TeacherSessionSummary,
)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

app = FastAPI(title="Hustle & Home API", version="0.2.0")
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


@app.post("/api/advance-day", response_model=AdvanceDayResponse)
def advance_day(req: AdvanceDayRequest, db: Session = Depends(get_db)) -> AdvanceDayResponse:
    repo = GameRepository(db)
    state = repo.get_state(req.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    if state.status != "active":
        raise HTTPException(status_code=400, detail=f"Game already {state.status}")

    result_data = engine.run_day(state, req.allocation)
    result = DailyResult(**result_data)
    score = engine.score(state)
    repo.update_state_and_log(state=state, score=score, result=result)

    return AdvanceDayResponse(state=state, result=result, score=score)


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
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[TeacherSessionSummary]:
    _require_teacher_key(x_teacher_key)
    safe_limit = max(1, min(limit, 200))
    repo = GameRepository(db)
    return repo.teacher_sessions(limit=safe_limit)


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
