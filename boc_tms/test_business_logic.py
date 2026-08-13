"""Standalone unit tests for database.py business logic (not shipped to user)."""
import os
import pandas as pd
import database
import excel_sync

# Use a throwaway DB so this doesn't disturb seeded demo data
database.DB_PATH = "test_boc.db"
excel_sync.BACKUP_PATH = "test_backup.xlsx"
for f in (database.DB_PATH, excel_sync.BACKUP_PATH):
    if os.path.exists(f):
        os.remove(f)

database.init_db()
database.seed_if_empty()

drivers = database.get_drivers()
vehicles = database.get_vehicles()
departments = database.get_departments()
d1, d2 = int(drivers.iloc[0]["id"]), int(drivers.iloc[1]["id"])
v1, v2 = int(vehicles.iloc[0]["id"]), int(vehicles.iloc[1]["id"])
dep = int(departments.iloc[0]["id"])

results = []

# 1) Baseline booking should succeed
ok, conflicts = database.add_appointment("2026-09-01", "09:00", "11:00", d1, v1, dep, "Test A", "tester")
results.append(("Baseline booking succeeds", ok and not conflicts))

# 2) Overlapping time, SAME driver, different vehicle -> must be rejected
ok, conflicts = database.add_appointment("2026-09-01", "10:00", "12:00", d1, v2, dep, "Test B", "tester")
results.append(("Driver double-booking rejected", not ok and len(conflicts) > 0))

# 3) Overlapping time, SAME vehicle, different driver -> must be rejected
ok, conflicts = database.add_appointment("2026-09-01", "10:00", "12:00", d2, v1, dep, "Test C", "tester")
results.append(("Vehicle double-booking rejected", not ok and len(conflicts) > 0))

# 4) Non-overlapping time, same driver+vehicle -> must succeed
ok, conflicts = database.add_appointment("2026-09-01", "11:00", "12:00", d1, v1, dep, "Test D", "tester")
results.append(("Back-to-back non-overlapping booking succeeds", ok and not conflicts))

# 5) Different date, same driver+vehicle+time -> must succeed
ok, conflicts = database.add_appointment("2026-09-02", "09:00", "11:00", d1, v1, dep, "Test E", "tester")
results.append(("Same slot different date succeeds", ok and not conflicts))

# 6) Cancelling an appointment should free the slot for a new booking
appts = database.get_appointments("2026-09-01", "2026-09-01")
first_id = int(appts.iloc[0]["id"])
database.update_appointment_status(first_id, "Cancelled")
ok, conflicts = database.add_appointment("2026-09-01", "09:00", "11:00", d1, v1, dep, "Test F", "tester")
results.append(("Cancelled appointment frees the slot", ok and not conflicts))