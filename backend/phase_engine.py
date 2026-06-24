"""
phase_engine.py

The core analysis engine. Run this after load_data.py to populate the
daily_insights table with phase assignments, predicted next period dates,
per-phase biometric averages, and human-readable alert text.

Usage:
    python phase_engine.py

How it works:
    1. Reads all period_start=True dates from cycle_logs to build a cycle history
    2. Computes average cycle length from that history
    3. Assigns every date in the database a cycle phase:
          menstrual  = days 1-5
          follicular = days 6-13
          ovulatory  = days 14-16
          luteal     = days 17-end
    4. Bins every biometric reading by phase and computes per-phase averages
    5. Predicts the next period date = last period + avg cycle length
    6. Writes one DailyInsight row per date, including a plain-English alert
       comparing phase averages to overall averages
    7. Re-running this script is safe -- it wipes and rewrites daily_insights
       from scratch each time, so it stays in sync with your latest data
"""

import numpy as np
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.database import engine, Base, SessionLocal
from app.models import BiometricStream, CycleLog, DailyInsight

# ---------------------------------------------------------------------------
# PHASE DEFINITIONS
# ---------------------------------------------------------------------------

PHASES = {
    "menstrual":  (1, 5),
    "follicular": (6, 13),
    "ovulatory":  (14, 16),
    "luteal":     (17, 99),   # ends at cycle end, however long that is
}

PHASE_COLORS = {
    "menstrual":  "#B5563C",
    "follicular": "#2D5A3D",
    "ovulatory":  "#D9A441",
    "luteal":     "#4A6FA5",
    "unknown":    "#CCCCCC",
}

METRIC_DB_NAMES = {
    "hrv":   "HRV",
    "rhr":   "Resting Heart Rate",
    "sleep": "Sleep Quality Index",
    "steps": "Steps",
}


# ---------------------------------------------------------------------------
# STEP 1: CYCLE HISTORY
# ---------------------------------------------------------------------------

def get_period_start_dates(db: Session) -> list[date]:
    """Return all dates where period_start=True, sorted ascending."""
    rows = (
        db.query(CycleLog)
        .filter(CycleLog.period_start == True)
        .order_by(CycleLog.date)
        .all()
    )
    return [r.date for r in rows]


def compute_avg_cycle_length(period_dates: list[date]) -> float:
    """
    Average number of days between consecutive period starts.
    Falls back to 28 if we don't have enough history.
    """
    if len(period_dates) < 2:
        return 28.0
    gaps = [
        (period_dates[i + 1] - period_dates[i]).days
        for i in range(len(period_dates) - 1)
    ]
    # filter out implausible gaps (< 18 or > 45 days) before averaging
    valid = [g for g in gaps if 18 <= g <= 45]
    return float(np.mean(valid)) if valid else 28.0


# ---------------------------------------------------------------------------
# STEP 2: PHASE ASSIGNMENT
# ---------------------------------------------------------------------------

def assign_phase(cycle_day: int) -> str:
    """Map a cycle day number to a phase name."""
    for phase, (start, end) in PHASES.items():
        if start <= cycle_day <= end:
            return phase
    return "luteal"  # past day 16 but no next period yet


def get_cycle_day_and_phase(target_date: date, period_dates: list[date]) -> tuple[int, str]:
    """
    Return (cycle_day, phase_name) for a given calendar date.
    cycle_day is 1-indexed from the most recent period start on or before the date.
    """
    past_starts = [d for d in period_dates if d <= target_date]
    if not past_starts:
        return 0, "unknown"
    last_period = max(past_starts)
    cycle_day = (target_date - last_period).days + 1
    return cycle_day, assign_phase(cycle_day)


# ---------------------------------------------------------------------------
# STEP 3: BIOMETRIC PHASE AVERAGES
# ---------------------------------------------------------------------------

def get_all_biometrics(db: Session) -> dict[str, list[tuple[date, float]]]:
    """
    Return all biometric readings as {metric_type: [(date, value), ...]}
    """
    rows = db.query(BiometricStream).all()
    result: dict[str, list] = {}
    for r in rows:
        key = r.metric_type
        d = r.timestamp.date()
        result.setdefault(key, []).append((d, r.value))
    return result


def compute_phase_averages(
    biometrics: dict[str, list[tuple[date, float]]],
    date_to_phase: dict[date, str],
) -> dict[str, dict[str, float]]:
    """
    Returns {metric_type: {phase_name: avg_value}}.
    Uses NumPy mean across all readings for that metric during that phase.
    """
    result: dict[str, dict[str, float]] = {}

    for metric, readings in biometrics.items():
        phase_buckets: dict[str, list[float]] = {p: [] for p in PHASES}
        phase_buckets["unknown"] = []

        for d, val in readings:
            phase = date_to_phase.get(d, "unknown")
            phase_buckets.setdefault(phase, []).append(val)

        result[metric] = {}
        for phase, vals in phase_buckets.items():
            if vals:
                result[metric][phase] = float(np.mean(vals))

    return result


def compute_overall_averages(
    biometrics: dict[str, list[tuple[date, float]]]
) -> dict[str, float]:
    """Overall average per metric across all phases."""
    return {
        metric: float(np.mean([v for _, v in readings]))
        for metric, readings in biometrics.items()
        if readings
    }


# ---------------------------------------------------------------------------
# STEP 4: ALERT TEXT GENERATION
# ---------------------------------------------------------------------------

