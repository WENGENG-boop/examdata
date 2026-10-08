# 托福 API 修复报告（repair-20261005）

修复执行日期：2026-10-05（北京时间）。工作区：`C:\Users\weo\Desktop\api`。
任务依据：`toefl-api/AGENT_FIX_PROMPT_20261005.md`（与对话提示词一致）；问题清单依据独立审查报告 `toefl-api/AUDIT_REPORT_20261005.md` 及其统计证据 `toefl-api/audit-20261005/`。旧 `REPORT.md` 的 done 标记不作为验收证据。

修复边界（遵守）：只改 `toefl-api/lib/*.mjs`、`toefl-api/toefl-cli.mjs`、`examdata/src/examdata/api/toefl.py`、`examdata/docs/TOEFL_API.md`、`toefl-api/REPORT.md`；未改 CIE/Edexcel/IELTS 实现，未操作既有服务/数据库/密钥；未 commit/push、未安装依赖、未抓登录或付费内容。联网调用串行且起始间隔 ≥1.1 秒（实测 min_gap_ms=1150）。

## 1. 实际改动文件（7 个，SHA256 前→后）

修前哈希记录 `hashes-before.json`（34 文件含 15 个控制文件），修前文件备份于 `backup/`。

| 文件 | 改动内容 |
|---|---|
| `toefl-api/lib/util.mjs` | `httpGet` 增加手动重定向跟随：每跳先经 `validateRedirect` 校验，`maxRedirects=5`，相对 `Location` 先解析再校验，缺 `Location` 报错；不校验时保持原 `redirect:'follow'` 行为 |
| `toefl-api/lib/kmf.mjs` | 新增 `parseKmfDetailUrl`/`isKmfDetailUrl`/`resolveKmfHref`/`kmfRedirectValidator`/`validateKmfContent`；`fetchPage` 改为"先校验 URL → 缓存命中也要验内容 → 联网响应验内容后才写缓存"；听力表格题解析（`parseListenTable`）、阅读多选（`isMultiSelectForm`）、完整性字段（`content_complete`/`content_gaps`）；单进程节流 `THROTTLE_MS=1100` |
| `toefl-api/lib/jj.mjs` | `jjHashOf`/`fetchJjDetail` 改用严格解析器，非法 URL 在读取缓存与联网前拒绝 |
| `toefl-api/toefl-cli.mjs` | detail/jj/questions 命令入口 URL 严格校验；`info` 的 eras 仅六个数编号分区 + `format_revision_reference`；`normSet`/`normTpo`/`normTpoRange` 整串严格解析 |
| `examdata/src/examdata/api/toefl.py` | HTTP `/info` 同步六分区 + 改版参考说明；`/sets` 未知 era 返回 HTTP 200 + `ok:false`；set/tpo 参数整串严格解析；`exam_date` 保持 null |
| `examdata/docs/TOEFL_API.md` | 新增字段文档、era 说明、URL 校验与合规限制、证据口径限定（§4/§5/§9 等） |
| `toefl-api/REPORT.md` | 修复轮修订说明 + 第十二节（本轮修复与验证记录） |

未改动（哈希复核一致）：`lib/catalog.mjs`、`lib/detail.mjs`、`lib/search.mjs`、`lib/sources.mjs`、`tools/*`。`detail.mjs` 的 URL 校验经由 `jj.mjs`（`jjHashOf`/`fetchJjDetail`）与 `kmf.mjs`（`fetchPage`）的共用解析器生效，无需单独修改。

## 2. P1-01 详情 URL 未限制主机 → 任意地址访问与缓存污染

**根因**：`jjHashOf` 只用非锚定正则提取 `/detail/{section}/{hash}.html`，不解析 origin；`fetchPage` 按 section/hash 取缓存键；`questions --url` 不要求 kmf 主机；`httpGet` 自动跟随重定向。非法主机与合法主机同路径共用同一缓存键。

**修前反例**（审查报告原文）：`http://127.0.0.1:<port>/detail/speak/auditprobe20261005.html` 被 CLI detail 接受，本地服务收到 1 次请求，响应被写入 kmf 缓存。

