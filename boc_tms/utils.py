import math

# --------------------------------------------------------------------------
# BOC brand palette
# --------------------------------------------------------------------------
BOC_NAVY = "#003366"
BOC_NAVY_LIGHT = "#0A4D8C"
BOC_GOLD = "#FFCC00"
BOC_BG = "#F4F6F9"
BOC_WHITE = "#FFFFFF"

# Dark-mode counterparts, used by app.inject_theme() when
# st.context.theme.type == "dark". Keep these in sync with the
# [theme.dark] table in .streamlit/config.toml.
BOC_DARK_BG = "#0B1E33"
BOC_DARK_CARD = "#13294B"
BOC_DARK_SIDEBAR = "#001830"
BOC_DARK_TEXT = "#F4F6F9"

DRIVER_STATUS_COLORS = {
    "Available": "#2ECC71",
    "On Trip": "#FFCC00",
    "Off Duty": "#95A5A6",
    "On Leave": "#E74C3C",
}

VEHICLE_STATUS_COLORS = {
    "Available": "#2ECC71",
    "In Use": "#FFCC00",
    "Maintenance": "#E74C3C",
}

DEPARTMENT_PALETTE = [
    "#003366", "#FFCC00", "#2ECC71", "#8E44AD", "#E67E22",
    "#16A085", "#C0392B", "#2980B9", "#7F8C8D", "#D35400",
]


def department_color(department_name: str, department_list: list[str]) -> str:
    """Deterministic color per department, for the scheduler matrix."""
    if department_name not in department_list:
        return "#DDDDDD"
    idx = department_list.index(department_name) % len(DEPARTMENT_PALETTE)
    return DEPARTMENT_PALETTE[idx]


# --------------------------------------------------------------------------
# Geo helpers
# --------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two points, in kilometres."""
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------

TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(6, 21) for m in (0, 30)]


def minutes_between(start_hhmm: str, end_hhmm: str) -> int:
    sh, sm = map(int, start_hhmm.split(":"))
    eh, em = map(int, end_hhmm.split(":"))
    return (eh * 60 + em) - (sh * 60 + sm)