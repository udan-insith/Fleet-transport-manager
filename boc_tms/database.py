import sqlite3
import hashlib
import datetime
import random
import math
from contextlib import contextmanager
 
import pandas as pd
 
import utils
 
DB_PATH = "boc_transport.db"

#CONNECTION HELPERS
def get_connection():
    """
    Return a SQLite connection safe for use across Streamlit's reruns AND
    the background Excel-backup thread hitting the same file concurrently.
 
    - timeout=30: Python's sqlite3 waits up to 30s for a lock instead of
      immediately raising "database is locked" (default is 5s, too short
      under bursty write + concurrent backup-read load).
    - WAL journal mode: lets the backup thread's reads not block the main
      thread's writes (and vice versa) in the common case, instead of the
      default rollback-journal mode's stricter single-writer-blocks-all.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
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
    lon REAL,
    insurance_expiry TEXT,          -- YYYY-MM-DD
    revenue_license_expiry TEXT,    -- YYYY-MM-DD
    next_service_due TEXT           -- YYYY-MM-DD
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
    created_at TEXT,
    estimated_cost REAL             -- LKR, auto-computed from distance + vehicle rate
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
 
CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_id INTEGER NOT NULL REFERENCES drivers(id),
    start_date TEXT NOT NULL,       -- YYYY-MM-DD
    end_date TEXT NOT NULL,         -- YYYY-MM-DD
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'Pending',     -- Pending / Approved / Rejected
    requested_at TEXT,
    decided_at TEXT,
    decision_note TEXT
);
 
CREATE TABLE IF NOT EXISTS trip_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL UNIQUE REFERENCES appointments(id),
    rating INTEGER NOT NULL,        -- 1-5
    comment TEXT,
    submitted_by TEXT,
    submitted_at TEXT
);
 
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT
);
"""

def _migrate_schema():
    """
    Adds columns introduced after an existing boc_transport.db was created.
    SQLite supports ALTER TABLE ... ADD COLUMN, so this upgrades an
    existing database in place instead of forcing a data reset.
    """
    with get_cursor(commit=True) as cur:
        cur.execute("PRAGMA table_info(vehicles)")
        existing_vehicle_cols = {row["name"] for row in cur.fetchall()}
        for col in ("insurance_expiry", "revenue_license_expiry", "next_service_due"):
            if col not in existing_vehicle_cols:
                cur.execute(f"ALTER TABLE vehicles ADD COLUMN {col} TEXT")
 
        cur.execute("PRAGMA table_info(appointments)")
        existing_appt_cols = {row["name"] for row in cur.fetchall()}
        if "estimated_cost" not in existing_appt_cols:
            cur.execute("ALTER TABLE appointments ADD COLUMN estimated_cost REAL")
 
 
def init_db():
    with get_cursor(commit=True) as cur:
        cur.executescript(SCHEMA)
    _migrate_schema()

