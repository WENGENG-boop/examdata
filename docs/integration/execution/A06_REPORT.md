# A06 — Configuration and the controlled Node runner (Phase A, isolated)

**Status:** staged pass. Nothing merged, nothing deployed; every Phase B gate
remains closed. Work is confined to `integration-staging/` and
`docs/integration/execution/`.

## 1. Scope

Build the plan §3.5 / §6 layer that every later packet depends on: a single
resolved configuration, a component-manifest validator, and one bounded
child-process runner — plus the read-only doctor that reports on both without
creating anything.

* **Configuration** (plan 6.1–6.2): one resolver with a fixed precedence, an
  environment template, the A01 configuration matrix preserved and extended.
* **Component manifest** (plan 6.3): per-component name/version/revision, code
  location, runtime, entry point, command whitelist, schemas, environment
  allowlist, data roots, read/write policy and health probe; an invalid
  component is never admitted.
* **Controlled runner** (plan 6.4): the ten rules — whitelist, argument array
  (no shell), component-local cwd, filtered environment, bounded queue/time/
  bytes/concurrency, one JSON object on stdout, a stable classification per
  failure, process-tree termination with cleanup evidence, redacted stderr, and
  no per-list-item process fan-out.
* **Doctor** (plan 6.2–6.3): read-only diagnostics; resolving or importing must
  never create a directory.

Inputs (hashed into the ledger): the four governing documents, the ledger, the
A05 report, the four original gateway sources inspected read-only for the spawn
contract (`examdata/api/ielts.py`, `examdata/api/toefl.py`,
`examdata/core/config.py`, `examdata/api/security.py`), and the A05 runtime
artefacts.

## 2. Deliverables

Source (staged package `integration-staging/src/examdata_integration/`):

| file | role |
| --- | --- |
| `runtime/settings.py` | `SettingSpec`/`SETTING_SPECS` (24 settings), `SettingKind`, `ConfigLayer`, `resolve_config`, `ResolvedConfig` (`settings_report`, `ensure_directories`), `env_template`, 4 typed errors |
| `runtime/manifest.py` | `parse_component`, `load_manifest_set`, `ComponentManifest`, `ManifestSet`, `ManifestProblem`, `ManifestError`; 17 stable problem codes |
| `runtime/classification.py` | `RunnerOutcome` (14 outcomes), `OUTCOME_PRECEDENCE`, `ERROR_CODES`, `RETRYABLE_OUTCOMES`, `INFRASTRUCTURE_OUTCOMES`, `error_object` |
| `runtime/redact.py` | `redact_text` (secrets, UNC/drive/POSIX paths, whitespace, bound), `contains_path` |
| `runtime/runner.py` | `RunnerLimits`, `RunResult`, `parse_stdout`, `NodeRunner` (whitelist, argv array, filtered env, semaphore, timeouts, overflow kill, tree termination, cleanup evidence) |
| `runtime/doctor.py` | `doctor_report`, `build_report`, `main` (read-only; `creates_directories: false`) |
| `runtime/__init__.py` | the public surface |
| `testing/runtime_support.py` | test-only fixture/manifest helpers (never product code) |

Staged fixtures and config:

| path | role |
| --- | --- |
| `components/fake-node-cli/fake-cli.mjs` | synthetic zero-dependency Node CLI (12 commands) |
| `components/manifest.json` | `examdata.component-manifest/1`, one component `fake_cli` |
| `components/README.md` | provenance note (not a copy of the original gateways) |
| `config/staging.env.example` | environment template from `env_template()` |
| `config/staging-config.example.json` | the same settings as a JSON config file |
| `config/README.md` | precedence and file semantics |

Tools: `integration-staging/tools/a06_probe_runner.py` (31-scenario offline
runtime probe), `integration-staging/tools/a06_final_checks.py` (closing
checks), `integration-staging/tools/a06_close_patch.py` (ledger patch).

Tests (staged): `tests/test_config_resolution.py` (23),
`tests/test_config_manifest.py` (27), `tests/test_runner_classification.py` (29),
`tests/test_runner_limits.py` (12).

## 3. Configuration (frozen, tested)

Precedence, highest first: **explicit argument → process environment → config
file → manifest defaults → built-in default**. A setting is taken from the
highest layer that supplies a non-empty value; `source` and `origin` are recorded
per setting. Legacy aliases (`IELTS_API_DIR`, `TOEFL_API_DIR`) still work but
warn; two differing alias values raise `ConfigConflictError` instead of silently
choosing one. Unknown keys, bad ints/enums/URLs raise typed errors. `PATH`
values are made absolute; a `SECRET` is reported only as `set`/`unset`.

The A01 configuration matrix is preserved (every setting keeps its canonical
`EXAMDATA_*` name and legacy alias), and eight settings are marked
`new_in_phase_a`: `component_manifest`, `cie_index_root`, `toefl_data_root`,
`catalog_root`, `operations_root`, `network_mode` (default `offline`),
`runner_output_budget`, `crop_budget`, `total_response_budget`.

## 4. Component manifest (frozen, tested)

