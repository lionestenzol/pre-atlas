export const meta = {
  name: 'droplist-remediation',
  description: 'Verify 5 droplist findings at HEAD, then ship Stops 1-3 (links doc, test backfill, prod jsonschema). Stops 4-5 deferred.',
  phases: [
    { title: 'Verify', detail: 'Re-verify each finding at current HEAD' },
    { title: 'Fix-1-doc', detail: 'PKT-005 add links to mapping table' },
    { title: 'Fix-2-tests', detail: 'Extend structural_check for 9 fields' },
    { title: 'Fix-3-schema', detail: 'Move jsonschema strict_check into production emit_signal' },
    { title: 'Verify-fixes', detail: 'Run pytest, ensure all gates green' },
    { title: 'Synthesize', detail: 'Commit on branch, summary report' },
  ],
}

const VERIFY_SCHEMA = {
  type: 'object',
  required: ['finding', 'still_real_at_head', 'evidence'],
  properties: {
    finding: { type: 'string' },
    still_real_at_head: { type: 'boolean' },
    evidence: { type: 'string' },
    notes: { type: 'string' },
  },
}

const FIX_SCHEMA = {
  type: 'object',
  required: ['stop', 'changed_files', 'tests_pass', 'summary'],
  properties: {
    stop: { type: 'string' },
    changed_files: { type: 'array', items: { type: 'string' } },
    tests_pass: { type: 'boolean' },
    summary: { type: 'string' },
    skipped_reason: { type: 'string' },
  },
}

phase('Verify')
log('Re-verify all 5 findings at current HEAD before any edits')

const verifications = await parallel([
  () => agent(`Verify at HEAD: payload.data.links is emitted at services/droplist/droplist/atlas_signal.py:124 but missing from PKT-005 mapping table at services/droplist/PACKETS/005_atlas_seam_contract.md:68. Read both lines and check. Return still_real_at_head true/false with file:line evidence.`, { label: 'verify:links-doc', schema: VERIFY_SCHEMA }),
  () => agent(`Verify at HEAD: services/droplist/test_atlas_signal.py:131-165 structural_check has zero assertions for payload.task_id and the 8 payload.data.* sub-fields (dag_id, domain, type, dag_status, nodes, evidence_refs, entity_refs, links). Read the file and check. Return still_real_at_head true/false with evidence.`, { label: 'verify:test-gap', schema: VERIFY_SCHEMA }),
  () => agent(`Verify at HEAD: services/droplist/droplist/atlas_signal.py emit_signal function does NOT call jsonschema validation before POSTing; only test_atlas_signal.py:172 strict_check uses jsonschema. Read both files. Return still_real_at_head true/false with evidence.`, { label: 'verify:no-prod-schema', schema: VERIFY_SCHEMA }),
  () => agent(`Verify at HEAD: BIBLE.md:241 OQ-17 source_layer=optogon is still pending (not extended). Read BIBLE.md:240-245. Return still_real_at_head true/false. This is informational only; will not be fixed by this workflow.`, { label: 'verify:oq-17', schema: VERIFY_SCHEMA }),
  () => agent(`Verify at HEAD: _maybe_emit_atlas_signal at graph_engine.py:21-48 has NO retry buffer. Read the function. Return still_real_at_head true/false. This is informational only; will not be fixed by this workflow.`, { label: 'verify:no-retry', schema: VERIFY_SCHEMA }),
])

const verified = verifications.filter(Boolean)
const actionable = verified.slice(0, 3).filter(v => v.still_real_at_head)
log(`Verification complete: ${verified.length}/5 returned, ${actionable.length}/3 actionable findings still real at HEAD`)

if (actionable.length === 0) {
  log('All actionable findings already resolved at HEAD. Nothing to fix.')
  return { verified, actionable: 0, fixes: [], note: 'No work needed.' }
}

