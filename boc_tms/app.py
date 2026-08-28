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
 