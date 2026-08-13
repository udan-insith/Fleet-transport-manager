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