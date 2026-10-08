# TOEFL API 修复计划（repair-20261005）

规格（唯一依据）：`toefl-api/AGENT_FIX_PROMPT_20261005.md`（与用户会话提示词一致）。
问题依据：`toefl-api/AUDIT_REPORT_20261005.md` 与 `toefl-api/audit-20261005/{cache-summary,flow-summary,audio-summary,cleanup-manifest}.json`。

## 环境事实（2026-10-05 侦察）

- 工作区：`C:\Users\weo\Desktop\api`；根目录不是 Git 仓库 → 不依赖 git diff。
- Node：v24.19.0（`/c/Program Files/nodejs/node`）。
- Python：`examdata/.venv/Scripts/python.exe` = 3.14.7。
- 端口 8125 空闲（已查 netstat，无占用）。
- AGENTS.md：工作区根、toefl-api、examdata 下均无 AGENTS.md/CLAUDE.md；适用的是全局 `C:/Users/weo/.agents/AGENTS.md`（Kander 入口）。已按该入口读取 `kander config --json`（rules.code=true）与 `KANDER-BASE-RULES.md`、`KANDER-CODE-RULES.md`；本任务不走 Kander 流程，遵循其通用代码质量要求。

## 目录布局

- `repair-20261005/PLAN.md`：本文件（进度与状态）。
- `repair-20261005/hashes-before.json` / `hashes-after.json`：允许修改文件 + CIE/Edexcel/IELTS 控制模块哈希。
- `repair-20261005/hash_files.py`：哈希记录/对比脚本。
- `repair-20261005/backup/`：将修改的业务文件备份（保持相对路径）。
- `repair-20261005/evidence/`：统计证据（JSON/MD）。
- `repair-20261005/runtime/`：临时测试程序、下载物、私有测试库（最终整体删除）。
- `repair-20261005/REPAIR_REPORT.md`、`evidence-summary.json`、`cleanup-manifest.json`：最终交付。

## 边界

- 允许修改：`toefl-api/lib/*.mjs`、`toefl-api/toefl-cli.mjs`、必要的 `toefl-api/tools`、`examdata/src/examdata/api/toefl.py`、`examdata/docs/TOEFL_API.md`、`toefl-api/REPORT.md`。
- 禁止：CIE/Edexcel/IELTS 实现、既有服务/数据库/绑定/密钥、commit/push、安装依赖、抓登录或付费内容、访问锁定条目。
- 联网：串行、起始间隔 ≥1.1s；任一 403/404/409/502/超时/解析失败 → 存证并停止剩余联网测试（不重试、不换镜像、不加 force）。

## 进度

- [x] 1. 边界与准备：环境侦察、哈希记录、备份、工作区建立。
- [ ] 2. URL 校验与缓存写入修复（P1-01、P1-02）。
- [ ] 3. 听力表格题修复（P1-03，14 个 URL）。
- [ ] 4. 筛选与身份修复（P2-01、P2-02）。
- [ ] 5. 完整复测（离线回归 → HTTP/CLI → 联网样本 → 全量 pytest）。
- [ ] 6. 文档、清理与最终交付。

## 问题清单（来自审计报告）

- P1-01 详情 URL 无主机限制（`lib/jj.mjs:jjHashOf`、`lib/detail.mjs:fetchKmfDetail`、`lib/kmf.mjs:fetchPage/fetchKmfSet`、`lib/util.mjs:httpGet`）。
- P1-02 口写错误页当成功（`lib/jj.mjs:fetchJjDetail` speak/write 分支；先写缓存后验内容）。
- P1-03 14 道听力表格题丢选项与答案且 complete=true（`lib/kmf.mjs` 解析 + `fetchKmfSet.complete`）；代表 `listen/11dwej.html`（答案 B A A B）。
- P2-01 info 暴露 pre/post-2023-07 era 无法筛选（`catalog.eraOf` 只有六个编号分区）。
- P2-02 `normTpo` 宽松匹配（`garbage54`→tpo-54）。
- P2-03 完成汇报超证据（文档层面，第 6 节处理）。

## 记录

- 2026-10-05：完成第 1 节准备；备份与 hashes-before.json 生成；开始阅读 lib 代码。
