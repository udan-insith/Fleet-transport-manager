"""
auth.py
-------
Session-based authentication for the three portals:
  * Transport Officer  - full fleet/booking control
  * Driver              - sees/manages only their own schedule
  * Department          - a requesting branch/division; submits transport
                           requests and tracks their own status

Not intended as bank-grade security -- this is a demo/internal-tool login
gate (SHA-256 hashed passwords, Streamlit session_state as the session
store). Swap in BOC's real SSO/AD integration for production use.

Only one role can be signed in per browser session at a time, which
mirrors how a real single login session works. If someone tries to open
a different portal page while already signed in elsewhere, they're asked
to log out first rather than silently being allowed to hold two roles.
"""

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


def login_form(expected_role: str, demo_username: str, demo_password: str, hint: str = ""):
    """
    Renders a login form scoped to `expected_role`. Login only succeeds if
    the account's role in the database matches `expected_role` -- this is
    what keeps the three portals separate (an admin account can't sign into
    the Driver portal, a driver account can't sign into the Department
    portal, etc.), even though all three share one `users` table.
    """
    st.markdown(f"#### {expected_role} sign in")
    if hint:
        st.caption(hint)

    form_key = f"login_form_{expected_role.replace(' ', '_')}"
    with st.form(form_key, clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

    if submitted:
        user = database.verify_login(username.strip(), password)
        if user and user["role"] == expected_role:
            st.session_state["auth_user"] = user
            st.success(f"Welcome, {user['full_name']}.")
            st.rerun()
        elif user and user["role"] != expected_role:
            st.error(f"This account is registered as '{user['role']}', not '{expected_role}'. "
                      f"Use the correct portal for this login.")
        else:
            st.error("Invalid username or password.")

    with st.expander("Demo credentials"):
        st.code(f"username: {demo_username}\npassword: {demo_password}", language="text")


def logout_button():
    if st.sidebar.button("Log out", use_container_width=True):
        st.session_state.pop("auth_user", None)
        st.rerun()


def require_role_or_login(expected_role: str, demo_username: str, demo_password: str, hint: str = "") -> bool:
    """
    Standard guard used at the top of every portal page.
    Returns True if the correctly-scoped user is signed in and the caller
    should render the dashboard; returns False if it already rendered a
    login form or a "wrong portal" notice instead.
    """
    if is_logged_in():
        if current_role() == expected_role:
            return True
        st.warning(
            f"You're currently signed in as **{current_user()['full_name']}** "
            f"({current_role()}). Log out to switch to the {expected_role} portal."
        )
        logout_button()
        return False

    left, mid, right = st.columns([1, 1.2, 1])
    with mid:
        login_form(expected_role, demo_username, demo_password, hint)
    return False
