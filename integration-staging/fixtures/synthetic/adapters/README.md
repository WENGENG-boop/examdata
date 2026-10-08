# A07 read-adapter fixtures (synthetic)

These fixtures drive the A07 read adapters
(`integration-staging/src/examdata_integration/adapters/`). They are hand-authored
synthetic documents shaped like raw board indexes: invented text only, no
upstream content, no real document hashes.

| File | Shape exercised |
| --- | --- |
| `cie-index-adapters.json` | exact / ancestor / descendants answer resolution, a missing mark scheme, a document hash conflict, two regions on one question, rotated-page metadata, a region on an undeclared page |
| `edexcel-index-adapters.json` | qualification levels, unit/paper codes, session labels, aliases, a missing mark scheme, a conflicting region hash |

Provenance is recorded in `PROVENANCE.json`, written by
`integration-staging/tools/a07_capture_adapter_fixtures.py` and verified by
`integration-staging/tests/test_adapters_provenance.py`. Run the tool with
`--check` to confirm the manifest is current.

Nothing here may be promoted to verified content: every fixture carries
`"fixture_kind": "synthetic"` and the adapters refuse anything else.
