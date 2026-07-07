# CODEX EXECUTION PLAN: Seal 3 Execution Leaks

> Daemon is sole executor. Everything else emits to delta. No exceptions.

---

## TASK 1: auto_actor.py — Stop bypassing delta

**File:** `services/cognitive-sensor/auto_actor.py`

**What to do:**

1. Add at top (near line 42):
```python
DELTA_URL = "http://localhost:3001"
_DELTA_API_KEY = ""
_key_path = BASE.parent.parent / ".aegis-tenant-key"
if _key_path.exists():
    _DELTA_API_KEY = _key_path.read_text(encoding="utf-8").strip()
```

2. Replace `submit_task_to_cortex()` (line 434-460) with:
```python
def emit_task_to_delta(task_id: str, intent: str, domain: str, params: dict, priority: int = 1) -> str | None:
    """Emit a task to delta-kernel for daemon execution."""
    try:
        payload = json.dumps({
            "type": "ai",
            "title": task_id,
            "metadata": {
                "cmd": "@WORK",
                "inputs": params,
                "source": "auto_actor",
                "intent": intent,
                "domain": domain,
                "priority": priority,
                "constraints": {"timeout_seconds": 300, "max_cost_usd": 0.50},
            }
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if _DELTA_API_KEY:
            headers["Authorization"] = f"Bearer {_DELTA_API_KEY}"
        req = urllib.request.Request(
            f"{DELTA_URL}/api/work/request",
            data=payload,
            headers=headers,
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("status") in ("APPROVED", "QUEUED"):
            return result.get("job_id", task_id)
        print(f"  Delta denied: {result.get('reason', 'unknown')}")
        return None
    except Exception as e:
        print(f"  Delta emission failed: {e}")
        return None
```

3. Delete `submit_task_to_queue()` (line 463-491) entirely.

4. In `execute_ghost_directives()` (line 575), replace:
```python
job_id = submit_task_to_cortex(
```
with:
```python
job_id = emit_task_to_delta(
```

**Verify:**
```bash
cd services/cognitive-sensor && python -c "from auto_actor import emit_task_to_delta; print('OK')"
python auto_actor.py  # with delta-kernel running
curl -H "Authorization: Bearer $(cat ../../.aegis-tenant-key)" http://localhost:3001/api/work/status
```
Expect: emitted ghost tasks visible in work queue. No calls to :3009 or :3005.

---

## TASK 2: api.py — Orchestrator stops executing

**File:** `services/mosaic-orchestrator/src/mosaic/api.py`

**What to do:**

1. Replace `/api/v1/tasks/execute` endpoint (lines 112-158) with:
```python
@app.post("/api/v1/tasks/execute")
async def execute_task(task_spec: dict):
    """Emit a task to delta for daemon execution."""
    if metering.is_paused():
        return {"status": "paused", "message": "AI metering is paused"}

    _priority_int = {"low": 0, "normal": 1, "high": 2, "critical": 3}
    result = await delta.request_work({
        "type": "ai",
        "title": task_spec.get("task_id", "manual-task"),
        "timeout_ms": task_spec.get("timeout_seconds", 300) * 1000,
        "metadata": {
            "cmd": "@WORK",
            "inputs": {
                "instructions": task_spec.get("instructions", ""),
                "files_context": task_spec.get("files_context", []),
            },
            "source": "orchestrator",
            "intent": "execute_task",
            "priority": _priority_int.get(task_spec.get("priority", "normal"), 1),
        }
    })
    return {"status": "emitted", "job_id": result.get("job_id"), "admission": result.get("status")}
```

