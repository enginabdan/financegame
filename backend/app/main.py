from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth, credentials
except Exception:  # pragma: no cover - optional dependency fallback
    firebase_admin = None
    firebase_auth = None
    credentials = None
try:
    from google.cloud import firestore, storage
except Exception:  # pragma: no cover - optional dependency fallback
    firestore = None
    storage = None
from sqlalchemy.orm import Session

from .db import SessionLocal, init_db
from .engine import FinanceGameEngine, StrategyAssignmentEngine
from .repository import GameRepository
from .schemas import (
    ActionResponse,
    AdvanceDayRequest,
    AdvanceDayResponse,
    AssignmentRubricRow,
    AssignmentSummary,
    AuditEventSummary,
    BulkArchiveRequest,
    BulkDeleteRequest,
    ClassroomSummary,
    CreateAssignmentRequest,
    CreateClassroomRequest,
    DeletedEntitySummary,
    DailyResult,
    GameState,
    NewGameRequest,
    PurgeOlderRequest,
    StudentClassJoinRequest,
    StudentClassSummary,
    StudentClassAssignmentsResponse,
    StudentProfileSummary,
    StudentRegisterRequest,
    StudentTurnInRequest,
    StudentJoinAssignmentRequest,
    TeacherClassStudentRow,
    TeacherClassStudentUpdateRequest,
    UpdateAssignmentRequest,
    UpdateClassroomRequest,
    UpdateTeacherSessionRequest,
    StrategyChooseRequest,
    StrategyChooseResponse,
    StrategyLeaderboardRow,
    StrategyResultResponse,
    StrategySessionReview,
    StrategyStartRequest,
    StrategyPublicState,
    TeacherDayLog,
    TeacherRiskAlert,
    TeacherOverviewResponse,
    TeacherSessionSummary,
)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

USE_FIRESTORE = os.getenv("USE_FIRESTORE", "").strip().lower() in {"1", "true", "yes", "on"} or bool(
    os.getenv("FIREBASE_PROJECT_ID", "").strip()
)
if USE_FIRESTORE:
    try:
        from .firestore_repository import FirestoreGameRepository

        GameRepository = FirestoreGameRepository  # type: ignore[misc,assignment]
    except Exception:
        USE_FIRESTORE = False

