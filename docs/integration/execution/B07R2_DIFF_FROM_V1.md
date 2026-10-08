# B07R2 — precise diff from B07 v1

Run: `b07-reviewfix-20261007-774e4dad` (second private review-fix run).
Status: private, unmerged, undeployed; all seven gates closed. This document
describes the exact delta between the frozen B07 candidate (v1) and the
review-fix candidate (v2) and names the artifacts that prove it.

## 1. Delta summary

v2 adds nothing and removes nothing relative to v1 except:

- **3 files rewritten in place** (byte-precise replacements):
  `src/examdata/integration/operations/published.py` (F1, F2),
  `src/examdata/integration/operations/jobs.py` (F3, F4),
  `src/examdata/integration/operations/checkpoints.py` (F3);
- **1 file added**: `B07R2_CANDIDATE_MANIFEST.json` (this run's manifest).
- Every other file is carried byte-for-byte, including the parent's own
  `B07_CANDIDATE_MANIFEST.json` (sha256 unchanged
  `3e7d2a7721b04a1663400ca335ae213c75e7696dbb60c656b938f2c32d061784`).
- Carried-verbatim projection (218 files, excluding both manifests and the
  three rewritten modules): byte-identical on both sides —
  v1 `8d1ab7071a505ae3511651639d1ca8273ef34a844583ffd9391d4323ae6da14a`
  = v2 `8d1ab7071a505ae3511651639d1ca8273ef34a844583ffd9391d4323ae6da14a`.

## 2. Per-file hashes and diffstat

| File | v1 sha256 (parent) | v2 sha256 (written) | +/- | lines v1→v2 |
|------|--------------------|---------------------|-----|-------------|
| `src/examdata/integration/operations/published.py` | `54522b9e669c57b9a21564a98d1075f02664611f310cc72868cab793f82a925a` | `7fbb4f5dd69d0b94a039e5507f820227701b3cecac8a9190b996ddb7a84468ff` | +117/−32 | 310 → 395 |
| `src/examdata/integration/operations/jobs.py` | `916ae7b195902856de2521661aaae4bf0dcd940592bf19a315536f9134427839` | `3b1935c2bba35af565a4307e26b2c3443268bc677fb88ed6b3aa3f565032e2eb` | +138/−35 | 348 → 451 |
| `src/examdata/integration/operations/checkpoints.py` | `1f49dde5e36ed3aaa8b82af5b83b6fd72821d67808addc34047b3b4db580805b` | `2e888c6fb36f9655b37a656c8df805808a507801f1d8e31d36b666ba1dd9d279` | +136/−14 | 303 → 425 |
| `B07R2_CANDIDATE_MANIFEST.json` (added; excluded from v2 tree digest) | — | `920f41c1b98199b087a4a8c7dea918c23d0f8144afdfebb87bfb2b2e9bcec9ce` | +85 | 0 → 85 |

Totals: 4 files changed, **476 insertions, 81 deletions** (`git diff
--no-index --stat`, recorded in `reports/B07R2_DIFF_FROM_V1.stat.txt`).

## 3. Tree digests

| Projection | v1 | v2 |
|------------|----|----|
| Tree excluding the run's own manifest | 221 files `5df259843b26792910de697b2c646fc413c5b936edf3d95d04baf7afa482c179` | 222 files `8171cf1c67c7891fc4c3354a482fb65600886aa0b5b88f9a1a546333c738fa48` (excl. `B07R2_CANDIDATE_MANIFEST.json`) |
| Tree including both manifests | 222 files `8dad753d0697dc708b54658aa4492e45954200c51a3cebd58c4ef3161dbf80bf` | 223 files on disk |
| Carried-verbatim projection (218 files) | `8d1ab7071a505ae3511651639d1ca8273ef34a844583ffd9391d4323ae6da14a` | `8d1ab7071a505ae3511651639d1ca8273ef34a844583ffd9391d4323ae6da14a` |

Digest rule (both runs): sha256 over `path\0sha256\n` per file, sorted by
path, excluding `__pycache__`/`.pytest_cache` and the named manifest.

## 4. Change semantics (mapped to findings)

- `published.py` — **F1**: identity-known entries no longer become verified
  without quality evidence; verification requires complete content
  (`_content_complete`, L210) and an answer-verification value in
  `_ANSWER_VERIFIED` (L202) on the same entry (`_answers_verified`, L215);
  `_quality_bucket` (L225) classifies quality evidence and never promotes
  unknown identity or absent evidence. **F2**: coverage rows keep expected and
  observed counts distinct (`_coverage_row`, L240); an
  `expected_below_published` conflict (L270) renders as an explicit problem
  with no percentage and can never read as complete; completion requires
  `observed == expected > 0` with no partial/unknown entries; an unknown
  denominator reports `denominator_known False` with no percentage.
  `build_published` (L312) consumes any iterable exactly once
  (`entries = list(entries)`, L318) so multi-scope manifests work with lists,
  tuples and generators.
- `jobs.py` — **F3**: scan budgets bound discovery as well as reading
  (`MAX_SCAN_FILES=256`, `MAX_CHECKPOINT_BYTES=4 MiB`, `MAX_SCAN_ENTRIES=4096`,
  `MAX_SKIPPED_RESULTS=64`, `MAX_READ_BYTES=32 MiB`, L58–62);
  `scan_checkpoint_root` (L148) counts every attempt against the budget and
  reports exhaustion signals in `ScanResult.exhausted` (L126); skipped
  results are capped by `_retain_skip` (L133). **F4**: `sanitize_tree` (L78)
  performs explicit public projection that also sanitizes dynamic mapping
  keys (collision suffixes never overwrite existing keys).
- `checkpoints.py` — **F3**: bounded lazy walker `_CheckpointPathWalk` (L315),
  `iter_checkpoint_paths` (L395), bounded reader `read_checkpoint_bounded`
  (L202) and `CheckpointTooLargeError` (L51); `DEFAULT_MAX_CHECKPOINT_BYTES`
  (L64).

## 5. Evidence artifacts for this diff

| Artifact | Path | sha256 |
|----------|------|--------|
| Unified diff of the 3 rewritten files | `reports/B07R2_DIFF_FROM_V1.patch` | `cd97823c5ee8c669076499090f5cfd8935e2c3d1dbc272cabe14e235c865319d` |
| numstat + stat | `reports/B07R2_DIFF_FROM_V1.stat.txt` | `bdfd231d7aa1470b4f61ae32344c0dcb680a3161ba606094db316bba3a4f2875` |
| v1↔v2 file-level tree diff checklist | `evidence/step6_v1_v2_tree_diff.txt` | `6014adcab9854f95bdf375aa218d0c898299c193831702e9316dbe3c2910f15c` |
| Manifest input digests (v1/v2/carried/edited) | `evidence/step6_v2_manifest_inputs.json` | `792f8aa363732e39edb5567b2d3da63cd327d89274bfe06189a29b7881c37166` |
| Carried-verbatim match record | `evidence/step6_v2_carried_verbatim_matched.json` | `15d8901a3784f6ef0901dc1308ab1901d289c8505c7d249c79ff52a86234d190` |

Method: `diff -u` per file (labels rewritten to `a/…` / `b/…`), plus
`git diff --no-index --numstat/--stat` between the two candidate roots
(`-c core.autocrlf=false` to keep the stat artifact free of git noise).
Both candidate roots are private trees under `integration-staging/**`; the
original project was not read or touched.
