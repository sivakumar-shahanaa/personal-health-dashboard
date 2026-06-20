import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("/Users/shahanaa/Desktop/bco/backend/analytics.db")
cursor = conn.cursor()

# Clear out previous single test rows if you want a clean slate
cursor.execute("DELETE FROM biometrics")
cursor.execute("DELETE FROM cycle_logs")

# Generate 5 days of metrics
base_time = datetime.utcnow() - timedelta(days=5)

metrics_to_seed = [
    # Day 1
    ( (base_time + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), "Resting Heart Rate", 65.0 ),
    ( (base_time + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), "HRV", 45.0 ),
    # Day 2
    ( (base_time + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"), "Resting Heart Rate", 68.0 ),
    ( (base_time + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"), "HRV", 42.0 ),
    # Day 3
    ( (base_time + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"), "Resting Heart Rate", 62.0 ),
    ( (base_time + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"), "HRV", 55.0 ),
    # Day 4
    ( (base_time + timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S"), "Resting Heart Rate", 71.0 ),
    ( (base_time + timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S"), "HRV", 38.0 ),
    # Day 5
    ( (base_time + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"), "Resting Heart Rate", 64.0 ),
    ( (base_time + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"), "HRV", 50.0 ),
]

for ts, m_type, val in metrics_to_seed:
    cursor.execute(
        "INSERT INTO biometrics (timestamp, metric_type, value) VALUES (?, ?, ?)",
        (ts, m_type, val)
    )

# Seed a couple manual symptom cycle entries as well
cursor.execute(
    "INSERT INTO cycle_logs (date, period_start, abdominal_pain_severity) VALUES (?, ?, ?)",
    ((base_time + timedelta(days=2)).strftime("%Y-%m-%d"), True, 4)
)
cursor.execute(
    "INSERT INTO cycle_logs (date, period_start, abdominal_pain_severity) VALUES (?, ?, ?)",
    ((base_time + timedelta(days=3)).strftime("%Y-%m-%d"), False, 2)
)

conn.commit()
conn.close()
print("Database successfully seeded with historical trends!")