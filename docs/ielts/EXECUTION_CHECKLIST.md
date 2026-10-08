# IELTS 修复执行清单（S01–S17 + S18 官方核验扩展）

- 任务: 按 `docs/ielts/IELTS_REPAIR_IMPLEMENTATION_PLAN.md` 执行 S01–S17；解决 `docs/ielts/IELTS_COMPLETENESS_AUDIT_20261003.md` A01–A16。
- Run ID: `20261003T140007Z-repair`；运行目录 `ielts-data/runs/20261003T140007Z-repair/`。
- 治理说明: 本会话按用户显式 S01–S17 流程执行；未建看板卡（用户流程优先）。工作区根非 git 仓库，`examdata` 为既有 git 仓库（只读记录，不改其历史）。
- 状态枚举: pending / running / done / partial / blocked。
- 每步固定字段: id、status、files、command、exit_code、evidence、gaps、next_action。

## 总览

| id | 标题 | status | 关键证据 |
|----|------|--------|----------|
| S01 | 基线、备份、受保护文件清单 | done | `ielts-data/runs/20261003T140007Z-repair/` |
| S02 | 预期清单与覆盖分母（manifest/schema/catalog） | done | `ielts-api/data/expected-manifest.json`（925 items、0 error、40/40 tests） |
| S03 | 不可变 raw 与版本化存储（data-store/fetch-source） | done | `ielts-api/data-store.mjs`、`ielts-api/fetch-source.mjs`（60/60 tests） |
| S04 | PTE 结构提取重写（空答案移位） | done | `ielts-api/tests/ielts-pte-parser.test.mjs`（28 用例）；88/88 全量回归 |
| S05 | cam21 多选组与答案键语义 + 跨源适配器统一 | done | `ielts-api/cam21.mjs` 重写 + `ielts-cam21.test.mjs`（23 用例）；适配器统一（ito/iprog/zhan/ielts-api）+ `ielts-adapters.test.mjs`（14 用例）；125/125 全量回归；raw-332 越界修复 |
| S06 | PDF 官方对照与题组/图表资产提取 | done | `ielts-api/pdf-adapter.mjs`、`ielts-api/tools/import-pdf.mjs`、`ielts-pdf-extract.test.mjs`（9 用例）；134/134 回归；9 次导入 7 册 145 页；book20 4 分册核验；cam21 交叉核对 all_ok |
| S07 | 题目—答案匹配与 45 裁决迁移 | done | `answer-matcher.mjs`（8 算法）、`adjudications.mjs`（45 条）、`tests/ielts-answer-matcher.test.mjs`（32 用例）、`tools/compare-official.mjs`；166/166 回归；compare 冒烟 38/1/1 |
| S08 | 统一分类与题目索引 | done | `taxonomy.mjs` 重写+48 fallback 复核；1365/1368 classified（3 empty）；diff 24 组全复核 |
| S09 | 音频目录与身份验证 | done | catalog 362 条（320 available/16 verified/26 candidate 派生）；tree-check 336/336；cam21 16/16 verified；234/234 tests；evidence/S09-* 8 件 |
| S10 | 音频逐题对齐 | done | `ielts-api/audio-matcher.mjs`、`alignment-provider.mjs`、`tools/run-alignment.mjs`、`tools/align-audio.py`；33 identity 产物、cam21 gold 66 verified 窗；249/249 tests；evidence/S10-* 9 件 |
| S11 | 原文逐 Part 回落与截尾检查 | done | `ielts-api.mjs`（listeningScript/aggregate 重构）+ `transcript-matcher.mjs`；B0–B4 多源逐 Part 回落；contract 9/9、249/249 tests |
| S12 | resolver/coverage 与 ielts-api 重写 | done | `resolver.mjs`、`coverage.mjs`（新增）、`book3-listening.mjs`（新增）；370 units 全量 coverage；索引 168 页/1396 组/6724 题；271/271 tests；shared_prompt 污染修复（>4000 桶清零） |
| S13 | 三入口统一（CLI/Node HTTP/FastAPI） | done | 三入口共享 resolver/v2-api；v2 variant=gta/gtb + 分页；reading-enriched 三入口（剑19 live ok）；25/25 一致性；fetch=0；287/287+9/9+16/16+pytest 19 |
| S14 | 审计/刷新/索引工具 | done | `tools/audit-all.mjs`（790行）+ `tools/refresh.mjs`（668行）+ `tools/build-index.mjs`（287行）；C1–C7 全跑（offline 0 / refresh 0,0,1,1 / full-audit 1 partial / build-index 0）；168 combos、音频 336/336 hash、12 stale 修复；evidence/S14-* |
| S15 | fixtures 与全套回归 | done | e2e 22/22；node 309 pass；contract 9/9；verify-decisions 39；route-inventory 11；pytest 19+1skip；evidence/S15-* |
| S16 | 文档与另一副本同步 | done | 同步 add 70/overwrite 12/conflict 0/failed 0；两副本测试（主 309/另一副本 307+2skip）；受保护复核+8000检查；evidence/S16-* |
| S17 | 结果报告与剩余缺口 | done | `IELTS_IMPLEMENTATION_RESULT.md` + `IELTS_REMAINING_GAPS.md` + `coverage.md`；checkpoint stage=S17 全 done |
| S18 | 官方答案逐题核验扩展（15 册 PDF 键提取 + 119 cell compare） | done | 119 cells EXIT=0；match 2833 / conflict 985（分类 4 类 + plain_diff 子模式）/ answer_only 939 / pdf_only 6 / missing 1 / unverified 946；`evidence/S18-official-compare.json` + `.md` + `S18-compare-batch.txt`；book14 t1 reading 缺官方键（NO-PDF）；book11 页→套错位已完成重比对（G14：旋转在来源侧确证、索引映射逐格登记、231 冲突作废；`S18-book11-remap.md`）；G14 两项跟进闭环至本地证据上限：t4R 19–26 部分裁决（版式异常确证，意图值重建，Q24 双值）、pte-4L unverified（512 页 OCR 0 真命中）（`S18-book11-remap-followup.md`）|

---

## S01. 基线、备份、受保护文件清单

- id: S01
- status: done
- files:
  - 新增 `ielts-api/tools/baseline.mjs`
  - 新增 `ielts-data/runs/20261003T140007Z-repair/baseline.json`
  - 新增 `ielts-data/runs/20261003T140007Z-repair/protected-files-baseline.json`
  - 新增 `ielts-data/runs/20261003T140007Z-repair/backup/**`（18/18 待改文件备份）
  - 新增 `ielts-data/runs/20261003T140007Z-repair/evidence/**`
- command:
  - `node ielts-api/tools/baseline.mjs --run-id 20261003T140007Z-repair`（两次：初次与 npm 版本采集修复后复跑）
  - `node --test ./ielts-api/tests/contract.test.mjs`
  - `EXAMDATA_DATABASE_URL='sqlite:///:memory:' EXAMDATA_DATA_DIR='C:/Users/weo/Desktop/api/ielts-data/test-examdata' EXAMDATA_IELTS_DIR='C:/Users/weo/Desktop/api/ielts-api' EXAMDATA_TEST_LIVE='0' ./examdata/.venv/Scripts/python.exe -m pytest ./examdata/tests/test_api_ielts.py ./examdata/tests/test_ielts_concurrency.py -q`
- exit_code: 0（baseline）/ 0（node --test）/ 0（pytest）
- evidence:
  - `ielts-data/runs/20261003T140007Z-repair/baseline.json`（node v24.19.0、npm 12.0.2、python 3.14.7、venv 3.14.7、13 个共有文件 SHA256、副本差异、live `/api/v1/ielts/info` HTTP 200/3241 字节快照）
  - `ielts-data/runs/20261003T140007Z-repair/protected-files-baseline.json`（adapters 10 / edexcel_papers 4 / markscheme 4 / specs 27；生产 DB `.data/examdata.db` 297,164,800B 等；注明运行中 DB 可能独立变化）
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S01-node-contract-baseline.txt`（9 tests / 9 pass / 0 fail）
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S01-pytest-baseline.txt`（6 passed / 1 skipped；1 条既有 starlette deprecation warning）
  - 副本差异: both_equal=14, differ=0；dst_only=`contract.test.mjs`(根), `tools/baseline.mjs`；src_only=REVIEW-PROMPT.md 等 12 个文件（S16 不得删除）
- gaps: 无阻塞。备注: 生产数据库为运行中实例，hash 基线可能独立变化（已在 protected-files-baseline.json 注明）；无看板卡（用户显式流程优先）。
- next_action: S02（catalog.mjs / schema.mjs / data/expected-manifest.json / tools/build-manifest.mjs）

---

## S02. 预期清单与覆盖分母

