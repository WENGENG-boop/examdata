# IELTS 剩余缺口报告（IELTS_REMAINING_GAPS）

- 生成: 2026-10-05（S17）
- 数据集 revision: `rev-8b21015ab64bb73c`；run: `ielts-data/runs/20261003T140007Z-repair`
- 语义声明：本文件只记录**真实缺口**（本机实测产物中的缺失、冲突、未核验、未对齐项），不生成占位数据、不猜测答案。所有计数可由下列 JSON/证据文件复算：
  - 全量覆盖: `ielts-data/manifests/rev-8b21015ab64bb73c/coverage.json` / `coverage.md`（370 units 明细）
  - 题目索引: `ielts-data/indexes/rev-8b21015ab64bb73c/questions.json`（stats 段）
  - 全量审计: `ielts-data/runs/full-audit/`（matrix.json / errors.jsonl / questions.jsonl）
  - 音频目录: `ielts-data/runs/20261003T140007Z-repair/audio/audio-catalog.json`
  - 对齐产物: `ielts-data/runs/20261003T140007Z-repair/alignment/`（33 identity + summary.json）
  - 恢复 checkpoint: `ielts-data/runs/20261003T140007Z-repair/checkpoint.json`

## 0. 统计总览（当前真实完成度）

| 维度 | 数字 | 说明 |
| --- | --- | --- |
| coverage units | 370 | complete **0** / partial 168 / not_extracted 154 / unverified 48 |
| 题目索引 | 6724 题 | answer attached 6717 / **missing 6 / empty 1**；content complete 6589 / partial 39 / missing_content 46 / missing_options 25 / missing_asset 25 |
| 分类 | 6678 classified / **unknown 46** | unknown 全部为 pte 页 no_group + missing_content |
| 全量审计 | combos 168 | errors 1（expected_assets_unmatched）；assets 1936（verified_file 80 / external_only 1856 / broken 0）；audio 336/336 hash 校验通过 |
| 音频目录 | 362 条 | available 320 / **verified 16** / **candidate 26（未下载核验）** |
| 音频逐题对齐 | 33 identity 产物、331 题 | **verified 66**（全部为 cam21）；其余 unverified |
| 官方核验 | 2 条裁决 | 仅 b9t1r 6/40 题有官方核验；b10t1r 冒烟 38/1/1 |
| PDF | 册 1–19 完整 | **册 20 抢先版 34 页 / 册 21 无本地整册** |

---

## G1. 答案槽位源缺口（7 槽，保留不移位，不移位=不打乱题号）

| identity | skill | Q | gap_kind | expected | observed | source attempts | raw/PDF hash | reason | next_step | needs_external |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cambridge:1:shared:listening:1:P4 | listening | 41 | answer_missing | 剑1 T2 听力为 41 题特殊卷；Q41 属 "in any order" 组 | 源答案键无 Q41 独立槽 | pte raw-127 系列 + 官方答案页 book1 p136 | book_1.pdf（`tmp_audit_ielts/downloads/book_1.pdf`，28,252,883 B） | 原书答案键本身未列该槽（41 题设计），非抓取丢失 | 保留空槽；如获得官方答案页可补 "eat lots/eat most either way round" 备注为组语义 | 是（官方答案页） |
| cambridge:1:shared:listening:2:P4 | listening | 40 | answer_missing | Q40 答案存在 | 空 | pte raw + 答案页 book1 p140 | 同上 | 同上（Q40/41 图页组 41 eat lots//eat most either way round） | 同上 | 是 |
| cambridge:1:shared:listening:2:P4 | listening | 41 | answer_missing | 同上 | 空 | 同上 | 同上 | 同上 | 同上 | 是 |
| cambridge:1:academic:reading:2:P3 | reading | 41 | answer_missing | 剑1 T2 阅读 Q41（41 题卷） | 空 | pte raw | book_1.pdf | 原书 41 题设计，答案键未含 | 保留空槽 | 是 |
| cambridge:1:shared:listening:4:P4 | listening | 41 | answer_missing | 存在 | 空 | pte raw | book_1.pdf | 同上 | 保留空槽 | 是 |
| cambridge:1:shared:listening:4:P4 | listening | 42 | answer_missing | 存在 | 空 | pte raw | book_1.pdf | 同上 | 保留空槽 | 是 |
| cambridge:10:academic:reading:1:P3 | reading | 34 | answer_empty | PDF 答案键 Q34=F | 源侧空值（PDF 键=F 已视觉核验） | compare-official 冒烟 pdf_only=1 | book_10.pdf sha256=`3f1c532893532971…ca129c82` | 源 pte 答案侧空、PDF 侧有值；保持原样不猜测 | 已由 compare-official 记为 pdf_only；如需官方裁决可用 compare 输出 | 是（官方裁决） |

