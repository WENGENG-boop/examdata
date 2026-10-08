> 最新剩余工作结果见 [REMAINING_WORK_RESULTS.md](REMAINING_WORK_RESULTS.md)，前批记录见 [REVIEW_ACCEPTANCE.md](REVIEW_ACCEPTANCE.md)。下文保留为切换时历史现场，不能作为当前状态。

# examdata 开发交接：审查修复未完成

更新时间：2026-09-30 16:36（本地时间，UTC+08:00）。用户要求汇报现状并切换 Agent，因此本轮已停止实现；本文不是完成报告，也不是正式审核通过证明。

## 1. 接任 Agent 先读这一段

- 仓库：`C:/Users/weo/Desktop/api/examdata`；会话初始工作目录是其父目录 `C:/Users/weo/Desktop/api`。
- Windows + Git Bash；项目 Python：`.venv/Scripts/python.exe`，不要用缺少项目依赖的系统 Python。
- 分支：`main`；HEAD：`d8e64a690b4e8f1b7cb8dac32d6fc2325252d80e`。
- 全部开发改动尚未提交、未推送。交接检查时有 **40 个已跟踪文件修改、10 个未跟踪文件**，本文创建后另多一个文档；`git diff --stat` 不统计未跟踪内容。
- **不要 reset、checkout、stash 覆盖工作树，也不要为清障删除已有数据。** 下一个 Agent 必须在现有代码上继续，不应重做全部修复。
- **`examples/browser.html` 是用户已有改动，不属于修复分工。禁止修改/回退。** 当前 SHA256：`fad2bca3920ecf13801c68770f398c571edf84c473b395d741a2b5a888a156b5`，大小 11051 字节。
- 不擅自 commit/push；先把修复和验证闭环，提交/集成另按用户授权处理。“不建卡/不建 worktree/不提交”是此前助手的执行选择，不能倒写成用户原话。
- 不把开发数据库当测试写入目标，不在开发库运行 reparse、reset、enrich 或 `scripts/verify_state.py`；后者也会重建并提交，不是只读脚本。
- 不运行真实站点采集来代替离线回归。H 分工曾误触发包含真实上游路径的测试，故不能宣称本轮全程没有联网尝试。

**目前不能交付为“全部修好”：已知有红测试、最后改动未复测、人工数据保护未完成、全量测试/空库/wheel 尚未重新验证。**

## 2. 用户目标与执行历史

原用户要求“完整的代码审查一遍仓库和代码”，随后要求“修”“继续”“为什么停下来了”“完成所有进度”。没有发现用户批准把历史发现永久缩减成少数修复的记录。

历史主会话：`session_9b704d3e-fe5d-4b67-a1aa-a59018f0be1c`。当前延续会话：`session_7462733f-bfb6-4c1b-ba73-507bfa5455f2`。

本轮流程：8 个只读调查分工完成后，形成 5 批修复计划；再派 9 个实现分工 A–I。用户中断时 **E 完成、其余 8 个中断**。切换前已恢复这些分工，仅让它们返回交接事实，未让它们继续实现或跑测试。

计划存在于：
`C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_7462733f-bfb6-4c1b-ba73-507bfa5455f2/agents/main/plans/crimson-avenger-white-tiger-dagger.md`

计划为自动 permission 模式退出时自动批准，**不是用户逐条确认过的业务决策**。下面记录实际落地状态；不要仅按计划判断实现完成。

## 3. 已有修复基线：保留，别重做

进入本轮前工作树已有：测试 SQLite 副本隔离、override `*` 精确适用判断、provenance board 范围、taxonomy/similarity 幂等、Edexcel URL 白名单及相对导入、查询分页/计数/LIKE、CLI 参数守卫、robots 分类与 Fetcher 复用、25 clip 上限、附件头生成、health 异常脱敏、API 初始化缓存、`py.typed` 等修改。

**旧版本实际验证记录**（发生在本轮大改动之前，不能代表当前代码）：

| 场景 | 旧版本结果 |
| --- | --- |
| 正常语料，全套 pytest | 438 passed，0 skipped，0 failed |
| 无源库/未建表/空 document | 256 passed，182 skipped，0 failed |
| 空库查询参数守卫 | 6 passed，7 skipped |
| PEP517 wheel 构建、target 安装 | 成功，wheel 内有 `examdata/py.typed` |
| installed wheel CLI/API | initdb、search、health、分页及 422 实际调用成功 |