app = FastAPI(title="Hustle & Home API", version="0.3.0")
engine = FinanceGameEngine()
strategy_engine = StrategyAssignmentEngine()

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:4173,http://localhost:4173").split(",")
TEACHER_API_KEY = os.getenv("TEACHER_API_KEY", "")
USE_FIREBASE_AUTH = os.getenv("USE_FIREBASE_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "").strip()
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
MAX_EVIDENCE_FILE_BYTES = 15 * 1024 * 1024

if USE_FIREBASE_AUTH:
    if firebase_admin is None:
        USE_FIREBASE_AUTH = False
    else:
        try:
            if not firebase_admin._apps:
                cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
                if cred_path:
                    firebase_admin.initialize_app(credentials.Certificate(cred_path))
                else:
                    firebase_admin.initialize_app()
        except Exception:
            USE_FIREBASE_AUTH = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    if not USE_FIRESTORE:
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


def _verify_firebase_token(authorization: Optional[str]) -> dict:
    if not USE_FIREBASE_AUTH:
        raise HTTPException(status_code=503, detail="Firebase Auth is not enabled")
    if firebase_auth is None:
        raise HTTPException(status_code=503, detail="firebase_admin is not installed")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Firebase bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Firebase bearer token")
    try:
        return firebase_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Firebase token") from exc


def _student_email_from_record(student_obj: object) -> str:
    if isinstance(student_obj, dict):
        return str(student_obj.get("school_email", "")).strip().lower()
    return str(getattr(student_obj, "school_email", "")).strip().lower()


def _require_student_access(repo: GameRepository, student_id: str, authorization: Optional[str]) -> None:
    if not USE_FIREBASE_AUTH:
        return
    decoded = _verify_firebase_token(authorization)
    token_email = str(decoded.get("email", "")).strip().lower()
    if not token_email:
        raise HTTPException(status_code=401, detail="Firebase token has no email")
    student_obj = repo.get_student(student_id)
    if student_obj is None:
        raise HTTPException(status_code=404, detail="Student profile not found")
    student_email = _student_email_from_record(student_obj)
    if student_email != token_email:
        raise HTTPException(status_code=403, detail="Student token email does not match student profile")


def _parse_iso_datetime(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format. Use ISO datetime.") from exc


def _require_firestore_mode() -> None:
    if not USE_FIRESTORE:
        raise HTTPException(status_code=400, detail="This feature requires USE_FIRESTORE=1")
    if firestore is None or storage is None:
        raise HTTPException(status_code=503, detail="google-cloud-firestore/storage is not installed")


def _get_firestore_client() -> firestore.Client:
    _require_firestore_mode()
    return firestore.Client(project=FIREBASE_PROJECT_ID or None) if FIREBASE_PROJECT_ID else firestore.Client()


def _resolve_storage_bucket_name() -> str:
    if FIREBASE_STORAGE_BUCKET:
        return FIREBASE_STORAGE_BUCKET
    if FIREBASE_PROJECT_ID:
        return f"{FIREBASE_PROJECT_ID}.appspot.com"
    raise HTTPException(status_code=503, detail="FIREBASE_STORAGE_BUCKET or FIREBASE_PROJECT_ID must be set")


def _get_storage_bucket():
    bucket_name = _resolve_storage_bucket_name()
    client = storage.Client(project=FIREBASE_PROJECT_ID or None) if FIREBASE_PROJECT_ID else storage.Client()
    return client.bucket(bucket_name)


def _sanitize_filename(filename: str) -> str:
    base = Path(filename or "upload.bin").name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-")
    return clean or "upload.bin"


def _serialize_firestore_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_firestore_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_firestore_value(v) for v in value]
    return value


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


@app.post("/api/student/register", response_model=StudentProfileSummary)
def register_student(
    req: StudentRegisterRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> StudentProfileSummary:
    repo = GameRepository(db)
    if USE_FIREBASE_AUTH:
        decoded = _verify_firebase_token(authorization)
        token_email = str(decoded.get("email", "")).strip().lower()
        if not token_email:
            raise HTTPException(status_code=401, detail="Firebase token has no email")
        if token_email != req.school_email.strip().lower():
            raise HTTPException(status_code=403, detail="School email must match Firebase login email")
    try:
        return repo.register_student_with_identity(
            first_name=req.first_name,
            last_name=req.last_name,
            school_email=req.school_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/student/join-class", response_model=StudentClassSummary)
def join_class(
    req: StudentClassJoinRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> StudentClassSummary:
    repo = GameRepository(db)
    _require_student_access(repo, req.student_id, authorization)
    try:
        return repo.join_class(student_id=req.student_id, class_code=req.class_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/student/me/classes", response_model=list[StudentClassSummary])
def student_classes(
    student_id: str,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[StudentClassSummary]:
    repo = GameRepository(db)
    _require_student_access(repo, student_id, authorization)
    try:
        return repo.student_classes(student_id=student_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/student/join-assignment", response_model=GameState)
def join_assignment(
    req: StudentJoinAssignmentRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> GameState:
    repo = GameRepository(db)
    _require_student_access(repo, req.student_id, authorization)
    session_id = str(uuid.uuid4())
    try:
        return repo.create_session_from_assignment(
            student_id=req.student_id,
            player_name=req.player_name,
            class_code=req.class_code,
            assignment_code=req.assignment_code,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/student/join-assignment-sprint", response_model=StrategyPublicState)
def join_assignment_sprint(
    req: StudentJoinAssignmentRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> StrategyPublicState:
    repo = GameRepository(db)
    _require_student_access(repo, req.student_id, authorization)
    brief, offers = strategy_engine.build_day_offers(
        day=1,
        total_days=30,
        running_profit=0.0,
        previous_channels=[],
    )
    offers_payload = [
        {
            "offer_id": o.offer_id,
            "title": o.title,
            "text": o.text,
            "channel": o.channel,
            "time_hours": o.time_hours,
            "miles": o.miles,
            "cash_in": o.cash_in,
            "cash_out": o.cash_out,
            "risk": o.risk,
            "expected_profit": o.expected_profit,
        }
        for o in offers
    ]
    try:
        return repo.create_strategy_session_from_assignment(
            student_id=req.student_id,
            player_name=req.player_name,
            class_code=req.class_code,
            assignment_code=req.assignment_code,
            offers=offers_payload,
            day_brief=brief,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/student/classes/{class_code}/assignments", response_model=StudentClassAssignmentsResponse)
def student_class_assignments(
    class_code: str,
    student_id: str,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> StudentClassAssignmentsResponse:
    repo = GameRepository(db)
    _require_student_access(repo, student_id, authorization)
    try:
        return repo.student_class_assignments(student_id=student_id, class_code=class_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/student/turn-in", response_model=ActionResponse)
def student_turn_in(
    req: StudentTurnInRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    repo = GameRepository(db)
    _require_student_access(repo, req.student_id, authorization)
    try:
        return repo.turn_in_assignment(session_id=req.session_id, student_id=req.student_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/student/turn-in-sprint", response_model=ActionResponse)
def student_turn_in_sprint(
    req: StudentTurnInRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    repo = GameRepository(db)
    _require_student_access(repo, req.student_id, authorization)
    try:
        return repo.turn_in_strategy_assignment(session_id=req.session_id, student_id=req.student_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/student/evidence/upload")
async def student_upload_evidence(
    student_id: str = Form(...),
    note: str = Form(default=""),
    session_id: str = Form(default=""),
    class_code: str = Form(default=""),
    assignment_code: str = Form(default=""),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    repo = GameRepository(db)
    _require_student_access(repo, student_id, authorization)
    _require_firestore_mode()

    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_EVIDENCE_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 15MB limit")

    student_key = student_id.strip().upper()
    evidence_id = uuid.uuid4().hex
    safe_filename = _sanitize_filename(file.filename)
    object_name = f"evidence/{student_key}/{evidence_id}-{safe_filename}"
    content_type = (file.content_type or "application/octet-stream").strip()

    bucket = _get_storage_bucket()
    blob = bucket.blob(object_name)
    blob.upload_from_string(content, content_type=content_type)

    now = datetime.utcnow()
    record = {
        "evidence_id": evidence_id,
        "student_id": student_key,
        "session_id": session_id.strip(),
        "class_code": class_code.strip().upper(),
        "assignment_code": assignment_code.strip().upper(),
        "note": note.strip(),
        "filename": safe_filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "bucket": bucket.name,
        "object_name": object_name,
        "created_at": now,
    }
    fs = _get_firestore_client()
    fs.collection("student_evidence").document(evidence_id).set(record)
    return {
        "evidence_id": evidence_id,
        "student_id": student_key,
        "filename": safe_filename,
        "size_bytes": len(content),
        "content_type": content_type,
        "session_id": session_id.strip(),
        "class_code": class_code.strip().upper(),
        "assignment_code": assignment_code.strip().upper(),
        "note": note.strip(),
        "created_at": now.isoformat(),
    }


@app.get("/api/student/evidence")
def student_list_evidence(
    student_id: str,
    limit: int = 50,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    repo = GameRepository(db)
    _require_student_access(repo, student_id, authorization)
    _require_firestore_mode()
    safe_limit = max(1, min(limit, 200))
    student_key = student_id.strip().upper()
    fs = _get_firestore_client()
    rows: list[dict] = []
    for doc in fs.collection("student_evidence").stream():
        data = doc.to_dict() or {}
        if str(data.get("student_id", "")).upper() != student_key:
            continue
        data["download_endpoint"] = f"/api/student/evidence/{doc.id}/download?student_id={student_key}"
        rows.append(_serialize_firestore_value(data))
    rows.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return rows[:safe_limit]


@app.get("/api/student/evidence/{evidence_id}/download")
def student_download_evidence(
    evidence_id: str,
    student_id: str,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Response:
    repo = GameRepository(db)
    _require_student_access(repo, student_id, authorization)
    _require_firestore_mode()
    fs = _get_firestore_client()
    snap = fs.collection("student_evidence").document(evidence_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Evidence not found")
    data = snap.to_dict() or {}
    if str(data.get("student_id", "")).upper() != student_id.strip().upper():
        raise HTTPException(status_code=403, detail="Evidence does not belong to this student")
    bucket = _get_storage_bucket()
    blob = bucket.blob(str(data.get("object_name", "")))
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Evidence file not found in storage")
    payload = blob.download_as_bytes()
    filename = str(data.get("filename", "evidence.bin"))
    content_type = str(data.get("content_type", "application/octet-stream"))
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type=content_type, headers=headers)


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


@app.get("/api/teacher/classes/{class_code}/students", response_model=list[TeacherClassStudentRow])
def class_students(
    class_code: str,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[TeacherClassStudentRow]:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.class_students(class_code=class_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/teacher/classes/{class_code}/students/{student_id}", response_model=ActionResponse)
def remove_student_from_class(
    class_code: str,
    student_id: str,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.remove_student_from_class(class_code=class_code, student_id=student_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/teacher/classes/{class_code}/students/{student_id}", response_model=ActionResponse)
def update_student_membership_status(
    class_code: str,
    student_id: str,
    req: TeacherClassStudentUpdateRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.set_student_class_membership_status(class_code=class_code, student_id=student_id, status=req.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/teacher/classes/{class_code}", response_model=ClassroomSummary)
def update_classroom(
    class_code: str,
    req: UpdateClassroomRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ClassroomSummary:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.update_classroom(class_code=class_code, class_name=req.class_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/teacher/classes/{class_code}", response_model=ActionResponse)
def delete_classroom(
    class_code: str,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.delete_classroom(class_code=class_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
            sprint_minutes_per_day=req.sprint_minutes_per_day,
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


@app.patch("/api/teacher/assignments/{assignment_code}", response_model=AssignmentSummary)
def update_assignment(
    assignment_code: str,
    req: UpdateAssignmentRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> AssignmentSummary:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.update_assignment(
            assignment_code=assignment_code,
            title=req.title,
            city=req.city,
            start_cash=req.start_cash,
            duration_days=req.duration_days,
            sprint_minutes_per_day=req.sprint_minutes_per_day,
            is_active=req.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/teacher/assignments/{assignment_code}", response_model=ActionResponse)
def delete_assignment(
    assignment_code: str,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.delete_assignment(assignment_code=assignment_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


@app.patch("/api/teacher/sessions/{session_id}", response_model=TeacherSessionSummary)
def update_teacher_session(
    session_id: str,
    req: UpdateTeacherSessionRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> TeacherSessionSummary:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.update_teacher_session(
            session_id=session_id,
            player_name=req.player_name,
            city=req.city,
            status=req.status,
            day=req.day,
            cash=req.cash,
            tax_reserve=req.tax_reserve,
            debt=req.debt,
            stress=req.stress,
            score=req.score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/teacher/sessions/{session_id}", response_model=ActionResponse)
def delete_teacher_session(
    session_id: str,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.delete_teacher_session(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/teacher/sessions/{session_id}/enrollment", response_model=ActionResponse)
def remove_teacher_session_enrollment(
    session_id: str,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.remove_session_from_class(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/teacher/sessions/bulk-delete", response_model=ActionResponse)
def bulk_delete_teacher_sessions(
    req: BulkDeleteRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    return repo.bulk_delete_sessions(session_ids=req.ids)


@app.post("/api/strategy/start", response_model=StrategyPublicState)
def strategy_start(req: StrategyStartRequest, db: Session = Depends(get_db)) -> StrategyPublicState:
    repo = GameRepository(db)
    brief, offers = strategy_engine.build_day_offers(
        day=1,
        total_days=req.total_days,
        running_profit=0.0,
        previous_channels=[],
    )
    offers_payload = [
        {
            "offer_id": o.offer_id,
            "title": o.title,
            "text": o.text,
            "channel": o.channel,
            "time_hours": o.time_hours,
            "miles": o.miles,
            "cash_in": o.cash_in,
            "cash_out": o.cash_out,
            "risk": o.risk,
            "expected_profit": o.expected_profit,
        }
        for o in offers
    ]
    return repo.create_strategy_session(
        player_name=req.player_name,
        total_days=req.total_days,
        assignment_minutes=req.assignment_minutes,
        offers=offers_payload,
        day_brief=brief,
    )


@app.get("/api/strategy/{session_id}", response_model=StrategyPublicState)
def strategy_state(session_id: str, db: Session = Depends(get_db)) -> StrategyPublicState:
    repo = GameRepository(db)
    state = repo.get_strategy_state(session_id=session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Strategy session not found")
    return state


@app.get("/api/strategy/{session_id}/result", response_model=StrategyResultResponse)
def strategy_result(session_id: str, db: Session = Depends(get_db)) -> StrategyResultResponse:
    repo = GameRepository(db)
    result = repo.strategy_result(session_id=session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Strategy session not found")
    return result


@app.post("/api/strategy/choose", response_model=StrategyChooseResponse)
def strategy_choose(req: StrategyChooseRequest, db: Session = Depends(get_db)) -> StrategyChooseResponse:
    repo = GameRepository(db)
    state = repo.get_strategy_state(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Strategy session not found")
    if state.status != "active":
        raise HTTPException(status_code=400, detail="Strategy session already completed")

    previous_channels = repo.list_strategy_recent_channels(req.session_id, limit=6)
    next_offers_payload: list[dict] | None = None
    next_brief: str | None = None

    if state.current_day < state.total_days:
        next_brief, next_offers = strategy_engine.build_day_offers(
            day=state.current_day + 1,
            total_days=state.total_days,
            running_profit=state.total_profit,
            previous_channels=previous_channels,
        )
        next_offers_payload = [
            {
                "offer_id": o.offer_id,
                "title": o.title,
                "text": o.text,
                "channel": o.channel,
                "time_hours": o.time_hours,
                "miles": o.miles,
                "cash_in": o.cash_in,
                "cash_out": o.cash_out,
                "risk": o.risk,
                "expected_profit": o.expected_profit,
            }
            for o in next_offers
        ]

    try:
        return repo.choose_strategy_offer(
            session_id=req.session_id,
            offer_id=req.offer_id,
            next_offers=next_offers_payload,
            next_day_brief=next_brief,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/teacher/strategy/leaderboard", response_model=list[StrategyLeaderboardRow])
def teacher_strategy_leaderboard(
    limit: int = 50,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[StrategyLeaderboardRow]:
    _require_teacher_key(x_teacher_key)
    safe_limit = max(1, min(limit, 200))
    repo = GameRepository(db)
    return repo.strategy_leaderboard(limit=safe_limit)


@app.get("/api/teacher/strategy/sessions/{session_id}", response_model=StrategySessionReview)
def teacher_strategy_session_review(
    session_id: str,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> StrategySessionReview:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    review = repo.strategy_session_review(session_id=session_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Strategy session not found")
    return review


@app.delete("/api/teacher/strategy/sessions/{session_id}", response_model=ActionResponse)
def teacher_delete_strategy_session(
    session_id: str,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.delete_strategy_session(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/teacher/strategy/sessions/bulk-delete", response_model=ActionResponse)
def teacher_bulk_delete_strategy_sessions(
    req: BulkDeleteRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    return repo.bulk_delete_strategy_sessions(session_ids=req.ids)


@app.get("/api/teacher/trash", response_model=list[DeletedEntitySummary])
def teacher_list_trash(
    limit: int = 200,
    entity_type: str | None = None,
    since_days: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[DeletedEntitySummary]:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    safe_limit = max(1, min(limit, 500))
    safe_since_days = None if since_days is None else max(1, min(since_days, 3650))
    parsed_from = _parse_iso_datetime(from_date, "from_date")
    parsed_to = _parse_iso_datetime(to_date, "to_date")
    return repo.list_deleted_entities(
        limit=safe_limit,
        entity_type=entity_type,
        since_days=safe_since_days,
        from_date=parsed_from,
        to_date=parsed_to,
    )


@app.post("/api/teacher/trash/{archive_id}/restore", response_model=ActionResponse)
def teacher_restore_from_trash(
    archive_id: int,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    try:
        return repo.restore_deleted_entity(archive_id=archive_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/teacher/trash/bulk-restore", response_model=ActionResponse)
def teacher_bulk_restore_from_trash(
    req: BulkArchiveRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    return repo.bulk_restore_deleted_entities(archive_ids=req.ids)


@app.post("/api/teacher/trash/purge", response_model=ActionResponse)
def teacher_purge_trash(
    req: BulkArchiveRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    return repo.purge_deleted_entities(archive_ids=req.ids)


@app.post("/api/teacher/trash/purge-older", response_model=ActionResponse)
def teacher_purge_trash_older(
    req: PurgeOlderRequest,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    return repo.purge_deleted_entities_older_than(days=req.days)


@app.get("/api/teacher/audit", response_model=list[AuditEventSummary])
def teacher_audit_events(
    limit: int = 300,
    action: str | None = None,
    target_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[AuditEventSummary]:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    safe_limit = max(1, min(limit, 1000))
    return repo.list_audit_events(
        limit=safe_limit,
        action=action,
        target_type=target_type,
        from_date=_parse_iso_datetime(from_date, "from_date"),
        to_date=_parse_iso_datetime(to_date, "to_date"),
    )


@app.get("/api/teacher/risk-alerts", response_model=list[TeacherRiskAlert])
def teacher_risk_alerts(
    limit: int = 100,
    class_code: str | None = None,
    assignment_code: str | None = None,
    x_teacher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> list[TeacherRiskAlert]:
    _require_teacher_key(x_teacher_key)
    repo = GameRepository(db)
    safe_limit = max(1, min(limit, 300))
    return repo.teacher_risk_alerts(
        limit=safe_limit,
        class_code=class_code,
        assignment_code=assignment_code,
    )


@app.get("/api/teacher/evidence")
def teacher_list_evidence(
    limit: int = 100,
    class_code: str | None = None,
    assignment_code: str | None = None,
    student_id: str | None = None,
    x_teacher_key: Optional[str] = Header(default=None),
) -> list[dict]:
    _require_teacher_key(x_teacher_key)
    _require_firestore_mode()
    safe_limit = max(1, min(limit, 400))
    class_filter = (class_code or "").strip().upper()
    assignment_filter = (assignment_code or "").strip().upper()
    student_filter = (student_id or "").strip().upper()
    fs = _get_firestore_client()
    rows: list[dict] = []
    for doc in fs.collection("student_evidence").stream():
        data = doc.to_dict() or {}
        if class_filter and str(data.get("class_code", "")).upper() != class_filter:
            continue
        if assignment_filter and str(data.get("assignment_code", "")).upper() != assignment_filter:
            continue
        if student_filter and str(data.get("student_id", "")).upper() != student_filter:
            continue
        out = _serialize_firestore_value(data)
        out["download_endpoint"] = f"/api/teacher/evidence/{doc.id}/download"
        rows.append(out)
    rows.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return rows[:safe_limit]


@app.get("/api/teacher/evidence/{evidence_id}/download")
def teacher_download_evidence(
    evidence_id: str,
    x_teacher_key: Optional[str] = Header(default=None),
) -> Response:
    _require_teacher_key(x_teacher_key)
    _require_firestore_mode()
    fs = _get_firestore_client()
    snap = fs.collection("student_evidence").document(evidence_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Evidence not found")
    data = snap.to_dict() or {}
    bucket = _get_storage_bucket()
    blob = bucket.blob(str(data.get("object_name", "")))
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Evidence file not found in storage")
    payload = blob.download_as_bytes()
    filename = str(data.get("filename", "evidence.bin"))
    content_type = str(data.get("content_type", "application/octet-stream"))
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type=content_type, headers=headers)


@app.delete("/api/teacher/evidence/{evidence_id}", response_model=ActionResponse)
def teacher_delete_evidence(
    evidence_id: str,
    x_teacher_key: Optional[str] = Header(default=None),
) -> ActionResponse:
    _require_teacher_key(x_teacher_key)
    _require_firestore_mode()
    fs = _get_firestore_client()
    ref = fs.collection("student_evidence").document(evidence_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Evidence not found")
    data = snap.to_dict() or {}
    bucket = _get_storage_bucket()
    object_name = str(data.get("object_name", "")).strip()
    if object_name:
        blob = bucket.blob(object_name)
        if blob.exists():
            blob.delete()
    ref.delete()
    return ActionResponse(message=f"Evidence {evidence_id} deleted")
