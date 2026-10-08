# CIE cieparse 回归报告

样本：199  生成方式：`python tools/run_regression.py`

状态含义：

- `PASS`：封面总分与解析出的分值合计一致。注意这是**自校验**——总分和合计都来自同一份 PDF 的解析结果。
- `WARN`：不一致，或封面读不到总分，但解析器已在 `checks.warnings` 中说明原因（不是静默通过）。
- `FAIL`：校验不通过且没有任何 warning，属于必须修的缺陷。
- `KNOWN`：已登记在 `testdata/manifest.json` 的 `known_failures` 中的已知缺陷。
- `DIFF`：自校验通过或未做自校验，但**跨文档**逐题对照 qp 与 ms 时对不上。
- `NOC`：payload 没有 `checks` 块，解析器**没有做分值校验**（选择题答案表 `mcq_key`、经济结构化评分标准）。既不是通过也不是失败——`PASS` 只用于「校验过且一致」。
- `SKIP`：PDF 未下载。`N/A`：gt/er 类文档没有 header，无分值可比对。

`逐题一致` 列是**跨文档校验**：把 qp 与 ms 两份独立 PDF 的逐题分值对照，比上面的自校验更有说服力。`–` 表示两侧至少有一侧没有数值分值（选择题卷正文不印 `[n]`，或 MS 的分值列未解析），因此不可比，不算不一致。经济卷的 ms 逐题分值是分级给分（Level 制），与 qp 的逐题满分本就不是同一口径，因此经济样本的 `DIFF` 需另行判断。

