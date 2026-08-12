import sqlite3
import hashlib
import datetime
import random
from contextlib import contextmanager

import pandas as pd

DB_PATH = "boc_transport.db"

#CONNECTION HELPERS
def get_connection():
    """Return a SQLite connection safe for use across Streamlit's reruns."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_cursor(commit: bool = False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()

#SQL SCHEMAS
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Transport Officer',   -- Transport Officer / Driver / Department
    linked_driver_id INTEGER REFERENCES drivers(id),
    linked_department_id INTEGER REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    license_no TEXT NOT NULL,
    phone TEXT,
    base_location TEXT,
    status TEXT NOT NULL DEFAULT 'Available',   -- Available / On Trip / Off Duty / On Leave
    lat REAL,
    lon REAL
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_no TEXT UNIQUE NOT NULL,
    vehicle_type TEXT NOT NULL,
    capacity INTEGER,
    status TEXT NOT NULL DEFAULT 'Available',   -- Available / In Use / Maintenance
    lat REAL,
    lon REAL
);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    lat REAL,
    lon REAL
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appt_date TEXT NOT NULL,        -- YYYY-MM-DD
    start_time TEXT NOT NULL,       -- HH:MM
    end_time TEXT NOT NULL,         -- HH:MM
    driver_id INTEGER NOT NULL REFERENCES drivers(id),
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    department_id INTEGER NOT NULL REFERENCES departments(id),
    purpose TEXT,
    status TEXT NOT NULL DEFAULT 'Scheduled',   -- Scheduled / Completed / Cancelled
    created_by TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS trip_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    appt_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    purpose TEXT,
    status TEXT NOT NULL DEFAULT 'Pending',     -- Pending / Approved / Rejected / Cancelled
    requested_by TEXT,
    created_at TEXT,
    appointment_id INTEGER REFERENCES appointments(id),
    decision_note TEXT,
    decided_at TEXT
);
"""


def init_db():
    with get_cursor(commit=True) as cur:
        cur.executescript(SCHEMA)

#AUTH HELPERS
def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_login(username: str, password: str):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
    if row and row["password_hash"] == hash_password(password):
        return dict(row)
    return None
