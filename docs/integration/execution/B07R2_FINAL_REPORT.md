# B07R2 — FINAL REPORT (second private review-fix run)

Run: `b07-reviewfix-20261007-774e4dad` · Date: 2026-10-07 ·
Status: **private, unmerged, undeployed — proposal only, ready for review,
not merged and not deployed.** All seven gates remain closed. No claim of
deployment, live cutover, or real-data acceptance is made anywhere in this
report.

This report repairs F1–F4 from
`docs/integration/execution/B07_INDEPENDENT_REVIEW_2026-10-07.md`
(sha256 `8673d30e25a1dcd36900aded4b60540c7ccbc2be0ee5354e5f2b29c6c9753498`)
in a new private candidate copied solely from the frozen B07 v1 candidate.
Previous B07 records (report, proposals, ledgers, `execution-ledger.json`) and
the earlier review-fix run `b07-reviewfix-20261007-fzgu78c6` (all `B07R_*`
artifacts) are byte-for-byte unchanged; every artifact here is additive.

## 1. Provenance gate (STEP 1) and frozen-hash recheck (STEP 7)

- Before any copy, the frozen B07 v1 digest was recomputed with the documented
  algorithm (sha256 over `path\0sha256\n`, sorted, excluding caches and the
  named manifest): **221 files /
  `5df259843b26792910de697b2c646fc413c5b936edf3d95d04baf7afa482c179`** —
  matches the recorded value exactly, and the same reimplementation
  cross-checked against the B06 parent digest (208 /
  `ffe774db608ff9d86246458a38265f9baa760b40880e48197e84d887f85d53f4`).
  Baseline record: `evidence/provenance_before_copy.json`
  (`1de1ac39e106ab21c255700dfba7c4a83ad7dd930263cfbf4b3cd707e700b558`),
  verdict `proceed`.
- Frozen input hashes recorded at the gate and re-verified at freeze
  (`evidence/step7_provenance_recheck.json`,
  `1ee98064c5e4010f29ab9552ea0387fece47218a06ed47506e2c8fa9cb090ae9`,
  verdict **`unchanged`**, all nine checks true):
  - `docs/integration/execution/execution-ledger.json` sha256
    `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba` — unchanged;
  - frozen B07 run root: 255 files /
    `82b35360f670f85ebcfe1532ea1ac19fb7af2c368bd38cc3efc7daf83336b21b` — unchanged;
  - frozen B07 docs evidence dir: 5 files /
    `8440917107e60c209a55c006a7baaf4c432eb9b26b41cefa04641930aaf8f990` — unchanged;
  - independent-review dir: 4 files /
    `b42911e7af6d082a9fefeb398238d236031c08a4d2a8d1ee37490d13534df020` — unchanged;
  - earlier review-fix run root `b07-reviewfix-20261007-fzgu78c6`: 614 files /
    `a7d7dbf78a9b7ee330994a0095c61995c6f9e7667562bf63acd0b02c63b69e2b` — unchanged;
  - named files (B07 report `ee6a9ece…`, review `8673d30e…`, results.json
    `34eaa3ad…`, progress ledgers, B07 proposals, v1 manifest `3e7d2a77…`,
    all `B07R_*` docs artifacts) — all unchanged;
  - candidate v2 manifest `920f41c1…9bcec9ce`, tree digest 222 /
    `8171cf1c…38fa48`, on-disk count 223, all three edited-file hashes —
    unchanged.
- The original project was never read, imported, modified, copied from, or
  executed; no upstream contact, no real credentials, no service restarts, no
  CIE resume, no real-data writes, no deployment, no cleanup.

## 2. Findings — status, evidence, module origins

**F1 (High) — identity-known entries must not become verified without quality
evidence — FIXED.**

- Repair: `operations/published.py` — `_ANSWER_VERIFIED` (L202, only
  `source_verified`/`manual_adjudicated`), `_content_complete` (L210),
  `_answers_verified` (L215), `_quality_bucket` (L225): an entry is
  `verified` only when quality fields are present, `content == "complete"`,
  and answer verification is authoritative; an identity-known entry with no
  quality evidence lands in `unknown`, never `verified`.