旧 wheel 曾为 182444 字节，SHA256 `0bd9b25b6b17faab1fcbcf31b528f08801624cbd394beefdf72f62006e5aa49a`；私有构建/安装目录已清理。**该 wheel 不含本轮新增修复，必须重建。**

## 4. 当前分工状态与最后验证

以下数字来自各实现 Agent 的已结束工具结果/交接记录；切换阶段没有重跑 pytest。凡“测试后又编辑”的项，都不视作最终代码已验证。

### A：同步版本、missing、状态（agent-145）

文件：`src/examdata/sync/service.py`、`tests/test_sync_service.py`。

已落地：每轮统计/seen/cache 重置；missing 限成功完整巡检来源；相同 Document 当前 SHA256 不新增 revision；同 URL ArtifactRevision 链；candidate hash/validators/error；gated 优先于 no-download；304 无有效当前版本失败；partial/failed 状态；显式 Settings 存储根。内存 SQLite 回归开启 FK。

最后通过命令：
```bash
EXAMDATA_DATABASE_URL=sqlite:// EXAMDATA_DATA_DIR="$PWD/pytest-of-weo/sync-a3" \
  .venv/Scripts/python.exe -m pytest tests/test_sync_service.py -q
```
结果：**29 通过**。之后删除 304 分支的一行状态覆盖，未复测。

**已确认未修**：`sync/service.py:478` 仍在 SHA256 unchanged 返回前执行 `doc.status = "stored"`，会把已经解析的 `ok/needs_review` 覆盖。应移到真正新增 revision 路径，并补两种状态保持的回归。

### B：Edexcel 发现完整性/registry（agent-146）

文件：`adapters/edexcel/servlet.py`、`adapter.py`、`adapters/registry.py`、`tests/test_edexcel_adapter.py`。

已落地：HTTP/JSON/envelope/record 字段校验；拒绝 206；达到 cap 或 `nbHits` 表明遗漏时 `ShardExhausted`；取消从截断 facet 猜全量；家族/科目页失败显式错误；合法空响应仍成功；registry warning/LOAD_FAILURES/失败注册回滚。

最后 `pytest tests/test_edexcel_adapter.py -q`：**105 通过**。尝试 `tests/test_adapter_registry.py`：**退出码 4，文件不存在**，该回归尚未创建。

未完成：最后添加的 `EdexcelAdapter.__init__` 空 `load_errors` 列表无消费者、未复测，应清除或完成设计；registry 独立回归；与 conformance 最终联验。

**能力边界**：当前是 fail-closed，不是恢复大科目全量采集。没有可信的穷尽 facet/分页协议；达到上限会明确报错。不能将“不再静默漏数据”宣传为“已完整抓取全部 Pearson 资源”。

### C：编号、评分、跨页图片（agent-147）

文件：`parsing/numbering.py`、`markscheme/cambridge.py`、`parsing/segment.py`、`tests/test_parsing_regressions.py`。

已落地：同行编号链 `N(ii)/N (ii)/N(a)(ii)/(a)(ii)`、ix/x；重复号检测；跨页表格续行/无表头续页证据；分值保守判定；续文/纯图片页覆盖；图片不误挂下方下一题；重复 attach 幂等；父子分值/重复路径 findings。

最后完成的命令：
```bash
EXAMDATA_DATABASE_URL='sqlite:///:memory:' .venv/Scripts/python.exe -m pytest \
  tests/test_parsing_regressions.py tests/test_cambridge_parsing.py
```
**40 通过**，但在最后续页/幂等调整和新增合成测试之前。最终同命令被用户中断，没有最终结果。

语义取舍需复核：保留原 marks；父子分值缺失/矛盾、重复路径或不确定多行 Marks 时总分可能变为 `None`，而不是猜测部分和。不能只看“没有异常”，需核对真实 0580 与下游总分/ReviewTask 行为。

### D：reparse 与 pipeline（agent-148，最高优先级）

文件：`governance/reparse.py`、`parsing/pipeline.py`、新增 `tests/test_reparse_pipeline.py`。

