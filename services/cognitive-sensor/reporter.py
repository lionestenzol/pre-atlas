import subprocess
from datetime import datetime

print("Running radar...")
out = subprocess.check_output(["python", "radar.py"], text=True)

stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

with open("STATE_HISTORY.md", "a", encoding="utf-8") as f:
    f.write("\n\n")
    f.write(f"## {stamp}\n")
    f.write(out)

print("STATE_HISTORY.md updated.")