- id: S02
- status: done
- files:
  - 新增 `ielts-api/catalog.mjs`（21 册书目、edition `c<N>-<sha8>`、PDF sha256/页数、text_layer、GT 状态、外部源清单）
  - 新增 `ielts-api/schema.mjs`（ID 构造/校验、manifest 校验器、coverage 计算、题号区间工具）
  - 新增 `ielts-api/data/expected-structure.json`（21 册 925 单元：逐套 listening/academic reading/writing/speaking 及 GT 题号区间、页表、状态）
  - 新增 `ielts-api/tools/tmp_gen_structure.py`（结构生成器，含区间连续性断言）
  - 新增 `ielts-api/tools/printed_page.py`（PDF 印刷页号批量解析）
  - 新增 `ielts-api/tools/build-manifest.mjs`（catalog+structure+v5 答案键+PTE/cam21 快照 → expected-manifest，离线）
  - 新增 `ielts-api/data/expected-manifest.json`（925 items、cross_checks、validation、coverage、21 条 GT 裁决）
  - 新增 `ielts-api/data/printed-pages.json`
  - 新增 `ielts-api/tests/ielts-manifest.test.mjs`（31 用例）
  - 证据副本 `ielts-data/runs/20261003T140007Z-repair/evidence/expected-manifest.json`
- command:
  - `PYTHONIOENCODING=utf-8 examdata/.venv/Scripts/python.exe ielts-api/tools/tmp_gen_structure.py`
  - `node ielts-api/tools/build-manifest.mjs`
  - `node --test ielts-api/tests/ielts-manifest.test.mjs ielts-api/tests/contract.test.mjs`
- exit_code: 0 / 0 / 0
- evidence:
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S02-build-manifest.txt`：books=21、items=925、validation_ok=true、errors=0、warnings=3、complete_books=[1,3,4,5,6,7,8,11,12,14,17]、incomplete=[2,9,10,13,15,16,18,19,20,21]、pdf_hash 20/20 match、printed_pages=ok
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S02-node-tests.txt`：40 tests / 40 pass / 0 fail（manifest 31 + contract 9）
  - coverage：shared_listening / academic_reading / academic_writing / shared_speaking 各 expected 84 / verified 60 / unverified 24；general_reading 17/17/0；general_writing 17/17/0
  - questions_expected：listening 3366、academic reading 3358、general reading 681、writing/speaking 0（开放题不设唯一答案分母）
  - 结构断言（测试锁定）：剑1 T2 听力 41 题、T3 42 题；剑1 阅读 T1-T4=40/41/38/39；剑2 T1 阅读 13/14-27/28-40；剑3 T3 阅读 1-12/13-25/26-40；剑12 用 tests 5-8；剑1 GT 阅读 41 题；剑1 T2 L Part4 diagram asset；听力 84 单元全 variant=shared；书 11-17 无 general items（GT=not_in_book）；书 9/16/18/19/20/21 全 40 items unverified 且分母保留（L=160）；剑20 T2-T4 存在 unverified
  - 交叉校验：v5 答案键 116 ok / 15 note / 0 error（note 全属书 10/13/15，partial extraction）；cam21 8 快照、PTE 168 快照（3 not_ok）已记录
  - schema 拒收 10 类非法用例（重复 ID、part 重叠、union 缺口、item 非 gap-free、悬空 group→asset、组内非法 part、verified 无证据、错误 skill-part、variant/skill 不匹配、非法状态）
- gaps: 3 条 warning（page_unconfirmed）：`cambridge:2:shared:listening:2:P4`、`cambridge:2:shared:listening:4:P2`、`cambridge:13:shared:listening:2:P1` → S06 复核；PTE book3 test2-4 listening 空快照 → S06；剑20 本地 PDF 仅 34 页 Test1 分册且无文本层 → S06
- next_action: S03（data-store.mjs / fetch-source.mjs）

---

## S03. 不可变 raw 与版本化存储

- id: S03
- status: done
- files:
  - 新增 `ielts-api/data-store.mjs`（固定布局 ensureLayout、原子写 tmp+fsync+rename、sha256 工具、raw 按 hash 追加不覆写、二进制按 sha256 命名去重、normalized/indexes/manifests/decisions 写入、current 指针原子发布（validated 门禁）、stale 返回、dataset_revision 由输入 hash+版本计算、独占锁+过期接管、checkpoint 合并写读、requests/errors jsonl）
  - 新增 `ielts-api/fetch-source.mjs`（统一 fetcher：并发 2 / 每来源 1 / 30s 超时 / 网络重试 2 / 连续 5xx 阈值 5 / 请求与字节预算 / 单请求字节上限；403/429/连续5xx 立即阻塞来源并持久化 checkpoint；404=resource_missing 不重试；HTTP200 HTML 错误页与坏 JSON 拒绝；本地复用 reuseLocal*；fetchBatch 并发池；requests.jsonl/errors.jsonl/checkpoint 全记录）
  - 新增 `ielts-api/tests/ielts-store-fetch.test.mjs`（20 用例，含本地 HTTP 测试服务器与子进程并发写入）
- command:
  - `node --test ielts-api/tests/ielts-store-fetch.test.mjs`
  - `node --test ielts-api/tests/ielts-manifest.test.mjs ielts-api/tests/contract.test.mjs ielts-api/tests/ielts-store-fetch.test.mjs`
- exit_code: 0 / 0
- evidence:
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S03-node-tests.txt`：20 tests / 20 pass / 0 fail
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S03-full-regression.txt`：60 tests / 60 pass / 0 fail（manifest 31 + contract 9 + store-fetch 20）
  - `ielts-data/runs/20261003T140007Z-repair/checkpoint.json`：stage=S03、steps S01-S03 done、S04 next（含 S02 遗留 warning 清单）
  - 验收点覆盖（测试名对应）：raw hash 去重+meta 不覆写+无 tmp 残留；二进制 sha256 命名去重；两 run 并发写入（子进程，同一 raw 文件、无半文件）；锁独占/拒绝/过期接管保留 .stale 证据/token 不符拒释放；checkpoint 合并写读与恢复；dataset_revision 与时间无关；current 指针未校验拒发+原子发布+stale 返回保留最后成功版本+旧版本保留；looksLikeErrorPage（Cloudflare/404 标题）；fetchToRaw meta 全字段（url/final_url/fetched_at/status/content-type/etag/last-modified/bytes/sha256/parser_version）；404 不重试不阻塞；403/429 阻塞+后续不发网络+checkpoint 持久化；崩溃恢复（新 fetcher resume 后 blocked 保留且 0 网络调用）；连续 5xx 阻塞；5xx 重试成功计数重置；超时=网络异常重试后失败；坏 JSON/HTML 错误页拒绝（HTTP200 也不当成功）；预算三档（请求数/字节/单请求）；本地复用 0 网络请求；每来源在飞 ≤1；fetchBatch 全局并发 ≤2
- gaps: 无阻塞。备注：`EXAMDATA_IELTS_MAX_REQUESTS`/`EXAMDATA_IELTS_MAX_BYTES` 可覆盖预算默认（200 请求 / 1 GiB）；不换代理绕过；回落仅限已登记备用源（由调用方/catalog 决定）
- next_action: S04（pte.mjs 重写：parsePtePage 纯函数、空答案不移位、html-questions.mjs）

---

## S04. PTE 结构提取重写（空答案移位）

- id: S04
- status: done
- files:
  - 重写 `ielts-api/pte.mjs`（641 行；PARSER_VERSION `pte-s04-2026.10.2`；parsePtePage 纯函数 / parseHubLinks / expectedFor / bookTests / readingTest / listeningTest / audio / coverage / KNOWN_GAPS）
  - 深度修复 `ielts-api/html-questions.mjs`（1419 行；Edit A–F：OL start/LI value/空 LI 保留、编号段 empty/range/pair、cell_gap、multi_select、derived 补齐、bareMarker、RE_BOX 越界转槽）
  - 新增 `ielts-api/tests/ielts-pte-parser.test.mjs`（28 用例：A1–A14 内联 fixture + B1–B14 真实页断言）
- command:
  - `node --test ielts-api/tests/ielts-pte-parser.test.mjs`
  - `node --test ielts-api/tests/ielts-manifest.test.mjs ielts-api/tests/contract.test.mjs ielts-api/tests/ielts-store-fetch.test.mjs ielts-api/tests/ielts-pte-parser.test.mjs`
- exit_code: 0 / 0
- evidence:
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S04-pte-parser-tests.txt`：28 tests / 28 pass / 0 fail
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S04-node-tests.txt`：88 tests / 88 pass / 0 fail（manifest 31 + contract 9 + store-fetch 20 + pte-parser 28）
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S04-offline-regression.editF2.txt`：176 条目离线回归（Edit F + 空答案 null 化后；partial 25、q_missing 总 52）
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S04-test-expect.txt`、`S04-oor-scan.editF.txt`、`S04-oor-covered-summary.editF.txt`、`S04-raw-index.json`、`S04-offline-regression.editAE.json/txt`（Edit A–E 基线）
  - 关键断言覆盖：剑1T2 听力 41 题（qc=39、qm=[40,41]）、raw-143 Q34 空答案 null 且 q35="B"、raw-163 表格 cell_gap 7 槽 + 图资产绝对 URL、raw-35 boxes 29-33 转槽 + range_extended + 3 篇目标题、11 组 derived 单选、裸数字 5 页、raw-122 line_section、raw-103 池、raw-299 无池
- gaps: 无阻塞。备注：raw-index 的 skill 为 "reading"/"listening" 两值，测试与回归统一映射 reading→academic_reading（生产约定）
- next_action: S05（cam21.mjs 多选组与答案键语义）

---

## S05. cam21 多选组与答案键语义 + 跨源适配器统一