证据：`evidence/S06d-missing-resolution.json`（a_missing_cases=5/slots=7、empty_slots=1）、`evidence/s06-book10-t1-reading-key.json`、S07 冒烟 `scratch/s07/compare-smoke-out.json`（40 题：match=38 / conflict=1 / pdf_only=1）。

## G2. 预期资产未匹配（1）

| identity | skill | group | gap_kind | expected | observed | source attempts | hashes | reason | next_step | needs_external |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cambridge:1:shared:listening:2:P4 | listening | Q40–41 diagram | expected_assets_unmatched | Complete the diagram 图（evidence p45） | matched_assets=0 | 资产索引 + raw 扫描 | book_1.pdf | 原书图页未在可得 raw/资产中匹配到该图 | 需官方 PDF 图页裁剪或替代源图 | 是（官方 PDF 图） |

证据：`ielts-data/runs/full-audit/errors.jsonl`（kind=expected_assets_unmatched，item_id=cambridge:1:shared:listening:2:P4:c1-93ba03c1）。

## G3. unknown 题型 46 题（无 group / missing_content，不能伪造判型）

| book/skill/test:Part | 数量 | gap_kind | observed | reason | next_step | needs_external |
| --- | --- | --- | --- | --- | --- | --- |
| book1/listening/1:P4 | 1 | classification_unknown | pte 页、无 group、无 prompt、missing_content | no_group | 需官方/替代源该页正文以判型 | 是 |
| book1/listening/2:P4 | 2 | 同上 | 同上 | 同上 | 同上 | 是 |
| book1/listening/4:P3 | 6 | 同上 | 同上 | 同上 | 同上 | 是 |
| book1/listening/4:P4 | 2 | 同上 | 同上 | 同上 | 同上 | 是 |
| book1/reading/2:P2 | 4 | 同上 | 同上 | 同上 | 同上 | 是 |
| book1/reading/2:P3 | 1 | 同上 | 同上 | 同上 | 同上 | 是 |
| book3/reading/2:P1 | 5 | 同上 | 同上 | 同上 | 同上 | 是 |
| book8/reading/3:P1 | 4 | 同上 | 同上 | 同上 | 同上 | 是 |
| book11/reading/2:P2 | 7 | 同上 | 同上 | 同上 | 同上 | 是 |
| book11/reading/3:P1 | 5 | 同上 | 同上 | 同上 | 同上 | 是 |
| book12/listening/7:P3 | 6 | 同上 | 同上 | 同上 | 同上 | 是 |
| book17/listening/3:P1 | 3 | 同上 | 同上 | 同上 | 同上 | 是 |

合计 46 题，全部 content_status=missing_content、answer_status∈{attached,missing}、classification_reason=no_group。证据：`evidence/S12-unknown46-composition.txt`；索引 stats.by_classification_status.unknown=46。

## G4. missing_options（25 题，选项未随源页面提供）

