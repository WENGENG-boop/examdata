# 雅思修复实施结果报告（IELTS_IMPLEMENTATION_RESULT.md）

- 工作区: `C:/Users/weo/Desktop/api`
- 数据 revision: `rev-8b21015ab64bb73c`（`ielts-data/indexes/current` 与 `ielts-data/manifests/current` 同指该 revision）
- run: `20261003T140007Z-repair` ｜ 日期: 2026-10-05 (UTC+8)
- 计划: `docs/ielts/IELTS_REPAIR_IMPLEMENTATION_PLAN.md`（S01–S17）｜ 审计: `docs/ielts/IELTS_COMPLETENESS_AUDIT_20261003.md`（A01–A16）
- 执行清单: `docs/ielts/EXECUTION_CHECKLIST.md`（S01–S17 逐项命令、退出码、证据）
- 剩余缺口: `docs/ielts/IELTS_REMAINING_GAPS.md`
- 边界遵守: 未改 CIE/Edexcel 业务文件（adapters/markscheme/specs changed=0）；未改生产数据库；未重启 8000 服务；未推送/部署；雅思新数据全部落在独立 `ielts-data/`（`EXAMDATA_IELTS_DATA_DIR`）。

---

## 1. 修改文件清单

### 1.1 ielts-api（主业务；共 84 文件，其中 82 个为本次变更并同步另一副本）

- 模块（28）: `adjudications.mjs` `alignment-provider.mjs` `answer-matcher.mjs` `audio-catalog.mjs` `audio-matcher.mjs` `book3-listening.mjs` `cam21.mjs` `catalog.mjs` `coverage.mjs` `data-store.mjs` `fetch-source.mjs` `html-questions.mjs` `ielts-api.mjs` `ielts-cli.mjs` `iprog.mjs` `ito.mjs` `lfs.mjs` `pdf-adapter.mjs` `pte.mjs` `question-index.mjs` `resolver.mjs` `schema.mjs` `taxonomy.mjs` `transcript-matcher.mjs` `v2-api.mjs` `verify-pdfs.mjs` `zhan.mjs`、根级 `contract.test.mjs`
- 工具（27）: `tools/align-audio.py` `tools/audit-all.mjs` `tools/baseline.mjs` `tools/build-alignment-gold.mjs` `tools/build-index.mjs` `tools/build-manifest.mjs` `tools/build-question-index.mjs` `tools/check-route-inventory.mjs` `tools/compare-official.mjs` `tools/import-pdf.mjs` `tools/pdf_answer_keys.py` `tools/pdf_extract.py` `tools/printed_page.py` `tools/range_scan.py` `tools/refresh.mjs` `tools/run-alignment.mjs` `tools/verify-audio.mjs` `tools/verify-decisions.mjs` 及开发期扫描器 `tools/dump_pages.py` `tools/tmp_examiner_scan.py` `tools/tmp_gen_structure.py` `tools/tmp_listening_scan.py` `tools/tmp_parse_scan.py` `tools/tmp_probe9.py` `tools/tmp_reading_scan.py` `tools/tmp_skills_scan.py` `tools/tmp_v5_summary.py`
- 测试（22）: `tests/book3-listening.test.mjs` `tests/ielts-adapters.test.mjs` `tests/ielts-answer-matcher.test.mjs` `tests/ielts-audio-catalog.test.mjs` `tests/ielts-audio-matcher.test.mjs` `tests/ielts-cam21.test.mjs` `tests/ielts-e2e.test.mjs` `tests/ielts-manifest.test.mjs` `tests/ielts-pdf-extract.test.mjs` `tests/ielts-pte-parser.test.mjs` `tests/ielts-resolver.test.mjs` `tests/ielts-routes.test.mjs` `tests/ielts-store-fetch.test.mjs` `tests/ielts-taxonomy.test.mjs` `tests/ielts-transcript.test.mjs` + fixtures 4 件（`fixtures/manifest.json`、`fixtures/alignment-gold.json`、`fixtures/pdf-expected/book1-t2-q40-41-diagram.json`、`fixtures/pdf-expected/book10-t1-answer-keys.json`、`fixtures/pdf-expected/book3-answer-keys-t2-t4.json`、`fixtures/pdf-expected/book3-t2-t4-listening-ocr-pages.json`）
- 数据（3）: `data/expected-manifest.json`（925 items）、`data/expected-structure.json`（21 册 925 单元）、`data/printed-pages.json`
- 文档（2）: `API.md`、`DEVELOPMENT.md`
- 逐文件 sha256/字节/动作（add 70 + overwrite 12）: `ielts-data/runs/20261003T140007Z-repair/changed-files.json`
- 另 2 个文件（`AUDIT_REPORT.md`、`tests/stub-fetch.cjs`）两副本本就一致，未列入变更。

### 1.2 examdata 侧（仅雅思模块与雅思测试）

- `examdata/src/examdata/api/ielts.py`（28 路由；S16 增 info env：MAX_CONCURRENT/QUEUE_TIMEOUT/DATA_DIR）
- `examdata/docs/IELTS_API.md`（答案键口径、env 表、测试命令）
- `examdata/tests/test_api_ielts.py`、`examdata/tests/test_ielts_concurrency.py`、`examdata/tests/test_ielts_resolver_contract.py`（新增）
- 未改 examdata 其他任何业务模块。

### 1.3 文档与数据根

