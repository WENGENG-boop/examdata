# 审查报告

审查对象：`C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api` 与同内容的 `C:/Users/weo/Desktop/api/ielts-api`；增量网关 `examdata/src/examdata/api/ielts.py`。来源会话：`session_12f051fb-2b68-4452-a8dc-a8b0fb451d1b`。续作日期：2026-10-02。

证据严格分层：以下“历史实测”指已读取的2026-10-01原始输出/JSON/下载文件；“本轮复测”指本次实际执行。本轮没有重新下载全部20本、重扫全部168套或重跑全部CLI示例。2026-10-02 14:05:55 CIE续跑出现502后停止所有新上游请求，本报告后续检查只读本地文件或使用离线mock。原始审查要求未全部重新完成，不宣称全量验收。

## 结论摘要

- 总体判定：**有条件通过**，适用于本地学习聚合及三源网关；“完整教材/完整题干/全网唯一/永不异常”的泛化宣称不通过。
- 本轮新增发现：严重1项、中等3项、轻微1项，均已落实局部修复；没有声称全部原始审查项已验收。
- 本轮Node契约回归2/2通过，实际Node子进程网关联测4项通过；CIE索引、Edexcel直链、IELTS阅读均在同一服务返回200。全量来源覆盖数字是历史证据，不是本轮重新爬取结果。

## 宣称核验表

| # | 宣称 | 声称值 | 可复核结果 | 判定 | 证据 |
|---|---|---|---|---|---|
| 1 | 阅读 | 84套/3360答案 | 历史首扫84/3360条，其中3359非空；剑10T1随后修复。后续回归84/3360，但只存计数/缺题号，不能证明全部非空 | 有限通过 | `../tmp_audit_ielts/pte_sweep.json`、`regression_after_fixes.json`；`full_regression.mjs` |
| 2 | 听力 | PTE 81套/3239答案 | 历史PTE确为81/3239；新增iprog剑3 T2–T4后聚合84/3346 | 通过来源覆盖；完整题干有缺口 | `pte_sweep.json`、`cov_iprog.json`、`final_agg20_1.json`；组合题及 `questions_missing` 不能忽略 |
| 3 | 剑21 | 160阅读/147听力/16音频/738原文 | 历史独立Python/JS解析保存相应数字；本轮网关T1读取3篇/40题/40答案 | 通过历史快照；当前全套未重扫 | `cam21/py_count_result.json`、`vm_parse_result.json`、`continuation_cam21.json` |
| 4 | PDF下载 | 20/20整本，642MB，SHA与oid相同 | 本轮离线20/20重新SHA匹配，673,642,702B=642.4MiB，全部%PDF-；剑20文件仅Test1分册34页 | 哈希通过，“20整本”不通过 | `continuation_pdf_hashes.out`、`continuation_pdf_evidence.json`（逐文件hash/页数/历史下载记录）、`lfs_pointers.json`、`downloads/book_*.pdf` |
| 5 | 下载速度/耗时 | 完整重新下载 | 下载为历史行为；本轮0.7s是本地哈希计算，不能写为网络下载耗时。每本当前Content-Length、网络速度未重新验证 | 本轮无法验证 | `verify_all_pdfs.py`、`dl_list.tsv`；历史下载脚本/输出保留 |
| 6 | 原文 | 308 Part/20册完整 | 历史解析319 Part，剑20缺1段，源侧还存在省略号截尾 | 原308过时；“完整”不通过 | 原文sweep及`ito_sweep.json`；文档已改为有可用原文并注明缺口 |
| 7 | 音频 | PTE338MB、每个70k–157k帧 | 历史HEAD扫81独立URL，80成功1失败，合计1308.1MiB；两个实下载样本8,927/11,152帧，64kbps，466.39/267.65秒 | 原总量/统一帧数口径不通过 | `pte_audio_scan.json/.out`、`audio/parse_result_v2.json`；HEAD非完整下载 |
| 8 | ITO | 48/48、posts非pages | 历史48/48；原始WP响应及页面存档。部分原文截尾不等于完整转录 | 来源覆盖通过；全部边界本轮未逐项复验 | `ito_sweep.json`、`ito_10_1_raw.json`、`ito_analyze.out.txt` |
| 9 | 答案独立比对 | 至少5套 | 历史PDF抽取195条；2026-10-02 v3解析器扩展到剑3–8/12/17共8册（每册146–160条），逐册比对：剑3 40/40×4（T2–T4用iprog）、剑8全匹配、剑4 T1 34/40（6处为字母vs选项文本，已人工核对选项表）、剑17 T4 35/36等，详见文末补充 | 有限通过；非官方全题验收；剑9/16/18/19纯图像、剑10/14/15未适配 | `official_v3_extracted.json`、`official_v3_diffs.json`、`_v3_full_run2.txt`；剑21交叉`cmp_pte21_v2.out`、`cmp_pte21_listening2.out` |
| 10 | 路由/示例 | 原27路由 | 本轮静态CLI=HTTP=文档各35，无集合差异；历史HTTP sweep文件实际29条，不足以证明当前35条全部动态成功 | 静态35/35通过；全示例执行未完成 | `ielts-cli.mjs`、`API.md`、`route_sweep_results.json` |
| 11 | 三源集成 | 同服务调用 | 本轮CIE已有索引32节点200；Edexcel QP/MS两个直链200；IELTS19T1单篇13题200；剑21T1整套40题200 | 本轮通过明确端点 | `continuation_smoke.json`及各`continuation_*.json`；不据此认定CIE全科解析完成 |