- Red evidence (frozen v1): `evidence/step2_frozen_red_run1.log`
  (`27b42f385a84250beefe2ea3cea0e54b0c2d2c6a258541db7da0be3ed05cb7c1`,
  20 failed / 8 passed, 1 warning) —
  `test_f1_review_reproduction_partial_unverified_entry_is_not_verified`,
  `test_f1_verified_requires_content_and_answer_verification` FAIL.
- Green evidence (candidate v2): `evidence/step6_candidate_regression_run1.log`
  (`cc810dac389c8b573070b405f2fdaacdb86687c254566dfe55b0ac49a7695879`,
  28 passed, 1 warning) — all F1 tests PASS.
- Guard: `test_f1_identity_rules_still_hold` passes on v1 and v2 (identity
  semantics were already correct; not used to claim the fix).
- Module origin: v2
  `candidates/b07-operations-v2/src/examdata/integration/operations/published.py`
  (sha256 `7fbb4f5dd69d0b94a039e5507f820227701b3cecac8a9190b996ddb7a84468ff`);
  probe `module_origins` (24 entries) all resolve inside the v2 candidate;
  test-side origin proof in `evidence/step6_import_origin.txt`
  (`5872c9c171f695225f080186a4541a7627585d172b5d7165fd1005b387106a0b`),
  v1-side red-run origin in `evidence/step2_origin_check_v1.txt`
  (`a93eb67b7ff048e4a3c1db430dccf0e899876f139a975329c210b67d456fb5b5`).

**F2 (High) — expected/observed conflicts must never produce complete
coverage; counts stay distinct — FIXED.**

- Repair: `operations/published.py` — `_coverage_row` (L240) keeps
  `expected` (manifest-declared, `null` when the manifest declares none) and
  `observed` (= excluded + unknown + partial + verified) distinct;
  `unmet = max(expected − observed, 0)`; `expected_below_published` conflict
  (L270) becomes an explicit problem with **no percentage** and status
  `partial`; `derived_status == complete` only when not in conflict and
  `observed == expected > 0` with zero partial/unknown entries;
  `build_published` (L312); `entries = list(entries)` (L318) so one-shot
  iterables are consumed exactly once.
- Red evidence: same log — five F2 tests plus
  `test_multi_scope_processing_accepts_supported_iterables[generator]` FAIL
  (`test_f2_unknown_denominator_never_claims_completion` passes before and
  after as a guard). Semantics v1→v2 (pin diff, `evidence/step6_pindiff_v1.json`
  `3566efa1594d8ecf5af4b6e105c7314107893bb3974a9b9308272fafa2012ad9` /
  `step6_pindiff_v2.json`
  `d8726237757b681ad6307b7e829983c82bb437bcbe256e4729a445ee2eeb2dba`):
  v1 `verified` 4/8/1 → v2 `verified` 0/0/0; new axes `identity_complete`
  5/8/2, `content_complete` 0/0/0, `answers_verified` 0/0/0; `expected`
  null → 7/8/4; `missing` 2/0/2 → 0/0/0 with `unmet` 2/0/2; CIE percentage
  71.43 → 0.0, IELTS 100.0 `complete` → 0.0 `partial`, Edexcel 50.0 → 0.0,
  TOEFL `None`/`unknown` unchanged. v2 rows: CIE observed 5 / expected 7 /
  unmet 2 / unknown 4 / partial 1; IELTS observed 8 = expected, unknown 8,
  partial; Edexcel observed 2 / expected 4 / excluded 1 / unmet 2 / unknown 1.
- Green evidence: candidate regression log — all F2 + multi-scope tests PASS.
- Contract: the pre-existing `coverage/1` response contract is preserved
  additively and validated by
  `test_published_rows_keep_contract_fields_and_validate` (passes on v1 and
  v2); no key was removed or renamed. This response-contract extension is
  recorded in `evidence/step3_f12_semantics_note.md`
  (`f8c20e8cf8fe1be24fad0e509f716bf125395440061a5a2e59bbf61fa44d2262`) and
  the private consumers/tests in this candidate were adjusted in the same
  step — nothing was silently altered.