新接口：
```python
ParsePipeline.run(
    *, limit=None, document_id=None, document_ids=None,
    revision_ids=None, retry_failed=False, commit=True,
)
reparse_documents(..., settings=None)
```

已落地：空列表不扩成全库、目标校验；仅目标当前 revision（无 current 时回退最新）；每条解析保存点、失败计数回滚、ParseRun 增量统计；显式 artifact root；缺原件显式失败；reparse 外层保存点/内部不 commit；relink 限相关 entries；derived rebuild 限目标题目，相似题明确 `deferred`；keep_history=False 断开 ReviewTask 的 run FK。

**最后测试：**
```bash
.venv/Scripts/python.exe -m pytest -q tests/test_reparse_pipeline.py
```
**10 passed，2 failed**。两项 scoped reparse（keep_history True/False）在 `_purge_derived → session.flush → DELETE FROM question` 报 **FOREIGN KEY constraint failed**。

确定原因：测试有 `Formula.question_id`，purge 漏处理 Formula。最后只增加 `Formula` 导入（`reparse.py:563`），**没有实现删除/保留逻辑**，故不能说已修。

其他重要未完成：
- `_remap_overrides` 仍无条件 `setattr` 并清冲突（约 505–513 行），绕过版本/基线策略；Paper/改号/歧义自然键及主键复用风险未解决。
- `_purge_derived` 仍删除目标题的 approved/rejected explanation、manual taxonomy、official difficulty。**E 的 generate replace 保护不能防止此删除。**
- relink 只恢复 entry.question_id，不恢复已删 `OfficialAnswer`；QP-only 重解析后 official[]/has_answer 可能丢失。
- fallback 评分身份匹配与当前成功 Paper/ParseRun 选择不够严格。
- similarity 只延期，未真正范围重建；taxonomy 缺种子时未初始化；MS-only 依赖题重建尚需核对。
- 保存点测试只覆盖显式 BEGIN 的内存 SQLite；文件产物不随 ORM rollback；失败 ParseRun 完整审计仍未实现。
- 真实语料、PostgreSQL、旧治理测试未最终验证。

### E：生成解析审核保护（agent-149，唯一完成分工）

文件：`intelligence/explanation.py`、`tests/test_explanation.py`。

已落地：replace 只删当前 provider 未审核 pending；保留 approved/rejected，以及有 done 审计的重新 pending；旧版本审核结果保留；批量 skipped_existing 正确；拒绝空/非字符串 author；ReviewTask 持久化 `reason=explanation_review`、done、assignee=author、JSON 前后状态，与状态同事务。

原问题由合成回归先复现：16 passed、12 failed；修后：
```bash
EXAMDATA_DATABASE_URL='sqlite:///:memory:' .venv/Scripts/python.exe -m pytest \
  tests/test_explanation.py --basetemp=pytest-of-weo/explanation-final -o addopts='' -q
```
**28 passed**；compileall 与局部 diff-check 通过。

注意：这证明生成器/审核入口保护，不证明 reparse/reset 保留人工数据。CLI/文档仍笼统写“生成解析均 pending”，需改为“新生成默认 pending，已有审核结果保留”。

### F：查询、抽题、旋转裁剪（agent-150）

文件：`query/service.py`、`paperqa/locator.py`、`tests/test_query_service.py`、`tests/test_paperqa_locator.py`。

已落地：taxonomy/difficulty EXISTS 去重；source 独立筛选及同关联行条件；全候选池采样，去前5000截断；未旋转分析坐标/旋转渲染 clip；raster 实际放置 bbox；保持25 clip。

最后 `pytest tests/test_query_service.py tests/test_paperqa_locator.py -q`：**55 通过**（24 query + 31 locator）。合成 0/90/180/270° 回归检查非白 PNG；旧代码旋转后全白已实证。

未完成：更新顶部说明；加强“同题同 source 两条 difficulty，不允许跨行拼区间”的断言；全套/API/CLI/wheel 集成。5002题测试曾因 SQLite 临时排序目录失败，fixture 加 `temp_store=MEMORY` 后通过。

### G：流式响应上限（agent-151）