本轮验证命令（PowerShell，在API工作区运行）：

```powershell
node --test .\ielts-api\tests\contract.test.mjs
& .\examdata\.venv\Scripts\python.exe .\tmp_audit_ielts\verify_all_pdfs.py
# Live测试只在新的上游停止发生前执行，本轮4项通过：
$env:EXAMDATA_TEST_LIVE='1'
$env:EXAMDATA_DATABASE_URL='sqlite:///:memory:'
$env:EXAMDATA_DATA_DIR='C:/Users/weo/Desktop/api/examdata/.pytest_cache/continuation-ielts'
$env:EXAMDATA_IELTS_DIR='C:/Users/weo/Desktop/api/ielts-api'
& .\examdata\.venv\Scripts\python.exe -m pytest .\examdata\tests\test_api_ielts.py -q
```

## 严重问题（会导致错误结果或崩溃）

### [S1] HTTP200 HTML错误页被当成成功听力原文（已修）

- **位置**：`ielts-api.mjs`，`maslowScript()` 未分节时的raw回退。
- **问题**：无章节时直接返回raw文本成功，HTML报错页可进入有效槽位。
- **最小复现**：`node --test ./ielts-api/tests/contract.test.mjs` 第二项，将fetch替换成HTTP200 `<html><body>upstream error</body></html>`，完全离线。
- **实际输出**：`✔ bad JSON and HTML error pages do not become successful transcripts`，2 tests / 2 pass / 0 fail（本轮）。旧版没有HTML/长度检查会返回成功。
- **影响**：错误内容被计入原文与聚合评分；HTTP200/ok:true不足以验收有效内容。
- **修复**：raw回退拒绝HTML文档及不足200字符内容，非法book在请求前拒绝。测试同时检查坏JSON优雅降级与请求次数小于20。明确：仍不能由长度阈值证明所有正文都是真实/完整原文。

历史Kimi已修复的bad-JSON抛异常、LFS探测、cam21引号解析与CLI管道截断等不重复计为本轮新发现；本轮坏JSONmock确认没有异常。

## 中等问题

### [M1] 非法音频身份仍返回ok:true及不存在的URL（已修）

- **位置**：`ielts-api.mjs:listeningAudio()`、`cam21.mjs:audio()`。
- **最小复现**：`node --input-type=module -e "import('./ielts-api/ielts-api.mjs').then(async a=>console.log(await a.cam21Audio(1,999),a.listeningAudio(999,1,1)))"`，离线。
- **实际输出**：修前历史fuzz `PASS cam21Audio(1,999) -> {ok:true, error:-}`；本轮两者返回 `ok:false`，错误为范围约束。
- **影响/修复**：拒绝非整数、超范围、null、NaN、对象、Symbol；合法边界和省略section默认1仍正常。生成URL接口的ok:true只证明合法身份及链接构造，不代表MP3已下载验证。

### [M2] “20/20整本PDF”“全网唯一”超过证据（已修文档）

- **位置**：`API.md` PDF介绍/覆盖矩阵、`DEVELOPMENT.md` S3/源比较、`examdata/docs/IELTS_API.md`。
- **最小复现**：本地用PyMuPDF读取 `tmp_audit_ielts/downloads/book_20.pdf`，显示34页/Test1；`pdfLfs(20)`只返回该分册。查看LFS指针与同哈希文件不会补出Test2–4。
- **影响/修复**：全体文件哈希相同不能证明20本整书；改为剑1–19整本加剑20 Test1，其他分册由 `book20Set()` 提供。删去源唯一性断言，保留具体来源和时间。

