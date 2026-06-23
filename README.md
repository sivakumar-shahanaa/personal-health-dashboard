# Biometric Cycle Optimizer

A personal dashboard that correlates Apple Watch / Apple Health biometrics
(HRV, resting heart rate, sleep, steps) with manually logged cycle data, to
help spot patterns between physical recovery and hormonal cycle phases.

This is a personal tool built to run locally, with safeguards so real
health data never leaves your machine or gets committed to this repo.

## Goals

- Ingest biometric data exported from Apple Watch / Apple Health
- Correlate it with manually logged cycle symptoms
- Surface trends and recovery patterns, with AI-assisted insights when available

## Project structure

```
backend/
  app/
    main.py          FastAPI server entrypoint, /api/data endpoint
    routes.py         /api/v1/specialized-sync ingestion endpoint
    models.py          SQLAlchemy table definitions
    database.py         DB connection setup
  .streamlit/
    config.toml         Streamlit theme (colors, fonts)
  frontend.py            Streamlit dashboard (the actual UI)
  insights.py             AI / rule-based insight generation
  load_data.py             Loads demo or personal data into the DB
  test_sync.py               Sends a fake payload to the ingestion endpoint
  demo_data.json               Fake data, safe to commit, used by default
  my_data.json.example           Template for your real data (gitignored once renamed)
  analytics.db                    SQLite database (gitignored)
  requirements.txt
```

There is no separate frontend framework here — the dashboard is built
entirely in Streamlit (`frontend.py`), which is plain Python and runs
directly alongside the backend.

## Data Ingestion Pipeline

```
Apple Watch / iPhone Health  →  Autoexport-style export  →
  POST /api/v1/specialized-sync  →  SQLite (analytics.db)  →  Streamlit dashboard
```

## Demo data vs. your real data

To make this safe to share on GitHub, the dashboard never assumes real
personal data is present:

- `demo_data.json` : fake, fixed-seed data, committed to the repo. Anyone
  cloning this project gets a working demo with zero setup.
- `my_data.json` : your real exported data. **Never committed** (see
  `.gitignore`). If this file exists locally, `load_data.py` uses it instead
  of the demo data automatically.

To load demo data (or your own, once you have it):

```bash
cd backend
python load_data.py
```

## AI Insights

The "Automated Insights Layer" section analyzes your selected metric and
writes a short insight. It works in two modes:

- **AI mode** — if `ANTHROPIC_API_KEY` is set (in a local `.env` file) and
  has credit, insights are written by Claude based on summary statistics
  (never raw data).
- **Rule-based fallback** — if no key is set, or the API is unreachable for
  any reason, insights are generated locally for free using threshold rules
  on the same statistics. No code changes needed to switch between the two —
  it upgrades automatically the moment a working key is in place.

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy, SQLite
- **Dashboard:** Streamlit, Altair (charts), Pandas
- **AI Insights:** Anthropic API (`anthropic` Python SDK), with a local
  rule-based fallback
- **Data ingestion:** designed for Autoexport / Health Auto Export-style
  JSON payloads from Apple Watch and Apple Health

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# load demo data (or your own, once exported)
python load_data.py

# (optional) enable AI insights
cp .env.example .env
# then edit .env and add your ANTHROPIC_API_KEY

# start the dashboard
streamlit run frontend.py
```

The FastAPI ingestion server (`/api/v1/specialized-sync`) is only needed if
you're sending live data from a real export — for local testing or demo
purposes, `load_data.py` is enough on its own.

To test ingestion manually with fake data:

```bash
uvicorn app.main:app --reload --port 8000
# in another terminal:
python test_sync.py
```

## Privacy notes

The following are gitignored and will never be committed:
- `my_data.json` — your real exported health data
- `analytics.db` — the local database (may contain real data once loaded)
- `.env` — your Anthropic API key