| identity | Q 数 | gap_kind | observed | next_step | needs_external |
| --- | --- | --- | --- | --- | --- |
| cambridge:1:shared:listening:3:P1 | 1 | missing_options | 选项列表缺失 | 需官方/替代源选项页 | 是 |
| cambridge:1:shared:listening:3:P3 | 5 | missing_options | 同上 | 同上 | 是 |
| cambridge:2:academic:reading:1:P3 | 8 | missing_options | 同上 | 同上 | 是 |
| cambridge:3:academic:reading:3:P1 | 6 | missing_options | 同上 | 同上 | 是 |
| cambridge:3:academic:reading:4:P1 | 5 | missing_options | 同上 | 同上 | 是 |

合计 25（索引 stats.by_content_status.missing_options=25）。

## G5. missing_asset（25 题，题组所需图片/表格资产缺失）

| identity | Q 数 | gap_kind | observed | next_step | needs_external |
| --- | --- | --- | --- | --- | --- |
| cambridge:5:shared:listening:3:P2 | 3 | missing_asset | 地图/图表资产未匹配 | 需官方 PDF 裁剪 | 是 |
| cambridge:9:academic:reading:1:P3 | 6 | missing_asset | 同上（b9t1r 另有 assets 6 未匹配） | 同上 | 是 |
| cambridge:12:shared:listening:6:P3 | 5 | missing_asset | 同上 | 同上 | 是 |
| cambridge:16:academic:reading:1:P1 | 6 | missing_asset | 同上 | 同上 | 是 |
| cambridge:19:shared:listening:3:P3 | 5 | missing_asset | 同上 | 同上 | 是 |

合计 25（索引 stats.by_content_status.missing_asset=25）。全量资产统计：verified_file 80 / external_only 1856 / broken 0（`full-audit/matrix.json`）。

## G6. partial 内容（39 题，正文/题面不完整）

| identity | Q 数 |
| --- | --- |
| cambridge:1:shared:listening:1:P1 | 3 |
| cambridge:1:shared:listening:3:P1 | 1 |
| cambridge:1:shared:listening:4:P1 | 5 |
| cambridge:1:academic:reading:2:P2 | 7 |
| cambridge:2:shared:listening:3:P3 | 4 |
| cambridge:2:shared:listening:4:P4 | 5 |
| cambridge:3:shared:listening:1:P4 | 1 |
| cambridge:3:shared:listening:2:P4 | 3 |
| cambridge:3:shared:listening:4:P4 | 2 |
| cambridge:3:academic:reading:1:P1 | 4 |
| cambridge:4:academic:reading:1:P3 | 3 |
| cambridge:7:shared:listening:3:P2 | 1 |

合计 39（索引 stats.by_content_status.partial=39）。这些题组已有部分正文/题面，但未达到 complete 判定；不标 complete。

## G7. PDF / 版次缺口（未核实版次与整册不可用）

| identity | gap_kind | expected | observed | reason | next_step | needs_external |
| --- | --- | --- | --- | --- | --- | --- |
| cambridge:9,16,18,19,20（整册） | pdf_no_text_layer | 可提取文字层以核验 GT/Writing/Speaking 内容 | 无文字层（扫描版），不能确认 GT 阅读/写作/口语内容 | 无文字层册不导入（如实记 pdf_no_text_layer） | 需 OCR 或官方文字版 | 是 |
| cambridge:20 T2–T4 | pdf_preview_only | 整册 PDF | 本地 `book_20.pdf` 为 34 页抢先版（仅 Test1 部分），T2–T4 为 images-only（34/35/31/30 页、text_chars=0） | 抢先版不得当整册 | 需官方整册 PDF | 是 |
| cambridge:21（整册） | pdf_missing | 本地整册 PDF | 无本地 PDF；仅社区镜像直链（未本地核验，44,148,624 B 声称） | 未下载核验 | 可下载镜像并核验 hash/页数后升级 | 是 |
| general 全册缺口（S14 C4） | 36 条 | GT 阅读/写作/口语可核验 | 6 册 × 6 项 = 36：册 9/16/18/19/20 各 reading:gt-status + writing:gt-status + speaking:1–4 = 无文字层；册 21 同 6 项 = 无本地 PDF | 真实缺口（refresh exit 1 诚实上报） | 获取文字层/整册 PDF 后重跑 refresh | 是 |
| academic writing/speaking（S14 C5） | pdf_verified 120 / pdf_no_text_layer 40 / pdf_missing 8 | — | 同上册原因 | 同上 | 同上 | 是 |