- Module origin: same v2 `published.py`.

**F3 (Medium) — scan limits must bound discovery and attempted work, not just
successful observations — FIXED.**

- Repair: `operations/jobs.py` budgets (L58–62) `MAX_SCAN_FILES=256`,
  `MAX_CHECKPOINT_BYTES=4 MiB`, `MAX_SCAN_ENTRIES=4096`,
  `MAX_SKIPPED_RESULTS=64`, `MAX_READ_BYTES=32 MiB`; `ScanResult` (L107) with
  `exhausted` signal (L126); `_retain_skip` (L133); `scan_checkpoint_root`
  (L148) counts skipped/unreadable files as *attempted*; exhaustion returns
  `truncated=True`. `operations/checkpoints.py` adds the bounded lazy walker
  `_CheckpointPathWalker` (L315, `iter_checkpoint_paths` L395) that never
  materializes the whole tree and orders deterministically by sorted path
  (proven equal to `sorted(rglob)` in tests), plus `read_checkpoint_bounded`
  (L202), `CheckpointTooLargeError` (L51), `DEFAULT_MAX_CHECKPOINT_BYTES`
  (L64). Directory-entry, attempted-file, retained-result and byte budgets all
  have explicit exhaustion signals.
- Red evidence: eight F3 tests FAIL on v1 (attempt budget, exact/over limit,
  directory-entry discovery budget, retained-result budget, read-byte budget,
  bounded read of an oversized file, unreadable file as attempted,
  deterministic lazy order);
  `test_f3_oversized_file_is_skipped_and_counts_are_reported` passes on v1
  as a guard. Green: all PASS on v2.
- Tests use portable synthetic trees only (no protected directories, no
  wall-clock thresholds to establish boundedness). Residual limit documented:
  `evidence/step4_f3_scan_budget_note.md`
  (`e86021ea424abb0f46415cef62f1c5a914194b56883eeeda3b53179f9cf9235d`) —
  a single directory's listing is still sorted in memory (bounded per
  directory; the tree is never materialized).
- Module origin: v2 `jobs.py`
  (`3b1935c2bba35af565a4307e26b2c3443268bc677fb88ed6b3aa3f565032e2eb`) and
  `checkpoints.py`
  (`2e888c6fb36f9655b37a656c8df805808a507801f1d8e31d36b666ba1dd9d279`).

**F4 (Medium) — public sanitization must cover dynamic mapping keys via
explicit public projection — FIXED.**

- Repair: `operations/jobs.py` `sanitize_tree` (L78) now projects every
  mapping through explicit key handling (secret-bearing keys and path-shaped
  keys redacted, entries preserved, collision-safe suffixes so a redacted key
  never overwrites an existing one, fixed schema keys untouched);
  `JobView.to_public` (L295) uses it; projection path `api/dataset.py`
  `to_public` (L451) / `operations_view` (L470).
- Red evidence: `test_f4_review_reproduction_secret_and_path_keys_are_redacted`,
  `test_f4_collision_suffix_never_overwrites_an_existing_key`,
  `test_f4_operations_projection_redacts_keys`,
  `test_f4_http_routes_redact_keys` FAIL on v1; the last one exercises the
  **real candidate public projection and HTTP handler** with synthetic local
  fixtures (FastAPI testclient via `api/app.py` `create_app` + `api/links.py`
  `spec_for`, routes `/coverage` and `/jobs/{id}`), not a helper-only path.
  Guards `test_f4_nested_lists_keep_record_counts` and
  `test_f4_fixed_schema_keys_and_counts_survive` pass on v1 and v2. Green:
  all PASS on v2.
