# B01 merge map (A14 -> B01, rationale diff)

- map_version: `merge-map-b01/1`
- status: `proposed_staged_not_merged_not_deployed`
- mode: `PHASE_B_PENDING_RELEASE`
- generated_by: `integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_merge_map.py` at 2026-10-06T21:04:27+08:00
- derived_from: `docs/integration/execution/A14_MERGE_MAP.json` sha256 `29940a0b0582b8b7e8e6fea79692ba849e3d25dd917dfa059d8bbda98fc3654a` (byte-unchanged: True)
- frozen snapshot: `docs/integration/execution/evidence/B00/b00b01-20261006T132400/a_sealed_A14_MERGE_MAP.json`

## Counts

| metric | value |
| --- | --- |
| entries | 247 |
| not_merged | 92 |
| planned_original_edits | 6 |
| active_owner_deferred | 9 |
| entries_reconciled | 0 |
| entries_deferred | 247 |

## F01 correction (the only applied change)

- finding: F01 (PHASE_A_INDEPENDENT_REVIEW_2026-10-06.md): A14 targeted examdata/cli.py with base_exists=false but a 'restore the recorded base bytes' reversal; the real entry point is examdata/src/examdata/cli.py (pyproject.toml [project.scripts] examdata = 'examdata.cli:app')
- old target: `examdata/cli.py` (base_exists=False, reversal was `restore the recorded base bytes`)
- new target: `examdata/src/examdata/cli.py` (base_exists=True, size=60747, sha256 `514f04204f85ee146d5c209d5c1a29c41a5306395ca8e40a5e1a7ee5d6b29292`)
- entry point: `examdata = "examdata.cli:app"` from `examdata/pyproject.toml [project.scripts]`
- rollback: new_file = delete only if the candidate SHA256 still matches the recorded staged digest; never 'restore bytes' for a file that had no base
- rollback: existing_file = restore the B00 latest released base and verify no later modification is overwritten; do not restore an A14 snapshot

## Entries by group

### config (2 entries)

| id | staged_path | proposed_target | kind | action | disposition |
| --- | --- | --- | --- | --- | --- |
| MM-0242 | `integration-staging/config/staging-config.example.json` | `examdata/config.example.json` | new_file | add_file | deferred_pending_release |
| MM-0243 | `integration-staging/config/staging.env.example` | `examdata/.env.example` | new_file | add_file | deferred_pending_release |

### contracts (74 entries)