| 科目 | 文件 | 类型 | 封面总分 | qp合计 | ms合计 | 逐题一致 | 学科字段 | 状态 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| 0580 | 0580_s18_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 0580 | 0580_s18_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 0580 | 0580_s18_ms_11 | ms | 56 |  | 56 | ✔ | part_marks | PASS |  |
| 0580 | 0580_s18_ms_21 | ms | 70 |  | 70 | ✔ | part_marks | PASS |  |
| 0580 | 0580_s18_ms_31 | ms | 104 |  | 104 | ✔ | part_marks | PASS |  |
| 0580 | 0580_s18_ms_41 | ms | 130 |  | 129 | ✘ 7:qp15/ms14 | part_marks | WARN | mark scheme sum 129 does not match total mark 130 |
| 0580 | 0580_s18_qp_11 | qp | 56 | 56 |  | ✔ | – | PASS |  |
| 0580 | 0580_s18_qp_21 | qp | 70 | 70 |  | ✔ | – | PASS |  |
| 0580 | 0580_s18_qp_31 | qp | 104 | 104 |  | ✔ | – | PASS |  |
| 0580 | 0580_s18_qp_41 | qp | 130 | 130 |  | ✘ 7:qp15/ms14 | – | DIFF | qp/ms per-question mismatch |
| 0580 | 0580_s23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 0580 | 0580_s23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 0580 | 0580_s23_ms_11 | ms | 56 |  | 55 | ✘ 21:qp3/ms2 | part_marks | WARN | mark scheme sum 55 does not match total mark 56 |
| 0580 | 0580_s23_ms_21 | ms | 70 |  | 70 | ✔ | part_marks | PASS |  |
| 0580 | 0580_s23_ms_31 | ms | 104 |  | 104 | ✔ | part_marks | PASS |  |
| 0580 | 0580_s23_ms_41 | ms | 130 |  | 126 | ✘ 3:qp13/ms10,9:qp8/ms7 | part_marks | WARN | mark scheme sum 126 does not match total mark 130; 1 rows have no marks: 9(c)(ii) |
| 0580 | 0580_s23_qp_11 | qp | 56 | 56 |  | ✘ 21:qp3/ms2 | – | DIFF | qp/ms per-question mismatch |
| 0580 | 0580_s23_qp_21 | qp | 70 | 70 |  | ✔ | – | PASS |  |
| 0580 | 0580_s23_qp_31 | qp | 104 | 104 |  | ✔ | – | PASS |  |
| 0580 | 0580_s23_qp_41 | qp | 130 | 130 |  | ✘ 3:qp13/ms10,9:qp8/ms7 | – | DIFF | qp/ms per-question mismatch |
| 0580 | 0580_w23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 0580 | 0580_w23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 0580 | 0580_w23_ms_11 | ms | 56 |  | 56 | ✔ | part_marks | PASS |  |
| 0580 | 0580_w23_ms_21 | ms | 70 |  | 70 | ✔ | part_marks | PASS |  |
| 0580 | 0580_w23_ms_31 | ms | 104 |  | 104 | ✔ | part_marks | PASS |  |
| 0580 | 0580_w23_ms_41 | ms | 130 |  | 130 | ✔ | part_marks | PASS |  |
| 0580 | 0580_w23_qp_11 | qp | 56 | 56 |  | ✔ | – | PASS |  |
| 0580 | 0580_w23_qp_21 | qp | 70 | 70 |  | ✔ | – | PASS |  |
| 0580 | 0580_w23_qp_31 | qp | 104 | 104 |  | ✔ | – | PASS |  |
| 0580 | 0580_w23_qp_41 | qp | 130 | 130 |  | ✔ | – | PASS |  |
| 9709 | 9709_s18_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 9709 | 9709_s18_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 9709 | 9709_s18_ms_11 | ms | 75 |  | 75 | ✔ | part_marks | PASS | 4 rows have no marks: 7, 8(b), 9, 10 |
| 9709 | 9709_s18_ms_21 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s18_ms_31 | ms | 75 |  | 75 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s18_ms_41 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s18_ms_51 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s18_ms_61 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s18_ms_71 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s18_qp_11 | qp | 75 | 75 |  | ✔ | – | PASS |  |
| 9709 | 9709_s18_qp_21 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_s18_qp_31 | qp | 75 | 75 |  | ✔ | – | PASS |  |
| 9709 | 9709_s18_qp_41 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_s18_qp_51 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_s18_qp_61 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_s18_qp_71 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_s23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 9709 | 9709_s23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 9709 | 9709_s23_ms_11 | ms | 75 |  | 75 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s23_ms_21 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s23_ms_31 | ms | 75 |  | 75 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s23_ms_41 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s23_ms_51 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s23_ms_61 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_s23_qp_11 | qp | 75 | 75 |  | ✔ | – | PASS |  |
| 9709 | 9709_s23_qp_21 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_s23_qp_31 | qp | 75 | 75 |  | ✔ | – | PASS |  |
| 9709 | 9709_s23_qp_41 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_s23_qp_51 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_s23_qp_61 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_w23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 9709 | 9709_w23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 9709 | 9709_w23_ms_11 | ms | 75 |  | 75 | ✔ | part_marks | PASS |  |
| 9709 | 9709_w23_ms_21 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_w23_ms_31 | ms | 75 |  | 75 | ✔ | part_marks | PASS |  |
| 9709 | 9709_w23_ms_41 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_w23_ms_51 | ms | 50 |  | 52 | ✘ 2:qp7/ms9 | part_marks | WARN | mark scheme sum 52 does not match total mark 50 |
| 9709 | 9709_w23_ms_61 | ms | 50 |  | 50 | ✔ | part_marks | PASS |  |
| 9709 | 9709_w23_qp_11 | qp | 75 | 75 |  | ✔ | – | PASS |  |
| 9709 | 9709_w23_qp_21 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_w23_qp_31 | qp | 75 | 75 |  | ✔ | – | PASS |  |
| 9709 | 9709_w23_qp_41 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 9709 | 9709_w23_qp_51 | qp | 50 | 50 |  | ✘ 2:qp7/ms9 | – | DIFF | qp/ms per-question mismatch |
| 9709 | 9709_w23_qp_61 | qp | 50 | 50 |  | ✔ | – | PASS |  |
| 0625 | 0625_s18_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 0625 | 0625_s18_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 0625 | 0625_s18_ms_11 | ms | 40 |  | 40 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_s18_ms_21 | ms | 40 |  | 40 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_s18_ms_31 | ms | 80 |  | 80 | ✔ | part_marks | PASS |  |
| 0625 | 0625_s18_ms_41 | ms | 80 |  | 85 | ✘ 3:qp6/ms8,5:qp8/ms9,9:qp9/ms11 | part_marks | WARN | mark scheme sum 85 does not match total mark 80 |
| 0625 | 0625_s18_ms_51 | ms | 40 |  | 40 | ✔ | part_marks | PASS |  |
| 0625 | 0625_s18_ms_61 | ms | 40 |  | 40 | ✔ | part_marks | PASS |  |
| 0625 | 0625_s18_qp_11 | qp | 40 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_s18_qp_21 | qp | 40 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_s18_qp_31 | qp |  | 80 |  | ✔ | – | WARN | total mark not found on the cover |
| 0625 | 0625_s18_qp_41 | qp |  | 80 |  | ✘ 3:qp6/ms8,5:qp8/ms9,9:qp9/ms11 | – | WARN | total mark not found on the cover |
| 0625 | 0625_s18_qp_51 | qp |  | 40 |  | ✔ | – | WARN | total mark not found on the cover |
| 0625 | 0625_s18_qp_61 | qp |  | 40 |  | ✔ | – | WARN | total mark not found on the cover |
| 0625 | 0625_s23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 0625 | 0625_s23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 0625 | 0625_s23_ms_11 | ms | 40 |  | 40 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_s23_ms_21 | ms | 40 |  | 40 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_s23_ms_31 | ms | 80 |  | 80 | ✔ | part_marks | PASS |  |
| 0625 | 0625_s23_ms_41 | ms | 80 |  | 80 | ✔ | part_marks | PASS |  |
| 0625 | 0625_s23_ms_51 | ms | 40 |  | 40 | ✔ | part_marks | PASS |  |
| 0625 | 0625_s23_ms_61 | ms | 40 |  | 40 | ✔ | part_marks | PASS |  |
| 0625 | 0625_s23_qp_11 | qp | 40 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_s23_qp_21 | qp | 40 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_s23_qp_31 | qp | 80 | 80 |  | ✔ | – | PASS |  |
| 0625 | 0625_s23_qp_41 | qp | 80 | 80 |  | ✔ | – | PASS |  |
| 0625 | 0625_s23_qp_51 | qp | 40 | 40 |  | ✔ | – | PASS |  |
| 0625 | 0625_s23_qp_61 | qp | 40 | 40 |  | ✔ | – | PASS |  |
| 0625 | 0625_w23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 0625 | 0625_w23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 0625 | 0625_w23_ms_11 | ms | 40 |  | 40 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_w23_ms_21 | ms | 40 |  | 40 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 0625 | 0625_w23_ms_31 | ms | 80 |  | 71 | ✘ 7:qp5/ms4,11:qp8/ms0 | part_marks | KNOWN | cover fields empty: syllabus, component; mark scheme sum 71 does not match total mark 80 |
| 0625 | 0625_w23_ms_41 | ms | 80 |  | 80 | ✔ | part_marks | PASS |  |
| 0625 | 0625_w23_ms_51 | ms | 40 |  | 40 | ✔ | part_marks | PASS |  |
| 0625 | 0625_w23_ms_61 | ms | 40 |  | 40 | ✔ | part_marks | PASS |  |
| 0625 | 0625_w23_qp_11 | qp |  | 0 |  | – | – | KNOWN | cover fields empty: syllabus, component, session; total mark not found on the cover |
| 0625 | 0625_w23_qp_21 | qp |  | 0 |  | – | – | KNOWN | cover fields empty: syllabus, component, session; total mark not found on the cover |
| 0625 | 0625_w23_qp_31 | qp | 80 | 80 |  | ✘ 7:qp5/ms4,11:qp8/ms0 | – | DIFF | qp/ms per-question mismatch |
| 0625 | 0625_w23_qp_41 | qp | 80 | 80 |  | ✔ | – | PASS |  |
| 0625 | 0625_w23_qp_51 | qp | 40 | 40 |  | ✔ | – | PASS |  |
| 0625 | 0625_w23_qp_61 | qp | 40 | 40 |  | ✔ | – | PASS |  |
| 9702 | 9702_s18_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 9702 | 9702_s18_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 9702 | 9702_s18_ms_11 | ms | 40 |  | 40 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 9702 | 9702_s18_ms_21 | ms | 60 |  | 62 | ✘ 1:qp7/ms9 | part_marks | WARN | mark scheme sum 62 does not match total mark 60 |
| 9702 | 9702_s18_ms_31 | ms | 40 |  | 40 | ✔ | part_marks | PASS |  |
| 9702 | 9702_s18_ms_41 | ms | 100 |  | 99 | ✘ 3:qp8/ms7,12:qp15/ms7,13:qp0/ms8 | part_marks | WARN | mark scheme sum 99 does not match total mark 100 |
| 9702 | 9702_s18_ms_51 | ms | 30 |  | 30 | ✔ | part_marks | PASS |  |
| 9702 | 9702_s18_qp_11 | qp | 40 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9702 | 9702_s18_qp_21 | qp |  | 60 |  | ✘ 1:qp7/ms9 | – | WARN | total mark not found on the cover |
| 9702 | 9702_s18_qp_31 | qp |  | 40 |  | ✔ | – | WARN | total mark not found on the cover |
| 9702 | 9702_s18_qp_41 | qp |  | 100 |  | ✘ 3:qp8/ms7,12:qp15/ms7,13:qp0/ms8 | – | WARN | total mark not found on the cover |
| 9702 | 9702_s18_qp_51 | qp |  | 30 |  | ✔ | – | WARN | total mark not found on the cover |
| 9702 | 9702_s23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 9702 | 9702_s23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 9702 | 9702_s23_ms_11 | ms | 40 |  | 40 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 9702 | 9702_s23_ms_21 | ms | 60 |  | 60 | ✔ | part_marks | PASS |  |
| 9702 | 9702_s23_ms_31 | ms | 40 |  | 40 | ✔ | part_marks | PASS |  |
| 9702 | 9702_s23_ms_41 | ms | 100 |  | 100 | ✔ | part_marks | PASS |  |
| 9702 | 9702_s23_ms_51 | ms | 30 |  | 30 | ✔ | part_marks | PASS |  |
| 9702 | 9702_s23_qp_11 | qp |  | 0 |  | – | – | KNOWN | cover fields empty: syllabus, component, session; total mark not found on the cover |
| 9702 | 9702_s23_qp_21 | qp | 60 | 60 |  | ✔ | – | PASS |  |
| 9702 | 9702_s23_qp_31 | qp | 40 | 40 |  | ✔ | – | PASS |  |
| 9702 | 9702_s23_qp_41 | qp | 100 | 100 |  | ✔ | – | PASS |  |
| 9702 | 9702_s23_qp_51 | qp | 30 | 30 |  | ✔ | – | PASS |  |
| 9702 | 9702_w23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 9702 | 9702_w23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 9702 | 9702_w23_ms_11 | ms | 40 |  | 40 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 9702 | 9702_w23_ms_21 | ms | 60 |  | 60 | ✔ | part_marks | PASS |  |
| 9702 | 9702_w23_ms_31 | ms | 40 |  | 40 | ✔ | part_marks | PASS |  |
| 9702 | 9702_w23_ms_41 | ms | 100 |  | 100 | ✔ | part_marks | PASS |  |
| 9702 | 9702_w23_ms_51 | ms | 30 |  | 30 | ✔ | part_marks | PASS |  |
| 9702 | 9702_w23_qp_11 | qp | 40 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9702 | 9702_w23_qp_21 | qp | 60 | 60 |  | ✔ | – | PASS |  |
| 9702 | 9702_w23_qp_31 | qp | 40 | 40 |  | ✔ | – | PASS |  |
| 9702 | 9702_w23_qp_41 | qp | 100 | 100 |  | ✔ | – | PASS |  |
| 9702 | 9702_w23_qp_51 | qp | 30 | 30 |  | ✔ | – | PASS |  |
| 0455 | 0455_s18_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 0455 | 0455_s18_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 0455 | 0455_s18_ms_11 | ms | 30 |  | 30 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 0455 | 0455_s18_ms_21 | ms | 90 |  | 89 | ✘ 1:qp30/ms15,2:qp20/ms14,3:qp20/ms10,4:qp20/ms12,6:qp20/ms4,7:qp20/ms14 | – | DIFF | payload carries no checks block, so no marks check was made; qp/ms per-question mismatch |
| 0455 | 0455_s18_qp_11 | qp | 30 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 0455 | 0455_s18_qp_21 | qp |  | 150 |  | ✘ 1:qp30/ms15,2:qp20/ms14,3:qp20/ms10,4:qp20/ms12,6:qp20/ms4,7:qp20/ms14 | – | WARN | total mark not found on the cover |
| 0455 | 0455_s23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 0455 | 0455_s23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 0455 | 0455_s23_ms_11 | ms | 30 |  | 30 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 0455 | 0455_s23_ms_21 | ms | 90 |  | 48 | ✘ 1:qp30/ms18,2:qp20/ms6,3:qp20/ms6,4:qp20/ms12,5:qp20/ms6 | levels | DIFF | payload carries no checks block, so no marks check was made; qp/ms per-question mismatch |
| 0455 | 0455_s23_qp_11 | qp | 30 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 0455 | 0455_s23_qp_21 | qp | 90 | 110 |  | ✘ 1:qp30/ms18,2:qp20/ms6,3:qp20/ms6,4:qp20/ms12,5:qp20/ms6 | – | DIFF | qp/ms per-question mismatch |
| 0455 | 0455_w23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 0455 | 0455_w23_ms_11 | ms | 30 |  | 30 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 0455 | 0455_w23_ms_21 | ms | 90 |  | 69 | ✘ 1:qp30/ms15,2:qp20/ms15,3:qp20/ms15,4:qp20/ms9,5:qp20/ms15 | – | DIFF | payload carries no checks block, so no marks check was made; qp/ms per-question mismatch |
| 0455 | 0455_w23_qp_11 | qp | 30 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 0455 | 0455_w23_qp_21 | qp | 90 | 110 |  | ✘ 1:qp30/ms15,2:qp20/ms15,3:qp20/ms15,4:qp20/ms9,5:qp20/ms15 | – | DIFF | qp/ms per-question mismatch |
| 9708 | 9708_s18_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 9708 | 9708_s18_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 9708 | 9708_s18_ms_11 | ms | 30 |  | 30 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s18_ms_21 | ms | 40 |  | 62 | ✘ 1:qp20/ms14,4:qp20/ms8 | – | DIFF | payload carries no checks block, so no marks check was made; qp/ms per-question mismatch |
| 9708 | 9708_s18_ms_31 | ms | 30 |  | 30 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s18_ms_41 | ms | 70 |  | 0 | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s18_qp_11 | qp | 30 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s18_qp_21 | qp |  | 80 |  | ✘ 1:qp20/ms14,4:qp20/ms8 | – | WARN | total mark not found on the cover |
| 9708 | 9708_s18_qp_31 | qp | 30 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s18_qp_41 | qp |  | 170 |  | – | – | WARN | total mark not found on the cover |
| 9708 | 9708_s23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 9708 | 9708_s23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 9708 | 9708_s23_ms_11 | ms | 30 |  | 28 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s23_ms_21 | ms | 40 |  | 0 | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s23_ms_31 | ms | 30 |  | 30 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s23_ms_41 | ms | 70 |  | 0 | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s23_qp_11 | qp | 30 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s23_qp_21 | qp | 60 | 100 |  | – | – | PASS |  |
| 9708 | 9708_s23_qp_31 | qp | 30 |  |  | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_s23_qp_41 | qp | 60 | 100 |  | – | – | PASS |  |
| 9708 | 9708_w23_er | er |  |  |  |  | papers | N/A | no assertions defined |
| 9708 | 9708_w23_gt | gt |  |  |  |  | components, options, syllabus, title | N/A | no assertions defined |
| 9708 | 9708_w23_ms_11 | ms | 30 |  | 30 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_w23_ms_21 | ms | 60 |  | 0 | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_w23_ms_31 | ms | 30 |  | 30 | – | answer_key | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_w23_ms_41 | ms | 60 |  | 0 | – | – | NOC | payload carries no checks block, so no marks check was made |
| 9708 | 9708_w23_qp_11 | qp |  | 0 |  | – | – | KNOWN | cover fields empty: syllabus, component, session; total mark not found on the cover |
| 9708 | 9708_w23_qp_21 | qp | 60 | 100 |  | – | – | PASS |  |
| 9708 | 9708_w23_qp_31 | qp |  | 0 |  | – | – | KNOWN | cover fields empty: syllabus, component, session; total mark not found on the cover |
| 9708 | 9708_w23_qp_41 | qp | 60 | 100 |  | – | – | PASS |  |