- Residual detail: `evidence/step5_f4_sanitize_note.md`
  (`1d864a9f1423badc7c0a1c40ba2c25b850b6d03807f03bcdba0a90c9c915f4f1`).
- Module origin: v2 `jobs.py`.

## 3. Candidate-specific results (STEP 6) — separate from base suite

| Check | Label | Result | Evidence |
|-------|-------|--------|----------|
| 28-test candidate regression (13 published incl. 3 multi-scope params + 9 scan + 6 sanitize) | candidate regression | **28 passed, 1 warning, exit 0** | `evidence/step6_candidate_regression_run1.log` (`cc810dac…`) |
| Same tests on frozen v1 (reproductions) | candidate regression (frozen baseline) | **20 failed / 8 passed, 1 warning** (preserved red) | `evidence/step2_frozen_red_run1.log` (`27b42f38…`) |
| Import-origin assertions | candidate regression | all tested modules resolve inside v2 | `evidence/step6_import_origin.txt` (`5872c9c1…`) |
| Standalone route probe (adapted copy) | candidate validation | **174 checks, 173 ok, 1 failed** — `J_published_statuses_pinned` (expected F1/F2 consequence; pinned v1 values) | `evidence/step6_probe_run1.json` (`44dde29c…`); extract `_extract.txt` (`8ed44728…`) |
| Validator, 3 working directories | candidate validation | exit 1; verdict `b07_rehearsal_not_valid`; 3× finding `B07-PROBE-FAIL` each listing only `J_published_statuses_pinned`; 9 cross-cwd identity checks true (discovery/stability/seam/operations/frontend/projection/cross_stack/ledger/digest) | `evidence/step6_validate_run.txt` (`68fdec65…`); 5 files under `docs/integration/execution/evidence/B07/b07-reviewfix-20261007-774e4dad/`: `B07_LAYOUT_VALIDATION.json` (`e90a2bb8…`), `b07_validation_run.txt` (`36627097…`), `probe_cwd1.json` (`978769d6…`), `probe_cwd2.json` (`7b4e8ea7…`), `probe_cwd3.json` (`739049ad…`) |
| Candidate import smoke | candidate validation | exit 0, `structural_ok: true`, counts 7/7/5/2/7/4 | `evidence/step6_smoke_import.json` (`fb33d1c8…`) |
| Cross-stack Node checks | **synthetic** | 18/18 ok (`H_cross_stack_all_18_pass`), node v24.19.0 | inside `step6_probe_run1.json` (H_*) |
| Staged Node suite | **synthetic** | `F_node_test_suite_41_passed` 41/41, exit 0; `F_node_check_parses_new_frontend_js` exit 0 | inside `step6_probe_run1.json` (F_*) |
| Layout/build validation | candidate validation | layout JSON emitted; the frozen build script `b07_build_candidate.py` was **not executed** (it rewrites frozen v1 in place) — build equivalence proven by v1 digest recompute + tree diff + carried-verbatim projection + v2 manifest digest recompute instead | `evidence/step6_validation_note.md` (`65805dcf…`); `step6_v1_v2_tree_diff.txt` (`6014adca…`); `step6_v2_carried_verbatim_matched.json` (`15d8901a…`) |
| Adapted private tools | record | 126-line unified diff; assertions preserved, only run identity adapted | `evidence/step6_adapted_tools.diff` (`622d235f…`) |

Warnings: only `StarletteDeprecationWarning` (httpx/starlette testclient,
environmental; recorded, not suppressed). Skipped: none within the candidate
suite. Cache hygiene after all runs (`evidence/step6_cache_check.txt`,
`d3ce3641…`): no `__pycache__`/`.pytest_cache` in the frozen B07 root or this
run root; the 24 pre-existing caches under `runtime/b03..b05` predate this run
and were left untouched; frozen v1 digest re-verified 221 / `5df25984…`.

## 4. Base staging suite (separate label — not candidate coverage)

