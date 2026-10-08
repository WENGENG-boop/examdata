# TOEFL API 修复实施计划（TOEFL_REPAIR_IMPLEMENTATION_PLAN）

- 制定日期：2026-10-05（北京时间）。工作区：`C:\Users\weo\Desktop\api`。
- 问题依据：独立重复审查报告 `toefl-api/AUDIT_REPORT_20261005.md`（完整副本见本目录 `TOEFL_COMPLETENESS_AUDIT_20261005.md`）及其统计证据 `toefl-api/audit-20261005/{cache-summary,flow-summary,audio-summary,cleanup-manifest}.json`。旧 `toefl-api/REPORT.md` 的 done 标记不作为验收证据。
- 任务规格（唯一执行依据）：`toefl-api/AGENT_FIX_PROMPT_20261005.md`（完整副本见本目录 `TOEFL_EXECUTION_AGENT_PROMPT.md`）。
- 执行状态：**S01–S06 全部 done**（2026-10-05 当日完成）。执行记录见本目录 `EXECUTION_CHECKLIST.md`；结果见本目录 `TOEFL_IMPLEMENTATION_RESULT.md`；剩余缺口见本目录 `TOEFL_REMAINING_GAPS.md`。
- 执行期工作目录：`toefl-api/repair-20261005/`——计划 `PLAN.md`、修前基线 `hashes-before.json` 与 `hash_files.py`、备份 `backup/`、证据 `evidence/`（24 文件）、最终报告 `REPAIR_REPORT.md`、`evidence-summary.json`、`cleanup-manifest.json`。临时程序与下载物在 `runtime/`（已按 S06 删除）。

## 0. 边界、环境事实与完成定义

### 0.1 允许修改 / 禁止操作

- 允许修改：`toefl-api/lib/*.mjs`、`toefl-api/toefl-cli.mjs`、必要的 `toefl-api/tools`、`examdata/src/examdata/api/toefl.py`、`examdata/docs/TOEFL_API.md`、`toefl-api/REPORT.md`。
- 禁止：改 CIE/Edexcel/IELTS 实现；操作既有服务/数据库/绑定/密钥；commit/push；安装依赖；抓登录或付费内容；访问锁定条目。
- 联网规则：串行调用，网络请求起始间隔 ≥1.1 秒；任一源请求出现 403/404/409/502、超时或解析失败 → 保存 URL/状态/时间/阶段并停止剩余联网测试，不重试、不换镜像、不加 force。可以继续离线修复与统计，报告联网阻塞，不得写全通过。
- 根目录不是 Git 仓库 → 不依赖 `git diff`；以 SHA256 基线 + 备份作为变更凭据。

### 0.2 环境事实（2026-10-05 侦察）

- Node：v24.19.0（`/c/Program Files/nodejs/node`）。
- Python：`examdata/.venv/Scripts/python.exe` = 3.14.7。
- 端口 8125 空闲（netstat 查无占用）；如被占用另选空闲端口，不停止别人的服务。
- AGENTS.md：工作区根、`toefl-api/`、`examdata/` 下均无项目级 `AGENTS.md`/`CLAUDE.md`；适用的是全局 `C:/Users/weo/.agents/AGENTS.md`（Kander 入口，rules.code=true，已读基础与代码规则分册）。本任务不走 Kander 流程，遵循其通用代码质量要求。
- `examdata/` 是既有 git 仓库（分支 `main`、HEAD `d8e64a6`），本轮只读记录，不改其历史；`toefl-api/` 与工作区根不是 git 仓库。

### 0.3 完成定义（验收条件，全部达成才算完成）

1. 共用详情 URL 解析器在 detail、jj、questions 用户输入与低层 `fetchPage` 前生效；非法 URL 在读取业务缓存之前被拒绝；重定向逐跳校验、上限 5 跳。
2. speak/write 内容在写缓存之前验证必要结构；HTTP 200 维护页/登录页/无题干页不得 `ok:true`、不得写入正式缓存；已有缓存命中同样验证内容。
3. 14 道听力表格题得到明确结构（列/行/按行答案，顺序以 DOM 为准），题型不再误标 `multiple_choice`，多值答案不截取首字母；完整性字段区分抓取完整与内容可作答完整。
4. `info` 可筛选 era 仅六个编号分区；pre/post-2023-07 仅作格式改版参考说明；`sets` 未知 era 返回 HTTP 200 + `ok:false`；set/tpo 参数整串严格解析。
5. 全量复测：离线重解析 971 入口 0 新增失败；HTTP 流程与 CLI 八命令通过；联网四科样本 + 音频 Range 验证按规则执行；examdata 全量 pytest 保留退出码与汇总、逐条归类失败。
6. 文档口径限定到实际证据；runtime 清理并输出 manifest；非托福模块哈希复核一致；端口关闭；终态冒烟通过。