#AUTH HELPERS
def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
 
 
def verify_login(username: str, password: str):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
    if row and row["password_hash"] == hash_password(password):
        log_action(username, "login_success", row["role"])
        return dict(row)
    log_action(username, "login_failed", "")
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
            today = datetime.date.today()
            vehicles = []
            for i in range(10):
                vtype, cap = random.choice(types)
                plate = f"WP {'CAB' if vtype!='Bus' else 'NB'}-{random.randint(1000,9999)}"
                status = statuses[i % len(statuses)]
                lat = 6.9271 + random.uniform(-0.09, 0.09)
                lon = 79.8612 + random.uniform(-0.09, 0.09)
                # spread compliance dates across overdue / due-soon / healthy for a realistic demo
                insurance_expiry = (today + datetime.timedelta(days=random.randint(-10, 200))).isoformat()
                revenue_license_expiry = (today + datetime.timedelta(days=random.randint(-5, 250))).isoformat()
                next_service_due = (today + datetime.timedelta(days=random.randint(-15, 120))).isoformat()
                vehicles.append((plate, vtype, cap, status, lat, lon,
                                 insurance_expiry, revenue_license_expiry, next_service_due))
            cur.executemany(
                """INSERT INTO vehicles (plate_no, vehicle_type, capacity, status, lat, lon,
                                          insurance_expiry, revenue_license_expiry, next_service_due)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
 
            # Same open transaction/cursor, so this sees the vehicles/departments
            # just inserted above even though nothing has committed yet.
            cur.execute("SELECT id, vehicle_type FROM vehicles")
            vehicle_type_by_id = {r["id"]: r["vehicle_type"] for r in cur.fetchall()}
            cur.execute("SELECT id, lat, lon FROM departments")
            dept_coords_by_id = {r["id"]: (r["lat"], r["lon"]) for r in cur.fetchall()}
 
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
                dep_lat, dep_lon = dept_coords_by_id.get(dep_id, (None, None))
                estimated_cost = None
                if dep_lat is not None:
                    dist_km = utils.haversine_km(DEPOT_LAT, DEPOT_LON, dep_lat, dep_lon)
                    estimated_cost = utils.estimate_trip_cost(vehicle_type_by_id.get(v_id), dist_km)
                appts.append((appt_date, start_time, end_time, d_id, v_id, dep_id,
                              random.choice(purposes), "Scheduled", "admin",
                              datetime.datetime.now().isoformat(timespec="seconds"), estimated_cost))
            cur.executemany(
                """INSERT INTO appointments
                   (appt_date, start_time, end_time, driver_id, vehicle_id, department_id,
                    purpose, status, created_by, created_at, estimated_cost)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
           a.purpose, a.status, a.created_by, a.created_at, a.estimated_cost
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
DEPOT_LAT, DEPOT_LON = 6.9271, 79.8612  # Head Office depot, used as the cost-estimation origin
 
 
def _compute_trip_cost(vehicle_id: int, department_id: int) -> float | None:
    """Best-effort estimated cost; returns None if vehicle/department lookup fails."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT vehicle_type FROM vehicles WHERE id = ?", (vehicle_id,))
            v = cur.fetchone()
            cur.execute("SELECT lat, lon FROM departments WHERE id = ?", (department_id,))
            dep = cur.fetchone()
        if not v or not dep or dep["lat"] is None or dep["lon"] is None:
            return None
        distance_km = utils.haversine_km(DEPOT_LAT, DEPOT_LON, dep["lat"], dep["lon"])
        return utils.estimate_trip_cost(v["vehicle_type"], distance_km)
    except Exception:
        return None
 
 
def add_appointment(appt_date, start_time, end_time, driver_id, vehicle_id,
                     department_id, purpose, created_by):
    conflicts = check_conflict(appt_date, start_time, end_time, driver_id, vehicle_id)
    if conflicts:
        return False, conflicts
 
    estimated_cost = _compute_trip_cost(vehicle_id, department_id)
 
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO appointments
               (appt_date, start_time, end_time, driver_id, vehicle_id, department_id,
                purpose, status, created_by, created_at, estimated_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Scheduled', ?, ?, ?)""",
            (appt_date, start_time, end_time, driver_id, vehicle_id, department_id,
             purpose, created_by, datetime.datetime.now().isoformat(timespec="seconds"),
             estimated_cost),
        )
 
    log_action(created_by, "appointment_created",
               f"{appt_date} {start_time}-{end_time}, driver #{driver_id}, vehicle #{vehicle_id}")
    _touch_backup()
    return True, []
 
 
def update_appointment_status(appt_id: int, status: str, actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appt_id))
    log_action(actor, "appointment_status_updated", f"appointment #{appt_id} -> {status}")
    _touch_backup()
 
 
