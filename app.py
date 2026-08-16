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

#PAGE CONFIG + ONE-TIME INITIALIZATION
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

#THEME + CSS INJECTION
def inject_theme():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {utils.BOC_BG};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {utils.BOC_NAVY};
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
            background-color: {utils.BOC_NAVY};
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
            background-color: {utils.BOC_WHITE};
            border: 1px solid #E0E4EA;
            border-left: 5px solid {utils.BOC_NAVY};
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

#SETTING UP LIVE DASHBOARD
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