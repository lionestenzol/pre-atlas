$pgBin = "C:\Program Files\PostgreSQL\12\bin"
$env:PGPASSWORD = "aegis_dev_pass"
$db = "aegis_tnt_5d2af820b8e9"

$A1 = "cf3a5df1-cc76-4786-9a21-74fed77ec266"
$A2 = "7faeb5db-fcf6-4af5-a79f-e09b4b020b09"
$A3 = "bc71a375-11f5-4697-b90f-d3c039504a0f"
$A4 = "0fa51e52-eb9d-49e4-b7e3-c5a7d1c148c7"

$sql = @"
-- Approvals
INSERT INTO approvals (approval_id, action_id, agent_id, action, params, status, requested_at, expires_at) VALUES
  ('apr-001', 'act-100', '$A3', 'delete_task', '{"entity_id":"old-config","reason":"Archiving deprecated config"}', 'PENDING', NOW() - interval '2 hours', NOW() + interval '22 hours'),
  ('apr-002', 'act-101', '$A4', 'propose_delta', '{"entity_id":"governance-rules","reason":"Modify compliance rules"}', 'PENDING', NOW() - interval '30 minutes', NOW() + interval '47 hours'),
  ('apr-003', 'act-102', '$A1', 'complete_task', '{"entity_id":"critical-infra","reason":"Mark critical task complete"}', 'PENDING', NOW() - interval '10 minutes', NOW() + interval '11 hours'),
  ('apr-004', 'act-050', '$A2', 'create_task', '{"title":"Auto-generated report"}', 'APPROVED', NOW() - interval '1 day', NOW() + interval '1 day'),
  ('apr-005', 'act-051', '$A3', 'delete_task', '{"entity_id":"temp-data"}', 'REJECTED', NOW() - interval '3 days', NOW() - interval '2 days');

UPDATE approvals SET decided_at = NOW() - interval '23 hours', decided_by = 'bruke', reason = 'Approved for Q4 reporting' WHERE approval_id = 'apr-004';
UPDATE approvals SET decided_at = NOW() - interval '2 days', decided_by = 'bruke', reason = 'Data still needed by analytics team' WHERE approval_id = 'apr-005';

-- Usage records
INSERT INTO usage_records (agent_id, period, actions_count, tokens_used, cost_usd, by_action) VALUES
  ('$A1', '2026-02-22', 47, 125000, 3.750000, '{"create_task":15,"update_task":12,"propose_delta":20}'),
  ('$A1', '2026-02-21', 38, 98000, 2.940000, '{"create_task":10,"update_task":18,"complete_task":10}'),
  ('$A1', '2026-02-20', 52, 142000, 4.260000, '{"create_task":22,"propose_delta":30}'),
  ('$A2', '2026-02-22', 23, 67000, 1.340000, '{"create_task":8,"update_task":5,"query_state":10}'),
  ('$A2', '2026-02-21', 31, 89000, 1.780000, '{"update_task":11,"query_state":20}'),
  ('$A3', '2026-02-22', 15, 0, 0.000000, '{"complete_task":10,"propose_delta":5}'),
  ('$A3', '2026-02-21', 22, 0, 0.000000, '{"complete_task":12,"delete_task":2,"propose_delta":8}'),
  ('$A4', '2026-02-22', 8, 32000, 0.640000, '{"propose_delta":5,"create_task":3}'),
  ('$A4', '2026-02-21', 12, 41000, 0.820000, '{"propose_delta":8,"query_state":4}');

-- Entities (materialized state objects the dashboard can browse)
INSERT INTO entities (entity_id, entity_type, version, current_hash, state) VALUES
  ('ent-task-001', 'aegis_task', 3, 'abc123def456', '{"title":"Implement hash chain verification","status":"in_progress","priority":"high","assignee":"Claude Opus","started_at":"2026-02-22T10:00:00Z"}'),
  ('ent-task-002', 'aegis_task', 2, 'def456ghi789', '{"title":"Analyze delta throughput","status":"completed","category":"analytics","result":"Throughput: 1200 ops/sec","completed_at":"2026-02-22T16:00:00Z"}'),
  ('ent-task-003', 'aegis_task', 1, 'ghi789jkl012', '{"title":"Implement snapshot pruning","status":"open","priority":"medium","estimated_hours":4}'),
  ('ent-task-004', 'aegis_task', 1, 'jkl012mno345', '{"title":"Q1 compliance audit","status":"open","urgency":"critical","type":"governance"}'),
  ('ent-task-005', 'aegis_task', 1, 'mno345pqr678', '{"title":"Deploy Redis cluster","status":"completed","completed_at":"2026-02-22T14:30:00Z"}'),
  ('ent-config-001', 'aegis_config', 5, 'cfg001hash', '{"key":"rate_limit","value":{"window_ms":3600000,"max_requests":10000},"updated_by":"bruke"}'),
  ('ent-config-002', 'aegis_config', 2, 'cfg002hash', '{"key":"snapshot_interval","value":{"every_n_deltas":1000,"prune_after_days":30},"updated_by":"system"}'),
  ('ent-report-001', 'aegis_report', 1, 'rpt001hash', '{"title":"Daily Delta Summary","period":"2026-02-22","total_deltas":47,"total_agents":4,"top_action":"propose_delta"}');

"@

Write-Host "Inserting demo approvals, usage, and entities..."
$sql | & "$pgBin\psql.exe" -U aegis -d $db 2>&1
Write-Host "Done!"
