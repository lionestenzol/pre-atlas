"""
verify_coverage — check whether a built artifact covers the concepts
extracted from a harvested thread.

Inputs:
  - concepts.json (from parse_conversation.py)
  - an artifact path (directory or file) to audit

Output:
  coverage.json / coverage.md next to concepts.json, with each concept
  marked as one of:
    covered       - strong signal found in artifact (file-content match)
    partial       - filename hit but no direct content match
    missing       - nothing matched
    unverifiable  - concept kind (idea/decision) needs human review

Local-only. No LLM calls.

Usage:
  python verify_coverage.py 487 apps/ai-exec-pipeline
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

BASE = Path(__file__).parent.resolve()
REPO_ROOT = BASE.parent.parent  # services/cognitive-sensor → services → repo

# Verification strategy per technical signal.
# content_patterns: regexes to search inside artifact text files
# file_globs:       filenames whose presence is a strong positive
VERIFIERS: dict[str, dict] = {
    "flask-server":       {"content": [r"\bfrom flask import", r"\bFlask\s*\("]},
    "flask-cors":         {"content": [r"flask[_-]cors", r"\bCORS\s*\("]},
    "json-persistence":   {"content": [r"json\.(dump|load)", r"\.json['\"]"]},
    "api-key-auth":       {"content": [r"X-API-KEY", r"API_KEY", r"VALID_API_KEYS"]},
    "openai":             {"content": [r"\bimport openai\b", r"from openai\b", r"ChatCompletion"]},
    "anthropic":          {"content": [r"from anthropic", r"\banthropic\b", r"claude[-_]api"]},
    "react-native":       {"content": [r"react-native", r"@react-navigation"], "files": ["*.jsx", "App.tsx", "metro.config.js"]},
    "react-web":          {"content": [r"import React\b", r"useState\(", r"useEffect\("], "files": ["*.jsx", "*.tsx"]},
    "axios":              {"content": [r"\baxios\.", r"from ['\"]axios['\"]"]},
    "requests-py":        {"content": [r"\bimport requests\b", r"requests\.(get|post)"]},
    "google-drive":       {"content": [r"googleapiclient", r"google\.oauth2"]},
    "polling-loop":       {"content": [r"while True", r"time\.sleep"]},
    "websocket":          {"content": [r"\bwebsockets?\b", r"socket\.io", r"\bWebSocket\b"]},
    "sqlite":             {"content": [r"\bimport sqlite3\b", r"sqlite3\.connect"]},
    "dart-flutter":       {"content": [r"import 'package:flutter"], "files": ["*.dart", "pubspec.yaml"]},
    "dotenv":             {"content": [r"from dotenv", r"load_dotenv"], "files": [".env", ".env.example"]},
    "cron-schedule":      {"content": [r"\bschedule\.every", r"APScheduler", r"\bcron\b"]},
    "subprocess-cli":     {"content": [r"subprocess\.(run|Popen)"]},
    "iteration-tracker":  {"content": [r"iteration", r"workflow_status", r"conversation_flow"]},
    "execution-pipeline": {"content": [r"execution[_ ]pipeline", r"ExecutionPipeline", r"AI[_ ]Execution"]},
    "report-generation":  {"content": [r"generate[_ ]?report", r"weekly[_ ]?report"]},
}

TEXT_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".yaml", ".yml",
    ".html", ".css", ".sh", ".dart", ".toml", ".ini", ".cfg", ".env", ".example",
}


@dataclass
class CoverageRow:
    id: str
    kind: str
    label: str
    signal: str
    status: str                # covered | partial | missing | unverifiable
    evidence: list[str]        # file paths / match notes
    note: str = ""


def _load_artifact_text(artifact: Path) -> dict[Path, str]:
    """Load all text files under artifact into memory. Small artifacts only."""
    if artifact.is_file():
        return {artifact: _safe_read(artifact)}
    out: dict[Path, str] = {}
    for p in artifact.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in TEXT_EXT and p.name not in {".env", ".env.example", ".gitignore"}:
            continue
        if any(seg in p.parts for seg in ("node_modules", "__pycache__", ".venv", "dist", "build")):
            continue
        out[p] = _safe_read(p)
    return out


def _safe_read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def verify_technical(concept: dict, files: dict[Path, str], artifact_root: Path) -> CoverageRow:
    sig = concept["signal"]
    spec = VERIFIERS.get(sig)
    if spec is None:
        return CoverageRow(
            id=concept["id"], kind=concept["kind"], label=concept["label"], signal=sig,
            status="unverifiable", evidence=[], note=f"No verifier for signal '{sig}'",
        )

    evidence: list[str] = []
    content_hits = 0
    for path, text in files.items():
        rel = str(path.relative_to(artifact_root)) if path != artifact_root else path.name
        for pat in spec.get("content", []):
            if re.search(pat, text):
                content_hits += 1
                evidence.append(f"{rel}: /{pat}/")
                break  # one hit per file is enough

    file_hits = 0
    for glob in spec.get("files", []):
        if artifact_root.is_dir():
            matches = list(artifact_root.rglob(glob)) if "/" in glob or "*" in glob else []
            if not matches:
                matches = [p for p in artifact_root.rglob("*") if p.name == glob]
            if matches:
                file_hits += len(matches)
                evidence.append(f"file: {matches[0].relative_to(artifact_root)}")

    if content_hits > 0:
        status = "covered"
    elif file_hits > 0:
        status = "partial"
    else:
        status = "missing"

    return CoverageRow(
        id=concept["id"], kind=concept["kind"], label=concept["label"], signal=sig,
        status=status, evidence=evidence[:5],
    )


def _artifact_summary(artifact: Path, files: dict[Path, str], max_chars: int = 6000) -> str:
    """Compact artifact summary: tree + README + file heads. For LLM batch audit."""
    lines: list[str] = []
    lines.append(f"PATH: {artifact}")
    lines.append("")
    lines.append("FILES:")
    for p in sorted(files.keys()):
        rel = p.relative_to(artifact) if artifact.is_dir() else p.name
        lines.append(f"  {rel} ({len(files[p])} chars)")
    lines.append("")

    # Prefer README + package manifests as primary context
    primary_names = ("README.md", "readme.md", "package.json", "requirements.txt", "pyproject.toml")
    primary = [p for p in files if p.name in primary_names]
    rest = [p for p in files if p not in primary]

    def _dump(p: Path, budget: int) -> str:
        rel = p.relative_to(artifact) if artifact.is_dir() else p.name
        body = files[p]
        head = body[:budget]
        return f"\n--- {rel} ---\n{head}"

    budget = max_chars
    for p in primary:
        chunk = _dump(p, min(2000, budget))
        lines.append(chunk)
        budget -= len(chunk)
        if budget <= 0:
            break
    for p in rest:
        if budget <= 200:
            break
        chunk = _dump(p, min(800, budget))
        lines.append(chunk)
        budget -= len(chunk)

    return "\n".join(lines)


def _auto_check_soft_concepts(
    concepts: list[dict],
    artifact_summary: str,
) -> dict[str, tuple[str, str]]:
    """
    Batch-audit idea/decision concepts via `claude -p` in a SINGLE call.
    Returns {concept_id: (status, reason)}.
    status ∈ {"covered", "partial", "missing"}.
    """
    soft = [c for c in concepts if c["kind"] in ("idea", "decision")]
    if not soft:
        return {}

    concept_block = "\n".join(
        f'[{c["id"]}] ({c["kind"]}) {c["evidence_quote"]}' for c in soft
    )

    prompt = f"""You are auditing whether a built software artifact reflects concepts discussed in a planning conversation.

