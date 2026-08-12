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

#READ HELPERS (RETURN DATAFRAMES)
def get_drivers(status: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    q = "SELECT * FROM drivers"
    params = ()
    if status:
        q += " WHERE status = ?"
        params = (status,)
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def get_vehicles(status: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    q = "SELECT * FROM vehicles"
    params = ()
    if status:
        q += " WHERE status = ?"
        params = (status,)
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def get_departments() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM departments", conn)
    conn.close()
    return df


def get_appointments(date_from: str | None = None, date_to: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    q = """
    SELECT a.id, a.appt_date, a.start_time, a.end_time,
           d.id AS driver_id, d.name AS driver_name,
           v.id AS vehicle_id, v.plate_no, v.vehicle_type,
           dep.id AS department_id, dep.name AS department_name,
           a.purpose, a.status, a.created_by, a.created_at
    FROM appointments a
    JOIN drivers d ON d.id = a.driver_id
    JOIN vehicles v ON v.id = a.vehicle_id
    JOIN departments dep ON dep.id = a.department_id
    """
    clauses, params = [], []
    if date_from:
        clauses.append("a.appt_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("a.appt_date <= ?")
        params.append(date_to)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY a.appt_date, a.start_time"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df

#CONFLICT VALIDATION
def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _overlaps(s1, e1, s2, e2) -> bool:
    return _to_minutes(s1) < _to_minutes(e2) and _to_minutes(s2) < _to_minutes(e1)


def check_conflict(appt_date, start_time, end_time, driver_id, vehicle_id, exclude_id=None):
    """
    Returns a list of human-readable conflict messages (empty list = no conflict).
    Checks both the driver and the vehicle against every *active* (non-cancelled)
    appointment on the same date.
    """
    conflicts = []
    with get_cursor() as cur:
        cur.execute(
            """SELECT a.*, d.name as driver_name, v.plate_no
               FROM appointments a
               JOIN drivers d ON d.id = a.driver_id
               JOIN vehicles v ON v.id = a.vehicle_id
               WHERE a.appt_date = ? AND a.status != 'Cancelled'""",
            (appt_date,),
        )
        rows = cur.fetchall()

    for row in rows:
        if exclude_id is not None and row["id"] == exclude_id:
            continue
        if not _overlaps(start_time, end_time, row["start_time"], row["end_time"]):
            continue
        if row["driver_id"] == driver_id:
            conflicts.append(
                f"Driver already booked {row['start_time']}-{row['end_time']} "
                f"(appointment #{row['id']})."
            )
        if row["vehicle_id"] == vehicle_id:
            conflicts.append(
                f"Vehicle {row['plate_no']} already booked {row['start_time']}-{row['end_time']} "
                f"(appointment #{row['id']})."
            )
    return conflicts

#WRITE HELPERS
def add_appointment(appt_date, start_time, end_time, driver_id, vehicle_id,
                     department_id, purpose, created_by):
    conflicts = check_conflict(appt_date, start_time, end_time, driver_id, vehicle_id)
    if conflicts:
        return False, conflicts

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO appointments
               (appt_date, start_time, end_time, driver_id, vehicle_id, department_id,
                purpose, status, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Scheduled', ?, ?)""",
            (appt_date, start_time, end_time, driver_id, vehicle_id, department_id,
             purpose, created_by, datetime.datetime.now().isoformat(timespec="seconds")),
        )

    _touch_backup()
    return True, []


def update_appointment_status(appt_id: int, status: str):
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appt_id))
    _touch_backup()


def update_driver_status(driver_id: int, status: str):
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE drivers SET status = ? WHERE id = ?", (status, driver_id))
    _touch_backup()


def update_vehicle_status(vehicle_id: int, status: str):
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE vehicles SET status = ? WHERE id = ?", (status, vehicle_id))
    _touch_backup()


def add_driver(name, license_no, phone, base_location, status="Available", lat=None, lon=None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO drivers (name, license_no, phone, base_location, status, lat, lon)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, license_no, phone, base_location, status, lat, lon),
        )
    _touch_backup()


def add_vehicle(plate_no, vehicle_type, capacity, status="Available", lat=None, lon=None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO vehicles (plate_no, vehicle_type, capacity, status, lat, lon)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (plate_no, vehicle_type, capacity, status, lat, lon),
        )
    _touch_backup()


def nudge_driver_locations():
    """
    Mock GPS simulation: nudges the coordinates of drivers currently
    'On Trip' by a small random offset, so the Live Map page feels like
    it is tracking moving vehicles when the user clicks 'Simulate GPS Ping'.
    """
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT id, lat, lon FROM drivers WHERE status = 'On Trip'")
        rows = cur.fetchall()
        for row in rows:
            new_lat = (row["lat"] or 6.9271) + random.uniform(-0.004, 0.004)
            new_lon = (row["lon"] or 79.8612) + random.uniform(-0.004, 0.004)
            cur.execute("UPDATE drivers SET lat = ?, lon = ? WHERE id = ?",
                        (new_lat, new_lon, row["id"]))
    _touch_backup()

#TRANSPORT REQUESTS
def add_trip_request(department_id, appt_date, start_time, end_time, purpose, requested_by):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO trip_requests
               (department_id, appt_date, start_time, end_time, purpose, status, requested_by, created_at)
               VALUES (?, ?, ?, ?, ?, 'Pending', ?, ?)""",
            (department_id, appt_date, start_time, end_time, purpose, requested_by,
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
    _touch_backup()


def get_trip_requests(status: str | None = None, department_id: int | None = None) -> pd.DataFrame:
    conn = get_connection()
    q = """
    SELECT r.*, dep.name AS department_name,
           a.driver_id, d.name AS driver_name, a.vehicle_id, v.plate_no
    FROM trip_requests r
    JOIN departments dep ON dep.id = r.department_id
    LEFT JOIN appointments a ON a.id = r.appointment_id
    LEFT JOIN drivers d ON d.id = a.driver_id
    LEFT JOIN vehicles v ON v.id = a.vehicle_id
    """
    clauses, params = [], []
    if status:
        clauses.append("r.status = ?")
        params.append(status)
    if department_id is not None:
        clauses.append("r.department_id = ?")
        params.append(department_id)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY r.created_at DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def approve_trip_request(request_id: int, driver_id: int, vehicle_id: int):
    """Assign a driver+vehicle to a pending request. Runs the same conflict
    check as a normal booking; on success this creates the appointment and
    marks the request Approved, atomically (same DB transaction)."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM trip_requests WHERE id = ?", (request_id,))
        req = cur.fetchone()
    if req is None:
        return False, ["Request not found."]
    if req["status"] != "Pending":
        return False, [f"Request is already '{req['status']}'."]

    conflicts = check_conflict(req["appt_date"], req["start_time"], req["end_time"],
                                driver_id, vehicle_id)
    if conflicts:
        return False, conflicts

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO appointments
               (appt_date, start_time, end_time, driver_id, vehicle_id, department_id,
                purpose, status, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Scheduled', ?, ?)""",
            (req["appt_date"], req["start_time"], req["end_time"], driver_id, vehicle_id,
             req["department_id"], req["purpose"], "Transport Officer (from request)",
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
        new_appt_id = cur.lastrowid
        cur.execute(
            """UPDATE trip_requests SET status = 'Approved', appointment_id = ?, decided_at = ?
               WHERE id = ?""",
            (new_appt_id, datetime.datetime.now().isoformat(timespec="seconds"), request_id),
        )
    _touch_backup()
    return True, []


def reject_trip_request(request_id: int, note: str = ""):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE trip_requests SET status = 'Rejected', decision_note = ?, decided_at = ?
               WHERE id = ?""",
            (note, datetime.datetime.now().isoformat(timespec="seconds"), request_id),
        )
    _touch_backup()


def cancel_trip_request(request_id: int):
    """Requesting department withdraws its own still-pending request."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE trip_requests SET status = 'Cancelled' WHERE id = ? AND status = 'Pending'",
            (request_id,),
        )
    _touch_backup()

#DEPARTMENT MANAGEMENT + LINKED LOGIN
def add_department(name, location, lat=None, lon=None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO departments (name, location, lat, lon) VALUES (?, ?, ?, ?)",
            (name, location, lat, lon),
        )
        dept_id = cur.lastrowid
    _touch_backup()
    return dept_id


def create_login(username, password, full_name, role, linked_driver_id=None, linked_department_id=None):
    """Create a portal login of a given role, optionally linked to a driver or department."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO users (username, password_hash, full_name, role, linked_driver_id, linked_department_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, hash_password(password), full_name, role, linked_driver_id, linked_department_id),
        )
    _touch_backup()


def username_exists(username: str) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        return cur.fetchone() is not None


def _touch_backup():
    """Fire-and-forget Excel backup, imported lazily to avoid circular imports."""
    try:
        import excel_sync
        excel_sync.trigger_backup()
    except Exception:
        # Backup failures must never break the live app.
        pass


if __name__ == "__main__":
    # Standalone smoke test: `python3 database.py`
    init_db()
    seed_if_empty()
    print("Drivers:", len(get_drivers()))
    print("Vehicles:", len(get_vehicles()))
    print("Departments:", len(get_departments()))
    print("Appointments:", len(get_appointments()))
    print("Login check (admin/BOC@Transport2026):", bool(verify_login("admin", "BOC@Transport2026")))