def generate_alert_text(
    phase: str,
    cycle_day: int,
    phase_avgs: dict[str, dict[str, float]],
    overall_avgs: dict[str, float],
    predicted_next_period: date | None,
) -> str:
    """
    Build a plain-English alert comparing the current phase's biometric
    averages to overall averages. Flags metrics that differ by >= 8%.
    """
    if phase == "unknown":
        return "Not enough cycle history to assign a phase. Log a period start date to activate phase tracking."

    lines = []

    hrv_db = METRIC_DB_NAMES["hrv"]
    rhr_db = METRIC_DB_NAMES["rhr"]
    sleep_db = METRIC_DB_NAMES["sleep"]

    for metric_db, label, direction_word in [
        (hrv_db,   "HRV",               "lower"),   # lower HRV in luteal = bad
        (rhr_db,   "resting heart rate", "higher"),  # higher RHR in luteal = potential fatigue
        (sleep_db, "sleep quality",      "lower"),
    ]:
        phase_avg = phase_avgs.get(metric_db, {}).get(phase)
        overall_avg = overall_avgs.get(metric_db)

        if phase_avg is None or overall_avg is None or overall_avg == 0:
            continue

        pct_diff = ((phase_avg - overall_avg) / overall_avg) * 100

        if abs(pct_diff) >= 8:
            direction = "lower" if pct_diff < 0 else "higher"
            lines.append(
                f"⚠️  {label.capitalize()} averages {abs(pct_diff):.0f}% {direction} "
                f"during your {phase} phase ({phase_avg:.1f} vs overall {overall_avg:.1f})."
            )

    if not lines:
        lines.append(
            f"Your biometrics look consistent across cycle phases — "
            f"no significant dips detected in your {phase} phase data so far."
        )

    # append cycle day and prediction
    lines.append(f"Today is estimated cycle day {cycle_day} ({phase} phase).")
    if predicted_next_period:
        days_away = (predicted_next_period - date.today()).days
        if days_away >= 0:
            lines.append(f"Next period predicted in ~{days_away} day(s) ({predicted_next_period}).")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# STEP 5: WRITE TO daily_insights
# ---------------------------------------------------------------------------

def run(db: Session):
    print("Running phase engine...")

    # ensure tables exist
    Base.metadata.create_all(bind=engine)

    # --- cycle history ---
    period_dates = get_period_start_dates(db)
    avg_cycle_len = compute_avg_cycle_length(period_dates)
    print(f"  Period start dates found: {len(period_dates)}")
    print(f"  Average cycle length: {avg_cycle_len:.1f} days")

    last_period = max(period_dates) if period_dates else None
    predicted_next_period = (
        last_period + timedelta(days=round(avg_cycle_len))
        if last_period else None
    )
    print(f"  Predicted next period: {predicted_next_period}")

    # --- get all biometric dates so we know what dates to write insights for ---
    biometrics = get_all_biometrics(db)
    all_dates: set[date] = set()
    for readings in biometrics.values():
        for d, _ in readings:
            all_dates.add(d)
    # also include any cycle log dates
    for row in db.query(CycleLog).all():
        all_dates.add(row.date)

    print(f"  Unique dates to process: {len(all_dates)}")

    # --- assign phase to every date ---
    date_to_phase: dict[date, str] = {}
    date_to_cycle_day: dict[date, int] = {}
    for d in all_dates:
        cycle_day, phase = get_cycle_day_and_phase(d, period_dates)
        date_to_phase[d] = phase
        date_to_cycle_day[d] = cycle_day

    # --- phase averages and overall averages ---
    phase_avgs = compute_phase_averages(biometrics, date_to_phase)
    overall_avgs = compute_overall_averages(biometrics)

    # helper: safely get a phase avg for a specific metric
    def phase_avg(metric_db: str, phase: str) -> float | None:
        return phase_avgs.get(metric_db, {}).get(phase)

    def overall_avg(metric_db: str) -> float | None:
        return overall_avgs.get(metric_db)

    # --- wipe and rewrite daily_insights ---
    db.query(DailyInsight).delete()
    db.commit()

    rows_written = 0
    for d in sorted(all_dates):
        phase = date_to_phase[d]
        cycle_day = date_to_cycle_day[d]

        alert = generate_alert_text(
            phase, cycle_day, phase_avgs, overall_avgs, predicted_next_period
        )

        db.add(DailyInsight(
            date=d,
            cycle_phase=phase,
            cycle_day=cycle_day,
            predicted_next_period=predicted_next_period,
            hrv_phase_avg=phase_avg(METRIC_DB_NAMES["hrv"], phase),
            rhr_phase_avg=phase_avg(METRIC_DB_NAMES["rhr"], phase),
            sleep_phase_avg=phase_avg(METRIC_DB_NAMES["sleep"], phase),
            steps_phase_avg=phase_avg(METRIC_DB_NAMES["steps"], phase),
            hrv_overall_avg=overall_avg(METRIC_DB_NAMES["hrv"]),
            rhr_overall_avg=overall_avg(METRIC_DB_NAMES["rhr"]),
            sleep_overall_avg=overall_avg(METRIC_DB_NAMES["sleep"]),
            steps_overall_avg=overall_avg(METRIC_DB_NAMES["steps"]),
            insight_text=alert,
        ))
        rows_written += 1

    db.commit()
    print(f"  Wrote {rows_written} rows to daily_insights.")
    print("Phase engine complete.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()