- `docs/ielts/EXECUTION_CHECKLIST.md`（S01–S17 执行清单，新增）
- `docs/ielts/IELTS_IMPLEMENTATION_RESULT.md`（本文件）、`docs/ielts/IELTS_REMAINING_GAPS.md`（新增）
- `ielts-data/`（新数据根）: `raw/`（193 条不可变 raw）、`audio/`（336 文件 / 2.1GB）、`pdf/`、`indexes/`、`manifests/`、`normalized/`、`assets/`、`refresh/`、`runs/20261003T140007Z-repair/`（证据、checkpoint、alignment、backup）

---

## 2. 测试命令与退出码（全部实测）

| 步骤 | 命令（摘） | 结果 | 退出码 | 证据 |
|---|---|---|---|---|
| S01 | `node --test ielts-api/tests/contract.test.mjs`；pytest 2 文件 | 9/9 pass；6 passed 1 skipped | 0；0 | `evidence/S01-node-contract-baseline.txt`、`S01-pytest-baseline.txt` |
| S02 | `node --test tests/ielts-manifest.test.mjs tests/contract.test.mjs` | 40/40 pass | 0 | `evidence/S02-node-tests.txt` |
| S03 | `node --test tests/ielts-store-fetch.test.mjs` + 60 回归 | 20/20；60/60 | 0 | `evidence/S03-node-tests.txt`、`S03-full-regression.txt` |
| S04 | `node --test tests/ielts-pte-parser.test.mjs` + 88 回归 | 28/28；88/88 | 0 | `evidence/S04-pte-parser-tests.txt`、`S04-node-tests.txt` |
| S05 | cam21 23 + 111 + 125 回归 | 23/23；111/111；125/125 | 0 | `evidence/S05-cam21-tests.txt`、`S05-full-regression.txt`、`S05-adapters.txt` |
| S06 | 7 文件 134 回归 + 提取/导入命令 | 134/134；EXIT=0 | 0 | `evidence/S06e-node-tests.txt`、`S06-provenance-chain.txt` |
| S07 | answer-matcher 32 + 166 回归；compare-official 冒烟 | 166/166；match38/conflict1/pdf_only1 | 0 | `evidence/S07-node-tests.txt`、`S07-summary.md` |
| S08 | `node tools/build-question-index.mjs` + 190 回归 | 190/190；index 6604 题 | 0 | `evidence/S08-node-tests.txt`、`S08-build-index.txt` |
| S09 | `node tools/verify-audio.mjs --download …` + 234 回归 | tree-check 336/336；234/234 | 0 | `evidence/S09-*.txt`（8 件） |
| S10 | `python tools/align-audio.py …`；`node tools/run-alignment.mjs …`；249 回归 | 33 identity；cam21 66 verified 窗；249/249 | 0 | `evidence/S10-*.txt`（9 件） |
| S11 | contract + 249 回归 + live 冒烟 | 9/9；249/249；冒烟全过 | 0 | `evidence/S11-*.txt`（5 件） |
| S12 | `build-question-index` + 全量 coverage + 271 回归 | 271/271；contract 9/9 | 0 | `evidence/S12-regression-tests.txt` 等 |
| S13 | node 287 + contract 9 + routes 16 + pytest | 287/287；9/9；16/16；19 passed 1 skipped | 0 | `evidence/S13-*.txt` |
| S14 | C1–C7 工具电池（见下） | C1=0 C2=0 C3=0 C4=1 C5=1 C6=1 C7=0 | 0/0/0/1/1/1/0 | `evidence/S14-command-battery.txt` 等 7 件 |
| S15 | e2e / 全套 node / contract / verify-decisions / route-inventory / pytest | 22/22；309/309；9/9；39/39；11/11；19 passed 1 skipped | 全 0 | `evidence/S15-*.txt`（7 件） |
| S16 | 主副本 node；另一副本 node；pytest；语法 | 309/309；307 pass/0 fail/2 skip；19 passed 1 skipped；SYNTAX-OK | 全 0 | `evidence/S16-main-tests.txt`、`S16-other-tests-round2.txt`、`S16-pytest.txt`、`S16-syntax.txt` |
| S17 | 本报告；coverage.md 生成；checkpoint 更新 | 见 §11 | 0 | 本文件 + `evidence/S16-*` |

S14 工具电池（逐条）:

| # | 命令 | 退出码 | 说明 |
|---|---|---|---|
| C1 | `node ielts-api/tools/audit-all.mjs --offline --fixtures ./ielts-api/tests/fixtures --out ./ielts-data/runs/offline-audit` | 0 | errors_total=0 |
| C2 | `node ielts-api/tools/refresh.mjs --books 1,3,10,20,21 --variant academic --skills reading,listening --jobs 2 --max-requests 300 --resume` | 0 | tasks=40 skipped=40 |
| C3 | `node ielts-api/tools/refresh.mjs --books 1-21 --variant academic --skills reading,listening --jobs 2 --max-requests 1500 --resume` | 0 | tasks=168 skipped=168 |
| C4 | `node ielts-api/tools/refresh.mjs --books 1-21 --variant general --skills reading,writing,speaking --jobs 2 --max-requests 800 --resume` | 1 | 真实缺口：gaps=36（9/16/18/19/20 no_text_layer、21 no_local_pdf） |
| C5 | `node ielts-api/tools/refresh.mjs --books 1-21 --variant academic --skills writing,speaking --jobs 2 --max-requests 800 --resume` | 1 | pdf_verified=120 / no_text_layer=40 / missing=8（诚实语义） |
| C6 | `node ielts-api/tools/audit-all.mjs --dataset current --verify-assets --verify-audio --out ./ielts-data/runs/full-audit` | 1 | combos=168、audio 336/336 hash、overall=partial（诚实语义） |
| C7 | `node ielts-api/tools/build-index.mjs --dataset current` | 0 | pages=168 / questions=6724 |