**修复实现**：
- 共用严格解析器 `parseKmfDetailUrl`：仅接受 `https://toefl.kmf.com`；拒绝 userinfo、非默认端口、其它协议/域名/IP；路径完整匹配 `/detail/(read|listen|speak|write)/[a-z0-9]+.html`，兼容实测存在的单个数字后缀 `/1`（后缀统计：jj 索引 32 条带 `/1`，kmf 索引 758 条无后缀，全量缓存 4417 文件无其它后缀形态）；拒绝 query/fragment/多余路径段。不使用 substring/includes 判断。
- 调用点：detail、jj、questions 三个 CLI 入口 + HTTP 对应路由 + 低层 `fetchPage`（在读缓存与联网之前）；内部 tab 相对路径用 `resolveKmfHref` 以可信 origin 解析后再校验。
- 重定向：`httpGet` 每跳校验目标 origin/path，上限 5 跳，非法即 `ok:false`；GitHub 原文 fetch 不经过 kmf 校验器（合法用途分离）。

**修后验证**（全部通过，0 失败）：

| 验证 | 数量 | 结果 | 证据 |
|---|---|---|---|
| CLI 矩阵（含 10 类非法 URL × detail/jj/questions） | 59 用例 | 59 pass / 0 fail | `evidence/cli-matrix-after.txt` |
| 受控 localhost HTTP 服务：非法 URL 请求数=0；恶意主机+真实缓存 hash 不读缓存；合法 cache-hit 正常 | 24 断言 | 24 pass / 0 fail，localhost hits=0 | `evidence/zero-request.json` |
| 重定向逐跳校验（5 跳成功、6 跳拒绝、跨主机拒绝且恶意主机未被 fetch、http 降级拒绝、相对路径接受、缺 Location、非详情路径、userinfo、query 注入、fetchPage 不写缓存） | 10 用例 | 10 pass / 0 fail | `evidence/redirect-validation.json` |
| 全量索引 URL 严格解析（kmf 758 + jj 213 非锁定） | 971 | 0 失败 | `evidence/validate-scan.json` |

**未验证/限制**：未做真实源站恶意重定向演练（源站未返回跨主机重定向；用 monkey-patch fetch 模拟验证）；节流为单进程内 `THROTTLE_MS=1100`，不提供跨进程全局 1 req/s 保证。

## 3. P1-02 口写错误页被当作成功内容并写缓存

**根因**：`fetchJjDetail` 的 speak/write 分支以"整页 text 非空"判成功；`fetchPage` 先写缓存后验内容；HTTP 200 维护页因此 `ok:true` 并污染缓存。

**修前反例**（审查报告原文）：受控复现返回 HTTP 200 HTML，正文仅 `upstream maintenance`；detail 返回 `ok:true`、`question:null`、`text:"upstream maintenance"`，并写入缓存。

**修复实现**：
- `validateKmfContent(section, html)` 按科目验证必要 DOM：read 需 `#js-stem-cont` + `inner js-translate-new` 题目容器 + `g-hl-2` 答案标记；listen 需 `question-cont js-translate-new` + `data-href="/detail/listen/"` + `true-answer`；speak 需 `item-desc` 题干 ≥10 字；write 需 `content-subject` 材料/题干 ≥10 字。维护页/登录页/无题干页均不满足。
- `fetchPage` 顺序改为：URL 校验 → 缓存命中读取后也要验内容（坏缓存拒绝返回 `ok:false`）→ 联网响应验内容通过后才写缓存。
- 写作 `essay` 可空、独立写作 `audio` 可空——空值不算失败；合法页面结构不可识别时明确失败并保留统计，不编造题干。
- speak 新增结构化字段：题干（`question` 保留原字段兼容）、`audio_url`、`text`；write 新增 `materials`（阅读/听力材料字符数）、`prompt`、`essay`。

**修后验证**：
- 全量缓存复检：4417 页（listen 2133 / read 1880 / speak 271 / write 133）逐页 `validateKmfContent`，失败 0；`evidence/validate-scan.json`。
- 缓存命中路径同样经过内容校验（`fetchPage` 代码路径 + zero-request 测试的合法 cache-hit 断言）。
- 联网四科 refresh 样本全部通过且写入的均为合法内容（§7）。
- 既有缓存中未发现已证实的错误页（4417 页全过）；未全删任何业务缓存。

**未验证/限制**：维护页/登录页的拒绝逻辑用单元级与缓存级验证（本地构造 + 全量复检）；未等源站真实返回维护页再演练（不可控）。缓存里不存在真实错误页样本可清，故本轮无缓存清除项。

## 4. P1-03 听力表格题丢失选项与答案，却报告完整

**根因**：听力选项/答案/题型解析只支持普通单选（`data-option`/`true-answer` 单值），不支持 `table.content-logic` 表格结构与多值答案；`fetchKmfSet.complete` 只看抓取题数，不看内容可作答性。

**修前反例**（审查报告原文）：14 道全部返回 `type:"multiple_choice"`、`options:[]`、`answer:[]`，所在套题仍 `complete=true`。最小代表 Official 04 Set 2 `listen/11dwej.html` qid=64670：源表格为 Yes/No 判断，源答案 B A A B。

