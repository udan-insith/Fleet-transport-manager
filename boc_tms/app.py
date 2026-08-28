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