| id | staged_path | proposed_target | kind | action | disposition |
| --- | --- | --- | --- | --- | --- |
| MM-0106 | `integration-staging/contracts/examples/answers__cie__ans_72ccqqvhg5nrr7guisdmxgqnhupsnlpx.json` | `examdata/contracts/examples/answers__cie__ans_72ccqqvhg5nrr7guisdmxgqnhupsnlpx.json` | new_file | add_file | deferred_pending_release |
| MM-0107 | `integration-staging/contracts/examples/answers__cie__ans_wiiw7mnvhotjje3lg3ndu4nr6zt4pzbl.json` | `examdata/contracts/examples/answers__cie__ans_wiiw7mnvhotjje3lg3ndu4nr6zt4pzbl.json` | new_file | add_file | deferred_pending_release |
| MM-0108 | `integration-staging/contracts/examples/answers__ielts__ans_hhkuiea6jo5wh7wgv7dnm6sehkfj26xh.json` | `examdata/contracts/examples/answers__ielts__ans_hhkuiea6jo5wh7wgv7dnm6sehkfj26xh.json` | new_file | add_file | deferred_pending_release |
| MM-0109 | `integration-staging/contracts/examples/answers__ielts__ans_rcimn5qhnqwi6szz5iiivxmrc6d6tbke.json` | `examdata/contracts/examples/answers__ielts__ans_rcimn5qhnqwi6szz5iiivxmrc6d6tbke.json` | new_file | add_file | deferred_pending_release |
| MM-0110 | `integration-staging/contracts/examples/answers__ielts__ans_vn5kcb4yyscfh4535ju2nooinqzn3ynb.json` | `examdata/contracts/examples/answers__ielts__ans_vn5kcb4yyscfh4535ju2nooinqzn3ynb.json` | new_file | add_file | deferred_pending_release |
| MM-0111 | `integration-staging/contracts/examples/answers__ielts__ans_zi2f545psrcgmxbjwcwd5jmhqjexqlfo.json` | `examdata/contracts/examples/answers__ielts__ans_zi2f545psrcgmxbjwcwd5jmhqjexqlfo.json` | new_file | add_file | deferred_pending_release |
| MM-0112 | `integration-staging/contracts/examples/answers__ielts__ans_zpoupdffgdwaq6rho46xi36cj2bzqlvc.json` | `examdata/contracts/examples/answers__ielts__ans_zpoupdffgdwaq6rho46xi36cj2bzqlvc.json` | new_file | add_file | deferred_pending_release |
| MM-0113 | `integration-staging/contracts/examples/assets__cie__asset_e5biyakxxkv5bvh64kasz5dyl5kolrkl.json` | `examdata/contracts/examples/assets__cie__asset_e5biyakxxkv5bvh64kasz5dyl5kolrkl.json` | new_file | add_file | deferred_pending_release |
| MM-0114 | `integration-staging/contracts/examples/assets__cie__asset_gxwjjdcnhc5m4mcvcqhx4fmrd3ktefwd.json` | `examdata/contracts/examples/assets__cie__asset_gxwjjdcnhc5m4mcvcqhx4fmrd3ktefwd.json` | new_file | add_file | deferred_pending_release |
| MM-0115 | `integration-staging/contracts/examples/assets__ielts__asset_hvzh75bs2y6opts3xkwy5rv45pmxog3m.json` | `examdata/contracts/examples/assets__ielts__asset_hvzh75bs2y6opts3xkwy5rv45pmxog3m.json` | new_file | add_file | deferred_pending_release |
| MM-0116 | `integration-staging/contracts/examples/containers__cie__container_6cnnjvwpypjw2orom36k3xjazamje2x3.json` | `examdata/contracts/examples/containers__cie__container_6cnnjvwpypjw2orom36k3xjazamje2x3.json` | new_file | add_file | deferred_pending_release |
| MM-0117 | `integration-staging/contracts/examples/containers__edexcel__container_3bbmo2jmeebj3htxofgvkubtrcj23pct.json` | `examdata/contracts/examples/containers__edexcel__container_3bbmo2jmeebj3htxofgvkubtrcj23pct.json` | new_file | add_file | deferred_pending_release |
| MM-0118 | `integration-staging/contracts/examples/containers__ielts__container_qrbvatrkkwbf3xgdurbm4d2otobg5zcq.json` | `examdata/contracts/examples/containers__ielts__container_qrbvatrkkwbf3xgdurbm4d2otobg5zcq.json` | new_file | add_file | deferred_pending_release |
| MM-0119 | `integration-staging/contracts/examples/courses__cie__course_ukyoxjr7v3wfqva5qgctydf75d6xeqfg.json` | `examdata/contracts/examples/courses__cie__course_ukyoxjr7v3wfqva5qgctydf75d6xeqfg.json` | new_file | add_file | deferred_pending_release |
| MM-0120 | `integration-staging/contracts/examples/courses__edexcel__course_vfthis5jlxjijxarwasb7bbyghnx7fqt.json` | `examdata/contracts/examples/courses__edexcel__course_vfthis5jlxjijxarwasb7bbyghnx7fqt.json` | new_file | add_file | deferred_pending_release |
| MM-0121 | `integration-staging/contracts/examples/coverage__cie__cov_synthetic_cie.json` | `examdata/contracts/examples/coverage__cie__cov_synthetic_cie.json` | new_file | add_file | deferred_pending_release |
| MM-0122 | `integration-staging/contracts/examples/coverage__ielts__cov_synthetic_ielts.json` | `examdata/contracts/examples/coverage__ielts__cov_synthetic_ielts.json` | new_file | add_file | deferred_pending_release |
| MM-0123 | `integration-staging/contracts/examples/examination_systems__synthetic__es_xdxhmo4qetoi52ht5f6qkevfi56ob3h4.json` | `examdata/contracts/examples/examination_systems__synthetic__es_xdxhmo4qetoi52ht5f6qkevfi56ob3h4.json` | new_file | add_file | deferred_pending_release |
| MM-0124 | `integration-staging/contracts/examples/identity-registry__cie.json` | `examdata/contracts/examples/identity-registry__cie.json` | new_file | add_file | deferred_pending_release |
| MM-0125 | `integration-staging/contracts/examples/identity-registry__edexcel.json` | `examdata/contracts/examples/identity-registry__edexcel.json` | new_file | add_file | deferred_pending_release |
| MM-0126 | `integration-staging/contracts/examples/identity-registry__ielts.json` | `examdata/contracts/examples/identity-registry__ielts.json` | new_file | add_file | deferred_pending_release |
| MM-0127 | `integration-staging/contracts/examples/INDEX.json` | `examdata/contracts/examples/INDEX.json` | new_file | add_file | deferred_pending_release |
| MM-0128 | `integration-staging/contracts/examples/jobs__synthetic__job_6zcvxittpvvbnvtpqttigpsmos2i5zmn.json` | `examdata/contracts/examples/jobs__synthetic__job_6zcvxittpvvbnvtpqttigpsmos2i5zmn.json` | new_file | add_file | deferred_pending_release |
| MM-0129 | `integration-staging/contracts/examples/materials__synthetic__mat_mmfjianasbw6qrncjkldxnfuavnls3ou.json` | `examdata/contracts/examples/materials__synthetic__mat_mmfjianasbw6qrncjkldxnfuavnls3ou.json` | new_file | add_file | deferred_pending_release |
| MM-0130 | `integration-staging/contracts/examples/questions__cie__q_2tc2e4uhkufazt3aszordnnbilofoy6s.json` | `examdata/contracts/examples/questions__cie__q_2tc2e4uhkufazt3aszordnnbilofoy6s.json` | new_file | add_file | deferred_pending_release |
| MM-0131 | `integration-staging/contracts/examples/questions__cie__q_cb5bnkkjhe4ct7mrvespujhxowo2r3up.json` | `examdata/contracts/examples/questions__cie__q_cb5bnkkjhe4ct7mrvespujhxowo2r3up.json` | new_file | add_file | deferred_pending_release |
| MM-0132 | `integration-staging/contracts/examples/questions__cie__q_ngtwfvjwc26jyirswzxxcccjeeidio56.json` | `examdata/contracts/examples/questions__cie__q_ngtwfvjwc26jyirswzxxcccjeeidio56.json` | new_file | add_file | deferred_pending_release |
| MM-0133 | `integration-staging/contracts/examples/questions__cie__q_nxjtvu4225v43syunzyhurjzvxl7szhk.json` | `examdata/contracts/examples/questions__cie__q_nxjtvu4225v43syunzyhurjzvxl7szhk.json` | new_file | add_file | deferred_pending_release |
| MM-0134 | `integration-staging/contracts/examples/questions__cie__q_w4ecszmbbqa54chk22paau3sluucc22z.json` | `examdata/contracts/examples/questions__cie__q_w4ecszmbbqa54chk22paau3sluucc22z.json` | new_file | add_file | deferred_pending_release |
| MM-0135 | `integration-staging/contracts/examples/questions__ielts__q_b43mm5rvfp6qfwqwrxxi46d4fk3mm7hd.json` | `examdata/contracts/examples/questions__ielts__q_b43mm5rvfp6qfwqwrxxi46d4fk3mm7hd.json` | new_file | add_file | deferred_pending_release |
| MM-0136 | `integration-staging/contracts/examples/questions__ielts__q_egcwv27xjaq2elinkwd63fu6zvvq45ck.json` | `examdata/contracts/examples/questions__ielts__q_egcwv27xjaq2elinkwd63fu6zvvq45ck.json` | new_file | add_file | deferred_pending_release |
| MM-0137 | `integration-staging/contracts/examples/questions__ielts__q_lkzo7pnl2zjiboucetyjy5ddgdxxcx3k.json` | `examdata/contracts/examples/questions__ielts__q_lkzo7pnl2zjiboucetyjy5ddgdxxcx3k.json` | new_file | add_file | deferred_pending_release |
| MM-0138 | `integration-staging/contracts/examples/questions__ielts__q_pjo55lma3or42y2ncw2sa7kwqzkc4lwy.json` | `examdata/contracts/examples/questions__ielts__q_pjo55lma3or42y2ncw2sa7kwqzkc4lwy.json` | new_file | add_file | deferred_pending_release |
| MM-0139 | `integration-staging/contracts/examples/questions__ielts__q_rtf7wrlwtotph3p45wx5wlfpfuo32iku.json` | `examdata/contracts/examples/questions__ielts__q_rtf7wrlwtotph3p45wx5wlfpfuo32iku.json` | new_file | add_file | deferred_pending_release |
| MM-0140 | `integration-staging/contracts/examples/questions__ielts__q_vv7cxbrhbxxdpmtnlkcwzhyjs4dbeiq5.json` | `examdata/contracts/examples/questions__ielts__q_vv7cxbrhbxxdpmtnlkcwzhyjs4dbeiq5.json` | new_file | add_file | deferred_pending_release |
| MM-0141 | `integration-staging/contracts/examples/questions__ielts__q_ymm437ermxommfdifgexf7eq6dm6kdxc.json` | `examdata/contracts/examples/questions__ielts__q_ymm437ermxommfdifgexf7eq6dm6kdxc.json` | new_file | add_file | deferred_pending_release |
| MM-0142 | `integration-staging/contracts/examples/questions__ielts__q_zlx6ycscjqsk3e4gs5sq3ruxfzvuqtvf.json` | `examdata/contracts/examples/questions__ielts__q_zlx6ycscjqsk3e4gs5sq3ruxfzvuqtvf.json` | new_file | add_file | deferred_pending_release |
| MM-0143 | `integration-staging/contracts/examples/regions__synthetic__region_fn2r2ikszwe234bmma3a5zorsr7snsk3.json` | `examdata/contracts/examples/regions__synthetic__region_fn2r2ikszwe234bmma3a5zorsr7snsk3.json` | new_file | add_file | deferred_pending_release |
| MM-0144 | `integration-staging/contracts/examples/syllabi__synthetic__syl_6ytdfhso2hvo47geydgicjiuyilumcei.json` | `examdata/contracts/examples/syllabi__synthetic__syl_6ytdfhso2hvo47geydgicjiuyilumcei.json` | new_file | add_file | deferred_pending_release |
| MM-0145 | `integration-staging/contracts/examples/tags__synthetic__tag_fz2cdf3lly5r3uybtl2vmbubioquwymu.json` | `examdata/contracts/examples/tags__synthetic__tag_fz2cdf3lly5r3uybtl2vmbubioquwymu.json` | new_file | add_file | deferred_pending_release |
| MM-0146 | `integration-staging/contracts/examples/timetable_events__cie__tte_punqoxygppjubuhcuj4nkd4nbikowv3f.json` | `examdata/contracts/examples/timetable_events__cie__tte_punqoxygppjubuhcuj4nkd4nbikowv3f.json` | new_file | add_file | deferred_pending_release |
| MM-0147 | `integration-staging/contracts/examples/timetable_events__edexcel__tte_5kfllz2yp7iibointgdo56rmvnm7zgjc.json` | `examdata/contracts/examples/timetable_events__edexcel__tte_5kfllz2yp7iibointgdo56rmvnm7zgjc.json` | new_file | add_file | deferred_pending_release |
| MM-0148 | `integration-staging/contracts/examples/timetable_events__edexcel__tte_hdxrn6xaev6ihma5sgilzhroxl5olams.json` | `examdata/contracts/examples/timetable_events__edexcel__tte_hdxrn6xaev6ihma5sgilzhroxl5olams.json` | new_file | add_file | deferred_pending_release |
| MM-0149 | `integration-staging/contracts/examples/timetable_windows__synthetic__ttw_m6m5zleg2srdbeqt32mlqs7yrhmacczv.json` | `examdata/contracts/examples/timetable_windows__synthetic__ttw_m6m5zleg2srdbeqt32mlqs7yrhmacczv.json` | new_file | add_file | deferred_pending_release |
| MM-0150 | `integration-staging/contracts/identity-keys.json` | `examdata/contracts/identity-keys.json` | new_file | add_file | deferred_pending_release |
| MM-0151 | `integration-staging/contracts/quality-transitions.json` | `examdata/contracts/quality-transitions.json` | new_file | add_file | deferred_pending_release |
| MM-0152 | `integration-staging/contracts/schema/answer-conflict.schema.json` | `examdata/contracts/schema/answer-conflict.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0153 | `integration-staging/contracts/schema/answer.schema.json` | `examdata/contracts/schema/answer.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0154 | `integration-staging/contracts/schema/asset.schema.json` | `examdata/contracts/schema/asset.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0155 | `integration-staging/contracts/schema/container.schema.json` | `examdata/contracts/schema/container.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0156 | `integration-staging/contracts/schema/course.schema.json` | `examdata/contracts/schema/course.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0157 | `integration-staging/contracts/schema/coverage.schema.json` | `examdata/contracts/schema/coverage.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0158 | `integration-staging/contracts/schema/examination-system.schema.json` | `examdata/contracts/schema/examination-system.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0159 | `integration-staging/contracts/schema/gap.schema.json` | `examdata/contracts/schema/gap.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0160 | `integration-staging/contracts/schema/job-status.schema.json` | `examdata/contracts/schema/job-status.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0161 | `integration-staging/contracts/schema/lineage.schema.json` | `examdata/contracts/schema/lineage.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0162 | `integration-staging/contracts/schema/manual-decision.schema.json` | `examdata/contracts/schema/manual-decision.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0163 | `integration-staging/contracts/schema/material.schema.json` | `examdata/contracts/schema/material.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0164 | `integration-staging/contracts/schema/option.schema.json` | `examdata/contracts/schema/option.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0165 | `integration-staging/contracts/schema/payload-labels.schema.json` | `examdata/contracts/schema/payload-labels.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0166 | `integration-staging/contracts/schema/payload-matching.schema.json` | `examdata/contracts/schema/payload-matching.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0167 | `integration-staging/contracts/schema/payload-options.schema.json` | `examdata/contracts/schema/payload-options.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0168 | `integration-staging/contracts/schema/payload-table.schema.json` | `examdata/contracts/schema/payload-table.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0169 | `integration-staging/contracts/schema/payload-text.schema.json` | `examdata/contracts/schema/payload-text.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0170 | `integration-staging/contracts/schema/payload-unknown.schema.json` | `examdata/contracts/schema/payload-unknown.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0171 | `integration-staging/contracts/schema/quality.schema.json` | `examdata/contracts/schema/quality.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0172 | `integration-staging/contracts/schema/question.schema.json` | `examdata/contracts/schema/question.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0173 | `integration-staging/contracts/schema/region.schema.json` | `examdata/contracts/schema/region.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0174 | `integration-staging/contracts/schema/source-ref.schema.json` | `examdata/contracts/schema/source-ref.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0175 | `integration-staging/contracts/schema/syllabus.schema.json` | `examdata/contracts/schema/syllabus.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0176 | `integration-staging/contracts/schema/table-cell.schema.json` | `examdata/contracts/schema/table-cell.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0177 | `integration-staging/contracts/schema/tag.schema.json` | `examdata/contracts/schema/tag.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0178 | `integration-staging/contracts/schema/timetable-event.schema.json` | `examdata/contracts/schema/timetable-event.schema.json` | new_file | add_file | deferred_pending_release |
| MM-0179 | `integration-staging/contracts/schema/timetable-window.schema.json` | `examdata/contracts/schema/timetable-window.schema.json` | new_file | add_file | deferred_pending_release |