A manifest is `{"manifest_version": "examdata.component-manifest/1",
"components": [...]}`. Each component declares the plan 6.3 fields. Validation
problems carry a stable code and the offending field: `missing_field`,
`wrong_type`, `empty`, `bad_identifier`, `bad_command`, `duplicate_command`,
`not_relative_path`, `path_escapes_root`, `unknown_runtime`, `unknown_policy`,
`bad_env_name`, `bad_role`, `health_probe_unknown_command`, `entry_point_missing`,
`duplicate_component_id`. `load_manifest_set` raises only for an unusable
document (unreadable JSON, wrong version, empty list); otherwise it collects
problems and admits **only** problem-free components, so a component with any
problem never reaches the runner whitelist. Every accepted location must be a
relative path resolving inside the deployment root.

## 5. Runner classification (frozen, tested)

One outcome per invocation, chosen deterministically by `OUTCOME_PRECEDENCE`
(whitelist → missing → startup → queue → cancelled → overflow → timeout →
non-zero exit → invalid JSON → multiple values → business failure → ok):

| outcome | error code | retryable |
| --- | --- | --- |
| `ok` | `ok` | — |
| `business_failure` | `business_failure` | no |
| `component_not_allowed` | `component_not_allowed` | no |
| `command_not_allowed` | `command_not_allowed` | no |
| `missing_component` | `component_missing` | no |
| `missing_runtime` | `runtime_missing` | no |
| `startup_failure` | `startup_failure` | no |
| `queue_full` | `queue_full` | **yes** |
| `timeout` | `timeout` | **yes** |
| `cancelled` | `cancelled` | no |
| `output_overflow` | `output_overflow` | no |
| `nonzero_exit` | `nonzero_exit` | no |
| `invalid_json` | `invalid_json` | no |
| `multiple_json_values` | `multiple_json_values` | no |

`ok` and `business_failure` are the only non-infrastructure outcomes. On
timeout/overflow/cancellation the process tree is terminated and the run records
cleanup evidence (`terminated`, `method`, `waited`, `returncode`,
`readers_alive`, `orphan_check`, `pid_alive_after`). The concurrency limit is
process-local — not a global limit across Uvicorn workers — so initial deployment
stays at one worker (plan 6.4).

## 6. Evidence

| check | result | evidence |
| --- | --- | --- |
| Runtime probe, 31 scenarios, offline, real `node` | **A06_PROBE: PASS (0 failing)** | `evidence/A06/runner_stdout.txt` |
| Staged suite, offline | **232 passed**, exit 0 | `evidence/A06/pytest_run_stdout.txt` |
| Configuration precedence + validation | **PASS** | `tests/test_config_resolution.py` |
| Manifest validation + doctor | **PASS** | `tests/test_config_manifest.py` |
| Runner classification (12 named modes) | **PASS** | `tests/test_runner_classification.py` |
| Runner bounds and result shape | **PASS** | `tests/test_runner_limits.py` |
| Closing checks | see `final_checks.txt` | `evidence/A06/final_checks.txt` |

Suite growth: A05 baseline 141 → 232 (A06 adds 91 tests: 23 + 27 + 29 + 12).

## 7. Corrections made in this packet

1. **Windows environment names are case-insensitive.** `"PATH" in os.environ`
   was false (the inherited key is `Path`), so the child environment was nearly
   empty and `node` exited 1. Fixed with a case-insensitive `NodeRunner._set_env`
   used by both the constructor and `child_environment`.
2. **Relative component locations resolved against the wrong base.** A relative
   `entry_point`/`code_location` combined with the component-local `cwd` made the
   script path relative to the wrong directory (`MODULE_NOT_FOUND`). Fixed by
   making the deployment root absolute in `settings.resolve_config`,
   `manifest.parse_component`, `manifest.load_manifest_set` and
   `NodeRunner.__init__`.
3. **Overflow/cancel race.** A reader thread could set the overflow flag while
   the process was already exiting on its own, so a clean exit was misreported.
   Fixed by joining the reader threads before classification and only terminating
   when the process is still running.
4. Test-only corrections while writing the suite: `ConfigLayer` values are
   `manifest_default` and `config_file` (not `manifest`/`file`), and a
   parametrised manifest case needed its display id separated from the expected
   problem code.

## 8. Deliberate limitations

* The runner starts only the synthetic `fake_cli` fixture; there is **no real
  Node gateway adapter** yet (that is A10/A11) and **no network or database
  access**. `network_mode` is `offline` and the doctor flags any other value.
* The manifest declares one component. Real component discovery is A07–A11.
* `path_escapes_root` is defensive: any `..`/drive/root prefix is already
  rejected as `not_relative_path`, so a relative declaration cannot reach the
  root-escape branch. A test documents this by construction.
* `secrets=` must be supplied by the caller for secret redaction — the runner
  cannot guess which value is a secret; tests build the runner through
  `runtime_support.runner`, which registers the fixture secret.

## 9. Remaining gaps / deferred

* Real CIE/Edexcel/IELTS/TOEFL read adapters (A07/A08) consume this runner next;
  nothing here reads protected or live resources.
* The runner's concurrency bound stays process-local until shared source limiting
  exists; the plan keeps initial deployment at one worker (deferred to Phase B).
* Active materials/timetable integration stays deferred to the active owner.

## 10. Next action

A07 — CIE and Edexcel read adapters over synthetic fixtures (plan §11), then A08
IELTS/TOEFL, A09 catalog + revision publication, A10 the isolated v2 API, A11
binary ranges and budgets, A12 the route worksheet, A13 the frontend proposal,
A14 the file-by-file merge map and A15 `PHASE_A_REPORT.md`.
