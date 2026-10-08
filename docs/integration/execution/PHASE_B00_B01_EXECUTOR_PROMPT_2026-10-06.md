# 下一阶段执行提示词：B00–B01

你是 C:/Users/weo/Desktop/api 的整合执行 agent。Phase A 已封版。你的下一轮任务是完成 **B00：记录释放与重新建立最终基线；B01：在私有副本中调和暂存方案**。完成有证据的交付，不只再写一份计划。此轮不执行 B02–B10，不把私有副本通过称为原件已合并或已部署。

## 0. 先读现有记录，不重做 Phase A

完整阅读：

1. C:/Users/weo/Desktop/api/docs/integration/MASTER_EXECUTION_PLAN_EN.md（主契约，尤其 §0、§3.5、§12–17）。
2. docs/integration/EXECUTOR_PROMPT_EN.md（Phase A 原提示词，仅用于历史范围；明确释放后按本轮 B00/B01 指令和主计划执行）。
3. docs/integration/execution/ownership.json、execution-ledger.json、PHASE_A_REPORT.md、PHASE_A_DEFERRED_WORK.md。
4. docs/integration/execution/PHASE_A_INDEPENDENT_REVIEW_2026-10-06.md 和 evidence/A15/independent_checks_2026-10-06.txt。
5. A14_MERGE_MAP.json/.md、A14_RELEASE_MANIFEST.json、A14_REHEARSAL.json、A12_ROUTE_COMPATIBILITY_WORKSHEET.json、docs/integration/ROUTE_INVENTORY_CURRENT.json。
6. 当前 Kimi 最终报告、相关代码/测试/路由注册与适用 AGENTS.md。不要用旧消息或目录静默推断完成；不向 Kimi 发送指令或干预其进程。

所有相对路径均以 C:/Users/weo/Desktop/api 为根。先读取台账和实际文件，检查是否已有新 B 记录；若有，按最新证据续作，不覆盖它们。

## 1. 授权与入口检查

当前已知基线：A00–A15 staged_pass；B00–B10 not_started；七 gate 全 false。“检查、写下一阶段提示词”没有释放原件路径；收到本文件也不等于人类已经释放。

只有当前会话的人类明确释放，才能登记 original_paths_released。记录原文、实际消息时间（Asia/Shanghai，不能编造）、具体路径范围、剩余约束。若会话已经给出这些信息，直接使用，不重复索要。时间无法精确取得时如实记录时间精度及来源。

没有明确释放：保持 A 封版和 B 状态，完成可允许的只读预检和两写根内的准备交付，报告缺少的确切释放范围后停止，不标 B00/B01 passed，不开始复制/执行仍属 active-owner 的材料/时间表代码。不要循环轮询 owner 或把沉默视为授权。

授权凭据示例，仅供人类填写，**示例本身不是授权**：

```text
我确认相关 owner 工作已经结束，释放以下路径用于 B00 基线记录和 B01 私有副本调和：<明确路径列表>。
本轮只准读取释放原件、在 integration-staging/runtime/phase-b/ 中制作私有候选、在 docs/integration/execution/ 下写证据；不修改原件、不切服务、不写真实业务数据、不联网、不恢复 CIE、不远程部署、不清理原件。
消息时间由执行 agent 按此条实际时间记录。
```

这是一种可用的有限释放，不应擅自扩大为合并权限。若人类授权范围不同，忠实使用实际授权。明确释放一个子集后，只处理其覆盖的文件；其他路径继续保护。

工作输出放在：

```text
C:/Users/weo/Desktop/api/integration-staging/runtime/phase-b/<本次唯一运行标识>/
C:/Users/weo/Desktop/api/docs/integration/execution/evidence/B00/<本次唯一运行标识>/
C:/Users/weo/Desktop/api/docs/integration/execution/evidence/B01/<本次唯一运行标识>/
```

每次创建前确认所有权、现有内容和绝对路径。不要覆盖 A 暂存源和 A14 文件；新增 B 版本记录。不要删除旧审计证据或私有失败副本来制造干净结果。

## 2. B00：最终释放基线与可靠台账

### 2.1 保存 A 封版输入

把当前 A 台账、ownership、worksheet、A14 map/manifest/rehearsal 的精确字节与 SHA256 保存到本次 B00 证据目录，标注其来源和时间。A00–A15 记录以后保持不变；不把 staged_pass 批量改成 merged_pass。

### 2.2 建立 Phase B 台账工具

现有 integration-staging/tools/ledger_update.py 只接受 PHASE_A_ISOLATED_ONLY，拒绝 merged_pass；--validate-only 主要是摘要输出。不要用它登记 B 合并，不删除它的 Phase A 断言。

新增独立工具（建议 integration-staging/tools/b_ledger_update.py）：版本化模式、逐包允许路径、按动作声明所需 gate、原子写入与回读、并发修改检测，保留完整历史。实现并测试以下拒绝条件：