### [M3] IELTS请求无限创建子进程，取消请求未回收子进程（已修）

- **位置**：`ielts-cli.mjs` HTTP handler、`examdata/src/examdata/api/ielts.py` 每次请求独立Node子进程。
- **最小复现**：`python -m pytest tests/test_ielts_concurrency.py -q`。离线占满2槽位，第三个等待超时返回503，取消排队请求不泄漏槽位；取消已运行请求需kill并wait子进程。
- **实际证据**：本轮IELTS单篇13.10s、剑21整套5.18s；历史aggregate20T1 15.39s。不存在负载压测或内存测量证据，不能声称高并发安全。
- **修复/验证**：仅IELTS网关增加每个服务进程/事件循环默认4槽位和5s排队超时；满额503，运行超时504，取消请求回收子进程后释放槽位。新增2项离线并发/取消回归通过，合并原网关测试为5 passed、1 live skipped。尚无跨进程全局速率限制、缓存或真实负载压测；不将此声称为生产性能验收。独立IELTS重试与CIE批次“首错误停止”规则不可混用。

## 轻微问题

### [L1] 声称和复测时间、计数单位混淆（已修）

- **位置**：三份使用/架构文档覆盖矩阵。
- **检查/证据**：673,642,702字节应为642.4MiB；0.7s是本地哈希时间。35条路由静态匹配与历史29条实际请求是不同覆盖。
- **修复**：文档补日期、来源快照、套数/题干/分册及缺Part边界；本报告保留未完成项，不把原始宣称或历史todo“done”作为证明。

## 负向宣称的复核结果

三项均已有历史反例，**找到**，所以无需再扩大搜索来证明“全网无源”。本轮未重发这些下载请求，不能将历史可访问性说成当前保证。

| 缺口 | 反例 | 可复核证据/调用 |
|---|---|---|
| 剑21 PDF | `aqinaq/agylshyn` 社区镜像146页，44,148,624字节 | `cov_pdf21.json`，`node ielts-cli.mjs pdf21` 返回直链 `https://raw.githubusercontent.com/aqinaq/agylshyn/main/site/pdf/ielts-21.pdf` |
| 剑3 T2–T4答案 | `ieltsprogress.com` | `iprog3_t2.html`/t3/t4、`cov_iprog.json`，`node ielts-cli.mjs iprog-listening 3 2` |
| 剑20/21中英精读 | `top.zhan.com` 24篇 | `cov_zhan.json`，`node ielts-cli.mjs zhan-reading 20 1 1` |

历史实际探查过GitHub/站点/WP接口/镜像等具体渠道以保留脚本及响应为准；未见完整证据证明用户列出的HuggingFace、archive.org、Telegram、所有语言渠道都执行过，不补造渠道清单。jsDelivr链路已于2026-10-02直连复验：4条/gh/ URL全部HTTP 200无301，模拟raw故障后回落成功（详见文末补充）。

## 代码质量评分

评分为本地工程审查判断，不是自动测试结论。

| 维度 | 评分(1–10) | 理由 |
|---|---|---|
| 正确性 | 7 | 主要来源与真实网关可用，仍有源侧缺题/原文截尾及组合题口径 |
| 健壮性 | 7 | 本轮坏JSON/HTML/非法输入通过；“永不抛异常”不能覆盖所有导出及环境 |
| 性能 | 5 | 单篇秒级至十余秒，每请求起Node；无当前并发/内存压测 |
| 可维护性 | 7 | 来源分模块、无第三方npm运行依赖；两目录副本仍需同步 |
| 文档准确性 | 7 | 已纠正分册与唯一性；当前全示例动态验证仍有缺口 |
| 合规性 | 5 | 使用公开第三方内容不能推导具有再分发授权；未作法律结论或全面robots复查 |

合规事实边界：没有本轮登录/付费抓取或访问控制绕过；历史robots探查不代表所有源均允许全部路径。并发槽位已限制子进程数，但尚未实现跨进程全局速率限制。教材版权/镜像授权及对外再分发需要另行核实，本地技术可访问性不作为授权证据。

## 文档缺陷清单

| 文档 | 位置 | 问题 | 严重度/状态 |
|---|---|---|---|
| API.md | PDF介绍及覆盖矩阵 | 剑20 Test1被称整本 | 中等，已修 |
| DEVELOPMENT.md | S3、覆盖、源比较 | 整本及唯一性泛化 | 中等，已修 |
| 三份文档 | 覆盖矩阵 | 套数不等于所有题干完整；319 Part仍缺1段 | 轻微，已补边界 |
| 原审查要求 | 全部CLI/curl示例 | 历史29实际路由不足以证明当前35及所有示例执行 | 待完成验证，明确保留 |