文件：`core/fetch.py`、`paperqa/sources/base.py`、`tests/test_paperqa.py`。

已落地：`MAX_RESPONSE_BYTES=64*1024*1024`（64 MiB）；流式有界读、声明/实际超限关闭且不重试；redirect 逐跳不读中间正文；gzip/deflate 有界解压；source 层再查长度阻止自定义 Fetcher 大正文进入 PDF 解析；UpstreamError=502。

最后离线 `pytest tests/test_paperqa.py`：**93 passed，1 warning**。之后又加入 gzip 多成员和显式 Accept-Encoding，**未复测**。

未完成：robots `_policy()` eager GET 尚无 cap；多 PDF/PNG/ZIP/base64 请求级 aggregate budget 未做；跨主机 redirect/次数耗尽专项；64 MiB 仅单响应及各解码阶段上限，不是进程内存保证。

可能残留 `.paperqa-test-*` 私有目录，不知道准确名称，不要盲删用户目录。

### H：API 安全与 HTTP 契约（agent-152）

文件：`api/security.py`、`api/app.py`、`api/unified.py`、新增 `tests/test_api_security.py`/`test_api_contracts.py`。

已落地：root_path 精确豁免；资产路径 resolve containment/Windows drive/NUL 拒绝；403非法、410缺失/目录；旧/统一 PaperQA 常见结构异常映射固定502；统一链接显式 board；key/CORS/health/403/409/502/下载/资产独立回归。

最后选定 API + `tests/test_paperqa_api.py` 等命令：**84 passed，1 skipped**。skip 为 Windows 真符号链接创建权限不足（WinError1314）；不是其他路径逃逸用例跳过。

未完成：完整构建/全套；Windows链接有权限环境；POSIX反斜杠语义；宽泛 HTTP 捕获与 source 已验证错误映射的边界需审阅。H 曾运行 `test_api.py test_api_unified.py -k 'not live'`，该筛选仍含真实上游测试，不能照搬作为离线命令。

### I：CLI/reset/conformance/conftest（agent-153）

文件：`cli.py`、`scripts/reset_derived.py`、`tests/conformance/test_adapter_contract.py`、`tests/test_cli_guards.py`、`tests/conftest.py`。

已落地：classify current revision/范围删除/一次分类/证据版本；apply conflict 设置 needs_review 并幂等 ReviewTask；报告模式不假称入队；review-list limit>=1；reset main guard/Settings选库/--yes/--dry-run/事务；conformance 离线回放和真实共享断言；私有 DB+文件根、parsed corpus 检测、逐用例 skip、默认 HTTPTransport 禁网。

最后 `pytest tests/test_cli_guards.py tests/conformance -q`：**41 通过**；之后新增6个 guard、调整 conftest/补 imports，未复测。

**重大差距（父 Agent 已读当前脚本确认）：** reset 目前只要求 `--yes`，可删除所有 generated explanations/manual taxonomy/official difficulty，却保留整数 target_id 的 overrides；没有人工数据拒绝保护、没有自然键恢复，也没有严格 SQLite-only 拒绝。**绝不要在真实库用 `--yes`。** 默认是拒绝执行而非自动 dry-run；计划里的 `--apply --yes` 并未实现。

未完成：classify/reset 合成事务回归；D 新接口与 parse-docs/reparse CLI 守卫/--retry-failed适配；E文案；README/DEPLOY旧reset/5000池/发现完整性/conformance说明更新。

## 5. 当前测试隔离契约：下一步必需理解

`tests/conftest.py` 已被 I 大改，不再是旧的 test-copy-{pid}.db 版本：

- 不显式设置 DB URL 时，在 `.pytest_cache/examdata-tests-*` 建私有根，SQLite `mode=ro` 在线备份源库，并复制 artifacts/assets/raw_pages；设置 DB URL 和 DATA_DIR 后 init_db。
- 退出 dispose + rmtree（ignore_errors）；清理是否完整尚未核验。
- corpus 检测要求 question/paper/current revision 且 parse_status 为 parsed/needs_review，逐用例 skip；独立 explanation/query/conformance 应继续运行。
- 默认 monkeypatch HTTPTransport/AsyncHTTPTransport 拒绝 live HTTP，MockTransport 和 TestClient 不受影响；`EXAMDATA_TEST_LIVE=1` 放开。**不要为把测试变绿打开 live 开关。**
- 显式 DB URL 被尊重：可能直接写那个库！只可提供明确的内存/私有库。显式地址但无 DATA_DIR 时建私有文件根却不复制原件，语料 reparse 可能找不到 PDF。
- 缺源库/未建表/空 document 全套在新版 conftest 上还未执行。数据目录复制量/空间/异常/cleanup 与独立测试分级仍需真实验证。

