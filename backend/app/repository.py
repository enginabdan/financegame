from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import GameDayLogModel, GameSessionModel
from .schemas import DailyResult, GameState, TeacherDayLog, TeacherOverviewResponse, TeacherSessionSummary


class GameRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, state: GameState) -> None:
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
        self.db.commit()

    def get_state(self, session_id: str) -> GameState | None:
        row = self.db.get(GameSessionModel, session_id)
        if row is None:
            return None
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

    def teacher_sessions(self, limit: int = 50) -> list[TeacherSessionSummary]:
        rows = (
            self.db.query(GameSessionModel)
            .order_by(GameSessionModel.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            TeacherSessionSummary(
                session_id=row.session_id,
                player_name=row.player_name,
                city=row.city,
                status=row.status,
                day=row.day,
                cash=round(row.cash, 2),
                stress=row.stress,
                score=row.score,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

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
