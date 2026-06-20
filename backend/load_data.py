"""
load_data.py

Run this once before starting the dashboard. It decides which dataset to load
into analytics.db:

    backend/my_data.json exists?
        YES -> loads YOUR real data (this file is gitignored, never uploaded)
        NO  -> loads demo_data.json instead (fake data, safe, ships with repo)

This means:
  - On YOUR computer: rename my_data.json.example to my_data.json, fill it in
    with your real export, and this script will use it automatically.
  - On anyone else's computer (cloned from GitHub): my_data.json won't exist,
    so it falls back to demo_data.json with zero setup required.

Usage:
    python load_data.py
"""

import json
import os
from datetime import datetime

from app.database import SessionLocal, engine, Base
from app.models import BiometricStream, CycleLog

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PERSONAL_DATA_PATH = os.path.join(BACKEND_DIR, "my_data.json")
DEMO_DATA_PATH = os.path.join(BACKEND_DIR, "demo_data.json")


def pick_data_source():
    if os.path.exists(PERSONAL_DATA_PATH):
        print("Found my_data.json -- loading YOUR real data.")
        return PERSONAL_DATA_PATH, "personal"
    print("No my_data.json found -- loading demo_data.json (fake data).")
    return DEMO_DATA_PATH, "demo"


def load_payload(path):
    with open(path, "r") as f:
        return json.load(f)


def clear_existing_data(db):
    # Wipe the tables so re-running this script doesn't pile up duplicates
    # or mix demo data with personal data.
    db.query(BiometricStream).delete()
    db.query(CycleLog).delete()
    db.commit()


def insert_data(db, payload):
    biometrics = payload.get("biometrics", [])
    cycle_logs = payload.get("cycle_logs", [])

    for b in biometrics:
        ts = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        db.add(BiometricStream(
            timestamp=ts,
            metric_type=b["metric"],
            value=float(b["value"])
        ))

    for log in cycle_logs:
        d = datetime.strptime(log["date"], "%Y-%m-%d").date()
        db.add(CycleLog(
            date=d,
            period_start=log.get("period_start", False),
            abdominal_pain_severity=int(log.get("cramps_severity") or 0)
        ))

    db.commit()
    return len(biometrics), len(cycle_logs)


def main():
    # make sure tables exist
    Base.metadata.create_all(bind=engine)

    path, source_type = pick_data_source()
    payload = load_payload(path)

    db = SessionLocal()
    try:
        clear_existing_data(db)
        n_bio, n_logs = insert_data(db, payload)
    finally:
        db.close()

    print(f"Loaded {n_bio} biometric readings and {n_logs} cycle logs "
          f"from {source_type} data into analytics.db")


if __name__ == "__main__":
    main()