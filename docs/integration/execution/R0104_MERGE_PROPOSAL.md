# R0104 merge proposal (private preparation only)

Generated: 2026-10-06T22:56:37+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 16 (8 require the human release, 8 are staging-only tooling)

Nothing in this proposal has been applied. All seven gates are closed.

## Action-level gate model

A gate is required only for the action that performs that effect.
A private-preparation pass never satisfies an original-action prerequisite.

| Action | Gate required |
| --- | --- |
| private preparation (read, stage, copy, offline validate) | none |
| write into the original project | `original_paths_released` |
| real data write | `real_data_write_authorized` |
| existing service cutover | `existing_service_cutover_authorized` |
| upstream request | `upstream_requests_authorized` |
| CIE resume | `cie_resume_authorized` |
| remote deployment | `remote_deployment_authorized` |
| original cleanup | `original_cleanup_authorized` |

## Entries

| id | finding | staged path | proposed target | before | after | gates |
| --- | --- | --- | --- | --- | --- | --- |
| RP-0001 | R01,R02 | `integration-staging/tools/b_ledger_update.py` | `(staging only)` | ac9b01cbfc27 | ec80a56ac2c9 | none |
| RP-0002 | R04 | `integration-staging/src/examdata_integration/runtime/manifest.py` | `examdata/src/examdata/integration/runtime/manifest.py` | 8a56f668cc72 | 7ff0e084db5d | original_paths_released |
| RP-0003 | R04 | `integration-staging/src/examdata_integration/runtime/runner.py` | `examdata/src/examdata/integration/runtime/runner.py` | 5d45f6de87fb | 75001ddba5a6 | original_paths_released |
| RP-0004 | R04 | `integration-staging/src/examdata_integration/runtime/settings.py` | `examdata/src/examdata/integration/runtime/settings.py` | 94e825030d13 | 320f9e39fe65 | original_paths_released |
| RP-0005 | R04 | `integration-staging/src/examdata_integration/api/dataset.py` | `examdata/src/examdata/integration/api/dataset.py` | 5801f31c5c17 | c341ce3018f1 | original_paths_released |
| RP-0006 | R04 | `integration-staging/src/examdata_integration/adapters/source_reader.py` | `examdata/src/examdata/integration/adapters/source_reader.py` | 42505ce1eb4a | eb77e0004d3a | original_paths_released |
| RP-0007 | R04 | `integration-staging/tests/conftest.py` | `examdata/tests/integration/conftest.py` | d15742bd1810 | 4b28ad52a9bb | original_paths_released |
| RP-0008 | R04 | `integration-staging/tests/test_config_resolution.py` | `examdata/tests/integration/test_config_resolution.py` | 18cd2340adf0 | cc0a8fb6611d | original_paths_released |
| RP-0009 | R04 | `integration-staging/src/examdata_integration/runtime/paths.py` | `examdata/src/examdata/integration/runtime/paths.py` | none | d0207fc79d66 | original_paths_released |
| RP-0010 | R04 | `integration-staging/tools/a06_probe_runner.py` | `(staging only)` | none | 3f9d5f172ba3 | none |
| RP-0011 | R04 | `integration-staging/tools/a06_final_checks.py` | `(staging only)` | none | e461eb5f9394 | none |
| RP-0012 | R04 | `integration-staging/tools/a08_probe_adapters.py` | `(staging only)` | none | 76d253aa4ab8 | none |
| RP-0013 | R04 | `integration-staging/tools/a10_probe_api.py` | `(staging only)` | none | 676848ef34e3 | none |
| RP-0014 | R04 | `integration-staging/tools/a11_probe_binary.py` | `(staging only)` | none | a0099f4e50fe | none |
| RP-0015 | R04 | `integration-staging/tools/a14_build_artifacts.py` | `(staging only)` | none | 3173adc76bf0 | none |
| RP-0016 | R04 | `integration-staging/tools/a14_final_checks.py` | `(staging only)` | none | 923b5414c00d | none |

## Requirements before merge

- explicit human release opening original_paths_released with an explicit scope
- re-run the isolated staged suite against the frozen candidate
- verify each proposed target's sha256 before and after the add_file