## 亮点

- PDF原文件与LFS oid可重新字节验证，本轮20/20确实相同。
- 结构化剑21数据有另一语言解析存档，降低与被测解析器同源偏差。
- 三项“无源”通过具体反例修正并接入独立槽位。
- IELTS以独立路由增量接入，本轮未改CIE/Edexcel业务逻辑；业务失败与基础设施错误状态码区分。

## 给下一步的具体建议

1. 当前不发新上游请求；保持CIE `needs_user_resume=true`。先完成可离线部分。
2. 并发上限与进程回收已通过离线回归；进一步对实际Node慢进程/多worker负载做验证，再决定跨进程限流与缓存。
3. 有新联网授权后，对当前35条路由及全部文档CLI/curl逐项执行，保留原始响应；补所有答案非空/占位检查，区别整套和单篇。
4. 对用户指定的解析器边界（正则字面量、Unicode、模板、注释、__proto__）、实际aggregate请求总数、选源反例及内存压测逐项建立可重复离线测试；现有零散历史检查不冒充全覆盖。
5. 需要对外服务/再分发时逐源核实许可、路径访问政策与数据完整性，保持个人学习范围标记。

没有删除API工作区内容、没有安装依赖、没有写开发数据库、没有修改 `examples/browser.html`、没有提交推送。被测代码在原独立审查之后按用户继续修复的授权改动，本轮修改列在S1/M1/M3；两份聚合器已同步。

---

## 2026-10-02 补充复验（用户 6 条清单逐条落实）

原审查之后，用户给出 6 条治理清单（2 高 / 2 中 / 2 低）；以下为逐条落实与复验记录，全部为 2026-10-02 本轮实际执行，证据文件均在 `tmp_audit_ielts/`。

### ① jsDelivr `/gh/` 301 回落——复验完成，保留备用路径（清单第 1 条，高）

- 直连复验（`fallback_cdn_curl_20261002.txt`）：4 条 `/gh/` URL 全部 **HTTP 200、redirects=0、无 301**——cam21 `t1-reading.html` 87,412 B；ielts-reader `data/passages/c1-test1-p1.json` 40,458 B；maslow `ielts_index/listening_index.json` 505,035 B；LFS 指针 133 B（oid `93ba03c1…`、size 28,252,883）。
- 故障回落端到端（`fallback_e2e.mjs` → `fallback_e2e_20261002.txt`）：模拟 raw 全故障后 `cam21.reading(1)` 经 cdn 返回 `{"ok":true,"via":"cdn","answers":40}`（raw 1 次 / cdn 1 次）；`ielts.reading(1,1,1)` 返回 `{"ok":true,"questions":15}`（raw 3 / cdn 1）。
- 结论：「jsDelivr 301 指回 raw」在本次复验中**不可再现**；`via:"cdn"` 作为 raw 的备用通道保留并已写入 `DEVELOPMENT.md` §6.1。

### ② verify-pdfs 固化为项目回归脚本（清单第 2 条，高）

- `verify-pdfs.mjs`（188 行，零依赖）已是独立入口：`node verify-pdfs.mjs [册号…] [--jobs N] [--json]`；`ielts-cli.mjs` 提供 `verify-pdfs` 子命令；退出码 0/1/2。
- 修复一个真 bug：CLI 曾把 `--jobs N` 的值当作册号过滤。修复后行为（`parseargs_fix_20261002.txt`）：`['--jobs','13']` → jobs=13、books=[]；`['1','20']` → books=[1,20]；`['--jobs','2','5']` → jobs=2、books=[5]；`['abc']` → bad=["abc"]。
- 契约回归 `node --test tests/contract.test.mjs` → **3/3 pass**（含 parseArgs 断言）。
- 另修复根目录遗留副本 `contract.test.mjs` 的导入路径（审查期间产生，此前会使根目录 `node --test` 整体失败）：修复后根目录全量发现 **6/6 pass**（根副本 3 + `tests/` 3）。
- 全量联网复验（`verify_pdfs_live_full_20261002.txt`）：**20/20 PASS**，673,642,702 B（642.4 MiB），用时 3397.7s，EXIT=0；每册实际字节数 = LFS size、SHA256 = oid、首字节 `%PDF-`、均经 `media.githubusercontent.com` 下载（含剑19 105,388,262 B、剑20 5,327,081 B 两个边界）。
- 注：仓库无 CI（无 `.github/workflows`），脚本设计为本地/定时执行；源更新后可直接重跑全量校验。

