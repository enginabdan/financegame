# Hustle & Home: Charlotte 30

A web-based, AI-assisted personal finance simulation for U.S. high school classrooms.

Players manage one month of life as a gig worker and online seller in Charlotte, NC while supporting a family of four.

## Learning Goals

- Build budgeting and cash-flow discipline
- Understand taxes, commissions, and hidden business costs
- Compare opportunity cost across multiple income streams
- Make short-term vs. long-term tradeoffs under uncertainty
- Evaluate household financial resilience over 30 days

## Core Scenario

The player simultaneously manages:

- Gig driving (Uber-like work)
- Delivery routes (Amazon/Walmart-style shifts)
- Online selling (Amazon, Etsy, Walmart Marketplace)
- Daily financial decisions on insurance, car actions, and emergency-fund contributions

Household context includes:

- Rent and utilities
- Car ownership and maintenance risk
- Two student children
- Spouse not currently employed
- Health insurance via marketplace
- Tax and platform fee exposure

## Tech Stack

- Frontend: Vanilla HTML/CSS/JS
- Backend: FastAPI (Python)
- Database: Firestore (recommended for persistence) or SQLite fallback (`backend/financegame.db`)
- AI layer: OpenAI API (optional fallback-safe)
- Deployment target: Firebase Hosting (frontend) + Google Cloud Run (backend)
- Domain target: GoDaddy-managed domain (e.g., bosembo.net)
- School landing page: Google Sites linking into the game

## Quick Start

### 1) Backend

```bash
cd backend
# Python 3.14 recommended for this project:
/Users/engin/.local/python-3.14.3/bin/python3.14 -m venv .venv314
source .venv314/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000
```

### 2) Frontend

```bash
cd frontend
python3 -m http.server 4173
```

### 3) One Command Dev Mode

```bash
./dev.sh
```

Student game: `http://127.0.0.1:4173`
Teacher dashboard: `http://127.0.0.1:4173/teacher.html`
Sprint module: included in the main student page (`/`)

## Environment Variables

See `.env.example`.

- `OPENAI_API_KEY`: optional but recommended
- `OPENAI_MODEL`: default `gpt-5-mini`
- `ALLOWED_ORIGINS`: frontend origins allowed to call API
- `USE_FIRESTORE`: set `1` to persist data in Firestore (recommended)
- `FIREBASE_PROJECT_ID`: Firebase/GCP project id for Firestore client
- `FIREBASE_STORAGE_BUCKET`: Firebase Storage bucket (example `financegame-78d26.appspot.com`)
- `GOOGLE_APPLICATION_CREDENTIALS`: local service-account JSON path (optional on Cloud Run)
- `USE_FIREBASE_AUTH`: set `1` to require Firebase login token on student endpoints
- `TEACHER_API_KEY`: required for teacher endpoints
- `DATABASE_URL`: optional if using SQL mode instead of Firestore

If `OPENAI_API_KEY` is missing, gameplay still works with deterministic fallback events.

## Firebase Setup (Recommended)

1. Firebase Console:
- Enable **Firestore Database** (Native mode).
- Enable **Authentication -> Email/Password**.

2. Frontend runtime config:
- Edit `frontend/runtime-config.js` and set:
  - `FIREBASE_WEB_API_KEY` = your Firebase Web API key.
  - `API_BASE` = your backend URL (for production `https://api.bosembo.net`).

3. Cloud Run environment variables:
- `USE_FIRESTORE=1`
- `FIREBASE_PROJECT_ID=your-project-id`
- `USE_FIREBASE_AUTH=1`
- `OPENAI_API_KEY=...`
- `TEACHER_API_KEY=...`
- `ALLOWED_ORIGINS=https://play.bosembo.net,https://financegame-78d26.web.app`

4. IAM for Cloud Run service account:
- Grant `Cloud Datastore User` (or equivalent Firestore read/write role) so backend can read/write Firestore.
- Grant `Storage Object Admin` (or equivalent bucket read/write role) for evidence file upload/download/delete.

5. Deploy:
- Backend: Cloud Run new revision
- Frontend: `firebase deploy --only hosting`

## Firebase Storage (Student Evidence)

Student upload flow:
- Student uploads screenshot/receipt from `/` -> **Upload Evidence**.
- File is saved in Firebase Storage under `evidence/{student_id}/...`.
- Metadata is stored in Firestore collection `student_evidence`.

Teacher review flow:
- Teacher opens `/teacher.html` -> **Student Evidence (Firebase Storage)**.
- Filter by class / assignment / student, then download or delete submissions.

## One-Time Migration: SQLite -> Firestore

If you already have local SQLite data and want to keep it in Firebase:

```bash
cd /Users/engin/D/mygithub/financegame
source backend/.venv314/bin/activate
python backend/scripts/migrate_sqlite_to_firestore.py \
  --sqlite-path backend/financegame.db \
  --project-id financegame-78d26
```

Optional reset import:

