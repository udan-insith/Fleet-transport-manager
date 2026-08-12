import streamlit as st
import database

ROLE_DRIVER = "Driver"
ROLE_DEPARTMENT = "Department"
ROLE_OFFICER = "Transport Officer"


def is_logged_in() -> bool:
    return st.session_state.get("auth_user") is not None


def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def current_role() -> str | None:
    user = current_user()
    return user["role"] if user else None

