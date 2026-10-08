# B07R — FINAL REPORT (private review-fix run)

Run: `b07-reviewfix-20261007-fzgu78c6` · Date: 2026-10-07 ·
Status: **private, unmerged, undeployed — proposal only, ready for review,
not merged and not deployed.** All seven gates remain closed. No claim of
deployment, live cutover, or real-data acceptance is made anywhere in this
report.

This report repairs F1–F4 from
`docs/integration/execution/B07_INDEPENDENT_REVIEW_2026-10-07.md`
(sha256 `8673d30e25a1dcd36900aded4b60540c7ccbc2be0ee5354e5f2b29c6c9753498`)
in a new private candidate copied solely from the frozen B07 v1 candidate.
Previous B07 records (report, proposals, ledgers, execution-ledger.json) are
byte-for-byte unchanged; every artifact here is additive.

## 1. Provenance gate (STEP 1) and frozen-hash recheck (STEP 7)

- Before any copy, the frozen B07 v1 digest was recomputed with the documented
  algorithm (sha256 over `path\0sha256\n`, sorted, excluding caches and the
  named manifest): **221 files /
  `5df259843b26792910de697b2c646fc413c5b936edf3d95d04baf7afa482c179`** —
  matches the recorded value exactly, and the same reimplementation
  cross-checked against the B06 parent digest (208 / `ffe774db…53f4`).
  Baseline record: `evidence/provenance_before_copy.json`
  (`f5bad53881bb990df18ea417ed2473671dd89614cd1fa602ebf14066d156246c`).
- Frozen input hashes recorded at the gate and re-verified at freeze
  (`evidence/step7_provenance_recheck.json`,
  `217b53b896342a1105dca8441f0f934ec23c52947c3f88a8aa0386bb7160aa8c`,
  verdict **`unchanged`**, all nine checks true; stdout
  `4bcf7b02919a10d19ea9a55583a3be459a10174984ae9e923126f7134e077025`,
  stderr empty):
  - `docs/integration/execution/execution-ledger.json` sha256
    `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba` — unchanged;
  - frozen B07 run root: 255 files /
    `82b35360f670f85ebcfe1532ea1ac19fb7af2c368bd38cc3efc7daf83336b21b` — unchanged;
  - frozen B07 docs evidence dir: 5 files /
    `8440917107e60c209a55c006a7baaf4c432eb9b26b41cefa04641930aaf8f990` — unchanged;
  - independent-review dir: 4 files /
    `b42911e7af6d082a9fefeb398238d236031c08a4d2a8d1ee37490d13534df020` — unchanged;
  - named files (report `ee6a9ece…`, review `8673d30e…`, results.json
    `34eaa3ad…`, progress ledgers, B07 proposals, v1 manifest `3e7d2a77…`) —
    all unchanged;
  - candidate v2 manifest `0a0052cd…1662ea54`, tree digest 222 /
    `f0f9a3c4…a022c`, all three edited-file hashes — unchanged.
- The original project was never read, imported, modified, copied from, or
  executed; no upstream contact, no real credentials, no service restarts, no
  CIE resume, no real-data writes, no deployment, no cleanup.

## 2. Findings — status, evidence, module origins

**F1 (High) — identity-known entries must not become verified without quality
evidence — FIXED.**

- Repair: `operations/published.py` `_quality_bucket` (L237) and
  `build_published` (L319): verification now additionally requires quality
  fields to be present and `content == "complete"` and
  `answer_verification ∈ _ANSWER_VERIFIED` (L210); an identity-known entry
  with no quality evidence lands in `unknown`, never `verified`.
- Red evidence (frozen v1): `evidence/step2_frozen_red_run2.log`
  (`747e8255a4dcf51cbf7efbc683e853c3864488810fd2d4e48cacc19790c465d7`,
  18 failed / 8 passed) — `test_f1_identity_known_unverified_entry_is_not_verified`,
  `test_f1_verified_requires_content_and_answer_verification` FAIL.