## 汇总

| 状态 | 数量 |
|---|---|
| PASS | 93 |
| WARN | 18 |
| FAIL | 0 |
| KNOWN | 6 |
| DIFF | 11 |
| NOC | 36 |
| SKIP | 0 |
| N/A | 35 |

## 分科汇总

| 科目 | 样本 | PASS | WARN | FAIL | KNOWN | DIFF | NOC | SKIP | N/A | 通过率 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0580 | 30 | 18 | 3 | 0 | 0 | 3 | 0 | 0 | 6 | 75% |
| 9709 | 44 | 36 | 1 | 0 | 0 | 1 | 0 | 0 | 6 | 95% |
| 0625 | 42 | 17 | 5 | 0 | 3 | 1 | 10 | 0 | 6 | 65% |
| 9702 | 36 | 18 | 6 | 0 | 1 | 0 | 5 | 0 | 6 | 72% |
| 0455 | 17 | 0 | 1 | 0 | 0 | 5 | 6 | 0 | 5 | 0% |
| 9708 | 30 | 4 | 2 | 0 | 2 | 1 | 15 | 0 | 6 | 44% |

通过率 = `PASS` / (样本 − `SKIP` − `N/A` − `NOC`)：只在**真正做过校验**的样本上计算，`NOC` 与 `N/A` 不拉低也不抬高。