### docs (4 entries)

| id | staged_path | proposed_target | kind | action | disposition |
| --- | --- | --- | --- | --- | --- |
| MM-0244 | `integration-staging/docs/integration-guide.md` | `examdata/docs/integration-guide.md` | new_file | add_file | deferred_pending_release |
| MM-0245 | `integration-staging/docs/README.md` | `examdata/docs/README.md` | new_file | add_file | deferred_pending_release |
| MM-0246 | `integration-staging/docs/release-and-rollback.md` | `examdata/docs/release-and-rollback.md` | new_file | add_file | deferred_pending_release |
| MM-0247 | `integration-staging/docs/v2-api-reference.md` | `examdata/docs/v2-api-reference.md` | new_file | add_file | deferred_pending_release |

### fixtures (49 entries)

| id | staged_path | proposed_target | kind | action | disposition |
| --- | --- | --- | --- | --- | --- |
| MM-0180 | `integration-staging/fixtures/copied/edexcel/subjects-source.json` | `examdata/tests/integration/fixtures/copied/edexcel/subjects-source.json` | copied_snapshot | verify_copy | deferred_pending_release |
| MM-0181 | `integration-staging/fixtures/copied/ielts/indexes-current.json` | `examdata/tests/integration/fixtures/copied/ielts/indexes-current.json` | copied_snapshot | verify_copy | deferred_pending_release |
| MM-0182 | `integration-staging/fixtures/copied/ielts/manifests-current.json` | `examdata/tests/integration/fixtures/copied/ielts/manifests-current.json` | copied_snapshot | verify_copy | deferred_pending_release |
| MM-0183 | `integration-staging/fixtures/copied/ielts/pdf-provenance.json` | `examdata/tests/integration/fixtures/copied/ielts/pdf-provenance.json` | copied_snapshot | verify_copy | deferred_pending_release |
| MM-0184 | `integration-staging/fixtures/copied/ielts/printed-pages.json` | `examdata/tests/integration/fixtures/copied/ielts/printed-pages.json` | copied_snapshot | verify_copy | deferred_pending_release |
| MM-0185 | `integration-staging/fixtures/copied/toefl/ddy-index.json` | `examdata/tests/integration/fixtures/copied/toefl/ddy-index.json` | copied_snapshot | verify_copy | deferred_pending_release |
| MM-0186 | `integration-staging/fixtures/PROVENANCE.json` | `examdata/tests/integration/fixtures/PROVENANCE.json` | new_file | add_file | deferred_pending_release |
| MM-0187 | `integration-staging/fixtures/PROVENANCE.md` | `examdata/tests/integration/fixtures/PROVENANCE.md` | new_file | add_file | deferred_pending_release |
| MM-0188 | `integration-staging/fixtures/README.md` | `examdata/tests/integration/fixtures/README.md` | new_file | add_file | deferred_pending_release |
| MM-0189 | `integration-staging/fixtures/synthetic/adapters/cie-index-adapters.json` | `examdata/tests/integration/fixtures/synthetic/adapters/cie-index-adapters.json` | new_file | add_file | deferred_pending_release |
| MM-0190 | `integration-staging/fixtures/synthetic/adapters/edexcel-index-adapters.json` | `examdata/tests/integration/fixtures/synthetic/adapters/edexcel-index-adapters.json` | new_file | add_file | deferred_pending_release |
| MM-0191 | `integration-staging/fixtures/synthetic/adapters/PROVENANCE.json` | `examdata/tests/integration/fixtures/synthetic/adapters/PROVENANCE.json` | new_file | add_file | deferred_pending_release |
| MM-0192 | `integration-staging/fixtures/synthetic/adapters/README.md` | `examdata/tests/integration/fixtures/synthetic/adapters/README.md` | new_file | add_file | deferred_pending_release |
| MM-0193 | `integration-staging/fixtures/synthetic/binary/cie-diagram.png` | `examdata/tests/integration/fixtures/synthetic/binary/cie-diagram.png` | new_file | add_file | deferred_pending_release |
| MM-0194 | `integration-staging/fixtures/synthetic/binary/cie-ms.pdf` | `examdata/tests/integration/fixtures/synthetic/binary/cie-ms.pdf` | new_file | add_file | deferred_pending_release |
| MM-0195 | `integration-staging/fixtures/synthetic/binary/cie-qp.pdf` | `examdata/tests/integration/fixtures/synthetic/binary/cie-qp.pdf` | new_file | add_file | deferred_pending_release |
| MM-0196 | `integration-staging/fixtures/synthetic/binary/crop-cie-1-page2.png` | `examdata/tests/integration/fixtures/synthetic/binary/crop-cie-1-page2.png` | new_file | add_file | deferred_pending_release |
| MM-0197 | `integration-staging/fixtures/synthetic/binary/crop-cie-2-page3.png` | `examdata/tests/integration/fixtures/synthetic/binary/crop-cie-2-page3.png` | new_file | add_file | deferred_pending_release |
| MM-0198 | `integration-staging/fixtures/synthetic/binary/crop-cie-3-page4.png` | `examdata/tests/integration/fixtures/synthetic/binary/crop-cie-3-page4.png` | new_file | add_file | deferred_pending_release |
| MM-0199 | `integration-staging/fixtures/synthetic/binary/edexcel-ms.pdf` | `examdata/tests/integration/fixtures/synthetic/binary/edexcel-ms.pdf` | new_file | add_file | deferred_pending_release |
| MM-0200 | `integration-staging/fixtures/synthetic/binary/edexcel-qp.pdf` | `examdata/tests/integration/fixtures/synthetic/binary/edexcel-qp.pdf` | new_file | add_file | deferred_pending_release |
| MM-0201 | `integration-staging/fixtures/synthetic/binary/ielts-diagram.png` | `examdata/tests/integration/fixtures/synthetic/binary/ielts-diagram.png` | new_file | add_file | deferred_pending_release |
| MM-0202 | `integration-staging/fixtures/synthetic/binary/manifest.json` | `examdata/tests/integration/fixtures/synthetic/binary/manifest.json` | new_file | add_file | deferred_pending_release |
| MM-0203 | `integration-staging/fixtures/synthetic/binary/material-synthetic-cie-ins.pdf` | `examdata/tests/integration/fixtures/synthetic/binary/material-synthetic-cie-ins.pdf` | new_file | add_file | deferred_pending_release |
| MM-0204 | `integration-staging/fixtures/synthetic/binary/PROVENANCE.json` | `examdata/tests/integration/fixtures/synthetic/binary/PROVENANCE.json` | new_file | add_file | deferred_pending_release |
| MM-0205 | `integration-staging/fixtures/synthetic/binary/syllabus-synthetic-cie-0580.pdf` | `examdata/tests/integration/fixtures/synthetic/binary/syllabus-synthetic-cie-0580.pdf` | new_file | add_file | deferred_pending_release |
| MM-0206 | `integration-staging/fixtures/synthetic/catalog/catalog-base-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/catalog/catalog-base-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0207 | `integration-staging/fixtures/synthetic/catalog/catalog-duplicate-native-id-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/catalog/catalog-duplicate-native-id-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0208 | `integration-staging/fixtures/synthetic/catalog/catalog-incomplete-reference-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/catalog/catalog-incomplete-reference-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0209 | `integration-staging/fixtures/synthetic/catalog/catalog-quality-upgrade-unexplained-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/catalog/catalog-quality-upgrade-unexplained-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0210 | `integration-staging/fixtures/synthetic/catalog/catalog-removal-unexplained-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/catalog/catalog-removal-unexplained-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0211 | `integration-staging/fixtures/synthetic/catalog/PROVENANCE.json` | `examdata/tests/integration/fixtures/synthetic/catalog/PROVENANCE.json` | new_file | add_file | deferred_pending_release |
| MM-0212 | `integration-staging/fixtures/synthetic/cie/cie-index-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/cie/cie-index-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0213 | `integration-staging/fixtures/synthetic/edexcel/index-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/edexcel/index-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0214 | `integration-staging/fixtures/synthetic/ielts/questions-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/ielts/questions-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0215 | `integration-staging/fixtures/synthetic/ielts-toefl/ielts-audio-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/ielts-toefl/ielts-audio-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0216 | `integration-staging/fixtures/synthetic/ielts-toefl/ielts-questions-a08-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/ielts-toefl/ielts-questions-a08-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0217 | `integration-staging/fixtures/synthetic/ielts-toefl/PROVENANCE.json` | `examdata/tests/integration/fixtures/synthetic/ielts-toefl/PROVENANCE.json` | new_file | add_file | deferred_pending_release |
| MM-0218 | `integration-staging/fixtures/synthetic/ielts-toefl/README.md` | `examdata/tests/integration/fixtures/synthetic/ielts-toefl/README.md` | new_file | add_file | deferred_pending_release |
| MM-0219 | `integration-staging/fixtures/synthetic/ielts-toefl/toefl-bad-cache-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/ielts-toefl/toefl-bad-cache-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0220 | `integration-staging/fixtures/synthetic/ielts-toefl/toefl-questions-synthetic.json` | `examdata/tests/integration/fixtures/synthetic/ielts-toefl/toefl-questions-synthetic.json` | new_file | add_file | deferred_pending_release |
| MM-0221 | `integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-running.json` | `examdata/tests/integration/fixtures/synthetic/operations/cie-batch-checkpoint-running.json` | new_file | add_file | deferred_pending_release |
| MM-0222 | `integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-stopped.json` | `examdata/tests/integration/fixtures/synthetic/operations/cie-batch-checkpoint-stopped.json` | new_file | add_file | deferred_pending_release |
| MM-0223 | `integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-ok-stale.json` | `examdata/tests/integration/fixtures/synthetic/operations/ielts-run-checkpoint-ok-stale.json` | new_file | add_file | deferred_pending_release |
| MM-0224 | `integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-ok.json` | `examdata/tests/integration/fixtures/synthetic/operations/ielts-run-checkpoint-ok.json` | new_file | add_file | deferred_pending_release |
| MM-0225 | `integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-partial.json` | `examdata/tests/integration/fixtures/synthetic/operations/ielts-run-checkpoint-partial.json` | new_file | add_file | deferred_pending_release |
| MM-0226 | `integration-staging/fixtures/synthetic/operations/PROVENANCE.json` | `examdata/tests/integration/fixtures/synthetic/operations/PROVENANCE.json` | new_file | add_file | deferred_pending_release |
| MM-0227 | `integration-staging/fixtures/synthetic/operations/README.md` | `examdata/tests/integration/fixtures/synthetic/operations/README.md` | new_file | add_file | deferred_pending_release |
| MM-0228 | `integration-staging/fixtures/synthetic/operations/unsupported-checkpoint.json` | `examdata/tests/integration/fixtures/synthetic/operations/unsupported-checkpoint.json` | new_file | add_file | deferred_pending_release |

### frontend (13 entries)

| id | staged_path | proposed_target | kind | action | disposition |
| --- | --- | --- | --- | --- | --- |
| MM-0229 | `integration-staging/frontend/app.js` | `frontend/app.js` | modified_copy | reconcile_modify | deferred_pending_release |
| MM-0230 | `integration-staging/frontend/client.mjs` | `frontend/client.mjs` | new_file | add_file | deferred_pending_release |
| MM-0231 | `integration-staging/frontend/fixture-server.mjs` | `frontend/fixture-server.mjs` | new_file | add_file | deferred_pending_release |
| MM-0232 | `integration-staging/frontend/fixtures/catalog.json` | `frontend/fixtures/catalog.json` | new_file | add_file | deferred_pending_release |
| MM-0233 | `integration-staging/frontend/fixtures/resources.json` | `frontend/fixtures/resources.json` | new_file | add_file | deferred_pending_release |
| MM-0234 | `integration-staging/frontend/fixtures/syllabi.json` | `frontend/fixtures/syllabi.json` | new_file | add_file | deferred_pending_release |
| MM-0235 | `integration-staging/frontend/index.html` | `frontend/index.html` | modified_copy | reconcile_modify | deferred_pending_release |
| MM-0236 | `integration-staging/frontend/README.md` | `frontend/README.md` | modified_copy | reconcile_modify | deferred_pending_release |
| MM-0237 | `integration-staging/frontend/search.mjs` | `frontend/search.mjs` | copied_snapshot | verify_copy | deferred_pending_release |
| MM-0238 | `integration-staging/frontend/styles.css` | `frontend/styles.css` | copied_snapshot | verify_copy | deferred_pending_release |
| MM-0239 | `integration-staging/frontend/tests/client.test.mjs` | `frontend/tests/client.test.mjs` | new_file | add_file | deferred_pending_release |
| MM-0240 | `integration-staging/frontend/tests/flow.test.mjs` | `frontend/tests/flow.test.mjs` | new_file | add_file | deferred_pending_release |
| MM-0241 | `integration-staging/frontend/tests/search.test.mjs` | `frontend/tests/search.test.mjs` | modified_copy | reconcile_modify | deferred_pending_release |

### python (62 entries)

| id | staged_path | proposed_target | kind | action | disposition |
| --- | --- | --- | --- | --- | --- |
| MM-0001 | `integration-staging/src/examdata_integration/__init__.py` | `examdata/src/examdata/integration/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0002 | `integration-staging/src/examdata_integration/adapters/__init__.py` | `examdata/src/examdata/integration/adapters/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0003 | `integration-staging/src/examdata_integration/adapters/answers.py` | `examdata/src/examdata/integration/adapters/answers.py` | new_file | add_file | deferred_pending_release |
| MM-0004 | `integration-staging/src/examdata_integration/adapters/bundle.py` | `examdata/src/examdata/integration/adapters/bundle.py` | new_file | add_file | deferred_pending_release |
| MM-0005 | `integration-staging/src/examdata_integration/adapters/cie.py` | `examdata/src/examdata/integration/adapters/cie.py` | new_file | add_file | deferred_pending_release |
| MM-0006 | `integration-staging/src/examdata_integration/adapters/documents.py` | `examdata/src/examdata/integration/adapters/documents.py` | new_file | add_file | deferred_pending_release |
| MM-0007 | `integration-staging/src/examdata_integration/adapters/edexcel.py` | `examdata/src/examdata/integration/adapters/edexcel.py` | new_file | add_file | deferred_pending_release |
| MM-0008 | `integration-staging/src/examdata_integration/adapters/ielts.py` | `examdata/src/examdata/integration/adapters/ielts.py` | new_file | add_file | deferred_pending_release |
| MM-0009 | `integration-staging/src/examdata_integration/adapters/problems.py` | `examdata/src/examdata/integration/adapters/problems.py` | new_file | add_file | deferred_pending_release |
| MM-0010 | `integration-staging/src/examdata_integration/adapters/reader.py` | `examdata/src/examdata/integration/adapters/reader.py` | new_file | add_file | deferred_pending_release |
| MM-0011 | `integration-staging/src/examdata_integration/adapters/regions.py` | `examdata/src/examdata/integration/adapters/regions.py` | new_file | add_file | deferred_pending_release |
| MM-0012 | `integration-staging/src/examdata_integration/adapters/source_reader.py` | `examdata/src/examdata/integration/adapters/source_reader.py` | new_file | add_file | deferred_pending_release |
| MM-0013 | `integration-staging/src/examdata_integration/adapters/toefl.py` | `examdata/src/examdata/integration/adapters/toefl.py` | new_file | add_file | deferred_pending_release |
| MM-0014 | `integration-staging/src/examdata_integration/api/__init__.py` | `examdata/src/examdata/integration/api/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0015 | `integration-staging/src/examdata_integration/api/app.py` | `examdata/src/examdata/integration/api/app.py` | new_file | add_file | deferred_pending_release |
| MM-0016 | `integration-staging/src/examdata_integration/api/binary.py` | `examdata/src/examdata/integration/api/binary.py` | new_file | add_file | deferred_pending_release |
| MM-0017 | `integration-staging/src/examdata_integration/api/dataset.py` | `examdata/src/examdata/integration/api/dataset.py` | new_file | add_file | deferred_pending_release |
| MM-0018 | `integration-staging/src/examdata_integration/api/envelope.py` | `examdata/src/examdata/integration/api/envelope.py` | new_file | add_file | deferred_pending_release |
| MM-0019 | `integration-staging/src/examdata_integration/api/links.py` | `examdata/src/examdata/integration/api/links.py` | new_file | add_file | deferred_pending_release |
| MM-0020 | `integration-staging/src/examdata_integration/api/openapi.py` | `examdata/src/examdata/integration/api/openapi.py` | new_file | add_file | deferred_pending_release |
| MM-0021 | `integration-staging/src/examdata_integration/api/pagination.py` | `examdata/src/examdata/integration/api/pagination.py` | new_file | add_file | deferred_pending_release |
| MM-0022 | `integration-staging/src/examdata_integration/api/view.py` | `examdata/src/examdata/integration/api/view.py` | new_file | add_file | deferred_pending_release |
| MM-0023 | `integration-staging/src/examdata_integration/catalog/__init__.py` | `examdata/src/examdata/integration/catalog/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0024 | `integration-staging/src/examdata_integration/catalog/builder.py` | `examdata/src/examdata/integration/catalog/builder.py` | new_file | add_file | deferred_pending_release |
| MM-0025 | `integration-staging/src/examdata_integration/catalog/model.py` | `examdata/src/examdata/integration/catalog/model.py` | new_file | add_file | deferred_pending_release |
| MM-0026 | `integration-staging/src/examdata_integration/catalog/revision.py` | `examdata/src/examdata/integration/catalog/revision.py` | new_file | add_file | deferred_pending_release |
| MM-0027 | `integration-staging/src/examdata_integration/catalog/store.py` | `examdata/src/examdata/integration/catalog/store.py` | new_file | add_file | deferred_pending_release |
| MM-0028 | `integration-staging/src/examdata_integration/contracts/__init__.py` | `examdata/src/examdata/integration/contracts/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0029 | `integration-staging/src/examdata_integration/contracts/base.py` | `examdata/src/examdata/integration/contracts/base.py` | new_file | add_file | deferred_pending_release |
| MM-0030 | `integration-staging/src/examdata_integration/contracts/canonical.py` | `examdata/src/examdata/integration/contracts/canonical.py` | new_file | add_file | deferred_pending_release |
| MM-0031 | `integration-staging/src/examdata_integration/contracts/completeness.py` | `examdata/src/examdata/integration/contracts/completeness.py` | new_file | add_file | deferred_pending_release |
| MM-0032 | `integration-staging/src/examdata_integration/contracts/enums.py` | `examdata/src/examdata/integration/contracts/enums.py` | new_file | add_file | deferred_pending_release |
| MM-0033 | `integration-staging/src/examdata_integration/contracts/ids.py` | `examdata/src/examdata/integration/contracts/ids.py` | new_file | add_file | deferred_pending_release |
| MM-0034 | `integration-staging/src/examdata_integration/contracts/jsonschema_lite.py` | `examdata/src/examdata/integration/contracts/jsonschema_lite.py` | new_file | add_file | deferred_pending_release |
| MM-0035 | `integration-staging/src/examdata_integration/contracts/models.py` | `examdata/src/examdata/integration/contracts/models.py` | new_file | add_file | deferred_pending_release |
| MM-0036 | `integration-staging/src/examdata_integration/contracts/quality.py` | `examdata/src/examdata/integration/contracts/quality.py` | new_file | add_file | deferred_pending_release |
| MM-0037 | `integration-staging/src/examdata_integration/legacy/__init__.py` | `examdata/src/examdata/integration/legacy/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0038 | `integration-staging/src/examdata_integration/legacy/bridge.py` | `examdata/src/examdata/integration/legacy/bridge.py` | new_file | add_file | deferred_pending_release |
| MM-0039 | `integration-staging/src/examdata_integration/legacy/decisions.py` | `examdata/src/examdata/integration/legacy/decisions.py` | new_file | add_file | deferred_pending_release |
| MM-0040 | `integration-staging/src/examdata_integration/legacy/parity.py` | `examdata/src/examdata/integration/legacy/parity.py` | new_file | add_file | deferred_pending_release |
| MM-0041 | `integration-staging/src/examdata_integration/legacy/registry.json` | `examdata/src/examdata/integration/legacy/registry.json` | new_file | add_file | deferred_pending_release |
| MM-0042 | `integration-staging/src/examdata_integration/legacy/translate.py` | `examdata/src/examdata/integration/legacy/translate.py` | new_file | add_file | deferred_pending_release |
| MM-0043 | `integration-staging/src/examdata_integration/operations/__init__.py` | `examdata/src/examdata/integration/operations/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0044 | `integration-staging/src/examdata_integration/operations/checkpoints.py` | `examdata/src/examdata/integration/operations/checkpoints.py` | new_file | add_file | deferred_pending_release |
| MM-0045 | `integration-staging/src/examdata_integration/operations/coverage.py` | `examdata/src/examdata/integration/operations/coverage.py` | new_file | add_file | deferred_pending_release |
| MM-0046 | `integration-staging/src/examdata_integration/providers/__init__.py` | `examdata/src/examdata/integration/providers/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0047 | `integration-staging/src/examdata_integration/providers/capabilities.py` | `examdata/src/examdata/integration/providers/capabilities.py` | new_file | add_file | deferred_pending_release |
| MM-0048 | `integration-staging/src/examdata_integration/providers/fixtures.py` | `examdata/src/examdata/integration/providers/fixtures.py` | new_file | add_file | deferred_pending_release |
| MM-0049 | `integration-staging/src/examdata_integration/providers/protocol.py` | `examdata/src/examdata/integration/providers/protocol.py` | new_file | add_file | deferred_pending_release |
| MM-0050 | `integration-staging/src/examdata_integration/providers/registry.py` | `examdata/src/examdata/integration/providers/registry.py` | new_file | add_file | deferred_pending_release |
| MM-0051 | `integration-staging/src/examdata_integration/providers/results.py` | `examdata/src/examdata/integration/providers/results.py` | new_file | add_file | deferred_pending_release |
| MM-0052 | `integration-staging/src/examdata_integration/runtime/__init__.py` | `examdata/src/examdata/integration/runtime/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0053 | `integration-staging/src/examdata_integration/runtime/classification.py` | `examdata/src/examdata/integration/runtime/classification.py` | new_file | add_file | deferred_pending_release |
| MM-0054 | `integration-staging/src/examdata_integration/runtime/doctor.py` | `examdata/src/examdata/integration/runtime/doctor.py` | new_file | add_file | deferred_pending_release |
| MM-0055 | `integration-staging/src/examdata_integration/runtime/manifest.py` | `examdata/src/examdata/integration/runtime/manifest.py` | new_file | add_file | deferred_pending_release |
| MM-0056 | `integration-staging/src/examdata_integration/runtime/redact.py` | `examdata/src/examdata/integration/runtime/redact.py` | new_file | add_file | deferred_pending_release |
| MM-0057 | `integration-staging/src/examdata_integration/runtime/runner.py` | `examdata/src/examdata/integration/runtime/runner.py` | new_file | add_file | deferred_pending_release |
| MM-0058 | `integration-staging/src/examdata_integration/runtime/settings.py` | `examdata/src/examdata/integration/runtime/settings.py` | new_file | add_file | deferred_pending_release |
| MM-0059 | `integration-staging/src/examdata_integration/testing/__init__.py` | `examdata/src/examdata/integration/testing/__init__.py` | new_file | add_file | deferred_pending_release |
| MM-0060 | `integration-staging/src/examdata_integration/testing/guards.py` | `examdata/src/examdata/integration/testing/guards.py` | new_file | add_file | deferred_pending_release |
| MM-0061 | `integration-staging/src/examdata_integration/testing/node_guard.py` | `examdata/src/examdata/integration/testing/node_guard.py` | new_file | add_file | deferred_pending_release |
| MM-0062 | `integration-staging/src/examdata_integration/testing/runtime_support.py` | `examdata/src/examdata/integration/testing/runtime_support.py` | new_file | add_file | deferred_pending_release |

