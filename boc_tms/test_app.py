from streamlit.testing.v1 import AppTest

def check(at, label):
    if at.exception:
        print(f"[{label}] EXCEPTION(S):")
        for e in at.exception:
            print("  -", e)
        return False
    print(f"[{label}] OK - no exceptions. Elements: "
          f"{len(at.get('metric'))} metrics, {len(at.get('dataframe'))} tables")
    return True

at = AppTest.from_file("app.py", default_timeout=30)
at.run()
ok1 = check(at, "Dashboard (default page)")

# Switch to Live GPS Map
at.sidebar.radio[0].set_value("Live GPS Map").run()
ok2 = check(at, "Live GPS Map")

# Switch to Monthly Scheduler
at.sidebar.radio[0].set_value("Monthly Scheduler").run()
ok3 = check(at, "Monthly Scheduler")

# Switch to Transport Officer Portal (logged out state)
at.sidebar.radio[0].set_value("Transport Officer Portal").run()
ok4 = check(at, "Transport Officer Portal (logged out)")

# Attempt officer login
try:
    at.text_input[0].set_value("admin")
    at.text_input[1].set_value("BOC@Transport2026")
    at.button[0].click().run()
    ok5 = check(at, "Transport Officer Portal (after login attempt)")
except Exception as e:
    print("[Officer login flow] harness-level error:", e)
    ok5 = False
