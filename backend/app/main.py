# configures and boots the app

import os
from fastapi import FastAPI, Depends
from app.database import engine, Base, get_db
from sqlalchemy.orm import Session
from app.models import BiometricStream, CycleLog

# scans the models.py, makes the Python models into SQL data isntructions, issues to engine
Base.metadata.create_all(bind = engine)

# create the central web server app instance

app = FastAPI(title="Secure Personal Health Dashboard")

@app.get("/api/data")
def get_metrics(db: Session = Depends(get_db)):
    def latest_avg(metric_type):
        rows = db.query(BiometricStream).filter(
            BiometricStream.metric_type == metric_type
        ).order_by(BiometricStream.timestamp.desc()).limit(7).all()
        if not rows:
            return None, None
        latest = rows[0].value
        avg = sum(r.value for r in rows) / len(rows)
        return latest, avg

    hrv_latest, hrv_avg = latest_avg("HRV")
    rhr_latest, rhr_avg = latest_avg("Resting Heart Rate")

    return {
        "status": "success",
        "hrv": {"latest": hrv_latest, "rolling_avg": hrv_avg},
        "rhr": {"latest": rhr_latest, "rolling_avg": rhr_avg},
    }