**修复实现**：
- 新增表格题表示 `type:"table_choice"`，字段 `table:{columns:[...], rows:[{label, answer}], answer_letters:[...]}`；列/行顺序以 DOM 为准，不猜 A/B 对应顺序；保留 `options`/`answer` 契约兼容（表格题 `options:[]` 合法、`answer` 为按行字母数组）。
- 题型判断：识别 `table.content-logic` 即 `table_choice`，不再误标 `multiple_choice`；多值答案不截取首字母。
- 完整性：`content_complete` 与抓取完整性分开表达；必要选项/表格/答案缺失产生 `content_gaps`，`fetchKmfSet` 不再无条件 `complete=true`；原本无选项的合法题型按题型判断，不一刀切要求 options 非空。
- 阅读多选（`isMultiSelectForm`）同样修复：选项数完整保留，`n_options` 从 0/残缺恢复为全量（20 道）。

**修后逐项结果**（14/14 通过；答案数量=行数、字母落在列范围内、与源 `true-answer` 一致；`evidence/reparse-diff-summary.txt` 与 `evidence/reparse-diff.json`）：

| 套次 | qid | 行×列 | 答案 |
|---|---|---|---|
| Official 53 Set 2 | 75647 | 5×2 | B A A A B |
| Official 45 Set 5 | 67531 | 4×2 | B A B B |
| Official 33 Set 2 | 66386 | 4×3 | B A C B |
| Official 24 Set 4 | 68017 | 5×2 | A B B A A |
| Official 20 Set 2 | 67977 | 5×2 | B A A B A |
| Official 18 Set 5 | 67831 | 5×2 | A A B A B |
| Official 16 Set 2 | 67742 | 6×2 | A B A A A B |
| Official 13 Set 5 | 64674 | 4×2 | A B A B |
| Official 10 Set 6 | 64673 | 5×2 | A B A A B |
| Official 08 Set 4 | 64672 | 5×2 | B A A A B |
| Official 05 Set 6 | 64671 | 6×2 | B A A B B B |
| Official 04 Set 2 | 64670 | 4×2 | B A A B |
| Official 02 Set 1 | 64680 | 4×2 | A B A A |
| Official 02 Set 5 | 64669 | 4×3 | B A C B |

代表页 `listen/11dwej.html`：索引条目（914lxj）与审计 URL（11dwej）双查均为 4 行、答案 B A A B，`problems:[]`。

**全量离线重解析**（禁网，全部 TPO 758 + 免费机经 213，共 971 入口）：971/971 可解析，**新增失败 0**；变化 34 条目 / 48 字段变化（14 表格题 × type+answer + 20 阅读多选 n_options），全部为预期修复，`unexpected=0`；essay 字符差异 0。未编造任何源站没有的解析/答案。

## 5. P2-01/P2-02 era 筛选与套次身份

**根因**：`info.eras` 列出 pre/post-2023-07 两个改版分区，但 `catalog.eraOf` 只实现六个数编号分区，`/sets?era=pre-2023-07` 返回 HTTP 200 + `ok:true` + 空列表（假成功）；`normTpo` 从任意字符串提取数字，`set=garbage54` 静默成功返回 tpo-54。

**修前反例**（审查报告原文）：`/sets?era=pre-2023-07` 与 `/sets?era=post-2023-07` 均 HTTP 200、ok=true、total=0；`/get?set=garbage54` 实际成功返回 tpo-54。

**修复实现**：
- `info`（CLI + HTTP 同步）eras 仅保留 catalog 真正实现的六个编号分区；pre/post-2023-07 移入 `format_revision_reference` 参考说明并明确"不支持按它们映射套次"；`exam_date` 保持 null；未建立无真实来源的改版套次映射。
- `/sets` 未知 era → HTTP 200 + `ok:false`（业务失败），不再返回成功的空列表。
- set 参数只接受整串 `tpo-N`（N 正整数）；tpo/tpo-min/tpo-max 只接受完整十进制整数，随后按收录范围处理；明确拒绝 `garbage54`、`tpo-540`（业务失败）、`tpo-54junk`、`54.5`、负值、混杂文本。

**修后验证**（CLI 59/59 中含 18 个 era/身份用例；HTTP 流程含 6 个负例）：非法 era/set 全部 `ok:false`；`tpo-30`/`tpo-54` 合法调用不变；HTTP 与 CLI 结果一致。证据：`evidence/cli-matrix-after.txt`、`evidence/http-flow-after.json`。

