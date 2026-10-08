# B02 rehearsal review report (private preparation only)

Generated: 2026-10-06T23:54:49+08:00  
Packet: **B02** — integrate shared configuration and component packaging  
Status: `b02_private_rehearsal_complete_pending_human_release`  
Probe verdict: `b02_rehearsal_valid_private_only`  
Probe findings: 0

Nothing in this report has been merged or deployed. The original project was not read, imported or written by any B02 step. All seven gates are closed.

## 1. What B02 rehearsed

B02 owns the shared configuration and component packaging. What can be done without the human release is a rehearsal: take the R04 target-layout candidate as the parent, package the shared configuration beside it, and prove the acceptance properties that do not need the original tree — old aliases keep resolving, startup behaviour is unchanged, and component discovery does not depend on the working directory.

## 2. Candidate and lineage

- Candidate: `integration-staging/runtime/b02-rehearsal-20261006/candidates/b02-shared-config-v1`
- Parent: `integration-staging/runtime/r0104-repair-20261006/candidates/r04-target-layout-v2` (the R04 target-layout candidate)
- Parent tree: 182 files, sha256 `c84973e0072fdc9b35f14d8ad1f5a3746f3f8793c340aefc304eb18c51e16098`
- Candidate tree: 185 files (182 carried from the parent + 3 packaged config files), sha256 `463628cff11ef88ef9f42898cf31647483edcafb369bcc4c4b96dec2b7cb22cf`
- Candidate digest reproducible from the tree on disk: `True` (re-checked independently by the validator, not just self-reported by the builder)
- Parent manifest sha256 unchanged at build time: `923e7a298179ef22c6cb715deb701d9ec79b2fa2b1159136af1802c24c988c6a`

The parent tree digest was re-computed after the copy and is unchanged, so the R04 candidate was not modified by this rehearsal.

## 3. Commands, working directory and exit codes

| Step | Command | cwd | Exit |
| --- | --- | --- | --- |
| build candidate | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b02-rehearsal-20261006/b02_build_candidate.py` | `C:/Users/weo/Desktop/api` | 0 |
| validate (probe from 3 cwds) | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b02-rehearsal-20261006/b02_validate.py` | `C:/Users/weo/Desktop/api` | 0 |
| isolated staged suite | `bash integration-staging/tools/run_staged_tests.sh -q` | `C:/Users/weo/Desktop/api` | 0 |
| merge + rollback proposals | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b02-rehearsal-20261006/b02_build_proposals.py` | `C:/Users/weo/Desktop/api` | 0 |
| review report + progress ledger | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b02-rehearsal-20261006/b02_build_report.py` | `C:/Users/weo/Desktop/api` | 0 |

## 4. Test results

- **Probe**: 32 checks x 3 working directories = 96 check executions, 0 failed.
- **Isolated staged suite**: 887 passed, 1 warning in 42.91s (exit 0). Unchanged from the R04 baseline of 887; B02 adds no test file to that suite.
- **Build checks**: 13/13.

### Negative results (the checks that must refuse or stay unchanged)

- `startup.import_creates_nothing`
- `startup.resolve_config_does_not_mutate_environ`
- `startup.resolve_creates_no_directory`
- `startup.ensure_directories_refuses_outside_root`
- `startup.secret_not_rendered`
- `startup.no_staging_override`
- `alias.conflicting_values_still_rejected`
- `packaging.discovery_independent_of_cwd`

### Positive controls

- `startup.root_env_is_candidate`
- `origin.runtime_within_candidate`
- `origin.paths_within_candidate`
- `precedence.order_unchanged`
- `alias.ielts_legacy_resolves`
- `alias.ielts_origin_is_legacy_name`
- `alias.toefl_legacy_resolves`
- `alias.deprecation_warned`
- `alias.canonical_name_needs_no_warning`
- `alias.same_value_only_warns`
- `alias.env_template_still_documents_aliases`
- `packaging.component_manifest_packaged`
- `packaging.exactly_fake_cli`
- `packaging.no_problems`
- `packaging.entry_point_inside_candidate`
- `packaging.discovery_recorded_two_cwds`
- `entry.examdata.integration.runtime`
- `entry.examdata.integration.runtime.settings`
- `entry.examdata.integration.runtime.runner`
- `entry.examdata.integration.runtime.manifest`
- `entry.examdata.integration.runtime.paths`
- `entry.examdata.integration.runtime.doctor`
- `entry.examdata.integration.legacy`
- `entry.examdata.integration.legacy.bridge`

## 5. Old-alias preservation and startup behaviour

- `IELTS_API_DIR` still resolves `ielts_dir` and still emits a deprecated-alias warning; the same holds for `TOEFL_API_DIR` / `toefl_dir`.
- The canonical names alone emit no warning; the same value under both names emits only a duplicate-alias warning; conflicting values still raise.
- Precedence is unchanged: explicit 9 > environment 8 > config file 7 > manifest default 6 > default 4.
- Importing the package creates nothing, and `resolve_config` does not mutate `os.environ`.

## 6. Component packaging

Discovery admits exactly the synthetic component set (['fake_cli']) with no problems, from an entry path inside the candidate, and the recorded result is identical from both working directories (`discovery_identical_across_cwds: True`).

## 7. Proposals

- Merge proposal: `docs/integration/execution/B02_MERGE_PROPOSAL.json` — 4 entries, 2 requiring the human release, 2 staging-only.
- Rollback proposal: `docs/integration/execution/B02_ROLLBACK_PROPOSAL.json`.

Both are marked `proposal_only_not_merged`. Nothing has been applied to the original project.

## 8. Live ledger and gates

- `docs/integration/execution/execution-ledger.json` sha256 `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Expected frozen value: `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Byte-unchanged: `True`
- Gates open: [] (all closed: `True`)

## 9. Not run

- real legacy Node gateway execution (ielts-api / toefl-api) — gate original_paths_released is closed
- real Node component execution — gate original_paths_released is closed; synthetic fixture only
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots unchanged

## 10. Not claimed / remaining blockers

Not claimed: `merged_pass`, `deployment`, `full B00/B01 completion`.

- original-project merge of the B02 payload — gate original_paths_released is closed; an explicit human release with an explicit scope is required
- real Node component execution (ielts-api / toefl-api) — the original components are not released; only the synthetic fake-node-cli fixture is discovered and it is never executed
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B02