## 6. 优先续作清单

### P0：先恢复可验证状态，别再同时大改全部模块

1. 保留工作树，用当前 diff 判断每个最后修改。处理 D 的 Formula FK 红测试；先明确 Formula/人工内容应保留还是可重建，不把“删 Formula 让测试绿”当成人工保护闭环。
2. 修 A 的 unchanged 状态覆盖；加已解析 ok/needs_review 的回归。
3. 禁止真实 reset；补人工/已审核/官方记录与 overrides 的安全拒绝/恢复策略和合成 FK/rollback 测试。不得关 FK 绕过错误。
4. 重跑 C/G/I 的最终版本离线定向测试；不要沿用“编辑前绿”的数字。

### P1：完成高风险数据一致性

5. D：target范围、reparse失败原子性、OfficialAnswer重建、正确身份/轮次、人工字段 remap 的版本/基线策略；与 E 审核审计共同保留 approved/rejected/manual/official 记录；消失/歧义时保留旧数据并明确冲突，不能丢内容。
6. 处理尚未做的 pipeline/pdfdoc/content_classify：failed ParseRun审计、仅前两页分类/避免整本重复读、双向 specimen 类型族、资产抽取诊断/ReviewTask、历史finding状态；`pdfdoc.py` 和 `content_classify.py` 本轮仍未改。
7. B registry 回归（文件还不存在）、删除无效 load_errors；检查 Cambridge 发现失败仍可能静默空的调用链；与 sync missing 完整性契约联验。
8. G robots cap、整体输出预算和最新解压实现；新的预算数值需明确契约，不能声称单响应64MiB已经限制总内存。
9. 更新 CLI 与 docs：scope/retry、classification报告与入队、reset确认/安全、审核保护、抽题全池、截断fail-closed、测试offline/local/live。

### P2：统一验收后才可说本批完成

10. 正常私有语料和空库全套，任何红测试先处理；区分明确数据skip与代码异常被skip，禁止放宽断言掩盖问题。
11. 重建/安装wheel，再从target导入确认真实CLI/API/下载调用，不能依赖editable源码。
12. git diff-check、开发DB/hash与文件清单、临时服务/目录退出清理、用户HTML保护。
13. 逐项对原审查发现：已修/不成立/证据不足/未完成，不把测试总数当全仓审计闭环。

## 7. 建议验证命令

先看源码和环境，不要把未安装的新工具或新选项当成现有能力。不要在显式开发DB环境运行 pytest。

离线合成核心（建议逐组执行以便定位）：
```bash
# cwd = C:/Users/weo/Desktop/api/examdata
EXAMDATA_DATABASE_URL='sqlite:///:memory:' .venv/Scripts/python.exe -m pytest -q -ra \
  tests/test_reparse_pipeline.py tests/test_explanation.py tests/test_sync_service.py

EXAMDATA_DATABASE_URL='sqlite:///:memory:' .venv/Scripts/python.exe -m pytest -q -ra \
  tests/test_parsing_regressions.py tests/test_cambridge_parsing.py \
  tests/test_query_service.py tests/test_paperqa_locator.py

EXAMDATA_DATABASE_URL='sqlite:///:memory:' .venv/Scripts/python.exe -m pytest -q -ra \
  tests/test_edexcel_adapter.py tests/test_paperqa.py tests/test_api_security.py \
  tests/test_api_contracts.py tests/test_paperqa_api.py \
  tests/test_cli_guards.py tests/conformance
```

正常私有副本全套（新版隔离尚待验证）：
```bash
env -u EXAMDATA_DATABASE_URL -u EXAMDATA_DATA_DIR -u EXAMDATA_TEST_LIVE \
  .venv/Scripts/python.exe -m pytest -q -ra --tb=short
```

