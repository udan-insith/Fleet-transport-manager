"""
excel_sync.py
-------------
Background Excel mirror for the BOC Transport SQLite database.

Design goals (per spec):
  * The .xlsx file is regenerated every time an appointment (or any core
    record) is added/modified.
  * The web app must never block/wait on the Excel write, and the Excel
    file must never be "locked" mid-write for anyone who has it open.

How it works:
  * `trigger_backup()` is called by database.py after every write. It
    spins up a daemon thread that performs the actual export, so the
    Streamlit request thread returns immediately.
  * A module-level `threading.Lock` serialises concurrent backup jobs so
    two rapid writes can't corrupt the file.
  * The export writes to a temporary file first, then atomically renames
    it over the real backup file with `os.replace`. On every mainstream
    OS this rename is atomic, so a reader (e.g. someone with the file
    open in Excel via "Data > Refresh", or the OS reading its directory
    entry) never sees a half-written file.
"""

import os
import threading
import tempfile
import datetime

import pandas as pd

import database

BACKUP_PATH = "boc_transport_backup.xlsx"
_backup_lock = threading.Lock()


def _export_now():
    """Actually perform the export. Runs inside a worker thread."""
    with _backup_lock:
        drivers = database.get_drivers()
        vehicles = database.get_vehicles()
        departments = database.get_departments()
        appointments = database.get_appointments()
        trip_requests = database.get_trip_requests()

        summary = pd.DataFrame({
            "Metric": [
                "Total Drivers", "Available Drivers",
                "Total Vehicles", "Available Vehicles",
                "Total Departments", "Total Appointments (all time)",
                "Pending Trip Requests",
                "Last Backup",
            ],
            "Value": [
                len(drivers),
                int((drivers["status"] == "Available").sum()) if len(drivers) else 0,
                len(vehicles),
                int((vehicles["status"] == "Available").sum()) if len(vehicles) else 0,
                len(departments),
                len(appointments),
                int((trip_requests["status"] == "Pending").sum()) if len(trip_requests) else 0,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ],
        })

        # Write to a temp file in the same directory, then atomically swap it in.
        target_dir = os.path.dirname(os.path.abspath(BACKUP_PATH)) or "."
        fd, tmp_path = tempfile.mkstemp(suffix=".xlsx", dir=target_dir)
        os.close(fd)
        try:
            with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
                summary.to_excel(writer, sheet_name="Summary", index=False)
                drivers.to_excel(writer, sheet_name="Drivers", index=False)
                vehicles.to_excel(writer, sheet_name="Vehicles", index=False)
                departments.to_excel(writer, sheet_name="Departments", index=False)
                appointments.to_excel(writer, sheet_name="Appointments", index=False)
                trip_requests.to_excel(writer, sheet_name="Trip Requests", index=False)
            os.replace(tmp_path, BACKUP_PATH)  # atomic on POSIX & Windows (NTFS)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


def trigger_backup():
    """Fire-and-forget: schedule a backup on a daemon thread and return instantly."""
    t = threading.Thread(target=_export_now, daemon=True)
    t.start()
    return t


def force_sync_blocking():
    """Synchronous variant, useful for the initial seed / CLI testing."""
    _export_now()


if __name__ == "__main__":
    database.init_db()
    database.seed_if_empty()
    force_sync_blocking()
    print(f"Backup written to {os.path.abspath(BACKUP_PATH)}")
