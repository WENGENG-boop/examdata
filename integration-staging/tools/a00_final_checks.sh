#!/usr/bin/env bash
# A00 final checks for the Phase A integration (run AFTER execution-ledger.json is written).
# Produces: docs/integration/execution/evidence/A00/final_checks.txt
# Usage (from anywhere): bash integration-staging/tools/a00_final_checks.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.." || exit 1
source "$SCRIPT_DIR/_env.sh"
OUT=docs/integration/execution/evidence/A00/final_checks.txt
{
  echo "=== A00 final checks (runner: integration-staging/tools/a00_final_checks.sh) ==="
  echo "generated_at_local: $(date --iso-8601=seconds)"
  echo "generated_at_utc:   $(date -u --iso-8601=seconds)"
  echo "cwd: $(pwd)"
  echo
  echo "--- 1. artifact inventory (files under the two Phase A roots, excluding this transcript) ---"
  find integration-staging docs/integration/execution -type f ! -name final_checks.txt | sort
  echo
  echo "--- 2. JSON validation: execution-ledger.json + ownership.json ---"
  "$INTEGRATION_PYTHON" - <<'PY'
import json, sys
with open('docs/integration/execution/execution-ledger.json', encoding='utf-8') as f:
    ledger = json.load(f)
with open('docs/integration/execution/ownership.json', encoding='utf-8') as f:
    ownership = json.load(f)
ids = [t['task_id'] for t in ledger['tasks']]
expected = ['A%02d' % i for i in range(16)] + ['B%02d' % i for i in range(11)]
missing = [t for t in expected if t not in ids]
extra = [t for t in ids if t not in expected]
statuses = {}
for t in ledger['tasks']:
    statuses[t['status']] = statuses.get(t['status'], 0) + 1
a00 = [t for t in ledger['tasks'] if t['task_id'] == 'A00'][0]
gates = ledger['gates']
open_gates = [g for g, v in gates.items() if v.get('open')]
print('ledger_schema:', ledger['schema'])
print('ledger_mode:', ledger['mode'])
print('task_count:', len(ids))
print('unique_task_ids:', len(set(ids)))
print('missing_task_ids:', missing)
print('unexpected_task_ids:', extra)
print('status_counts:', json.dumps(statuses, sort_keys=True))
print('A00_status:', a00['status'])
print('gate_count:', len(gates))
print('open_gates:', open_gates)
print('ownership_allowed_write_roots:', len(ownership['allowed_write_roots']))
ok = (
    len(ids) == 27 and len(set(ids)) == 27 and not missing and not extra
    and a00['status'] == 'staged_pass'
    and len(gates) == 7 and not open_gates
    and len(ownership['allowed_write_roots']) == 2
    and ledger['schema'] == 'examdata.integration.ledger/1'
    and ledger['mode'] == 'PHASE_A_ISOLATED_ONLY'
)
print('FINAL_CHECKS_JSON:', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
PY
  echo "json_validation_exit=$?"
  echo
  echo "--- 3. artifact sha256 manifest (excluding this transcript) ---"
  find integration-staging docs/integration/execution -type f ! -name final_checks.txt -print0 | sort -z | xargs -0 sha256sum
  echo
  echo "--- 4. examdata git re-observation (point-in-time; concurrent-owner noise expected, plan section 0.9) ---"
  GIT_OPTIONAL_LOCKS=0 git -C examdata log -1 --format='%H | %ad | %s' --date=iso
  echo -n 'tracked-modified count: '; GIT_OPTIONAL_LOCKS=0 git -C examdata status --porcelain=v1 --untracked-files=no | wc -l
  echo -n 'all-entries count: '; GIT_OPTIONAL_LOCKS=0 git -C examdata status --porcelain=v1 | wc -l
} 2>&1 | tee "$OUT"
if grep -q 'FINAL_CHECKS_JSON: PASS' "$OUT"; then
  echo "FINAL_CHECKS: PASS" | tee -a "$OUT"
  exit 0
else
  echo "FINAL_CHECKS: FAIL" | tee -a "$OUT"
  exit 1
fi
