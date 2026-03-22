#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from google.cloud import firestore


def parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        return datetime.utcnow()
    text = str(value).strip()
    if not text:
        return datetime.utcnow()
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def rows(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    return list(conn.execute(query).fetchall())


def maybe_clear_collections(client: firestore.Client, clear_first: bool) -> None:
    if not clear_first:
        return
    collections = [
        "classrooms",
        "assignments",
        "students",
        "memberships",
        "game_sessions",
        "game_day_logs",
        "strategy_sessions",
        "strategy_decisions",
        "deleted_entities",
        "audit_events",
        "_meta",
    ]
    for col in collections:
        for doc in client.collection(col).stream():
            doc.reference.delete()


def migrate(sqlite_path: Path, project_id: str | None, clear_first: bool) -> dict[str, int]:
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    client = firestore.Client(project=project_id) if project_id else firestore.Client()

    maybe_clear_collections(client, clear_first)

    classrooms = rows(conn, "SELECT id, class_code, class_name, created_at FROM classrooms")
    assignments = rows(
        conn,
        "SELECT id, assignment_code, classroom_id, title, city, start_cash, duration_days, "
        "COALESCE(sprint_minutes_per_day, 2) AS sprint_minutes_per_day, is_active, created_at "
        "FROM assignments",
    )
    students = rows(
        conn,
        "SELECT id, student_id, first_name, last_name, school_email, is_active, created_at "
        "FROM student_profiles",
    )
    memberships = rows(
        conn,
        "SELECT student_id_fk, classroom_id, status, created_at FROM student_class_memberships",
    )
    sessions = rows(
        conn,
        "SELECT session_id, student_id, player_name, city, day, cash, tax_reserve, debt, stress, "
        "status, score, created_at, updated_at FROM game_sessions",
    )
    session_logs = rows(
        conn,
        "SELECT id, session_id, day, gross_income, platform_fees, variable_costs, household_costs, "
        "tax_reserve, event_title, event_text, event_cash_impact, end_cash, created_at FROM game_day_logs",
    )
    enrollments = rows(
        conn,
        "SELECT assignment_id, session_id, created_at FROM assignment_enrollments",
    )
    strategy_sessions = rows(
        conn,
        "SELECT session_id, student_id, class_code, assignment_code, is_class_assignment, player_name, "
        "current_day, total_days, assignment_minutes, status, total_profit, optimal_profit, selected_count, "
        "current_offers_json, current_day_brief, turned_in_at, created_at, updated_at "
        "FROM strategy_sessions",
    )
    strategy_decisions = rows(
        conn,
        "SELECT id, session_id, day, chosen_offer_id, chosen_offer_title, chosen_profit, optimal_profit, "
        "offers_json, day_brief, created_at FROM strategy_decisions",
    )
    deleted_entities = rows(
        conn,
        "SELECT id, entity_type, entity_key, payload_json, deleted_at FROM deleted_entities",
    )
    audit_events = rows(
        conn,
        "SELECT id, actor, action, target_type, target_key, detail_json, created_at FROM audit_events",
    )

    class_id_to_code = {int(r["id"]): str(r["class_code"]).upper() for r in classrooms}
    assign_id_to_code = {int(r["id"]): str(r["assignment_code"]).upper() for r in assignments}
    assignment_code_to_class = {
        str(r["assignment_code"]).upper(): class_id_to_code.get(int(r["classroom_id"]), "")
        for r in assignments
    }
    student_fk_to_public_id = {int(r["id"]): str(r["student_id"]).upper() for r in students}
    session_to_assignment_code: dict[str, str] = {}
    for e in enrollments:
        acode = assign_id_to_code.get(int(e["assignment_id"]), "")
        sid = str(e["session_id"])
        if acode and sid:
            session_to_assignment_code[sid] = acode

    # Classrooms
    for row in classrooms:
        class_code = str(row["class_code"]).upper()
        client.collection("classrooms").document(class_code).set(
            {
                "class_code": class_code,
                "class_name": str(row["class_name"] or "").strip(),
                "created_at": parse_dt(row["created_at"]),
            }
        )

    # Assignments
    for row in assignments:
        assignment_code = str(row["assignment_code"]).upper()
        class_code = class_id_to_code.get(int(row["classroom_id"]), "")
        client.collection("assignments").document(assignment_code).set(
            {
                "assignment_code": assignment_code,
                "class_code": class_code,
                "title": str(row["title"] or "").strip(),
                "city": str(row["city"] or "Charlotte, NC"),
                "start_cash": float(row["start_cash"] or 0.0),
                "duration_days": int(row["duration_days"] or 30),
                "sprint_minutes_per_day": int(row["sprint_minutes_per_day"] or 2),
                "is_active": bool(row["is_active"]),
                "created_at": parse_dt(row["created_at"]),
            }
        )

    # Students
    for row in students:
        student_id = str(row["student_id"]).upper()
        first_name = str(row["first_name"] or "").strip() or "Student"
        last_name = str(row["last_name"] or "").strip() or "User"
        email = str(row["school_email"] or "").strip().lower()
        client.collection("students").document(student_id).set(
            {
                "student_id": student_id,
                "first_name": first_name,
                "last_name": last_name,
                "school_email": email,
                "is_active": bool(row["is_active"]),
                "created_at": parse_dt(row["created_at"]),
            }
        )

    # Memberships
    for row in memberships:
        class_code = class_id_to_code.get(int(row["classroom_id"]), "")
        student_id = student_fk_to_public_id.get(int(row["student_id_fk"]), "")
        if not class_code or not student_id:
            continue
        doc_id = f"{class_code}_{student_id}"
        client.collection("memberships").document(doc_id).set(
            {
                "class_code": class_code,
                "student_id": student_id,
                "status": str(row["status"] or "active"),
                "created_at": parse_dt(row["created_at"]),
            }
        )

    # Game sessions
    for row in sessions:
        sid = str(row["session_id"])
        assignment_code = session_to_assignment_code.get(sid, "")
        class_code = assignment_code_to_class.get(assignment_code, "")
        client.collection("game_sessions").document(sid).set(
            {
                "session_id": sid,
                "student_id": (str(row["student_id"]).upper() if row["student_id"] else None),
                "player_name": str(row["player_name"] or "").strip() or "Student",
                "city": str(row["city"] or "Charlotte, NC"),
                "day": int(row["day"] or 1),
                "cash": float(row["cash"] or 0.0),
                "tax_reserve": float(row["tax_reserve"] or 0.0),
                "debt": float(row["debt"] or 0.0),
                "stress": int(row["stress"] or 0),
                "status": str(row["status"] or "active"),
                "score": int(row["score"] or 0),
                "class_code": class_code or None,
                "assignment_code": assignment_code or None,
                "created_at": parse_dt(row["created_at"]),
                "updated_at": parse_dt(row["updated_at"]),
            }
        )

    # Game day logs
    for row in session_logs:
        log_id = str(int(row["id"]))
        client.collection("game_day_logs").document(log_id).set(
            {
                "id": int(row["id"]),
                "session_id": str(row["session_id"]),
                "day": int(row["day"] or 1),
                "gross_income": float(row["gross_income"] or 0.0),
                "platform_fees": float(row["platform_fees"] or 0.0),
                "variable_costs": float(row["variable_costs"] or 0.0),
                "household_costs": float(row["household_costs"] or 0.0),
                "tax_reserve": float(row["tax_reserve"] or 0.0),
                "event_title": str(row["event_title"] or ""),
                "event_text": str(row["event_text"] or ""),
                "event_cash_impact": float(row["event_cash_impact"] or 0.0),
                "end_cash": float(row["end_cash"] or 0.0),
                "created_at": parse_dt(row["created_at"]),
            }
        )

    # Strategy sessions
    for row in strategy_sessions:
        sid = str(row["session_id"])
        client.collection("strategy_sessions").document(sid).set(
            {
                "session_id": sid,
                "student_id": (str(row["student_id"]).upper() if row["student_id"] else None),
                "class_code": (str(row["class_code"]).upper() if row["class_code"] else None),
                "assignment_code": (str(row["assignment_code"]).upper() if row["assignment_code"] else None),
                "is_class_assignment": bool(row["is_class_assignment"]),
                "player_name": str(row["player_name"] or "Student"),
                "current_day": int(row["current_day"] or 1),
                "total_days": int(row["total_days"] or 30),
                "assignment_minutes": int(row["assignment_minutes"] or 60),
                "status": str(row["status"] or "active"),
                "total_profit": float(row["total_profit"] or 0.0),
                "optimal_profit": float(row["optimal_profit"] or 0.0),
                "selected_count": int(row["selected_count"] or 0),
                "current_offers_json": str(row["current_offers_json"] or "[]"),
                "current_day_brief": str(row["current_day_brief"] or ""),
                "turned_in_at": parse_dt(row["turned_in_at"]) if row["turned_in_at"] else None,
                "created_at": parse_dt(row["created_at"]),
                "updated_at": parse_dt(row["updated_at"]),
            }
        )

    # Strategy decisions
    for row in strategy_decisions:
        decision_id = str(int(row["id"]))
        client.collection("strategy_decisions").document(decision_id).set(
            {
                "id": int(row["id"]),
                "session_id": str(row["session_id"]),
                "day": int(row["day"] or 1),
                "chosen_offer_id": str(row["chosen_offer_id"] or ""),
                "chosen_offer_title": str(row["chosen_offer_title"] or ""),
                "chosen_profit": float(row["chosen_profit"] or 0.0),
                "optimal_profit": float(row["optimal_profit"] or 0.0),
                "offers_json": str(row["offers_json"] or "[]"),
                "day_brief": str(row["day_brief"] or ""),
                "created_at": parse_dt(row["created_at"]),
            }
        )

    # Deleted entities
    max_deleted_id = 0
    for row in deleted_entities:
        entity_id = int(row["id"])
        max_deleted_id = max(max_deleted_id, entity_id)
        client.collection("deleted_entities").document(str(entity_id)).set(
            {
                "id": entity_id,
                "entity_type": str(row["entity_type"] or ""),
                "entity_key": str(row["entity_key"] or ""),
                "payload_json": str(row["payload_json"] or "{}"),
                "deleted_at": parse_dt(row["deleted_at"]),
            }
        )

    # Audit events
    max_audit_id = 0
    for row in audit_events:
        event_id = int(row["id"])
        max_audit_id = max(max_audit_id, event_id)
        client.collection("audit_events").document(str(event_id)).set(
            {
                "id": event_id,
                "actor": str(row["actor"] or "teacher"),
                "action": str(row["action"] or ""),
                "target_type": str(row["target_type"] or ""),
                "target_key": str(row["target_key"] or ""),
                "detail_json": str(row["detail_json"] or "{}"),
                "created_at": parse_dt(row["created_at"]),
            }
        )

    client.collection("_meta").document("counters").set(
        {
            "deleted_entities": max_deleted_id,
            "audit_events": max_audit_id,
        },
        merge=True,
    )

    conn.close()
    return {
        "classrooms": len(classrooms),
        "assignments": len(assignments),
        "students": len(students),
        "memberships": len(memberships),
        "game_sessions": len(sessions),
        "game_day_logs": len(session_logs),
        "strategy_sessions": len(strategy_sessions),
        "strategy_decisions": len(strategy_decisions),
        "deleted_entities": len(deleted_entities),
        "audit_events": len(audit_events),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate local SQLite data into Firestore collections.")
    parser.add_argument(
        "--sqlite-path",
        default="backend/financegame.db",
        help="Path to sqlite database file (default: backend/financegame.db)",
    )
    parser.add_argument(
        "--project-id",
        default="",
        help="Firebase/GCP project id (optional if default credentials already scoped)",
    )
    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="Delete existing Firestore collections used by this app before importing.",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path).expanduser().resolve()
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite file not found: {sqlite_path}")

    counts = migrate(
        sqlite_path=sqlite_path,
        project_id=args.project_id.strip() or None,
        clear_first=bool(args.clear_first),
    )
    print("Migration complete.")
    for key, value in counts.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