空库场景需先完善安全测试入口或建隔离仓库副本（不要移动/删除真实 `.data`），覆盖缺库、未建表、空document、有document但无parsed question。旧 `--data-seed=empty|local` 只是调查建议，**当前没有该选项**。

标准构建历史采用：
```bash
.venv/Scripts/python.exe -m pip wheel --no-deps --wheel-dir <private-wheel-dir> .
.venv/Scripts/python.exe -m pip install --no-deps --target <private-installed-dir> <new-wheel>
```
需确认 PEP517 构建依赖可用，不为绕过构建错误静默换实现；installed target 的 `examdata.__file__` 必须来自该目录，再用真实HTTP调用 health/search/参数422、403/409/502、binary/json/ZIP。禁止以导入成功替代运行验证。

## 8. 数据、进程与现场核验

切换阶段父Agent实际只读核验：

- `git diff --check` 退出0，无空白错误，只有LF→CRLF提示；这不证明业务正确。
- 开发库 `.data/examdata.db`：4182016字节，SHA256仍为
  `d0f59c2a6ab918c8dbd0f6aafba1a4da538687d7606b30830004d074080a6c3f`，与前轮基线一致。
- `TaskList(active_only=true)`：0个工具后台任务。原实现分工均已结束/只读交接，不再开发。
- Windows进程列表仍有4个命令行涉及examdata的Python进程：PID 35124/32916、34140/14016；不含pytest/uvicorn标识，归属未确认，**未杀进程**。不能因TaskList为空便断言全系统无服务。
- 可能残留 `pytest-of-weo/sync-a*`、`api-h-data`、`explanation-final`、`.pytest_cache`、`__pycache__`、`.paperqa-test-*`。仅清理可证明本任务创建的目录，不动 `tmp_dl`、`tmp_unified*`、其他旧用户产物。
- 正式 Kander/reviewer 未执行：当前工作树未提交且非干净审核目标，不能标PM/QA/CSA/Hacker PASS。协作CCCC bootstrap daemon曾连接拒绝，不代表代码验证故障。

## 9. 证据日志与规则

没有仓库级 AGENTS.md/CLAUDE.md（此前Glob未找到）。全局入口：`C:/Users/weo/.agents/AGENTS.md`；新会话按该入口读取作用域config和启用规则。当前配置rules.code/collaboration/git/reporting/review/task_intake/task_groups均true。不应为了完成正式审核擅自提交用户工作树；报告准确标未执行。

证据均在本机，不保证切换到另一机器仍可访问：

- 原审查：
  `C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_9b704d3e-fe5d-4b67-a1aa-a59018f0be1c/agents/main/wire.jsonl`
  原完整报告在该日志第742行，用户后续“完成所有进度”在1797行；先Grep定位，再Read单条记录，不整日志倒入上下文。
- 历史发现核验汇总：
  `C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_7462733f-bfb6-4c1b-ba73-507bfa5455f2/agents/main/tasks/agent-lkmllh38/output.log`
- 本轮8个只读调查完整结果：
  `C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_7462733f-bfb6-4c1b-ba73-507bfa5455f2/agents/main/tool-results/AgentSwarm-call_WPAccA76iwKvZvBYpKncFYcM-5a66ab7f-49f3-4b7d-9d74-1e260f44595e.txt`
- 当前主日志及实现分工日志：
  `C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_7462733f-bfb6-4c1b-ba73-507bfa5455f2/agents/main/wire.jsonl`
  同级 `agents/agent-145` 至 `agents/agent-153` 各有 `wire.jsonl`（A–I；E=149）。优先恢复原分工上下文，不重复盲搜。

## 10. 可直接发给接任 Agent 的任务

> 请读取 `docs/AGENT_HANDOFF.md`，在现有未提交工作树继续完成 examdata 审查修复。先处理重解析Formula外键红测试、同步unchanged状态覆盖，以及reparse/reset人工数据保护；然后复测中断后的改动，再完成全套正常/空库和installed-wheel验收。保留用户examples/browser.html，不重置工作树，不写开发库、不擅自提交推送。逐项报告实际结果和剩余缺口，不能用此前438通过或局部通过宣布全部完成。
