# Staged frontend copy (Phase A · A13)

This directory is the Phase A proposal for the frontend integration: a staged
copy of the original `frontend/` tree, re-wired to the staged v2 API envelope
and exercised only against a private, offline fixture server.

**Staged, not merged.** Nothing here is deployed, and the original `frontend/`
tree is untouched — `PROVENANCE.json` records the byte-level source hashes
that prove that. Active materials/timetable integration stays deferred.

## What is here

| File | Role |
| --- | --- |
| `index.html`, `styles.css`, `app.js`, `search.mjs` | copied from `frontend/`; `app.js` and `index.html` carry the minimal staged edits listed in `PROVENANCE.json` |
| `client.mjs` | new: v2 client (`/api/v2` envelope, season fan-out, staged-origin labels, reversible `examdata.v2-client` off-switch) |
| `fixture-server.mjs` | new: private offline server; serves the page, the synthetic snapshots and `/api/v2/resources*` with the same envelope as the staged v2 API, plus the fixture failure map |
| `fixtures/` | new: synthetic `/catalog.json`, `/syllabi.json`, resource items and failure injection; all values fictional (`fixtures/PROVENANCE.json` lists hashes) |
| `tests/` | `node --test` suites: copied search tests, client contract tests, end-to-end fixture-server flows |

## What changed in the copied files, and why

* `app.js` imports `./client.mjs` instead of calling `/resources` directly.
  The dead `/gateway` helper and the then-unused `params` helper were removed;
  everything else is preserved verbatim.
* `liveSearch()` calls `searchDocuments()` and labels results honestly:
  `暂存夹具验证（staged fixture validation）· 合成夹具数据` while the data is
  synthetic, `原始来源文件` otherwise. The detail dialog shows
  `STAGED FIXTURE · 合成夹具` for synthetic-quality rows.
* When the storage marker `examdata.v2-client` is `off`, live search is
  disabled with a clear message and only catalog ER rows remain; removing the
  marker switches it back on.
* `index.html` gains a visible banner: this copy is staged fixture validation
  only and is not connected to any real source.

## Run it (offline)

    node integration-staging/frontend/fixture-server.mjs     # 127.0.0.1, ephemeral port
    node --test integration-staging/frontend/tests/          # same fixtures, no server needed

The fixture server never uses the network, never binds 5188/8000 (the
original service ports) and never reads the original tree.

## Phase B merge requirements (not done here)

* The real backend must expose source-discovery fields (board/subject/year/
  season/paper/document_type) on `/api/v2/resources` items — the `discovery`
  block used here is a proposal fixture, not an upstream contract. The legacy
  discovery logic lives in `frontend/resources.mjs`, which this staged copy
  intentionally does not ship.
* `/catalog.json` and `/syllabi.json` snapshots must come from the merged
  build; the fixtures here are synthetic stand-ins.
* `resources.mjs`, `server.mjs`, `build-*.mjs` and `syllabi.test.mjs` from the
  original tree are out of scope for this copy. The six legacy
  `resources.mjs` tests are retired; their observable behaviour (all-season
  fan-out, partial failure, gated files, labels) is re-covered by
  `tests/client.test.mjs` and `tests/flow.test.mjs` against the v2 envelope.