### tests (43 entries)

| id | staged_path | proposed_target | kind | action | disposition |
| --- | --- | --- | --- | --- | --- |
| MM-0063 | `integration-staging/tests/conftest.py` | `examdata/tests/integration/conftest.py` | new_file | add_file | deferred_pending_release |
| MM-0064 | `integration-staging/tests/test_adapters_answers.py` | `examdata/tests/integration/test_adapters_answers.py` | new_file | add_file | deferred_pending_release |
| MM-0065 | `integration-staging/tests/test_adapters_cie.py` | `examdata/tests/integration/test_adapters_cie.py` | new_file | add_file | deferred_pending_release |
| MM-0066 | `integration-staging/tests/test_adapters_documents.py` | `examdata/tests/integration/test_adapters_documents.py` | new_file | add_file | deferred_pending_release |
| MM-0067 | `integration-staging/tests/test_adapters_edexcel.py` | `examdata/tests/integration/test_adapters_edexcel.py` | new_file | add_file | deferred_pending_release |
| MM-0068 | `integration-staging/tests/test_adapters_ielts.py` | `examdata/tests/integration/test_adapters_ielts.py` | new_file | add_file | deferred_pending_release |
| MM-0069 | `integration-staging/tests/test_adapters_provenance.py` | `examdata/tests/integration/test_adapters_provenance.py` | new_file | add_file | deferred_pending_release |
| MM-0070 | `integration-staging/tests/test_adapters_reader.py` | `examdata/tests/integration/test_adapters_reader.py` | new_file | add_file | deferred_pending_release |
| MM-0071 | `integration-staging/tests/test_adapters_regions.py` | `examdata/tests/integration/test_adapters_regions.py` | new_file | add_file | deferred_pending_release |
| MM-0072 | `integration-staging/tests/test_adapters_source_reader.py` | `examdata/tests/integration/test_adapters_source_reader.py` | new_file | add_file | deferred_pending_release |
| MM-0073 | `integration-staging/tests/test_adapters_toefl.py` | `examdata/tests/integration/test_adapters_toefl.py` | new_file | add_file | deferred_pending_release |
| MM-0074 | `integration-staging/tests/test_api_binary_fixtures.py` | `examdata/tests/integration/test_api_binary_fixtures.py` | new_file | add_file | deferred_pending_release |
| MM-0075 | `integration-staging/tests/test_api_binary_store.py` | `examdata/tests/integration/test_api_binary_store.py` | new_file | add_file | deferred_pending_release |
| MM-0076 | `integration-staging/tests/test_api_binary_transport.py` | `examdata/tests/integration/test_api_binary_transport.py` | new_file | add_file | deferred_pending_release |
| MM-0077 | `integration-staging/tests/test_api_dataset.py` | `examdata/tests/integration/test_api_dataset.py` | new_file | add_file | deferred_pending_release |
| MM-0078 | `integration-staging/tests/test_api_envelope.py` | `examdata/tests/integration/test_api_envelope.py` | new_file | add_file | deferred_pending_release |
| MM-0079 | `integration-staging/tests/test_api_links_openapi.py` | `examdata/tests/integration/test_api_links_openapi.py` | new_file | add_file | deferred_pending_release |
| MM-0080 | `integration-staging/tests/test_api_pagination.py` | `examdata/tests/integration/test_api_pagination.py` | new_file | add_file | deferred_pending_release |
| MM-0081 | `integration-staging/tests/test_api_routes.py` | `examdata/tests/integration/test_api_routes.py` | new_file | add_file | deferred_pending_release |
| MM-0082 | `integration-staging/tests/test_catalog_builder.py` | `examdata/tests/integration/test_catalog_builder.py` | new_file | add_file | deferred_pending_release |
| MM-0083 | `integration-staging/tests/test_catalog_revision.py` | `examdata/tests/integration/test_catalog_revision.py` | new_file | add_file | deferred_pending_release |
| MM-0084 | `integration-staging/tests/test_catalog_store.py` | `examdata/tests/integration/test_catalog_store.py` | new_file | add_file | deferred_pending_release |
| MM-0085 | `integration-staging/tests/test_config_manifest.py` | `examdata/tests/integration/test_config_manifest.py` | new_file | add_file | deferred_pending_release |
| MM-0086 | `integration-staging/tests/test_config_resolution.py` | `examdata/tests/integration/test_config_resolution.py` | new_file | add_file | deferred_pending_release |
| MM-0087 | `integration-staging/tests/test_contracts_completeness.py` | `examdata/tests/integration/test_contracts_completeness.py` | new_file | add_file | deferred_pending_release |
| MM-0088 | `integration-staging/tests/test_contracts_identity.py` | `examdata/tests/integration/test_contracts_identity.py` | new_file | add_file | deferred_pending_release |
| MM-0089 | `integration-staging/tests/test_contracts_quality.py` | `examdata/tests/integration/test_contracts_quality.py` | new_file | add_file | deferred_pending_release |
| MM-0090 | `integration-staging/tests/test_contracts_schemas.py` | `examdata/tests/integration/test_contracts_schemas.py` | new_file | add_file | deferred_pending_release |
| MM-0091 | `integration-staging/tests/test_fixture_provenance.py` | `examdata/tests/integration/test_fixture_provenance.py` | new_file | add_file | deferred_pending_release |
| MM-0092 | `integration-staging/tests/test_frontend_staged_copy.py` | `examdata/tests/integration/test_frontend_staged_copy.py` | new_file | add_file | deferred_pending_release |
| MM-0093 | `integration-staging/tests/test_harness_isolation.py` | `examdata/tests/integration/test_harness_isolation.py` | new_file | add_file | deferred_pending_release |
| MM-0094 | `integration-staging/tests/test_legacy_adapters.py` | `examdata/tests/integration/test_legacy_adapters.py` | new_file | add_file | deferred_pending_release |
| MM-0095 | `integration-staging/tests/test_legacy_bridge_contracts.py` | `examdata/tests/integration/test_legacy_bridge_contracts.py` | new_file | add_file | deferred_pending_release |
| MM-0096 | `integration-staging/tests/test_legacy_decisions.py` | `examdata/tests/integration/test_legacy_decisions.py` | new_file | add_file | deferred_pending_release |
| MM-0097 | `integration-staging/tests/test_legacy_parity.py` | `examdata/tests/integration/test_legacy_parity.py` | new_file | add_file | deferred_pending_release |
| MM-0098 | `integration-staging/tests/test_legacy_translate.py` | `examdata/tests/integration/test_legacy_translate.py` | new_file | add_file | deferred_pending_release |
| MM-0099 | `integration-staging/tests/test_node_import_guard.py` | `examdata/tests/integration/test_node_import_guard.py` | new_file | add_file | deferred_pending_release |
| MM-0100 | `integration-staging/tests/test_operations_checkpoints.py` | `examdata/tests/integration/test_operations_checkpoints.py` | new_file | add_file | deferred_pending_release |
| MM-0101 | `integration-staging/tests/test_operations_coverage.py` | `examdata/tests/integration/test_operations_coverage.py` | new_file | add_file | deferred_pending_release |
| MM-0102 | `integration-staging/tests/test_providers_fixtures.py` | `examdata/tests/integration/test_providers_fixtures.py` | new_file | add_file | deferred_pending_release |
| MM-0103 | `integration-staging/tests/test_providers_registry.py` | `examdata/tests/integration/test_providers_registry.py` | new_file | add_file | deferred_pending_release |
| MM-0104 | `integration-staging/tests/test_runner_classification.py` | `examdata/tests/integration/test_runner_classification.py` | new_file | add_file | deferred_pending_release |
| MM-0105 | `integration-staging/tests/test_runner_limits.py` | `examdata/tests/integration/test_runner_limits.py` | new_file | add_file | deferred_pending_release |