`books_pdf_complete = [1..19]`；book20/21 = false（coverage.summary）。证据：`evidence/S14-cmd4-refresh-general.txt`、`S14-cmd5-refresh-writing-speaking.txt`、`evidence/S06-book20-structure.json`。

## G8. 音频未下载 / 未验证（26 条 candidate，full_test 派生）

| identity（26 条） | gap_kind | observed | reason | next_step | needs_external |
| --- | --- | --- | --- | --- | --- |
| cambridge:1:shared:listening:1–4 | audio_candidate | maslow 全卷文件（full_test 派生），无独立 per-Part 文件 | 未下载核验；不能按 identity 直接绑定 Part | 下载后按 Part 切分并核验 hash/时长 | 是 |
| cambridge:2:shared:listening:1–4 | 同上 | 同上 | 同上 | 同上 | 是 |
| cambridge:4:shared:listening:1–4 | 同上 | 同上 | 同上 | 同上 | 是 |
| cambridge:7:shared:listening:3 | 同上 | 同上 | 同上 | 同上 | 是 |
| cambridge:16:shared:listening:1 | 同上 | 同上 | 同上 | 同上 | 是 |
| cambridge:18:shared:listening:1–4 | 同上 | 同上 | 同上 | 同上 | 是 |
| cambridge:19:shared:listening:1–4 | 同上 | 同上 | 同上 | 同上 | 是 |
| cambridge:20:shared:listening:1–4 | 同上 | 同上 | 同上 | 同上 | 是 |

目录统计：362 条（available 320 / verified 16 / candidate 26）。candidate 的 `scope=full_test`、`part=null`，属未下载核验的候选（不是可用音频）。证据：`audio/audio-catalog.json`。

## G9. 音频逐题对齐未完成（336 Part 中仅 33 有对齐产物）

| 范围 | observed | reason | next_step | needs_external |
| --- | --- | --- | --- | --- |
| 336 个听力 Part | 336/336 音频 hash 校验通过（tree-check） | — | — | — |
| 对齐产物覆盖 | 33 identity（cam21 16 + b3 t2–t4 12 + b1t2 4 + b20t2 1）；331 题 | 仅对已有身份+标签来源的 Part 运行对齐 | 其余 Part 需先解决音频身份（G8）或标签来源 | 部分 |
| verified 窗 | 66（全部 cam21：T1 13 / T2 15 / T3 19 / T4 19） | 有 gold 标签的 160 题中 66 题达成 verified（其余 unverified） | 需要 gold/人工标签继续核验 | 是 |
| b1t2 / b3 t2–t4 / b20t2（17 Part） | 0 verified（ASR 强制对齐，无 gold 标签） | 无可靠标签 → 如实 unverified，未生成假 verified 区间 | 需 gold 标签或人工审听 | 是 |
| 严格 no_match（2 处） | cam21 t1s4 Q31（metals vs 词干 metal）、t3s4 Q33（holidays vs holiday）answer_form_mismatch score=0 | 词干在窗内但不放宽比较器 | 保持 no_match；如需收录需人工裁决 | 是（人工裁决） |

对齐方法：候选/上下文/动态规划 + ASR 强制对齐（whisperx 3.8.6 / faster-whisper 1.2.1 / whisper-small + wav2vec2 align）；时间戳校验音频 hash + 时钟基准（clock_valid）。证据：`alignment/summary.json`、`alignment/cambridge_21_*.json`、`scratch/s10-gold-crosscheck-dry.json`（problems=2）、`evidence/S10-summary.md`。

