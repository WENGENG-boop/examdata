# Main code merge validation — 2026-10-08

Human authorization: “全部到main里面了吗？然后所有部分全部先合并”. This run performs a code merge in an independent checkout for GitHub main. The running original Windows workspace, its services and real data remain unchanged.

## Resulting layout and reconciliation

- Existing Python project remains at the repository root; original CLI commands are preserved.
- The latest `integration-closure-20261007-c8b4e0c8/candidates/closure-v1` integration package and contracts are now in the real package and repository resource paths. `MAIN_MERGE_MANIFEST.json` records source and final target hashes.
- Candidate CLI is preserved as the explicitly rehearsal-only `examdata.integration.rehearsal_cli`, rather than overwriting the original CLI. Its regression tests follow the namespace change while retaining the response schema.
- `examdata workspace` and `examdata-workspace` supervise the existing Python API, main Web and classic frontend. The same public port serves `/`, `/classic/`, API v1, health and API documentation.
- IELTS, TOEFL and timetable paths resolve inside the cloned repository. Web's former sibling-checkout assumption was corrected.
- Explicit production v2 app composition accepts a real `ProductionAssembly`. Without one, v2 returns an explicit 503; no synthetic provider, fixture dataset or rehearsal content is enabled by the launcher.
- Rehearsal resources remain in `fixtures/synthetic` for the inherited tests only. Historical staging copies and evidence are not active production configuration.
- Fresh comparison found zero drift in original Python source outside the files deliberately reconciled in this merge.

## Current verification

| Verification | Result |
| --- | --- |
| Inherited integration suite, against the merged package | Passed; 200 collected, one Windows native-symlink case skipped |
| Workspace, original API contracts, authentication and request budgets | 65 passed, 1 skipped |
| Frontend and Web tests | 44 passed |
| Real-process offline workspace smoke | 16 checks passed, including both frontends, OpenAPI, CIE/Edexcel board route, IELTS/TOEFL info, direct API authentication, v2 unavailable state and legacy HEAD behavior |
| Child process cleanup | All three private test ports closed after clean supervisor shutdown |
| Package wheel build | Passed |
| Wheel installed in a separate environment | Imports resolved to the installed wheel, and the real-process smoke passed again; existing dependency libraries were reused, rather than reinstalling every dependency |
| New source credential scan | Only explicit synthetic markers in test cases/fixtures; no real credential discovered |

The first process smoke exposed missing database initialization. The launcher now starts the existing `examdata serve` CLI, retaining its initialization behavior, instead of bypassing it through direct uvicorn startup. The initial rehearsal-CLI namespace test failure was fixed without changing the original CLI or response schema. The original runtime executable had temporary-directory permission restrictions; verification used newly created private virtual environments. Initial wheel build lacked setuptools in that environment; the build dependencies were installed only in the private verification environment.

## Uncompleted data and acceptance work

A broader data-dependent IELTS resolver run produced **8 failed, 70 passed, 1 skipped**. The failed cases require local normalized IELTS datasets/run IDs, answers or PDF/audio files that were not uploaded. That failure is retained as an explicit data portability limitation; these tests were not rewritten to report success. The subsequent code-only regression selection above excludes this data-dependent test file.

This merge does not establish full v2 real-provider acceptance, database/PDF/audio migration, all-subject completeness, Linux/VPS deployment, public-network acceptance or human browser acceptance. No service cutover or deployment has been performed. The original upstream stop conditions and manual-review states have not been changed.
