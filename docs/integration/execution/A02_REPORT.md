# A02 — Private staging harness (Phase A, `PHASE_A_ISOLATED_ONLY`)

- **Packet:** A02 of `docs/integration/MASTER_EXECUTION_PLAN_EN.md` §11
- **Status:** `staged_pass` (staged only — nothing merged, nothing deployed)
- **Date:** 2026-10-05 (local +08:00)
- **Dependencies:** A00 (protected boundary), A01 (read-only inventory) — both `staged_pass`
- **Writable roots used:** `integration-staging/` and `docs/integration/execution/` only

## 1. What the plan required (A02)

> **Write:** a minimal staged package, tests directory, fixture directory, private runtime/data directories, and test configuration.
> **Steps:** use the existing Python executable without installing into its venv; direct bytecode, pytest cache, HOME-like application state and temporary files into staging; disable real network transports; use only private subprocess cwd and data paths.
> **Pass:** a fixture test can run and every created file is inside the allowlist; a deliberate prohibited source-network call fails.
> **Additional isolation checks:** inspect module resolution before importing any application module; assert every application module loaded during staged tests has `__file__` under staging; reject symlinks/junctions resolving back to original code; for copied Node code, resolve local imports and reject imports that escape staging; the check must fail deliberately when a forbidden module or data path is supplied.
> A copied test is not automatically safe — never copy the original `conftest.py`; build an explicit staging test configuration.

## 2. What was built

| Path | Purpose |
| --- | --- |
| `integration-staging/pytest.ini` | Explicit staging test config: `testpaths = tests`, `pythonpath = src`, `cache_dir = runtime/pytest-cache`, `norecursedirs = runtime fixtures .git __pycache__`. No original `conftest.py` or `pyproject`/`setup.cfg` is reused. |
| `integration-staging/src/examdata_integration/__init__.py` | Minimal staged package (`__version__ = "0.0.0-phasea"`); no application code copied yet. |
| `integration-staging/src/examdata_integration/testing/guards.py` | Module guard, module audit, path guard, loopback-only network guard, `offline_transport()`. |
| `integration-staging/src/examdata_integration/testing/node_guard.py` | Static Node import resolver: relative/absolute specifiers that escape staging are rejected; bare specifiers listed, not resolved. |
| `integration-staging/tests/conftest.py` | Explicit staging configuration (not a copy of the original): creates private dirs, pins `HOME`/`USERPROFILE` → `runtime/home`, `TEMP`/`TMP` → `runtime/tmp`, the six `EXAMDATA_*_DIR` variables → `runtime/data/…`, sets `PYTHONDONTWRITEBYTECODE=1`; installs the module guard at import and the network guard at configure; audits `sys.modules` after every test and at session finish. |
| `integration-staging/tests/test_harness_isolation.py` | 13 tests proving the harness, including deliberate-failure cases. |
| `integration-staging/tests/test_node_import_guard.py` | 5 tests for the Node import guard. |
| `integration-staging/fixtures/` | Private fixture root (README only so far; fixtures arrive in A03). |
| `integration-staging/runtime/{data,home,tmp,pytest-cache,pytest-temp}` | Private runtime state, caches and temp dirs — all inside the allowlist. |
| `integration-staging/tools/inspect_module_resolution.py` | Read-only module-resolution audit (`find_spec`, editable-install artefacts, verdict). |
| `integration-staging/tools/run_staged_tests.sh` | Runs pytest from inside staging with private basetemp/cache. |
| `integration-staging/tools/a02_final_checks.py` | This packet's closing checks (run last). |

## 3. Evidence

| Evidence | Path | Label |
| --- | --- | --- |
| Module-resolution audit (before any application import) | `docs/integration/execution/evidence/A02/module_resolution_before_imports.txt` | `static_inspection` |
| Staged test run (18 passed, exit 0) | `docs/integration/execution/evidence/A02/pytest_run_stdout.txt` | `synthetic_fixture` |
| Post-run leak check | `docs/integration/execution/evidence/A02/leak_check_after_pytest.txt` | `static_inspection` |
| Closing checks transcript | `docs/integration/execution/evidence/A02/final_checks.txt` | `static_inspection` |

All four are produced by the shared venv interpreter (`examdata/.venv/Scripts/python.exe`, Python 3.14.7, pytest 9.1.1) with `PYTHONDONTWRITEBYTECODE=1`; nothing was installed into that venv.

## 4. Module-resolution audit — hazard confirmed and neutralised

The shared venv carries an editable install:

- artefact: `examdata/.venv/Lib/site-packages/__editable__.examdata-0.1.0.pth`
- content: `C:\Users\weo\Desktop\api\examdata\src`
- effect: `find_spec("examdata").origin == C:\Users\weo\Desktop\api\examdata\src\examdata\__init__.py`

So a naive `import examdata` inside staged tests would load and execute **original** application code. The harness therefore:

1. installs a meta-path finder that raises `ForbiddenImportError` for the top-level name `examdata` (proved by `import examdata` raising in-test, and by `find_spec` raising);
2. audits `sys.modules` after every test and at session finish — any loaded `examdata_integration.*` module whose `__file__` is outside `integration-staging` raises `StagingViolationError` (proved by a deliberate violation test);
3. resolves paths through `os.path.realpath`, so symlinks/junctions that point back at original code are rejected (proved by a link-escape test with junction fallback);
4. rejects `examdata/src`, `ielts-data` and the workspace root as staged paths while allowing paths under `integration-staging`.