## 1. 问题清单（来自审计报告）

| 编号 | 问题 | 关键反例 |
|---|---|---|
| P1-01 | 详情 URL 未限制主机 → 任意地址访问与缓存污染 | `http://127.0.0.1:<port>/detail/speak/auditprobe20261005.html` 被 CLI detail 接受，本地服务收到 1 次请求且响应被写入 kmf 缓存 |
| P1-02 | 口写错误页被当作成功内容并写缓存 | HTTP 200 维护页（正文仅 `upstream maintenance`）→ `ok:true`、`question:null`，并写入缓存 |
| P1-03 | 14 道听力表格题丢选项与答案，却报告 `complete=true` | 14 道全部 `type:"multiple_choice"`、`options:[]`、`answer:[]`；代表 `listen/11dwej.html` 源答案 B A A B |
| P2-01 | `info.eras` 暴露 pre/post-2023-07，但无法筛选 | `/sets?era=pre-2023-07`、`post-2023-07` 均 HTTP 200 + `ok:true` + 空列表（假成功） |
| P2-02 | `normTpo` 宽松匹配（从任意字符串提取数字） | `set=garbage54` 静默成功返回 tpo-54 |
| P2-03 | 完成汇报超证据（文档层面） | 旧报告宣称"全量在线零差异"等，仅凭 4 列表页 + 2 详情页归一化比较 |

## S01. 基线、备份、受保护文件清单（状态：done）

**目标**：在任何修改之前建立可复核的变更凭据与回滚材料。

**实现要点**：

- 新增 `toefl-api/repair-20261005/hash_files.py`：记录/对比 SHA256（区分 `[allowed]` 允许修改文件与 `[control]` 控制文件）。
- 生成 `hashes-before.json`：34 文件 = 19 个允许修改文件 + 15 个 CIE/Edexcel/IELTS 关键模块控制文件。
- 备份将修改的业务文件（保持相对路径）到 `repair-20261005/backup/`（11 文件）；不备份已要求删除的测试下载物。
- 建立 `repair-20261005/{PLAN.md,evidence/,runtime/}` 工作布局；临时测试程序与下载物只放 `runtime/`。
- 记录审计探针反例（修前探针输出 `probe-*.txt`、解析器校准 `calibration*.json`）。

**验证与证据**：`hashes-before.json`（含 `hash_files.py record/compare` 运行记录）；`backup/`（11 文件）。

**完成标准**：哈希基线覆盖全部允许修改文件与控制文件；备份可恢复；工作布局就绪。✅

## S02. URL 校验与缓存写入修复（P1-01、P1-02）（状态：done）

**目标**：非法主机不能访问、不能命中缓存；错误页不能成为成功结果或写入缓存。

**实现要点**：

- `lib/kmf.mjs` 新增共用严格解析器：`parseKmfDetailUrl` / `isKmfDetailUrl` / `resolveKmfHref` / `kmfRedirectValidator` / `validateKmfContent`。
  - 只接受 `https://toefl.kmf.com`；拒绝 userinfo、非标准端口、其它协议/域名/IP。
  - 路径完整匹配 `/detail/(read|listen|speak|write)/[a-z0-9]+.html`，兼容实测存在的单个数字后缀 `/1`（后缀统计：jj 索引 32 条带 `/1`，kmf 索引 758 条无后缀，全量缓存 4417 文件无其它形态——先统计后确定，见 `evidence/url-stats.json`、`evidence/suffix-scan.txt`）。
  - 拒绝 query/fragment 注入、多余后缀；不使用 substring/includes 判断。