## G10. Writing / Speaking 开放题（不设唯一答案分母）

| 范围 | units | gap_kind | observed | next_step | needs_external |
| --- | --- | --- | --- | --- | --- |
| writing/academic | 84 | open_response_or_not_extracted | 开放题；样例答案不标唯一标准答案 | 如需评分样例需官方 rubric/样卷 | 是 |
| speaking/shared | 84 | open_response_or_not_extracted | 同上 | 同上 | 是 |
| writing/general | 17 | open_response_or_not_extracted | 同上（另有 36 条 general 内容缺口，见 G7） | 同上 | 是 |

coverage.by_skill：reading/academic 84、listening/shared 84、writing/academic 84、speaking/shared 84、reading/general 17、writing/general 17（合计 370）。

## G11. 官方核验未完成（S18 后：15 册 119 cell 已比对；book11 作废；其余限制如下）

| identity / 范围 | gap_kind | expected | observed | next_step | needs_external |
| --- | --- | --- | --- | --- | --- |
| 15 册（1–8、10–15、17）× 8 cell = 119 cell | compare_done_20261005 | 官方 PDF 逐题核验 | 已比对（EXIT=0）：total 4764 / match 2833 / conflict 985 / pdf_only 6 / answer_only 939 / missing 1 / unverified 946；证据 `evidence/S18-official-compare.json` + `.md` | conflict 985 与 answer_only 939 的逐条复核（按分类抽样） | 部分 |
| cambridge:10:academic:reading:1 | compare_done_strict | 全 40 题官方核验 | S18 严格重跑 match=36 / conflict=3（Q9/Q10/Q12 变体形）/ pdf_only=1（Q34）；取代 S06 冒烟值（match=38 / conflict=1 Q22，Q22 现为 match） | 变体形确认裁决（earthquake(s) / 4 sides / verandas） | 否 |
| cambridge:11（全册 8 cell） | rotation_confirmed | 官方逐题核验 | 页→套旋转已确证：pte-N 持书 t(N−1) 答案（回绕），索引忠实复制来源、逐格 0 差异（34/34…40/40）；231 条冲突作废为核验证据；G14 两项已闭环至本地证据上限：t4R 19–26 部分裁决（印块版式异常确证；意图值重建，Q24 保留 C/D 双值）、pte-4L unverified（512 页 OCR 0 真命中） | 两项外部核验：不同印次/勘误页；pte 源独立键（见 G14） | 部分 |
| 册 9/16/18/19/20 | no_text_layer | 官方逐题核验 | 无文字层 PDF，未纳入 S18 比对 | 需 OCR 或外部文字层来源 | 是 |
| 册 21（cam21） | same_source | 官方逐题核验 | 本地无 PDF；cam21 镜像源与索引同源，非独立核验 | 需独立官方 PDF | 是 |
| GT reading/listening（各册） | not_indexed | 官方逐题核验 | GT 无索引题目，不可比 | 先建 GT 索引 | 是 |
| cambridge:9:academic:reading:1（Q21–26 / Q18–20） | official_verified 6/40 | 官方 PDF 逐题核验 | 已核验 6 题（gv-01/gv-02）；其余 34 题未比对（册 9 无文字层） | OCR 后纳入下一批 compare | 是 |
| 索引 official_verifications | not_written_back | — | S18 compare 证据未写回索引（仍 2 条 gv-01/gv-02） | 按裁决流程写回（不把未复核冲突直接入库） | 否 |

answer_only 939 集中于 b13/14/15（176/177/146）；`//` 多值口径未进比较器；待复核样本：book12 t5 R Q4（pdf TRUE vs ans tue）、Q38（NOT GVEN vs yes）、book15 t4 R Q7。

## G12. 跨源冲突保留（3 条，原值与裁决来源均保留）