## 6. P2-03 文档口径

`examdata/docs/TOEFL_API.md` 与 `toefl-api/REPORT.md` 已按实际证据限定所有"完整/零差异/1 req/s/全量在线"类宣称：缓存全量复算（4417 页/971 入口）与联网四科样本分别表述；源站上限（Official ≤54、部分页 404、无年份/考试季节、无范文/转写字段）写明；单进程节流非全局保证；未宣称支持 2026 新版全题库；未做跨进程并发压测。详见两文档本轮修订段落。

## 7. 联网四科样本与音频 Range（第 5 节）

串行执行、起始间隔 ≥1.1s（实测 min_gap_ms=1150），一次通过，`failure=null`，`stopped_network_early=false`；证据 `evidence/live-samples.json`。

| 科目 | URL | refresh=1（真正联网） | 结果 |
|---|---|---|---|
| read | `read/11m4mj.html` | 10.5s | ok，10/10 题，content_complete=true，set_id=tpo-54 |
| listen | `listen/11mc6j.html` | 4.9s | ok，5/5 题，content_complete=true |
| speak | `speak/f1m9gj.html` | 522ms | ok，题干 125 字，audio_url 非空 |
| write | `write/c1m97j.html` | 564ms | ok，prompt 142 字，materials 阅读 1729 字/听力 3660 字，essay 空（正常） |

- 无 refresh 复跑（纯缓存）：四科全 ok，88–110ms——记录真正联网与缓存调用的区别。
- 缓存 diff：refresh 流程 17 pages changed / 0 added；cachehit 流程 0 changed / 0 added。
- 音频 Range（`bytes=0-1023`，不落正式目录）：listen 206 `audio/mpeg` 1024B `bytes 0-1023/47646`；speak 206 1024B `/183065`；write 206 1024B `/4611734`；均无重定向，sha256 见 `live-samples.json`。**是 1KB 样本验证，不是完整下载/试听**。
- 未触发 403/404/409/502/超时/解析失败，未重试、未换镜像、未加 force、未访问锁定条目。

## 8. 全量回归与 pytest

离线/HTTP/CLI 汇总：

| 套件 | 结果 | 证据 |
|---|---|---|
| 全量离线重解析（禁网 971 入口） | 971 ok / 0 新增失败 | `evidence/reparse-diff-summary.txt` |
| HTTP 流程（独立端口 8125、私有临时 DB） | 30 cases：28 真实用例全 PASS / 0 FAIL（2 项为元数据记录）；cache-mtime-diff changed=0 added=0；服务已终止 | `evidence/http-flow-after.json` |
| CLI 八命令矩阵 | 59/59 pass | `evidence/cli-matrix-after.txt` |
| zero-request / redirect 专项 | 24/24、10/10 | `evidence/zero-request.json`、`evidence/redirect-validation.json` |
| 联网四科样本 + 音频 | 4/4 ok、3×206 | `evidence/live-samples.json` |

**examdata 全量 pytest**（命令：`examdata` 下 `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`，`PYTHONDONTWRITEBYTECODE=1`、`EXAMDATA_TEST_LIVE=0`）：

- **退出码：1**；套件执行到 100%（1185 例），约 20 分钟（任务墙钟 1218s）。
- **计数：1178 通过 + 6 跳过 + 1 失败**（由进度标记重建）。注：命令行 `-q` 与 pyproject `addopts="-q"` 叠加为 `-qq`，pytest 9.1.1 在该级别不打印最终计数行（已用同参数 2 例小样验证），故以进度标记重建；日志 `evidence/pytest-full.log` 保留完整进度与失败详情。
- **唯一失败**：`tests/test_api.py::test_provenance_coverage_is_complete`（第 220 行）——`/provenance/coverage` HTTP 200 但 `body.complete=false`，断言 `complete is True` 失败。
- **关联性判定：既有 / 不相关候选，未修**。依据：(1) 审计轮在完全未改业务代码时以 `-x` 复现的首个失败即此项（见 `AUDIT_REPORT_20261005.md`「整体回归终态」）；(2) 该端点为 examdata 通用溯源覆盖接口（`governance/provenance.py:coverage`，统计 Question/MarkSchemeEntry/Asset/OfficialAnswer/Paper 五类主体的来源覆盖比例），不经过本轮改动的 TOEFL 路由；(3) 本轮 examdata 侧仅改 `toefl.py`，除该失败外无其他失败。
- 按任务边界未修其他模块；该失败留作既有/不相关候选。

## 9. 失败 / 跳过 / 未验证项