- id: S05
- status: done
- files:
  - ① `ielts-api/cam21.mjs`（重写：安全字面量解析替代旧正则；阅读 GROUPS/多选组展开；听力组题/字母库/多选展开/逐句原文；`scanUnsupported`/`parseLiteral` 非数据表达式检测）；`ielts-api/tests/ielts-cam21.test.mjs`（23 用例）；`ielts-api/html-questions.mjs`（raw-332 指令范围双源修复：RE_NEXT_TO + declaredRanges）
  - ② `ielts-api/ito.mjs`（`practiceSlugs` 补 `-with-answer` 候选；`extractItoAnswerKey` 行首题号精确提取替代宽泛正则；`opts.html` 注入；`skill/answer_only/provenance`；`__internals`）；`ielts-api/iprog.mjs`（`opts.html`；`skill/answer_only/qa_complete/questions:[]`；`answer_key_numbered` 统一身份；`__internals`）；`ielts-api/zhan.mjs`（`opts.html` 透传；`answer_authority:false`、`close_reading:true`、`provenance`；`__internals`）；`ielts-api/ielts-api.mjs`（`listeningQA`/`listeningSegments` 加 `opts.json` 注入、`number` 别名、逐题 `alignment_status:"unverified"` 与 `provenance`）；`ielts-api/tests/ielts-adapters.test.mjs`（14 用例，离线 + 真实 raw 回归）
- command:
  - `node --test ielts-api/tests/ielts-cam21.test.mjs`
  - `node --test <manifest+contract+store-fetch+pte-parser+cam21>`
  - `node --test <manifest+contract+store-fetch+pte-parser+cam21+adapters>`
  - `node ielts-data/runs/20261003T140007Z-repair/scratch/scan-oor-list.mjs`；`node scratch/s05-cam21-smoke.mjs`；`node scratch/s05-warnings-check.mjs`