| identity | kind | from | to/canonical | 处理 |
| --- | --- | --- | --- | --- |
| cambridge:9:academic:reading:1:P2:G2（Q21–26） | classification_conflict | true_false_not_given（pool_overrides_instruction） | yes_no_not_given | 裁决 gv-01（官方 PDF 指令页 p16/printed 24 证据） |
| cambridge:9:academic:reading:1:P2:G1（Q18–20） | word_limit_conflict | 源词数限制 | 官方词数限制 | 裁决 gv-02 |
| cambridge:12（整册 test 编号） | test_numbering | practicepteonline 1–4 | book-internal 5–8（mapping 1→5…） | 保留双编号，映射已记录 |

证据：索引 `cross_source_conflicts`（3 条）；`evidence/S07-summary.md`（45 条裁决 + 7 条窄修正保留）。

## G13. S07 遗留（compare-official 未接入 audit-all）

| 项 | observed | reason | next_step |
| --- | --- | --- | --- |
| `tools/compare-official.mjs` 未接入 `audit-all` 自动流程 | CLI 已暴露（S13）；S18 已产出 119 cell 比对证据（`evidence/S18-official-compare.json` + `.md`），审计流水线仍未调用 | 逐题 PDF 值未持久化为 audit 输入（避免伪造对比） | 将 official-keys 逐题值持久化后接入 audit-all |

## G14. book11 页→套错位重比对（S18 调查 → 2026-10-05 完成；旋转确证，231 条冲突作废；两项跟进已闭环至本地证据上限）

**结论**: 官方 PDF 页序为书内实际印刷顺序；答案旋转发生在来源侧（pte-11 抓取源套号与书内印刷套号存在偏移）：pte-N 持书 t(N−1) 答案（N=1 回绕到 t4）。索引忠实复制来源（pte），只登记映射、不修改索引数据。原 231 条冲突作废为核验证据。两项跟进（2026-10-05）：t4R 19–26 部分裁决（印块版式异常确证；意图值重建；Q24 保留 C/D 双值）、pte-4L unverified（5 册 512 页 OCR 检索 0 真命中）。

| 项 | 结论 | 证据 |
| --- | --- | --- |
| 旋转规则 | pte-2→书 t1、pte-3→书 t2、pte-4→书 t3、pte-1→书 t4（回绕）；书 t4L==pte-1L（全等）、书 t4R==pte-1R（1–18、27–40）、书 t3R==pte-4R 30/30 | 四路对照 `scratch/s18/check-align.py/.txt` |
| 索引映射 | INDEX tN == pte-N 逐格精确（34/34、40/40、40/40、33/33、30/30、33/33、36/36、40/40，0 差异）⇒ 索引 tN 持书 t(N−1) 答案；索引含 pte JSON 缺失值（t1L 21–26=B,D,A,B,B,E；t4L 21–24=B,D,A,E，后者与书 t4L B,D,A,B 仅 21–23 同） | `scratch/s18/index-rotation-check.py/.txt` |
| 目视裁决 | 页 121=t3L 完整 40 行、页 123=t4L（21&22/23&24/25&26 IN EITHER ORDER 配对）、页 124=t4R 40 行；页 123 展开 == INDEX t1L S3 逐格一致 | 裁剪图 13 张（`scratch/s18/page12{1,3,4}-crop-*.png`；sha256 见证据文件） |
| 保留冲突（双值保留） | ① t4R Q9：书 A vs pte B；② t2R Q5：书 FALSE vs pte C；另 t4R Q24 双值（C 主依据 vs D pte 单反源，见下行） | `evidence/S18-book11-remap.md`（保留冲突节） |
| t4R 19–26 印次核验（部分裁决，2026-10-05） | 印块版式异常确证：错位模型 印块[21..26]==意图[20..25] 6/6 + 两处组内非法值（印块 19=D、24=FALSE）；意图值重建 [19 NG,20 T,21 NG,22 T,23 F,24 C,25 A,26 E]（20–23/25 三方一致：错位模型+pte-1R+语义）；Q24 双值保留（C=错位模型+语义主依据 vs D=pte 单反源）；未官方核验（本机唯一印次） | `evidence/S18-book11-remap-followup.md` §1 |
| pte-4L 定源（unverified，2026-10-05） | 对象=practicepteonline "IELTS Listening Test 80"（page_id 2943，audio 80_we.mp3）；5 册无文字层 OCR 300dpi 512 页（book9 165/16 74/18 71/19 72/20 t1–t4 34+35+31+30）+ 31 PRIMARY + 20 SECONDARY 模式全资源检索 0 真命中（2 条 PRIMARY 命中均假阳性：book18 页12 'car'+'Goes' 拼接 argo（公交表单）、book20-t2 页19 North Carolina（MLB/ABS 棒球文））；域词仅现于其自身来源 | `evidence/S18-book11-remap-followup.md` §2 |
| 提取缺陷清单（本地侧，未改数据） | t4L S2 +1 移、t4R 1–9 −1 移、t4L S1 全丢、t4R 14–26/29/31 缺、t4R 27 'VJ'→vi、37 'ZO'→no、t2L Q38 'cuved'、t2R Q16 'vili'/Q36 'ZO'、t3L birds/flowers 丢弃、mushrooms 误配 Q3、t4L Q40 'paymentpayments'、页 124 原始层 15/16 互换（更正：实为提取工具配对偏移假象，非原书异常，见 followup §1.9） | `evidence/S18-book11-remap.md`（缺陷节）+ followup §1.9 |

