# Phase A 独立检查报告

检查日期：2026-10-06。结论：**Phase A 暂存交付及隔离验证可复现；可以准备 B00–B01，但当前没有原件释放授权，不能开始原件合并。** 人工检查发现一处 CLI 合并映射问题，必须在 B01 修正；自动 PASS 不代表映射已经可以直接执行。

## 本次验证

在 C:/Users/weo/Desktop/api，以现有 examdata/.venv/Scripts/python.exe 只运行暂存工具：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& .\examdata\.venv\Scripts\python.exe .\integration-staging\tools\a15_final_checks.py --out docs/integration/execution/evidence/A15/independent_checks_2026-10-06.txt
```

本次 transcript 记录时间为 2026-10-06 12:43:25 +08:00；命令退出码 0。

| 项目 | 本次结果 | 证据 |
|---|---|---|
| A15 收尾校验 | FINAL_CHECKS: PASS，42/42 | evidence/A15/independent_checks_2026-10-06.txt |
| A14 合并映射重核 | PASS | 同上，build_artifacts rc=0 |
| A14 回滚演练重核 | PASS，报告与新运行一致 | 同上，rehearsal rc=0 |
| 暂存 pytest | 887 passed，0 failed，1 warning，26.00 秒 | evidence/A15/pytest_rerun.txt |
| 暂存前端 Node | 27 passed，0 failed，0 skipped | evidence/A15/node_rerun.txt |
| 台账 | 27 个唯一任务；16 个 staged_pass，11 个 not_started | 独立 transcript + execution-ledger.json |
| 七 gate | 全部 false；本次没有修改 gate | 同上 |
| 基线路由 worksheet | 71/71；64 staged_pass + 7 deferred_active_owner | A12_ROUTE_COMPATIBILITY_WORKSHEET.json + 独立 transcript |
| 合并映射 | 247 条目，92 not_merged，6 项拟原件编辑 | A14_MERGE_MAP.json |

pytest 的 warning 是当前 TestClient/httpx 弃用提示；本次未为此改共享 venv 或安装 httpx2。A15 工具重写了 staging/runtime 下的私有测试/演练输出及 A15 的 pytest_rerun.txt、node_rerun.txt；独立最终 transcript 使用新文件名，没有覆盖旧 final_checks.txt。以上是本次新增的实测结果，不是转述先前测试数字。

## 人工发现与下一阶段要求

### F01：CLI 目标路径与回滚动作不匹配（B01 必须修正）

A14_MERGE_MAP.json 的 planned_original_edits 把 CLI 目标写成 `examdata/cli.py`，base_exists=false、base_sha256=null，却给出 restore recorded base bytes 的回滚动作。实际文件是 `examdata/src/examdata/cli.py`，且 pyproject.toml 明确声明 `examdata = "examdata.cli:app"`。

风险：按旧映射在根目录新增 cli.py 不会更新已安装 examdata 命令的入口；不存在的文件也不能恢复“原字节”。B01 必须确认最终入口，重新记录正确文件的 SHA256 和语义差异。若确实需要新文件，回滚应只移除本次新增且摘要仍匹配的文件；已有文件的回滚应恢复 B00 的最新释放基线，并避免覆盖后来修改。不得直接恢复 A14 旧快照。

### F02：Phase A 校验工具不能直接作为 Phase B 台账工具

ledger_update.py 在入口限定 `mode == PHASE_A_ISOLATED_ONLY`，并明确拒绝 merged_pass。其 `--validate-only` 分支主要输出任务数/gate 状态，不能独立证明依赖、授权范围或所有证据有效。A15 校验也要求所有 B 任务未启动、所有 gate 关闭。

B00 需要一个新的 Phase B 台账更新/校验器：备份 A 记录、保留 A00–A15 历史、验证人类授权四要素与逐任务路径范围、检查依赖和所有适用 gate、原子写入与回读、拒绝无证据 passed。不能把 Phase A 工具的保护断言删除后复用，也不能开启 B 后仍以 A15 全关检查作为 B 验收。

### F03：路径迁移必须验证模块解析与发布资源

暂存包名是 examdata_integration；拟目标是 examdata.integration。暂存 conftest/guards 会阻止导入 examdata，并把数据与模块限定在 staging。A14 已把这些列为后续要求，但当前隔离测试没有证明迁移后的包可导入。

B01 要在私有副本中完成 import 名称、测试根路径、fixture provenance、配置默认值、Node 组件查找和 contracts/schema 资源路径调整，并证明实际加载的是私有目标文件。不能带着暂存 PYTHONPATH 跑通就宣布最终布局正确。fake-node-cli、synthetic manifest、前端 fixtures/tests 不得进入生产静态或组件目录。wheel/干净安装仍是 B09 的强制项。

### F04：当前依赖链与 gate 要进入机器校验

B00–B10 的台账依赖是串行链，但现有 B 任务 blocked_by 只预置 original_paths_released；不应据此认为其他六个 gate 不需要。PHASE_A_DEFERRED_WORK.md 表格明确要求 B02/B06/B07 的 service-cutover gate、B03/B08 的 real-data-write gate、B05 的 upstream gate等。

下一执行轮先聚焦 B00–B01。按原计划和 gate 表执行；gate 未开时可做已授权的私有准备，不能更改受保护原件、把包标为 merged_pass 或跳过必需依赖。代码可合并、服务可切换、数据可写、联网可请求分别记录，不能互相替代。

## 证据边界

本次没有运行原项目 app/pytest，没有调用 5188/8000 服务、打开 live DB、请求上游、恢复 CIE、修改共享 venv、合并原件或部署。只在 integration-staging/ 与 docs/integration/execution/ 内产生验证输出和本报告。

42/42 自动检查验证了记录一致性和隔离行为，不覆盖实现中所有语义缺陷。原件不干扰证据基于既有记录、指定 base 文件当前摘要和隔离守卫，并非对本轮开始前后全部原件做完整哈希比对；不能独立证明历史整个执行期间每一个原文件都未变化。

数据库单元仍是 not_run；wheel 仍未构建；七条 active-owner 路由仍待释放后的基线重核。合并映射 base drift 为零只说明被记录的文件当时一致，不证明 Kimi 已结束、原件已释放或工作树全部无变化。

## 交付与下一步

下一阶段可复制执行的提示词见同目录 `PHASE_B00_B01_EXECUTOR_PROMPT_2026-10-06.md`。默认保留所有 gate 关闭；有明确人类释放后执行 B00/B01，完成新的基线、路由 worksheet、逐文件调和映射、私有副本验证和台账工具。原件合并与运行服务切换留给后续包，不能自动推进。