- Green evidence (candidate v2): `evidence/step6_candidate_regression_run1.log`
  (`ee4433e8491286d4500527369b287a9b59ce36556283b442a6d4b05d9a554358`,
  26 passed) — all F1 tests PASS.
- Module origin: v2 `candidates/b07-operations-v2/src/examdata/integration/operations/published.py`
  (sha256 `af32610d…21af2574`); probe `module_origins` (24 entries) all resolve
  inside the v2 candidate; test-side origin proof in
  `evidence/step6_import_origin.txt` (`7b5a88995123af9b372531156762f7569be463856d20ec84f95f93322ac2a824`).

**F2 (High) — expected/observed conflicts must never produce complete
coverage; counts stay distinct — FIXED.**

- Repair: `_coverage_row` (L254) keeps `expected` and `observed` distinct
  (`observed` = actual published count = excluded + unknown + partial +
  verified; `unmet = max(expected−observed, 0)`), renders an
  `expected_below_published` conflict as an explicit problem with **no
  percentage**, and completes only when `observed == expected > 0` with zero
  partial/unknown entries. Classification order (L352-368): exclusion >
  manifest partial > identity-unknown > quality bucket.
- Red evidence: same log — five F2 tests plus
  `test_multi_scope_processing_accepts_supported_iterables[generator]` FAIL
  (`test_f2_unknown_denominator_never_claims_completion` passes before and
  after as a guard). Published percentages v1→v2: cie 71.43→0.0 (observed 7→5,
  missing 2→0, verified 4→0, unknown 0→4, expected 7/unmet 2), ielts 100.0
  `complete`→0.0 `partial` (verified 8→0, unknown 0→8), edx 50.0→0.0 (observed
  4→2, excluded 1 unchanged, verified 1→0), toefl `None`/`unknown` unchanged.
  Recorded: `evidence/step6_pindiff_v1.json`
  (`3566efa1594d8ecf5af4b6e105c7314107893bb3974a9b9308272fafa2012ad9`) and
  `step6_pindiff_v2.json`
  (`3d3fbcaddfbe34714bfe164196ff27e8ecb875a709e7cbe31922670fff909f40`).
- Green evidence: candidate regression log — all F2 + multi-scope tests PASS.
- Module origin: same `published.py` (v2). The pre-existing `coverage/1`
  response contract is preserved and validated by
  `test_published_rows_keep_contract_fields_and_validate` (passes on v1 and
  v2); the only semantic change is what the counters *mean* and that a
  conflict can no longer read as complete — this proposed response-contract
  change is recorded here and in
  `evidence/step3_f12_semantics_note.md`
  (`13ee8412fed2e5e775f98d1257a7f02c79bf2cb71be23f205fbe9b0571f08285`).

**F3 (Medium) — scan limits must bound discovery and attempted work, not just
successful observations — FIXED.**

- Repair: `operations/jobs.py` budgets `MAX_SCAN_FILES=256`,
  `MAX_SCAN_ENTRIES=4096`, `MAX_SCAN_SKIPPED=64`, `MAX_CHECKPOINT_BYTES=4 MiB`,
  `MAX_SCAN_READ_BYTES=32 MiB` (L60-64) with `scan_checkpoint_root` (L131)
  counting skipped/unreadable files as *attempted*, returning additive
  `attempted/entries_seen/bytes_read/exhausted` signals and `truncated=True`
  on exhaustion; `operations/checkpoints.py` adds the bounded lazy walker
  `_CheckpointPathWalk` (L301, `iter_checkpoint_paths` L372) that never
  materializes the whole tree and orders deterministically by sorted path
  (proven equal to `sorted(rglob)` in tests), plus `read_checkpoint_bounded`
  (L190) and `CheckpointTooLargeError` (L51) for oversized files.