另: 对齐重跑 `node ielts-api/tools/run-alignment.mjs --only cambridge:3:shared:listening:{2,3,4}:P{1..4} --force --reuse-asr` = 0（processed=12 errors=0）；CLI 参数校验 15 例 exit 2（符合）、dry-run 2 例零写入。

---

## 3. A01–A16 逐项修复结果

> status 语义: **resolved** = 该问题在代码/数据层完成并有证据；**partial** = 已完成可独立部分，剩余部分为源/外部依赖缺口（见 `IELTS_REMAINING_GAPS.md`）；**not_run** = 未执行（如实标注）。

### A01 通用路由范围失配（P0）— status: resolved
- **before**: `ielts-cli.mjs` routes 把 listening-qa 指向 TaroFlink（仅 16–20）；`/listening/1/1` HTTP200 但 ok:false；reading 仅 reader 1–19 单篇；pdf 仅 4–18；CLI/HTTP/FastAPI 三入口语义不一致。
- **after**: 三入口（CLI / Node HTTP `v2-api.mjs` / FastAPI `ielts.py`）统一共享 `resolver.mjs` 身份解析与调度；reading-enriched 单篇路由（默认 passage=1）三入口可用（剑19 单篇 live ok 13 题；剑20 404 如实报错，不回落冒充）；v2 `?variant=academic|general|gta|gtb` + `type/offset/limit` 分页（limit≤500）。三入口 25/25 cases 输出一致；独立端口 8799 路由清单 11/11。
- **evidence**: `evidence/S13-three-entry-consistency.txt`、`S13-three-entry-report.json`、`S15-route-inventory.txt`、`S13-routes-tests.txt`、`S12-rebuild-index-2.out`。

### A02 空答案错位（P0）— status: resolved
- **before**: `pte.mjs` LI 提取 `.filter(Boolean)` 导致空 LI 后答案整体错位（Q2 挂 Q3 答案）。
- **after**: PTE 结构提取重写（`pte.mjs` 641 行 + `html-questions.mjs` Edit A–F）：OL start / LI value / 空 LI 保留、编号段 empty/range/pair、cell_gap；空答案 null 化且**不移位**（测试锁定 raw-143 Q34 空 → q35="B" 不变）；`answer-matcher.mjs` 空 LI 不移位语义 + e2e 空答案案例。
- **evidence**: `evidence/S04-pte-parser-tests.txt`（28 用例）、`S04-offline-regression.editF2.txt`、`S07-node-tests.txt`（32 用例）、`S15-e2e-tests.txt`。

### A03 老版题号及预期结构硬编码（P0）— status: resolved（结构层）；源缺口 6 槽保留
- **before**: extractAnswers/extractQuestions/missingNumbers 硬限 1–40；剑1 T2 Q41 无处理。
- **after**: `data/expected-structure.json` 21 册 925 单元逐套题号区间（剑1 T2 听力 41 题、T3 42 题、剑1 阅读 40/41/38/39、剑12 tests 5–8 等），schema 校验 + 测试锁定；解析器不再假定 10 题/Part；索引如实含 41/42 题（剑1 T2 听力 41 题、T3 42 题、T4 42 题）。空/缺答案槽位（剑1 六处 + 剑10 T1 Q34）保留原值/空值不移位、不删分母。
- **evidence**: `evidence/S02-build-manifest.txt`、`S04-pte-parser-tests.txt`、`S06d-missing-resolution.json`、`S12-rebuild-index.out`。

### A04 不完整题干和资源丢失（P0）— status: resolved（提取层）；images-only 书籍如实 partial
- **before**: 正则不保留选项/题组/表格/图片/地图/字数限制；prompt 截 400 字符；三篇边界未建立。
- **after**: `html-questions.mjs` 保留选项/组/表格 cell/多选 inputs；`cam21.mjs` 表格/地图/流程图资产 + 字数限制（b21 320 题全 complete）；`pdf_extract.py` 逐页结构 + 图资产导出 + OCR 合并；三篇目标题（剑3 T3 阅读 1-12/13-25/26-40 等）与逐套 Part 结构入 manifest；shared_prompt 污染修复（>4000 桶 69→0、1200–4000 桶 9→0、92 组缩短、键值零变化）。
- **evidence**: `evidence/S04-pte-parser-tests.txt`、`S06-provenance-chain.txt`、`S12-cam21-assets.txt`、`S12-sharedprompt-fix-diff.txt`。

### A05 剑3三套听力只有答案缺试卷题目（P0）— status: resolved（T2–T4 160 题）；6 题 partial（图片选项）
- **before**: `ielts-api.mjs:594/602` 空 questions；iprog 只能补答案。
- **after**: 新增 `book3-listening.mjs` 转换器：剑3 T2–T4 听力 160 题（154 complete / 6 partial——图片选项如实标 partial，不用 transcript 伪装 question）；PDF 提取 + iprog 答案键融合；答案-only 状态清除（qa_complete 语义）。
- **evidence**: `evidence/S12-b3-rebuild.txt`、`S12-b3-index-diff.txt`、`S12-rebuild-index.out`、`S05-adapters.txt`。