`integration-staging` base staging suite: **887 passed, 1 warning, exit 0,
52.52 s** — evidence `evidence/step6_base_staging_suite.txt`
(`44a8fb2a91ccb42177a4910d31a7a96a9eecd8becb803ffd9389a49dd73caed3`).
Labeled **base staging regression**; it does not substitute for the
candidate-specific coverage in §3.

## 5. not_run real-world acceptance items and required authorizations

All fifteen items are `not_run` exactly as recorded by the probe
(`evidence/step6_probe_run1.json`, `not_run` section; extract
`evidence/step6_probe_run1_extract.txt`). Required authorization = the named
gate in `execution-ledger.json` (all closed):

| # | not_run item | Required authorization |
|---|--------------|------------------------|
| 1 | Real merge into the original project | `original_paths_released` |
| 2 | Real active-owner integration (materials, syllabuses, timetables) | no owner release exists; would require `original_paths_released` |
| 3 | Real baseline verification against the actual legacy application | `original_paths_released` |
| 4 | Real Node component execution (fake-cli.mjs on the Node runtime) | `original_paths_released` |
| 5 | Real Node/source validation against the original project | `original_paths_released` |
| 6 | Real database schema / data migration | `real_data_write_authorized` |
| 7 | Live service / upstream provider calls | `upstream_requests_authorized` |
| 8 | Cutover of the existing service | `existing_service_cutover_authorized` |
| 9 | Deployment to any target | `remote_deployment_authorized` |
| 10 | Cleanup of the original project | `original_cleanup_authorized` |
| 11 | Credential usage of any kind | none required by design (no real credential used/read/fabricated; only fixture-labelled synthetic values exist) |
| 12 | Real frontend cutover | `existing_service_cutover_authorized` |
| 13 | Real source-provider fetching from the frontend process | `upstream_requests_authorized` |
| 14 | Real job-service interaction (resume/cancel/enqueue) | none exists and none needed (view is read-only by construction) |
| 15 | Writes of any kind to an operations root | `original_paths_released` |

Additionally `cie_resume_authorized` remains closed and is not requested
(CIE was not resumed).

## 6. Artifacts and hashes

Full enumeration: `reports/B07R2_EVIDENCE_INDEX.json` (its sha256 is pinned in
`evidence/step7_freeze_hashes.txt` together with `logs/commands.log`).
Principal artifacts:

