import sys
from pathlib import Path
sys.path.insert(0, str(Path("c:/Users/srich/OneDrive/Desktop/Health_AI/backend").resolve()))

from app.timezone_helper import datetime
from app.database import SessionLocal
from app import models
import datetime as orig_datetime

print("=== Timezone / IST Patched Verification ===")
print("System timezone/local time:", orig_datetime.datetime.now())
print("IST timezone current time:", datetime.datetime.now())
print("IST timezone current date:", datetime.date.today())
print("IST timezone utcnow (should match IST):", datetime.datetime.utcnow())

db = SessionLocal()
try:
    # Check current appointments in DB
    appt = db.query(models.Appointment).order_by(models.Appointment.id.desc()).first()
    if appt:
        print(f"Latest appointment ID: {appt.id}")
        print(f"Appointment created_at: {appt.created_at}")
    else:
        print("No appointments found in DB.")
        
    # Check latest audit logs
    log = db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).first()
    if log:
        print(f"Latest audit log: ID {log.id}, action '{log.action}', timestamp {log.timestamp}")
    else:
        print("No audit logs found.")
finally:
    db.close()