2. Replace `/api/v1/project/goals/{goal_id}/decompose` endpoint (lines 250-356) with:
```python
@app.post("/api/v1/project/goals/{goal_id}/decompose")
async def decompose_goal(goal_id: str):
    """Emit a goal decomposition task to delta for daemon execution."""
    goals_data = cognitive.read_project_goals()
    if "error" in goals_data:
        return {"error": goals_data["error"]}

    goal = next((g for g in goals_data["goals"] if g["goal_id"] == goal_id), None)
    if not goal:
        return {"error": f"Goal {goal_id} not found"}
    if goal.get("milestones"):
        return {"error": f"Goal {goal_id} already has milestones"}

    prompt = f"""Decompose this project goal into milestones and subtasks.

Goal: {goal['title']}
Ship Criteria: {goal.get('ship_criteria', 'Not specified')}

Return a JSON array of milestones. Each milestone has:
- "title": string
- "subtasks": array of objects with "title", "tags", "depends_on_titles"

Return 3-5 milestones, each with 2-5 subtasks. Order by execution sequence.
Return ONLY the JSON array."""

    result = await delta.request_work({
        "type": "ai",
        "title": f"decompose-goal-{goal_id}",
        "metadata": {
            "cmd": "@WORK",
            "inputs": {
                "instructions": prompt,
                "goal_id": goal_id,
                "output_handler": "goal_decompose",
            },
            "source": "orchestrator",
            "intent": "decompose_goal",
            "priority": 1,
            "constraints": {"timeout_seconds": 120, "max_cost_usd": 0.50},
        }
    })
    return {"status": "emitted", "goal_id": goal_id, "job_id": result.get("job_id")}
```

**Verify:**
```bash
# Restart orchestrator first
curl -X POST http://localhost:3005/api/v1/tasks/execute \
  -H "Content-Type: application/json" \
  -d '{"instructions":"test task","task_id":"smoke-test"}'
```
Expect: `{"status":"emitted","job_id":"...","admission":"APPROVED"}` — not an execution result.

```bash
curl -H "Authorization: Bearer $(cat .aegis-tenant-key)" http://localhost:3001/api/work/status
```
Expect: `smoke-test` task in active or queued jobs.

---

## TASK 3: compound_loop.py — Stop writing files

**File:** `services/mosaic-orchestrator/src/mosaic/workflows/compound_loop.py`

**What to do:**

1. Add `delta` parameter to `run_compound_loop()` signature (already passed from api.py).

2. Replace lines 140-148 (direct writes + signal push) with:
```python
    # Emit state update task to delta for daemon execution
    try:
        await delta.request_work({
            "type": "system",
            "title": "compound-loop-state-update",
            "metadata": {
                "cmd": "@WORK",
                "inputs": {
                    "handler": "compound_state_update",
                    "compound_state": compound_state,
                    "signal_updates": signal_updates,
                },
                "source": "orchestrator",
                "intent": "update_state",
                "priority": 1,
            }
        })
        log.info("compound_loop.state_emitted_to_delta")
    except Exception as exc:
        log.error("compound_loop.delta_emit_failed", error=str(exc))
```

3. Delete `_push_signal_updates()` function entirely (lines 172-250).

4. Keep lines 151-164 (NATS publish + OpenClaw alert) — those are notifications, not execution.

**Verify:**
```bash
curl -X POST http://localhost:3005/api/v1/workflows/compound
```
Expect: response still contains `compound_score`. Check:
```bash
curl -H "Authorization: Bearer $(cat .aegis-tenant-key)" http://localhost:3001/api/work/status
```
Expect: `compound-loop-state-update` task in work queue.

---

## EXECUTION ORDER

1. Task 1 (auto_actor.py) — standalone Python, no restart needed
2. Task 2 (api.py) — requires orchestrator restart after edit
3. Task 3 (compound_loop.py) — same restart as Task 2

Tasks 2 and 3 share the same service restart. Do them together.

## DONE CRITERIA

- `grep -r "localhost:3009/tasks/submit" services/cognitive-sensor/` returns nothing
- `grep -r "claude_adapter.execute_task" services/mosaic-orchestrator/src/mosaic/api.py` returns nothing
- `grep -r "cognitive.write_compound_state\|cognitive.write_skill_registry\|cognitive.write_analyst_decisions\|cognitive.write_risk_state" services/mosaic-orchestrator/src/mosaic/workflows/compound_loop.py` returns nothing
- All 3 verify steps pass (tasks appear in delta work queue)