### A06 cam21 及组题（P0）— status: resolved
- **before**: cam21 阅读/听力多选题缺组选项、slots、无序集合与评分规则；147 答案键被当 147 题。
- **after**: `cam21.mjs` 重写：听力 4 套各 40 槽（raw 键 38/35/36/38 → inputs 展开 160 条答案）、多选组 group_slots/pick/accept sets（阅读 t2 Q20/Q21 等）；147 条原始答案键→按 inputs 覆盖验收，展开为 160（不是凑数）；多选组 13/13 = mcq_multiple；字数限制与资产（表格/地图/流程图）齐备。
- **evidence**: `evidence/S05-cam21-tests.txt`（23 用例）、`S06-cam21-crosscheck.json`（all_ok=true）、`S08-verify-cam21.txt`、`S12-cam21-assets.txt`。

### A07 分类没有统一标准（P1）— status: resolved（6678/6724）；46 unknown 如实记录
- **before**: reader/TaroFlink 有 type、cam21 局部、PTE 只有全卷 instructions、听力几乎全 gap。
- **after**: `taxonomy.mjs` 重写（14 题型规则 + 结构回退 + pool 覆盖）；`question-index.mjs` 统一索引：pages=168 / groups=1396 / questions=6724 / classified=6678；18 种题型分布入索引（note_completion 1475、multiple_choice_single 905、matching_features 716…）；46 题 unknown 有组成文件（pte 页、no_group，source_missing）。筛选/查询统一在 resolver/queryIndex。
- **evidence**: `evidence/S08-summary.md`、`S08-node-tests.txt`、`S12-unknown46-composition.txt`、`runs/full-audit/matrix.json`（findings.index_stats）。

### A08 空 Q34 / 旧比较器 / 官方核验（P0）— status: partial（比较器已修 + 15 册 119 cell 官方比对完成；book11 旋转已确证并登记（G14）；5 册无文字层 + 剑21 同源 + GT 不可比）
- **before**: 剑10 T1 Q34 空；旧 `official_pdf_cmp_v3.py` 子串比较漏洞（`match_one('read research methods','E')==True`）；官方核验仅有限听力集合。
- **after**: 剑10 T1 Q34 OCR 复核定位（答案候选已提取），保持 empty 不移位（answer_status=empty 如实）；新 `answer-matcher.mjs` 8 算法 + `tools/compare-official.mjs`（PDF sha256 校验）；45 条裁决 + 7 条窄修正迁入 `adjudications.mjs`（守卫回归 39 项，`verify-decisions.mjs` 全过）；b9t1r 官方核验 gv-01（Q21-26 tfng→ynng + 官方映射）+ gv-02（Q18-20 word_limit）；coverage 中仅 cambridge:9:academic:reading:1 达 official 6/40，其余全部 `official_unverified:0/40`。
- **S18 扩展（2026-10-05）**: 15 册（1–8、10–15、17）× 8 cell = 119 cell 官方键逐题比对（全部 EXIT=0，error cells=0）：total 4764 / match 2833 / conflict 985 / pdf_only 6 / answer_only 939 / missing 1 / unverified 946；冲突分类 plain_diff 786（pdf_superset 202 / disjoint 485 / punct_case_only 61 / idx_superset 38）+ alt_match 124 + alt_no_match 68 + nonascii_ocr 7。剑10 T1 阅读 S18 严格重跑 match=36 / conflict=3（Q9 `earthquake` vs `earthquakes`、Q10 `4/four sides` vs `4 sides`、Q12 `verandas/verandahs` vs `verandas`）/ pdf_only=1（Q34, PDF=F），取代 S06 冒烟值（match=38 / conflict=1(Q22)；Q22 现为 match）。点名项：剑1 T2 听力 41 题（match 24 / conflict 15 / pdf_only 2）、剑3 T2–T4 六 cell 各 40 题连续；全对样例：book10 t3 听力 40/40 + 阅读 40/40、book12 t6 听力 40/40、book7 t3 听力 40/40、book7 t4 阅读 40/40。book11 页→套错位已完成重比对调查（G14，2026-10-05）：旋转在来源侧确证（pte-N 持书 t(N−1) 答案，回绕），索引忠实复制来源、逐格 0 差异；231 条冲突作废为核验证据。G14 两项跟进（2026-10-05）闭环至本地证据上限：t4R 19–26 部分裁决（印块版式异常确证：错位模型 印块[21..26]==意图[20..25] + 两处组内非法值；意图值重建 [19 NG,20 T,21 NG,22 T,23 F,24 C,25 A,26 E]，20–23/25 三方一致；Q24 保留 C/D 双值）；pte-4L 定源 unverified（5 册 512 页 OCR + 31 具体域词检索 0 真命中，2 假阳性；详见 `evidence/S18-book11-remap-followup.md`）。
- **未完成**: 5 册无文字层（9/16/18/19/20）+ 剑21 同源镜像 + GT 无索引——未纳入官方比对；book11 G14 两项需外部独立核验（本地范围已闭环）：t4R 19–26 部分裁决后待不同印次/勘误页核验（Q24 C/D 双值保留）、pte-4L unverified 待 pte 源独立键——详见 G14；compare 证据未写回索引（`official_verifications` 仍 2 条 gv-01/gv-02）。
- **evidence**: `evidence/S06-book10-t1-reading-key.json`、`S07-summary.md`、`S07-node-tests.txt`、`S08-summary.md`、`S15-verify-decisions.txt`、`S18-official-compare.json`（sha256 9aaa3708…d35db9）、`S18-official-compare.md`（211f449a…d6c48）、`S18-compare-batch.txt`（5b23fba5…67007f）、`S18-book11-shift-check.txt`（96fd90ee…4a49a0）、`S18-book11-remap.md`（1e58248c…d9e6aa）、`S18-book11-remap-followup.md`（3b877380…1da96e）。

