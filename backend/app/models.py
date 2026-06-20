# clarifies all of the info needed for each metric

from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, Date
from datetime import datetime
from app.database import Base

# For automated Apple Watch records
class BiometricStream(Base):

    __tablename__ = "biometrics"

    id = Column(Integer, primary_key = True, index = True)
    timestamp = Column(DateTime, default = datetime.utcnow, nullable = False)
    # HRV , Resting Heart Rate, Sleep, etc.
    metric_type = Column(String, nullable = False)
    #ensures that all data is a float
    value = Column(Float, nullable = False)

# for manual daily user sympotom entries
class CycleLog(Base):

    __tablename__ = "cycle_logs"

    # index = True creates an internal sorted reference tree
    # makes for O(logN) rather than O(N) search
    
    id = Column(Integer, primary_key = True, index = True)
    # avoids duplicates
    date = Column(Date, unique = True, nullable = False, index = True)
    period_start = Column(Boolean, default = False)
    # 0 is none and 5 is most
    abdominal_pain_severity = Column(Integer, default = 0)