- gate 没有人类凭据四要素却要求开启；授权范围不包含目标路径。
- 缺依赖、伪造 passed、未附具体命令/退出码/证据，或验证时输入摘要已经变化。
- 通过 original_paths_released 自动开启其他 gate；修改 A00–A15 封版记录。
- 将私有候选验证标为原件 merged_pass；偷偷扩大 allowed_write_roots。

为 B00/B01 用 staged_pass 表示本轮私有准备验收，额外明确 `original_changes_applied=false`；若既有最新 schema 有不同合法规范，解释并一致采用它。mode 建議 PHASE_B_PRIVATE_RECONCILIATION，不伪造主计划规定的状态。未满足强制项就 partial/blocked，注明确切缺口。

其他 gate 仍保持实际人类授权状态。本轮全程不触及 service/data/upstream/CIE/deployment/cleanup 动作，因此不能为方便自行开启它们。

### 2.3 新基线与路由 worksheet

只读记录释放路径的实际源代码、tests、报告、配置/入口、Node 组件、前端和相关文档摘要；记录当前 revision 及已修改文件列表（不写 Git 索引，不 stash/reset/commit）。至少核对 A14 的所有目标和拟原件编辑项，不只看 HEAD。

逐个记录 A14 base、当前原件 hash、是否存在、owner、是否释放、变化含义。Kimi 新增内容是新基线，不回退它来套用旧 patch。所有权不明的文件不复制、不执行、不改。

先用静态读取重建路由清单，避免 import 原 app 触发目录/DB 初始化。路由身份按 method + 完整 path，保留顺序、动态/静态路径冲突、operationId、响应类型、功能来源。保留 71 个原基线路由；登记 Kimi 新增/变更，并逐项解释变化。七条 deferred_active_owner 路由释放后不能机械改成通过，必须有对应证据。

建议输出：B00_RELEASE_RECORD.json、B00_BASELINE.json、B00_ROUTE_INVENTORY.json、B00_ROUTE_COMPATIBILITY_WORKSHEET.json、B00_REPORT.md。记录时间、scope、observed_only/not_run、来源路径和 SHA256。

### 2.4 B00 验收

释放凭据有效；目标范围明确；新版台账工具拒绝测试通过；新基线可复现；71 条旧路由去向和新路由均有记录；A 记录未变；没有原件写入。不能靠新增路由数或只比较 HTTP path 宣称兼容。

## 3. B01：私有副本逐文件语义调和

在唯一运行目录创建最小必要私有源副本，拒绝 junction/symlink 越界；不复制 venv、live DB、缓存、PDF 数据、CIE tmp 或 secret 配置。没有数据写授权时只能用已允许的私有 fixture，不打开/备份 live DB。

按 A14 的 247 条目及 92 not_merged 排除理由逐项重评。使用“旧 base → 新释放原件 → staged 提案”做三方语义调和；缺旧 base 字节时明确降级为两方比较及其局限，不能称完整三方合并。逐模块形成差异、用途、兼容影响、候选文件摘要与回滚动作，不进行无关格式化。

### 3.1 本次必须修复的 F01

A14 把 CLI 目标写成 examdata/cli.py，但实际入口为 examdata/src/examdata/cli.py，pyproject.toml 的 script 是 examdata.cli:app。重新确认最终入口、命令冲突、读取命令/刷新写入命令的分离，将 B01 map 指向实际生效文件。base_exists=false 的回滚不能写 restore bytes；新文件记录“仅当候选 SHA256 仍匹配时删除”，已有文件记录恢复 B00 最新 base 并检查后来修改。

不要直接改封版 A14 map；生成新的 B01_MERGE_MAP.json/.md，附 A14→B01 的理由差异。不要恢复 A14 旧 base 覆盖 Kimi 最终代码。

### 3.2 模块布局与资源迁移

明确最终包名，可采用 examdata.integration，但不得把 examdata_integration 源文件按目录一复制就认为完成。逐项检查：

- absolute/relative import、动态 import 字符串、package discovery、CLI 和 api 注册入口。
- conftest/guards 的“禁止 examdata”规则与路径根计算：私有目标需要导入 examdata，但仍禁止解析到真实原件/shared editable checkout。
- 所有应用模块 __file__ 都来自本次私有候选；保留私有数据根和网络守卫，不为导入方便解除隔离。
- contracts/schemas、fixture provenance、config 示例、运行时资源定位与不同 cwd；不要依赖 staging 的 PYTHONPATH 使错误布局蒙混通过。
- real Node components 与 synthetic fake-node-cli/manifest 分开；真实组件尚未释放就继续 not_run，不能用 fake 填补生产发布清单。
- 前端 tests/fixtures 不进入生产静态服务目录；保留可逆客户端开关和当前 Kimi 前端功能。

B01 可验证源码候选解析和资源布局；wheel/干净环境安装属于 B09，不能提前以未构建包宣称安装通过。共享 venv 只用于读取现有解释器，不安装/升级其依赖。

### 3.3 验证方式