## FAIL 明细

无。

## 未做分值校验（NOC）

这些样本的 payload 没有 `checks` 块，解析器没有做任何分值校验，因此不能当作通过：

| 科目 | 文件 | 类型 | 封面总分 | 解析出的合计 |
|---|---|---|---|---|
| 0625 | 0625_s18_ms_11 | ms | 40 | 40 |
| 0625 | 0625_s18_ms_21 | ms | 40 | 40 |
| 0625 | 0625_s18_qp_11 | qp | 40 | – |
| 0625 | 0625_s18_qp_21 | qp | 40 | – |
| 0625 | 0625_s23_ms_11 | ms | 40 | 40 |
| 0625 | 0625_s23_ms_21 | ms | 40 | 40 |
| 0625 | 0625_s23_qp_11 | qp | 40 | – |
| 0625 | 0625_s23_qp_21 | qp | 40 | – |
| 0625 | 0625_w23_ms_11 | ms | 40 | 40 |
| 0625 | 0625_w23_ms_21 | ms | 40 | 40 |
| 9702 | 9702_s18_ms_11 | ms | 40 | 40 |
| 9702 | 9702_s18_qp_11 | qp | 40 | – |
| 9702 | 9702_s23_ms_11 | ms | 40 | 40 |
| 9702 | 9702_w23_ms_11 | ms | 40 | 40 |
| 9702 | 9702_w23_qp_11 | qp | 40 | – |
| 0455 | 0455_s18_ms_11 | ms | 30 | 30 |
| 0455 | 0455_s18_qp_11 | qp | 30 | – |
| 0455 | 0455_s23_ms_11 | ms | 30 | 30 |
| 0455 | 0455_s23_qp_11 | qp | 30 | – |
| 0455 | 0455_w23_ms_11 | ms | 30 | 30 |
| 0455 | 0455_w23_qp_11 | qp | 30 | – |
| 9708 | 9708_s18_ms_11 | ms | 30 | 30 |
| 9708 | 9708_s18_ms_31 | ms | 30 | 30 |
| 9708 | 9708_s18_ms_41 | ms | 70 | – |
| 9708 | 9708_s18_qp_11 | qp | 30 | – |
| 9708 | 9708_s18_qp_31 | qp | 30 | – |
| 9708 | 9708_s23_ms_11 | ms | 30 | 28 |
| 9708 | 9708_s23_ms_21 | ms | 40 | – |
| 9708 | 9708_s23_ms_31 | ms | 30 | 30 |
| 9708 | 9708_s23_ms_41 | ms | 70 | – |
| 9708 | 9708_s23_qp_11 | qp | 30 | – |
| 9708 | 9708_s23_qp_31 | qp | 30 | – |
| 9708 | 9708_w23_ms_11 | ms | 30 | 30 |
| 9708 | 9708_w23_ms_21 | ms | 60 | – |
| 9708 | 9708_w23_ms_31 | ms | 30 | 30 |
| 9708 | 9708_w23_ms_41 | ms | 60 | – |

