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

#SEEDING DATA FOR THE FIRST RUN ONLY
def _table_count(cur, table):
    cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
    return cur.fetchone()["c"]


def seed_if_empty():
    with get_cursor(commit=True) as cur:
        if _table_count(cur, "departments") == 0:
            departments = [
                ("Head Office - Treasury Division", "Colombo 01", 6.9344, 79.8428),
                ("Colombo Fort Branch", "Colombo 01", 6.9319, 79.8478),
                ("Corporate Banking Division", "Colombo 02", 6.9184, 79.8479),
                ("Kandy Regional Office", "Kandy", 7.2906, 80.6337),
                ("Galle Branch", "Galle", 6.0535, 80.2210),
                ("Negombo Branch", "Negombo", 7.2083, 79.8358),
                ("Kurunegala Branch", "Kurunegala", 7.4863, 80.3623),
                ("IT Division - Head Office", "Colombo 01", 6.9350, 79.8440),
            ]
            cur.executemany(
                "INSERT INTO departments (name, location, lat, lon) VALUES (?, ?, ?, ?)",
                departments,
            )

        if _table_count(cur, "drivers") == 0:
            first_names = ["Sunil", "Nimal", "Kasun", "Priyantha", "Chamara", "Ruwan",
                            "Ajith", "Lasantha", "Suresh", "Dinesh", "Mahinda", "Roshan"]
            last_names = ["Perera", "Fernando", "Silva", "Bandara", "Gunawardena",
                          "Rathnayake", "Jayasuriya", "Wickramasinghe", "Dias", "Kumara"]
            statuses = ["Available", "Available", "Available", "On Trip", "Off Duty", "On Leave"]
            random.seed(42)
            drivers = []
            for i in range(12):
                name = f"{random.choice(first_names)} {random.choice(last_names)}"
                lic = f"B{random.randint(1000000, 9999999)}"
                phone = f"07{random.randint(0,9)}-{random.randint(1000000,9999999)}"
                status = statuses[i % len(statuses)]
                # scatter around Colombo for the live map demo
                lat = 6.9271 + random.uniform(-0.09, 0.09)
                lon = 79.8612 + random.uniform(-0.09, 0.09)
                drivers.append((name, lic, phone, "Head Office Depot", status, lat, lon))
            cur.executemany(
                """INSERT INTO drivers (name, license_no, phone, base_location, status, lat, lon)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                drivers,
            )

        if _table_count(cur, "vehicles") == 0:
            types = [("Van", 12), ("Car", 4), ("Double Cab", 4), ("Bus", 30), ("Lorry", 2)]
            statuses = ["Available", "Available", "In Use", "Available", "Maintenance"]
            random.seed(7)
            vehicles = []
            for i in range(10):
                vtype, cap = random.choice(types)
                plate = f"WP {'CAB' if vtype!='Bus' else 'NB'}-{random.randint(1000,9999)}"
                status = statuses[i % len(statuses)]
                lat = 6.9271 + random.uniform(-0.09, 0.09)
                lon = 79.8612 + random.uniform(-0.09, 0.09)
                vehicles.append((plate, vtype, cap, status, lat, lon))
            cur.executemany(
                """INSERT INTO vehicles (plate_no, vehicle_type, capacity, status, lat, lon)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                vehicles,
            )

        if _table_count(cur, "users") == 0:
            # Transport Officer (full control over fleet + bookings)
            cur.execute(
                """INSERT INTO users (username, password_hash, full_name, role)
                   VALUES (?, ?, ?, ?)""",
                ("admin", hash_password("BOC@Transport2026"), "Transport Duty Officer", "Transport Officer"),
            )

            # Driver login — linked to the first seeded driver, so this account
            # only ever sees/manages that driver's own schedule and status.
            cur.execute("SELECT id, name FROM drivers ORDER BY id LIMIT 1")
            first_driver = cur.fetchone()
            if first_driver:
                cur.execute(
                    """INSERT INTO users (username, password_hash, full_name, role, linked_driver_id)
                       VALUES (?, ?, ?, 'Driver', ?)""",
                    ("driver1", hash_password("Driver@123"), first_driver["name"], first_driver["id"]),
                )

            # Department login — linked to a requesting department/branch, so
            # this account can only submit/view requests for that department.
            cur.execute("SELECT id, name FROM departments WHERE name LIKE 'Kandy%' LIMIT 1")
            req_dept = cur.fetchone()
            if req_dept:
                cur.execute(
                    """INSERT INTO users (username, password_hash, full_name, role, linked_department_id)
                       VALUES (?, ?, ?, 'Department', ?)""",
                    ("kandy_branch", hash_password("Dept@123"), req_dept["name"], req_dept["id"]),
                )

        if _table_count(cur, "appointments") == 0:
            cur.execute("SELECT id FROM drivers")
            driver_ids = [r["id"] for r in cur.fetchall()]
            cur.execute("SELECT id FROM vehicles")
            vehicle_ids = [r["id"] for r in cur.fetchall()]
            cur.execute("SELECT id FROM departments")
            dept_ids = [r["id"] for r in cur.fetchall()]

            random.seed(99)
            today = datetime.date.today()
            purposes = ["Cash in transit", "Staff transport", "Document courier",
                        "Branch inspection visit", "VIP transport", "Equipment delivery"]
            appts = []
            used_pairs = set()
            for i in range(18):
                day_offset = random.randint(-3, 20)
                appt_date = (today + datetime.timedelta(days=day_offset)).isoformat()
                start_hour = random.choice([8, 9, 10, 13, 14])
                start_time = f"{start_hour:02d}:00"
                end_time = f"{start_hour + random.choice([1, 2, 3]):02d}:00"
                d_id = random.choice(driver_ids)
                v_id = random.choice(vehicle_ids)
                key = (appt_date, d_id, v_id, start_time)
                if key in used_pairs:
                    continue
                used_pairs.add(key)
                dep_id = random.choice(dept_ids)
                appts.append((appt_date, start_time, end_time, d_id, v_id, dep_id,
                              random.choice(purposes), "Scheduled", "admin",
                              datetime.datetime.now().isoformat(timespec="seconds")))
            cur.executemany(
                """INSERT INTO appointments
                   (appt_date, start_time, end_time, driver_id, vehicle_id, department_id,
                    purpose, status, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                appts,
            )