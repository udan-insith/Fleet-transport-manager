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