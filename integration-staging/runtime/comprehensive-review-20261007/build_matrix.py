"""Build the explicit acceptance template and verify review artifact provenance."""
from pathlib import Path
import json, hashlib, datetime

WS = Path(__file__).resolve().parents[3]
DOCS = WS / 'docs/integration/execution'
rows = []
def add(area, mode, definitions, gates=()):
    for line in definitions.strip().splitlines():
        ident, requirement, evidence = line.split('|', 2)
        rows.append(dict(id=ident, area=area, mode=mode, mandatory=True,
                         requirement=requirement, acceptance_evidence=evidence,
                         required_gates=list(gates), status='pending',
                         evidence_paths=[], evidence_sha256=[], tested_revision=None,
                         authorization_basis=None, blocked_reason=None))

add('ownership and provenance','private', '''
P01|Verify frozen parent candidate and manifest before copying|Digest matches 222 files and 8171cf1c...38fa48; manifest matches 920f41c1...9bcec9ce
P02|Prove imports originate from the intended candidate or installed environment|Module-origin map and fail-on-wrong-origin assertions
P03|Preserve frozen trees, evidence and formal ledger|Before/after file-hash comparison with no unexplained changes
P04|Track private and real effects separately|Closure ledger with per-action permissions and dependency validation
P05|Retain all failed runs and exact transcripts|Command/cwd/exit/timestamp records, distinct red and green artifacts
''')
add('coverage trust and semantics','private','''
Q01|Reject unsupported quality promotion|Empty or unsuitable provenance does not produce verified real content
Q02|Handle contradictory quality states|Missing answers plus source_verified cannot produce complete verified coverage
Q03|Validate required identity fields|Empty/null/unknown/persisted unknown identities remain unresolved; type-specific exceptions tested
Q04|Preserve evidence-backed positive cases|Authoritative evidence and manual decisions trace to retained records
Q05|Respect entity-specific requirements|Documents/assets and applicable question types do not require irrelevant answers; required assets are enforced
Q06|Validate manifest references and declarations|Absent/wrong-scope IDs, duplicate scopes/references and exclusion-partial conflicts fail or downgrade explicitly
Q07|Count unique valid membership|Duplicate/colliding IDs cannot inflate observed or verified counts; normal and alternate ingestion tested
Q08|Keep denominator and count semantics consistent|Expected/observed/unmet/missing/excluded/verified documented and checked for overfill/underfill
Q09|Handle unknown zero and all-excluded scopes|No invented percentage; documented meaningful status and denominator behavior
Q10|Process generators and multiple scopes correctly|One-shot and reusable iterables give identical intended results
Q11|Validate public coverage contract and consumers|HTTP output/schema/client tests, versioned semantics and independently calculated expected values
''')
add('bounded operations IO','private','''
I01|Bound actual flat-directory enumeration|Instrumented scandir count obeys declared budget including any documented overflow probe
I02|Bound deep-tree retained work|Measured retained records/depth and no unbounded parent-list accumulation
I03|Count skipped files against attempt/result budgets|Oversized/unreadable files cannot evade attempt cap; retained diagnostics bounded
I04|Enforce cumulative budget during actual reads|Growth-after-stat case never silently exceeds the declared read allowance
I05|Account for read failures and detection bytes|Partial/error/oversize paths count bytes consistently and expose exhaustion
I06|Validate exact zero and invalid budgets|Deterministic exact-limit semantics and rejected invalid configuration
I07|Bound expected-manifest loading and complexity|Actual byte cap plus scope/reference/depth/length limits and structured errors
I08|Constrain checkpoint reads to authorized root|Synthetic traversal/link/reparse/special-file tests; blocked native cases explicitly recorded
I09|Expose bounded sanitized scan diagnostics|HTTP view retains truncation reasons and distinguishes incomplete scans from complete coverage
''')
add('sanitization and operations freshness','private','''
S01|Reuse normalized secrets across recursion|Tuple and generator inputs redact all dynamic keys/values and nested records
S02|Preserve schema and records under key collisions|Full serialized-output checks with collision counts and fixed-key behavior
S03|Keep paths secrets and traces out of public diagnostics|Synthetic marker checks across errors/jobs/coverage/log projections
S04|Refresh or explicitly stale-label observations|Same-app checkpoint update reaches declared freshness bound or returns stale state
S05|Preserve stopped-job authority|Running-to-stopped test never reports fresh old running state and never resumes/writes
S06|Resolve concurrent and conflicting observations safely|Timestamp ties/errors/cache failures tested; observation revision distinguished from dataset revision
''')
add('whole private API and product','private','''
A01|Separate fixture and production assembly|Production missing configuration fails closed; injected private production seam tested
A02|Account for all planned and legacy route families|Capability/route matrix with fixture versus real evidence and unavailable states
A03|Preserve routing and host composition behavior|Synthetic host legacy errors, route ordering, OpenAPI and operation ID checks
A04|Verify envelopes errors filters and pagination|Typed HTTP failures, unsupported filters, stable/stale cursor and revision tests
A05|Verify binary transport and content linkage|Magic bytes/MIME, size/range/ETag, content hash, unavailable-link and crop guards
A06|Enforce source and runner side-effect limits|No arbitrary URL proxy, list-triggered fetch/crop, or per-item subprocess multiplication
A07|Preserve partial-source outcomes|Partial-source and all-source failures remain distinct across API/client
A08|Support private CIE and Edexcel journeys|Actual browser course/syllabus/resources/question/answer/crop flows or declared unavailable behavior
A09|Support private IELTS journey|Actual browser book/variant/skill/test/question/answer/audio-state flow
A10|Support private TOEFL journey|Actual browser set/table-question/answer/restricted-source flow
A11|Support private materials and timetable journeys|Version/layout/null-date/unknown-season and unsupported-state browser cases
A12|Support private operations and gaps journeys|Browser coverage denominators/evidence/job freshness and error/empty/partial states
A13|Keep source logic and secrets out of browser|Network/code inspection plus loading/retry/back/keyboard/narrow-screen checks
A14|Preserve installed CLI contract|Console entry-point commands work with private roots; no original application import
''')
add('migration and restore','private','''
M01|Create explicit synthetic migration manifest|Per-file hashes, per-scope counts, identities, references, provenance and decisions
M02|Handle interruption idempotence and collisions|Failure injection and retry preserve current state; conflicts explicit
M03|Publish revisions atomically and concurrently|Failed build leaves current unchanged; lost-update and reader-consistency tests
M04|Rehearse consistent database backup|Synthetic SQLite backup/export plus FK and relationship checks
M05|Execute actual restore|Queries/assets/manual decisions/pointers match pre-migration state after restore
''')
add('build and clean installation','private','''
B01|Build an actual versioned release artifact|Build command/log and wheel or appropriate distribution hash; source digest alone fails
B02|Install into a fresh private environment|No PYTHONPATH/development checkout fallback; installed package/version origin proven
B03|Include package data frontend and components|Artifact inventory and installed runtime reads of schemas/JSON/assets/component manifests
B04|Work across directories and code/data separation|Three cwd checks including spaces/non-ASCII; writable roots separate from code
B05|Exercise installed runner lifecycle|Missing runtime/component, timeout/cancellation/child cleanup and queue/output limits
B06|Keep installed fixture/production modes truthful|Synthetic components labelled; production mode never silently serves fixture content
''')
add('private final acceptance','private','''
V01|Close the obsolete coverage probe pin|Reviewed assertion diff and full green probe with no suppressed mandatory assertions
V02|Pass three-cwd whole validator|Successful actual validator exits and identity checks on final revision
V03|Run final candidate and installed regressions|28 inherited cases plus new regressions; base suite labelled separately
V04|Freeze and retest exact final revision|Source/artifact/data hashes match acceptance records; changes invalidate affected tests
V05|Produce consolidated exact merge and rollback maps|All inherited deltas reconciled; source/target/base/result hashes, conflict behavior and per-action gates
V06|Rehearse private rollback on disposable copy|Frozen parent preserved; undo evidence distinct from production health evidence
V07|Deliver current docs and verified evidence index|All required handoff files present; paths/hashes resolve; no unsupported completion claims
''')
add('released original integration','released_original','''
R01|Record explicit current human path release|Exact instruction/time/paths/constraints; no inference from Kimi inactivity
R02|Refresh baseline and preserve active-owner work|Current route/source/config/entry-point inventory with Kimi changes and tests retained
R03|Perform three-way semantic reconciliation|Old base/current original/new proposal per-file dispositions; private merged-copy tests
R04|Guard original writes against drift|Latest target hash before write, backup and conditional rollback; no unspecified targets
R05|Integrate real configuration and components|Real Node/gateway and Python package behavior parity from released sources
R06|Preserve every current legacy route|Refreshed method/path/default/content-type/error matrix; no shadowing or unexplained removals
R07|Validate real feature adapters|Approved layout/version samples and truthful CIE/Edexcel/materials/syllabus/timetable capabilities
R08|Validate approved real snapshot content and provenance|Native lookup/count/reference/decision checks; current visual crop evidence where required
R09|Complete real local browser journeys|Supported systems and failure/partial/unknown states exercised against released local stack
R10|Build and accept final reconciled artifact|New real-source artifact with installed tests; private artifact cannot substitute
R11|Update released documentation and handoff|Current configuration/CLI/API/migration/operations/deploy/rollback docs agree with tested revision
''',('original_paths_released',))
add('approved real data actions','authorized_action','''
D01|Rehearse migration using approved consistent real backups|Explicit snapshot scope, per-scope reconciliation and executed restore in private destination
D02|Apply an explicitly authorized real data pointer or write|Action/path scope, backup, current hashes, reversible change and post-change verification
''',('original_paths_released','real_data_write_authorized'))
# D01 is backup/snapshot rehearsal; it does not inherently write live data.
next(row for row in rows if row['id']=='D01')['required_gates']=['original_paths_released']
next(row for row in rows if row['id']=='D01')['mode']='released_original'
next(row for row in rows if row['id']=='D01')['additional_scope_requirement']='Explicit approval for the consistent real snapshot and private copy destination; add real_data_write_authorized only if the chosen action actually writes protected real data.'
add('authorized upstream validation','authorized_action','''
U01|Run only authorized live source samples|Bounded source scope, first-failure preservation and established stop conditions; no implied full-source coverage
''',('upstream_requests_authorized',))
add('authorized runtime cutover','authorized_action','''
O01|Cut over only named existing services|Explicit target/process/port scope, tested artifact, health/user-flow/version checks and rollback
''',('existing_service_cutover_authorized',))
add('authorized deployment','authorized_action','''
O02|Deploy only to named authorized target|Artifact digest/running version/health/user-flow/rollback evidence from that target
''',('remote_deployment_authorized',))
add('optional separately authorized actions','optional_action','''
O03|Perform only explicitly approved original cleanup|Exact allowlist/retention/current acceptance/hash preconditions; preserve later edits
''',('original_cleanup_authorized',))
add('optional separately authorized actions','optional_action','''
O04|Resume stopped CIE work only under explicit resume instruction|Original stop policy, source scope and real first-failure evidence; no automatic retries
''',('cie_resume_authorized',))
for row in rows:
    if row['mode'] in ('authorized_action','optional_action'):
        row['mandatory']=False
        row['becomes_mandatory_when']='The human explicitly includes this action in the operational completion scope; applicable prerequisite gates and path/data scopes must also hold.'

