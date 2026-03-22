#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any

from google.cloud import firestore

APP_COLLECTIONS = [
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
]


def as_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick Firestore health check for financegame collections.")
    parser.add_argument("--project-id", default="", help="Firebase/GCP project id (optional)")
    args = parser.parse_args()

    client = firestore.Client(project=(args.project_id.strip() or None)) if args.project_id.strip() else firestore.Client()

    print("Firestore health check")
    print(f"- project: {args.project_id.strip() or '(default creds project)'}")

    total = 0
    newest: datetime | None = None
    newest_label = ""
    for col in APP_COLLECTIONS:
        count = 0
        for doc in client.collection(col).stream():
            count += 1
            data = doc.to_dict() or {}
            for key in ("updated_at", "created_at", "deleted_at"):
                dt = as_dt(data.get(key))
                if dt and (newest is None or dt > newest):
                    newest = dt
                    newest_label = f"{col}/{doc.id}:{key}"
        total += count
        print(f"- {col}: {count}")

    print(f"- total_docs: {total}")
    if newest:
        print(f"- newest_activity: {newest.isoformat()} ({newest_label})")
    else:
        print("- newest_activity: n/a")


if __name__ == "__main__":
    main()

