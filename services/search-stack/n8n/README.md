# n8n workflow templates

Drop-in JSON workflows for the search-stack ↔ n8n seam.

## daily-intel.json

What it does:
- Fires daily at 7am (cron `0 7 * * *`)
- Iterates a topic list (edit the `Topics` code node)
- For each topic, calls `POST localhost:3070/search`
- Shapes each hit as an `intel_drop` packet
- POSTs to DropList intake (defaults to `localhost:3070/memory/save`, override with `DROPLIST_INTAKE_URL` env)

To activate:
1. Open n8n (`n8n` from terminal or your hosted instance)
2. Import → "From File" → select `daily-intel.json`
3. Open the `Topics` node, edit the array to your real targets
4. Toggle the workflow `Active` on
5. (Optional) Set `DROPLIST_INTAKE_URL` if DropList intake lives elsewhere

## Why not run the cron inside search-stack itself?

n8n owns scheduling + retry + fan-out. search-stack owns dispatch + budget guards. Each tool stays minimal. Pre Atlas already has n8n installed (npm-global) — this just adds one workflow file.

## Adding more workflows

Pattern is always: Schedule → Topics → search-stack → Shape → Save (or notify, email, Slack, etc.). Keep them in this directory so they stay versioned with the service contract that backs them.