先固定私有目录、网络守卫与所有会写路径，之后才导入候选 app 或运行候选/释放测试。不要直接在 examdata 原目录运行 pytest；原 conftest 可能在收集期写 .pytest_cache。

为本轮编写独立、可复制的 run/check 工具，命令日志保留 cwd、非秘密环境、开始/结束、退出码与 stdout/stderr。脚本存在且 --help/参数核实后才执行；不要假装有不存在的 B00/B01 工具。

运行有意义的针对检查：CLI 真正生效的解析来源（不执行刷新/爬取）；候选模块解析；不同 cwd 的组件/资源解析；静态+参数化路径顺序与冲突；保留 legacy 默认 content type 和失败语义；CIE SHA/坐标和 partial/uncertain 不提升；IELTS 缺槽/Q41/答案冲突、TOEFL 表格和手动判断来源不丢失；材料与时间表保留最终 Kimi 功能、null 日期/考季证据。实际源数据/联网验证无授权时标 not_run。

在私有候选运行受控兼容回归，不机械要求仍为 887 个测试：记录新增、迁移、替换或未运行项及原因，强制用例不得静默 skip。出现失败先落盘，不为使通过而删除 Kimi 测试/功能。保留全部 mandatory 检查到最终验收。

B01 输出建议：B01_LAYOUT_DECISION.md、B01_MERGE_MAP.json/.md、B01_RECONCILIATION_DIFF.md、B01_TEST_REPORT.md、B01_ROLLBACK_PLAN.json、B01_REPORT.md。每项包含目标、旧/新 base、候选、理由、包 owner、依赖、需要的 gate、可逆动作。

### 3.4 B01 验收与停止点

每条映射有明确处理/排除理由；CLI 目标与回滚问题修正；没有丢 Kimi 功能/测试；私有候选模块/资源解析正确；真实原件没有被写；所有必需检查有证据或任务明确 partial/blocked；台账与实际结果一致。

完成 B00/B01 后停止本轮，交付 B02 的具体输入与尚关闭 gate。不开始 B02–B10，不将本轮 staged_pass 当成 merged_pass。若部分路径未释放，先完成独立可做工作，再列未完成项，不能把整包标通过。

## 4. 后续 gate 与不可省略事项

按 PHASE_A_DEFERRED_WORK.md 和主契约检查；现有 B blocked_by 只列 original_paths_released 不代表其余 gate 可忽略：

| Gate | 控制的动作 / 既有包要求 |
|---|---|
| original_paths_released | B00–B07/B09/B10 的释放范围；不包含隐含扩大权限 |
| real_data_write_authorized | B03/B08 真实业务数据写入与迁移演练的授权数据范围 |
| existing_service_cutover_authorized | gate 表列 B02/B06/B07；实际重启、配置/端口/运行切换需明确授权；私有预备结果不能算完整包已通过 |
| upstream_requests_authorized | B05 与任何实际上游请求，不能拿本地 GET 当作无副作用 |
| cie_resume_authorized | 停止批次续作独立授权；路径释放和 upstream gate 均不自动恢复 CIE |
| remote_deployment_authorized | B10 实际远程部署，需真实目标和范围 |
| original_cleanup_authorized | B10 原件清理，不删除原件来完成迁移 |

对计划中 gate 表与包正文有歧义的动作，先区分私有准备与实际受保护效果，记录具体冲突并在两写根内继续独立工作；不能把广泛的代码释放解释为 live cutover。缺少授权且需要受保护动作时，只向人类提出一条确切动作/范围的问题，不反复确认已有授权。

后续 B08 必须真实一致备份、私有目标迁移和恢复验证，不能继续用数据库 not_run 通过最终验收；B09 必须 wheel 与干净安装、最终回归及 source/data revision；B10 必须真实差异、完整兼容矩阵、浏览器流程证据、部署/回滚说明，并如实区分 cutover not_run/已执行。

## 5. 通用停止与报告规则

发现私有路径越界、原件写入风险、源摘要在调和时再次变化、授权不覆盖、不可归因失败时，保存具体证据并停止依赖动作。可以继续独立任务，不能回滚 owner 变化或用旧快照覆盖原件。所有删除/恢复只作用于确证本轮所有的私有路径；先校验解析后绝对路径及摘要。不创建/启动新 chat 或给其他 agent 发指令；不自行派发子 agent。

不得提交/推送/reset/stash，不写共享/用户级环境，不装共享 venv，不碰现有 5188/8000，不打开 live DB，不访问上游，不恢复 CIE，不部署/清理原件。

最终报告先给结果，再列 B00/B01 状态、实际命令与证据、新基线路由数和每条旧路由去向、CLI 映射修正、候选差异、失败/警告/skip、仍关闭 gate、确切下一步。证据标签明确区分 copied_snapshot/synthetic/private_candidate/original_read_only/merged/live/deployed。本轮完成意味着 B00–B01 私有调和交付完成；不意味着整合上线或真实数据全部完成。
