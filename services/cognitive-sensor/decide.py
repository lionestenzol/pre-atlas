import sqlite3
import subprocess
import urllib.request
import json
import os
from datetime import datetime

con = sqlite3.connect("results.db")
cur = con.cursor()

# Get most recent resurfaced loop
try:
    text = open("RESURFACER_LOG.md", encoding="utf-8").read().strip().split("UNRESOLVED LOOP:")[-1]
    title = text.split("\n")[1].strip()
except:
    print("No resurfaced loop found.")
    exit()

# Find convo_id by title
row = cur.execute("SELECT convo_id FROM convo_titles WHERE title=?", (title,)).fetchone()
if not row:
    print("Loop not found.")
    exit()

cid = row[0]

print("\nCurrent loop:")
print(title)
print("\nChoose:")
print("1 = CLOSE")
print("2 = CONTINUE")
print("3 = ARCHIVE")

choice = input("> ").strip()

if choice == "1":
    decision = "CLOSE"
elif choice == "2":
    decision = "CONTINUE"
elif choice == "3":
    decision = "ARCHIVE"
else:
    print("Invalid choice.")
    exit()

cur.execute("INSERT INTO loop_decisions VALUES (?,?,?)",
            (cid, decision, datetime.now().strftime("%Y-%m-%d %H:%M")))
con.commit()
con.close()

print("Decision recorded:", decision)

# --- Auto-refresh pipeline after decision ---
refresh_script = os.path.join(os.path.dirname(__file__), "refresh.py")
if os.path.exists(refresh_script):
    print("\nRefreshing pipeline...")
    result = subprocess.run(
        ["python", refresh_script],
        cwd=os.path.dirname(__file__),
        capture_output=True, text=True, timeout=120
    )
    if result.returncode == 0:
        print("Pipeline refreshed successfully.")
    else:
        print("Refresh failed:", result.stderr[:300] if result.stderr else "unknown error")
else:
    print("Warning: refresh.py not found, skipping auto-refresh.")

# Notify delta-kernel API (if running)
try:
    req = urllib.request.Request(
        "http://localhost:3001/api/law/refresh",
        data=json.dumps({}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    urllib.request.urlopen(req, timeout=5)
    print("Delta-kernel notified.")
except Exception:
    print("Delta-kernel not reachable (API may not be running).")
