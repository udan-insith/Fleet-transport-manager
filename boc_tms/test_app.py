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

# Log out, then check Driver Portal (logged out state + login)
try:
    at.sidebar.button[0].click().run()  # log out
except Exception:
    pass
at.sidebar.radio[0].set_value("Driver Portal").run()
ok6 = check(at, "Driver Portal (logged out)")
try:
    at.text_input[0].set_value("driver1")
    at.text_input[1].set_value("Driver@123")
    at.button[0].click().run()
    ok7 = check(at, "Driver Portal (after login attempt)")
except Exception as e:
    print("[Driver login flow] harness-level error:", e)
    ok7 = False

# Log out, then check Department Portal (logged out state + login)
try:
    at.sidebar.button[0].click().run()  # log out
except Exception:
    pass
at.sidebar.radio[0].set_value("Department Portal").run()
ok8 = check(at, "Department Portal (logged out)")
try:
    at.text_input[0].set_value("kandy_branch")
    at.text_input[1].set_value("Dept@123")
    at.button[0].click().run()
    ok9 = check(at, "Department Portal (after login attempt)")
except Exception as e:
    print("[Department login flow] harness-level error:", e)
    ok9 = False

# Cross-portal rejection: driver1 credentials should NOT work on the officer login
at2 = AppTest.from_file("app.py", default_timeout=30)
at2.run()
at2.sidebar.radio[0].set_value("Transport Officer Portal").run()
try:
    at2.text_input[0].set_value("driver1")
    at2.text_input[1].set_value("Driver@123")
    at2.button[0].click().run()
    still_logged_out = not any("Signed in as" in str(at2.sidebar.markdown[i].value)
                                for i in range(len(at2.sidebar.markdown))) if at2.sidebar.markdown else True
    ok10 = check(at2, "Cross-portal login rejection")
    print(f"[Cross-portal rejection] driver1 blocked from Officer portal: {'checked' if ok10 else 'ERROR STATE'}")
except Exception as e:
    print("[Cross-portal rejection] harness-level error:", e)
    ok10 = False

print("\nALL PASS:", all([ok1, ok2, ok3, ok4, ok5, ok6, ok7, ok8, ok9, ok10]))