| Artifact | sha256 |
|----------|--------|
| Candidate manifest `candidates/b07-operations-v2/B07R2_CANDIDATE_MANIFEST.json` | `920f41c1b98199b087a4a8c7dea918c23d0f8144afdfebb87bfb2b2e9bcec9ce` |
| `reports/B07R2_DIFF_FROM_V1.md` | `34ef1d0ec5cc8e309cf740caeb819882c5fb74d18d2e028e480d658c3bcaa494` |
| `reports/B07R2_DIFF_FROM_V1.patch` | `cd97823c5ee8c669076499090f5cfd8935e2c3d1dbc272cabe14e235c865319d` |
| `reports/B07R2_DIFF_FROM_V1.stat.txt` | `bdfd231d7aa1470b4f61ae32344c0dcb680a3161ba606094db316bba3a4f2875` |
| `reports/B07R2_FINDINGS_TO_TESTS_MATRIX.md` | `45d1c824aaddf1aafa07516440772477f79c5afb079e25789b00a6daada7e160` |
| `reports/B07R2_MERGE_PROPOSAL.json` / `.md` | `1b4513189d63b78d6c28e639c74d12ad371ae1d4b8c09c5203d37df44ade0c0c` / `82ed27fbf3271a6034448b18074375c473504e3c655897639fc71ef7a982d06c` |
| `reports/B07R2_ROLLBACK_PROPOSAL.json` / `.md` | `186b91198728c06811acf95944a9434a57c626ce6578b278949d76b16ed731d6` / `f151a154c2b358f99ee46fac472dfdeaba3dbb65358cc44132dc3486888cc2ca` |
| `evidence/step7_provenance_recheck.json` | `1ee98064c5e4010f29ab9552ea0387fece47218a06ed47506e2c8fa9cb090ae9` |
| Red reproduction log `evidence/step2_frozen_red_run1.log` | `27b42f385a84250beefe2ea3cea0e54b0c2d2c6a258541db7da0be3ed05cb7c1` |
| Green candidate log `evidence/step6_candidate_regression_run1.log` | `cc810dac389c8b573070b405f2fdaacdb86687c254566dfe55b0ac49a7695879` |
| Semantics/budget/sanitize notes (step3/4/5) | `f8c20e8c…` / `e86021ea…` / `1d864a9f…` |
| `evidence/step6_validation_note.md` / `step6_hashes.txt` | `65805dcf7bed5b6cf83b77997c3fd980fcddb28866b5c6f279cd5e3e94000e56` / `2e199b850e6ec43c67c1ac767546b6400480fc3409bdc02132389a76962f6bda` |
| Adapted-tools diff `evidence/step6_adapted_tools.diff` | `622d235fedc617fb4b388717195bc4e8dc16db225f2afbc434895108f059fbdd` |
| Tests `tests/` | `b07r2_common.py` `afe64901…`, `pytest.ini` `aaabed12…`, `test_b07r2_published_semantics.py` `766c29ac…`, `test_b07r2_sanitize_keys.py` `a86e2c8f…`, `test_b07r2_scan_budgets.py` `dc72dc93…` |
| Adapted tools `b07_route_probe.py` / `b07_validate.py` / `b07_smoke_import.py` / `tools/b07r2_pin_diff.py` / `tools/b07_cross_stack.mjs` | `82bc7a6b…` / `30fa2fa0…` / `8900f492…` / `b8c80fa4…` / `7aff2774…` (cross-stack verbatim) |
| Baseline provenance `evidence/provenance_before_copy.json` | `1de1ac39e106ab21c255700dfba7c4a83ad7dd930263cfbf4b3cd707e700b558` |

Copies of this report, the diff summary, the matrix, both proposals, and the
evidence index are placed additively under `docs/integration/execution/`
(names `B07R2_*`); nothing existing was modified. `logs/commands.log` is
rebuilt from the append-only session wire at freeze; per the log's own
documented convention, the rebuild command and the freeze-hash write are
outside its own snapshot — their outputs are in the wire.

## 7. Residual defects and caveats (nothing is being declared complete)

1. **`J_published_statuses_pinned` is permanently red on v2 by design.** It
   pins the old (defective) coverage values; it may be re-pinned only through
   an explicitly authorized review change, never silently. The validator
   therefore returns `b07_rehearsal_not_valid` with `B07-PROBE-FAIL` — the
   honest signal that the frozen probe still checks the old contract.
2. **The frozen build script was not executed** (it rebuilds v1 in place);
   build equivalence was proven by digest, tree diff, carried-verbatim
   projection, and manifest recompute instead. This substitution is
   documented, not silent.
3. **Scan-budget residual:** one directory's listing is still sorted in
   memory (bounded per directory; the tree is never materialized).
4. **Test-environment note:** the pytest runs set `PYTHONPATH` to the
   candidate's `src` (matching the frozen run's own pattern) and assert
   origin via `B07R2_EXPECT_CANDIDATE_ROOT`; `EXAMDATA_INTEGRATION_STAGING_ROOT`
   was unset; basetemps lived inside this run root.
5. **Warnings:** only the environmental StarletteDeprecationWarning.
6. **No real-world acceptance item ran** (§5); nothing here says the
   integration is complete, merged, deployed, or safe for real data.
7. Previous B07 completion records, the execution ledger, and the earlier
   `B07R_*` review-fix artifacts are unchanged; this proposal is additive and
   private.

## 8. Stop statement

The private proposal is ready for review: candidate `b07-operations-v2`
(digest-verified child of B07 v1), regression evidence red-on-v1/green-on-v2,
candidate manifest, precise diff, merge/rollback proposals, evidence index,
and findings-to-tests matrix. F1–F4 are repaired in the private candidate.
This run stops here — no merge, no deployment, no gate opened.
