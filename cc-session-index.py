import os, datetime, json, sys, re

CWD_PATTERN = re.compile(r'"cwd"\s*:\s*"((?:[^"\\]|\\.)*)"')

def extract_cwd(project_dir):
    for r, dirs, files in os.walk(project_dir):
        for f in files:
            if not f.endswith(".jsonl"):
                continue
            fp = os.path.join(r, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                    chunk = fh.read(16384)
                m = CWD_PATTERN.search(chunk)
                if m:
                    return m.group(1).encode().decode("unicode_escape")
            except Exception:
                pass
    return None

ROOT = r"C:\Users\bruke\.claude\projects"
OUT_MD = r"C:\Users\bruke\Pre Atlas\cc-session-index.md"
OUT_JSON = r"C:\Users\bruke\Pre Atlas\cc-session-index.json"

rows = []
grand_count = 0
grand_sub = 0
grand_bytes = 0
all_mtimes = []

for entry in os.scandir(ROOT):
    if not entry.is_dir():
        continue
    name = entry.name
    count_main = 0
    count_sub = 0
    total_bytes = 0
    mtimes = []
    sample_session_ids = []
    for r, dirs, files in os.walk(entry.path):
        for f in files:
            if not f.endswith(".jsonl"):
                continue
            fp = os.path.join(r, f)
            try:
                st = os.stat(fp)
                total_bytes += st.st_size
                mtimes.append(st.st_mtime)
                if "subagents" in r.lower():
                    count_sub += 1
                else:
                    count_main += 1
                    if len(sample_session_ids) < 3:
                        sample_session_ids.append(f.replace(".jsonl", ""))
            except Exception:
                pass
    total = count_main + count_sub
    if total == 0:
        continue
    newest = max(mtimes) if mtimes else 0
    oldest = min(mtimes) if mtimes else 0
    cwd = extract_cwd(entry.path)
    rows.append({
        "slug": name,
        "cwd": cwd,
        "sessions_main": count_main,
        "sessions_subagent": count_sub,
        "size_bytes": total_bytes,
        "first_mtime": oldest,
        "last_mtime": newest,
        "sample_session_ids": sample_session_ids,
    })
    grand_count += count_main
    grand_sub += count_sub
    grand_bytes += total_bytes
    all_mtimes.extend(mtimes)

rows.sort(key=lambda r: -(r["sessions_main"] + r["sessions_subagent"]))

def fmt_date(t):
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d") if t else "-"

def fmt_mb(b):
    return f"{b/(1024*1024):.1f} MB" if b >= 1024*1024 else f"{b/1024:.1f} KB"


with open(OUT_MD, "w", encoding="utf-8") as f:
    f.write("# Claude Code Session Index\n\n")
    f.write(f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}\n\n")
    f.write(f"Source: `{ROOT}`\n\n")
    f.write("## Totals\n\n")
    f.write(f"- Project directories with sessions: **{len(rows)}**\n")
    f.write(f"- Top-level session files: **{grand_count}**\n")
    f.write(f"- Subagent session files: **{grand_sub}**\n")
    f.write(f"- Grand total .jsonl: **{grand_count + grand_sub}**\n")
    f.write(f"- Total size on disk: **{grand_bytes/(1024*1024):.1f} MB**\n")
    if all_mtimes:
        f.write(f"- Date range: **{fmt_date(min(all_mtimes))}** to **{fmt_date(max(all_mtimes))}**\n")
    f.write("\n## Per-project index (sorted by session count, descending)\n\n")
    f.write("| # | Sessions | Subagents | Size | First | Last | Working directory (from JSONL) | Project slug |\n")
    f.write("|---:|---:|---:|---:|---|---|---|---|\n")
    for i, row in enumerate(rows, 1):
        cwd_disp = f"`{row['cwd']}`" if row['cwd'] else "_(no cwd record found)_"
        f.write(f"| {i} | {row['sessions_main']} | {row['sessions_subagent']} | {fmt_mb(row['size_bytes'])} | {fmt_date(row['first_mtime'])} | {fmt_date(row['last_mtime'])} | {cwd_disp} | `{row['slug']}` |\n")

with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump({
        "generated_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "source_root": ROOT,
        "totals": {
            "project_dirs": len(rows),
            "sessions_main": grand_count,
            "sessions_subagent": grand_sub,
            "sessions_total": grand_count + grand_sub,
            "size_bytes": grand_bytes,
            "date_first": fmt_date(min(all_mtimes)) if all_mtimes else None,
            "date_last": fmt_date(max(all_mtimes)) if all_mtimes else None,
        },
        "projects": rows,
    }, f, indent=2)

print(f"Wrote:\n  {OUT_MD}\n  {OUT_JSON}")
print()
print(f"Totals: {len(rows)} project dirs · {grand_count} sessions + {grand_sub} subagents · {grand_bytes/(1024*1024):.1f} MB")
if all_mtimes:
    print(f"Date range: {fmt_date(min(all_mtimes))} -> {fmt_date(max(all_mtimes))}")