- 调用点：detail、jj、questions 三个 CLI 入口 + HTTP 对应路由 + 低层 `fetchPage`（在读缓存与联网之前）；内部 tab 相对路径用 `resolveKmfHref` 以可信 origin 解析后再校验。
- `lib/util.mjs` `httpGet` 增加手动重定向跟随：每跳先经 `validateRedirect` 校验目标 origin/path，`maxRedirects=5`，相对 `Location` 先解析再校验，缺 `Location` 报错；失败 `ok:false`。GitHub 原文 fetch 不经过 kmf 校验器（合法用途分离）。
- `lib/jj.mjs` `jjHashOf`/`fetchJjDetail` 改用严格解析器，非法 URL 在读取缓存与联网前拒绝。
- `fetchPage` 顺序改为：**URL 校验 → 缓存命中读取后也要验内容（坏缓存拒绝返回 `ok:false`）→ 联网响应验内容通过后才写缓存**。
- `validateKmfContent(section, html)` 按科目验证必要 DOM：read 需 `#js-stem-cont` + `inner js-translate-new` 题目容器 + `g-hl-2` 答案标记；listen 需 `question-cont js-translate-new` + `data-href="/detail/listen/"` + `true-answer`；speak 需 `item-desc` 题干 ≥10 字；write 需 `content-subject` 材料/题干 ≥10 字。维护页/登录页/无题干页均不满足。
- 写作 `essay` 可空、独立写作 `audio` 可空——空值不算失败；合法页面结构不可识别时明确失败并保留统计，不编造题干。speak 新增结构化字段（`audio_url` 等），write 新增 `materials`/`prompt`/`essay`，保留原字段兼容。

**验证与证据**（全部 0 失败）：

| 验证 | 数量 | 结果 | 证据 |
|---|---|---|---|
| CLI 矩阵（10 类非法 URL × detail/jj/questions + 合法对照） | 59 用例 | 59 pass / 0 fail | `evidence/cli-matrix-after.txt` |
| 受控 localhost HTTP 服务（非法 URL 请求数=0；恶意主机+真实缓存 hash 不读缓存；合法 cache-hit 正常） | 24 断言 | 24 pass / 0 fail，localhost hits=0 | `evidence/zero-request.json` |
| 重定向逐跳校验（5 跳成功、6 跳拒绝、跨主机拒绝且恶意主机未被 fetch、http 降级拒绝、相对路径接受、缺 Location、非详情路径、userinfo、query 注入、fetchPage 不写缓存） | 10 用例 | 10 pass / 0 fail | `evidence/redirect-validation.json` |
| 全量索引 URL 严格解析（kmf 758 + jj 213 非锁定） | 971 | 0 失败 | `evidence/validate-scan.json` |
| 全量缓存内容复检（listen 2133 / read 1880 / speak 271 / write 133） | 4417 页 | 0 失败 | `evidence/validate-scan.json` |

**完成标准**：非法 URL 在任何缓存/网络操作前拒绝；恶意主机无法命中合法缓存；错误页不成功不写缓存；合法缓存与合法原站详情继续工作。✅

**如实限制**：未做真实源站恶意重定向演练（源站未返回跨主机重定向；用 monkey-patch fetch 模拟验证）；维护页拒绝为单元级与缓存级验证（本地构造），未等源站真实返回维护页再演练；节流为单进程内 `THROTTLE_MS=1100`，不提供跨进程全局 1 req/s 保证。

## S03. 听力表格题修复（P1-03）（状态：done）

**目标**：14 道表格题得到完整结构（列、行、按行答案），题型判断正确，完整性表达修正。

**实现要点**：

- 以 `audit-20261005/cache-summary.json` 的 `answer_gaps` 列出 14 个 URL 逐项读取业务缓存，检查 `table.content-logic`、行列文本、`true-answer` 和 `data-type`；不猜 A/B 对应顺序。
- 新增表格题表示 `type:"table_choice"`，字段 `table:{columns:[...], rows:[{label, answer}], answer_letters:[...]}`；列/行顺序以 DOM 为准；保留 `options`/`answer` 契约兼容（表格题 `options:[]` 合法、`answer` 为按行字母数组）。
- 题型判断：识别 `table.content-logic` 即 `table_choice`，不再误标 `multiple_choice`；多值答案不截取首字母。
- 完整性：`content_complete` 与抓取完整性分开表达；必要选项/表格/答案缺失产生 `content_gaps`，`fetchKmfSet` 不再无条件 `complete=true`；原本无选项的合法题型按题型判断，不一刀切要求 options 非空。
- 阅读多选（`isMultiSelectForm`）同样修复：选项数完整保留，`n_options` 从 0/残缺恢复为全量（20 道）。

**验证与证据**：

- 14/14 逐项通过：答案数量=行数、字母落在列范围内、与源 `true-answer` 一致（`evidence/reparse-diff-summary.txt`、`evidence/reparse-diff.json`）。
- 代表页 `listen/11dwej.html`：索引条目（914lxj）与审计 URL（11dwej）双查均为 4 行、答案 B A A B，`problems:[]`。
- 全量离线重解析（禁网，全部 TPO 758 + 免费机经 213，共 971 入口）：971/971 可解析，**新增失败 0**；变化 34 条目 / 48 字段变化（14 表格题 × type+answer + 20 阅读多选 n_options），全部为预期修复，`unexpected=0`；essay 字符差异 0。未编造任何源站没有的解析/答案。

