# catches the export app urls data

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
    if (x_api_key != LOCAL_SECRET_KEY):
        raise HTTPException(static_code = 403, detail = "Invalid API Key Header Secret")
    
    biometrics = payload.get("biometrics", [])
    cycle_logs = payload.get("cycle_logs", [])

    # Process the AppleWatch Array loop
    for b in biometrics:

        t = datetime.fromisoformat(b.get("timestamp").replace("Z", "+00:00"))

        db_b = BiometricStream(
            timestamp = t,
            metric_type = b.get("metric"),
            value = float(b.get("value"))
        )
        db.add(db_b)
    
    # Process the CycleLog Data
    for log in cycle_logs:

        t = datetime.strptime(log.get("date"), "%Y-%m-%d").date()

        existing_log = db.query(CycleLog).filter(CycleLog.date == t).first()
        # if the log is already in thed database, avoids duplicates
        if existing_log:
            continue

        db_log = CycleLog(
            date = t,
            period_start = log.get("period_start", False),
            abdominal_pain_severity = int(log.get("cramps_severity") or 0)
        )
        db.add(db_log)
    
    # permanently writes to the analytics.db file
    db.commit()

    return {
        "status": "success",
        "saved_biometrics": len(biometrics),
        "saved_logs": len(cycle_logs)
    }