## Not merged (excluded) — 92

| staged_path | group | reason |
| --- | --- | --- |
| `integration-staging/frontend/fixtures/PROVENANCE.json` | frontend | staging provenance consumed by B01; not a product file |
| `integration-staging/frontend/PROVENANCE.json` | frontend | staging provenance consumed by B01; not a product file |
| `integration-staging/config/README.md` | config | staging notes; the configuration precedence text is folded into docs/integration-guide.md |
| `integration-staging/tools/_env.sh` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a00_final_checks.sh` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a01_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a01_inventory_routes.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a01_static_inventory.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a01_worksheet_build.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a02_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a03_attribution.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a03_capture_fixtures.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a03_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a04_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a04_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a04_generate_schemas.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a04_roundtrip_fixtures.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a05_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a05_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a05_probe_dispatch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a06_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a06_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a06_probe_runner.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a07_capture_adapter_fixtures.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a07_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a07_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a07_probe_adapters.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a08_capture_fixtures.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a08_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a08_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a08_probe_adapters.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a09_capture_fixtures.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a09_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a09_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a09_probe_catalog.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a10_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a10_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a10_probe_api.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a11_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a11_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a11_probe_binary.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a12_build_registry.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a12_build_worksheet.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a12_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a12_extract_legacy_shapes.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a12_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a12_probe_compat.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a13_capture_fixtures.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a13_close_patch.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a13_final_checks.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a13_frontend_provenance.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a14_build_artifacts.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/a14_rehearsal.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/build_binary_fixtures.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/inspect_module_resolution.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/ledger_update.py` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/tools/run_staged_tests.sh` | tools | Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally. |
| `integration-staging/runtime/a01_preclose_final_checks.txt` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/a12_fc_run1.txt` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/a12_fc_run2.txt` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/a13_final_run1.txt` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/a13_node_tests.txt` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/a13_pytest.txt` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A01_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A02_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A03_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A04_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A05_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A06_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A07_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A08_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A09_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A10_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A11_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A12_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/ledger-patches/A13_close.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/README.md` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/_probe_fw.py` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/a07-invalid.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/a07-undecodable.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/a11_fc2_stdout.txt` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/missing-manifest.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/probe space dir/fake node cli/fake-cli.mjs` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/probe-missing/manifest.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/probe-space-manifest/manifest.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/space dir a06/fake node cli/fake-cli.mjs` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/runtime/tmp/space-manifest.json` | runtime | Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged. |
| `integration-staging/components/fake-node-cli/fake-cli.mjs` | components | Synthetic fixture component for the staged Node runner (fake-cli) and its manifest. The runner and the manifest format merge with src/; the fake component must not be packaged. |
| `integration-staging/components/manifest.json` | components | Synthetic fixture component for the staged Node runner (fake-cli) and its manifest. The runner and the manifest format merge with src/; the fake component must not be packaged. |
| `integration-staging/components/README.md` | components | Synthetic fixture component for the staged Node runner (fake-cli) and its manifest. The runner and the manifest format merge with src/; the fake component must not be packaged. |
| `integration-staging/pytest.ini` | root | Staging test configuration (testpaths, pythonpath=src, private cache dirs). The merged project uses its own test configuration. |
| `integration-staging/README.md` | root | Staging-tree orientation document. Superseded after merge by the proposed docs/ set. |