Decide for each concept whether the artifact CLEARLY covers it, PARTIALLY covers it, or MISSES it.
- "covered": artifact visibly addresses this intent
- "partial": some evidence but weak or incomplete
- "missing": no evidence in the artifact

ARTIFACT SUMMARY:
{artifact_summary}

CONCEPTS TO CHECK:
{concept_block}

Reply with a JSON array only. No prose. Format:
[{{"id": "I1", "status": "covered|partial|missing", "reason": "<12 words or less>"}}, ...]
"""

    cli = os.environ.get("CLAUDE_CLI", "claude")
    try:
        result = subprocess.run(
            [cli, "-p", prompt],
            capture_output=True, text=True, timeout=300,
            encoding="utf-8", errors="replace",
        )
    except Exception as exc:
        print(f"[llm error] {exc}")
        return {}

    if result.returncode != 0:
        print(f"[claude exit {result.returncode}] {result.stderr.strip()[:300]}")
        return {}

    raw = result.stdout.strip()
    # Claude sometimes wraps in a code fence; strip it.
    m = re.search(r"\[\s*\{.*\}\s*\]", raw, re.DOTALL)
    if not m:
        print(f"[parse error] no JSON array in response: {raw[:200]}")
        return {}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        print(f"[json parse error] {exc}")
        return {}

    out: dict[str, tuple[str, str]] = {}
    for row in parsed:
        cid = row.get("id")
        status = row.get("status", "missing")
        reason = row.get("reason", "")
        if cid and status in ("covered", "partial", "missing"):
            out[cid] = (status, reason)
    return out


def _load_plan(harvest_dir: Path) -> dict | None:
    plan_path = harvest_dir / "build_plan.json"
    if not plan_path.exists():
        return None
    return json.loads(plan_path.read_text(encoding="utf-8"))


def _scope_concepts(concepts: list[dict], plan: dict | None) -> tuple[list[dict], dict[str, str]]:
    """If a plan is present, restrict to MUST+NICE concepts and return scope map."""
    if plan is None:
        return concepts, {}
    scope_map: dict[str, str] = {}
    for bucket in ("must", "nice"):
        for item in plan.get(bucket, []):
            scope_map[item["id"]] = bucket.upper()
    if not scope_map:
        return concepts, {}
    scoped = [c for c in concepts if c["id"] in scope_map]
    return scoped, scope_map


def verify(convo_id: int, artifact: Path, auto: bool = False,
           use_plan: bool = True) -> tuple[Path, Path]:
    harvest_dirs = list((BASE / "harvest").glob(f"{convo_id}_*"))
    if not harvest_dirs:
        raise SystemExit(f"No harvest folder for convo_id {convo_id}")
    harvest_dir = harvest_dirs[0]

    concepts_path = harvest_dir / "concepts.json"
    if not concepts_path.exists():
        raise SystemExit(f"Missing {concepts_path}. Run parse_conversation.py first.")

    concepts_doc = json.loads(concepts_path.read_text(encoding="utf-8"))
    artifact_abs = artifact if artifact.is_absolute() else (REPO_ROOT / artifact).resolve()
    if not artifact_abs.exists():
        raise SystemExit(f"Artifact not found: {artifact_abs}")

    plan = _load_plan(harvest_dir) if use_plan else None
    scoped_concepts, scope_map = _scope_concepts(concepts_doc["concepts"], plan)
    if plan:
        print(f"[scoped] build_plan.json -> {len(scoped_concepts)} concepts "
              f"(MUST+NICE), skipped {len(concepts_doc['concepts']) - len(scoped_concepts)} SKIP items")

    files = _load_artifact_text(artifact_abs)

    auto_results: dict[str, tuple[str, str]] = {}
    if auto:
        summary = _artifact_summary(artifact_abs, files)
        print(f"[auto] batching {sum(1 for c in scoped_concepts if c['kind'] in ('idea', 'decision'))} soft concepts to claude -p...")
        auto_results = _auto_check_soft_concepts(scoped_concepts, summary)
        print(f"[auto] got {len(auto_results)} verdicts back")

    rows: list[CoverageRow] = []
    for c in scoped_concepts:
        if c["kind"] == "technical":
            row = verify_technical(c, files, artifact_abs)
        elif c["id"] in auto_results:
            status, reason = auto_results[c["id"]]
            row = CoverageRow(
                id=c["id"], kind=c["kind"], label=c["label"], signal=c["signal"],
                status=status, evidence=[f"llm: {reason}"] if reason else [],
                note="auto-checked via claude -p",
            )
        else:
            row = CoverageRow(
                id=c["id"], kind=c["kind"], label=c["label"], signal=c["signal"],
                status="unverifiable", evidence=[],
                note="Idea / decision - run with --auto to check via claude -p.",
            )
        if scope_map:
            row.note = (f"[{scope_map[c['id']]}] " + row.note).strip()
        rows.append(row)

    summary = {
        "covered": sum(1 for r in rows if r.status == "covered"),
        "partial": sum(1 for r in rows if r.status == "partial"),
        "missing": sum(1 for r in rows if r.status == "missing"),
        "unverifiable": sum(1 for r in rows if r.status == "unverifiable"),
    }

    out_json = harvest_dir / "coverage.json"
    out_md = harvest_dir / "coverage.md"
    payload = {
        "convo_id": convo_id,
        "artifact": str(artifact_abs.relative_to(REPO_ROOT)) if artifact_abs.is_relative_to(REPO_ROOT) else str(artifact_abs),
        "summary": summary,
        "rows": [asdict(r) for r in rows],
        "scoped_by_plan": bool(plan),
        "scope_map": scope_map,
    }
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(payload, rows), encoding="utf-8")
    return out_json, out_md


def render_markdown(payload: dict, rows: list[CoverageRow]) -> str:
    s = payload["summary"]
    icon = {"covered": "✓", "partial": "~", "missing": "✗", "unverifiable": "?"}
    lines = [
        f"# Coverage Audit — #{payload['convo_id']}",
        "",
        f"**Artifact:** `{payload['artifact']}`",
        "",
        f"- covered: {s['covered']}",
        f"- partial: {s['partial']}",
        f"- missing: {s['missing']}",
        f"- unverifiable: {s['unverifiable']}",
        "",
    ]

    def section(title: str, kind: str) -> None:
        items = [r for r in rows if r.kind == kind]
        if not items:
            return
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        lines.append("| ID | Status | Concept | Evidence |")
        lines.append("|---|---|---|---|")
        for r in items:
            ev = "; ".join(r.evidence) if r.evidence else (r.note or "—")
            label = r.label.replace("|", "\\|")
            ev_clean = ev.replace("|", "\\|")[:120]
            lines.append(f"| {r.id} | {icon[r.status]} {r.status} | {label} | {ev_clean} |")
        lines.append("")

    section("Technical coverage", "technical")
    section("Idea coverage", "idea")
    section("Decision coverage", "decision")

    still_manual = [r for r in rows if r.status == "unverifiable"]
    if still_manual:
        lines.append("## Still unverifiable (run with --auto)")
        lines.append("")
        for r in still_manual:
            lines.append(f"- [ ] **{r.id}** ({r.kind}) · {r.label}")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("convo_id", type=int)
    p.add_argument("artifact", type=Path, help="Path to built artifact (directory or file)")
    p.add_argument("--auto", action="store_true",
                   help="Auto-check idea/decision concepts via a single batched claude -p call")
    p.add_argument("--no-plan", action="store_true",
                   help="Ignore build_plan.json and verify against every concept")
    args = p.parse_args()
    j, m = verify(args.convo_id, args.artifact, auto=args.auto, use_plan=not args.no_plan)
    doc = json.loads(j.read_text(encoding="utf-8"))
    s = doc["summary"]
    print(f"wrote {j}")
    print(f"wrote {m}")
    print()
    print(f"covered: {s['covered']}  partial: {s['partial']}  missing: {s['missing']}  unverifiable: {s['unverifiable']}")


if __name__ == "__main__":
    main()