```bash
python backend/scripts/migrate_sqlite_to_firestore.py \
  --sqlite-path backend/financegame.db \
  --project-id financegame-78d26 \
  --clear-first
```

## Firestore Operations (Backup / Restore / Health)

Export backup JSON:

```bash
cd /Users/engin/D/mygithub/financegame
source backend/.venv314/bin/activate
python backend/scripts/firestore_backup_json.py \
  --project-id financegame-78d26
```

Restore from backup JSON:

```bash
python backend/scripts/firestore_restore_json.py \
  --project-id financegame-78d26 \
  --input backend/backups/firestore-backup-YYYYMMDD-HHMMSS.json
```

Restore and replace existing data:

```bash
python backend/scripts/firestore_restore_json.py \
  --project-id financegame-78d26 \
  --input backend/backups/firestore-backup-YYYYMMDD-HHMMSS.json \
  --clear-first
```

Quick health check:

```bash
python backend/scripts/firestore_health_check.py \
  --project-id financegame-78d26
```

## API Surface

- `GET /health`
- `POST /api/new-game`
- `POST /api/student/register`
- `POST /api/student/join-class`
- `GET /api/student/me/classes`
- `GET /api/student/classes/{class_code}/assignments?student_id=...`
- `POST /api/student/join-assignment`
- `POST /api/advance-day`
- `POST /api/strategy/start`
- `POST /api/strategy/choose`
- `GET /api/strategy/{session_id}`
- `GET /api/strategy/{session_id}/result`
- `POST /api/teacher/classes` (header: `x-teacher-key`)
- `GET /api/teacher/classes` (header: `x-teacher-key`)
- `GET /api/teacher/classes/{class_code}/students` (header: `x-teacher-key`)
- `DELETE /api/teacher/classes/{class_code}/students/{student_id}` (header: `x-teacher-key`)
- `PATCH /api/teacher/classes/{class_code}` (header: `x-teacher-key`)
- `DELETE /api/teacher/classes/{class_code}` (header: `x-teacher-key`)
- `POST /api/teacher/assignments` (header: `x-teacher-key`)
- `GET /api/teacher/assignments` (header: `x-teacher-key`)
- `PATCH /api/teacher/assignments/{assignment_code}` (header: `x-teacher-key`)
- `DELETE /api/teacher/assignments/{assignment_code}` (header: `x-teacher-key`)
- `GET /api/teacher/assignments/{assignment_code}/rubric` (header: `x-teacher-key`)
- `GET /api/teacher/overview` (header: `x-teacher-key`)
- `GET /api/teacher/sessions` (header: `x-teacher-key`)
- `GET /api/teacher/sessions/{session_id}/logs` (header: `x-teacher-key`)
- `PATCH /api/teacher/sessions/{session_id}` (header: `x-teacher-key`)
- `DELETE /api/teacher/sessions/{session_id}` (header: `x-teacher-key`)
- `GET /api/teacher/strategy/leaderboard` (header: `x-teacher-key`)
- `GET /api/teacher/strategy/sessions/{session_id}` (header: `x-teacher-key`)
- `DELETE /api/teacher/strategy/sessions/{session_id}` (header: `x-teacher-key`)
- `POST /api/teacher/sessions/bulk-delete` (header: `x-teacher-key`)
- `POST /api/teacher/strategy/sessions/bulk-delete` (header: `x-teacher-key`)
- `GET /api/teacher/trash` (header: `x-teacher-key`)
- `POST /api/teacher/trash/{archive_id}/restore` (header: `x-teacher-key`)
- `POST /api/teacher/trash/bulk-restore` (header: `x-teacher-key`)
- `POST /api/teacher/trash/purge` (header: `x-teacher-key`)
- `POST /api/teacher/trash/purge-older` (header: `x-teacher-key`)
- `GET /api/teacher/audit` (header: `x-teacher-key`)
- `GET /api/teacher/risk-alerts` (header: `x-teacher-key`)

## Classroom Flow

1. Teacher opens `/teacher.html`, enters API base URL and `TEACHER_API_KEY`.
2. Teacher creates a class and gets a `CLASS_CODE`.
3. Teacher creates an assignment under that class and gets an `ASSIGNMENT_CODE`.
4. Student opens `/`, creates a student profile (gets `STUDENT_ID`), and joins class using `CLASS_CODE`.
5. Student loads only their joined classes and active assignments, then starts assignment run.
6. Teacher dashboard shows all sessions and per-day logs in real time.
7. Teacher can open assignment rubric and export sessions/day-logs as CSV.
8. Teacher can edit or delete classes, assignments, and sessions directly in dashboard cards.
9. Teacher can remove students from class rosters when needed.
10. Teacher can inspect full sprint decision history (all offered options, selected option, optimal benchmark gap) and delete sprint sessions if needed.

## Documents

- `docs/game-design.md`
- `docs/architecture.md`

## Status

Iteration 4: full teacher data management (edit/delete class-assignment-session) + sprint decision audit view.
