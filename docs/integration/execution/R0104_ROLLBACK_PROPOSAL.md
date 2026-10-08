# R0104 rollback proposal (private preparation only)

Generated: 2026-10-06T22:56:37+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 16 (staging level: 1 delete, 8 restore, 7 line removal; original level: 8 delete, 8 no original action)

Nothing has been merged, so nothing is currently pending rollback. This file states how each change would be reversed.

## Guards

- verify the resolved absolute path and its sha256 before any delete/restore
- no delete or restore ever targets a protected original in Phase A
- planned original edits are reversible only after the human release
- all seven gates remain closed during rollback

## Never

- never touch docs/integration/execution/evidence/**
- never touch integration-staging/runtime/phase-b/** sealed transcripts
- never restore the live execution ledger from a private copy

## Entries

| id | staged path | kind | restore to | reversal |
| --- | --- | --- | --- | --- |
| RP-0001 | `integration-staging/tools/b_ledger_update.py` | modified_staged_file | ac9b01cbfc27 | no reversal needed: the file never leaves integration-staging/ |
| RP-0002 | `integration-staging/src/examdata_integration/runtime/manifest.py` | modified_staged_file | 8a56f668cc72 | delete_file at the proposed target, and only if the target's current sha256 still equals staged_sha256_after |
| RP-0003 | `integration-staging/src/examdata_integration/runtime/runner.py` | modified_staged_file | 5d45f6de87fb | delete_file at the proposed target, and only if the target's current sha256 still equals staged_sha256_after |
| RP-0004 | `integration-staging/src/examdata_integration/runtime/settings.py` | modified_staged_file | 94e825030d13 | delete_file at the proposed target, and only if the target's current sha256 still equals staged_sha256_after |
| RP-0005 | `integration-staging/src/examdata_integration/api/dataset.py` | modified_staged_file | 5801f31c5c17 | delete_file at the proposed target, and only if the target's current sha256 still equals staged_sha256_after |
| RP-0006 | `integration-staging/src/examdata_integration/adapters/source_reader.py` | modified_staged_file | 42505ce1eb4a | delete_file at the proposed target, and only if the target's current sha256 still equals staged_sha256_after |
| RP-0007 | `integration-staging/tests/conftest.py` | modified_staged_file | d15742bd1810 | delete_file at the proposed target, and only if the target's current sha256 still equals staged_sha256_after |
| RP-0008 | `integration-staging/tests/test_config_resolution.py` | modified_staged_file | 18cd2340adf0 | delete_file at the proposed target, and only if the target's current sha256 still equals staged_sha256_after |
| RP-0009 | `integration-staging/src/examdata_integration/runtime/paths.py` | new_file | delete | delete_file at the proposed target, and only if the target's current sha256 still equals staged_sha256_after |
| RP-0010 | `integration-staging/tools/a06_probe_runner.py` | staging_tooling_edit | delete | remove the added os.environ.setdefault(EXAMDATA_INTEGRATION_ROOT, ...) line (exact line recorded in the change manifest) |
| RP-0011 | `integration-staging/tools/a06_final_checks.py` | staging_tooling_edit | delete | remove the added os.environ.setdefault(EXAMDATA_INTEGRATION_ROOT, ...) line (exact line recorded in the change manifest) |
| RP-0012 | `integration-staging/tools/a08_probe_adapters.py` | staging_tooling_edit | delete | remove the added os.environ.setdefault(EXAMDATA_INTEGRATION_ROOT, ...) line (exact line recorded in the change manifest) |
| RP-0013 | `integration-staging/tools/a10_probe_api.py` | staging_tooling_edit | delete | remove the added os.environ.setdefault(EXAMDATA_INTEGRATION_ROOT, ...) line (exact line recorded in the change manifest) |
| RP-0014 | `integration-staging/tools/a11_probe_binary.py` | staging_tooling_edit | delete | remove the added os.environ.setdefault(EXAMDATA_INTEGRATION_ROOT, ...) line (exact line recorded in the change manifest) |
| RP-0015 | `integration-staging/tools/a14_build_artifacts.py` | staging_tooling_edit | delete | remove the added os.environ.setdefault(EXAMDATA_INTEGRATION_ROOT, ...) line (exact line recorded in the change manifest) |
| RP-0016 | `integration-staging/tools/a14_final_checks.py` | staging_tooling_edit | delete | remove the added os.environ.setdefault(EXAMDATA_INTEGRATION_ROOT, ...) line (exact line recorded in the change manifest) |
