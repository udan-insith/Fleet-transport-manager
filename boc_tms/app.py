import datetime
import calendar
 
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
 
import database
import excel_sync
import auth
import utils

# PAGE CONFIG + ONE TIME INITIALIZATION
st.set_page_config(
    page_title="BOC Transport Management System",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
database.init_db()
database.seed_if_empty()
 
if "backup_synced" not in st.session_state:
    excel_sync.trigger_backup()
    st.session_state["backup_synced"] = True
 
# BOC THEME
def _active_theme() -> str:
    """
    Returns 'light' or 'dark' based on the visitor's *currently active*
    Streamlit theme (whatever they picked in Settings, or their OS
    preference on first load) -- not just what's set in config.toml.
    Falls back to 'light' on older Streamlit versions that predate
    st.context.theme (added in Streamlit 1.46).
    """
    try:
        return st.context.theme.type
    except Exception:
        return "light"

def inject_theme():
    is_dark = _active_theme() == "dark"
 
    page_bg = utils.BOC_DARK_BG if is_dark else utils.BOC_BG
    sidebar_bg = utils.BOC_DARK_SIDEBAR if is_dark else utils.BOC_NAVY
    card_bg = utils.BOC_DARK_CARD if is_dark else utils.BOC_WHITE
    header_bg = utils.BOC_DARK_CARD if is_dark else utils.BOC_NAVY
    card_border = "#2A4A73" if is_dark else "#E0E4EA"
    metric_accent = utils.BOC_GOLD if is_dark else utils.BOC_NAVY
 
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {page_bg};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {sidebar_bg};
        }}
        section[data-testid="stSidebar"] * {{
            color: {utils.BOC_WHITE} !important;
        }}
        section[data-testid="stSidebar"] .stRadio > label {{
            color: {utils.BOC_WHITE} !important;
        }}
        div.stButton > button, div.stFormSubmitButton > button {{
            background-color: {utils.BOC_GOLD};
            color: {utils.BOC_NAVY};
            font-weight: 700;
            border: none;
            border-radius: 6px;
        }}
        div.stButton > button:hover, div.stFormSubmitButton > button:hover {{
            background-color: #e6b800;
            color: {utils.BOC_NAVY};
        }}
        .boc-header {{
            background-color: {header_bg};
            padding: 18px 28px;
            border-radius: 8px;
            border-bottom: 5px solid {utils.BOC_GOLD};
            margin-bottom: 22px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .boc-header h1 {{
            color: {utils.BOC_WHITE};
            font-size: 26px;
            margin: 0;
        }}
        .boc-header p {{
            color: {utils.BOC_GOLD};
            margin: 2px 0 0 0;
            font-size: 14px;
        }}
        .boc-logo-badge {{
            background-color: {utils.BOC_GOLD};
            color: {utils.BOC_NAVY};
            font-weight: 800;
            font-size: 20px;
            border-radius: 50%;
            width: 46px;
            height: 46px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        div[data-testid="stMetric"] {{
            background-color: {card_bg};
            border: 1px solid {card_border};
            border-left: 5px solid {metric_accent};
            border-radius: 8px;
            padding: 12px 16px;
        }}
        .status-pill {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            color: white;
            font-size: 12px;
            font-weight: 600;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
def render_header(subtitle: str):
    st.markdown(
        f"""
        <div class="boc-header">
            <div style="display:flex; align-items:center; gap:14px;">
                <div class="boc-logo-badge">BOC</div>
                <div>
                    <h1>Bank of Ceylon &mdash; WPS Transport Management System</h1>
                    <p>{subtitle}</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def status_pill(status: str, color_map: dict) -> str:
    color = color_map.get(status, "#7F8C8D")
    return f'<span class="status-pill" style="background-color:{color};">{status}</span>'

# PAGE LIVE DASHBOARD
def page_dashboard():
    render_header("Live Dashboard &mdash; Fleet Availability Overview")
 
    drivers = database.get_drivers()
    vehicles = database.get_vehicles()
    departments = database.get_departments()
    today = datetime.date.today().isoformat()
    todays_appts = database.get_appointments(date_from=today, date_to=today)
    todays_appts = todays_appts[todays_appts["status"] != "Cancelled"]
 
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Drivers", len(drivers))
    c2.metric("Available Drivers", int((drivers["status"] == "Available").sum()))
    c3.metric("Total Vehicles", len(vehicles))
    c4.metric("Available Vehicles", int((vehicles["status"] == "Available").sum()))
    c5.metric("Today's Trips", len(todays_appts))
 
    attention = database.vehicles_needing_attention(warn_days=14)
    if not attention.empty:
        st.warning(
            f"🔧 {len(attention)} vehicle(s) have insurance, revenue license, or service due "
            f"within 14 days (or overdue) — see **Reports & Analytics** for details.",
            icon="⚠️",
        )
 
    st.write("")
    col_a, col_b = st.columns(2)
 
    with col_a:
        st.subheader("Available Drivers")
        av_drivers = drivers[drivers["status"] == "Available"][
            ["name", "license_no", "phone", "base_location"]
        ].rename(columns={
            "name": "Name", "license_no": "License No.",
            "phone": "Phone", "base_location": "Base",
        })
        st.dataframe(av_drivers, use_container_width=True, hide_index=True)
 
    with col_b:
        st.subheader("Available Vehicles")
        av_vehicles = vehicles[vehicles["status"] == "Available"][
            ["plate_no", "vehicle_type", "capacity"]
        ].rename(columns={
            "plate_no": "Plate No.", "vehicle_type": "Type", "capacity": "Capacity",
        })
        st.dataframe(av_vehicles, use_container_width=True, hide_index=True)
 
    st.write("")
    st.subheader("📍 Find Nearby Available Units")
    st.caption("Select a department to rank currently available drivers and vehicles by distance.")
 
    dept_names = departments["name"].tolist()
    selected_dept = st.selectbox("Department / Destination", dept_names)
    dep_row = departments[departments["name"] == selected_dept].iloc[0]
 
    nc1, nc2 = st.columns(2)
    with nc1:
        st.markdown("**Nearest Available Drivers**")
        av = drivers[drivers["status"] == "Available"].copy()
        av["distance_km"] = av.apply(
            lambda r: utils.haversine_km(r["lat"], r["lon"], dep_row["lat"], dep_row["lon"]),
            axis=1,
        )
        av = av.sort_values("distance_km").head(5)
        av["distance_km"] = av["distance_km"].round(2)
        st.dataframe(
            av[["name", "phone", "distance_km"]].rename(
                columns={"name": "Driver", "phone": "Phone", "distance_km": "Distance (km)"}
            ),
            use_container_width=True, hide_index=True,
        )
 
    with nc2:
        st.markdown("**Nearest Available Vehicles**")
        avv = vehicles[vehicles["status"] == "Available"].copy()
        avv["distance_km"] = avv.apply(
            lambda r: utils.haversine_km(r["lat"], r["lon"], dep_row["lat"], dep_row["lon"]),
            axis=1,
        )
        avv = avv.sort_values("distance_km").head(5)
        avv["distance_km"] = avv["distance_km"].round(2)
        st.dataframe(
            avv[["plate_no", "vehicle_type", "distance_km"]].rename(
                columns={"plate_no": "Vehicle", "vehicle_type": "Type", "distance_km": "Distance (km)"}
            ),
            use_container_width=True, hide_index=True,
        )
 
    st.caption(
        f"Excel backup mirror: `{excel_sync.BACKUP_PATH}` — refreshed automatically on every booking change."
    )

# LIVE GPS
def page_live_map():
    render_header("Live GPS Map &mdash; Vehicle &amp; Driver Tracking (Mock Feed)")
 
    top_l, top_r = st.columns([3, 1])
    with top_r:
        if st.button("🔄 Simulate GPS Ping", use_container_width=True):
            database.nudge_driver_locations()
            st.success("Positions updated for on-trip vehicles.")
 
    drivers = database.get_drivers()
    vehicles = database.get_vehicles()
    departments = database.get_departments()
 
    fmap = folium.Map(location=[6.9271, 79.8612], zoom_start=8, tiles="CartoDB positron")
 
    for _, d in drivers.iterrows():
        if pd.isna(d["lat"]) or pd.isna(d["lon"]):
            continue
        color = utils.DRIVER_STATUS_COLORS.get(d["status"], "#7F8C8D")
        folium.CircleMarker(
            location=[d["lat"], d["lon"]],
            radius=8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=f"Driver: {d['name']} ({d['status']})",
            popup=folium.Popup(
                f"<b>{d['name']}</b><br>Status: {d['status']}<br>"
                f"License: {d['license_no']}<br>Base: {d['base_location']}",
                max_width=220,
            ),
        ).add_to(fmap)
    for _, v in vehicles.iterrows():
        if pd.isna(v["lat"]) or pd.isna(v["lon"]):
            continue
        color = utils.VEHICLE_STATUS_COLORS.get(v["status"], "#7F8C8D")
        folium.Marker(
            location=[v["lat"], v["lon"]],
            tooltip=f"Vehicle: {v['plate_no']} ({v['status']})",
            popup=folium.Popup(
                f"<b>{v['plate_no']}</b><br>Type: {v['vehicle_type']}<br>Status: {v['status']}",
                max_width=200,
            ),
            icon=folium.Icon(color="orange" if v["status"] == "In Use" else
                              ("gray" if v["status"] == "Maintenance" else "green"),
                              icon="car", prefix="fa"),
        ).add_to(fmap)
 
    for _, dep in departments.iterrows():
        folium.Marker(
            location=[dep["lat"], dep["lon"]],
            tooltip=f"Department: {dep['name']}",
            popup=f"<b>{dep['name']}</b><br>{dep['location']}",
            icon=folium.Icon(color="darkblue", icon="building", prefix="fa"),
        ).add_to(fmap)
 
    with top_l:
        st.caption(
            "🟢 Available &nbsp;&nbsp; 🟡 On Trip / In Use &nbsp;&nbsp; "
            "⚪ Off Duty &nbsp;&nbsp; 🔴 On Leave / Maintenance &nbsp;&nbsp; 🔵 Department"
        )
 
    st_folium(fmap, use_container_width=True, height=560, returned_objects=[])
 
    st.info(
        "This is a **mock** GPS feed for demonstration: driver/vehicle coordinates are "
        "seeded values that shift slightly when you click 'Simulate GPS Ping'. Wire this "
        "up to a real telematics/GPS API for production tracking.",
        icon="ℹ️",
    )

# MONTHLY SCHEDULER
def build_matrix(entity_df, entity_id_col, entity_label_col, appts, days_in_month, year, month):
    """
    Build a rows=entity x cols=day grid of department names (comma-joined if >1).
 
    Indexed internally by the entity's unique DB id (never by name/plate, which
    can collide) and only relabeled for display at the very end, so `.at[]`
    lookups always resolve to a single scalar cell.
    """
    entity_ids = entity_df["id"].tolist()
    day_cols = [str(d) for d in range(1, days_in_month + 1)]
    grid = pd.DataFrame("", index=entity_ids, columns=day_cols)
 
    for _, row in appts.iterrows():
        appt_date = datetime.date.fromisoformat(row["appt_date"])
        if appt_date.year != year or appt_date.month != month:
            continue
        entity_id = row[entity_id_col]            # e.g. row["driver_id"] or row["vehicle_id"]
        if entity_id not in grid.index:
            continue
        day_col = str(appt_date.day)
        existing = grid.at[entity_id, day_col]
        cell_text = row["department_name"]
        grid.at[entity_id, day_col] = f"{existing}, {cell_text}" if existing else cell_text
 
    # Make row labels unique for display (e.g. "Nimal Perera (#3)") in case
    # two drivers/vehicles happen to share the same name/plate.
    label_counts = entity_df[entity_label_col].value_counts()
    display_labels = []
    for _, r in entity_df.iterrows():
        base = r[entity_label_col]
        display_labels.append(f"{base} (#{r['id']})" if label_counts[base] > 1 else base)
    grid.index = display_labels
    return grid
 
 
def style_matrix(grid: pd.DataFrame, dept_list: list[str]):
    def color_cell(val):
        if not val:
            return "background-color: #FFFFFF; color: #C6C6C6;"
        first_dept = val.split(",")[0].strip()
        bg = utils.department_color(first_dept, dept_list)
        return f"background-color: {bg}22; color: {utils.BOC_NAVY}; font-weight: 600; border-left: 4px solid {bg};"
 
    styler = grid.style
    # pandas >= 2.1 renamed Styler.applymap to Styler.map; support both.
    if hasattr(styler, "map"):
        return styler.map(color_cell)
    return styler.applymap(color_cell)

def page_scheduler():
    render_header("Monthly Scheduler Matrix &mdash; Driver / Vehicle Assignments")
 
    today = datetime.date.today()
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        year = st.selectbox("Year", list(range(today.year - 1, today.year + 2)),
                             index=1)
    with c2:
        month = st.selectbox("Month", list(range(1, 13)),
                              index=today.month - 1,
                              format_func=lambda m: calendar.month_name[m])
    with c3:
        view_by = st.radio("View by", ["Driver", "Vehicle"], horizontal=True)
 
    days_in_month = calendar.monthrange(year, month)[1]
    month_start = datetime.date(year, month, 1).isoformat()
    month_end = datetime.date(year, month, days_in_month).isoformat()
    appts = database.get_appointments(date_from=month_start, date_to=month_end)
    appts = appts[appts["status"] != "Cancelled"]
 
    departments = database.get_departments()
    dept_list = departments["name"].tolist()
 
    if view_by == "Driver":
        drivers = database.get_drivers()
        grid = build_matrix(drivers, "driver_id", "name", appts, days_in_month, year, month)
    else:
        vehicles = database.get_vehicles()
        grid = build_matrix(vehicles, "vehicle_id", "plate_no", appts, days_in_month, year, month)
 
    st.markdown(f"**{calendar.month_name[month]} {year}** &mdash; grid cells show the department "
                f"each {view_by.lower()} is assigned to on that day. Empty = unassigned/free.")
 
    st.dataframe(style_matrix(grid, dept_list), use_container_width=True, height=430)
 
    with st.expander("Department color legend"):
        legend_cols = st.columns(4)
        for i, name in enumerate(dept_list):
            color = utils.department_color(name, dept_list)
            swatch = (
                f'<span style="display:inline-block;width:12px;height:12px;'
                f'background-color:{color};border-radius:3px;margin-right:6px;"></span> {name}'
            )
            legend_cols[i % 4].markdown(swatch, unsafe_allow_html=True)
 
    st.write("")
    st.subheader(f"Appointment list — {calendar.month_name[month]} {year}")
    if appts.empty:
        st.caption("No appointments scheduled this month.")
    else:
        display_cols = ["appt_date", "start_time", "end_time", "driver_name",
                         "plate_no", "department_name", "purpose", "status"]
        st.dataframe(
            appts[display_cols].rename(columns={
                "appt_date": "Date", "start_time": "Start", "end_time": "End",
                "driver_name": "Driver", "plate_no": "Vehicle",
                "department_name": "Department", "purpose": "Purpose", "status": "Status",
            }),
            use_container_width=True, hide_index=True,
        )
 
    st.success(
        "Conflict protection is active: the booking form in the Employee Portal blocks any "
        "driver or vehicle from being double-booked into overlapping time slots.",
        icon="🛡️",
    )

# CSV EXPORT HELPER
def csv_download_button(df: pd.DataFrame, label: str, filename: str, key: str):
    if df.empty:
        return
    st.download_button(
        label=f"⬇️ {label}",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )

# PAGE REPORTS ANALYTICS
def page_reports():
    render_header("Reports &amp; Analytics")
 
    today = datetime.date.today()
    c1, c2 = st.columns(2)
    with c1:
        date_from = st.date_input("From", value=today - datetime.timedelta(days=90), key="rep_from")
    with c2:
        date_to = st.date_input("To", value=today + datetime.timedelta(days=30), key="rep_to")
 
    appts = database.get_appointments(date_from.isoformat(), date_to.isoformat())
    active_appts = appts[appts["status"] != "Cancelled"]
 
    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Trips in range", len(active_appts))
    m2.metric("Completed", int((active_appts["status"] == "Completed").sum()))
    m3.metric("Scheduled", int((active_appts["status"] == "Scheduled").sum()))
    total_hours = sum(
        utils.minutes_between(r["start_time"], r["end_time"]) for _, r in active_appts.iterrows()
    ) / 60 if not active_appts.empty else 0
    m4.metric("Total vehicle-hours", f"{total_hours:.1f}")
 
    st.write("")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Trips by department")
        if active_appts.empty:
            st.caption("No trips in this date range.")
        else:
            by_dept = active_appts.groupby("department_name").size().sort_values(ascending=False)
            st.bar_chart(by_dept)
 
    with col_b:
        st.subheader("Trips by driver")
        if active_appts.empty:
            st.caption("No trips in this date range.")
        else:
            by_driver = active_appts.groupby("driver_name").size().sort_values(ascending=False).head(10)
            st.bar_chart(by_driver)
 
    st.subheader("Monthly trip volume")
    if active_appts.empty:
        st.caption("No trips in this date range.")
    else:
        monthly = active_appts.copy()
        monthly["month"] = pd.to_datetime(monthly["appt_date"]).dt.to_period("M").astype(str)
        by_month = monthly.groupby("month").size()
        st.line_chart(by_month)
 
    st.subheader("Vehicle utilization (hours booked)")
    if active_appts.empty:
        st.caption("No trips in this date range.")
    else:
        hours = active_appts.copy()
        hours["hours"] = hours.apply(
            lambda r: utils.minutes_between(r["start_time"], r["end_time"]) / 60, axis=1
        )
        by_vehicle = hours.groupby("plate_no")["hours"].sum().sort_values(ascending=False)
        st.bar_chart(by_vehicle)
 
    st.write("")
    st.subheader("🔧 Fleet compliance alerts")
    st.caption("Vehicles with insurance, revenue license, or service due within 30 days (or overdue).")
    attention = database.vehicles_needing_attention(warn_days=30)
    if attention.empty:
        st.success("No vehicles currently need attention.", icon="✅")
    else:
        st.dataframe(
            attention[["plate_no", "vehicle_type", "status", "issues"]].rename(columns={
                "plate_no": "Vehicle", "vehicle_type": "Type", "status": "Status", "issues": "Issues",
            }),
            use_container_width=True, hide_index=True,
        )
 
    st.write("")
    st.subheader("Export data")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        csv_download_button(appts, "Appointments CSV", "appointments.csv", "exp_appts")
    with e2:
        csv_download_button(database.get_drivers(), "Drivers CSV", "drivers.csv", "exp_drivers")
    with e3:
        csv_download_button(database.get_vehicles(), "Vehicles CSV", "vehicles.csv", "exp_vehicles")
    with e4:
        csv_download_button(database.get_trip_requests(), "Trip Requests CSV", "trip_requests.csv", "exp_reqs")

# PAGE EMPLOYEE PORTAL
def tab_add_appointment():
    st.subheader("New Appointment / Booking")
 
    drivers = database.get_drivers()
    vehicles = database.get_vehicles()
    departments = database.get_departments()
 
    driver_labels = {f"{r['name']} ({r['status']}) — ID {r['id']}": r["id"] for _, r in drivers.iterrows()}
    vehicle_labels = {f"{r['plate_no']} - {r['vehicle_type']} ({r['status']})": r["id"]
                       for _, r in vehicles.iterrows()}
 
    with st.form("add_appt_form"):
        col1, col2 = st.columns(2)
        with col1:
            appt_date = st.date_input("Date", value=datetime.date.today())
            start_time = st.selectbox("Start time", utils.TIME_OPTIONS, index=4)
            driver_label = st.selectbox("Driver", list(driver_labels.keys()))
        with col2:
            end_time = st.selectbox("End time", utils.TIME_OPTIONS, index=8)
            vehicle_label = st.selectbox("Vehicle", list(vehicle_labels.keys()))
            department_name = st.selectbox("Department / Destination", departments["name"].tolist())
 
        purpose = st.text_area("Purpose of trip", placeholder="e.g. Cash in transit to Kandy Regional Office")
        submitted = st.form_submit_button("Book Appointment", type="primary", use_container_width=True)
 
    if submitted:
        driver_id = int(driver_labels[driver_label])
        vehicle_id = int(vehicle_labels[vehicle_label])
        department_id = int(departments[departments["name"] == department_name].iloc[0]["id"])
 
        if end_time <= start_time:
            st.error("End time must be after start time.")
            return
 
        ok, conflicts = database.add_appointment(
            appt_date.isoformat(), start_time, end_time,
            driver_id, vehicle_id, department_id, purpose,
            created_by=auth.current_user()["username"],
        )
        if ok:
            st.success("Appointment booked successfully. Excel backup syncing in the background.")
            st.rerun()
        else:
            st.error("Booking rejected — conflict(s) detected:")
            for c in conflicts:
                st.write(f"- {c}")
 
 
def tab_manage_appointments():
    st.subheader("Manage Appointments")
 
    c1, c2 = st.columns(2)
    with c1:
        date_from = st.date_input("From", value=datetime.date.today() - datetime.timedelta(days=7))
    with c2:
        date_to = st.date_input("To", value=datetime.date.today() + datetime.timedelta(days=30))
 
    appts = database.get_appointments(date_from.isoformat(), date_to.isoformat())
    if appts.empty:
        st.caption("No appointments in this range.")
        return
 
    display_cols = ["id", "appt_date", "start_time", "end_time", "driver_name",
                     "plate_no", "department_name", "purpose", "status"]
    st.dataframe(
        appts[display_cols].rename(columns={
            "id": "ID", "appt_date": "Date", "start_time": "Start", "end_time": "End",
            "driver_name": "Driver", "plate_no": "Vehicle",
            "department_name": "Department", "purpose": "Purpose", "status": "Status",
        }),
        use_container_width=True, hide_index=True,
    )
    csv_download_button(appts, "Export Appointments CSV", "appointments.csv", "exp_appts_tab")
 
    st.markdown("**Update appointment status**")
    c3, c4, c5 = st.columns([1, 1, 1])
    with c3:
        appt_id = st.selectbox("Appointment ID", appts["id"].tolist())
    with c4:
        new_status = st.selectbox("New status", ["Scheduled", "Completed", "Cancelled"])
    with c5:
        st.write("")
        st.write("")
        if st.button("Apply Update", use_container_width=True):
            database.update_appointment_status(int(appt_id), new_status)
            st.success(f"Appointment #{appt_id} set to '{new_status}'.")
            st.rerun()

# MANAGE DRIVER TAB
def tab_manage_drivers():
    st.subheader("Manage Drivers")
    drivers = database.get_drivers()
    st.dataframe(
        drivers.rename(columns={
            "name": "Name", "license_no": "License No.", "phone": "Phone",
            "base_location": "Base", "status": "Status",
        })[["id", "Name", "License No.", "Phone", "Base", "Status"]],
        use_container_width=True, hide_index=True,
    )
    csv_download_button(drivers, "Export Drivers CSV", "drivers.csv", "exp_drivers_tab")
 
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("➕ Add new driver (optionally with a portal login)"):
            with st.form("add_driver_form"):
                name = st.text_input("Full name")
                license_no = st.text_input("License number")
                phone = st.text_input("Phone")
                base_location = st.text_input("Base location", value="Head Office Depot")
 
                st.markdown("---")
                create_login = st.checkbox("Also create a Driver Portal login for this driver")
                login_username = st.text_input("Login username", disabled=not create_login, key="drv_login_user")
                login_password = st.text_input("Login password", type="password",
                                                 disabled=not create_login, key="drv_login_pass")
 
                submitted = st.form_submit_button("Add Driver", use_container_width=True)
 
            if submitted:
                if not (name and license_no):
                    st.error("Name and license number are required.")
                elif create_login and not (login_username and login_password):
                    st.error("Provide a username and password, or untick the login checkbox.")
                elif create_login and database.username_exists(login_username.strip()):
                    st.error("That username is already taken.")
                else:
                    with database.get_cursor(commit=True) as cur:
                        cur.execute(
                            """INSERT INTO drivers (name, license_no, phone, base_location, status, lat, lon)
                               VALUES (?, ?, ?, ?, 'Available', 6.9271, 79.8612)""",
                            (name, license_no, phone, base_location),
                        )
                        new_driver_id = cur.lastrowid
                    database._touch_backup()
                    if create_login:
                        database.create_login(login_username.strip(), login_password, name,
                                               "Driver", linked_driver_id=new_driver_id)
                        st.success(f"Driver '{name}' added with a portal login.")
                    else:
                        st.success(f"Driver '{name}' added.")
                    st.rerun()
 
    with col2:
        with st.expander("🔄 Update driver status"):
            with st.form("update_driver_form"):
                driver_id = st.selectbox("Driver", drivers["id"].tolist(),
                                          format_func=lambda i: drivers[drivers["id"] == i].iloc[0]["name"])
                new_status = st.selectbox("Status", list(utils.DRIVER_STATUS_COLORS.keys()))
                if st.form_submit_button("Update Status", use_container_width=True):
                    database.update_driver_status(int(driver_id), new_status)
                    st.success("Driver status updated.")
                    st.rerun()


# MANAGE VEHICLES
def tab_manage_vehicles():
    st.subheader("Manage Vehicles")
    vehicles = database.get_vehicles()
 
    attention = database.vehicles_needing_attention(warn_days=30)
    if not attention.empty:
        st.warning(f"⚠️ {len(attention)} vehicle(s) need attention — see Reports & Analytics for details, "
                   f"or update dates below.", icon="🔧")
 
    st.dataframe(
        vehicles.rename(columns={
            "plate_no": "Plate No.", "vehicle_type": "Type",
            "capacity": "Capacity", "status": "Status",
            "insurance_expiry": "Insurance Exp.", "revenue_license_expiry": "Revenue Lic. Exp.",
            "next_service_due": "Next Service",
        })[["id", "Plate No.", "Type", "Capacity", "Status",
            "Insurance Exp.", "Revenue Lic. Exp.", "Next Service"]],
        use_container_width=True, hide_index=True,
    )
    csv_download_button(vehicles, "Export Vehicles CSV", "vehicles.csv", "exp_vehicles_tab")
 
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("➕ Add new vehicle"):
            with st.form("add_vehicle_form"):
                plate_no = st.text_input("Plate number")
                vehicle_type = st.selectbox("Type", ["Van", "Car", "Double Cab", "Bus", "Lorry"])
                capacity = st.number_input("Capacity", min_value=1, max_value=60, value=4)
                st.markdown("---")
                st.caption("Compliance dates (optional, can be added later)")
                insurance_expiry = st.date_input("Insurance expiry", value=None, key="new_veh_ins")
                revenue_license_expiry = st.date_input("Revenue license expiry", value=None, key="new_veh_rev")
                next_service_due = st.date_input("Next service due", value=None, key="new_veh_svc")
                if st.form_submit_button("Add Vehicle", use_container_width=True):
                    if plate_no:
                        try:
                            database.add_vehicle(
                                plate_no, vehicle_type, int(capacity), lat=6.9271, lon=79.8612,
                                insurance_expiry=insurance_expiry.isoformat() if insurance_expiry else None,
                                revenue_license_expiry=revenue_license_expiry.isoformat() if revenue_license_expiry else None,
                                next_service_due=next_service_due.isoformat() if next_service_due else None,
                            )
                            st.success(f"Vehicle '{plate_no}' added.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not add vehicle (duplicate plate?): {e}")
                    else:
                        st.error("Plate number is required.")
 
        with st.expander("🔧 Update compliance dates"):
            with st.form("update_compliance_form"):
                vehicle_id_c = st.selectbox("Vehicle", vehicles["id"].tolist(),
                                             format_func=lambda i: vehicles[vehicles["id"] == i].iloc[0]["plate_no"],
                                             key="compliance_vehicle_select")
                current = vehicles[vehicles["id"] == vehicle_id_c].iloc[0]
 
                def _parse(d):
                    try:
                        return datetime.date.fromisoformat(d) if d else None
                    except (TypeError, ValueError):
                        return None
 
                ins = st.date_input("Insurance expiry", value=_parse(current["insurance_expiry"]))
                rev = st.date_input("Revenue license expiry", value=_parse(current["revenue_license_expiry"]))
                svc = st.date_input("Next service due", value=_parse(current["next_service_due"]))
                if st.form_submit_button("Update Compliance Dates", use_container_width=True):
                    database.update_vehicle_compliance(
                        int(vehicle_id_c),
                        insurance_expiry=ins.isoformat() if ins else None,
                        revenue_license_expiry=rev.isoformat() if rev else None,
                        next_service_due=svc.isoformat() if svc else None,
                    )
                    st.success("Compliance dates updated.")
                    st.rerun()
 
    with col2:
        with st.expander("🔄 Update vehicle status"):
            with st.form("update_vehicle_form"):
                vehicle_id = st.selectbox("Vehicle", vehicles["id"].tolist(),
                                           format_func=lambda i: vehicles[vehicles["id"] == i].iloc[0]["plate_no"])
                new_status = st.selectbox("Status", list(utils.VEHICLE_STATUS_COLORS.keys()))
                if st.form_submit_button("Update Status", use_container_width=True):
                    database.update_vehicle_status(int(vehicle_id), new_status)
                    st.success("Vehicle status updated.")
                    st.rerun()

# PENDING REQUESTS TAB
def tab_pending_requests():
    st.subheader("Department Transport Requests")
    st.caption("Requests submitted by branches/divisions via the Department Portal. "
               "Approving assigns a driver + vehicle and runs the same conflict check as a normal booking.")
 
    status_filter = st.radio("Show", ["Pending", "Approved", "Rejected", "Cancelled", "All"],
                              horizontal=True, key="req_status_filter")
    reqs = database.get_trip_requests(status=None if status_filter == "All" else status_filter)
 
    if reqs.empty:
        st.caption("No requests in this category.")
        return
 
    display_cols = ["id", "department_name", "appt_date", "start_time", "end_time",
                     "purpose", "status", "requested_by", "driver_name", "plate_no"]
    st.dataframe(
        reqs[display_cols].rename(columns={
            "id": "ID", "department_name": "Department", "appt_date": "Date",
            "start_time": "Start", "end_time": "End", "purpose": "Purpose",
            "status": "Status", "requested_by": "Requested By",
            "driver_name": "Assigned Driver", "plate_no": "Assigned Vehicle",
        }),
        use_container_width=True, hide_index=True,
    )
 
    pending = database.get_trip_requests(status="Pending")
    if pending.empty:
        return
 
    st.markdown("**Review a pending request**")
    drivers = database.get_drivers()
    vehicles = database.get_vehicles()
 
    req_options = {
        f"#{r['id']} — {r['department_name']} — {r['appt_date']} {r['start_time']}-{r['end_time']}": r["id"]
        for _, r in pending.iterrows()
    }
    driver_labels = {f"{r['name']} ({r['status']})": r["id"] for _, r in drivers.iterrows()}
    vehicle_labels = {f"{r['plate_no']} - {r['vehicle_type']} ({r['status']})": r["id"]
                       for _, r in vehicles.iterrows()}
 
    c1, c2, c3 = st.columns(3)
    with c1:
        req_choice = st.selectbox("Request", list(req_options.keys()))
    with c2:
        driver_choice = st.selectbox("Assign driver", list(driver_labels.keys()))
    with c3:
        vehicle_choice = st.selectbox("Assign vehicle", list(vehicle_labels.keys()))
 
    a1, a2 = st.columns(2)
    with a1:
        if st.button("✅ Approve & Assign", type="primary", use_container_width=True):
            ok, conflicts = database.approve_trip_request(
                req_options[req_choice], driver_labels[driver_choice], vehicle_labels[vehicle_choice]
            )
            if ok:
                st.success("Request approved and appointment created.")
                st.rerun()
            else:
                st.error("Could not approve — conflict(s) detected:")
                for c in conflicts:
                    st.write(f"- {c}")
    with a2:
        with st.popover("❌ Reject request", use_container_width=True):
            note = st.text_area("Reason (optional)", key="reject_note")
            if st.button("Confirm rejection", key="confirm_reject"):
                database.reject_trip_request(req_options[req_choice], note)
                st.success("Request rejected.")
                st.rerun()

# TAB MANAGE DRIVERS
def tab_manage_departments():
    st.subheader("Manage Departments / Branches")
    departments = database.get_departments()
    st.dataframe(
        departments.rename(columns={
            "name": "Name", "location": "Location", "lat": "Latitude", "lon": "Longitude",
        })[["id", "Name", "Location", "Latitude", "Longitude"]],
        use_container_width=True, hide_index=True,
    )
 
    with st.expander("➕ Add new department / branch (optionally with a portal login)"):
        with st.form("add_department_form"):
            name = st.text_input("Department / branch name")
            location = st.text_input("Location (city/area)")
            lat = st.number_input("Latitude", value=6.9271, format="%.4f")
            lon = st.number_input("Longitude", value=79.8612, format="%.4f")
 
            st.markdown("---")
            create_login = st.checkbox("Also create a Department Portal login for this branch")
            login_username = st.text_input("Login username", disabled=not create_login)
            login_password = st.text_input("Login password", type="password", disabled=not create_login)
 
            submitted = st.form_submit_button("Add Department", use_container_width=True)
 
        if submitted:
            if not name:
                st.error("Department name is required.")
            elif create_login and not (login_username and login_password):
                st.error("Provide a username and password, or untick the login checkbox.")
            elif create_login and database.username_exists(login_username.strip()):
                st.error("That username is already taken.")
            else:
                dept_id = database.add_department(name, location, lat, lon)
                if create_login:
                    database.create_login(login_username.strip(), login_password, name,
                                           "Department", linked_department_id=dept_id)
                    st.success(f"Department '{name}' added with a portal login.")
                else:
                    st.success(f"Department '{name}' added.")
                st.rerun()

# TAB LEAVE REQUESTS
def tab_leave_requests():
    st.subheader("Driver Leave Requests")
 
    status_filter = st.radio("Show", ["Pending", "Approved", "Rejected", "All"],
                              horizontal=True, key="leave_status_filter")
    leaves = database.get_leave_requests(status=None if status_filter == "All" else status_filter)
 
    if leaves.empty:
        st.caption("No leave requests in this category.")
        return
 
    st.dataframe(
        leaves[["id", "driver_name", "start_date", "end_date", "reason", "status"]].rename(columns={
            "id": "ID", "driver_name": "Driver", "start_date": "From", "end_date": "To",
            "reason": "Reason", "status": "Status",
        }),
        use_container_width=True, hide_index=True,
    )
 
    pending = database.get_leave_requests(status="Pending")
    if pending.empty:
        return
 
    st.markdown("**Review a pending leave request**")
    options = {
        f"#{r['id']} — {r['driver_name']} — {r['start_date']} to {r['end_date']}": r["id"]
        for _, r in pending.iterrows()
    }
    choice = st.selectbox("Request", list(options.keys()), key="leave_review_select")
 
    a1, a2 = st.columns(2)
    with a1:
        if st.button("✅ Approve Leave", type="primary", use_container_width=True):
            database.approve_leave_request(options[choice])
            st.success("Leave approved.")
            st.rerun()
    with a2:
        with st.popover("❌ Reject leave", use_container_width=True):
            note = st.text_area("Reason (optional)", key="leave_reject_note")
            if st.button("Confirm rejection", key="leave_confirm_reject"):
                database.reject_leave_request(options[choice], note)
                st.success("Leave rejected.")
                st.rerun()