- Red evidence: seven F3 tests FAIL on v1 (attempt budget, exact/over limit,
  directory-entry discovery budget, retained-result budget, read-byte budget,
  unreadable file, deterministic lazy order);
  `test_f3_oversized_file_is_skipped_and_counts_are_reported` passes on v1
  as a guard. Green: all PASS on v2.
- Tests use portable synthetic trees only (no protected directories, no
  wall-clock thresholds). Residual limit documented:
  `evidence/step4_f3_scan_budget_note.md`
  (`aec11e670560a73b5f61cf66071f9ac5d9892f9a45da58607270b3435580bc0c`) —
  a single directory's listing is still sorted in memory (bounded per
  directory; the tree is never materialized).
- Module origin: v2 `jobs.py` (`d0405b8b…af55cd15`) and `checkpoints.py`
  (`0a439d26…ecdcb6b4`).

**F4 (Medium) — public sanitization must cover dynamic mapping keys via
explicit public projection — FIXED.**

- Repair: `operations/jobs.py` `sanitize_tree` (L80) now projects every
  mapping through explicit key handling (secret-bearing keys and
  path-shaped keys redacted, entries preserved, fixed schema keys
  untouched); `to_public` (L274) uses it.
- Red evidence: `test_f4_secret_and_path_keys_are_redacted_without_losing_entries`,
  `test_f4_operations_projection_redacts_keys`,
  `test_f4_http_routes_redact_keys` FAIL on v1; the last one exercises the
  **real candidate public projection and HTTP handler** with synthetic local
  fixtures (FastAPI testclient), not a helper-only path. Guards
  `test_f4_nested_lists_keep_record_counts` and
  `test_f4_fixed_schema_keys_and_counts_survive` pass on v1 and v2. Green:
  all PASS on v2.
- Residual detail: `evidence/step5_f4_sanitize_note.md`
  (`acd7f0024d8d54049af1635ee1b6d2a500aca3058683b7456e9f639d1d14d5ca`).
- Module origin: v2 `jobs.py`.

## 3. Candidate-specific results (STEP 6) — separate from base suite

| Check | Label | Result | Evidence |
|-------|-------|--------|----------|
| 26-test candidate regression (13 published incl. 3 multi-scope params + 8 scan + 5 sanitize) | candidate regression | **26 passed, 1 warning, exit 0** | `evidence/step6_candidate_regression_run1.log` (`ee4433e8…`) |
| Import-origin assertions | candidate regression | all tested modules resolve inside v2 | `evidence/step6_import_origin.txt` (`7b5a8899…`) |
| Standalone route probe (adapted copy) | candidate validation | **174 checks, 173 ok, 1 failed** — `J_published_statuses_pinned` (expected F1/F2 consequence) | `evidence/step6_probe_run1.json` (`c6e4a7de4f0dc02ab1732ea2560e9c0caabbb2a255d8ffb76b235827104ae3e7`); extract `_extract.txt` (`065ed6bb…`) |
| Validator, 3 working directories | candidate validation | exit 1; verdict `b07_rehearsal_not_valid`; 3× finding `B07-PROBE-FAIL` each listing only `J_published_statuses_pinned`; cross-cwd identity for discovery/stability/seam/operations/frontend/projection/cross_stack all true; ledger consistency true; tree digest reproducible true | `evidence/step6_validate_run.txt` (`9f290070…`); 5 files under `docs/integration/execution/evidence/B07/b07-reviewfix-20261007-fzgu78c6/`: `B07_LAYOUT_VALIDATION.json` (`9422b4ae…`), `b07_validation_run.txt` (`c40307f1…`), `probe_cwd1.json` (`de95d308…`), `probe_cwd2.json` (`457c8bb5…`), `probe_cwd3.json` (`4cc416c9…`) |
| Candidate import smoke | candidate validation | exit 0, `structural_ok: true`, counts 7/7/5/2/7/4 | `evidence/step6_smoke_import.json` (`4da8bbf2…`) |
| Cross-stack Node checks | **synthetic** | 18 checks ok; node v24.19.0; content triple sha `6596e686…` | inside `step6_probe_run1.json` (H_node) |
| Layout/build validation | candidate validation | layout JSON emitted; the frozen build script was **not executed** (it rebuilds v1 in place) — build equivalence proven by digest + tree diff + carried-verbatim check instead | `evidence/step6_validation_note.md` §3 (`bb3f20714d1c082358bb7104f189e29a16c93fb9945230983d74011d1f98a6bc`) |