**完成标准**：14 项正确结构、逐项复核通过；全量重解析不新增失败；不得用题干长度或答案非空替代"答案数量=行数、字母在列范围"检查。✅

## S04. 筛选与身份修复（P2-01、P2-02）（状态：done）

**目标**：`info` era 与实际筛选能力一致；`sets` 不返回假成功；set/tpo 参数整串严格解析。

**实现要点**：

- `info`（CLI + HTTP 同步）eras 仅保留 catalog 真正实现的六个编号分区：`tpo-01-10`、`tpo-11-20`、`tpo-21-30`、`tpo-31-40`、`tpo-41-50`、`tpo-51-54`。
- pre/post-2023-07 移入 `format_revision_reference` 参考说明，明确"不支持按它们映射套次"；`exam_date` 保持 null；没有真实来源就不建立改版套次映射。
- `/sets` 未知 era → HTTP 200 + `ok:false`（业务失败），不再返回成功的空列表。
- set 参数只接受整串 `tpo-N`（N 正整数）；tpo/tpo-min/tpo-max 只接受完整十进制整数，随后按收录范围处理；明确拒绝 `garbage54`、`tpo-540`（业务失败）、`tpo-54junk`、`54.5`、负值、混杂文本。

**验证与证据**：

- CLI 59/59 中含 18 个 era/身份用例（`evidence/cli-matrix-after.txt`）；HTTP 流程含 6 个负例（`evidence/http-flow-after.json`）。
- 非法 era/set 全部 `ok:false`；`tpo-30`/`tpo-54` 合法调用不变；HTTP 与 CLI 结果一致。

**完成标准**：`info` 六分区 + 改版参考说明；未知 era 业务失败；非法身份明确拒绝；合法调用不回归。✅

## S05. 完整复测（状态：done）

**目标**：离线回归 → HTTP/CLI → 联网样本 → 全量 pytest，全部按任务规则执行并留证。

**实现要点与结果**：

- 独立空闲端口 8125；子进程只由本次启动并记录 PID（HTTP 流程 server pid=63128），finally 中 SIGTERM 终止并复核；临时数据库使用 runtime 私有路径（`http-flow-test.db`、`final-smoke.db`），不接生产数据目录。
- **HTTP 流程**（30 cases = 28 真实用例全 PASS / 0 FAIL，2 项为元数据记录；含负例：缺 url=422、非法 url/section/era/set=200+ok:false；locked 列表验证 `url=null`，不抓锁定内容）：`evidence/http-flow-after.json`。
- **CLI 八命令**各执行一次（info/coverage/sets/get/questions/detail/search/jj），59/59 pass：`evidence/cli-matrix-after.txt`。
- **联网四科样本**（串行、起始间隔 ≥1.1s、实测 min_gap_ms=1150、`failure=null`、一次通过；四科各一项 Official 54 详情 `refresh=1`；read/listen 不设 limit 应拉全部题）：
  - read `11m4mj` 10.5s → ok，10/10 题，`content_complete=true`，set_id=tpo-54；
  - listen `11mc6j` 4.9s → ok，5/5 题，`content_complete=true`；
  - speak `f1m9gj` 522ms → ok，题干 125 字，`audio_url` 非空；
  - write `c1m97j` 564ms → ok，prompt 142 字，materials 阅读 1729 字/听力 3660 字，essay 空（正常）；
  - 无 refresh 复跑（纯缓存）四科全 ok、88–110ms——记录真正联网与缓存调用的区别；refresh 流程 17 pages changed / 0 added，cachehit 流程 0 changed / 0 added。
  - **音频 Range**（`bytes=0-1023`，不落正式目录）：listen 206 `audio/mpeg` 1024B `bytes 0-1023/47646`；speak 206 1024B `/183065`；write 206 1024B `/4611734`；均无重定向，sha256 见 `evidence/live-samples.json`。**是 1KB 样本验证，不是完整下载/试听**。
  - 未触发 403/404/409/502/超时/解析失败，未重试、未换镜像、未加 force、未访问锁定条目。