phase('Fix-1-doc')
const fix1 = verified[0]?.still_real_at_head
  ? await agent(`Stop 1: Add "links" to the contract mapping table at services/droplist/PACKETS/005_atlas_seam_contract.md line 68. Current line 68 reads: "| payload.data | { dag_id, domain, type, dag_status, nodes: [...], evidence_refs, entity_refs } | structured introspection |". Edit it to include links: "| payload.data | { dag_id, domain, type, dag_status, nodes: [...], evidence_refs, entity_refs, links } | structured introspection |". Use the Edit tool. Confirm with a re-read. Return changed_files=['services/droplist/PACKETS/005_atlas_seam_contract.md'], tests_pass=true (no code changed), summary describing the edit.`, { label: 'fix:links-doc', schema: FIX_SCHEMA, phase: 'Fix-1-doc' })
  : { stop: '1', changed_files: [], tests_pass: true, summary: 'skipped', skipped_reason: 'finding not real at HEAD' }

phase('Fix-2-tests')
const fix2 = verified[1]?.still_real_at_head
  ? await agent(`Stop 2: Extend services/droplist/test_atlas_signal.py to assert presence and type of payload.task_id and 8 payload.data sub-fields (dag_id, domain, type, dag_status, nodes, evidence_refs, entity_refs, links). Add either: (a) extend REQUIRED_PAYLOAD list at the top of the file AND add a REQUIRED_PAYLOAD_DATA list with the 8 sub-fields; OR (b) add a new test function test_payload_data_fields_present that runs each fixture through dag_to_signal and asserts each sub-field is present with the expected shape. Pick the option more idiomatic to existing test style. Run pytest after editing. Return changed_files, tests_pass, summary. If tests fail, debug and re-run before reporting.`, { label: 'fix:test-backfill', schema: FIX_SCHEMA, phase: 'Fix-2-tests', agentType: 'tdd-guide' })
  : { stop: '2', changed_files: [], tests_pass: true, summary: 'skipped', skipped_reason: 'finding not real at HEAD' }

phase('Fix-3-schema')
const fix3 = verified[2]?.still_real_at_head
  ? await agent(`Stop 3: Move jsonschema validation from test-only into production emit_signal. Current state: test_atlas_signal.py:172 strict_check uses jsonschema if available. atlas_signal.py:154 emit_signal POSTs without validation.

Design decision (make and document): fail-loud (raise/return error if invalid) vs fail-soft (log and POST anyway). Default to fail-soft with prominent logging: keep emission resilient (it's already fail-soft for HTTP errors per the wrapper), but emit a structured log record when a malformed Signal would be sent.

Add a new function validate_signal(signal) -> list[str] in atlas_signal.py (similar shape to test_atlas_signal.structural_check but production-side). Call it inside emit_signal before POST. If non-empty errors and DROPLIST_STRICT_EMIT env var is set, raise/return early with structured error; otherwise log via storage.append(DAG_EVENTS, {event: 'signal_validation_warning', errors}) and POST anyway.

Add tests covering: valid signal passes, invalid signal in strict mode returns error without POST, invalid signal in non-strict mode logs warning and still POSTs.

Run pytest. Return changed_files, tests_pass, summary including design choice rationale.`, { label: 'fix:prod-schema', schema: FIX_SCHEMA, phase: 'Fix-3-schema' })
  : { stop: '3', changed_files: [], tests_pass: true, summary: 'skipped', skipped_reason: 'finding not real at HEAD' }

const fixes = [fix1, fix2, fix3].filter(Boolean)

phase('Verify-fixes')
const finalCheck = await agent(`Run the full droplist test suite: cd services/droplist && python -m pytest -v. Report total tests, passed, failed. Also run a final grep to confirm: (a) PKT-005:68 now contains "links"; (b) test_atlas_signal.py asserts on task_id and data sub-fields; (c) atlas_signal.py emit path now calls validate_signal or equivalent. Return a single-paragraph summary verdict.`, { label: 'verify:all-fixes' })

phase('Synthesize')
const summary = await agent(`Build a final markdown report at experiments/droplist-remediation/REPORT.md summarizing:
- Verifications run (5 findings, results)
- Fixes shipped (1-3, with file:line citations to each change)
- Tests after: pass count
- Stops 4 (retry buffer) and 5 (OQ-17 enum) explicitly deferred per BIBLE doctrine

Then commit on a fresh branch experiment/droplist-remediation-<date> (use today's date YYYY-MM-DD from external context if available, otherwise just "remediation"). Push the branch. Output the PR-ready URL.

If any fix failed tests and was rolled back, list it explicitly.`, { label: 'synthesize' })

return {
  verifications: verified,
  fixes,
  final_check: finalCheck,
  summary,
}
