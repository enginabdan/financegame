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


def decode(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return value
    return value


def clear_collections(client: firestore.Client) -> None:
    for col in APP_COLLECTIONS:
        for doc in client.collection(col).stream():
            doc.reference.delete()


def run(project_id: str | None, input_path: Path, clear_first: bool) -> dict[str, int]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    collections = payload.get("collections", {})

    client = firestore.Client(project=project_id) if project_id else firestore.Client()
    if clear_first:
        clear_collections(client)

    counts: dict[str, int] = {}
    for col in APP_COLLECTIONS:
        docs = collections.get(col, []) or []
        written = 0
        for row in docs:
            doc_id = str(row.get("id", "")).strip()
            if not doc_id:
                continue
            data = decode(row.get("data", {}) or {})
            client.collection(col).document(doc_id).set(data)
            written += 1
        counts[col] = written
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore app Firestore collections from JSON backup.")
    parser.add_argument("--project-id", default="", help="Firebase/GCP project id (optional)")
    parser.add_argument("--input", required=True, help="Input backup JSON path")
    parser.add_argument("--clear-first", action="store_true", help="Delete existing app collections before restore")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Backup file not found: {input_path}")

    counts = run(
        project_id=args.project_id.strip() or None,
        input_path=input_path,
        clear_first=bool(args.clear_first),
    )
    print(f"Restore complete from: {input_path}")
    for key in APP_COLLECTIONS:
        print(f"- {key}: {counts.get(key, 0)}")


if __name__ == "__main__":
    main()