### A09 错音频及虚假可用（P0）— status: resolved
- **before**: aggregate 构造 4 个对象即判 audio=true；剑21 四个对象全 ok:false；`/listening-audio/21/1` 实测失败；1–20 URL 未证明可下载/对应。
- **after**: `audio-catalog.mjs` + `verify-audio.mjs`：catalog 362 条 = 320 available（maslow，独立文件）+ 16 verified（cam21，4 页 sha256 + 16 mp3）+ 26 candidate（full_test 派生，**不冒充 verified**）；tree-check 336/336 matched；audit 336/336 verified_hash、mismatch=0、file_missing=0；aggregate 不再按数组长度判 complete；剑21 音频经身份核验可用；e2e 篡改音频 hash 被 audit-all 捕获。
- **evidence**: `evidence/S09-summary.md` 等 8 件、`S14-cmd6-audit-full.txt`、`S15-e2e-tests.txt`。

### A10 逐题音频匹配（P1）— status: partial（33 identity；cam21 66 窗 verified；其余 unverified）
- **before**: 各源时间戳无统一 audio_id/哈希/时间基准；无问题→证据区间映射；按答案同词出现冒充定位风险。
- **after**: `audio-matcher.mjs` + `alignment-provider.mjs` + `tools/run-alignment.mjs` + `tools/align-audio.py`（whisperx 3.8.6 / whisper-small + wav2vec2-base-960h / int8 / cpu）：33 identity 对齐产物；cam21 gold 窗口注入后 verified 66 窗（t1P1 10/10、t3P1 10/10、t4P4 10/10、t4P1 9/10…）；gold fixture 103 窗 / crosscheck asr_confirmed 66 / not_text_verifiable 28 / no_match 9；时间单位/时钟/偏移有 e2e 案例；audio hash 与时间基准校验入文档；未达证据门槛的一律 `alignment_status:"unverified"`，不造假窗。
- **未完成**: 336 Part 中仅 33 有对齐文档（其余 unverified；maslow 无独立标签源）。
- **evidence**: `evidence/S10-*.txt`（9 件）、`S14-alignment-rerun.txt`、`S14-alignment-matrix.json`、`S15-e2e-tests.txt`。

### A11 截尾 / 缺 Part / raw 空 text（P1）— status: resolved
- **before**: 剑20 T2 缺 Part4；原文省略号截尾；aggregate 只用 listeningScript；raw 未分节时 tests={} 仍 ok:true 可得空 text。
- **after**: `ielts-api.mjs` listeningScript/testScript 重构：B0–B4 多源逐 Part 回落（maslow/reader/ito/cam21），review/partial/cross_source_agreement 诚实语义；`countCleanScriptParts` 修复整本捷径（≥16 parts 且 ≥40k 字符）；截尾检查（省略号/尾截断检测）；raw 空 text 不再算原文完整；aggregate 消费新形状（剑1 整本 16/16 parts、missing=0）。
- **evidence**: `evidence/S11-summary.md`、`S11-live-smoke-listeningscript.txt`、`S11-live-smoke-aggregate.txt`、`S12-script-status-table.txt`。

### A12 聚合完整度假阳性（P0）— status: resolved
- **before**: reading/listening_qa/script/pdf 按对象存在、音频按数组长度即算完成；reader 回落仅 P1 也算整卷；score 5/5 误导。
- **after**: `coverage.mjs` 重写：370 units 逐单元 status_reasons（missing_numbers/extra_numbers/content_incomplete/missing_group_members/missing_assets/passages_present/empty_answers/answer_conflicts/unknown_types/official_unverified）；fully_complete_units=0（诚实：剑3 曾 answer-only、reader 单篇、失败音频、剑20 T1 等不冒充 complete）；audit-all overall=partial；score 语义不再是验收口径。
- **evidence**: `manifests/rev-8b21015ab64bb73c/coverage.json`、`coverage.md`、`evidence/S12-coverage-full.json`、`S14-cmd6-audit-full.txt`。

### A13 PDF 覆盖及文档残留错误（P1）— status: resolved（核验+文档）；book20 T2–T4 images-only partial
- **before**: SOURCES.lfs/cam21、lfs.mjs 注释“唯一”“剑1–20 完整”“10.7MB”；book20 硬编码；pdf21 ok:true 硬编码。
- **after**: 剑20 分册核验（Test1 34 页 + T2/T3/T4 实下载 5.6/4.9/5.2MB，34/35/31/30 页，图像型 text_chars=0，Part4 全部确证）；文档修正（`ielts-api.mjs`/`lfs.mjs`/`verify-pdfs.mjs`/`DEVELOPMENT.md`/`IELTS_API.md`：剑1–19 整本 + 剑20 Test1 分册 20/20 LFS 实测）；去除“唯一/整本”不当表述；book21 无本地 PDF 如实标注。
- **evidence**: `evidence/S06-book20-probe.json`、`S06-book20-download.json`、`S06-book20-verify.json`、`S06-book20-structure.json`、`S16-doc-diff.txt`。