def update_driver_status(driver_id: int, status: str, actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE drivers SET status = ? WHERE id = ?", (status, driver_id))
    log_action(actor, "driver_status_updated", f"driver #{driver_id} -> {status}")
    _touch_backup()
 
 
def update_vehicle_status(vehicle_id: int, status: str, actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE vehicles SET status = ? WHERE id = ?", (status, vehicle_id))
    log_action(actor, "vehicle_status_updated", f"vehicle #{vehicle_id} -> {status}")
    _touch_backup()
 
 
def add_driver(name, license_no, phone, base_location, status="Available", lat=None, lon=None,
               actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO drivers (name, license_no, phone, base_location, status, lat, lon)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, license_no, phone, base_location, status, lat, lon),
        )
    log_action(actor, "driver_added", f"{name} ({license_no})")
    _touch_backup()
 
 
def add_vehicle(plate_no, vehicle_type, capacity, status="Available", lat=None, lon=None,
                 insurance_expiry=None, revenue_license_expiry=None, next_service_due=None,
                 actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO vehicles (plate_no, vehicle_type, capacity, status, lat, lon,
                                      insurance_expiry, revenue_license_expiry, next_service_due)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (plate_no, vehicle_type, capacity, status, lat, lon,
             insurance_expiry, revenue_license_expiry, next_service_due),
        )
    log_action(actor, "vehicle_added", f"{plate_no} ({vehicle_type})")
    _touch_backup()
 
 
def update_vehicle_compliance(vehicle_id: int, insurance_expiry=None, revenue_license_expiry=None,
                               next_service_due=None, actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE vehicles
               SET insurance_expiry = ?, revenue_license_expiry = ?, next_service_due = ?
               WHERE id = ?""",
            (insurance_expiry, revenue_license_expiry, next_service_due, vehicle_id),
        )
    log_action(actor, "vehicle_compliance_updated",
               f"vehicle #{vehicle_id}: insurance={insurance_expiry}, "
               f"revenue_license={revenue_license_expiry}, service={next_service_due}")
    _touch_backup()
 
 
def vehicles_needing_attention(warn_days: int = 30) -> pd.DataFrame:
    """
    Returns vehicles whose insurance, revenue license, or next service is
    already overdue or due within `warn_days`, with a human-readable
    'issues' column listing which. Used for the fleet compliance alerts
    on the Dashboard and Reports pages.
    """
    vehicles = get_vehicles()
    if vehicles.empty:
        return vehicles.assign(issues=[])
 
    today = datetime.date.today()
    horizon = today + datetime.timedelta(days=warn_days)
 
    def _status(date_str, label):
        # iterrows() can upcast a per-row None to float('nan') when the
        # same column holds real date strings on other rows -- and
        # bool(float('nan')) is True in Python, so `not date_str` alone
        # doesn't catch it. Check for NaN explicitly.
        if not date_str or (isinstance(date_str, float) and math.isnan(date_str)):
            return None
        try:
            d = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None
        if d < today:
            return f"{label} OVERDUE ({date_str})"
        if d <= horizon:
            return f"{label} due {date_str}"
        return None
 
    rows = []
    for _, v in vehicles.iterrows():
        issues = [
            m for m in (
                _status(v.get("insurance_expiry"), "Insurance"),
                _status(v.get("revenue_license_expiry"), "Revenue license"),
                _status(v.get("next_service_due"), "Service"),
            ) if m
        ]
        if issues:
            row = v.to_dict()
            row["issues"] = "; ".join(issues)
            rows.append(row)
 
    return pd.DataFrame(rows) if rows else vehicles.iloc[0:0].assign(issues=[])

# DRIVER LEAVE REQUESTS
def add_leave_request(driver_id: int, start_date: str, end_date: str, reason: str,
                       actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO leave_requests (driver_id, start_date, end_date, reason, status, requested_at)
               VALUES (?, ?, ?, ?, 'Pending', ?)""",
            (driver_id, start_date, end_date, reason,
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
    log_action(actor, "leave_requested", f"driver #{driver_id}: {start_date} to {end_date}")
    _touch_backup()
 
 
def get_leave_requests(status: str | None = None, driver_id: int | None = None) -> pd.DataFrame:
    conn = get_connection()
    q = """
    SELECT l.*, d.name AS driver_name
    FROM leave_requests l
    JOIN drivers d ON d.id = l.driver_id
    """
    clauses, params = [], []
    if status:
        clauses.append("l.status = ?")
        params.append(status)
    if driver_id is not None:
        clauses.append("l.driver_id = ?")
        params.append(driver_id)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY l.requested_at DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df
 
 
def approve_leave_request(request_id: int, actor: str | None = None):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM leave_requests WHERE id = ?", (request_id,))
        req = cur.fetchone()
    if req is None or req["status"] != "Pending":
        return
 
    today = datetime.date.today().isoformat()
    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE leave_requests SET status = 'Approved', decided_at = ? WHERE id = ?""",
            (datetime.datetime.now().isoformat(timespec="seconds"), request_id),
        )
        # If leave covers today, reflect it on the driver's status immediately.
        if req["start_date"] <= today <= req["end_date"]:
            cur.execute("UPDATE drivers SET status = 'On Leave' WHERE id = ?", (req["driver_id"],))
    log_action(actor, "leave_approved", f"leave request #{request_id} (driver #{req['driver_id']})")
    _touch_backup()
 
 
def reject_leave_request(request_id: int, note: str = "", actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE leave_requests SET status = 'Rejected', decision_note = ?, decided_at = ?
               WHERE id = ?""",
            (note, datetime.datetime.now().isoformat(timespec="seconds"), request_id),
        )
    log_action(actor, "leave_rejected", f"leave request #{request_id}: {note}")
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

#TRIP FEEDBACK AND DRIVER RATING
def add_trip_feedback(appointment_id: int, rating: int, comment: str, submitted_by: str):
    """One feedback entry per appointment (enforced by the UNIQUE constraint
    on trip_feedback.appointment_id)."""
    rating = max(1, min(5, int(rating)))
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO trip_feedback (appointment_id, rating, comment, submitted_by, submitted_at)
               VALUES (?, ?, ?, ?, ?)""",
            (appointment_id, rating, comment, submitted_by,
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
    log_action(submitted_by, "trip_feedback_submitted", f"appointment #{appointment_id}: {rating}/5")
    _touch_backup()
 
 
def has_feedback(appointment_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM trip_feedback WHERE appointment_id = ?", (appointment_id,))
        return cur.fetchone() is not None
 
 
def get_driver_rating_summary() -> pd.DataFrame:
    """Average rating + number of rated trips per driver, for display in
    Manage Drivers and the Driver Portal."""
    conn = get_connection()
    q = """
    SELECT d.id AS driver_id, d.name AS driver_name,
           AVG(f.rating) AS avg_rating, COUNT(f.id) AS rated_trips
    FROM drivers d
    LEFT JOIN appointments a ON a.driver_id = d.id
    LEFT JOIN trip_feedback f ON f.appointment_id = a.id
    GROUP BY d.id, d.name
    """
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df

#TRIP REQUESTS
def add_trip_request(department_id, appt_date, start_time, end_time, purpose, requested_by):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO trip_requests
               (department_id, appt_date, start_time, end_time, purpose, status, requested_by, created_at)
               VALUES (?, ?, ?, ?, ?, 'Pending', ?, ?)""",
            (department_id, appt_date, start_time, end_time, purpose, requested_by,
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
    log_action(requested_by, "trip_requested", f"department #{department_id}: {appt_date} {start_time}-{end_time}")
    _touch_backup()
 
 
def add_recurring_trip_request(department_id, start_date: str, start_time: str, end_time: str,
                                purpose: str, requested_by: str, weeks: int) -> int:
    """
    Submits `weeks` separate Pending trip_requests, one per week starting
    at `start_date` (same weekday/time each week). Each is still approved
    individually by the Transport Officer -- this just saves the
    requesting department from re-submitting the same weekly trip by hand.
    Returns the number of requests created.
    """
    base = datetime.date.fromisoformat(start_date)
    created = 0
    for i in range(max(1, weeks)):
        occurrence_date = (base + datetime.timedelta(weeks=i)).isoformat()
        add_trip_request(department_id, occurrence_date, start_time, end_time, purpose, requested_by)
        created += 1
    return created
 
 
def get_trip_requests(status: str | None = None, department_id: int | None = None) -> pd.DataFrame:
    conn = get_connection()
    q = """
    SELECT r.*, dep.name AS department_name,
           a.driver_id, d.name AS driver_name, a.vehicle_id, v.plate_no, a.estimated_cost
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
 
 
def approve_trip_request(request_id: int, driver_id: int, vehicle_id: int, actor: str | None = None):
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
 
    estimated_cost = _compute_trip_cost(vehicle_id, req["department_id"])
 
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO appointments
               (appt_date, start_time, end_time, driver_id, vehicle_id, department_id,
                purpose, status, created_by, created_at, estimated_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Scheduled', ?, ?, ?)""",
            (req["appt_date"], req["start_time"], req["end_time"], driver_id, vehicle_id,
             req["department_id"], req["purpose"], actor or "Transport Officer (from request)",
             datetime.datetime.now().isoformat(timespec="seconds"), estimated_cost),
        )
        new_appt_id = cur.lastrowid
        cur.execute(
            """UPDATE trip_requests SET status = 'Approved', appointment_id = ?, decided_at = ?
               WHERE id = ?""",
            (new_appt_id, datetime.datetime.now().isoformat(timespec="seconds"), request_id),
        )
    log_action(actor, "trip_request_approved",
               f"request #{request_id} -> appointment #{new_appt_id} "
               f"(driver #{driver_id}, vehicle #{vehicle_id})")
    _touch_backup()
    return True, []
 
 
def reject_trip_request(request_id: int, note: str = "", actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE trip_requests SET status = 'Rejected', decision_note = ?, decided_at = ?
               WHERE id = ?""",
            (note, datetime.datetime.now().isoformat(timespec="seconds"), request_id),
        )
    log_action(actor, "trip_request_rejected", f"request #{request_id}: {note}")
    _touch_backup()
 
 
def cancel_trip_request(request_id: int, actor: str | None = None):
    """Requesting department withdraws its own still-pending request."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE trip_requests SET status = 'Cancelled' WHERE id = ? AND status = 'Pending'",
            (request_id,),
        )
    log_action(actor, "trip_request_cancelled", f"request #{request_id}")
    _touch_backup()

#DEPARTMENT MANAGEMENT + LOGIN AUTHENTICATION
def add_department(name, location, lat=None, lon=None, actor: str | None = None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO departments (name, location, lat, lon) VALUES (?, ?, ?, ?)",
            (name, location, lat, lon),
        )
        dept_id = cur.lastrowid
    log_action(actor, "department_added", name)
    _touch_backup()
    return dept_id
 
 
def create_login(username, password, full_name, role, linked_driver_id=None, linked_department_id=None,
                  actor: str | None = None):
    """Create a portal login of a given role, optionally linked to a driver or department."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO users (username, password_hash, full_name, role, linked_driver_id, linked_department_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, hash_password(password), full_name, role, linked_driver_id, linked_department_id),
        )
    log_action(actor, "login_created", f"{username} ({role})")
    _touch_backup()
 
 
def username_exists(username: str) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        return cur.fetchone() is not None

#AUDIT LOG
def log_action(actor: str | None, action: str, details: str = ""):
    """
    Records one audit trail entry. `actor` is normally the acting user's
    username; falls back to 'system' for background/unattributed actions
    (e.g. the mock GPS ping). Never raises -- a logging failure must not
    break the calling operation.
    """
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO audit_log (timestamp, actor, action, details) VALUES (?, ?, ?, ?)",
                (datetime.datetime.now().isoformat(timespec="seconds"), actor or "system", action, details),
            )
    except Exception:
        pass
 
 
def get_audit_log(limit: int = 300, actor_filter: str | None = None,
                   action_filter: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    q = "SELECT * FROM audit_log"
    clauses, params = [], []
    if actor_filter:
        clauses.append("actor LIKE ?")
        params.append(f"%{actor_filter}%")
    if action_filter:
        clauses.append("action LIKE ?")
        params.append(f"%{action_filter}%")
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df
 
 
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
 