matrix={'schema':'integration.final_acceptance_template/1','created_date':'2026-10-07','workspace':str(WS),
        'purpose':'Complete closure checklist; pending rows are requirements, not claims of test execution.',
        'completion_rules':{
            'private':'All mandatory private rows pass on the final revision; real-only rows remain explicitly blocked until released.',
            'real_integration':'All mandatory released-original rows pass in addition to private rows; required snapshot scope is explicit.',
            'operational':'Every action selected by the human passes on the named target with its action-specific authorization.',
            'not_applicable':'Requires explicit documented applicability basis; never use it to hide unsupported required scope.',
            'warnings':'Distinct scenarios and repeated runs must be reported separately. Synthetic evidence does not satisfy real-world rows.'},
        'evidence_classes':['static_inspection','synthetic_fixture','copied_snapshot','isolated_real_data','live_local_service','live_upstream_sample','full_source_validation','deployed_target_validation'],
        'criteria_count':len(rows),'criteria':rows}
(DOCS/'FINAL_ACCEPTANCE_MATRIX_2026-10-07.json').write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

run=WS/'integration-staging/runtime/b07-reviewfix-20261007-774e4dad'
index=json.loads((run/'reports/B07R2_EVIDENCE_INDEX.json').read_text(encoding='utf8'))
checks=[]; missing=[]
def visit(value):
    if isinstance(value,dict):
        if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):
            p=Path(value['path'])
            p=p if p.is_absolute() else (WS/p if value['path'].startswith(('docs/','integration-staging/')) else run/p)
            if p.is_file(): checks.append({'path':str(p),'match':hashlib.sha256(p.read_bytes()).hexdigest()==value['sha256']})
            else: missing.append(str(p))
        for v in value.values(): visit(v)
    elif isinstance(value,list):
        for v in value:visit(v)
visit(index)
assert len({row['id'] for row in rows})==len(rows)
result={'matrix_rows':len(rows),'indexed_hashes_checked':len(checks),'mismatches':[c for c in checks if not c['match']],'unresolved_index_paths':missing,
        'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(Path(__file__).parent/'final-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,indent=2))
