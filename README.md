# Landed

Landed is an AI job search command center for a live demo flow: paste a job post, edit a track-specific resume, watch ATS and hiring-manager scores update, log the application, then prep with Jordan voice coaching.

## What It Does

- Split-screen analyzer for job post plus editable resume
- Two seeded position tracks with per-track base resumes
- Live ATS and HM scoring with analysis panels
- Application tracker with track filtering and status badges
- Jordan prep sessions with cached first-question audio and push-back on vague answers

## Local Run

1. Create a virtual environment and install requirements:
   `python -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt`
2. Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` if you want live Claude analysis.
3. Run the app:
   `cd backend && uvicorn main:app --reload --port 8000`
4. Open `http://127.0.0.1:8000`

## Test

Run everything with:

`pytest`

## Render Deploy

- Repo root build command: `pip install -r backend/requirements.txt`
- Repo root start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- Required environment variable: `ANTHROPIC_API_KEY`

The checked-in `render.yaml` and `Procfile` match this layout.