- exit_code: 0（全部命令 0；冒烟 136/136）
- evidence:
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S05-cam21-tests.txt`：23 tests / 23 pass / 0 fail（含 A13 非数据表达式、B10 真实文件 warnings 全空）
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S05-full-regression.txt`：111 tests / 111 pass / 0 fail（manifest 31 + contract 9 + store-fetch 20 + pte-parser 28 + cam21 23）
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S05-adapters.txt`：125 tests / 125 pass / 0 fail（6 文件，含 adapters 14），EXIT=0
  - `ielts-data/runs/20261003T140007Z-repair/evidence/S05-oor-after.txt`：含 out_of_range 的组 10 → 9；raw-332 越界消失；剩 9 组为日期/时长噪声（raw-27/60/121/132/144/260/292/324）+ raw-280 b18t3 G8 真实内容行（留 S06 核查）
  - 关键断言覆盖：阅读 4 套各 40 槽/40 答案键（t2 多选组 Q20/Q21 展开 group_slots=[20,21]/pick=2/5 选项、accept 不 join；t4 Q9 accept=["fermentation","fermentation process"]）；听力 4 套各 40 槽（raw 键 38/35/36/38 → 展开 160；multiCorrect inputs 字符串与数字两种；t1/t3 letter_match 10 槽、t4 13 槽；t2 无 mcq）；逐句原文 738 行（89/204/230/215；t1 有说话人、t3 全 null）；安全解析防原型污染、坏字面量不抛
  - 适配器断言覆盖：ito 真实 raw（sha a57bd226…，`practice-cam-10-listening-test-01-with-answer`）→ 39 行覆盖 40 题、1=Ardleigh、6="beach / beaches"、7="2020"、9="429"、11&12 paired（answer="A, C"）、40="expansion"；无答案标题页不回落全文（answer_count=0）；iprog 40 行表格 → `answer_key_numbered` 1..40 身份 + `qa_complete:false`；zhan index/passage/reading 三路 `answer_authority:false`；tarof `number===q_num`、timestamps 原样保留、逐题与整体 `alignment_status:"unverified"`
- gaps:
  - 听力 t2–t4 源侧说话人为空（sp:""）→ speaker=null，不得声称官方完整；raw-280 真实内容行待 S06 PDF 核查；cam21 音频 URL 为仓库路径，文件真实性/哈希验证在 S09；cam21 数据快照尚未写入 ielts-data（S12/S14 落盘）
  - ITO 缺陷已修复：`practiceSlugs()` 原缺 `-with-answer` 变体（实测书10 practice 页 slug 为 `practice-cam-10-listening-test-01-with-answer`，post id 9736）；站上两种命名并存（另有裸模式），候选现含三种
  - TaroFlink/reader 时间戳默认 `alignment_status:"unverified"`，音频 hash 与时间基准核验在 S10；zhan 仅精读（answer_authority:false），不提升为答案权威
- next_action: S06（PDF 官方对照与题组/图表资产提取）

---

## S06. PDF 官方对照与题组/图表资产提取

- id: S06
- status: done
- files:
  - ① 提取器 `ielts-api/tools/pdf_extract.py`（PyMuPDF 逐页结构：text_layer/columns/lines/numbers/figures/needs_review/suspected_scan；`--ocr-json` 合并 OCR；`--assets` 导出图资产）；OCR 环境 `ielts-data/tools/ocr-venv`（rapidocr-onnxruntime，numpy）
  - ② 持久层适配器 `ielts-api/pdf-adapter.mjs`（extract → 规范化 page 记录 + 资产 sha256 存储 + provenance 链 raw/pdf-extract/raw/pdf-ocr/derived/pdf）；导入工具 `ielts-api/tools/import-pdf.mjs`（幂等、missing_pages/missing_assets 显式记录、`--run` 关联）
  - ③ 测试 `ielts-api/tests/ielts-pdf-extract.test.mjs`（9 用例：fixture 提取/资产导出/needs_review/suspected_scan/OCR 合并/幂等导入/缺失记录/链校验等）
  - ④ 剑20 分册候选核验（S06d）：`ielts-data/raw/pdf-source/book20-test{1,2,3,4}.pdf`（T2–T4 本轮下载，test1 自历史目录只读复制）+ 4 件证据
  - ⑤ OCR 复核产物 `ielts-data/runs/20261003T140007Z-repair/derived/ocr20/`（4 册页眉条结构图 + 深核整页）
- command:
  - S06a/S06b: `PYTHONIOENCODING=utf-8 examdata/.venv/Scripts/python.exe ielts-api/tools/pdf_extract.py --book 1|3|10 --pages … --out … --assets …`（含 `--ocr-json` 合并；剑10 fp145 乱码块 300/600dpi rapidocr 复核）
  - S06c2/S06e: `node --test ielts-api/tests/{ielts-manifest,contract,ielts-store-fetch,ielts-pte-parser,ielts-cam21,ielts-adapters,ielts-pdf-extract}.test.mjs`
  - S06d: `node scratch/s06/probe-book20.mjs`；`node scratch/s06/download-book20.mjs`；`PYTHONIOENCODING=utf-8 examdata/.venv/Scripts/python.exe scratch/s06/verify-book20.py`；`…/ocr-venv/Scripts/python.exe scratch/s06/s06_ocr.py --pdf book20-test{1..4}.pdf …`（页眉条 130 页）；`node scratch/s06/cam21-crosscheck.mjs`；`node scratch/s06/offline-regress-s06.mjs`；`python scratch/s06/consolidate-book20.py`；`python scratch/s06/gen-s06d-evidence.py`
- exit_code: 0（全部命令；S06e 回归 134/134 EXIT=0）
- evidence:
  - `evidence/S06e-node-tests.txt`（与 `S06-node-tests.txt` 同口径）：134 tests / 134 pass / 0 fail，7 文件，EXIT=0
  - `evidence/S06-provenance-chain.txt`：CHAIN OK（book3×2、book1、book10 raw+ocr+assets verified）
  - `evidence/S06-offline-regression.json/.txt`：176 entries、165 parsed、165 ok、24 partial、errors=0；totals q_missing=48 / a_missing=7 / empty_slots=1
  - `evidence/S06d-missing-resolution.json`：11 例 q_missing（48 槽）+ 5 例 a_missing（7 槽）逐项定位；import_inventory 9 次导入（7 册 145 页 124 资产，missing 全空）；raw-328 粘连头根因 + cam21 镜像对照 + 三候选修复（S12 决定）
  - `evidence/import-pdf-book{1,3,8,10,11,12,17}-*.json`（8 件导入证据）+ `derived/pdf/<book>/<sha8>/provenance-*.json`
  - `evidence/S06-cam21-crosscheck.json`：all_ok=true；4 套听力各 40 槽/40 键、multi 组 2/5/4/2（成员槽 4/10/8/4，accept 无缺失）；4 套阅读各 40 槽/40 键；8 镜像 HTML bytes+sha256 记录
  - `evidence/S06-book20-probe.json`（T2/T3/T4 status 206 真实 PDF 5.6/4.9/5.2MB）；`S06-book20-download.json`（15.7MB，sha256）；`S06-book20-verify.json`（34/35/31/30 页、text_chars=0 图像型）；`S06-book20-structure.json`（4 套均确证 Listening Part4 题面：Reclaiming urban rivers / Developing food trends / Inclusive design / The importance of birds of prey；test2 答案页含备选）
  - `evidence/s06-book10-t1-reading-key.json`：剑10 fp145 乱码块 text layer rawdict + 300/600dpi rapidocr 复核（Q34 空答案定位）
  - `evidence/s06-pages/*.txt`：书1/书3/书10 题面页文本 dump（提取过程证据）
- gaps:
  - 21-3-listening [23,24]：raw-328 粘连头（`…clothing labels. Questions 23 and 24</span>`）根因已定位；cam21 镜像同组结构干净；解析修复三候选记录在 S06d 证据，S12 融合时实施
  - 10-1-reading [34]：S06b OCR 复核完成（答案候选已提取），合并入库在 S12 融合
  - 剑1 全部缺块页、剑3 T2–T4、剑8/11/12/17 缺块页：均已提取+导入 store；offline regression 缺槽清零需 S12 融合（当前 regression 只反映 raw 源侧状态）
  - book20 分册为图像 PDF（text_chars=0），题面提取需 OCR；本轮已做页眉结构图，题面全量 OCR 按需在 S12
  - 12 例 out_of_range 警告为源侧日期/时长噪声（非缺失），3-4-reading 1 例 candidate_section_heading_skipped 已在 S05 记录
- next_action: S07（题目—答案匹配与 45 裁决迁移）

---

## S07. 题目—答案匹配与 45 裁决迁移

- id: S07
- status: done
- files: `ielts-api/answer-matcher.mjs`、`ielts-api/adjudications.mjs`、`ielts-api/tests/ielts-answer-matcher.test.mjs`、`ielts-api/tools/compare-official.mjs`
- command:
  - `node --test ielts-api/tests/ielts-answer-matcher.test.mjs`
  - `node --test ielts-api/tests/ielts-manifest.test.mjs ielts-api/tests/contract.test.mjs ielts-api/tests/ielts-store-fetch.test.mjs ielts-api/tests/ielts-pte-parser.test.mjs ielts-api/tests/ielts-cam21.test.mjs ielts-api/tests/ielts-adapters.test.mjs ielts-api/tests/ielts-pdf-extract.test.mjs ielts-api/tests/ielts-answer-matcher.test.mjs`
  - `node ielts-api/tools/compare-official.mjs --identity book=10,test=1,skill=reading --pdf scratch/s07/compare-smoke-pdf.json --answers scratch/s07/compare-smoke-answers.json --out scratch/s07/compare-smoke-out.json`（+ `--pdf-file tmp_audit_ielts/downloads/book_10.pdf` 哈希校验）
  - `node scratch/s07/smoke-matcher.mjs`
- exit_code: 0（全部）
- evidence:
  - `evidence/S07-node-tests.txt`：166 tests / 166 pass / 0 fail（8 文件，含新 32 用例），EXIT=0
  - `evidence/S07-summary.md`：交付文件、45 裁决迁移事实（分类计数/7 修正/PDF sha256）、12 必测对照、compare-official 冒烟结果
  - `scratch/s07/compare-smoke-{pdf,answers,out,hash-out}.json`：40 题 match=38 / conflict=1（Q22）/ pdf_only=1（Q34，PDF=F）；40/40 hash_verified=true
  - `ielts-api/adjudications.mjs`：45 条（option_mapping 8/representation 7/source_error 7/order_semantics 14/extraction_artifact 9；correct 7）；生成器 `scratch/s07/gen-adjudications.py`
- gaps:
  - 历史 `official_pdf_cmp_v3.py`/`match_one` 保留在历史证据目录只读，新工具不引用（已 grep 确认 ielts-api 内无引用）
  - 新审计工具接入 compare-official 在 S14；CLI 挂 `compare-official` 命令在 S13
- next_action: S08（统一分类与题目索引）

---

## S08. 统一分类与题目索引

- id: S08
- status: done
- files:
  - `ielts-api/taxonomy.mjs`（重写：14 题型规则表 + 结构回退 + pool 覆盖；新增 `match the X with/to`、`write the correct letter A,B,C`、`next to questions`、句首 `the following are`、`each` 负前瞻等模式；matching_information 增 `in which (TWO) paragraphs`；short_answer 增 `list the (TWO...)`）
  - `ielts-api/question-index.mjs`（新：INDEX_SCHEMA/CONTENT_STATUS/ANSWER_STATUS/ANSWER_MODES/CLASSIFICATION_STATUS、buildIndex、queryIndex、summarize、applyGroupVerifications）
  - `ielts-api/adjudications.mjs`（新增 GROUP_VERIFICATIONS gv-01/gv-02 + groupVerificationById；45 条 DECISIONS 未动）
  - `ielts-api/tools/build-question-index.mjs`（新：构建 + 应用官方核验 + 写 index.official_verifications/verification_issues）
  - `ielts-api/tests/ielts-taxonomy.test.mjs`（新：分类/索引/核验用例）
- command:
  - `node --check ielts-api/taxonomy.mjs`（SYNTAX_OK）
  - `cd ielts-data/runs/20261003T140007Z-repair/scratch/s08 && node regress-classify.mjs`
  - `node snapshot-classify.mjs snapshot-before-fix.json`（改动前）/ `snapshot-after-fix.json` / `snapshot-after-fix2.json` / `snapshot-after-fix3.json`（定稿）+ `node -e "…diff…"`（`diff-final.txt`、`diff-round2-3.txt`）
  - `node verify-cam21.mjs`（cam21 阅读 33 组 + 听力 33 组；产物 `verify-cam21-out.json`、`evidence/S08-verify-cam21.txt`）
  - `cd ielts-api && node tools/build-question-index.mjs`（`evidence/S08-build-index.txt`）
  - `cd ielts-api && node --test tests/*.test.mjs`（`evidence/S08-node-tests.txt`）
  - b9t1r 官方核验：`PYTHONIOENCODING=utf-8 ielts-data/tools/ocr-venv/Scripts/python.exe scratch/s08/ocr_sweep.py --book 9 --pages 1-165 --out scratch/s08/b9-ocr-sweep-150.jsonl --dpi 150` + 300dpi 全页复核（`b9-hi-300.json`）+ 600dpi 裁剪（`b9-600-p16-ynng.json`、`b9-600-p145-left.json`、`b9-600-p145-right.json`、`b9-600-p16-wordlimit.json`）
- exit_code: 0（全部）
- evidence:
  - `evidence/S08-summary.md`、`S08-node-tests.txt`（190/190 pass）、`S08-build-index.txt`、`S08-verify-cam21.txt`
  - 构建（index/question-index.json）：pages=165 groups=1366 questions=6604 answers=6604 answer_groups=14；fully_complete=6439/6604；official_verifications=2 verification_issues=0；cross_source_conflicts=3（classification_conflict/word_limit_conflict/test_numbering）；answer_status: attached 6597/missing 6/empty 1
  - 分类回退复核：48 个非直判组逐条（`scratch/s08/fallbacks-full.txt`）；17 组 independent_sentence_slots 实为 matching_features、b2t2r 21-24 实为 short_answer（"List the FOUR main ways"）、b3t1r 34-35 实为 matching_information（官方 PDF book_3.pdf 第 30 页核验）、3 处 "Which TWO" 过度匹配（b14t4r 23-24 / b16t3l 13-14 / b9t4l 5-6）修正为 mcq_multiple；`diff-final.txt` 28 组变化全部逐条复核（b1t3r 35-38 → mcq_multiple、b12t3l 18-20 → table_completion、b6t3r 10-13 → mcq_single、b8t3r 4-6 → sentence_completion）；"Which TWO" 文本模式经 b2t4l 16-20 回归后回退为结构兜底
  - cam21 验证：阅读 33/33 classified（全部 source_type+instruction）；听力 33/33 classified（instruction 19 / source_type+instruction 3 / slot_multi_select 11）；多选组 13/13 = mcq_multiple（含 t2–t4 无 "Choose TWO" 指令的 11 组经 kind=multi_select 结构兜底）；t2 s3 Q27-30 为 flow-chart completion（字母库输入格式）
  - b9t1r 官方核验（本轮新增）：gv-01 → `cambridge:9:academic:reading:1:P2:G2` [21-26] tfng→ynng（reason=official_pdf_override）、Q21-26 official 答案映射（raw 保留，raw_form_consistent=true）；gv-02 → `…:P2:G1` [18-20] 补 word_limit=NO MORE THAN THREE WORDS AND/OR A NUMBER；证据 `scratch/s08/b9-ocr-sweep-150.jsonl`（150dpi 全册）、`b9-hi-300.json`（p16/p145 300dpi）、`b9-600-p145-{left,right}.json`、`b9-600-p16-ynng.json`（600dpi 复核；book_9.pdf sha256=b25f954d…，file_page 16=printed 24、145=printed 153）；`b9-600-p16-wordlimit.json` 裁剪返回 0 词异常已记入 gv-02 notes（300dpi 全页已含完整限制行，不阻塞）
  - 回归：`node --test tests/*.test.mjs` 190/190 pass（8 文件；含新 taxonomy/index/核验用例）
- gaps:
  - b9t1r 21-26 已由 gv-01 官方核验解决（不再遗留）
  - 46 题 type=unknown / group_id=null（content_not_indexed=205 缺口，含 b11t3 阅读 Q11-13 等）→ S12 融合
  - 3 个空组已排除并记缺口：b11t3 listening P2 11-20、b14t1 listening 11-20、b20t1 listening 21-30（empty_group_excluded）
  - b10t1r Q34 answer_status=empty（raw=""）、b12 test_numbering 冲突（test 5-8 / source_test 1-4）、b3t2/b3t3/b3t4 listening PTE raw_index=null（PDF 侧已提取待融合）→ S12
  - b3t3r 22-25 shared_prompt 被整段 passage 文本污染；b9t1r P2 G2 shared_prompt 被 P3 正文污染 → S11
  - 其余 11 组 pool_overrides_instruction 的 pool 值与指令一致，未逐一官方核验（如实记录）
- next_action: S09（音频目录与身份验证）→ 已完成，见下方 S09 段

---

## S09. 音频目录与身份验证

- id: S09
- status: done
- files: `ielts-api/audio-catalog.mjs`、`ielts-api/tools/verify-audio.mjs`、`ielts-api/tests/ielts-audio-catalog.test.mjs`
- command: `node tools/verify-audio.mjs --download`（ALL parts, queue=302）→ `--fetch-cam21-pages --reuse-pages` → `--mark-cam21` → `--tree-check`；`node --test tests/*.test.mjs`
- exit_code: 0 / 0 / 0 / 0 / 0
- evidence: `evidence/S09-summary.md`、`S09-full-download.txt`、`S09-priority-download.txt`、`S09-range-probe.txt`、`S09-cam21-pages.txt`、`S09-mark-cam21.txt`、`S09-tree-check.txt`、`S09-node-tests.txt`
- results: catalog records=362（available 320 / verified 16 cam21 / candidate 26 full_test 派生）；tree-check checked=336 matched=336 mismatched=0 not_applicable=26；cam21 4 页 sha256 校验通过、16/16 verified；请求 683 条 ≈4.13 GiB，errors 7 条均为传输重试后成功；tests 234/234 pass
- gaps: 26 条 full_test 派生记录无独立文件（不冒充 verified）；逐题时间戳区间未生成 → S10；whisperx 模型已就绪（model-lock.json）
- next_action: S10（音频逐题对齐）

---

## S10. 音频逐题对齐

- id: S10
- status: done
- files: `ielts-api/audio-matcher.mjs`、`ielts-api/alignment-provider.mjs`、`ielts-api/tools/run-alignment.mjs`、`ielts-api/tools/align-audio.py`、`ielts-api/tools/build-alignment-gold.mjs`、`ielts-api/tests/fixtures/alignment-gold.json`、`ielts-api/tests/ielts-audio-matcher.test.mjs`
- command: `python tools/align-audio.py --audio <cam21 t1p1.mp3> --out <result.json>`（独立进程冒烟）→ `node tools/run-alignment.mjs --targets verified` → `node tools/run-alignment.mjs --targets verified --gold tests/fixtures/alignment-gold.json --reuse-asr` → `node tools/run-alignment.mjs --targets maslow-priority`（后台任务）→ `node tools/build-alignment-gold.mjs --asr-dir …/alignment --crosscheck` → `node --test tests/*.test.mjs`
- exit_code: 0 / 0 / 0 / 0 / 0 / 0
- evidence: `evidence/S10-summary.md`、`S10-align-audio-smoke.txt`、`S10-run-alignment-cam21-asr.txt`、`S10-run-alignment-cam21-gold.txt`、`S10-run-alignment-maslow.txt`、`S10-gold-rebuild.txt`、`S10-crosscheck.txt`、`S10-whisperx-install.txt`、`S10-node-tests.txt`
- results: 33 identity 对齐产物（17 maslow-priority + 16 cam21）；cam21 ASR 16/16 ok，gold 窗口注入后 verified 66 窗（t1P1 10/10、t3P1 10/10、t4P4 10/10、t4P1 9/10 等）；maslow 17/17 ASR ok、errors 0、no_question_parts 12（b3t2–4 空快照属预期）；gold fixture parts_with_windows=10 / windows=103 / crosscheck {asr_confirmed 66, not_text_verifiable 28, no_match 9}；whisperx 3.8.6（whisper-small + wav2vec2-base-960h, int8/cpu）；tests 249/249 pass
- gaps: maslow 其余 Part 无独立标签源保持 unverified（不造假窗）；problems=2 为 answer_form_mismatch（t1s4 q31 metals/metal、t3s4 q33 holidays/holiday）严格保持 no_match；字母类答案 not_text_verifiable 不计对齐完成
- next_action: S11（原文逐 Part 回落与截尾检查）→ 已完成，见下方 S11 段

---

## S11. 原文逐 Part 回落与截尾检查

- id: S11
- status: done
- files: `ielts-api/ielts-api.mjs`（listeningScript/testScript/wholeBookScript 重构 + countCleanScriptParts）、`ielts-api/transcript-matcher.mjs`、`ielts-api/tests/ielts-transcript.test.mjs`
- command: `node --check ielts-api.mjs`；离线 mock `listeningScript(999)` / `listeningScript(5)`；`node --test contract.test.mjs`；`node --test tests/*.test.mjs`；live 冒烟 `scratch/s11-smoke-listeningscript.mjs` + `scratch/s11-smoke-aggregate-non21.mjs`（aggregate 非剑21 路径）
- exit_code: 0 / 0 / 0 / 0 / 0 / 0
- evidence: `evidence/S11-summary.md`、`S11-contract-tests.txt`、`S11-node-tests.txt`、`S11-live-smoke-listeningscript.txt`、`S11-live-smoke-aggregate.txt`
- results: B0–B4 落地（多源逐 Part 回落 + review/partial/cross_source_agreement 诚实语义 + maslow unsegmented skip + aggregate 消费新形状）；maslowGood 修复：整本捷径改为 countCleanScriptParts≥16 且 ≥40k 字符 → 剑1整本 16/16 parts、missing=0；live 冒烟 (1,1)/(3,2)/(10,1)/(19,4)/(20,2)/(21,1) 全过，aggregate(21,1) completeness 全 true；非剑21 aggregate 冒烟 aggregate(1,1) 5/5 全 true、aggregate(20,2) 4/5（阅读缺失属已知 book20 缺口，不冒充）；contract 9/9、tests 249/249 pass
- gaps: coverage() 仍按旧整本形状消费（S12 重写）；其余册整本未逐册 live 抽查（S12/S14 审计覆盖）；b3t3r+b9t1r shared_prompt 污染 defer S12
- next_action: S12（resolver/coverage 与融合）

---

## S12. resolver/coverage 与 ielts-api 重写

- id: S12
- status: done
- files: `ielts-api/resolver.mjs`、`ielts-api/coverage.mjs`（新增）、`ielts-api/question-index.mjs`、`ielts-api/taxonomy.mjs`、`ielts-api/book3-listening.mjs`（新增，剑3 T2–T4 听力转换器）、`ielts-api/cam21.mjs`（表格/地图/流程图资产 + 字数限制）、`ielts-api/html-questions.mjs` + `ielts-api/pte.mjs`（shared_prompt 截断修复）、`ielts-api/ielts-api.mjs`（包装兼容）、`ielts-api/tools/build-question-index.mjs`；测试 `tests/ielts-resolver.test.mjs`、`tests/book3-listening.test.mjs`、`tests/ielts-taxonomy.test.mjs`、`tests/ielts-pte-parser.test.mjs`（+B15）
- command: `node tools/build-question-index.mjs`（重建）→ `node tmp_s12_coverage_full.mjs`（21 册全量 coverage）→ `node --test tests/*.test.mjs` → `node --test contract.test.mjs` → 修复前后对比 `tmp_s12_sp_probe.mjs`/`tmp_s12_diff.mjs`/`tmp_s12_diff2.mjs`
- exit_code: 0 / 0 / 0 / 0 / 0
- evidence: `evidence/S12-rebuild-index.out`、`S12-rebuild-index-2.out`、`S12-cam21-assets.txt`、`S12-script-status-table.txt`、`S12-b3-rebuild.txt`、`S12-b3-index-diff.txt`、`S12-coverage-run.txt`、`S12-coverage-full.json`、`S12-coverage-summary.md`、`S12-regression-tests.txt`、`S12-regression-contract.txt`、`S12-sharedprompt-fix-rebuild.txt`、`S12-sharedprompt-fix-diff.txt`、`S12-sharedprompt-fix-tests.txt`、`S12-index-before-sharedprompt-fix.json`、`S12-unknown46-composition.txt`
- results: resolver 统一 resolveTest/Reading/Listening/Audio/Pdf + coverage `ielts.coverage/1`；全量 370 units（reading/academic 84、listening/shared 84、writing/academic 84、speaking/shared 84、reading/general 17、writing/general 17）；unit_status={partial:168, not_extracted:154, unverified:48}、fully_complete_units=0（诚实语义：剑3 answer-only、reader 单篇、失败音频、剑20 T1 等不冒充 complete）；索引 pages=168 groups=1396 questions=6724 answers=6724 answer_groups=16、fully_complete=6588/6724、issues=0；cam21 资产：b21 320 题全 complete（表格/地图/流程图资产 + WORD AND/OR A NUMBER 字数）；剑3 T2–T4 听力转换 160 题（154 complete/6 partial，图片选项如实标 partial）；shared_prompt 污染修复：>4000 桶 69→0、1200-4000 桶 9→0、92 组缩短>200、questions/answers 键数与值零变化、每页 counts 零差异；测试 271/271（含 B15）、contract 9/9
- gaps: 46 题 unknown（pte 页、no_group、missing_content，12 个 book/part 组合）无 alternate source → 记 source_missing；fully_complete_units=0 属诚实语义非回归；音频对齐完成 0（S10 33 identity 产物、66 verified 窗）；剑20 分册 images-only 仍 partial
- next_action: S13（三入口统一 CLI/Node HTTP/FastAPI）

---

## S13. 三入口统一（CLI/Node HTTP/FastAPI）

- id: S13
- status: done
- files: `examdata/src/examdata/api/ielts.py`（28 路由：+reading-enriched、v2 variant/分页）、`ielts-api/v2-api.mjs`（variant=gta/gtb、type/offset/limit 分页、coverage invalid_test）、`examdata/tests/test_ielts_resolver_contract.py`、`ielts-api/tests/ielts-routes.test.mjs`、`scratch/s13/fetch-guard.cjs` + `scratch/s13/compare_entries.py`
- command: `node --test tests/*.test.mjs`；`node --test contract.test.mjs`；`node --test tests/ielts-routes.test.mjs`；pytest 3 文件；`node scratch/s13/compare_entries.py`（25 cases 三入口一致性 + fetch guard）
- exit_code: 0 / 0 / 0 / 0 / 0
- evidence: `evidence/S13-node-tests.txt`、`S13-contract-tests.txt`、`S13-routes-tests.txt`、`S13-pytest.txt`、`S13-three-entry-consistency.txt`、`S13-three-entry-report.json`、`S13-fetch-guard.log`、`S13-summary.md`
- results: 三入口（CLI / Node HTTP / FastAPI）共享 resolver/v2-api 语义；FastAPI 28 路由含 reading-enriched（默认 passage=1）与 v2 test `?variant=`、v2 questions `type=&offset=&limit=`（limit≤500）；25/25 cases 三方输出一致；非法批次 16 调用 fetch_delta=0（fetch-guard 证明零网络）；reading-enriched 剑19 单篇 live ok(13题)、剑20 404 如实（不回落冒充）；node 287/287 + contract 9/9 + routes 16/16 + pytest 19 passed 1 skipped
- gaps: reader 源无剑20（images-only）；live happy path 仅剑19 单篇抽验（全册抽查由 S14 审计工具覆盖）；一致性脚本暂留 scratch
- next_action: S14（审计/刷新/索引工具）

---

## S14. 审计/刷新/索引工具

- id: S14
- status: done
- files:
  - `ielts-api/tools/audit-all.mjs`（790 行，sha256 d18f47c6…4d5f）：offline/dataset 双模式；matrix.json+md、errors.jsonl、questions.jsonl；--verify-assets/--verify-audio（流式 sha256）；退出码 0/1/2/3
  - `ielts-api/tools/refresh.mjs`（668 行，sha256 643238d6…304d）：本地复用固化（网络请求恒为 0）；raw/pdf 内容寻址存储；音频 catalog 核对；ledger+report+checkpoint；CLI 全参数校验；dry-run 零写入
  - `ielts-api/tools/build-index.mjs`（287 行，sha256 329e4a05…8cc1）：构建 indexes/manifests/normalized 并原子发布 current；零网络
- command（全部实测，逐条 stdout+exit code 见 evidence）:
  - C1 `node ielts-api/tools/audit-all.mjs --offline --fixtures ./ielts-api/tests/fixtures --out ./ielts-data/runs/offline-audit`
  - C2 `node ielts-api/tools/refresh.mjs --books 1,3,10,20,21 --variant academic --skills reading,listening --jobs 2 --max-requests 300 --resume`
  - C3 `node ielts-api/tools/refresh.mjs --books 1-21 --variant academic --skills reading,listening --jobs 2 --max-requests 1500 --resume`
  - C4 `node ielts-api/tools/refresh.mjs --books 1-21 --variant general --skills reading,writing,speaking --jobs 2 --max-requests 800 --resume`
  - C5 `node ielts-api/tools/refresh.mjs --books 1-21 --variant academic --skills writing,speaking --jobs 2 --max-requests 800 --resume`
  - C6 `node ielts-api/tools/audit-all.mjs --dataset current --verify-assets --verify-audio --out ./ielts-data/runs/full-audit`
  - C7 `node ielts-api/tools/build-index.mjs --dataset current`
  - 对齐重跑 `node ielts-api/tools/run-alignment.mjs --only cambridge:3:shared:listening:{2,3,4}:P{1..4} --force --reuse-asr`（12 identity）
  - CLI 校验 15 例（3 工具参数校验 exit 2）+ dry-run 2 例（零写入）
- exit_code: C1=0；C2=0；C3=0；C4=1（真实缺口，预期）；C5=1（真实缺口，预期）；C6=1（overall=partial，诚实语义）；C7=0；对齐重跑=0；CLI 校验全部=2（符合）；dry-run 全部=0
- evidence:
  - `evidence/S14-summary.md`（总摘要）、`S14-command-battery.txt`（C1–C7 汇总）
  - 逐命令全文：`S14-cmd1-audit-offline.txt`、`S14-cmd2-refresh-subset.txt`、`S14-cmd3-refresh-academic.txt`、`S14-cmd4-refresh-general.txt`、`S14-cmd5-refresh-writing-speaking.txt`、`S14-cmd6-audit-full.txt`、`S14-cmd7-build-index.txt`
  - `S14-cli-validation.txt`（15 校验 + 2 dry-run 前后文件数对比）
  - `S14-alignment-rerun.txt`（12 identity 重跑：processed=12 errors=0 asr_ok=12）、`S14-alignment-matrix.json`（33 文档 0 stale）
  - 运行产物：`runs/offline-audit/`（matrix.json/md+errors+questions）、`runs/full-audit/`（同上）、`refresh/<scope>/ledger.json+report-*.json`、`runs/<runId>/checkpoint.json`
- results:
  - offline 审计 errors_total=0 overall=pass（12 stale 修复后）
  - full-audit：combos=168（21册×4套×2技能）；结构检查（阅读 3 passage/听力 4 Part/manifest 题号对照）全过；combos_with_issues=5 全部为 S06d 已记录源缺口（b1 Q41×3套+Q40、b1r Q41、b10r Q34 empty）；errors_total=1（b1t2l P4 diagram 未匹配）；audio 336/336 verified_hash、hash_mismatch=0、file_missing=0；assets 1936（broken=0、expected_assets 1 未匹配）
  - refresh 固化：raw 193 bodies（practicepteonline 170/cam21 8/pdf-extract 9/ieltstrainingonline 5/pdf-ocr 1）、pdf 15 文件 430MB、audio 336 文件 2.1GB；C3 全量 168/168 skipped_verified（resume 幂等）
  - 缺口如实：general gaps=36（册 9/16/18/19/20 no_text_layer ×6 + 册 21 no_local_pdf ×4）；academic writing+speaking pdf_verified=120/no_text_layer=40/missing=8
  - 12 个 cam3 T2–T4 对齐文档从 doc_questions=0 修复为 10（与 index 一致）；coverage 全 unverified（cam3 音频身份未核验，按 S10 语义不伪造 verified）
- gaps:
  - b1t2l P4 diagram（Q40-41，p45）本地无资产 → expected_assets_unmatched（S06 已记，需外部资源补图）
  - 7 个空/缺答案槽位（b1 六处 + b10r Q34）为源缺口，S06d 已逐项定位（answer_pages 已导入，融合未做）→ 保留原值/空值不移位，待官方逐题核验或外部源
  - 册 9/16/18/19/20 无文字层 PDF、册 21 无本地 PDF → pdf_no_text_layer/pdf_missing（refresh checkpoint 已持久化）
  - refresh 网络请求恒为 0（本地复用设计）；预算触顶 exit 3 路径由 fetch-source 层测试覆盖（4 组），refresh 工具层未现场触发
- next_action: S15（fixtures 集中登记 + e2e/verify-decisions/check-route-inventory + 全套回归）

---

## S15. fixtures 与全套回归

- id: S15
- status: done
- files:
  - `ielts-api/tests/fixtures/manifest.json`（sha256 1c90747f…31ea）：fixture 登记清单（sha256/字节/用途/期望值独立来源/读取入口/数据依赖），覆盖全部测试夹具
  - `ielts-api/tests/ielts-e2e.test.mjs`（596 行，sha256 b09f2c10…fd7f）：22 个端到端案例，全部经真实 CLI/refresh/audit-all 子进程 + 真实数据
  - `ielts-api/tools/verify-decisions.mjs`（290 行，sha256 6d4d0b97…c97c）：45 裁决 + 7 修正 + 2 组核验共 39 项校验
  - `ielts-api/tools/check-route-inventory.mjs`（243 行，sha256 f349f1d0…ce26）：独立端口 8799 校验 v2 路由 + Range 206 + 404 + 三入口清单比对
- command（全部实测，逐条 stdout+exit code 见 evidence）:
  - `cd ielts-api && node --test tests/ielts-e2e.test.mjs`
  - `cd ielts-api && node --test tests/*.test.mjs`
  - `cd ielts-api && node --test contract.test.mjs`
  - `cd ielts-api && node tools/verify-decisions.mjs`
  - `cd ielts-api && node tools/check-route-inventory.mjs`
  - `examdata/.venv/Scripts/python.exe -m pytest examdata/tests/test_api_ielts.py examdata/tests/test_ielts_concurrency.py examdata/tests/test_ielts_resolver_contract.py`（EXAMDATA_TEST_LIVE=0；EXAMDATA_DATABASE_URL=sqlite:///:memory:；EXAMDATA_IELTS_DATA_DIR=真实 ielts-data；EXAMDATA_IELTS_DIR=ielts-api）
- exit_code: e2e=0（22 pass/0 fail）；全套 Node=0（309 pass/0 fail）；contract=0（9/9）；verify-decisions=0（39 passed/0 failed）；route-inventory=0（11 passed/0 failed）；pytest=0（19 passed/1 skipped）
- evidence:
  - `evidence/S15-summary.md`（总摘要）
  - `evidence/S15-e2e-tests.txt`、`S15-node-tests.txt`、`S15-contract-tests.txt`、`S15-verify-decisions.txt`、`S15-route-inventory.txt`、`S15-pytest.txt`
- results:
  - Node 基线 287（S13）→ 309（+22 e2e）；contract 9、pytest 19+1skip 与基线持平
  - e2e 覆盖锚点：剑1T2 41 题、剑10T1 Q34 空答案、剑3T2–4 40 题、剑21 P3 多选组 accepted sets、general 变体路由、逐 Part 原文回落（剑1 available/剑3 source_missing）、篡改音频 hash 被 audit-all 捕获、时间戳单位/时钟/偏移、比较器单字母拒绝、裁决 stale 语义、SIGTERM ledger 完整性
  - 修复：coverage-v2 空目录输出约 1.1MB 超过 spawnSync 默认 maxBuffer（ENOBUFS）→ 3 处 spawnSync 加 64MB maxBuffer，首跑 21/22 → 重跑 22/22
- gaps:
  - 无新增数据缺口；e2e 断言均为本机实测值（真实数据+真实子进程），无 mock 充当通过
- next_action: S16（文档与另一副本同步）

---

## S16. 文档与另一副本同步

- id: S16
- status: done
- files:
  - `examdata/docs/IELTS_API.md`（sha256 adf48d74…d868）：答案键口径（阅读 3360/听力 3346/剑21 阅读160键+听力147键）、覆盖表后口径 blockquote、测试命令补 pytest resolver_contract/concurrency、§5 env 表补 EXAMDATA_IELTS_DATA_DIR、文末指向 AUDIT_REPORT/REMAINING_GAPS（147 行）
  - `ielts-api/DEVELOPMENT.md`（0b5c9caf…2ade）：L4 端到端口径 3360/3346 答案键、PDF 20/20（剑20 Test1 分册）
  - `ielts-api/ielts-api.mjs`（d25a56c2…0c3a）、`ielts-api/lfs.mjs`（bc99082e…d40b）、`ielts-api/verify-pdfs.mjs`（a8ee19f0…e28f）：PDF 范围表述（剑1–19 整本 + 剑20 Test1 分册，20/20 实测）；去“唯一/整本”
  - `ielts-api/API.md`（c5debe7e…d7c7）：v2 段/覆盖块/CLI 注释（前窗口完成，本步复核）
  - `examdata/src/examdata/api/ielts.py`（9d79ee00…11d3）：info 路由 env 字典 +MAX_CONCURRENT/+QUEUE_TIMEOUT/+DATA_DIR
  - 另一副本同步记录 `changed-files.json`（34ac2890…f1e7）：add 70 + overwrite 12，conflict 0，failed 0
- command:
  - `node --check ielts-api.mjs / lfs.mjs / verify-pdfs.mjs`；`py_compile ielts.py`
  - `python ielts-data/runs/20261003T140007Z-repair/scratch/sync-other-copy.py --execute`
  - `cd ielts-api && node --test tests/*.test.mjs`（主副本与另一副本；另一副本加临时 junction，见 evidence）
  - `python ielts-data/runs/20261003T140007Z-repair/scratch/protected-recheck.py`
  - `netstat -ano | grep :8000`；`curl -s -m 5 http://127.0.0.1:8000/api/v1/ielts/info`
  - `examdata/.venv/Scripts/python.exe -m pytest examdata/tests/test_api_ielts.py examdata/tests/test_ielts_concurrency.py examdata/tests/test_ielts_resolver_contract.py`（env 同 S15）
- exit_code: syntax=0（3×node --check + py_compile）；sync=0；主副本 node=0（309 pass/0 fail）；protected-recheck=0；8000 检查=0；pytest=0（19 passed/1 skipped）
- evidence:
  - `evidence/S16-summary.md`（0862ae7f…17af）、`S16-doc-diff.txt`（d3eb7cd2…f922）、`S16-sync.json`（4db1fc2f…e97e）、`S16-sync-verify.txt`（a60b10df…4608）、`S16-syntax.txt`（490a87b0…bc7a）
  - `S16-main-tests.txt`（f5f02a97…f8d6）、`S16-other-tests.txt`、`S16-other-tests-round2.txt`（b47ecf94…d1d0）、`S16-both-copies-tests.txt`（6f8922c0…8484）
  - `S16-protected-recheck.txt`（4de24231…5514）、`S16-port8000.txt`（1682f961…79f3）、`S16-pytest.txt`（e0551818…43ca）
  - 备份 `backup/other-copy-2026-10-05/`（12 文件）
- results:
  - 同步: add 70 + overwrite 12 / conflict 0 / failed 0；12 覆盖文件对方均=S01 基线 hash（无独立修改），覆盖前已备份；对方独有 12 文件保留未动；同步后校验 missing 0/mismatch 0；2026-10-05 复核 changed-after-sync=0
  - 两副本测试: 主 309/309/0 skip；另一副本 round1（无 junction）274 pass/8 fail（8 条全为缺工作区 raw 源 tmp_audit_ielts，非代码缺陷），round2（临时 junction ielts-data+tmp_audit_ielts）307 pass/0 fail/2 skip（2 skip 需 examdata venv）；强制 venv 后 pdf-extract gold 被防篡改路径守卫拒绝（跨工作区路径字符串不一致，预期行为）；junction 已移除，default-workspace 复原
  - 受保护复核: adapters/markscheme/specs changed=0/missing=0（新增项全为 __pycache__ 字节码）；edexcel_papers/pipeline.py changed=1（0ee9029cf869→c3c64aff46f2，mtime 2026-10-05 02:31:18 +0800，外部并发工作所为，非本任务——当日 00:10–03:08 另有 timetable/toefl/materials/paperqa 等外部修改）；DB examdata.db 变化（运行中服务/并发写入，不能归咎本任务）；backup DB same=True；git head=d8e64a6 不变，dirty=1003（含本任务允许修改）
  - 8000 服务未重启（PID 36036 运行中，info 200 JSON）；FastAPI pytest 19 passed/1 skipped
- gaps:
  - examdata 侧文件（ielts.py、docs/IELTS_API.md、examdata/tests）不属另一 ielts-api 副本同步范围（不同仓库），未同步
  - 另一副本 2 条 skip 与 1 条守卫拒绝为环境路径差异（缺 examdata venv；跨工作区 OCR 缓存路径守卫），非代码缺陷
  - edexcel_papers/pipeline.py 外部变更与生产 DB 变化已记录于 S16-protected-recheck.txt
- next_action: S17（结果报告与剩余缺口）

---

## S17. 结果报告与剩余缺口

- id: S17
- status: done
- files:
  - `docs/ielts/IELTS_IMPLEMENTATION_RESULT.md`（32913 B）：A01–A16 逐项修复结果、测试命令与退出码、两副本 hash、受保护边界、not_run 清单、恢复命令（11 节）
  - `docs/ielts/IELTS_REMAINING_GAPS.md`（17288 B）：G1–G13 全部缺口（7 空答案槽 / 1 资产未匹配 / 46 unknown / 25+25 缺选项资产 / 39 partial / PDF 版次缺口 / 26 candidate 音频 / 33 identity 66 verified 对齐状态 / writing-speaking 开放题 / 官方核验 2 裁决 / 3 跨源冲突 / S07 遗留），固定列 identity·skill·Q·gap_kind·expected·observed·source attempts·hashes·reason·next_step·needs_external
  - `docs/ielts/EXECUTION_CHECKLIST.md`（本文件）：总览表 S15–S17 转 done + 本段
  - `ielts-data/manifests/rev-8b21015ab64bb73c/coverage.md`（45030 chars，370 units 明细表，从 coverage.json 原样渲染）
- command:
  - `python ielts-data/runs/20261003T140007Z-repair/scratch/gen-coverage-md.py`（渲染 coverage.md）
  - `python ielts-data/runs/20261003T140007Z-repair/scratch/update-checkpoint-s16.py`（stage→S17）
  - 数字复核脚本：`scratch/classify-changed.py`、`scratch/gaps-extract.py`、`scratch/gaps-extract2.py`
  - 引用复核：`sha256sum tmp_audit_ielts/downloads/book_9.pdf book_10.pdf`；`grep` alignment/*.json 覆盖率复算
- exit_code: 0（渲染/更新/复核脚本全部 exit 0）
- evidence:
  - `docs/ielts/IELTS_IMPLEMENTATION_RESULT.md`、`docs/ielts/IELTS_REMAINING_GAPS.md`、`ielts-data/manifests/rev-8b21015ab64bb73c/coverage.md`
  - 数字复核产物：coverage.json（sha256 7f1de902…d7c7，units=370/partial 168/not_extracted 154/unverified 48/complete 0）、index stats（6724 题；attached 6717/missing 6/empty 1；unknown 46）、full-audit errors 1（b1t2l P4 diagram）、audio catalog 362（320/16/26）、alignment 33 文件 331 题 66 verified
  - `ielts-data/runs/20261003T140007Z-repair/checkpoint.json`（stage=S17，S01–S17 全 done，含 files/results/evidence 摘要）
- results:
  - 三份报告齐备且相互引用；RESULT 中两副本 hash 与 changed-files.json 一致（add 70/overwrite 12/conflict 0/failed 0；changed-files 分类 modules 28/tools 27/tests 22/data 3/docs 2=82）
  - 报告数字全部为 2026-10-05 本窗口实测复核值（非历史报告引用）；历史报告未被当作当前全题通过证据
- gaps:
  - S07 遗留：`tools/compare-official.mjs` 未接入 `audit-all` 自动流程（CLI 已暴露；因逐题 PDF 值未持久化而保留人工调用）
  - 其余缺口全部登记于 `IELTS_REMAINING_GAPS.md`（G1–G14），含 needs_external 标记
- next_action: 无（S01–S17 全部完成；后续推进项见 REMAINING_GAPS 的 next_step 列）

---

## S18. 官方答案逐题核验扩展（15 册官方键提取 + 119 cell 比对）

- id: S18
- status: done（比对执行完成；book11 页→套错位重比对调查完成（G14，2026-10-05）：旋转在来源侧确证、索引映射逐格登记、231 条冲突作废；G14 两项跟进闭环至本地证据上限——t4R 19–26 部分裁决（版式异常确证+意图值重建，Q24 双值保留）、pte-4L unverified（512 页 OCR 0 真命中））
- files:
  - 新增 `ielts-data/runs/20261003T140007Z-repair/official-keys/`：15 册（1–8、10–15、17）官方 PDF 键提取产物 = 每册 `_pages.json` + 8 个 `test_T_{reading,listening}.json`（book1 另含 `test_gt_listening.json`；book12 用 book-internal test 5–8 编号）+ `ocr/` 工作区 + `visual-fixes.json`
  - 新增 `ielts-data/runs/20261003T140007Z-repair/scratch/s18/`：`answers/`（我方答案 dumper 产物：21 册 + `_manifest.json`）、`compare/`（119 个逐 cell 比对 JSON + 119 个运行 log）、`compare-batch.sh`、`aggregate-compare.py`、`verify-book11-shift.py`；`probe-b11-pages.py` 因 venv 无 pypdf/PyPDF2 未运行（放弃，不再重试同法）
  - book11 重比对追加（`scratch/s18/`）：`check-align.py/.txt`（四路对照）、`index-rotation-check.py/.txt`（索引旋转校验）、`book11-mismatches.py/.txt`（三方逐题差异）、`book11-deepdump.py/.txt`（全量转储）、`page12{1,3,4}-crop-*.png`（13 张目视裁剪图）
- command:
  - `bash ielts-data/runs/20261003T140007Z-repair/scratch/s18/compare-batch.sh`（119 cell 批量 compare-official；book14 t1 reading 无官方键 → NO-PDF）
  - `python ielts-data/runs/20261003T140007Z-repair/scratch/s18/aggregate-compare.py`（聚合 → S18-official-compare.json/.md）
  - `python ielts-data/runs/20261003T140007Z-repair/scratch/s18/verify-book11-shift.py`（book11 错位矩阵复算）
  - book11 重比对（全部 exit 0）：`python scratch/s18/check-align.py`、`python scratch/s18/index-rotation-check.py`、`python scratch/s18/book11-mismatches.py`、`python scratch/s18/book11-deepdump.py`
- exit_code: 0（119/119 cell EXIT=0，error cells=0；聚合、复算与重比对脚本 exit 0）
- evidence:
  - `evidence/S18-official-compare.json`（sha256 9aaa37085c811cb9280a0b971c8c1e8113baa58d41f8cbf21cbcb6e283d35db9）
  - `evidence/S18-official-compare.md`（1211 行：119 cell 表 + totals + 每 cell 前 20 条冲突明细；sha256 211f449a92eda1549947a140411a5d79ce03e928722ace6ab82c0d84187d6c48）
  - `evidence/S18-compare-batch.txt`（121 行，末行 COMPARE-ALL-DONE；sha256 5b23fba5aa86bf53e452211d6ac92e1c2094a972abf694661d1b7bb74c67007f）
  - `evidence/S18-book11-shift-check.txt`（sha256 96fd90ee2de2a459b0ef18a09d7ef6740c26e3244fd18ffd3b17467a734a49a0）
  - `evidence/S18-book11-remap.md`（book11 重比对完整证据：旋转表/索引校验/目视读数/保留冲突/提取缺陷/输入 sha256；sha256 1e58248cd19b986175a3c9f00268aa969b5486cc4b138efb9771629cedd9e6aa）
  - `evidence/S18-book11-remap-followup.md`（G14 跟进：t4R 19–26 四通道复核+错位模型+语义核验+部分裁决；pte-4L 512 页 OCR 定源 0 真命中 unverified；含 45 个 g14b*/g14b2* 文件与关联输入 sha256；sha256 3b877380b5dac7a5eb98cbf0abcc36abe2a27ffcbaacfbc8a783e2bb621da96e）