Warnings: only `StarletteDeprecationWarning` (httpx/starlette testclient,
environmental; recorded, not suppressed). Skipped: none within the candidate
suite. Cache hygiene after all runs: 0 `__pycache__`/`.pytest_cache`/`*.pyc`
in v1, v2, and the run root; frozen v1 digest re-verified 221 / `5df25984…`.

## 4. Base staging suite (separate label — not candidate coverage)

`integration-staging` base staging suite: **887 passed, 1 warning, exit 0,
47.49s** — evidence `evidence/step6_base_staging_suite.txt`
(`0fb1c156dbc736b1d767de33e0069c9e3a2f1b26cb9368460142cdb350c12dfb`).
Labeled **base staging regression**; it does not substitute for the
candidate-specific coverage in §3.

## 5. not_run real-world acceptance items and required authorizations

All fifteen items are `not_run` exactly as recorded by the probe
(`evidence/step6_probe_run1.json`, `not_run` section). Required authorization
= the named gate in `execution-ledger.json` (all closed):

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

Full enumeration: `reports/B07R_EVIDENCE_INDEX.json` (its sha256 is pinned in
`evidence/step7_freeze_hashes.txt` together with `logs/commands.log`).
Principal artifacts:

| Artifact | sha256 |
|----------|--------|
| Candidate manifest `reports`-sibling: `candidates/b07-operations-v2/B07R_CANDIDATE_MANIFEST.json` | `0a0052cd3dd433b9d675d88728acac935af0fd83660075e5a86366ea1662ea54` |
| `reports/B07R_DIFF_FROM_V1.md` | `d7bb0d81fd7592ccd7432dd573a2e30c867bb6951063eb8a467bc8d83d10105d` |
| `reports/B07R_DIFF_FROM_V1.patch` | `55b2a07d06d5c8bcbf128d993b53e3ae494916073bac80ecff09aca07c7c4089` |
| `reports/B07R_DIFF_FROM_V1.stat.txt` | `222267bef35378a92426527c8bf03d7d56fd79e3f6af678f065bfebcc15002af` |
| `reports/B07R_FINDINGS_TO_TESTS_MATRIX.md` | `05024a7851eadd586b134e364f3aa1d78f0881dd89de7a0acddf863dfb7487ce` |
| `reports/B07R_MERGE_PROPOSAL.json` / `.md` | `0fc4f57cc37d7ae651d02caf10e9f023c7833dd7a96cf962e7ece1aa3d1adc57` / `72e22aeb4afbe67068cb8514a67696323d6b51c5bf7a54f1ab59eb5204a699e2` |
| `reports/B07R_ROLLBACK_PROPOSAL.json` / `.md` | `aa7206b420926c5152d59529a3104683712a9146d57031ccd3ed04271ad803e0` / `eb5ed4f17883d7188ca65dfc7f681f4ca4476708dfb7a39fb41403fa408bf8a3` |
| `evidence/step7_provenance_recheck.json` | `217b53b896342a1105dca8441f0f934ec23c52947c3f88a8aa0386bb7160aa8c` |
| Red reproduction logs `evidence/step2_frozen_red.log` / `step2_frozen_red_run2.log` | `831903697ccf6a1ec9133ce4211406100e16117b2f3c715c0fa954b6666601b2` / `747e8255a4dcf51cbf7efbc683e853c3864488810fd2d4e48cacc19790c465d7` |
| Green step logs `step3_green_run1.log` / `step4_green_run1.log` / `step5_green_run1.log` | `81dae8ce…` / `bfb60eac…` / `535b4c3e…` |
| Semantics/budget/sanitize notes (step3/4/5) | `13ee8412…` / `aec11e67…` / `acd7f002…` |
| Adapted-tools diff `evidence/step6_adapted_tools.diff` | `6a86cea7600b1e2f2fb0df9c7348ca8875bc9824d7cb3952bbfcbbffae28dee5` |
| `evidence/step6_hashes.txt` (step6 hash inventory) | `2632de6a88384480ba68ef8a4b848d2c8be200dfcd00c66d479d23d62bc6f92a` (as of last regeneration) |
| `evidence/step6_validation_note.md` | `bb3f20714d1c082358bb7104f189e29a16c93fb9945230983d74011d1f98a6bc` |
| Tests `tests/` | `b07r_common.py` `d65495fe…`, `test_b07r_published_semantics.py` `17ab7880…`, `test_b07r_scan_budgets.py` `c12d6097…`, `test_b07r_sanitize_keys.py` `a2ec5b97…` |
| Adapted tools `b07_route_probe.py` / `b07_validate.py` / `b07_smoke_import.py` / `tools/b07_cross_stack.mjs` | `d6ef4b59…` / `41cf87e4…` / `1ba74942…` / `7aff2774…` (verbatim) |
| `evidence/step1-baseline provenance_before_copy.json` | `f5bad53881bb990df18ea417ed2473671dd89614cd1fa602ebf14066d156246c` |