### A14 provenance / cache / 重复拉取（P1）— status: resolved
- **before**: 每请求重拉；无 raw hash→题目→答案→音频→验收版本完整链条；修正元数据丢失；source 变化可使旧时间戳失效。
- **after**: `data-store.mjs`（内容寻址 raw、原子写、锁、checkpoint 合并、dataset_revision 与时间无关、current 指针门禁）+ `fetch-source.mjs`（并发 2/每来源 1、30s 超时、重试 2、连续 5xx 阻塞、请求与字节预算、403/429 阻塞持久化、本地复用 0 网络）；refresh 全量固化（C2/C3 幂等 skipped）；provenance 链（raw/pdf-extract/raw/pdf-ocr/derived/pdf）逐级 hash；7 条修正与 45 裁决带 guard 存于 `adjudications.mjs`。
- **evidence**: `evidence/S03-node-tests.txt`、`S03-full-regression.txt`、`S06-provenance-chain.txt`、`S14-cmd3-refresh-academic.txt`。

### A15 Writing/Speaking/General（P1）— status: partial（清单与路由完成；结构化内容未提取）
- **before**: General Reading 部分保留且可填入 Academic 空槽；无系统 Writing/Speaking 拉取；开放题无唯一答案。
- **after**: `expected-structure.json` 逐册登记 A/G 版与 writing/speaking 真实包含范围（GT 状态：in_book/not_in_book；剑11–17 GT not_in_book；剑1 GT 阅读 41 题）；general reading 17 units / general writing 17 units 入 coverage；writing/speaking 单元为 `unverified`（open_response_or_not_extracted，**不设唯一标准答案分母**）；三入口 `variant=gta/gtb` 路由可用；refresh C4/C5 如实报缺口（general gaps=36；writing/speaking pdf_verified=120/no_text_layer=40/missing=8）。
- **未完成**: writing/speaking 题目/图表的结构化提取（partial，见 §9/§10）。
- **evidence**: `evidence/S02-build-manifest.txt`、`S14-cmd4-refresh-general.txt`、`S14-cmd5-refresh-writing-speaking.txt`、`S13-*`。

### A16 全链路验收不足（P1）— status: partial（雅思链路全绿；全项目套件 not_run）
- **before**: 仅 9 种 Node 契约通过；缺覆盖全部入口/恢复/断网缓存/分类筛选/音频错版本的全量验收。
- **after**: 建立并执行：S01 基线（受保护文件 hash/DB/副本差异）→ S14 审计/刷新/索引工具电池（C1–C7 + CLI 校验 15 例 + dry-run）→ S15 fixtures manifest + e2e 22 + verify-decisions 39 + route-inventory 11（独立端口 8799 + Range 206）→ S16 两副本测试（主 309/309；另一副本 307 pass/0 fail/2 skip）+ 受保护复核 + 8000 检查（PID 36036，info 200，不重启）+ pytest（19 passed 1 skipped）。
- **未完成**: examdata 全项目套件 not_run（仅雅思相关 tests）；真实媒体全量核验 partial。
- **evidence**: `evidence/S01-*`、`S14-*`、`S15-*`、`S16-*`。

---

## 4. 逐册逐套覆盖矩阵链接

| 产物 | 路径 | 内容 |
|---|---|---|
| 覆盖 JSON（当前） | `ielts-data/manifests/rev-8b21015ab64bb73c/coverage.json`（sha256 7f1de9025cfa918c9f013ee5fa034b1c55ed912e17bdaa6af812803d26f9d7c7） | 370 units 全量状态 |
| 覆盖 Markdown（当前） | `ielts-data/manifests/rev-8b21015ab64bb73c/coverage.md` | 同上渲染 + 370 行单元明细表 |
| 数据集审计矩阵 | `ielts-data/runs/full-audit/matrix.json` / `matrix.md` | 168 combos + 370 units + findings |
| 逐题审计状态 | `ielts-data/runs/full-audit/questions.jsonl`（6724 行） | 每题的 content/answer/classification 状态与 source_refs |
| 离线审计 | `ielts-data/runs/offline-audit/matrix.md` | fixtures 离线基线 |
| 预期清单 | `ielts-api/data/expected-manifest.json`（925 items） | 逐册逐套预期结构与来源 |
| 期望结构 | `ielts-api/data/expected-structure.json` | 21 册 925 单元题号区间 |
| 历史覆盖快照 | `ielts-data/runs/20261003T140007Z-repair/evidence/S12-coverage-summary.md` | S12 时点 |

覆盖要点（当前 revision）: units=370（reading/academic 84、listening/shared 84、writing/academic 84、speaking/shared 84、reading/general 17、writing/general 17）；unit_status = partial 168 / not_extracted 154 / unverified 48 / complete 0 / source_missing 0；books_pdf_complete=1–19（20、21=false）；索引 pages=168 / groups=1396 / questions=6724 / answers=6724 / answer_groups=16 / fully_complete=6588 / gaps=202（全部 content_not_indexed）；168 combos 中 issues=5（全部为已定位源缺口：剑1 Q41×3 套+Q40、剑1r Q41、剑10r Q34 empty）。

---

## 5. 答案连接与官方核验分布

