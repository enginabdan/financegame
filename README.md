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
- Database: Postgres on Render (SQLite fallback in local dev if `DATABASE_URL` is not set)
- AI layer: OpenAI API (optional fallback-safe)
- Deployment target: Render (backend + static site)
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
- `POST /api/advance-day`
- `GET /api/teacher/overview` (header: `x-teacher-key`)
- `GET /api/teacher/sessions` (header: `x-teacher-key`)
- `GET /api/teacher/sessions/{session_id}/logs` (header: `x-teacher-key`)

## Documents

- `docs/game-design.md`
- `docs/architecture.md`

## Status

Iteration 2: persistent sessions + teacher dashboard endpoints + Render Postgres wiring.