## 跨文档逐题不一致（DIFF）

- `0580/0580_s18_qp_41`：✘ 7:qp15/ms14
- `0580/0580_s23_qp_11`：✘ 21:qp3/ms2
- `0580/0580_s23_qp_41`：✘ 3:qp13/ms10,9:qp8/ms7
- `9709/9709_w23_qp_51`：✘ 2:qp7/ms9
- `0625/0625_w23_qp_31`：✘ 7:qp5/ms4,11:qp8/ms0
- `0455/0455_s18_ms_21`：✘ 1:qp30/ms15,2:qp20/ms14,3:qp20/ms10,4:qp20/ms12,6:qp20/ms4,7:qp20/ms14
- `0455/0455_s23_ms_21`：✘ 1:qp30/ms18,2:qp20/ms6,3:qp20/ms6,4:qp20/ms12,5:qp20/ms6
- `0455/0455_s23_qp_21`：✘ 1:qp30/ms18,2:qp20/ms6,3:qp20/ms6,4:qp20/ms12,5:qp20/ms6
- `0455/0455_w23_ms_21`：✘ 1:qp30/ms15,2:qp20/ms15,3:qp20/ms15,4:qp20/ms9,5:qp20/ms15
- `0455/0455_w23_qp_21`：✘ 1:qp30/ms15,2:qp20/ms15,3:qp20/ms15,4:qp20/ms9,5:qp20/ms15
- `9708/9708_s18_ms_21`：✘ 1:qp20/ms14,4:qp20/ms8

## 与上次报告对比

- 上次报告样本数：199
- 新增 FAIL：0