- 答案连接: attached 6717 / missing 6 / empty 1（共 6724；6 个 missing + 1 empty 为源缺口，保留原值不移位）。
- 裁决: 45 条迁移（option_mapping 8 / representation 7 / source_error 7 / order_semantics 14 / extraction_artifact 9；action correct 7 / none 38；origin diff 43 / masked_by_comparator_bug 2）+ 7 条窄修正（adj-10/11/21/32/39/40/45，from→to 带 guard）——单一事实源 `ielts-api/adjudications.mjs`；守卫回归 39 项全过（`tools/verify-decisions.mjs`）。
- 比较器: `answer-matcher.mjs` 8 算法；严格拒绝单字母子串匹配（e2e 锁定）；MCQ 严格映射；TFNG/YNNG 拆分；组 accepted sets。
- 官方核验分布: 组级官方核验 2 组（gv-01 b9t1r P2 G2 Q21-26 tfng→ynng + 官方答案映射；gv-02 b9t1r P2 G1 Q18-20 word_limit）；coverage 中仅 cambridge:9:academic:reading:1 = official 6/40，其余单元 0/40（`official_unverified`）；S18 扩展：15 册（1–8、10–15、17）× 8 cell = 119 cell 官方逐题比对（全部 EXIT=0）：total 4764 / match 2833 / conflict 985 / pdf_only 6 / answer_only 939 / missing 1；剑10 T1 阅读严格重跑 match=36 / conflict=3（Q9/Q10/Q12 变体形）/ pdf_only=1（取代 S06 冒烟值 match=38/conflict=1）；book11 页→套旋转已确证并登记（G14：pte-N 持书 t(N−1) 答案、索引逐格 0 差异；231 冲突作废）；G14 两项跟进（2026-10-05）：t4R 19–26 部分裁决（版式异常确证；意图值重建；Q24 双值 C/D）、pte-4L unverified（512 页 OCR 0 真命中）——见 `evidence/S18-book11-remap.md` 与 `S18-book11-remap-followup.md`；compare 证据未写回索引（`official_verifications` 仍 2 条 gv-01/gv-02）。
- 结论: **答案连接（连接语义与裁决）resolved；官方逐题核验 partial（15 册 119 cell 已比对；book11 旋转已确证登记（G14）；5 册无文字层 + 剑21 同源 + GT 不可比）**——历史报告与 45 裁决不等于全题通过。

---

## 6. 音频可用 / 身份 / 逐题对齐分布

- 目录: 362 records = 320 available（maslow 独立文件）+ 16 verified（cam21：4 页 sha256 + 16 mp3）+ 26 candidate（full_test 派生，不冒充 verified）；catalog 路径 `ielts-data/runs/20261003T140007Z-repair/audio/audio-catalog.json`。
- 可用性审计: 336/336 expected parts verified_hash、hash_mismatch=0、file_missing=0、not_run=0；tree-check 336/336 matched。
- 身份: available 320 / verified 16（其余 26 无独立文件）。
- 逐题对齐: 33 identity 对齐文档（`ielts-data/runs/20261003T140007Z-repair/alignment/`，17 maslow-priority + 16 cam21）；cam21 gold verified 66 窗（t1 10/10、t3P1 10/10、t4P4 10/10 等）；per-combo: cambridge:21 listening T1 13/40、T2 15/40、T3 19/40、T4 19/40（合计 66/160）；其余 combos alignment_verified=0/40。
- units_with_audio_verified=4、units_with_alignment_complete=0（coverage 诚实语义）。
- 模型: whisperx 3.8.6 / faster_whisper 1.2.1 / whisper-small / wav2vec2-base-960h / int8 / cpu；锁文件 `ielts-data/tools/alignment-models/model-lock.json`。
- 结论: **音频文件与 hash 级可用性 resolved；逐题对齐 partial（66 窗 verified / 其余 unverified，未造假区间）**。

---

## 7. 两副本同步 hash 结果

- 范围: `ielts-api/` 逐文件（add 70 + overwrite 12，conflict 0，failed 0；2 个文件本就一致未动）；examdata 侧文件不属另一副本（不同仓库），未同步。
- 覆盖前对方 12 个文件均 = S01 基线 hash（无独立修改），备份于 `ielts-data/runs/20261003T140007Z-repair/backup/other-copy-2026-10-05/`（12 文件）；对方独有 12 文件（REVIEW-PROMPT.md、agg191/201/211.*、agg32/33/34.json、zcov.json、zr211.json）全部保留未动。
- 同步后校验: missing 0 / mismatch 0（`evidence/S16-sync-verify.txt`）；2026-10-05 复核 changed-after-sync=0。
- 关键文件 sha256（前8…后4）: `ielts-api.mjs` d25a56c2…0c3a；`lfs.mjs` bc99082e…d40b；`verify-pdfs.mjs` a8ee19f0…e28f；`API.md` c5debe7e…d7c7；`DEVELOPMENT.md` 0b5c9caf…2ade；`examdata/src/examdata/api/ielts.py` 9d79ee00…11d3；`examdata/docs/IELTS_API.md` adf48d74…d868。逐文件 82 条 hash: `evidence/S16-sync.json`、`changed-files.json`。
- 两副本测试: 主 309/309 EXIT=0；另一副本 307 pass/0 fail/2 skip EXIT=0（round1 无 junction 时 8 fail 全为缺工作区 raw 源，非代码缺陷）。

---

## 8. 受保护边界复核

- adapters 10 / markscheme 4 / specs 27 文件 changed=0 / missing=0（新增项全为 `__pycache__` 字节码）。
- **外部并发变更如实记录**: `edexcel_papers/pipeline.py` 0ee9029cf869→c3c64aff46f2（mtime 2026-10-05 02:31:18 +0800）非本任务所为（本会话日志无该文件写入；当日另有 timetable/toefl/materials/paperqa 等外部修改）；生产 DB `examdata/.data/examdata.db` 因运行中服务并发写入变化（backup DB same=True）；git head=d8e64a6 不变。
- 8000 服务: 未重启（PID 36036，`GET /api/v1/ielts/info` 200 JSON）。
- 证据: `evidence/S16-protected-recheck.txt`、`S16-port8000.txt`。

---

## 9. 未运行检查（not_run / partial，如实列出）

