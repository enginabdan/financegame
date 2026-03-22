from __future__ import annotations

import json
import os
import random
import string
from datetime import datetime, timedelta
from typing import Any

from google.cloud import firestore

from .schemas import (
    ActionResponse,
    AssignmentRubricRow,
    AssignmentSummary,
    AuditEventSummary,
    ClassroomSummary,
    DailyResult,
    DeletedEntitySummary,
    GameState,
    StudentAssignmentOption,
    StudentClassAssignmentsResponse,
    StudentClassSummary,
    StudentProfileSummary,
    StrategyChooseResponse,
    StrategyDecisionReview,
    StrategyLeaderboardRow,
    StrategyOffer,
    StrategyOfferReview,
    StrategyPublicState,
    StrategyResultResponse,
    StrategySessionReview,
    TeacherClassStudentRow,
    TeacherDayLog,
    TeacherOverviewResponse,
    TeacherRiskAlert,
    TeacherSessionSummary,
)


class FirestoreGameRepository:
    def __init__(self, _db: object | None = None) -> None:
        project_id = os.getenv("FIREBASE_PROJECT_ID") or None
        self.client = firestore.Client(project=project_id) if project_id else firestore.Client()

    # ---------- shared helpers ----------
    def _now(self) -> datetime:
        return datetime.utcnow()

    def _to_dt(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if hasattr(value, "to_datetime"):
            try:
                dt = value.to_datetime()
                if isinstance(dt, datetime):
                    return dt
            except Exception:
                pass
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except Exception:
                pass
        return self._now()

    def _safe_json(self, value: Any) -> str:
        try:
            return json.dumps(value)
        except Exception:
            return "{}"

    def _code(self, length: int) -> str:
        return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

    def _next_int(self, counter_name: str) -> int:
        ref = self.client.collection("_meta").document("counters")
        transaction = self.client.transaction()

        @firestore.transactional
        def _update(txn: firestore.Transaction) -> int:
            snap = ref.get(transaction=txn)
            data = snap.to_dict() if snap.exists else {}
            current = int(data.get(counter_name, 0)) + 1
            txn.set(ref, {counter_name: current}, merge=True)
            return current

        return int(_update(transaction))

    def _archive_entity(self, *, entity_type: str, entity_key: str, payload: dict) -> None:
        archive_id = self._next_int("deleted_entities")
        self.client.collection("deleted_entities").document(str(archive_id)).set(
            {
                "id": archive_id,
                "entity_type": entity_type,
                "entity_key": entity_key,
                "payload_json": self._safe_json(payload),
                "deleted_at": self._now(),
            }
        )

    def _audit(
        self,
        *,
        action: str,
        target_type: str,
        target_key: str,
        detail: dict | None = None,
        actor: str = "teacher",
    ) -> None:
        event_id = self._next_int("audit_events")
        self.client.collection("audit_events").document(str(event_id)).set(
            {
                "id": event_id,
                "actor": actor[:64],
                "action": action[:64],
                "target_type": target_type[:32],
                "target_key": target_key[:120],
                "detail_json": self._safe_json(detail or {}),
                "created_at": self._now(),
            }
        )

    def _unique_class_code(self) -> str:
        for _ in range(30):
            code = self._code(6)
            if not self.client.collection("classrooms").document(code).get().exists:
                return code
        raise RuntimeError("Unable to generate unique class code")

    def _unique_assignment_code(self) -> str:
        for _ in range(30):
            code = self._code(7)
            if not self.client.collection("assignments").document(code).get().exists:
                return code
        raise RuntimeError("Unable to generate unique assignment code")

    def _unique_student_id(self) -> str:
        for _ in range(30):
            sid = self._code(8)
            if not self.client.collection("students").document(sid).get().exists:
                return sid
        raise RuntimeError("Unable to generate unique student id")

    def _unique_strategy_session_id(self) -> str:
        for _ in range(30):
            sid = self._code(10)
            if not self.client.collection("strategy_sessions").document(sid).get().exists:
                return sid
        raise RuntimeError("Unable to generate unique strategy session id")

    def _get_doc(self, col: str, doc_id: str) -> dict | None:
        snap = self.client.collection(col).document(doc_id).get()
        if not snap.exists:
            return None
        return snap.to_dict() or {}

    def _list_docs(self, col: str) -> list[dict]:
        rows: list[dict] = []
        for doc in self.client.collection(col).stream():
            data = doc.to_dict() or {}
            rows.append(data)
        return rows

    # ---------- classroom / student ----------
    def create_classroom(self, class_name: str) -> ClassroomSummary:
        class_code = self._unique_class_code()
        created_at = self._now()
        row = {
            "class_code": class_code,
            "class_name": class_name.strip(),
            "created_at": created_at,
        }
        self.client.collection("classrooms").document(class_code).set(row)
        self._audit(action="create_classroom", target_type="classroom", target_key=class_code, detail={"class_name": class_name})
        return ClassroomSummary(
            class_code=class_code,
            class_name=row["class_name"],
            assignment_count=0,
            active_assignment_count=0,
            created_at=created_at,
        )

    def update_classroom(self, class_code: str, class_name: str) -> ClassroomSummary:
        code = class_code.upper()
        row = self._get_doc("classrooms", code)
        if row is None:
            raise ValueError("Class not found")
        self.client.collection("classrooms").document(code).set({"class_name": class_name.strip()}, merge=True)
        self._audit(action="update_classroom", target_type="classroom", target_key=code, detail={"class_name": class_name})
        assignments = [a for a in self._list_docs("assignments") if str(a.get("class_code", "")).upper() == code]
        return ClassroomSummary(
            class_code=code,
            class_name=class_name.strip(),
            assignment_count=len(assignments),
            active_assignment_count=sum(1 for a in assignments if bool(a.get("is_active", True))),
            created_at=self._to_dt(row.get("created_at")),
        )

    def delete_classroom(self, class_code: str) -> ActionResponse:
        code = class_code.upper()
        row = self._get_doc("classrooms", code)
        if row is None:
            raise ValueError("Class not found")
        assignments = [a for a in self._list_docs("assignments") if str(a.get("class_code", "")).upper() == code]
        payload = {"classroom": row, "assignments": assignments}
        self._archive_entity(entity_type="classroom", entity_key=code, payload=payload)
        self._audit(action="delete_classroom", target_type="classroom", target_key=code)
        for assignment in assignments:
            acode = str(assignment.get("assignment_code", "")).upper()
            if acode:
                self.client.collection("assignments").document(acode).delete()
        for membership in self._list_docs("memberships"):
            if str(membership.get("class_code", "")).upper() == code:
                doc_id = f"{code}_{str(membership.get('student_id', '')).upper()}"
                self.client.collection("memberships").document(doc_id).delete()
        self.client.collection("classrooms").document(code).delete()
        return ActionResponse(message=f"Class {code} deleted")

    def list_classrooms(self) -> list[ClassroomSummary]:
        classrooms = self._list_docs("classrooms")
        assignments = self._list_docs("assignments")
        out: list[ClassroomSummary] = []
        for row in classrooms:
            code = str(row.get("class_code", "")).upper()
            class_assignments = [a for a in assignments if str(a.get("class_code", "")).upper() == code]
            out.append(
                ClassroomSummary(
                    class_code=code,
                    class_name=str(row.get("class_name", "Class")),
                    assignment_count=len(class_assignments),
                    active_assignment_count=sum(1 for a in class_assignments if bool(a.get("is_active", True))),
                    created_at=self._to_dt(row.get("created_at")),
                )
            )
        out.sort(key=lambda x: x.created_at, reverse=True)
        return out

    def register_student(self, display_name: str) -> StudentProfileSummary:
        clean = display_name.strip() or "Student User"
        first, _, last = clean.partition(" ")
        last_name = last.strip() or "User"
        return self.register_student_with_identity(
            first_name=first.strip(),
            last_name=last_name,
            school_email=f"{clean.lower().replace(' ','.')}@student.local",
        )

    def register_student_with_identity(self, *, first_name: str, last_name: str, school_email: str) -> StudentProfileSummary:
        email = school_email.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Invalid school email format")
        students = self._list_docs("students")
        existing = next((s for s in students if str(s.get("school_email", "")).lower() == email), None)
        if existing:
            student_id = str(existing.get("student_id", "")).upper()
            self.client.collection("students").document(student_id).set(
                {
                    "first_name": first_name.strip(),
                    "last_name": last_name.strip(),
                    "display_name": f"{first_name.strip()} {last_name.strip()}".strip(),
                    "school_email": email,
                    "is_active": True,
                },
                merge=True,
            )
            self._audit(
                action="student_profile_login",
                target_type="student",
                target_key=student_id,
                detail={"school_email": email},
                actor="student",
            )
            created = self._to_dt(existing.get("created_at"))
            return StudentProfileSummary(
                student_id=student_id,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                school_email=email,
                is_active=True,
                created_at=created,
            )

        student_id = self._unique_student_id()
        created_at = self._now()
        row = {
            "student_id": student_id,
            "display_name": f"{first_name.strip()} {last_name.strip()}".strip(),
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "school_email": email,
            "is_active": True,
            "created_at": created_at,
        }
        self.client.collection("students").document(student_id).set(row)
        self._audit(
            action="register_student",
            target_type="student",
            target_key=student_id,
            detail={"school_email": email},
            actor="student",
        )
        return StudentProfileSummary(
            student_id=student_id,
            first_name=row["first_name"],
            last_name=row["last_name"],
            school_email=row["school_email"],
            is_active=True,
            created_at=created_at,
        )

    def get_student(self, student_id: str) -> dict | None:
        return self._get_doc("students", student_id.upper())

    def join_class(self, student_id: str, class_code: str) -> StudentClassSummary:
        student = self.get_student(student_id)
        if student is None:
            raise ValueError("Student profile not found")
        if not bool(student.get("is_active", True)):
            raise ValueError("Student profile is inactive")
        code = class_code.upper()
        classroom = self._get_doc("classrooms", code)
        if classroom is None:
            raise ValueError("Class not found")
        member_id = f"{code}_{student_id.upper()}"
        existing = self._get_doc("memberships", member_id)
        created_at = self._to_dt(existing.get("created_at")) if existing else self._now()
        self.client.collection("memberships").document(member_id).set(
            {
                "membership_id": member_id,
                "class_code": code,
                "student_id": student_id.upper(),
                "status": "active",
                "created_at": created_at,
            }
        )
        self._audit(
            action="join_class",
            target_type="classroom",
            target_key=code,
            detail={"student_id": student_id.upper()},
            actor="student",
        )
        return StudentClassSummary(
            class_code=code,
            class_name=str(classroom.get("class_name", "Class")),
            status="active",
            joined_at=created_at,
        )

    def student_classes(self, student_id: str) -> list[StudentClassSummary]:
        sid = student_id.upper()
        student = self.get_student(sid)
        if student is None:
            raise ValueError("Student profile not found")
        memberships = [m for m in self._list_docs("memberships") if str(m.get("student_id", "")).upper() == sid]
        out: list[StudentClassSummary] = []
        for row in memberships:
            code = str(row.get("class_code", "")).upper()
            classroom = self._get_doc("classrooms", code)
            if classroom is None:
                continue
            out.append(
                StudentClassSummary(
                    class_code=code,
                    class_name=str(classroom.get("class_name", "Class")),
                    status=str(row.get("status", "active")),
                    joined_at=self._to_dt(row.get("created_at")),
                )
            )
        out.sort(key=lambda x: x.joined_at, reverse=True)
        return out

    def _student_is_member_of_class(self, *, student_id: str, class_code: str) -> bool:
        student = self.get_student(student_id)
        if student is None or not bool(student.get("is_active", True)):
            return False
        membership = self._get_doc("memberships", f"{class_code.upper()}_{student_id.upper()}")
        return membership is not None and str(membership.get("status", "inactive")) == "active"

    def class_students(self, class_code: str) -> list[TeacherClassStudentRow]:
        code = class_code.upper()
        classroom = self._get_doc("classrooms", code)
        if classroom is None:
            raise ValueError("Class not found")
        members = [m for m in self._list_docs("memberships") if str(m.get("class_code", "")).upper() == code]
        out: list[TeacherClassStudentRow] = []
        for m in members:
            sid = str(m.get("student_id", "")).upper()
            student = self.get_student(sid)
            if student is None:
                continue
            out.append(
                TeacherClassStudentRow(
                    student_id=sid,
                    first_name=str(student.get("first_name", "Student")),
                    last_name=str(student.get("last_name", "User")),
                    school_email=str(student.get("school_email", "")),
                    status=str(m.get("status", "active")),
                    joined_at=self._to_dt(m.get("created_at")),
                )
            )
        out.sort(key=lambda x: x.joined_at, reverse=True)
        return out

    def set_student_class_membership_status(self, class_code: str, student_id: str, status: str) -> ActionResponse:
        code = class_code.upper()
        sid = student_id.upper()
        membership_id = f"{code}_{sid}"
        membership = self._get_doc("memberships", membership_id)
        if membership is None:
            raise ValueError("Student is not a member of this class")
        self.client.collection("memberships").document(membership_id).set({"status": status}, merge=True)
        self._audit(
            action="set_student_membership_status",
            target_type="classroom",
            target_key=code,
            detail={"student_id": sid, "status": status},
        )
        return ActionResponse(message=f"Student {sid} marked {status} in class {code}")

    def remove_student_from_class(self, class_code: str, student_id: str) -> ActionResponse:
        code = class_code.upper()
        sid = student_id.upper()
        membership_id = f"{code}_{sid}"
        membership = self._get_doc("memberships", membership_id)
        if membership is None:
            raise ValueError("Student is not a member of this class")
        self.client.collection("memberships").document(membership_id).delete()
        self._audit(
            action="remove_student_from_class",
            target_type="classroom",
            target_key=code,
            detail={"student_id": sid},
        )
        return ActionResponse(message=f"Student {sid} deleted from class {code}")

    # ---------- assignments ----------
    def create_assignment(
        self,
        class_code: str,
        title: str,
        city: str,
        start_cash: float,
        duration_days: int,
        sprint_minutes_per_day: int,
    ) -> AssignmentSummary:
        code = class_code.upper()
        classroom = self._get_doc("classrooms", code)
        if classroom is None:
            raise ValueError("Class code not found")
        assignment_code = self._unique_assignment_code()
        created_at = self._now()
        row = {
            "assignment_code": assignment_code,
            "class_code": code,
            "title": title.strip(),
            "city": city.strip(),
            "start_cash": float(start_cash),
            "duration_days": int(duration_days),
            "sprint_minutes_per_day": int(sprint_minutes_per_day),
            "is_active": True,
            "created_at": created_at,
        }
        self.client.collection("assignments").document(assignment_code).set(row)
        self._audit(
            action="create_assignment",
            target_type="assignment",
            target_key=assignment_code,
            detail={"class_code": code, "title": title, "sprint_minutes_per_day": sprint_minutes_per_day},
        )
        return AssignmentSummary(
            assignment_code=assignment_code,
            class_code=code,
            title=row["title"],
            city=row["city"],
            start_cash=row["start_cash"],
            duration_days=row["duration_days"],
            sprint_minutes_per_day=row["sprint_minutes_per_day"],
            is_active=True,
            enrolled_sessions=0,
            created_at=created_at,
        )

    def update_assignment(
        self,
        assignment_code: str,
        *,
        title: str | None,
        city: str | None,
        start_cash: float | None,
        duration_days: int | None,
        sprint_minutes_per_day: int | None,
        is_active: bool | None,
    ) -> AssignmentSummary:
        code = assignment_code.upper()
        existing = self._get_doc("assignments", code)
        if existing is None:
            raise ValueError("Assignment not found")
        patch: dict[str, Any] = {}
        if title is not None:
            patch["title"] = title.strip()
        if city is not None:
            patch["city"] = city.strip()
        if start_cash is not None:
            patch["start_cash"] = float(start_cash)
        if duration_days is not None:
            patch["duration_days"] = int(duration_days)
        if sprint_minutes_per_day is not None:
            patch["sprint_minutes_per_day"] = int(sprint_minutes_per_day)
        if is_active is not None:
            patch["is_active"] = bool(is_active)
        if patch:
            self.client.collection("assignments").document(code).set(patch, merge=True)
        row = self._get_doc("assignments", code) or {}
        self._audit(
            action="update_assignment",
            target_type="assignment",
            target_key=code,
            detail=row,
        )
        enrolled = len([s for s in self._list_docs("game_sessions") if str(s.get("assignment_code", "")).upper() == code])
        return AssignmentSummary(
            assignment_code=code,
            class_code=str(row.get("class_code", "")).upper(),
            title=str(row.get("title", "Assignment")),
            city=str(row.get("city", "Charlotte, NC")),
            start_cash=float(row.get("start_cash", 1800.0)),
            duration_days=int(row.get("duration_days", 30)),
            sprint_minutes_per_day=int(row.get("sprint_minutes_per_day", 2)),
            is_active=bool(row.get("is_active", True)),
            enrolled_sessions=enrolled,
            created_at=self._to_dt(row.get("created_at")),
        )

    def delete_assignment(self, assignment_code: str) -> ActionResponse:
        code = assignment_code.upper()
        row = self._get_doc("assignments", code)
        if row is None:
            raise ValueError("Assignment not found")
        payload = {"assignment": row, "class_code": row.get("class_code")}
        self._archive_entity(entity_type="assignment", entity_key=code, payload=payload)
        self._audit(action="delete_assignment", target_type="assignment", target_key=code)
        self.client.collection("assignments").document(code).delete()
        return ActionResponse(message=f"Assignment {code} deleted")

    def list_assignments(self, class_code: str | None = None) -> list[AssignmentSummary]:
        rows = self._list_docs("assignments")
        out: list[AssignmentSummary] = []
        for row in rows:
            code = str(row.get("assignment_code", "")).upper()
            ccode = str(row.get("class_code", "")).upper()
            if class_code and ccode != class_code.upper():
                continue
            enrolled = len([s for s in self._list_docs("game_sessions") if str(s.get("assignment_code", "")).upper() == code])
            out.append(
                AssignmentSummary(
                    assignment_code=code,
                    class_code=ccode,
                    title=str(row.get("title", "Assignment")),
                    city=str(row.get("city", "Charlotte, NC")),
                    start_cash=float(row.get("start_cash", 1800.0)),
                    duration_days=int(row.get("duration_days", 30)),
                    sprint_minutes_per_day=int(row.get("sprint_minutes_per_day", 2)),
                    is_active=bool(row.get("is_active", True)),
                    enrolled_sessions=enrolled,
                    created_at=self._to_dt(row.get("created_at")),
                )
            )
        out.sort(key=lambda x: x.created_at, reverse=True)
        return out

    def student_class_assignments(self, student_id: str, class_code: str) -> StudentClassAssignmentsResponse:
        sid = student_id.upper()
        code = class_code.upper()
        if not self._student_is_member_of_class(student_id=sid, class_code=code):
            raise ValueError("Student is not a member of this class")
        classroom = self._get_doc("classrooms", code)
        if classroom is None:
            raise ValueError("Class not found")
        rows = [
            row
            for row in self._list_docs("assignments")
            if str(row.get("class_code", "")).upper() == code and bool(row.get("is_active", True))
        ]
        rows.sort(key=lambda x: self._to_dt(x.get("created_at")), reverse=True)
        return StudentClassAssignmentsResponse(
            class_code=code,
            class_name=str(classroom.get("class_name", "Class")),
            assignments=[
                StudentAssignmentOption(
                    assignment_code=str(r.get("assignment_code", "")).upper(),
                    title=str(r.get("title", "Assignment")),
                    city=str(r.get("city", "Charlotte, NC")),
                    start_cash=float(r.get("start_cash", 1800.0)),
                    duration_days=int(r.get("duration_days", 30)),
                    sprint_minutes_per_day=int(r.get("sprint_minutes_per_day", 2)),
                )
                for r in rows
            ],
        )

    def assignment_rubric(self, assignment_code: str, limit: int = 200) -> list[AssignmentRubricRow]:
        acode = assignment_code.upper()
        sessions = [s for s in self._list_docs("game_sessions") if str(s.get("assignment_code", "")).upper() == acode]
        sessions.sort(key=lambda x: (int(x.get("score", 0)), self._to_dt(x.get("updated_at"))), reverse=True)
        rows = sessions[:limit]
        out: list[AssignmentRubricRow] = []
        for row in rows:
            score = int(row.get("score", 0))
            out.append(
                AssignmentRubricRow(
                    session_id=str(row.get("session_id", "")),
                    player_name=str(row.get("player_name", "Student")),
                    day=int(row.get("day", 1)),
                    cash=round(float(row.get("cash", 0.0)), 2),
                    debt=round(float(row.get("debt", 0.0)), 2),
                    stress=int(row.get("stress", 20)),
                    score=score,
                    letter_grade=self._grade_letter(score),
                    performance_band=self._performance_band(score),
                    status=str(row.get("status", "active")),
                    updated_at=self._to_dt(row.get("updated_at")),
                )
            )
        return out

    def _assignment_by_codes(self, class_code: str, assignment_code: str) -> dict | None:
        row = self._get_doc("assignments", assignment_code.upper())
        if row is None:
            return None
        if str(row.get("class_code", "")).upper() != class_code.upper():
            return None
        if not bool(row.get("is_active", True)):
            return None
        return row

    # ---------- game sessions ----------
    def create_session(
        self,
        state: GameState,
        class_code: str | None = None,
        assignment_code: str | None = None,
        student_id: str | None = None,
    ) -> None:
        now = self._now()
        row = {
            "session_id": state.session_id,
            "student_id": student_id.upper() if student_id else None,
            "player_name": state.player_name,
            "city": state.city,
            "day": state.day,
            "cash": state.cash,
            "tax_reserve": state.tax_reserve,
            "debt": state.debt,
            "stress": state.stress,
            "status": state.status,
            "score": 0,
            "class_code": class_code.upper() if class_code else None,
            "assignment_code": assignment_code.upper() if assignment_code else None,
            "created_at": now,
            "updated_at": now,
        }
        self.client.collection("game_sessions").document(state.session_id).set(row)
        self._audit(
            action="create_session",
            target_type="session",
            target_key=state.session_id,
            detail={"player_name": state.player_name, "city": state.city},
        )

    def create_session_from_assignment(
        self,
        student_id: str,
        player_name: str,
        class_code: str,
        assignment_code: str,
        session_id: str,
    ) -> GameState:
        if not self._student_is_member_of_class(student_id=student_id, class_code=class_code):
            raise ValueError("Student is not a member of this class")
        assignment = self._assignment_by_codes(class_code=class_code, assignment_code=assignment_code)
        if assignment is None:
            raise ValueError("Assignment not found or inactive")
        state = GameState(
            session_id=session_id,
            player_name=player_name,
            city=str(assignment.get("city", "Charlotte, NC")),
            cash=float(assignment.get("start_cash", 1800.0)),
            duration_days=int(assignment.get("duration_days", 30)),
            class_code=class_code.upper(),
            assignment_code=assignment_code.upper(),
        )
        self.create_session(
            state=state,
            class_code=class_code,
            assignment_code=assignment_code,
            student_id=student_id,
        )
        return state

    def get_state(self, session_id: str) -> GameState | None:
        row = self._get_doc("game_sessions", session_id)
        if row is None:
            return None
        duration_days = 30
        assignment_code = str(row.get("assignment_code", "")).upper() or None
        if assignment_code:
            assignment = self._get_doc("assignments", assignment_code)
            if assignment:
                duration_days = int(assignment.get("duration_days", 30))
        return GameState(
            session_id=str(row.get("session_id", session_id)),
            player_name=str(row.get("player_name", "Student")),
            city=str(row.get("city", "Charlotte, NC")),
            day=int(row.get("day", 1)),
            cash=float(row.get("cash", 0.0)),
            tax_reserve=float(row.get("tax_reserve", 0.0)),
            debt=float(row.get("debt", 0.0)),
            stress=int(row.get("stress", 20)),
            status=str(row.get("status", "active")),
            duration_days=duration_days,
            class_code=str(row.get("class_code", "")).upper() or None,
            assignment_code=assignment_code,
        )

    def update_state_and_log(self, state: GameState, score: int, result: DailyResult) -> None:
        session_ref = self.client.collection("game_sessions").document(state.session_id)
        session_ref.set(
            {
                "day": state.day,
                "cash": state.cash,
                "tax_reserve": state.tax_reserve,
                "debt": state.debt,
                "stress": state.stress,
                "status": state.status,
                "score": int(score),
                "updated_at": self._now(),
            },
            merge=True,
        )
        session_ref.collection("logs").document(f"{result.day}-{int(datetime.utcnow().timestamp() * 1000)}").set(
            {
                "day": result.day,
                "gross_income": result.gross_income,
                "platform_fees": result.platform_fees,
                "variable_costs": result.variable_costs,
                "household_costs": result.household_costs,
                "tax_reserve": result.tax_reserve,
                "event_title": result.event_title,
                "event_text": result.event_text,
                "event_cash_impact": result.event_cash_impact,
                "end_cash": result.end_cash,
                "created_at": self._now(),
            }
        )

    def turn_in_assignment(self, *, session_id: str, student_id: str) -> ActionResponse:
        row = self._get_doc("game_sessions", session_id)
        if row is None:
            raise ValueError("Session not found")
        if str(row.get("student_id", "")).upper() != student_id.upper():
            raise ValueError("Session does not belong to this student")
        assignment_code = str(row.get("assignment_code", "")).upper()
        class_code = str(row.get("class_code", "")).upper()
        if not assignment_code or not class_code:
            raise ValueError("Session is not linked to a class assignment")
        if str(row.get("status", "active")) == "completed":
            return ActionResponse(message=f"Assignment {assignment_code} already turned in")
        self.client.collection("game_sessions").document(session_id).set(
            {"status": "completed", "updated_at": self._now()}, merge=True
        )
        self._audit(
            action="turn_in_assignment",
            target_type="assignment",
            target_key=assignment_code,
            detail={"session_id": session_id, "student_id": student_id.upper(), "class_code": class_code},
            actor="student",
        )
        return ActionResponse(message=f"Turned in assignment {assignment_code} for class {class_code}")

    def teacher_overview(self) -> TeacherOverviewResponse:
        rows = self._list_docs("game_sessions")
        total = len(rows)
        active = sum(1 for r in rows if str(r.get("status", "active")) == "active")
        completed = sum(1 for r in rows if str(r.get("status", "")) == "completed")
        failed = sum(1 for r in rows if str(r.get("status", "")) == "failed")
        avg_score = round(sum(float(r.get("score", 0)) for r in rows) / total, 2) if total else 0.0
        return TeacherOverviewResponse(
            total_sessions=total,
            active_sessions=active,
            completed_sessions=completed,
            failed_sessions=failed,
            avg_score=avg_score,
        )

    def teacher_sessions(
        self,
        limit: int = 50,
        class_code: str | None = None,
        assignment_code: str | None = None,
    ) -> list[TeacherSessionSummary]:
        rows = self._list_docs("game_sessions")
        out: list[TeacherSessionSummary] = []
        for row in rows:
            ccode = str(row.get("class_code", "")).upper() or None
            acode = str(row.get("assignment_code", "")).upper() or None
            if class_code and ccode != class_code.upper():
                continue
            if assignment_code and acode != assignment_code.upper():
                continue
            out.append(
                TeacherSessionSummary(
                    session_id=str(row.get("session_id", "")),
                    player_name=str(row.get("player_name", "Student")),
                    city=str(row.get("city", "Charlotte, NC")),
                    status=str(row.get("status", "active")),
                    day=int(row.get("day", 1)),
                    cash=round(float(row.get("cash", 0.0)), 2),
                    stress=int(row.get("stress", 20)),
                    score=int(row.get("score", 0)),
                    class_code=ccode,
                    assignment_code=acode,
                    updated_at=self._to_dt(row.get("updated_at")),
                )
            )
        out.sort(key=lambda x: x.updated_at, reverse=True)
        return out[:limit]

    def teacher_session_logs(self, session_id: str, limit: int = 30) -> list[TeacherDayLog]:
        ref = self.client.collection("game_sessions").document(session_id).collection("logs")
        rows: list[dict] = [doc.to_dict() or {} for doc in ref.stream()]
        rows.sort(key=lambda x: self._to_dt(x.get("created_at")), reverse=True)
        rows = rows[:limit]
        return [
            TeacherDayLog(
                day=int(r.get("day", 1)),
                gross_income=float(r.get("gross_income", 0.0)),
                platform_fees=float(r.get("platform_fees", 0.0)),
                variable_costs=float(r.get("variable_costs", 0.0)),
                household_costs=float(r.get("household_costs", 0.0)),
                tax_reserve=float(r.get("tax_reserve", 0.0)),
                event_title=str(r.get("event_title", "")),
                event_text=str(r.get("event_text", "")),
                event_cash_impact=float(r.get("event_cash_impact", 0.0)),
                end_cash=float(r.get("end_cash", 0.0)),
                created_at=self._to_dt(r.get("created_at")),
            )
            for r in rows
        ]

    def update_teacher_session(
        self,
        session_id: str,
        *,
        player_name: str | None,
        city: str | None,
        status: str | None,
        day: int | None,
        cash: float | None,
        tax_reserve: float | None,
        debt: float | None,
        stress: int | None,
        score: int | None,
    ) -> TeacherSessionSummary:
        row = self._get_doc("game_sessions", session_id)
        if row is None:
            raise ValueError("Session not found")
        patch: dict[str, Any] = {"updated_at": self._now()}
        if player_name is not None:
            patch["player_name"] = player_name.strip()
        if city is not None:
            patch["city"] = city.strip()
        if status is not None:
            patch["status"] = status
        if day is not None:
            patch["day"] = int(day)
        if cash is not None:
            patch["cash"] = float(cash)
        if tax_reserve is not None:
            patch["tax_reserve"] = float(tax_reserve)
        if debt is not None:
            patch["debt"] = float(debt)
        if stress is not None:
            patch["stress"] = int(stress)
        if score is not None:
            patch["score"] = int(score)
        self.client.collection("game_sessions").document(session_id).set(patch, merge=True)
        merged = {**row, **patch}
        self._audit(action="update_session", target_type="session", target_key=session_id, detail=merged)
        return TeacherSessionSummary(
            session_id=session_id,
            player_name=str(merged.get("player_name", "Student")),
            city=str(merged.get("city", "Charlotte, NC")),
            status=str(merged.get("status", "active")),
            day=int(merged.get("day", 1)),
            cash=round(float(merged.get("cash", 0.0)), 2),
            stress=int(merged.get("stress", 20)),
            score=int(merged.get("score", 0)),
            class_code=str(merged.get("class_code", "")).upper() or None,
            assignment_code=str(merged.get("assignment_code", "")).upper() or None,
            updated_at=self._to_dt(merged.get("updated_at")),
        )

    def delete_teacher_session(self, session_id: str) -> ActionResponse:
        row = self._get_doc("game_sessions", session_id)
        if row is None:
            raise ValueError("Session not found")
        logs = [doc.to_dict() or {} for doc in self.client.collection("game_sessions").document(session_id).collection("logs").stream()]
        payload = {
            "session": row,
            "logs": logs,
            "enrollment": {
                "class_code": row.get("class_code"),
                "assignment_code": row.get("assignment_code"),
            }
            if row.get("class_code") and row.get("assignment_code")
            else None,
        }
        self._archive_entity(entity_type="session", entity_key=session_id, payload=payload)
        self._audit(action="delete_session", target_type="session", target_key=session_id)
        log_ref = self.client.collection("game_sessions").document(session_id).collection("logs")
        for doc in log_ref.stream():
            doc.reference.delete()
        self.client.collection("game_sessions").document(session_id).delete()
        return ActionResponse(message=f"Session {session_id} deleted")

    def remove_session_from_class(self, session_id: str) -> ActionResponse:
        row = self._get_doc("game_sessions", session_id)
        if row is None:
            raise ValueError("Session not found")
        if not row.get("class_code") or not row.get("assignment_code"):
            raise ValueError("Session is not enrolled in a class assignment")
        self.client.collection("game_sessions").document(session_id).set(
            {"class_code": None, "assignment_code": None, "updated_at": self._now()},
            merge=True,
        )
        self._audit(action="remove_session_enrollment", target_type="session", target_key=session_id)
        return ActionResponse(message=f"Session {session_id} removed from class assignment")

    # ---------- scoring helpers ----------
    def _grade_letter(self, score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def _performance_band(self, score: int) -> str:
        if score >= 90:
            return "Outstanding financial management"
        if score >= 80:
            return "Strong and consistent decisions"
        if score >= 70:
            return "Meets expectations with moderate risk"
        if score >= 60:
            return "At-risk budgeting and planning"
        return "Needs intervention and support"

    # ---------- strategy ----------
    def create_strategy_session(
        self,
        *,
        player_name: str,
        total_days: int,
        assignment_minutes: int,
        offers: list[dict],
        day_brief: str,
        student_id: str | None = None,
        class_code: str | None = None,
        assignment_code: str | None = None,
        is_class_assignment: bool = False,
    ) -> StrategyPublicState:
        session_id = self._unique_strategy_session_id()
        now = self._now()
        row = {
            "session_id": session_id,
            "student_id": student_id.upper() if student_id else None,
            "class_code": class_code.upper() if class_code else None,
            "assignment_code": assignment_code.upper() if assignment_code else None,
            "is_class_assignment": bool(is_class_assignment),
            "player_name": player_name.strip() or "Student",
            "current_day": 1,
            "total_days": int(total_days),
            "assignment_minutes": int(assignment_minutes),
            "status": "active",
            "total_profit": 0.0,
            "optimal_profit": 0.0,
            "selected_count": 0,
            "current_offers": offers,
            "current_day_brief": day_brief[:255],
            "turned_in_at": None,
            "created_at": now,
            "updated_at": now,
        }
        self.client.collection("strategy_sessions").document(session_id).set(row)
        self._audit(
            action="create_strategy_session",
            target_type="strategy_session",
            target_key=session_id,
            detail={
                "player_name": row["player_name"],
                "total_days": row["total_days"],
                "class_code": row["class_code"],
                "assignment_code": row["assignment_code"],
                "is_class_assignment": row["is_class_assignment"],
            },
        )
        return self._strategy_public_state(row)

    def create_strategy_session_from_assignment(
        self,
        *,
        student_id: str,
        player_name: str,
        class_code: str,
        assignment_code: str,
        offers: list[dict],
        day_brief: str,
    ) -> StrategyPublicState:
        if not self._student_is_member_of_class(student_id=student_id, class_code=class_code):
            raise ValueError("Student is not a member of this class")
        assignment = self._assignment_by_codes(class_code=class_code, assignment_code=assignment_code)
        if assignment is None:
            raise ValueError("Assignment not found or inactive")
        assignment_minutes = max(20, min(1200, int(assignment.get("sprint_minutes_per_day", 2)) * 30))
        return self.create_strategy_session(
            player_name=player_name,
            total_days=30,
            assignment_minutes=assignment_minutes,
            offers=offers,
            day_brief=day_brief,
            student_id=student_id,
            class_code=class_code,
            assignment_code=assignment_code,
            is_class_assignment=True,
        )

    def get_strategy_state(self, session_id: str) -> StrategyPublicState | None:
        row = self._get_doc("strategy_sessions", session_id)
        if row is None:
            return None
        return self._strategy_public_state(row)

    def list_strategy_recent_channels(self, session_id: str, limit: int = 6) -> list[str]:
        decisions = [doc.to_dict() or {} for doc in self.client.collection("strategy_sessions").document(session_id).collection("decisions").stream()]
        decisions.sort(key=lambda x: (int(x.get("day", 0)), self._to_dt(x.get("created_at"))), reverse=True)
        decisions = decisions[:limit]
        channels: list[str] = []
        for d in reversed(decisions):
            offers = d.get("offers") or []
            chosen = str(d.get("chosen_offer_id", ""))
            for offer in offers:
                if str(offer.get("offer_id", "")) == chosen and offer.get("channel"):
                    channels.append(str(offer.get("channel")))
                    break
        return channels

    def choose_strategy_offer(
        self,
        *,
        session_id: str,
        offer_id: str,
        next_offers: list[dict] | None,
        next_day_brief: str | None,
    ) -> StrategyChooseResponse:
        row = self._get_doc("strategy_sessions", session_id)
        if row is None:
            raise ValueError("Strategy session not found")
        if str(row.get("status", "active")) != "active":
            raise ValueError("Strategy session already completed")

        offers = row.get("current_offers") or []
        if not isinstance(offers, list) or not offers:
            raise ValueError("No offers available to choose")
        selected = next((o for o in offers if str(o.get("offer_id", "")) == offer_id), None)
        if selected is None:
            raise ValueError("Selected offer not found for current day")

        optimal = max(float(o.get("expected_profit", -10_000)) for o in offers)
        chosen_profit = float(selected.get("expected_profit", 0.0))
        chosen_title = str(selected.get("title", "Selected Offer"))[:160]

        next_day = int(row.get("current_day", 1))
        decision_payload = {
            "day": next_day,
            "chosen_offer_id": str(selected.get("offer_id", "")),
            "chosen_offer_title": chosen_title,
            "chosen_profit": chosen_profit,
            "optimal_profit": optimal,
            "offers": offers,
            "day_brief": str(row.get("current_day_brief", ""))[:255],
            "created_at": self._now(),
        }
        self.client.collection("strategy_sessions").document(session_id).collection("decisions").add(decision_payload)

        total_days = int(row.get("total_days", 30))
        patch: dict[str, Any] = {
            "total_profit": float(row.get("total_profit", 0.0)) + chosen_profit,
            "optimal_profit": float(row.get("optimal_profit", 0.0)) + optimal,
            "selected_count": int(row.get("selected_count", 0)) + 1,
            "updated_at": self._now(),
        }
        if next_day >= total_days:
            patch["status"] = "completed"
            patch["current_offers"] = []
            patch["current_day_brief"] = "Assignment completed."
        else:
            patch["current_day"] = next_day + 1
            patch["current_offers"] = next_offers or []
            patch["current_day_brief"] = (next_day_brief or f"Day {next_day + 1} opportunities loaded.")[:255]
        self.client.collection("strategy_sessions").document(session_id).set(patch, merge=True)
        updated = {**row, **patch}
        return StrategyChooseResponse(
            state=self._strategy_public_state(updated),
            chosen_offer_title=chosen_title,
            chosen_profit=round(chosen_profit, 2),
            running_profit=round(float(updated.get("total_profit", 0.0)), 2),
        )

    def turn_in_strategy_assignment(self, *, session_id: str, student_id: str) -> ActionResponse:
        row = self._get_doc("strategy_sessions", session_id)
        if row is None:
            raise ValueError("Sprint session not found")
        if not bool(row.get("is_class_assignment", False)):
            raise ValueError("Sprint session is not linked to a class assignment")
        if str(row.get("student_id", "")).upper() != student_id.upper():
            raise ValueError("Sprint session does not belong to this student")
        if row.get("turned_in_at") is not None:
            return ActionResponse(message=f"Assignment {row.get('assignment_code', '-') or '-'} already turned in")
        self.client.collection("strategy_sessions").document(session_id).set(
            {
                "status": "completed",
                "current_offers": [],
                "current_day_brief": "Assignment turned in.",
                "turned_in_at": self._now(),
                "updated_at": self._now(),
            },
            merge=True,
        )
        self._audit(
            action="turn_in_strategy_assignment",
            target_type="assignment",
            target_key=str(row.get("assignment_code", session_id)),
            detail={"session_id": session_id, "student_id": student_id.upper(), "class_code": row.get("class_code")},
            actor="student",
        )
        return ActionResponse(
            message=f"Turned in sprint assignment {row.get('assignment_code', '-') or '-'} for class {row.get('class_code', '-') or '-'}"
        )

    def strategy_result(self, session_id: str) -> StrategyResultResponse | None:
        row = self._get_doc("strategy_sessions", session_id)
        if row is None:
            return None
        denom = float(row.get("optimal_profit", 0.0)) if float(row.get("optimal_profit", 0.0)) > 0 else 1.0
        pct = max(0.0, min(100.0, (float(row.get("total_profit", 0.0)) / denom) * 100))
        return StrategyResultResponse(
            session_id=str(row.get("session_id", session_id)),
            player_name=str(row.get("player_name", "Student")),
            total_days=int(row.get("total_days", 30)),
            student_profit=round(float(row.get("total_profit", 0.0)), 2),
            optimal_profit=round(float(row.get("optimal_profit", 0.0)), 2),
            success_percentage=round(pct, 2),
            status=str(row.get("status", "active")),
        )

    def strategy_leaderboard(self, limit: int = 50) -> list[StrategyLeaderboardRow]:
        rows = self._list_docs("strategy_sessions")
        out: list[StrategyLeaderboardRow] = []
        for row in rows:
            denom = float(row.get("optimal_profit", 0.0)) if float(row.get("optimal_profit", 0.0)) > 0 else 1.0
            pct = max(0.0, min(100.0, (float(row.get("total_profit", 0.0)) / denom) * 100))
            out.append(
                StrategyLeaderboardRow(
                    session_id=str(row.get("session_id", "")),
                    player_name=str(row.get("player_name", "Student")),
                    current_day=int(row.get("current_day", 1)),
                    total_days=int(row.get("total_days", 30)),
                    total_profit=round(float(row.get("total_profit", 0.0)), 2),
                    optimal_profit=round(float(row.get("optimal_profit", 0.0)), 2),
                    success_percentage=round(pct, 2),
                    status=str(row.get("status", "active")),
                    updated_at=self._to_dt(row.get("updated_at")),
                )
            )
        out.sort(key=lambda x: (x.status != "completed", -x.success_percentage, -x.total_profit))
        return out[:limit]

    def strategy_session_review(self, session_id: str) -> StrategySessionReview | None:
        row = self._get_doc("strategy_sessions", session_id)
        if row is None:
            return None
        decisions_rows = [doc.to_dict() or {} for doc in self.client.collection("strategy_sessions").document(session_id).collection("decisions").stream()]
        decisions_rows.sort(key=lambda d: (int(d.get("day", 0)), self._to_dt(d.get("created_at"))))
        decisions: list[StrategyDecisionReview] = []
        for idx, dec in enumerate(decisions_rows, start=1):
            offers: list[StrategyOfferReview] = []
            for offer in dec.get("offers") or []:
                risk = str(offer.get("risk", "medium")).lower()
                if risk not in {"low", "medium", "high"}:
                    risk = "medium"
                offers.append(
                    StrategyOfferReview(
                        offer_id=str(offer.get("offer_id", "")),
                        title=str(offer.get("title", "Opportunity"))[:160],
                        channel=str(offer.get("channel", "Other"))[:80],
                        cash_in=float(offer.get("cash_in", 0.0)),
                        cash_out=float(offer.get("cash_out", 0.0)),
                        expected_profit=float(offer.get("expected_profit", 0.0)),
                        risk=risk,
                    )
                )
            decisions.append(
                StrategyDecisionReview(
                    id=idx,
                    day=int(dec.get("day", 1)),
                    chosen_offer_id=str(dec.get("chosen_offer_id", "")),
                    chosen_offer_title=str(dec.get("chosen_offer_title", "Selected Offer"))[:160],
                    chosen_profit=round(float(dec.get("chosen_profit", 0.0)), 2),
                    optimal_profit=round(float(dec.get("optimal_profit", 0.0)), 2),
                    gap_to_optimal=round(float(dec.get("optimal_profit", 0.0)) - float(dec.get("chosen_profit", 0.0)), 2),
                    day_brief=str(dec.get("day_brief", ""))[:255],
                    offers=offers,
                    created_at=self._to_dt(dec.get("created_at")),
                )
            )
        denom = float(row.get("optimal_profit", 0.0)) if float(row.get("optimal_profit", 0.0)) > 0 else 1.0
        pct = max(0.0, min(100.0, (float(row.get("total_profit", 0.0)) / denom) * 100))
        return StrategySessionReview(
            session_id=str(row.get("session_id", session_id)),
            player_name=str(row.get("player_name", "Student")),
            current_day=int(row.get("current_day", 1)),
            total_days=int(row.get("total_days", 30)),
            assignment_minutes=int(row.get("assignment_minutes", 60)),
            status=str(row.get("status", "active")),
            total_profit=round(float(row.get("total_profit", 0.0)), 2),
            optimal_profit=round(float(row.get("optimal_profit", 0.0)), 2),
            success_percentage=round(pct, 2),
            selected_count=int(row.get("selected_count", 0)),
            created_at=self._to_dt(row.get("created_at")),
            updated_at=self._to_dt(row.get("updated_at")),
            decisions=decisions,
        )

    def delete_strategy_session(self, session_id: str) -> ActionResponse:
        row = self._get_doc("strategy_sessions", session_id)
        if row is None:
            raise ValueError("Strategy session not found")
        decisions = [doc.to_dict() or {} for doc in self.client.collection("strategy_sessions").document(session_id).collection("decisions").stream()]
        payload = {"strategy_session": row, "decisions": decisions}
        self._archive_entity(entity_type="strategy_session", entity_key=session_id, payload=payload)
        self._audit(action="delete_strategy_session", target_type="strategy_session", target_key=session_id)
        dec_ref = self.client.collection("strategy_sessions").document(session_id).collection("decisions")
        for doc in dec_ref.stream():
            doc.reference.delete()
        self.client.collection("strategy_sessions").document(session_id).delete()
        return ActionResponse(message=f"Strategy session {session_id} deleted")

    # ---------- trash / audit / risk ----------
    def list_deleted_entities(
        self,
        *,
        limit: int = 200,
        entity_type: str | None = None,
        since_days: int | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[DeletedEntitySummary]:
        rows = self._list_docs("deleted_entities")
        out: list[DeletedEntitySummary] = []
        for row in rows:
            etype = str(row.get("entity_type", "")).lower()
            deleted_at = self._to_dt(row.get("deleted_at"))
            if entity_type and etype != entity_type.strip().lower():
                continue
            if since_days is not None and since_days > 0 and deleted_at < self._now() - timedelta(days=since_days):
                continue
            if from_date is not None and deleted_at < from_date:
                continue
            if to_date is not None and deleted_at > to_date:
                continue
            out.append(
                DeletedEntitySummary(
                    id=int(row.get("id", 0)),
                    entity_type=etype,
                    entity_key=str(row.get("entity_key", "")),
                    deleted_at=deleted_at,
                )
            )
        out.sort(key=lambda x: (x.deleted_at, x.id), reverse=True)
        return out[:limit]

    def list_audit_events(
        self,
        *,
        limit: int = 300,
        action: str | None = None,
        target_type: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[AuditEventSummary]:
        rows = self._list_docs("audit_events")
        out: list[AuditEventSummary] = []
        for row in rows:
            created_at = self._to_dt(row.get("created_at"))
            act = str(row.get("action", "")).lower()
            ttype = str(row.get("target_type", "")).lower()
            if action and act != action.strip().lower():
                continue
            if target_type and ttype != target_type.strip().lower():
                continue
            if from_date is not None and created_at < from_date:
                continue
            if to_date is not None and created_at > to_date:
                continue
            out.append(
                AuditEventSummary(
                    id=int(row.get("id", 0)),
                    actor=str(row.get("actor", "teacher")),
                    action=act,
                    target_type=ttype,
                    target_key=str(row.get("target_key", "")),
                    created_at=created_at,
                )
            )
        out.sort(key=lambda x: (x.created_at, x.id), reverse=True)
        return out[:limit]

    def teacher_risk_alerts(
        self,
        *,
        limit: int = 100,
        class_code: str | None = None,
        assignment_code: str | None = None,
    ) -> list[TeacherRiskAlert]:
        rows = self._list_docs("game_sessions")
        alerts: list[TeacherRiskAlert] = []
        for row in rows:
            ccode = str(row.get("class_code", "")).upper() or None
            acode = str(row.get("assignment_code", "")).upper() or None
            if class_code and ccode != class_code.upper():
                continue
            if assignment_code and acode != assignment_code.upper():
                continue

            cash = float(row.get("cash", 0.0))
            debt = float(row.get("debt", 0.0))
            stress = int(row.get("stress", 20))
            score = int(row.get("score", 0))
            day = int(row.get("day", 1))
            status = str(row.get("status", "active"))

            reasons: list[str] = []
            risk_score = 0
            if cash < 400:
                reasons.append("Very low cash buffer")
                risk_score += 30
            elif cash < 900:
                reasons.append("Low cash buffer")
                risk_score += 15
            if debt > 3000:
                reasons.append("High debt load")
                risk_score += 30
            elif debt > 1200:
                reasons.append("Rising debt")
                risk_score += 15
            if stress >= 85:
                reasons.append("Critical stress level")
                risk_score += 30
            elif stress >= 70:
                reasons.append("High stress level")
                risk_score += 15
            if status == "failed":
                reasons.append("Session failed")
                risk_score += 25
            if day >= 20 and score < 55:
                reasons.append("Low score late in assignment")
                risk_score += 20

            if risk_score < 15:
                level = "low"
            elif risk_score < 35:
                level = "medium"
            elif risk_score < 60:
                level = "high"
            else:
                level = "critical"
            if level == "low":
                continue
            alerts.append(
                TeacherRiskAlert(
                    session_id=str(row.get("session_id", "")),
                    player_name=str(row.get("player_name", "Student")),
                    class_code=ccode,
                    assignment_code=acode,
                    status=status,
                    day=day,
                    cash=round(cash, 2),
                    debt=round(debt, 2),
                    stress=stress,
                    score=score,
                    risk_score=min(risk_score, 100),
                    risk_level=level,
                    reasons=reasons,
                )
            )
        alerts.sort(key=lambda x: (-x.risk_score, x.day))
        return alerts[:limit]

    # ---------- restore / bulk ----------
    def restore_deleted_entity(self, archive_id: int) -> ActionResponse:
        ref = self.client.collection("deleted_entities").document(str(archive_id))
        snap = ref.get()
        if not snap.exists:
            raise ValueError("Archived record not found")
        row = snap.to_dict() or {}
        payload = json.loads(str(row.get("payload_json", "{}")) or "{}")
        entity_type = str(row.get("entity_type", ""))

        if entity_type == "classroom":
            self._restore_classroom(payload)
        elif entity_type == "assignment":
            self._restore_assignment(payload)
        elif entity_type == "session":
            self._restore_session(payload)
        elif entity_type == "strategy_session":
            self._restore_strategy_session(payload)
        else:
            raise ValueError("Unsupported archived entity type")

        ref.delete()
        self._audit(action="restore_deleted", target_type=entity_type, target_key=str(row.get("entity_key", "")), detail={"archive_id": archive_id})
        return ActionResponse(message=f"Restored {entity_type} ({row.get('entity_key', '')})")

    def bulk_delete_sessions(self, session_ids: list[str]) -> ActionResponse:
        deleted = 0
        for sid in session_ids:
            if self._get_doc("game_sessions", sid):
                self.delete_teacher_session(sid)
                deleted += 1
        self._audit(action="bulk_delete_sessions", target_type="session", target_key="bulk", detail={"count": deleted})
        return ActionResponse(message=f"Deleted {deleted} session(s)")

    def bulk_delete_strategy_sessions(self, session_ids: list[str]) -> ActionResponse:
        deleted = 0
        for sid in session_ids:
            if self._get_doc("strategy_sessions", sid):
                self.delete_strategy_session(sid)
                deleted += 1
        self._audit(action="bulk_delete_strategy_sessions", target_type="strategy_session", target_key="bulk", detail={"count": deleted})
        return ActionResponse(message=f"Deleted {deleted} sprint session(s)")

    def bulk_restore_deleted_entities(self, archive_ids: list[int]) -> ActionResponse:
        restored = 0
        failed = 0
        for aid in archive_ids:
            try:
                self.restore_deleted_entity(aid)
                restored += 1
            except Exception:
                failed += 1
        self._audit(action="bulk_restore_deleted", target_type="archive", target_key="bulk", detail={"restored": restored, "failed": failed})
        return ActionResponse(message=f"Restored {restored} record(s), failed: {failed}")

    def purge_deleted_entities(self, archive_ids: list[int]) -> ActionResponse:
        deleted = 0
        for aid in archive_ids:
            ref = self.client.collection("deleted_entities").document(str(aid))
            if ref.get().exists:
                ref.delete()
                deleted += 1
        self._audit(action="purge_deleted", target_type="archive", target_key="bulk", detail={"count": deleted})
        return ActionResponse(message=f"Permanently deleted {deleted} archived record(s)")

    def purge_deleted_entities_older_than(self, days: int) -> ActionResponse:
        threshold = self._now() - timedelta(days=days)
        deleted = 0
        for doc in self.client.collection("deleted_entities").stream():
            row = doc.to_dict() or {}
            if self._to_dt(row.get("deleted_at")) <= threshold:
                doc.reference.delete()
                deleted += 1
        self._audit(
            action="purge_deleted_older",
            target_type="archive",
            target_key=f"older_than_{days}_days",
            detail={"count": deleted, "days": days},
        )
        return ActionResponse(message=f"Permanently deleted {deleted} archived record(s) older than {days} day(s)")

    # ---------- restore internals ----------
    def _restore_classroom(self, payload: dict) -> None:
        classroom = payload.get("classroom", {})
        class_code = str(classroom.get("class_code", "")).upper()
        if not class_code:
            raise ValueError("Archived classroom payload invalid")
        if not self._get_doc("classrooms", class_code):
            self.client.collection("classrooms").document(class_code).set(
                {
                    "class_code": class_code,
                    "class_name": str(classroom.get("class_name", "Restored Class"))[:120],
                    "created_at": self._to_dt(classroom.get("created_at")),
                }
            )
        for assignment in payload.get("assignments", []):
            assignment_code = str(assignment.get("assignment_code", "")).upper()
            if not assignment_code or self._get_doc("assignments", assignment_code):
                continue
            self.client.collection("assignments").document(assignment_code).set(
                {
                    "assignment_code": assignment_code,
                    "class_code": class_code,
                    "title": str(assignment.get("title", "Restored Assignment"))[:120],
                    "city": str(assignment.get("city", "Charlotte, NC"))[:120],
                    "start_cash": float(assignment.get("start_cash", 1800.0)),
                    "duration_days": int(assignment.get("duration_days", 30)),
                    "sprint_minutes_per_day": int(assignment.get("sprint_minutes_per_day", 2)),
                    "is_active": bool(assignment.get("is_active", True)),
                    "created_at": self._to_dt(assignment.get("created_at")),
                }
            )

    def _restore_assignment(self, payload: dict) -> None:
        assignment = payload.get("assignment", {})
        assignment_code = str(assignment.get("assignment_code", "")).upper()
        class_code = str(payload.get("class_code", "")).upper()
        if not assignment_code or not class_code:
            raise ValueError("Archived assignment payload invalid")
        if not self._get_doc("classrooms", class_code):
            raise ValueError("Cannot restore assignment: class not found")
        if self._get_doc("assignments", assignment_code):
            raise ValueError("Assignment already exists")
        self.client.collection("assignments").document(assignment_code).set(
            {
                "assignment_code": assignment_code,
                "class_code": class_code,
                "title": str(assignment.get("title", "Restored Assignment"))[:120],
                "city": str(assignment.get("city", "Charlotte, NC"))[:120],
                "start_cash": float(assignment.get("start_cash", 1800.0)),
                "duration_days": int(assignment.get("duration_days", 30)),
                "sprint_minutes_per_day": int(assignment.get("sprint_minutes_per_day", 2)),
                "is_active": bool(assignment.get("is_active", True)),
                "created_at": self._to_dt(assignment.get("created_at")),
            }
        )

    def _restore_session(self, payload: dict) -> None:
        session = payload.get("session", {})
        session_id = str(session.get("session_id", ""))
        if not session_id:
            raise ValueError("Archived session payload invalid")
        if self._get_doc("game_sessions", session_id):
            raise ValueError("Session already exists")
        self.client.collection("game_sessions").document(session_id).set(session)
        log_ref = self.client.collection("game_sessions").document(session_id).collection("logs")
        for log in payload.get("logs", []):
            log_ref.add(log)

    def _restore_strategy_session(self, payload: dict) -> None:
        strategy = payload.get("strategy_session", {})
        session_id = str(strategy.get("session_id", ""))
        if not session_id:
            raise ValueError("Archived strategy payload invalid")
        if self._get_doc("strategy_sessions", session_id):
            raise ValueError("Strategy session already exists")
        self.client.collection("strategy_sessions").document(session_id).set(strategy)
        dec_ref = self.client.collection("strategy_sessions").document(session_id).collection("decisions")
        for decision in payload.get("decisions", []):
            dec_ref.add(decision)

    def _strategy_public_state(self, row: dict) -> StrategyPublicState:
        public_offers: list[StrategyOffer] = []
        for offer in row.get("current_offers") or []:
            risk = str(offer.get("risk", "medium")).lower()
            if risk not in {"low", "medium", "high"}:
                risk = "medium"
            public_offers.append(
                StrategyOffer(
                    offer_id=str(offer.get("offer_id", "")),
                    title=str(offer.get("title", "Opportunity"))[:120],
                    text=str(offer.get("text", ""))[:180],
                    channel=str(offer.get("channel", "Other"))[:60],
                    time_hours=float(offer.get("time_hours", 1.0)),
                    miles=float(offer.get("miles", 0.0)),
                    cash_in=float(offer.get("cash_in", 0.0)),
                    cash_out=float(offer.get("cash_out", 0.0)),
                    risk=risk,
                )
            )
        return StrategyPublicState(
            session_id=str(row.get("session_id", "")),
            player_name=str(row.get("player_name", "Student")),
            current_day=int(row.get("current_day", 1)),
            total_days=int(row.get("total_days", 30)),
            assignment_minutes=int(row.get("assignment_minutes", 60)),
            status=str(row.get("status", "active")),
            total_profit=round(float(row.get("total_profit", 0.0)), 2),
            selected_count=int(row.get("selected_count", 0)),
            offers=public_offers,
            day_brief=str(row.get("current_day_brief", ""))[:255],
        )