`examdata_integration` itself resolves under `integration-staging/src`, as required.

## 5. Network and subprocess isolation

- `socket.socket` is replaced by a loopback-only subclass; `socket.create_connection` and `socket.getaddrinfo` are wrapped. Non-loopback `connect`, `connect_ex`, `create_connection` and DNS lookups raise `NetworkDisabledError`.
- `offline_transport()` is the failing transport that provider tests will use in later packets.
- Proved deliberately in-test: `connect("192.0.2.1", 9)` fails, `getaddrinfo("example.com", 443)` fails, `offline_transport()` fails; loopback is not blanket-blocked (so a private local test server can still be started later).
- Subprocess cwd and temp/HOME-like state are redirected into `integration-staging/runtime/`.

## 6. Failures encountered and fixed

| Failure | Evidence | Resolution |
| --- | --- | --- |
| First staged run: 1 failed / 17 passed — `test_bare_specifiers_are_listed_but_not_resolved` got `['lodash', 'node:fs']` instead of source order `['node:fs', 'lodash']`. | first run of `run_staged_tests.sh`, exit 1 (ledger `exit_codes` records the single `1`) | `iter_specifiers` in `node_guard.py` collected matches pattern-by-pattern; it now sorts matches by source position before de-duplicating, matching its documented "source order" contract. The guard was **not** weakened — the assertion was left as-is and the implementation fixed. |
| First `a02_final_checks.py` run: 2 FAILs — (a) `node_guard.rejects_escaping_import`: the probe's specifier `../../examdata/src/…` resolved to `integration-staging/examdata/src/…`, i.e. still *inside* staging, so the guard correctly allowed it; (b) `artifacts.all_present`: the required list contained this transcript, which the run itself creates. | `evidence/A02/final_checks.txt` (first run, exit 1) | Both were defects in the checks script, not the guards: the probe now computes its escape target with `os.path.relpath(guards.ORIGINAL_APP_CODE/…, probe_dir)` (three levels up, `../../../examdata/src/…`), and the self-referential required entry was removed (matching the A01 checks script). |

Second run of the staged suite: **18 passed, exit 0.** Second run of the closing checks (after the two probe fixes above): **PASS**.

## 7. Leak check (post-run)

- `__pycache__` directories created in protected roots (`examdata/src`, `ielts-api`, `ielts-data`, `toefl-api`, `frontend`, `docs`) during the run window: **0**.
- `.pytest_cache` directories touched during the window: **0** (cache is pinned to `integration-staging/runtime/pytest-cache`).
- Files created anywhere in the workspace during the window outside the two allowlist roots: **1**, namely `examdata/examples/curl.md` — the active owner's (Kimi Code's) own documentation work on the unified gateway; it is tracked-modified in the `examdata` repository and was not written by this executor. Owner activity in the original tree is expected and is never repaired (plan §0.9).
- All executor writes stayed inside `integration-staging/` and `docs/integration/execution/`.

## 8. Pass criteria → result

| Criterion | Result |
| --- | --- |
| A fixture test can run | PASS — 18 tests, exit 0 |
| Every created file is inside the allowlist | PASS — leak check §7 |
| A deliberate prohibited source-network call fails | PASS — non-loopback socket + DNS + `offline_transport` all raise `NetworkDisabledError` |
| Module resolution inspected before any application import | PASS — audit transcript precedes the test run |
| Every loaded application module resolves under staging | PASS — in-test audit, session-finish audit, deliberate violation detected |
| Symlinks/junctions to original code rejected | PASS — link-escape test |
| Copied Node imports escaping staging rejected | PASS — 5 node-guard tests |
| Check fails deliberately when a forbidden module/path is supplied | PASS — `import examdata`, `find_spec`, audit probe, path probes all raise |

## 9. Deferred / not done in A02

- No application code, test, or fixture has been copied into staging yet — A02 built only the minimal staged package and the isolation harness. Copy-for-execution of service modules happens in the packets that need them (A05 onward), each under this harness.
- Materials and timetable integration remain `deferred_active_owner` (7 worksheet rows); nothing in those areas was executed or copied.
- `node_guard` does not resolve bare specifiers, TypeScript path mappings or `package.json` `imports`/`exports` conditions; the controlled Node runner (A06) must additionally confine resolution to staged `node_modules` and validate `package.json` metadata.
- The network guard is process-local: a child process that is not launched through the controlled runner would inherit the patched module only if it imports this package. A06's runner must set its own env/network confinement for Node child processes.
- The module audit only inspects `examdata` and `examdata_integration` top-level names; third-party modules are intentionally allowed to come from the shared interpreter installation.

## 10. Staged vs merged vs deployed

- **Staged:** everything listed in §2, under `integration-staging/`.
- **Merged:** nothing. No file in the original project was created, modified or deleted by this executor.
- **Deployed:** nothing. No service was started, stopped, restarted or reconfigured; no database was touched; all seven Phase B gates remain closed.

## 11. Next action

A03 — capture safe fixtures (plan §11): build the fixture tree under `integration-staging/fixtures/` from small, immutable, non-active JSON (IELTS/TOEFL `data/*.json`, CIE indexes) as `copied_snapshot`, with a provenance manifest recording source path, source sha256, copy sha256, size and copy time; no databases, no examination materials, no timetable files.