Copies of this report, the diff summary, the matrix, both proposals, and the
evidence index are placed additively under `docs/integration/execution/`
(names `B07R_*`); nothing existing was modified. `logs/commands.log` is
rebuilt from the append-only session wire at freeze; per the log's own
documented convention, the rebuild command and the freeze-hash write are
outside its own snapshot — their outputs are in the wire.

## 7. Residual defects and caveats (nothing is being declared complete)

1. **`J_published_statuses_pinned` is permanently red on v2 by design.** It
   pins the old (defective) coverage semantics; it may be re-pinned only
   through an explicitly authorized review change. The validator therefore
   returns `b07_rehearsal_not_valid` with `B07-PROBE-FAIL` — the honest signal
   that the frozen probe still checks the old contract.
2. **The frozen build script was not executed** (it rebuilds v1 in place);
   build equivalence was proven by digest, tree diff, and carried-verbatim
   projection instead. This substitution is documented, not silent.
3. **Scan-budget residual:** one directory's listing is still sorted in
   memory (bounded per directory; the tree is never materialized).
4. **STEP 2 cache incident:** a first attempt wrote `__pycache__` into the
   frozen tree; artifacts were moved out (`evidence/step2_frozen_cache_artifacts/`),
   the tree restored, digest re-verified, and the incident recorded in
   `evidence/step2_frozen_cache_pollution_note.md` (`940ee8ef…`). No source
   bytes changed; all later runs used `PYTHONDONTWRITEBYTECODE=1`.
5. **Test-environment note:** the pytest runs set `PYTHONPATH` to the
   candidate's `src` (matching the frozen run's own pattern) and assert
   origin; `EXAMDATA_INTEGRATION_STAGING_ROOT` was unset.
6. **Warnings:** only the environmental StarletteDeprecationWarning.
7. **No real-world acceptance item ran** (§5); nothing here says the
   integration is complete, merged, deployed, or safe for real data.
8. Previous B07 completion records and the execution ledger are unchanged;
   this proposal is additive and private.

## 8. Stop statement

The private proposal is ready for review: candidate `b07-operations-v2`
(digest-verified child of B07 v1), regression evidence red-on-v1/green-on-v2,
candidate manifest, precise diff, merge/rollback proposals, evidence index,
and findings-to-tests matrix. F1–F4 are repaired in the private candidate.
This run stops here — no merge, no deployment, no gate opened.