1. **全 21 册逐题官方答案核验** — partial（S18：15 册 × 8 cell = 119 cell 已比对，EXIT=0；book11 页→套旋转已确证并登记（G14，2026-10-05）；G14 两项跟进闭环至本地证据上限：t4R 19–26 部分裁决（待外部印次）、pte-4L unverified（512 页 OCR 0 真命中）；未覆盖：5 册无文字层 9/16/18/19/20 + 剑21 同源 + GT 无索引；b9t1r 组级 2 项；compare 证据未写回索引）。
2. **examdata 全项目测试套件** — not_run（仅执行雅思相关 3 个测试文件；不把雅思绿测声称为整个 examdata 通过）。
3. **336 Part 全量音频逐题对齐** — partial（33 identity 有对齐文档；其余 unverified；maslow 其余 Part 无独立标签源）。
4. **writing/speaking 结构化内容提取** — partial（目录/范围/路由完成；题目与图表结构化未提取，open-response 不设唯一答案）。
5. **refresh 预算触顶 exit 3 现场触发** — not_run（由 fetch-source 层 4 组测试覆盖；refresh 工具层未现场触发）。
6. **compare-official 接入 audit-all** — not_run（compare-official 已由 CLI 暴露（S13）；audit-all 未接入因逐题 PDF 值未持久化）。
7. **剑20 T2–T4 题面全量 OCR** — not_run（仅页眉结构图与 Part4 确证；images-only 题面提取按需）。
8. **音频全量 ASR（336 Part）** — not_run（仅 33 identity 实跑；其余无标签/未跑）。
9. **全册 live happy-path 抽查** — partial（剑19 单篇 + 剑21 等抽验；全册 live 由 S14 审计工具以本地数据覆盖，非 live 网络）。
10. **45+7 裁决的人工全量复核** — partial（迁移与守卫回归完成；裁决本身的最终人工核验属外部评审范围）。

---

## 10. 资源 / 模型 / 人工裁决缺口（摘要，详见 REMAINING_GAPS）

- 剑1 T2 听力 P4 diagram 资产（Q40-41，p45）本地无匹配 → `expected_assets_unmatched`（1 条 error）。
- 7 个空/缺答案槽位（剑1 六处 + 剑10 T1 Q34）为源缺口，保留原值/空值。
- 46 题 unknown（pte 页、no_group、missing_content；12 个 book/part 组合）无 alternate source。
- 册 9/16/18/19/20 无文字层 PDF；册 21 无本地 PDF（cam21 镜像源）；剑20 T2–T4 images-only。
- 2 处 answer_form_mismatch 严格 no_match（cam21 t1s4 q31 metals/metal、t3s4 q33 holidays/holiday）。
- 模型环境: whisperx/faster-whisper/wav2vec2（int8/cpu）已固化；未使用 GPU。
- 需要外部资源或独立核验的精确清单: 见 `docs/ielts/IELTS_REMAINING_GAPS.md`（逐册逐套逐题/组/Part）。

---

## 11. 精确恢复命令

```bash
# 1) 重建索引 + manifests + coverage（离线，零网络；原子发布 current）
node ielts-api/tools/build-index.mjs --dataset current
# 2) 重新渲染 coverage Markdown（从 coverage.json 原样渲染）
python ielts-data/runs/20261003T140007Z-repair/scratch/gen-coverage-md.py
# 3) 离线 fixtures 审计（exit 0）
node ielts-api/tools/audit-all.mjs --offline --fixtures ./ielts-api/tests/fixtures --out ./ielts-data/runs/offline-audit
# 4) 数据集全量审计（含资产与音频 hash 流式校验；exit 1=partial 为诚实语义）
node ielts-api/tools/audit-all.mjs --dataset current --verify-assets --verify-audio --out ./ielts-data/runs/full-audit
# 5) 回归
cd ielts-api && node --test tests/*.test.mjs && node --test contract.test.mjs
node tools/verify-decisions.mjs
node tools/check-route-inventory.mjs
# 6) FastAPI 雅思测试（TestClient/独立进程；不重启 8000）
EXAMDATA_TEST_LIVE=0 EXAMDATA_DATABASE_URL='sqlite:///:memory:' \
EXAMDATA_DATA_DIR='C:/Users/weo/Desktop/api/ielts-data/test-examdata' \
EXAMDATA_IELTS_DATA_DIR='C:/Users/weo/Desktop/api/ielts-data' \
EXAMDATA_IELTS_DIR='C:/Users/weo/Desktop/api/ielts-api' \
examdata/.venv/Scripts/python.exe -m pytest examdata/tests/test_api_ielts.py examdata/tests/test_ielts_concurrency.py examdata/tests/test_ielts_resolver_contract.py
# 7) refresh（本地复用固化，网络请求恒 0；--resume 幂等）
node ielts-api/tools/refresh.mjs --books 1-21 --variant academic --skills reading,listening --jobs 2 --max-requests 1500 --resume
# 8) 对齐重跑（示例：cam21 verified 目标）
node ielts-api/tools/run-alignment.mjs --targets verified --force --reuse-asr
```

- 恢复锚点: `ielts-data/runs/20261003T140007Z-repair/checkpoint.json`（stage=S17；steps.S01–S17 全 done，每步含 files/results/evidence）。
- 请求/错误日志: `ielts-data/runs/20261003T140007Z-repair/requests.jsonl`（683 条）、`errors.jsonl`。
- 预算: `EXAMDATA_IELTS_MAX_REQUESTS` / `EXAMDATA_IELTS_MAX_BYTES`（默认 200 请求 / 1 GiB）。
