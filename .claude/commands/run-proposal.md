# Run Proposal (in-session executor)

Execute an approved auto_actor proposal using the **current** Claude Code session.
Alternative to the headless subprocess runner at `services/cognitive-sensor/proposal_runner.py`.

**When to use this vs the subprocess runner:**
- **This command**: you're in Claude Code anyway. Cheaper (no system-prompt reload). Interactive.
- **Subprocess runner** (`python atlas_approve.py approve <id>`): fully detached, runs in background, closes terminal. Autonomous but reloads ~30k system-prompt tokens each invocation.

Both write to the same `auto/<id>` branch scheme and update the same `proposals.json`.

---

## Usage

```
/run-proposal <proposal_id>
```

`$ARGUMENTS` = the proposal id.

---

## Steps to execute

**1. Pre-flight check.** Run these commands and show output:

```bash
# Confirm proposals.json has the id and status is approved (or pending)
python -c "
import json, sys
pid = '$ARGUMENTS'.strip()
ps = json.load(open('services/cognitive-sensor/proposals.json'))
p = next((x for x in ps if x.get('proposal_id') == pid), None)
if not p:
    print('PROPOSAL_NOT_FOUND'); sys.exit(1)
print('status:', p.get('status'))
print('dtype:', p.get('dtype'))
print('domain:', p.get('domain'))
print('rationale:', (p.get('rationale') or '')[:200])
print('suggested_action:', (p.get('suggested_action') or '')[:400])
"
git status --short | head -20
git rev-parse --abbrev-ref HEAD
```

If status is `approved` or `pending`, continue. If already `running`/`completed`/`failed`, STOP and ask the user whether to overwrite.

**CRITICAL:** If `git status --short` shows ANY modified or untracked files, STOP and ask the user to stash first:

```bash
git stash push -u -m "pre-run-proposal $ARGUMENTS"
```

Do not proceed with a dirty working tree. In Step 4 you will commit only the specific files you created/modified — never `git add -A` or `git add .`, because that would sweep unrelated uncommitted work into the proposal's branch.

**2. Flip status to `running` and create branch.**

```bash
python -c "
import json
from datetime import datetime, timezone
pid = '$ARGUMENTS'.strip()
path = 'services/cognitive-sensor/proposals.json'
ps = json.load(open(path))
for p in ps:
    if p.get('proposal_id') == pid:
        p['status'] = 'running'
        p['branch'] = f'auto/{pid}'
        p['started_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        p['runner'] = 'in_session'
        break
json.dump(ps, open(path, 'w'), indent=2)
print('status=running, runner=in_session')
"
git checkout -b "auto/$ARGUMENTS"
```

**3. Journal start to CycleBoard** (non-fatal if delta-kernel is down):

```bash
python -c "
import sys
sys.path.insert(0, 'services/cognitive-sensor')
from cycleboard_push import _load_api_key, get_cycleboard_state, put_cycleboard_state, _today_date, _now_iso
key = _load_api_key()
state = get_cycleboard_state(key) if key else None
if state is not None:
    j = list(state.get('Journal') or [])
    j.append({'id': 'slash-$ARGUMENTS', 'date': _today_date(), 'createdAt': _now_iso(),
              'content': 'In-session runner starting proposal $ARGUMENTS on branch auto/$ARGUMENTS', 'mood': None})
    state['Journal'] = j
    put_cycleboard_state(state, key)
    print('journaled')
else:
    print('no delta-kernel; skipping journal')
" 2>&1
```

**4. Execute the proposal.** Read the `rationale` and `suggested_action` from step 1's output. Do the work using your normal tools (Read, Edit, Write, Bash, Grep, Glob). Constraints:

- Stay inside the Pre Atlas repo.
- DO NOT merge to main. You are on `auto/$ARGUMENTS`.
- DO NOT run destructive commands (`rm -rf`, `git reset --hard`, `git push --force`).
- If the work exceeds scope, produce a partial deliverable + a markdown summary of what's left.
- End by running `git add <specific paths you touched>` (NEVER `git add -A` or `.`) and `git commit -m "<conventional message>"`. Track every file you create/edit so you can stage them by exact path.

**5. Flip status and journal completion:**

```bash
python -c "
import json, subprocess, sys
from datetime import datetime, timezone
pid = '$ARGUMENTS'.strip()
path = 'services/cognitive-sensor/proposals.json'
ps = json.load(open(path))
commit_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()[:12]
for p in ps:
    if p.get('proposal_id') == pid:
        p['status'] = 'completed'
        p['completed_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        p['commit'] = commit_sha
        break
json.dump(ps, open(path, 'w'), indent=2)
print(f'commit={commit_sha}')

sys.path.insert(0, 'services/cognitive-sensor')
from cycleboard_push import _load_api_key, get_cycleboard_state, put_cycleboard_state, _today_date, _now_iso
key = _load_api_key()
state = get_cycleboard_state(key) if key else None
if state is not None:
    j = list(state.get('Journal') or [])
    j.append({'id': 'slash-done-$ARGUMENTS', 'date': _today_date(), 'createdAt': _now_iso(),
              'content': f'In-session runner completed proposal $ARGUMENTS on branch auto/$ARGUMENTS commit={commit_sha}', 'mood': None})
    state['Journal'] = j
    put_cycleboard_state(state, key)
"
```

**6. Report to the user:**
- Branch name (`auto/$ARGUMENTS`)
- Commit SHA
- One-line summary of what was shipped
- Instructions: `git checkout main && git merge auto/$ARGUMENTS` to land it, or `git branch -D auto/$ARGUMENTS` to discard.

**If anything fails mid-execution:** set status to `failed` in `proposals.json`, journal the failure, leave the branch intact for review, and report the error to the user.