## Active-owner deferred — 9

| path | reason | revisit_at |
| --- | --- | --- |
| `examdata/src/examdata/materials/**` | Kimi-owned active feature; protected in Phase A (worksheet rows deferred_active_owner) | B05 after explicit human release |
| `examdata/src/examdata/timetable/**` | Kimi-owned active feature (historical timetables); protected in Phase A | B05 after explicit human release |
| `examdata/src/examdata/api/app.py` | shared route module; Kimi edits it concurrently; no staged file replaces it | B04 |
| `examdata/src/examdata/api/{unified,ielts,toefl}.py` | legacy route modules preserved verbatim; the compatibility adapters call them only by contract | B02/B04 |
| `examdata/pyproject.toml, examdata/cli.py, examdata/README.md` | shared project files; protected in Phase A | B02/B10 |
| `frontend/**` | Kimi-owned frontend; the staged copy is reconciled at B06, never overwritten | B06 |
| `ielts-api/**, toefl-api/**` | original Node components: not executed, not copied, not packaged in Phase A | B02 (component packaging) |
| `ielts-data/**, cie-location-batch/**, cie-index-batch-2026-10-01/**, cie-question-crops/**` | business data and stopped batch state; no live database or batch access in Phase A | B08 after a separate data authorization |
| `docs/integration/MASTER_EXECUTION_PLAN_EN.md, docs/integration/EXECUTOR_PROMPT_EN.md, docs/integration/ROUTE_INVENTORY_CURRENT.json, docs/PROJECT_STATUS.md` | governing planning inputs; read-only | B10 (status documents only) |

