#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
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
    "_meta",
]


def encode(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def run(project_id: str | None, output_path: Path) -> dict[str, int]:
    client = firestore.Client(project=project_id) if project_id else firestore.Client()

    payload: dict[str, Any] = {
        "exported_at": datetime.utcnow().isoformat(),
        "project_id": project_id or "",
        "collections": {},
    }
    counts: dict[str, int] = {}

    for col in APP_COLLECTIONS:
        docs: list[dict[str, Any]] = []
        for doc in client.collection(col).stream():
            docs.append({"id": doc.id, "data": encode(doc.to_dict() or {})})
        payload["collections"][col] = docs
        counts[col] = len(docs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Export app Firestore collections to a local JSON backup file.")
    parser.add_argument("--project-id", default="", help="Firebase/GCP project id (optional)")
    parser.add_argument(
        "--output",
        default=f"backend/backups/firestore-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json",
        help="Output backup JSON file path",
    )
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    counts = run(project_id=args.project_id.strip() or None, output_path=output_path)

    print(f"Backup complete: {output_path}")
    for key in APP_COLLECTIONS:
        print(f"- {key}: {counts.get(key, 0)}")


if __name__ == "__main__":
    main()

