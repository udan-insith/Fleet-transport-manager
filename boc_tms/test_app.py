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