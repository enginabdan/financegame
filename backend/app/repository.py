from __future__ import annotations

import random
import string

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .db import AssignmentEnrollmentModel, AssignmentModel, ClassroomModel, GameDayLogModel, GameSessionModel
from .schemas import (
    AssignmentRubricRow,
    AssignmentSummary,
    ClassroomSummary,
    DailyResult,
    GameState,
    TeacherDayLog,
    TeacherOverviewResponse,
    TeacherSessionSummary,
)


class GameRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

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

    def create_classroom(self, class_name: str) -> ClassroomSummary:
        class_code = self._unique_class_code()
        row = ClassroomModel(class_code=class_code, class_name=class_name.strip())
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return ClassroomSummary(
            class_code=row.class_code,
            class_name=row.class_name,
            assignment_count=0,
            active_assignment_count=0,
            created_at=row.created_at,
        )

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
        player_name: str,
        class_code: str,
        assignment_code: str,
        session_id: str,
    ) -> GameState:
        assignment_row = self._assignment_by_codes(class_code=class_code, assignment_code=assignment_code)
        if assignment_row is None:
            raise ValueError("Assignment not found or inactive")

        assignment, classroom = assignment_row

        state = GameState(
            session_id=session_id,
            player_name=player_name,
            city=assignment.city,
            cash=assignment.start_cash,
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
        if enrollment:
            _, assignment, classroom = enrollment
            class_code = classroom.class_code
            assignment_code = assignment.assignment_code

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
