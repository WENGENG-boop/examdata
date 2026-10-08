# B01 test report

All commands ran in the two Phase A write roots; the originals were read-only. Every exit code below is from the recorded transcript under `docs/integration/execution/evidence/B01/b00b01-20261006T132400/`.

## Executed checks

| check | command (cwd) | exit | evidence |
| --- | --- | --- | --- |
| isolated staged suite | `pytest -q -p no:cacheprovider` (cwd `integration-staging`) | 0 | `b01_staged_pytest_rerun.txt` (887 passed, 0 failed, 0 skipped) |
| B01 merge map build | `b01_build_merge_map.py` | 0 | `b01_build_merge_map_run.txt`, `B01_MERGE_MAP.json` |
| private-copy layout validation | `b01_validate_layout.py` | 0 | `b01_layout_validation_run.txt`, `B01_LAYOUT_VALIDATION.json` |
| Node component discovery | `b01_validate_node_discovery.py` | 0 | `b01_node_discovery_run.txt`, `B01_NODE_DISCOVERY.json` (5/5 checks) |

## Targeted results

- module resolution: 49 modules imported from the private tree, 3 refused (guard-blocked, see F03-GUARD-DEP), 0 resolved outside the private tree.
- Node component discovery: exactly one component is admitted (the synthetic `fake_cli`, labelled synthetic); its entry point resolves inside the deployment root; a manifest whose `code_location` escapes the root is refused and not admitted. Real Node components are not released, so their discovery stays `not_run` and no synthetic stand-in is promoted. In the private target layout the discovery module import is blocked by the same F03-GUARD-DEP guard dependency.
- contracts/schemas: 28/28 JSON resources loaded from the private tree.
- CLI target: `examdata/src/examdata/cli.py`, entry point `examdata = "examdata.cli:app"` (F01 corrected).
- A14 map: byte-unchanged (sha256 `29940a0b0582b8b7e8e6fea79692ba849e3d25dd917dfa059d8bbda98fc3654a`).

## Not run (explicit, with reason)

| check | reason |
| --- | --- |
| active materials/timetable integration | Kimi-owned active feature; worksheet rows `deferred_active_owner`; no release |
| released-tree three-way reconciliation | `gate:original_paths_released` closed |
| live data / DB migration | `gate:real_data_write_authorized` closed |
| upstream requests | `gate:upstream_requests_authorized` closed |
| service cutover / ports 8000/5188 | `gate:existing_service_cutover_authorized` closed |
| wheel / clean-env install | belongs to B09; not claimed early |
| real Node component discovery | real components not released (`gate:original_paths_released` closed); synthetic `fake_cli` is validated but never promoted to a production release manifest |

No mandatory case was silently skipped: each is either executed above or listed here with its blocking gate.
