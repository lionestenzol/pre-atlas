# ▶️ START HERE — Pre Atlas (Your Platform)

**What it is:** Your big personal "operating system" — about 16 small backend services (planning, execution, perception, messaging, a dashboard, and more) that work together.

**To start the whole thing at once:**
1. Open **Docker Desktop** first and let it finish starting.
2. Then run:
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\bruke\Pre Atlas\scripts\start_all_services.ps1"
```
This boots the core services, runs your daily routine, and opens the Atlas dashboard.

**To start just one service:** see `services\START-HERE.md` (in `C:\Users\bruke\pre-atlas\services\`) for the exact command for each one.

**Status:** 🟢 Most services work. A few are unfinished (`perception`, `triangulation`) or empty (`crucix`). Needs Docker Desktop for the full platform.

**The map of everything on this computer:** `C:\Users\bruke\START-HERE\OPERATOR-HANDBOOK.md`