## Planned original edits — 6 (not applied)

| target_path | packet | base_exists | base_sha256 | change |
| --- | --- | --- | --- | --- |
| `examdata/src/examdata/api/app.py` | B04 | True | `753749fac1361481034e0920c0543e3e621c0d638c21558c73852fd3237fef5d` | register the staged v2 routes in the shared application (include_router / factory hook) without removing or shadowing any legacy route; keep path ordering and operation IDs |
| `examdata/pyproject.toml` | B02 | True | `f8d69e9dc11c66e062f2e8955fa7fbc035d347841b95354d1b052c6a57226a66` | provisional: package-data/packaging delta only if the merge needs it ([tool.setuptools.packages.find] already covers examdata.integration.*); no new runtime dependencies are proposed |
| `examdata/src/examdata/cli.py` | B02/B10 | True | `514f04204f85ee146d5c209d5c1a29c41a5306395ca8e40a5e1a7ee5d6b29292` | provisional: add unified commands only after scanning for command-name conflicts; keep query commands separate from refresh/write commands |
| `frontend/server.mjs` | B06 | True | `05406d3aa9bc308abf9117e13281a3b1f88c18a0d8e2ddac3113cd738eb6e810` | provisional: serve the staged v2 client behind the reversible flag and keep tests/ and fixtures/ out of the static surface |
| `examdata/docs/API.md` | B10 | True | `aa238ecb1988635a278ae84aa4ccba635b3129a0110fd3ba703277aa37393d9d` | provisional: publish the v2 reference and the compatibility summary after the release (plan 9.3) |
| `docs/PROJECT_STATUS.md` | B10 | True | `0bb307bf292169a4a015201863527784806ab2e49444af9b92786f2d07ffe080` | provisional: replace the planning status with the delivered status after the merge |