- 证据文件: `evidence/S18-book11-remap.md`（sha256 1e58248cd19b986175a3c9f00268aa969b5486cc4b138efb9771629cedd9e6aa）；跟进 `evidence/S18-book11-remap-followup.md`（sha256 3b877380b5dac7a5eb98cbf0abcc36abe2a27ffcbaacfbc8a783e2bb621da96e）；旧矩阵 `evidence/S18-book11-shift-check.txt`（96fd90ee…4a49a0）。
- 下一步（可执行，均需外部）: ① t4R 19–26：不同印次/勘误页或独立来源核验（本机唯一 book_11.pdf；official-keys 该册 t4R 仅 24 条且 19–26 全缺）；② pte-4L：practicepteonline "IELTS Listening Test 80" 的来源册/套信息与独立答案键（本地 512 页 OCR + 全资源检索 0 真命中）。
- 状态: done（本地可做范围闭环；t4R 19–26 部分裁决、pte-4L unverified，均如实保留）。

## 恢复与复核命令

```bash
# 复核本报告全部数字（本地、零网络）
cd C:/Users/weo/Desktop/api
python - <<'PY'
import json
c=json.load(open('ielts-data/manifests/rev-8b21015ab64bb73c/coverage.json',encoding='utf-8'))
print(c['summary']['units'], c['summary']['unit_status'])
i=json.load(open('ielts-data/indexes/rev-8b21015ab64bb73c/questions.json',encoding='utf-8'))
print(i['stats']['by_answer_status'], i['stats']['by_content_status'], i['stats']['by_classification_status'])
PY

# 继续推进某一缺口的参考命令
node ielts-api/tools/compare-official.mjs --identity book=9,test=1,skill=reading --pdf <pdf_keys.json> --answers <answers.json> --out <out.json>
node ielts-api/tools/run-alignment.mjs --identity cambridge:21:shared:listening:1:P4 --out ielts-data/runs/20261003T140007Z-repair/alignment
node ielts-api/tools/refresh.mjs --books 20,21 --variant academic --skills reading,listening --resume
```

- 需要外部资源的缺口统一标记 `needs_external=true`：官方整册 PDF（册 20 T2–T4、21）、无文字层册 OCR/文字版（9/16/18/19/20）、官方答案页（剑1 41 题卷）、gold 音频标签或人工审听（17 个无标签 Part）、官方逐题核验（其余全部 units）。
- 未音频对齐 = 未验；未官方核验 = unverified；缺内容 = source_missing/missing_content。以上均不得在汇总中计为 complete。