- results:
  - 覆盖 15 册 × 8 cell = 119 cell；totals: total 4764 / match 2833 / conflict 985 / pdf_only 6 / answer_only 939 / missing 1 / unverified 946
  - 冲突分类: plain_diff 786（pdf_superset 202 / disjoint 485 / punct_case_only 61 / idx_superset 38）+ alt_match 124 + alt_no_match 68 + nonascii_ocr 7
  - 点名项: 剑1 T2 听力 41 题（match 24 / conflict 15 / pdf_only 2）；剑3 T2–T4 六 cell 各 40 题连续；剑10 T1 阅读 Q34 = pdf_only（全索引唯一 empty，保持不移位）；全对样例 book10 t3 听力 40/40 + 阅读 40/40、book12 t6 听力 40/40、book7 t3 听力 40/40、book7 t4 阅读 40/40
  - 剑10 T1 阅读 S18 严格重跑 match=36 / conflict=3（Q9/Q10/Q12 变体形）/ pdf_only=1，取代 S06 冒烟值（Q22 现为 match）
  - book11 重比对（G14，2026-10-05）: 旋转规则 pte-2→书 t1、pte-3→书 t2、pte-4→书 t3、pte-1→书 t4（回绕）；书 t4L==pte-1L（全等）、书 t4R==pte-1R（1–18、27–40）、书 t3R==pte-4R 30/30；INDEX tN == pte-N 逐格 0 差异（34/34、40/40、40/40、33/33、30/30、33/33、36/36、40/40）⇒ 索引 tN 持书 t(N−1) 答案；页 121=t3L 40 行、页 123=t4L 配对展开==INDEX t1L S3、页 124=t4R 40 行（目视裁决）；原 231 条冲突作废；保留冲突 3 项（t4R Q9、t4R 19–26、t2R Q5，双值保留）与 pte-4L 孤儿登记（两项跟进结果见下行）
  - book11 G14 跟进（2026-10-05）: t4R 19–26 部分裁决——印块四通道读数 [19 D,20 TRUE,21 TRUE,22 NG,23 TRUE,24 FALSE,25 C,26 A]；错位模型 印块[21..26]==意图[20..25] 6/6 + 两处组内非法值 ⇒ 版式异常确证；意图值重建 [19 NG,20 T,21 NG,22 T,23 F,24 C,25 A,26 E]（20–23/25 三方一致；Q24 双值 C 主/D pte 单源）；pte-4L 定源 unverified（5 册 512 页 OCR + 31 PRIMARY + 20 SECONDARY 模式检索 0 真命中，2 假阳性；对象 practicepteonline "IELTS Listening Test 80"）
- gaps:
  - book11（G14 已闭环至本地证据上限）：t4R 19–26 部分裁决（版式异常确证；意图值重建；Q24 保留 C/D 双值）——待外部独立来源（不同印次/勘误页）；pte-4L unverified——512 页 OCR + 全资源检索 0 真命中，待 pte 源独立键/来源册信息
  - 5 册无文字层（9/16/18/19/20）+ 剑21 同源镜像 + GT 无索引，未纳入本轮比对
  - answer_only 939 集中于 b13/14/15（176/177/146）；`//` 多值口径未进比较器；待复核样本 book12 t5 R Q4/Q38、book15 t4 R Q7
  - compare 证据未写回索引 official_verifications（仍 2 条 gv-01/gv-02）
- next_action: 无（book11 G14 两项闭环至本地证据上限并登记于 `IELTS_REMAINING_GAPS.md` G14；两项外部核验路径见 G14 下一步）；其余见 G11/G13
