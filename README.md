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
- Database: SQLite by default (`backend/financegame.db`), Postgres optional via `DATABASE_URL`
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

## Environment Variables

See `.env.example`.

- `OPENAI_API_KEY`: optional but recommended
- `OPENAI_MODEL`: default `gpt-5-mini`
- `ALLOWED_ORIGINS`: frontend origins allowed to call API
- `DATABASE_URL`: Render Postgres connection string
- `TEACHER_API_KEY`: required for teacher endpoints

If `OPENAI_API_KEY` is missing, gameplay still works with deterministic fallback events.

## API Surface

- `GET /health`
- `POST /api/new-game`
- `POST /api/student/join-assignment`
- `POST /api/advance-day`
- `POST /api/teacher/classes` (header: `x-teacher-key`)
- `GET /api/teacher/classes` (header: `x-teacher-key`)
- `POST /api/teacher/assignments` (header: `x-teacher-key`)
- `GET /api/teacher/assignments` (header: `x-teacher-key`)
- `GET /api/teacher/overview` (header: `x-teacher-key`)
- `GET /api/teacher/sessions` (header: `x-teacher-key`)
- `GET /api/teacher/sessions/{session_id}/logs` (header: `x-teacher-key`)

## Classroom Flow

1. Teacher opens `/teacher.html`, enters API base URL and `TEACHER_API_KEY`.
2. Teacher creates a class and gets a `CLASS_CODE`.
3. Teacher creates an assignment under that class and gets an `ASSIGNMENT_CODE`.
4. Student opens the game page and starts either:
   - Free play (leave codes empty), or
   - Classroom run (enter both class + assignment code).
5. Teacher dashboard shows all sessions and per-day logs in real time.

## Documents

- `docs/game-design.md`
- `docs/architecture.md`

## Status

Iteration 3: class/assignment flow + stronger daily simulation economics + teacher setup panel.
