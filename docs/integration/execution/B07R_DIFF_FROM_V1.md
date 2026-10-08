# B07R — precise diff from B07 v1

Run: `b07-reviewfix-20261007-fzgu78c6`. Status: private, unmerged, undeployed;
all seven gates closed. This document describes the exact delta between the
frozen B07 candidate (v1) and the review-fix candidate (v2) and names the
artifacts that prove it.

## 1. Delta summary

v2 adds nothing and removes nothing relative to v1 except:

- **3 files rewritten in place** (byte-precise replacements):
  `src/examdata/integration/operations/published.py` (F1, F2),
  `src/examdata/integration/operations/jobs.py` (F3, F4),
  `src/examdata/integration/operations/checkpoints.py` (F3);
- **1 file added**: `B07R_CANDIDATE_MANIFEST.json` (this run's manifest).
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
| `src/examdata/integration/operations/published.py` | `54522b9e669c57b9a21564a98d1075f02664611f310cc72868cab793f82a925a` | `af32610da2b9b86fa36eaeda2ba73c0dc79c6d77b303025ef5c9a19621af2574` | +136/−39 | 310 → 407 |
| `src/examdata/integration/operations/jobs.py` | `916ae7b195902856de2521661aaae4bf0dcd940592bf19a315536f9134427839` | `d0405b8ba71d13fcefc86b7f339f2e4a6056d3b8c9a0c456a47cc231af55cd15` | +104/−22 | 348 → 430 |
| `src/examdata/integration/operations/checkpoints.py` | `1f49dde5e36ed3aaa8b82af5b83b6fd72821d67808addc34047b3b4db580805b` | `0a439d26049c6d6b4c791b53a29ea02470a03bcf7d641802fede2f28ecdcb6b4` | +114/−14 | 303 → 403 |
| `B07R_CANDIDATE_MANIFEST.json` (added; excluded from v2 tree digest) | — | `0a0052cd3dd433b9d675d88728acac935af0fd83660075e5a86366ea1662ea54` | +85 | 0 → 85 |

Totals: 4 files changed, **439 insertions, 75 deletions** (`git diff
--no-index --stat`, recorded in `reports/B07R_DIFF_FROM_V1.stat.txt`).

## 3. Tree digests

| Projection | v1 | v2 |
|------------|----|----|
| Tree excluding the run's own manifest | 221 files `5df259843b26792910de697b2c646fc413c5b936edf3d95d04baf7afa482c179` | 222 files `f0f9a3c49db995ad5934907763a4664576ee07f3280c3586d9a8670c991a022c` (excl. `B07R_CANDIDATE_MANIFEST.json`) |
| Tree including both manifests | 222 files `8dad753d0697dc708b54658aa4492e45954200c51a3cebd58c4ef3161dbf80bf` | 223 files on disk |
| Carried-verbatim projection (218 files) | `8d1ab7071a505ae3511651639d1ca8273ef34a844583ffd9391d4323ae6da14a` | `8d1ab7071a505ae3511651639d1ca8273ef34a844583ffd9391d4323ae6da14a` |

Digest rule (both runs): sha256 over `path\0sha256\n` per file, sorted by
path, excluding `__pycache__`/`.pytest_cache` and the named manifest.

## 4. Change semantics (mapped to findings)

- `published.py` — **F1**: identity-known entries no longer become verified
  without quality evidence; verification requires `content == "complete"` and
  an answer-verification value in `_ANSWER_VERIFIED` (`_quality_bucket`, L237;
  `build_published` L319). **F2**: coverage rows keep expected and observed
  counts distinct; `expected_below_published` conflicts render as an explicit
  problem with no percentage and can never be complete; completion requires
  `observed == expected > 0` with no partial/unknown entries
  (`_coverage_row` L254).
- `jobs.py` — **F3**: scan budgets bound discovery and attempted work
  (`MAX_SCAN_FILES=256`, `MAX_SCAN_ENTRIES=4096`, `MAX_SCAN_SKIPPED=64`,
  `MAX_CHECKPOINT_BYTES=4 MiB`, `MAX_SCAN_READ_BYTES=32 MiB`, L60-64;
  `scan_checkpoint_root` L131) with explicit exhaustion signals.
  **F4**: `sanitize_tree` (L80) performs explicit public projection that also
  sanitizes dynamic mapping keys.
- `checkpoints.py` — **F3**: bounded lazy walker `_CheckpointPathWalk` (L301),
  `iter_checkpoint_paths` (L372), bounded reader `read_checkpoint_bounded`
  (L190) and `CheckpointTooLargeError` (L51).

## 5. Evidence artifacts for this diff

| Artifact | Path | sha256 |
|----------|------|--------|
| Unified diff of the 3 rewritten files | `reports/B07R_DIFF_FROM_V1.patch` | `55b2a07d06d5c8bcbf128d993b53e3ae494916073bac80ecff09aca07c7c4089` |
| numstat + stat | `reports/B07R_DIFF_FROM_V1.stat.txt` | `222267bef35378a92426527c8bf03d7d56fd79e3f6af678f065bfebcc15002af` |
| v1↔v2 file-level tree diff checklist | `evidence/step6_v1_v2_tree_diff.txt` | `927c866fff39306515da0d067e317cda61141f3ab46e73de15c4bbed5a950522` |
| Manifest input digests (v1/v2/carried/edited) | `evidence/step6_v2_manifest_inputs.json` | `f2cb61655e8bbc3637ed2cbe859d2d5dc61222b965b8cefa11984fb07194d9d4` |
| Carried-verbatim match record | `evidence/step6_v2_carried_verbatim_matched.json` | `b2b0cd1d3c2428f51cc5a35ce363305e1cfbb1b3a7d666dcb421a6dfc0c5732e` |

Method: `diff -u` per file (labels rewritten to `a/…` / `b/…`), plus
`git diff --no-index --numstat/--stat` between the two candidate roots
(`-c core.autocrlf=false` to keep the stat artifact free of git noise).
Both candidate roots are private trees under `integration-staging/**`; the
original project was not read or touched.