### ③ 音频统计口径——已改为实测值（清单第 3 条，中）

`DEVELOPMENT.md` §3 新增「统计口径与实测值（2026-10-02 复核）」：pte HEAD 81 条 URL 合计 **1,371,675,709 B（1308.1 MiB）**（80 成功/1 失败）；maslow git tree 346 个 MP3 合计 **2,592,743,250 B（2472.6 MiB）**（tree sha `2064b88b…`、truncated=false）；帧数样本 8,927 / 11,152 / 17,890 帧。原「338MB / 50.6MB / 70k–157k 帧」声明废弃（口径与时间点不可考）。

### ④ 剑4 PDF 答案提取器适配——完成（清单第 4 条，中）

v3 提取器适配 **剑3–8/12/17 共 8 册**（`_v3_full_run2.txt`、`official_v3_extracted.json`、`official_v3_diffs.json`），与 PDF 官方答案逐题比对：

| 册 | T1 | T2 | T3 | T4 |
|---|---|---|---|---|
| 剑3 | 40/40（pte+iprog 双源一致） | 40/40（iprog） | 40/40（iprog） | 40/40（iprog） |
| 剑4 | 34/40 | 40/40 | 39/40 | 40/40 |
| 剑5 | 39/40 | 36/40 | 38/40 | 35/40 |
| 剑6 | 33/38 | 37/40 | 38/40 | 33/40 |
| 剑7 | 40/40 | 35/38 | 39/40 | 37/38 |
| 剑8 | 38/38 | 40/40 | 38/38 | 36/36 |
| 剑12 | 37/38 | 40/40 | 36/36 | 40/40 |
| 剑17 | 34/34 | 38/38 | 38/38 | 35/36 |

差异已逐条人工核对，集中在三类：PDF 文本层 OCR 噪声（`lOO`/`100`、`I year`/`1 year`、`pnmary`/`primary`、`JO6337`/`106337`）、`IN ANY ORDER`/`IN EITHER ORDER` 多答案语义（pte 返回候选数组、PDF 单字母）、剑4 T1 6 处字母 vs 选项文本（Q24–30，已核对 PDF 选项表）。**未适配**：剑9/16/18/19（纯图像扫描，无文本层）、剑10/14/15（版式不同）、剑1/2（老版式）、剑20（源仅 34 页 Test1）。

### ⑤ book20 听力 15 段——已标注（清单第 5 条，低）

实测（`book20_script_parts_20261002.txt`）：`listeningScript(20)` → test1:4 / test2:**3**（缺 part4）/ test3:4 / test4:4 = **15 段**，source maslow/EnglishLearning。已在 `API.md` §4.4 + 覆盖矩阵行、`examdata/docs/IELTS_API.md` 注明「剑20 源侧仅 15 段，test2 缺 part4」（全库 319 Part = 剑1–19 各 16 段 + 剑20 15 段）。

### ⑥ ielts-api.mjs 拆分——决策：不拆分（清单第 6 条，低）

理由：① 保持单文件零依赖、可整体复制部署；② 五个源适配器（pte/cam21/lfs/ito/zhan）已按源分模块，`ielts-api.mjs` 主体是包装与聚合层，760 行尚在可控范围；③ 拆分需重跑全部回归（PDF/契约/网关），收益不抵风险；④ 超过 1000 行或包装逻辑再增长时重新评估。

### 三局同服务复验（本轮）

- curl（`three_boards_curl_20261002.txt`，同一 8000 端口服务）：CIE `/api/v1/search` total=751（0580 题干）；Edexcel `/api/v1/paper` 返回 2 个文档直链（que+rms）；IELTS `/api/v1/ielts/info`、`/reading/19/1`（13 题，3.2s）、`/aggregate/21/1`（score 5/5，5 源，4.1s）。
- pytest 网关：离线 **5 passed, 1 skipped**（`gateway_tests_offline_20261002.txt`，EXIT=0）；live（`EXAMDATA_TEST_LIVE=1`）**6 passed**（`gateway_tests_live_20261002.txt`，EXIT=0，5.23s）。
- 本轮新增 2 项 IELTS 并发/取消离线回归（`test_ielts_concurrency.py`）均通过；未做跨进程全局限流与真实负载压测，不声称生产级性能。
