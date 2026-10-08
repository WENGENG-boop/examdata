# Staged documentation (Phase A proposal)

Proposed versions of the documentation that will be published with the integration.
**They are not published anywhere yet**: plan §9.3 says shared documentation is updated
only after the Phase B release, so these drafts live in the staging tree and merge with
the code.

| file | content | status |
| --- | --- | --- |
| `integration-guide.md` | the merged integration guide (status, v1 compatibility, v2 reference, configuration precedence, component installation, data layout, identity and quality, source limitations, test commands, examples) | proposed |
| `release-and-rollback.md` | release bundle contents, smoke checks, rollback units and instructions | proposed |
| `v2-api-reference.md` | endpoint table generated from the staged app factory's OpenAPI document | generated |

The machine-readable merge map (`docs/integration/execution/A14_MERGE_MAP.json`) records,
per file, the eventual target path and the reversal. Nothing in this directory has been
merged or deployed; the original project is unchanged by this executor.

## Honesty rules these drafts follow

- Every staged claim is labelled `synthetic_fixture`, `copied_snapshot` or
  `static_inspection`; no fixture result is presented as live source validation.
- "Staged", "merged" and "deployed" are never conflated.
- Real data effects, real services and upstream sources are out of scope in Phase A and
  are reported as `not_run` until Phase B authorization exists.