- **examdata 全量 pytest**（`examdata` 下 `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`，`PYTHONDONTWRITEBYTECODE=1`、`EXAMDATA_TEST_LIVE=0`）：
  - **退出码 1**；套件执行到 100%（1185 例），约 20 分钟；**1178 通过 + 6 跳过 + 1 失败**（`-q` 与 pyproject `addopts="-q"` 叠加为 `-qq`，pytest 9.1.1 在该级别不打印最终计数行，以进度标记重建）。
  - 唯一失败 `tests/test_api.py::test_provenance_coverage_is_complete`：判定**既有 / 不相关候选，未修**（审计轮未改业务代码时同一失败；通用溯源覆盖接口，不经 TOEFL 路由；按边界未修其他模块）。
  - 日志 `evidence/pytest-full.log`。

**完成标准**：离线/HTTP/CLI/联网/pytest 全部执行并留证；失败项逐条归类；未验证项如实登记。✅

## S06. 文档、清理与最终交付（P2-03）（状态：done）

**目标**：文档口径限定到证据；清理临时物；输出最终报告与证据汇总。

**实现要点**：

- `examdata/docs/TOEFL_API.md` 与 `toefl-api/REPORT.md` 修订：新增字段文档（table_choice 等）、era 说明、URL 校验与合规限制；把"完整/零差异/1 req/s/全量在线"宣称限定到实际证据范围——缓存全量复算（4417 页/971 入口）与联网四科样本分别表述；源站上限（Official ≤54、部分页 404、无年份/考试季节、无范文/转写字段）写明；单进程节流非全局保证；未宣称支持 2026 新版全题库；未做跨进程并发压测。
- 写 `repair-20261005/REPAIR_REPORT.md`（根因、改动文件、修前反例、修后结果、精确数量、失败/跳过/未验证项、pytest 汇总）与 `evidence-summary.json`（只留元数据/统计/来源 URL/hash/退出码）。
- 清理：删除 `runtime/`（48 文件 / 3.1M）与 `.terminal-smoke/`（5 文件 / 520K）——删除前以 PowerShell `Resolve-Path` 核对绝对路径为 `C:\Users\weo\Desktop\api\toefl-api\repair-20261005\runtime`（及 `.terminal-smoke`），用 `Remove-Item -LiteralPath ... -Recurse -Force` 删除并复核不存在；删除本次生成的 orphan pyc（`toefl.cpython-314.pyc` 两实例）。不删其他模块测试/pyc、正式工具、原始第三方源、data 索引、`.data` 业务缓存（4417 页全保留）、`audit-20261005/` 审计证据。
- 输出 `cleanup-manifest.json`（具体路径、类别、数量、剩余检查）；`hash_files.py compare` 复核控制文件 0 差异（`evidence/hashes-compare-final.txt`）；确认端口 8125 无监听。
- 文档定稿后终态冒烟（独立端口 8125、私有临时 DB、全走缓存无新下载）：info / get tpo-54 / detail speak f1m9gj / search punctuated / questions tpo-30 read——**5/5 PASS，EXIT=0**（server pid=66336 已终止），`evidence/final-smoke-post-cleanup.json`。

**完成标准**：文档口径与证据一致；清理 manifest 完整；控制哈希 0 差异；端口关闭；终态冒烟通过。✅

## 附录 A. 问题 → 步骤 → 证据对照表

| 问题 | 修复步骤 | 核心改动文件 | 主要证据 |
|---|---|---|---|
| P1-01 URL 未限制主机 | S02 | `lib/kmf.mjs`、`lib/jj.mjs`、`lib/util.mjs`、`toefl-cli.mjs`、`api/toefl.py` | `cli-matrix-after.txt`、`zero-request.json`、`redirect-validation.json`、`validate-scan.json` |
| P1-02 错误页假成功写缓存 | S02 | `lib/kmf.mjs`、`lib/jj.mjs` | `validate-scan.json`（4417 页复检）、`zero-request.json`、`live-samples.json` |
| P1-03 表格题丢失 | S03 | `lib/kmf.mjs`、`api/toefl.py`（字段透传）、`docs/TOEFL_API.md` | `reparse-diff.json`、`reparse-diff-summary.txt` |
| P2-01 era 假成功 | S04 | `toefl-cli.mjs`、`api/toefl.py` | `cli-matrix-after.txt`、`http-flow-after.json` |
| P2-02 身份宽松匹配 | S04 | `toefl-cli.mjs`、`api/toefl.py` | `cli-matrix-after.txt`、`http-flow-after.json` |
| P2-03 文档超证据 | S06 | `docs/TOEFL_API.md`、`REPORT.md` | 两文档修订段落、`evidence-summary.json` limitations |

（全部步骤 done；逐项命令、退出码与缺口登记见 `EXECUTION_CHECKLIST.md`。）
