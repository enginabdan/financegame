from __future__ import annotations

import json
import random
import string
from datetime import datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .db import (
    AuditEventModel,
    AssignmentEnrollmentModel,
    AssignmentModel,
    ClassroomModel,
    DeletedEntityModel,
    GameDayLogModel,
    GameSessionModel,
    StudentClassMembershipModel,
    StudentProfileModel,
    StrategyDecisionModel,
    StrategySessionModel,
)
from .schemas import (
    ActionResponse,
    AuditEventSummary,
    DeletedEntitySummary,
    AssignmentRubricRow,
    AssignmentSummary,
    ClassroomSummary,
    DailyResult,
    GameState,
    StudentAssignmentOption,
    StudentClassSummary,
    StudentClassAssignmentsResponse,
    StudentProfileSummary,
    TeacherClassStudentRow,
    StrategyDecisionReview,
    TeacherDayLog,
    TeacherOverviewResponse,
    TeacherRiskAlert,
    TeacherSessionSummary,
    StrategyChooseResponse,
    StrategyLeaderboardRow,
    StrategyOffer,
    StrategyOfferReview,
    StrategyPublicState,
    StrategyResultResponse,
    StrategySessionReview,
)


class GameRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _serialize_value(self, value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    def _serialize_row(self, row, fields: list[str]) -> dict:
        return {field: self._serialize_value(getattr(row, field)) for field in fields}

    def _archive_entity(self, *, entity_type: str, entity_key: str, payload: dict) -> None:
        archive = DeletedEntityModel(
            entity_type=entity_type,
            entity_key=entity_key,
            payload_json=json.dumps(payload),
        )
        self.db.add(archive)

    def _audit(self, *, action: str, target_type: str, target_key: str, detail: dict | None = None, actor: str = "teacher") -> None:
        event = AuditEventModel(
            actor=actor[:64],
            action=action[:64],
            target_type=target_type[:32],
            target_key=target_key[:120],
            detail_json=json.dumps(detail or {}),
        )
        self.db.add(event)

    def _code(self, length: int = 6) -> str:
        return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

    def _unique_class_code(self) -> str:
        for _ in range(20):
            candidate = self._code(6)
            exists = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == candidate).first()
            if not exists:
                return candidate
        raise RuntimeError("Unable to generate unique class code")

    def _unique_assignment_code(self) -> str:
        for _ in range(20):
            candidate = self._code(7)
            exists = self.db.query(AssignmentModel).filter(AssignmentModel.assignment_code == candidate).first()
            if not exists:
                return candidate
        raise RuntimeError("Unable to generate unique assignment code")

    def _unique_strategy_session_id(self) -> str:
        for _ in range(30):
            candidate = self._code(10)
            exists = self.db.query(StrategySessionModel).filter(StrategySessionModel.session_id == candidate).first()
            if not exists:
                return candidate
        raise RuntimeError("Unable to generate strategy session id")

    def _unique_student_id(self) -> str:
        for _ in range(30):
            candidate = self._code(8)
            exists = self.db.query(StudentProfileModel).filter(StudentProfileModel.student_id == candidate).first()
            if not exists:
                return candidate
        raise RuntimeError("Unable to generate student id")

    def create_classroom(self, class_name: str) -> ClassroomSummary:
        class_code = self._unique_class_code()
        row = ClassroomModel(class_code=class_code, class_name=class_name.strip())
        self.db.add(row)
        self._audit(action="create_classroom", target_type="classroom", target_key=class_code, detail={"class_name": class_name})
        self.db.commit()
        self.db.refresh(row)
        return ClassroomSummary(
            class_code=row.class_code,
            class_name=row.class_name,
            assignment_count=0,
            active_assignment_count=0,
            created_at=row.created_at,
        )

    def update_classroom(self, class_code: str, class_name: str) -> ClassroomSummary:
        row = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code.upper()).first()
        if row is None:
            raise ValueError("Class not found")
        row.class_name = class_name.strip()
        self._audit(
            action="update_classroom",
            target_type="classroom",
            target_key=row.class_code,
            detail={"class_name": row.class_name},
        )
        self.db.commit()
        self.db.refresh(row)

        assignment_count = self.db.query(func.count(AssignmentModel.id)).filter(AssignmentModel.classroom_id == row.id).scalar() or 0
        active_assignment_count = (
            self.db.query(func.count(AssignmentModel.id))
            .filter(AssignmentModel.classroom_id == row.id, AssignmentModel.is_active.is_(True))
            .scalar()
            or 0
        )
        return ClassroomSummary(
            class_code=row.class_code,
            class_name=row.class_name,
            assignment_count=int(assignment_count),
            active_assignment_count=int(active_assignment_count),
            created_at=row.created_at,
        )

    def delete_classroom(self, class_code: str) -> ActionResponse:
        row = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code.upper()).first()
        if row is None:
            raise ValueError("Class not found")
        assignments = (
            self.db.query(AssignmentModel)
            .filter(AssignmentModel.classroom_id == row.id)
            .order_by(AssignmentModel.id.asc())
            .all()
        )
        payload = {
            "classroom": self._serialize_row(
                row,
                ["class_code", "class_name", "created_at"],
            ),
            "assignments": [
                self._serialize_row(
                    assignment,
                    [
                        "assignment_code",
                        "title",
                        "city",
                        "start_cash",
                        "duration_days",
                        "is_active",
                        "created_at",
                    ],
                )
                for assignment in assignments
            ],
        }
        self._archive_entity(entity_type="classroom", entity_key=row.class_code, payload=payload)
        self._audit(action="delete_classroom", target_type="classroom", target_key=row.class_code)
        self.db.delete(row)
        self.db.commit()
        return ActionResponse(message=f"Class {class_code.upper()} deleted")

    def list_classrooms(self) -> list[ClassroomSummary]:
        assignment_count_subq = (
            self.db.query(
                AssignmentModel.classroom_id,
                func.count(AssignmentModel.id).label("cnt"),
                func.sum(case((AssignmentModel.is_active.is_(True), 1), else_=0)).label("active_cnt"),
            )
            .group_by(AssignmentModel.classroom_id)
            .subquery()
        )

        rows = (
            self.db.query(ClassroomModel, assignment_count_subq.c.cnt, assignment_count_subq.c.active_cnt)
            .outerjoin(assignment_count_subq, assignment_count_subq.c.classroom_id == ClassroomModel.id)
            .order_by(ClassroomModel.created_at.desc())
            .all()
        )

        return [
            ClassroomSummary(
                class_code=row[0].class_code,
                class_name=row[0].class_name,
                assignment_count=int(row[1] or 0),
                active_assignment_count=int(row[2] or 0),
                created_at=row[0].created_at,
            )
            for row in rows
        ]

    def register_student(self, display_name: str) -> StudentProfileSummary:
        student_id = self._unique_student_id()
        row = StudentProfileModel(student_id=student_id, display_name=display_name.strip())
        self.db.add(row)
        self._audit(
            action="register_student",
            target_type="student",
            target_key=student_id,
            detail={"display_name": row.display_name},
            actor="student",
        )
        self.db.commit()
        self.db.refresh(row)
        return StudentProfileSummary(
            student_id=row.student_id,
            display_name=row.display_name,
            created_at=row.created_at,
        )

    def get_student(self, student_id: str) -> StudentProfileModel | None:
        return self.db.query(StudentProfileModel).filter(StudentProfileModel.student_id == student_id.upper()).first()

    def join_class(self, student_id: str, class_code: str) -> StudentClassSummary:
        student = self.get_student(student_id)
        if student is None:
            raise ValueError("Student profile not found")

        classroom = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code.upper()).first()
        if classroom is None:
            raise ValueError("Class not found")

        existing = (
            self.db.query(StudentClassMembershipModel)
            .filter(
                StudentClassMembershipModel.student_id_fk == student.id,
                StudentClassMembershipModel.classroom_id == classroom.id,
            )
            .first()
        )
        if existing is None:
            existing = StudentClassMembershipModel(student_id_fk=student.id, classroom_id=classroom.id)
            self.db.add(existing)
            self._audit(
                action="join_class",
                target_type="classroom",
                target_key=classroom.class_code,
                detail={"student_id": student.student_id},
                actor="student",
            )
            self.db.commit()
            self.db.refresh(existing)

        return StudentClassSummary(
            class_code=classroom.class_code,
            class_name=classroom.class_name,
            joined_at=existing.created_at,
        )

    def student_classes(self, student_id: str) -> list[StudentClassSummary]:
        student = self.get_student(student_id)
        if student is None:
            raise ValueError("Student profile not found")

        rows = (
            self.db.query(StudentClassMembershipModel, ClassroomModel)
            .join(ClassroomModel, ClassroomModel.id == StudentClassMembershipModel.classroom_id)
            .filter(StudentClassMembershipModel.student_id_fk == student.id)
            .order_by(StudentClassMembershipModel.created_at.desc())
            .all()
        )
        return [
            StudentClassSummary(
                class_code=classroom.class_code,
                class_name=classroom.class_name,
                joined_at=membership.created_at,
            )
            for membership, classroom in rows
        ]

    def _student_is_member_of_class(self, *, student_id: str, class_code: str) -> bool:
        student = self.get_student(student_id)
        if student is None:
            return False
        classroom = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code.upper()).first()
        if classroom is None:
            return False
        membership = (
            self.db.query(StudentClassMembershipModel)
            .filter(
                StudentClassMembershipModel.student_id_fk == student.id,
                StudentClassMembershipModel.classroom_id == classroom.id,
            )
            .first()
        )
        return membership is not None

    def class_students(self, class_code: str) -> list[TeacherClassStudentRow]:
        classroom = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code.upper()).first()
        if classroom is None:
            raise ValueError("Class not found")

        rows = (
            self.db.query(StudentClassMembershipModel, StudentProfileModel)
            .join(StudentProfileModel, StudentProfileModel.id == StudentClassMembershipModel.student_id_fk)
            .filter(StudentClassMembershipModel.classroom_id == classroom.id)
            .order_by(StudentClassMembershipModel.created_at.desc())
            .all()
        )
        return [
            TeacherClassStudentRow(
                student_id=student.student_id,
                display_name=student.display_name,
                joined_at=membership.created_at,
            )
            for membership, student in rows
        ]

    def remove_student_from_class(self, class_code: str, student_id: str) -> ActionResponse:
        classroom = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code.upper()).first()
        if classroom is None:
            raise ValueError("Class not found")
        student = self.get_student(student_id)
        if student is None:
            raise ValueError("Student not found")

        membership = (
            self.db.query(StudentClassMembershipModel)
            .filter(
                StudentClassMembershipModel.classroom_id == classroom.id,
                StudentClassMembershipModel.student_id_fk == student.id,
            )
            .first()
        )
        if membership is None:
            raise ValueError("Student is not a member of this class")

        self.db.delete(membership)
        self._audit(
            action="remove_student_from_class",
            target_type="classroom",
            target_key=classroom.class_code,
            detail={"student_id": student.student_id},
        )
        self.db.commit()
        return ActionResponse(message=f"Student {student.student_id} removed from class {classroom.class_code}")

    def create_assignment(
        self,
        class_code: str,
        title: str,
        city: str,
        start_cash: float,
        duration_days: int,
    ) -> AssignmentSummary:
        classroom = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code.upper()).first()
        if classroom is None:
            raise ValueError("Class code not found")

        assignment_code = self._unique_assignment_code()
        row = AssignmentModel(
            assignment_code=assignment_code,
            classroom_id=classroom.id,
            title=title.strip(),
            city=city.strip(),
            start_cash=start_cash,
            duration_days=duration_days,
            is_active=True,
        )
        self.db.add(row)
        self._audit(
            action="create_assignment",
            target_type="assignment",
            target_key=assignment_code,
            detail={"class_code": classroom.class_code, "title": title},
        )
        self.db.commit()
        self.db.refresh(row)

        return AssignmentSummary(
            assignment_code=row.assignment_code,
            class_code=classroom.class_code,
            title=row.title,
            city=row.city,
            start_cash=row.start_cash,
            duration_days=row.duration_days,
            is_active=row.is_active,
            enrolled_sessions=0,
            created_at=row.created_at,
        )

    def update_assignment(
        self,
        assignment_code: str,
        *,
        title: str | None,
        city: str | None,
        start_cash: float | None,
        duration_days: int | None,
        is_active: bool | None,
    ) -> AssignmentSummary:
        row_data = (
            self.db.query(AssignmentModel, ClassroomModel)
            .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
            .filter(AssignmentModel.assignment_code == assignment_code.upper())
            .first()
        )
        if row_data is None:
            raise ValueError("Assignment not found")

        assignment, classroom = row_data
        if title is not None:
            assignment.title = title.strip()
        if city is not None:
            assignment.city = city.strip()
        if start_cash is not None:
            assignment.start_cash = start_cash
        if duration_days is not None:
            assignment.duration_days = duration_days
        if is_active is not None:
            assignment.is_active = is_active
        self._audit(
            action="update_assignment",
            target_type="assignment",
            target_key=assignment.assignment_code,
            detail={
                "title": assignment.title,
                "city": assignment.city,
                "start_cash": assignment.start_cash,
                "duration_days": assignment.duration_days,
                "is_active": assignment.is_active,
            },
        )
        self.db.commit()
        self.db.refresh(assignment)

        enrolled = (
            self.db.query(func.count(AssignmentEnrollmentModel.id))
            .filter(AssignmentEnrollmentModel.assignment_id == assignment.id)
            .scalar()
            or 0
        )
        return AssignmentSummary(
            assignment_code=assignment.assignment_code,
            class_code=classroom.class_code,
            title=assignment.title,
            city=assignment.city,
            start_cash=assignment.start_cash,
            duration_days=assignment.duration_days,
            is_active=assignment.is_active,
            enrolled_sessions=int(enrolled),
            created_at=assignment.created_at,
        )

    def delete_assignment(self, assignment_code: str) -> ActionResponse:
        row = self.db.query(AssignmentModel).filter(AssignmentModel.assignment_code == assignment_code.upper()).first()
        if row is None:
            raise ValueError("Assignment not found")
        classroom = self.db.get(ClassroomModel, row.classroom_id)
        payload = {
            "assignment": self._serialize_row(
                row,
                [
                    "assignment_code",
                    "title",
                    "city",
                    "start_cash",
                    "duration_days",
                    "is_active",
                    "created_at",
                ],
            ),
            "class_code": classroom.class_code if classroom else None,
        }
        self._archive_entity(entity_type="assignment", entity_key=row.assignment_code, payload=payload)
        self._audit(action="delete_assignment", target_type="assignment", target_key=row.assignment_code)
        self.db.delete(row)
        self.db.commit()
        return ActionResponse(message=f"Assignment {assignment_code.upper()} deleted")

    def list_assignments(self, class_code: str | None = None) -> list[AssignmentSummary]:
        query = self.db.query(AssignmentModel, ClassroomModel).join(
            ClassroomModel,
            ClassroomModel.id == AssignmentModel.classroom_id,
        )

        if class_code:
            query = query.filter(ClassroomModel.class_code == class_code.upper())

        rows = query.order_by(AssignmentModel.created_at.desc()).all()

        results: list[AssignmentSummary] = []
        for assignment, classroom in rows:
            enrolled = (
                self.db.query(func.count(AssignmentEnrollmentModel.id))
                .filter(AssignmentEnrollmentModel.assignment_id == assignment.id)
                .scalar()
                or 0
            )
            results.append(
                AssignmentSummary(
                    assignment_code=assignment.assignment_code,
                    class_code=classroom.class_code,
                    title=assignment.title,
                    city=assignment.city,
                    start_cash=assignment.start_cash,
                    duration_days=assignment.duration_days,
                    is_active=assignment.is_active,
                    enrolled_sessions=int(enrolled),
                    created_at=assignment.created_at,
                )
            )
        return results

    def student_class_assignments(self, student_id: str, class_code: str) -> StudentClassAssignmentsResponse:
        student = self.get_student(student_id)
        if student is None:
            raise ValueError("Student profile not found")
        classroom = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code.upper()).first()
        if classroom is None:
            raise ValueError("Class not found")
        membership = (
            self.db.query(StudentClassMembershipModel)
            .filter(
                StudentClassMembershipModel.student_id_fk == student.id,
                StudentClassMembershipModel.classroom_id == classroom.id,
            )
            .first()
        )
        if membership is None:
            raise ValueError("Student is not a member of this class")

        rows = (
            self.db.query(AssignmentModel)
            .filter(AssignmentModel.classroom_id == classroom.id, AssignmentModel.is_active.is_(True))
            .order_by(AssignmentModel.created_at.desc())
            .all()
        )
        return StudentClassAssignmentsResponse(
            class_code=classroom.class_code,
            class_name=classroom.class_name,
            assignments=[
                StudentAssignmentOption(
                    assignment_code=row.assignment_code,
                    title=row.title,
                    city=row.city,
                    start_cash=row.start_cash,
                    duration_days=row.duration_days,
                )
                for row in rows
            ],
        )

    def assignment_rubric(self, assignment_code: str, limit: int = 200) -> list[AssignmentRubricRow]:
        rows = (
            self.db.query(GameSessionModel)
            .join(AssignmentEnrollmentModel, AssignmentEnrollmentModel.session_id == GameSessionModel.session_id)
            .join(AssignmentModel, AssignmentModel.id == AssignmentEnrollmentModel.assignment_id)
            .filter(AssignmentModel.assignment_code == assignment_code.upper())
            .order_by(GameSessionModel.score.desc(), GameSessionModel.updated_at.desc())
            .limit(limit)
            .all()
        )

        return [
            AssignmentRubricRow(
                session_id=row.session_id,
                player_name=row.player_name,
                day=row.day,
                cash=round(row.cash, 2),
                debt=round(row.debt, 2),
                stress=row.stress,
                score=row.score,
                letter_grade=self._grade_letter(row.score),
                performance_band=self._performance_band(row.score),
                status=row.status,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    def _assignment_by_codes(self, class_code: str, assignment_code: str) -> tuple[AssignmentModel, ClassroomModel] | None:
        row = (
            self.db.query(AssignmentModel, ClassroomModel)
            .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
            .filter(ClassroomModel.class_code == class_code.upper())
            .filter(AssignmentModel.assignment_code == assignment_code.upper())
            .filter(AssignmentModel.is_active == True)
            .first()
        )
        return row

    def create_session(self, state: GameState, class_code: str | None = None, assignment_code: str | None = None) -> None:
        row = GameSessionModel(
            session_id=state.session_id,
            player_name=state.player_name,
            city=state.city,
            day=state.day,
            cash=state.cash,
            tax_reserve=state.tax_reserve,
            debt=state.debt,
            stress=state.stress,
            status=state.status,
            score=0,
        )
        self.db.add(row)
        self._audit(
            action="create_session",
            target_type="session",
            target_key=state.session_id,
            detail={"player_name": state.player_name, "city": state.city},
        )
        self.db.flush()

        if class_code and assignment_code:
            assignment_row = self._assignment_by_codes(class_code=class_code, assignment_code=assignment_code)
            if assignment_row is None:
                self.db.rollback()
                raise ValueError("Assignment not found or inactive")
            assignment, _ = assignment_row
            enrollment = AssignmentEnrollmentModel(assignment_id=assignment.id, session_id=state.session_id)
            self.db.add(enrollment)

        self.db.commit()

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
        assignment_row = self._assignment_by_codes(class_code=class_code, assignment_code=assignment_code)
        if assignment_row is None:
            raise ValueError("Assignment not found or inactive")

        assignment, classroom = assignment_row

        state = GameState(
            session_id=session_id,
            player_name=player_name,
            city=assignment.city,
            cash=assignment.start_cash,
            duration_days=assignment.duration_days,
            class_code=classroom.class_code,
            assignment_code=assignment.assignment_code,
        )
        self.create_session(state, class_code=classroom.class_code, assignment_code=assignment.assignment_code)
        return state

    def get_state(self, session_id: str) -> GameState | None:
        row = self.db.get(GameSessionModel, session_id)
        if row is None:
            return None

        enrollment = (
            self.db.query(AssignmentEnrollmentModel, AssignmentModel, ClassroomModel)
            .join(AssignmentModel, AssignmentModel.id == AssignmentEnrollmentModel.assignment_id)
            .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
            .filter(AssignmentEnrollmentModel.session_id == session_id)
            .first()
        )

        class_code = None
        assignment_code = None
        duration_days = 30
        if enrollment:
            _, assignment, classroom = enrollment
            class_code = classroom.class_code
            assignment_code = assignment.assignment_code
            duration_days = assignment.duration_days

        return GameState(
            session_id=row.session_id,
            player_name=row.player_name,
            city=row.city,
            day=row.day,
            cash=row.cash,
            tax_reserve=row.tax_reserve,
            debt=row.debt,
            stress=row.stress,
            status=row.status,
            duration_days=duration_days,
            class_code=class_code,
            assignment_code=assignment_code,
        )

    def update_state_and_log(self, state: GameState, score: int, result: DailyResult) -> None:
        row = self.db.get(GameSessionModel, state.session_id)
        if row is None:
            return

        row.day = state.day
        row.cash = state.cash
        row.tax_reserve = state.tax_reserve
        row.debt = state.debt
        row.stress = state.stress
        row.status = state.status
        row.score = score

        log = GameDayLogModel(
            session_id=state.session_id,
            day=result.day,
            gross_income=result.gross_income,
            platform_fees=result.platform_fees,
            variable_costs=result.variable_costs,
            household_costs=result.household_costs,
            tax_reserve=result.tax_reserve,
            event_title=result.event_title,
            event_text=result.event_text,
            event_cash_impact=result.event_cash_impact,
            end_cash=result.end_cash,
        )
        self.db.add(log)
        self.db.commit()

    def teacher_overview(self) -> TeacherOverviewResponse:
        total = self.db.query(func.count(GameSessionModel.session_id)).scalar() or 0
        active = self.db.query(func.count(GameSessionModel.session_id)).filter(GameSessionModel.status == "active").scalar() or 0
        completed = (
            self.db.query(func.count(GameSessionModel.session_id)).filter(GameSessionModel.status == "completed").scalar()
            or 0
        )
        failed = self.db.query(func.count(GameSessionModel.session_id)).filter(GameSessionModel.status == "failed").scalar() or 0
        avg_score = self.db.query(func.avg(GameSessionModel.score)).scalar() or 0.0

        return TeacherOverviewResponse(
            total_sessions=int(total),
            active_sessions=int(active),
            completed_sessions=int(completed),
            failed_sessions=int(failed),
            avg_score=round(float(avg_score), 2),
        )

    def teacher_sessions(
        self,
        limit: int = 50,
        class_code: str | None = None,
        assignment_code: str | None = None,
    ) -> list[TeacherSessionSummary]:
        query = self.db.query(GameSessionModel).order_by(GameSessionModel.updated_at.desc())

        if class_code or assignment_code:
            query = (
                query.join(AssignmentEnrollmentModel, AssignmentEnrollmentModel.session_id == GameSessionModel.session_id)
                .join(AssignmentModel, AssignmentModel.id == AssignmentEnrollmentModel.assignment_id)
                .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
            )
            if class_code:
                query = query.filter(ClassroomModel.class_code == class_code.upper())
            if assignment_code:
                query = query.filter(AssignmentModel.assignment_code == assignment_code.upper())

        rows = query.limit(limit).all()

        summaries: list[TeacherSessionSummary] = []
        for row in rows:
            enrollment = (
                self.db.query(AssignmentEnrollmentModel, AssignmentModel, ClassroomModel)
                .join(AssignmentModel, AssignmentModel.id == AssignmentEnrollmentModel.assignment_id)
                .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
                .filter(AssignmentEnrollmentModel.session_id == row.session_id)
                .first()
            )

            class_code_value = None
            assignment_code_value = None
            if enrollment:
                _, assignment, classroom = enrollment
                class_code_value = classroom.class_code
                assignment_code_value = assignment.assignment_code

            summaries.append(
                TeacherSessionSummary(
                    session_id=row.session_id,
                    player_name=row.player_name,
                    city=row.city,
                    status=row.status,
                    day=row.day,
                    cash=round(row.cash, 2),
                    stress=row.stress,
                    score=row.score,
                    class_code=class_code_value,
                    assignment_code=assignment_code_value,
                    updated_at=row.updated_at,
                )
            )

        return summaries

    def teacher_session_logs(self, session_id: str, limit: int = 30) -> list[TeacherDayLog]:
        rows = (
            self.db.query(GameDayLogModel)
            .filter(GameDayLogModel.session_id == session_id)
            .order_by(GameDayLogModel.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            TeacherDayLog(
                day=row.day,
                gross_income=row.gross_income,
                platform_fees=row.platform_fees,
                variable_costs=row.variable_costs,
                household_costs=row.household_costs,
                tax_reserve=row.tax_reserve,
                event_title=row.event_title,
                event_text=row.event_text,
                event_cash_impact=row.event_cash_impact,
                end_cash=row.end_cash,
                created_at=row.created_at,
            )
            for row in rows
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
        row = self.db.get(GameSessionModel, session_id)
        if row is None:
            raise ValueError("Session not found")

        if player_name is not None:
            row.player_name = player_name.strip()
        if city is not None:
            row.city = city.strip()
        if status is not None:
            row.status = status
        if day is not None:
            row.day = day
        if cash is not None:
            row.cash = cash
        if tax_reserve is not None:
            row.tax_reserve = tax_reserve
        if debt is not None:
            row.debt = debt
        if stress is not None:
            row.stress = stress
        if score is not None:
            row.score = score
        self._audit(
            action="update_session",
            target_type="session",
            target_key=row.session_id,
            detail={
                "player_name": row.player_name,
                "city": row.city,
                "status": row.status,
                "day": row.day,
                "cash": row.cash,
                "stress": row.stress,
                "score": row.score,
            },
        )
        self.db.commit()
        self.db.refresh(row)

        enrollment = (
            self.db.query(AssignmentEnrollmentModel, AssignmentModel, ClassroomModel)
            .join(AssignmentModel, AssignmentModel.id == AssignmentEnrollmentModel.assignment_id)
            .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
            .filter(AssignmentEnrollmentModel.session_id == row.session_id)
            .first()
        )
        class_code_value = None
        assignment_code_value = None
        if enrollment:
            _, assignment, classroom = enrollment
            class_code_value = classroom.class_code
            assignment_code_value = assignment.assignment_code

        return TeacherSessionSummary(
            session_id=row.session_id,
            player_name=row.player_name,
            city=row.city,
            status=row.status,
            day=row.day,
            cash=round(row.cash, 2),
            stress=row.stress,
            score=row.score,
            class_code=class_code_value,
            assignment_code=assignment_code_value,
            updated_at=row.updated_at,
        )

    def delete_teacher_session(self, session_id: str) -> ActionResponse:
        row = self.db.get(GameSessionModel, session_id)
        if row is None:
            raise ValueError("Session not found")
        day_logs = (
            self.db.query(GameDayLogModel)
            .filter(GameDayLogModel.session_id == session_id)
            .order_by(GameDayLogModel.id.asc())
            .all()
        )
        enrollment = (
            self.db.query(AssignmentEnrollmentModel, AssignmentModel, ClassroomModel)
            .join(AssignmentModel, AssignmentModel.id == AssignmentEnrollmentModel.assignment_id)
            .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
            .filter(AssignmentEnrollmentModel.session_id == session_id)
            .first()
        )
        payload = {
            "session": self._serialize_row(
                row,
                [
                    "session_id",
                    "player_name",
                    "city",
                    "day",
                    "cash",
                    "tax_reserve",
                    "debt",
                    "stress",
                    "status",
                    "score",
                    "created_at",
                    "updated_at",
                ],
            ),
            "logs": [
                self._serialize_row(
                    log,
                    [
                        "day",
                        "gross_income",
                        "platform_fees",
                        "variable_costs",
                        "household_costs",
                        "tax_reserve",
                        "event_title",
                        "event_text",
                        "event_cash_impact",
                        "end_cash",
                        "created_at",
                    ],
                )
                for log in day_logs
            ],
            "enrollment": (
                {
                    "class_code": enrollment[2].class_code,
                    "assignment_code": enrollment[1].assignment_code,
                }
                if enrollment
                else None
            ),
        }
        self._archive_entity(entity_type="session", entity_key=row.session_id, payload=payload)
        self._audit(action="delete_session", target_type="session", target_key=row.session_id)
        self.db.delete(row)
        self.db.commit()
        return ActionResponse(message=f"Session {session_id} deleted")

    def remove_session_from_class(self, session_id: str) -> ActionResponse:
        enrollment = (
            self.db.query(AssignmentEnrollmentModel)
            .filter(AssignmentEnrollmentModel.session_id == session_id)
            .first()
        )
        if enrollment is None:
            raise ValueError("Session is not enrolled in a class assignment")
        self.db.delete(enrollment)
        self._audit(action="remove_session_enrollment", target_type="session", target_key=session_id)
        self.db.commit()
        return ActionResponse(message=f"Session {session_id} removed from class assignment")

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

    # ---------- Strategy Assignment (1-hour / 30-day sprint) ----------
    def create_strategy_session(
        self,
        *,
        player_name: str,
        total_days: int,
        assignment_minutes: int,
        offers: list[dict],
        day_brief: str,
    ) -> StrategyPublicState:
        session_id = self._unique_strategy_session_id()
        row = StrategySessionModel(
            session_id=session_id,
            player_name=player_name.strip() or "Student",
            current_day=1,
            total_days=total_days,
            assignment_minutes=assignment_minutes,
            status="active",
            total_profit=0.0,
            optimal_profit=0.0,
            selected_count=0,
            current_offers_json=json.dumps(offers),
            current_day_brief=day_brief[:255],
        )
        self.db.add(row)
        self._audit(
            action="create_strategy_session",
            target_type="strategy_session",
            target_key=session_id,
            detail={"player_name": row.player_name, "total_days": total_days},
        )
        self.db.commit()
        return self._strategy_public_state(row)

    def get_strategy_state(self, session_id: str) -> StrategyPublicState | None:
        row = self.db.get(StrategySessionModel, session_id)
        if row is None:
            return None
        return self._strategy_public_state(row)

    def list_strategy_recent_channels(self, session_id: str, limit: int = 6) -> list[str]:
        rows = (
            self.db.query(StrategyDecisionModel)
            .filter(StrategyDecisionModel.session_id == session_id)
            .order_by(StrategyDecisionModel.id.desc())
            .limit(limit)
            .all()
        )
        channels: list[str] = []
        for row in rows:
            try:
                offers = json.loads(row.offers_json)
            except Exception:
                offers = []
            for offer in offers:
                if offer.get("offer_id") == row.chosen_offer_id and offer.get("channel"):
                    channels.append(str(offer.get("channel")))
        channels.reverse()
        return channels

    def choose_strategy_offer(
        self,
        *,
        session_id: str,
        offer_id: str,
        next_offers: list[dict] | None,
        next_day_brief: str | None,
    ) -> StrategyChooseResponse:
        row = self.db.get(StrategySessionModel, session_id)
        if row is None:
            raise ValueError("Strategy session not found")
        if row.status != "active":
            raise ValueError("Strategy session already completed")

        offers = self._decode_offers(row.current_offers_json)
        if not offers:
            raise ValueError("No offers available to choose")

        selected = next((o for o in offers if str(o.get("offer_id")) == offer_id), None)
        if selected is None:
            raise ValueError("Selected offer not found for current day")

        optimal = max(float(o.get("expected_profit", -10_000)) for o in offers)
        chosen_profit = float(selected.get("expected_profit", 0.0))
        chosen_title = str(selected.get("title", "Selected Offer"))[:160]

        row.total_profit += chosen_profit
        row.optimal_profit += optimal
        row.selected_count += 1

        decision = StrategyDecisionModel(
            session_id=row.session_id,
            day=row.current_day,
            chosen_offer_id=str(selected.get("offer_id")),
            chosen_offer_title=chosen_title,
            chosen_profit=chosen_profit,
            optimal_profit=optimal,
            offers_json=json.dumps(offers),
            day_brief=row.current_day_brief,
        )
        self.db.add(decision)

        if row.current_day >= row.total_days:
            row.status = "completed"
            row.current_offers_json = "[]"
            row.current_day_brief = "Assignment completed."
        else:
            row.current_day += 1
            row.current_offers_json = json.dumps(next_offers or [])
            row.current_day_brief = (next_day_brief or f"Day {row.current_day} opportunities loaded.")[:255]

        self.db.commit()
        self.db.refresh(row)

        return StrategyChooseResponse(
            state=self._strategy_public_state(row),
            chosen_offer_title=chosen_title,
            chosen_profit=round(chosen_profit, 2),
            running_profit=round(row.total_profit, 2),
        )

    def strategy_result(self, session_id: str) -> StrategyResultResponse | None:
        row = self.db.get(StrategySessionModel, session_id)
        if row is None:
            return None
        denom = row.optimal_profit if row.optimal_profit > 0 else 1.0
        pct = max(0.0, min(100.0, (row.total_profit / denom) * 100))
        return StrategyResultResponse(
            session_id=row.session_id,
            player_name=row.player_name,
            total_days=row.total_days,
            student_profit=round(row.total_profit, 2),
            optimal_profit=round(row.optimal_profit, 2),
            success_percentage=round(pct, 2),
            status=row.status,
        )

    def strategy_leaderboard(self, limit: int = 50) -> list[StrategyLeaderboardRow]:
        rows = (
            self.db.query(StrategySessionModel)
            .order_by(StrategySessionModel.updated_at.desc())
            .limit(limit)
            .all()
        )
        data: list[StrategyLeaderboardRow] = []
        for row in rows:
            denom = row.optimal_profit if row.optimal_profit > 0 else 1.0
            pct = max(0.0, min(100.0, (row.total_profit / denom) * 100))
            data.append(
                StrategyLeaderboardRow(
                    session_id=row.session_id,
                    player_name=row.player_name,
                    current_day=row.current_day,
                    total_days=row.total_days,
                    total_profit=round(row.total_profit, 2),
                    optimal_profit=round(row.optimal_profit, 2),
                    success_percentage=round(pct, 2),
                    status=row.status,
                    updated_at=row.updated_at,
                )
            )
        data.sort(
            key=lambda x: (
                x.status != "completed",
                -x.success_percentage,
                -x.total_profit,
            )
        )
        return data[:limit]

    def strategy_session_review(self, session_id: str) -> StrategySessionReview | None:
        row = self.db.get(StrategySessionModel, session_id)
        if row is None:
            return None

        decisions_rows = (
            self.db.query(StrategyDecisionModel)
            .filter(StrategyDecisionModel.session_id == session_id)
            .order_by(StrategyDecisionModel.day.asc(), StrategyDecisionModel.id.asc())
            .all()
        )
        decisions: list[StrategyDecisionReview] = []
        for dec in decisions_rows:
            offers: list[StrategyOfferReview] = []
            for offer in self._decode_offers(dec.offers_json):
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
                    id=dec.id,
                    day=dec.day,
                    chosen_offer_id=dec.chosen_offer_id,
                    chosen_offer_title=dec.chosen_offer_title,
                    chosen_profit=round(dec.chosen_profit, 2),
                    optimal_profit=round(dec.optimal_profit, 2),
                    gap_to_optimal=round(dec.optimal_profit - dec.chosen_profit, 2),
                    day_brief=dec.day_brief,
                    offers=offers,
                    created_at=dec.created_at,
                )
            )

        denom = row.optimal_profit if row.optimal_profit > 0 else 1.0
        pct = max(0.0, min(100.0, (row.total_profit / denom) * 100))
        return StrategySessionReview(
            session_id=row.session_id,
            player_name=row.player_name,
            current_day=row.current_day,
            total_days=row.total_days,
            assignment_minutes=row.assignment_minutes,
            status=row.status,
            total_profit=round(row.total_profit, 2),
            optimal_profit=round(row.optimal_profit, 2),
            success_percentage=round(pct, 2),
            selected_count=row.selected_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
            decisions=decisions,
        )

    def delete_strategy_session(self, session_id: str) -> ActionResponse:
        row = self.db.get(StrategySessionModel, session_id)
        if row is None:
            raise ValueError("Strategy session not found")
        decisions = (
            self.db.query(StrategyDecisionModel)
            .filter(StrategyDecisionModel.session_id == session_id)
            .order_by(StrategyDecisionModel.id.asc())
            .all()
        )
        payload = {
            "strategy_session": self._serialize_row(
                row,
                [
                    "session_id",
                    "player_name",
                    "current_day",
                    "total_days",
                    "assignment_minutes",
                    "status",
                    "total_profit",
                    "optimal_profit",
                    "selected_count",
                    "current_offers_json",
                    "current_day_brief",
                    "created_at",
                    "updated_at",
                ],
            ),
            "decisions": [
                self._serialize_row(
                    decision,
                    [
                        "day",
                        "chosen_offer_id",
                        "chosen_offer_title",
                        "chosen_profit",
                        "optimal_profit",
                        "offers_json",
                        "day_brief",
                        "created_at",
                    ],
                )
                for decision in decisions
            ],
        }
        self._archive_entity(entity_type="strategy_session", entity_key=row.session_id, payload=payload)
        self._audit(action="delete_strategy_session", target_type="strategy_session", target_key=row.session_id)
        self.db.delete(row)
        self.db.commit()
        return ActionResponse(message=f"Strategy session {session_id} deleted")

    def list_deleted_entities(
        self,
        *,
        limit: int = 200,
        entity_type: str | None = None,
        since_days: int | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[DeletedEntitySummary]:
        query = self.db.query(DeletedEntityModel)
        if entity_type:
            query = query.filter(DeletedEntityModel.entity_type == entity_type.strip().lower())
        if since_days is not None and since_days > 0:
            min_time = datetime.utcnow() - timedelta(days=since_days)
            query = query.filter(DeletedEntityModel.deleted_at >= min_time)
        if from_date is not None:
            query = query.filter(DeletedEntityModel.deleted_at >= from_date)
        if to_date is not None:
            query = query.filter(DeletedEntityModel.deleted_at <= to_date)

        rows = query.order_by(DeletedEntityModel.deleted_at.desc(), DeletedEntityModel.id.desc()).limit(limit).all()
        return [
            DeletedEntitySummary(
                id=row.id,
                entity_type=row.entity_type,
                entity_key=row.entity_key,
                deleted_at=row.deleted_at,
            )
            for row in rows
        ]

    def list_audit_events(
        self,
        *,
        limit: int = 300,
        action: str | None = None,
        target_type: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[AuditEventSummary]:
        query = self.db.query(AuditEventModel)
        if action:
            query = query.filter(AuditEventModel.action == action.strip().lower())
        if target_type:
            query = query.filter(AuditEventModel.target_type == target_type.strip().lower())
        if from_date is not None:
            query = query.filter(AuditEventModel.created_at >= from_date)
        if to_date is not None:
            query = query.filter(AuditEventModel.created_at <= to_date)
        rows = query.order_by(AuditEventModel.created_at.desc(), AuditEventModel.id.desc()).limit(limit).all()
        return [
            AuditEventSummary(
                id=row.id,
                actor=row.actor,
                action=row.action,
                target_type=row.target_type,
                target_key=row.target_key,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def teacher_risk_alerts(
        self,
        *,
        limit: int = 100,
        class_code: str | None = None,
        assignment_code: str | None = None,
    ) -> list[TeacherRiskAlert]:
        query = self.db.query(GameSessionModel).order_by(GameSessionModel.updated_at.desc())
        if class_code or assignment_code:
            query = (
                query.join(AssignmentEnrollmentModel, AssignmentEnrollmentModel.session_id == GameSessionModel.session_id)
                .join(AssignmentModel, AssignmentModel.id == AssignmentEnrollmentModel.assignment_id)
                .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
            )
            if class_code:
                query = query.filter(ClassroomModel.class_code == class_code.upper())
            if assignment_code:
                query = query.filter(AssignmentModel.assignment_code == assignment_code.upper())

        rows = query.limit(max(limit * 2, 200)).all()
        alerts: list[TeacherRiskAlert] = []
        for row in rows:
            enrollment = (
                self.db.query(AssignmentEnrollmentModel, AssignmentModel, ClassroomModel)
                .join(AssignmentModel, AssignmentModel.id == AssignmentEnrollmentModel.assignment_id)
                .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
                .filter(AssignmentEnrollmentModel.session_id == row.session_id)
                .first()
            )
            ccode = enrollment[2].class_code if enrollment else None
            acode = enrollment[1].assignment_code if enrollment else None

            reasons: list[str] = []
            risk_score = 0
            if row.cash < 400:
                reasons.append("Very low cash buffer")
                risk_score += 30
            elif row.cash < 900:
                reasons.append("Low cash buffer")
                risk_score += 15
            if row.debt > 3000:
                reasons.append("High debt load")
                risk_score += 30
            elif row.debt > 1200:
                reasons.append("Rising debt")
                risk_score += 15
            if row.stress >= 85:
                reasons.append("Critical stress level")
                risk_score += 30
            elif row.stress >= 70:
                reasons.append("High stress level")
                risk_score += 15
            if row.status == "failed":
                reasons.append("Session failed")
                risk_score += 25
            if row.day >= 20 and row.score < 55:
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
                    session_id=row.session_id,
                    player_name=row.player_name,
                    class_code=ccode,
                    assignment_code=acode,
                    status=row.status,
                    day=row.day,
                    cash=round(row.cash, 2),
                    debt=round(row.debt, 2),
                    stress=row.stress,
                    score=row.score,
                    risk_score=min(risk_score, 100),
                    risk_level=level,
                    reasons=reasons,
                )
            )

        alerts.sort(key=lambda x: (-x.risk_score, x.day))
        return alerts[:limit]

    def restore_deleted_entity(self, archive_id: int) -> ActionResponse:
        row = self.db.get(DeletedEntityModel, archive_id)
        if row is None:
            raise ValueError("Archived record not found")
        payload = json.loads(row.payload_json or "{}")

        if row.entity_type == "classroom":
            self._restore_classroom(payload)
        elif row.entity_type == "assignment":
            self._restore_assignment(payload)
        elif row.entity_type == "session":
            self._restore_session(payload)
        elif row.entity_type == "strategy_session":
            self._restore_strategy_session(payload)
        else:
            raise ValueError("Unsupported archived entity type")

        self.db.delete(row)
        self._audit(action="restore_deleted", target_type=row.entity_type, target_key=row.entity_key, detail={"archive_id": archive_id})
        self.db.commit()
        return ActionResponse(message=f"Restored {row.entity_type} ({row.entity_key})")

    def bulk_delete_sessions(self, session_ids: list[str]) -> ActionResponse:
        deleted = 0
        for session_id in session_ids:
            row = self.db.get(GameSessionModel, session_id)
            if row is None:
                continue
            self.delete_teacher_session(session_id)
            deleted += 1
        self._audit(action="bulk_delete_sessions", target_type="session", target_key="bulk", detail={"count": deleted})
        self.db.commit()
        return ActionResponse(message=f"Deleted {deleted} session(s)")

    def bulk_delete_strategy_sessions(self, session_ids: list[str]) -> ActionResponse:
        deleted = 0
        for session_id in session_ids:
            row = self.db.get(StrategySessionModel, session_id)
            if row is None:
                continue
            self.delete_strategy_session(session_id)
            deleted += 1
        self._audit(
            action="bulk_delete_strategy_sessions",
            target_type="strategy_session",
            target_key="bulk",
            detail={"count": deleted},
        )
        self.db.commit()
        return ActionResponse(message=f"Deleted {deleted} sprint session(s)")

    def bulk_restore_deleted_entities(self, archive_ids: list[int]) -> ActionResponse:
        restored = 0
        failed = 0
        for archive_id in archive_ids:
            try:
                self.restore_deleted_entity(archive_id=archive_id)
                restored += 1
            except Exception:
                self.db.rollback()
                failed += 1
        self._audit(
            action="bulk_restore_deleted",
            target_type="archive",
            target_key="bulk",
            detail={"restored": restored, "failed": failed},
        )
        self.db.commit()
        return ActionResponse(message=f"Restored {restored} record(s), failed: {failed}")

    def purge_deleted_entities(self, archive_ids: list[int]) -> ActionResponse:
        rows = (
            self.db.query(DeletedEntityModel)
            .filter(DeletedEntityModel.id.in_(archive_ids))
            .all()
        )
        deleted = len(rows)
        for row in rows:
            self.db.delete(row)
        self._audit(action="purge_deleted", target_type="archive", target_key="bulk", detail={"count": deleted})
        self.db.commit()
        return ActionResponse(message=f"Permanently deleted {deleted} archived record(s)")

    def purge_deleted_entities_older_than(self, days: int) -> ActionResponse:
        threshold = datetime.utcnow() - timedelta(days=days)
        rows = (
            self.db.query(DeletedEntityModel)
            .filter(DeletedEntityModel.deleted_at <= threshold)
            .all()
        )
        deleted = len(rows)
        for row in rows:
            self.db.delete(row)
        self._audit(
            action="purge_deleted_older",
            target_type="archive",
            target_key=f"older_than_{days}_days",
            detail={"count": deleted, "days": days},
        )
        self.db.commit()
        return ActionResponse(message=f"Permanently deleted {deleted} archived record(s) older than {days} day(s)")

    def _parse_dt(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except Exception:
            return None

    def _restore_classroom(self, payload: dict) -> None:
        classroom = payload.get("classroom", {})
        class_code = str(classroom.get("class_code", "")).upper()
        if not class_code:
            raise ValueError("Archived classroom payload invalid")

        existing = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code).first()
        if existing is None:
            self.db.add(
                ClassroomModel(
                    class_code=class_code,
                    class_name=str(classroom.get("class_name", "Restored Class"))[:120],
                    created_at=self._parse_dt(classroom.get("created_at")) or datetime.utcnow(),
                )
            )
            self.db.flush()

        class_row = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code).first()
        for assignment in payload.get("assignments", []):
            assignment_code = str(assignment.get("assignment_code", "")).upper()
            if not assignment_code:
                continue
            exists = self.db.query(AssignmentModel).filter(AssignmentModel.assignment_code == assignment_code).first()
            if exists:
                continue
            self.db.add(
                AssignmentModel(
                    assignment_code=assignment_code,
                    classroom_id=class_row.id,
                    title=str(assignment.get("title", "Restored Assignment"))[:120],
                    city=str(assignment.get("city", "Charlotte, NC"))[:120],
                    start_cash=float(assignment.get("start_cash", 1800.0)),
                    duration_days=int(assignment.get("duration_days", 30)),
                    is_active=bool(assignment.get("is_active", True)),
                    created_at=self._parse_dt(assignment.get("created_at")) or datetime.utcnow(),
                )
            )

    def _restore_assignment(self, payload: dict) -> None:
        assignment = payload.get("assignment", {})
        assignment_code = str(assignment.get("assignment_code", "")).upper()
        class_code = str(payload.get("class_code", "")).upper()
        if not assignment_code or not class_code:
            raise ValueError("Archived assignment payload invalid")

        class_row = self.db.query(ClassroomModel).filter(ClassroomModel.class_code == class_code).first()
        if class_row is None:
            raise ValueError("Cannot restore assignment: class not found")
        exists = self.db.query(AssignmentModel).filter(AssignmentModel.assignment_code == assignment_code).first()
        if exists:
            raise ValueError("Assignment already exists")

        self.db.add(
            AssignmentModel(
                assignment_code=assignment_code,
                classroom_id=class_row.id,
                title=str(assignment.get("title", "Restored Assignment"))[:120],
                city=str(assignment.get("city", "Charlotte, NC"))[:120],
                start_cash=float(assignment.get("start_cash", 1800.0)),
                duration_days=int(assignment.get("duration_days", 30)),
                is_active=bool(assignment.get("is_active", True)),
                created_at=self._parse_dt(assignment.get("created_at")) or datetime.utcnow(),
            )
        )

    def _restore_session(self, payload: dict) -> None:
        session = payload.get("session", {})
        session_id = str(session.get("session_id", ""))
        if not session_id:
            raise ValueError("Archived session payload invalid")
        exists = self.db.get(GameSessionModel, session_id)
        if exists:
            raise ValueError("Session already exists")

        session_row = GameSessionModel(
            session_id=session_id,
            player_name=str(session.get("player_name", "Restored Student"))[:120],
            city=str(session.get("city", "Charlotte, NC"))[:120],
            day=int(session.get("day", 1)),
            cash=float(session.get("cash", 1800.0)),
            tax_reserve=float(session.get("tax_reserve", 0.0)),
            debt=float(session.get("debt", 0.0)),
            stress=int(session.get("stress", 20)),
            status=str(session.get("status", "active"))[:24],
            score=int(session.get("score", 0)),
            created_at=self._parse_dt(session.get("created_at")) or datetime.utcnow(),
            updated_at=self._parse_dt(session.get("updated_at")) or datetime.utcnow(),
        )
        self.db.add(session_row)
        self.db.flush()

        for log in payload.get("logs", []):
            self.db.add(
                GameDayLogModel(
                    session_id=session_id,
                    day=int(log.get("day", 1)),
                    gross_income=float(log.get("gross_income", 0.0)),
                    platform_fees=float(log.get("platform_fees", 0.0)),
                    variable_costs=float(log.get("variable_costs", 0.0)),
                    household_costs=float(log.get("household_costs", 0.0)),
                    tax_reserve=float(log.get("tax_reserve", 0.0)),
                    event_title=str(log.get("event_title", "Restored Log"))[:120],
                    event_text=str(log.get("event_text", ""))[:255],
                    event_cash_impact=float(log.get("event_cash_impact", 0.0)),
                    end_cash=float(log.get("end_cash", 0.0)),
                    created_at=self._parse_dt(log.get("created_at")) or datetime.utcnow(),
                )
            )

        enrollment = payload.get("enrollment")
        if enrollment:
            class_code = str(enrollment.get("class_code", "")).upper()
            assignment_code = str(enrollment.get("assignment_code", "")).upper()
            assignment_row = (
                self.db.query(AssignmentModel, ClassroomModel)
                .join(ClassroomModel, ClassroomModel.id == AssignmentModel.classroom_id)
                .filter(ClassroomModel.class_code == class_code)
                .filter(AssignmentModel.assignment_code == assignment_code)
                .first()
            )
            if assignment_row:
                assignment, _ = assignment_row
                self.db.add(AssignmentEnrollmentModel(assignment_id=assignment.id, session_id=session_id))

    def _restore_strategy_session(self, payload: dict) -> None:
        strategy = payload.get("strategy_session", {})
        session_id = str(strategy.get("session_id", ""))
        if not session_id:
            raise ValueError("Archived strategy payload invalid")
        exists = self.db.get(StrategySessionModel, session_id)
        if exists:
            raise ValueError("Strategy session already exists")

        strategy_row = StrategySessionModel(
            session_id=session_id,
            player_name=str(strategy.get("player_name", "Restored Sprint"))[:120],
            current_day=int(strategy.get("current_day", 1)),
            total_days=int(strategy.get("total_days", 30)),
            assignment_minutes=int(strategy.get("assignment_minutes", 60)),
            status=str(strategy.get("status", "active"))[:24],
            total_profit=float(strategy.get("total_profit", 0.0)),
            optimal_profit=float(strategy.get("optimal_profit", 0.0)),
            selected_count=int(strategy.get("selected_count", 0)),
            current_offers_json=str(strategy.get("current_offers_json", "[]")),
            current_day_brief=str(strategy.get("current_day_brief", ""))[:255],
            created_at=self._parse_dt(strategy.get("created_at")) or datetime.utcnow(),
            updated_at=self._parse_dt(strategy.get("updated_at")) or datetime.utcnow(),
        )
        self.db.add(strategy_row)
        self.db.flush()

        for decision in payload.get("decisions", []):
            self.db.add(
                StrategyDecisionModel(
                    session_id=session_id,
                    day=int(decision.get("day", 1)),
                    chosen_offer_id=str(decision.get("chosen_offer_id", ""))[:64],
                    chosen_offer_title=str(decision.get("chosen_offer_title", "Restored Choice"))[:160],
                    chosen_profit=float(decision.get("chosen_profit", 0.0)),
                    optimal_profit=float(decision.get("optimal_profit", 0.0)),
                    offers_json=str(decision.get("offers_json", "[]")),
                    day_brief=str(decision.get("day_brief", ""))[:255],
                    created_at=self._parse_dt(decision.get("created_at")) or datetime.utcnow(),
                )
            )

    def _decode_offers(self, offers_json: str) -> list[dict]:
        try:
            payload = json.loads(offers_json or "[]")
            if isinstance(payload, list):
                return payload
            return []
        except Exception:
            return []

    def _strategy_public_state(self, row: StrategySessionModel) -> StrategyPublicState:
        offers_raw = self._decode_offers(row.current_offers_json)
        public_offers: list[StrategyOffer] = []
        for offer in offers_raw:
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
            session_id=row.session_id,
            player_name=row.player_name,
            current_day=row.current_day,
            total_days=row.total_days,
            assignment_minutes=row.assignment_minutes,
            status=row.status,
            total_profit=round(row.total_profit, 2),
            selected_count=row.selected_count,
            offers=public_offers,
            day_brief=row.current_day_brief,
        )
