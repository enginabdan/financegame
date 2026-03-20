# Architecture (MVP)

## Overview

The project uses a split architecture:

- Static frontend for UI and interaction flow
- API backend for simulation state transitions
- Optional OpenAI decision/event generation layer

## Components

### Frontend (`frontend/`)

- Displays game state dashboard
- Captures daily allocation decisions
- Calls backend endpoints
- Renders logs and event cards

### Backend (`backend/app/`)

- Owns game rules and score calculations
- Applies taxes, fees, and household expenses
- Produces deterministic fallback events
- Optionally asks OpenAI for dynamic event text and event parameters

### Storage

- SQLAlchemy persistence layer
- Render Postgres in production
- SQLite fallback in local development when `DATABASE_URL` is unset

## API Surface (MVP)

- `GET /health`
- `POST /api/new-game`
- `POST /api/advance-day`
- `GET /api/teacher/overview` (requires `x-teacher-key`)
- `GET /api/teacher/sessions` (requires `x-teacher-key`)
- `GET /api/teacher/sessions/{session_id}/logs` (requires `x-teacher-key`)

## AI Integration

AI is used as a bounded event generator, not an unrestricted game engine.

Guardrails:

- JSON-only event schema expected
- Numeric impact ranges clamped server-side
- Hard floor/ceiling for economic outcomes

If AI is unavailable, deterministic events keep gameplay functional.

## Deployment Plan

### Render

- Web service: FastAPI backend
- Static site: frontend bundle

### Domain

- GoDaddy DNS points to Render services
- Subdomain option:
  - `play.bosembo.net` -> frontend
  - `api.bosembo.net` -> backend

### Google Sites

- Classroom-facing landing page and teacher instructions
- Links into game frontend URL

## Security & Operations

- API key kept in server environment variables only
- CORS restricted to approved frontend domains
- Rate limiting and session throttling (next iteration)
- Basic logging for gameplay analytics and QA

## Next Iterations

1. Teacher assignment codes and class grouping
2. Multi-city cost-of-living modules
3. Expanded policy and insurance scenarios
4. Leaderboards and longitudinal performance analytics