- **pytest 唯一失败**：`tests/test_api.py::test_provenance_coverage_is_complete`——既有/不相关候选（审计轮未改业务代码时同一失败；通用溯源覆盖接口，不经 TOEFL 路由），按边界未修；除此之外无其他失败，6 例跳过。
- 未做跨进程并发/生产负载压测；节流为单进程内实现。
- 未完整下载、解码或人工试听任何音频；仅 1KB Range 样本。
- 源站边界：Official 收录上限为 54；部分页面 404；无年份/考试季节字段；无范文/转写字段（essay 可空属正常，非缺陷）。
- 联网验证为四科各一项 Official 54 样本，非全量在线逐条对照。
- 未声称支持 2026 新版全题库；未重新爬取全部在线列表。

## 10. 清理与最终复核

清理执行与完整清单见 `cleanup-manifest.json`；摘要：

- **runtime 删除**：`toefl-api/repair-20261005/runtime`（48 文件 / 3.1M：临时脚本、私有测试 DB、server 日志与中间产物）——删除前以 PowerShell `Resolve-Path` 核对绝对路径为 `C:\Users\weo\Desktop\api\toefl-api\repair-20261005\runtime`，以 `Remove-Item -LiteralPath ... -Recurse -Force` 删除并复核不存在；需保留的证据在此之前已复制到 `evidence/`。
- **终态冒烟临时目录删除**：`toefl-api/repair-20261005/.terminal-smoke`（5 文件 / 520K）——同法核对路径并删除、复核不存在；冒烟结果保留于 `evidence/final-smoke-post-cleanup.json`。
- **orphan pyc 删除**：`examdata/src/examdata/api/__pycache__/toefl.cpython-314.pyc` 两次删除（13:31:00 实例；14:39:36 再现实例与终态冒烟服务器及并发会话 examdata pytest 时间重叠、无法唯一归因，属可再生的编译缓存）。
- **`examdata/.pytest_cache/` 未删任何文件**：内含并发其他会话产物（Cambridge 历史 fixtures、edexcel 探测、`examdata-tests-*` 临时目录、`v/cache` 于 14:39 被其更新）；本修复 pytest 以 `-p no:cacheprovider` 运行且 conftest 对自身临时目录 atexit 自动清理，未写入任何文件。
- **未动**：其他模块既有测试/pyc、正式工具、原始第三方源、data 索引、`.data` 业务缓存（4417 页全量保留）、`audit-20261005/` 审计证据。
- **控制文件哈希复核**：`hash_files.py compare`（`evidence/hashes-compare-final.txt`）——恰好 7 个 `[allowed]` 差异（即本轮修复的 7 个文件），**0 个 `[control]` 差异**（CIE/Edexcel/IELTS 关键模块与修前一致）。
- **端口**：8125 终态无 LISTENING；两轮冒烟服务器均记录 PID 并在 finally 中 SIGTERM 终止后复核。
- **终态冒烟**（清理与哈希复核完成后执行；独立端口 8125、私有临时 DB、全走缓存无新下载）：info / get tpo-54 / detail speak f1m9gj / search punctuated / questions tpo-30 read——**5/5 PASS，EXIT=0**（server pid=66336 已终止），见 `evidence/final-smoke-post-cleanup.json`；14:24 首轮冒烟同结果见 `evidence/final-smoke.json`。本节为结果记录。

## 11. 证据文件清单

- `evidence/url-stats.json`、`suffix-scan.txt`：URL/后缀形态统计
- `evidence/validate-scan.json`：4417 缓存页 + 971 索引 URL 严格校验
- `evidence/reparse-diff-summary.txt`、`evidence/reparse-diff.json`：971 全量重解析 diff 与 14 项表格题逐条结果
- `evidence/cli-matrix-after.txt`、`cli-info-after.json`：CLI 59/59
- `evidence/http-flow-after.json`：HTTP 30 cases（28 真实用例全 PASS / 0 FAIL，2 项元数据记录）
- `evidence/pytest-full.log`：examdata 全量 pytest 完整进度与失败详情（退出码 1）
- `evidence/zero-request.json`、`redirect-validation.json`：安全专项
- `evidence/live-samples.json`：联网四科 + 音频 Range
- `evidence/final-smoke.json`、`evidence/final-smoke-post-cleanup.json`：终态冒烟两轮（均 5/5）
- `evidence/hashes-compare-final.txt`：终态哈希复核（0 control 差异）
- `evidence/probe-*.txt`、`calibration*.json`：修前探针与解析器校准
- `hashes-before.json`、`hash_files.py`、`backup/`：修前基线与备份
- `cleanup-manifest.json`、`evidence-summary.json`：清理清单与证据汇总
