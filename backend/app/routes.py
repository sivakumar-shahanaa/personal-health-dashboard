# catches the export app data and writes it to the database

from fastapi import APIRouter, HTTPException, Header, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models import BiometricStream, CycleLog

router = APIRouter()
LOCAL_SECRET_KEY = "my_health_dashboard_token"


@router.post("/api/v1/specialized-sync")
async def ingest_specialized_data(
    payload: dict,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db)
):
    # Security Access Gatekeeper
    # (was static_code -- that typo caused the server to crash on any bad auth attempt)
    if x_api_key != LOCAL_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key Header Secret")

    biometrics = payload.get("biometrics", [])
    cycle_logs = payload.get("cycle_logs", [])

    saved_biometrics = 0
    skipped_biometrics = 0

    # Process the Apple Watch biometric array
    for b in biometrics:
        t = datetime.fromisoformat(b.get("timestamp").replace("Z", "+00:00"))
        # strip timezone info so it stores cleanly in SQLite as a naive datetime
        t = t.replace(tzinfo=None)

        # dedup check: skip if this exact (timestamp, metric_type) already exists
        existing = db.query(BiometricStream).filter(
            BiometricStream.timestamp == t,
            BiometricStream.metric_type == b.get("metric")
        ).first()

        if existing:
            skipped_biometrics += 1
            continue

        db.add(BiometricStream(
            timestamp=t,
            metric_type=b.get("metric"),
            value=float(b.get("value"))
        ))
        saved_biometrics += 1

    saved_logs = 0
    skipped_logs = 0

    # Process the CycleLog data
    for log in cycle_logs:
        t = datetime.strptime(log.get("date"), "%Y-%m-%d").date()

        # dedup: one entry per date maximum
        existing_log = db.query(CycleLog).filter(CycleLog.date == t).first()
        if existing_log:
            skipped_logs += 1
            continue

        db.add(CycleLog(
            date=t,
            period_start=log.get("period_start", False),
            abdominal_pain_severity=int(log.get("cramps_severity") or 0)
        ))
        saved_logs += 1

    # permanently write to analytics.db
    db.commit()

    return {
        "status": "success",
        "saved_biometrics": saved_biometrics,
        "skipped_biometrics_duplicates": skipped_biometrics,
        "saved_logs": saved_logs,
        "skipped_logs_duplicates": skipped_logs,
    }