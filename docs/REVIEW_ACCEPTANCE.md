# 审查修复与最终验收记录（2026-09-30）

本批三项优先修复和正常/空库/installed-wheel 验收已执行；**这不是全仓审查全部完成声明**。
在 main 的现有未提交工作树继续；未 reset、stash、commit 或 push。交接原记录保留在 AGENT_HANDOFF.md。

## 本批结果

| 项目 | 实际处理与证据 |
| --- | --- |
| Formula 外键两项失败 | 在 question 删除前处理 Formula；自动来源可清理，人工来源保留并严格恢复。keep_history True/False 的两项 scoped reparse 回归现已通过，未关闭外键。 |
| unchanged 覆盖解析状态 | SHA256 unchanged 分支返回前不再写 stored；只有新增 revision 才写。SHA256 和 304 对 ok/needs_review 四个回归通过。 |
| 重解析人工/审核/官方保护 | 保存并恢复 GeneratedExplanation（包括 pending/approved/rejected）、OfficialAnswer、manual/reviewed taxonomy、非 estimated difficulty 和人工 Formula；保留原记录 ID、内容与审核引用。自然键必须唯一且正文一致，否则整批保存点回滚、旧结果保留。14 个成功/正文变化回滚合成用例通过。 |
| 人工字段覆盖 | 暂停并隔离本批 override 的旧整数主键，防止 SQLite 主键复用误应用；含 inactive 历史和 Paper 的重新挂接。使用解析轮次版本与 source_value 基线，不再无条件覆盖或清冲突；同题多字段只应用一次。目标缺失/歧义回滚并写冲突 ReviewTask。范围外 active/inactive override 保持全部字段不变。 |
| 评分关联身份 | 按资格、科目、考试系列、年份、component/variant/level、paper 与 specimen 类型族精确匹配；要求唯一且 Paper 解析轮次对应当前 revision。原评分关联无法恢复则回滚。QP-only 通过受保护答案恢复避免 official[] 丢失。 |
| reset | 仅 SQLite；默认拒绝、dry-run 计数。即使 --yes，也拒绝官方答案、人工/审核数据、审核处置和所有 overrides（含撤销历史）。文件 SQLite 全表快照回归证明拒绝前后数据完全相同。 |
| 其他最后改动 | 中断后的 C/G/I 等最终改动均随全套复测；补 registry 加载失败/部分注册回滚测试，删除 Edexcel 无消费者 load_errors。robots 改为有界流式读取，超限拒绝资源。CLI 增加范围下限与 --retry-failed；更新审核保护、reset、完整抽题池和离线测试说明。 |
| SQLite 初始化 | schema 反射与列迁移共用同一事务连接，避免内存 SQLite 初始化嵌套 BEGIN；测试临时存储使用 MEMORY，避免 Windows 临时目录权限阻断保存点。 |

## 最终版本验收

所有下列结果来自本轮最终源码或最终 wheel，未引用旧 438 项通过记录。

| 场景 | 结果 | 原始日志 |
| --- | --- | --- |
| 源码：正常私有语料全套 | 721 passed / 4 skipped / 0 failed；34.09 s | ../.pytest_cache/accept-normal.log |
| installed wheel：正常私有语料全套 | 721 passed / 4 skipped / 0 failed；36.41 s | ../.pytest_cache/accept-corpus-wheel-final.log |
| installed wheel：无源数据库 | 664 passed / 61 skipped / 0 failed；22.01 s | ../.pytest_cache/accept-missing-wheel-final.log |
| installed wheel：源库文件存在但未建表 | 664 passed / 61 skipped / 0 failed；20.93 s | ../.pytest_cache/accept-uninitialized-wheel-final.log |
| installed wheel：空 document 表 | 664 passed / 61 skipped / 0 failed；22.30 s | ../.pytest_cache/accept-empty-wheel-final.log |
| installed wheel：有 document、无 parsed question | 664 passed / 61 skipped / 0 failed；22.00 s | ../.pytest_cache/accept-unparsed-wheel-final.log |
| PEP517 wheel 构建与 target 安装 | 成功；188442 bytes；py.typed 存在 | ../.pytest_cache/accept-build-final.log |
| installed wheel CLI 与实际本地 HTTP | initdb、search-questions、search-papers；health、查询/分页、422、asset bytes、PDF binary/JSON/base64/ZIP、403/409/502 全通过；服务已退出 | ../.pytest_cache/accept-wheel-http-final.log |
| compileall / git diff --check | 均退出 0；diff 只有 Git LF/CRLF 提示 | ../.pytest_cache/accept-diff-check.log |

wheel SHA256：`91f4c375f666d2d8fbd4e86ad5c6bb537503800950c277c06f50cca64cf8c1ce`。
文件：`.pytest_cache/accept-wheel-final/examdata-0.1.0-py3-none-any.whl`。
安装验收明确断言 `examdata.__file__` 来自 `.pytest_cache/accept-installed-final`；运行目录为私有副本，使用 `python -I` 后显式将 installed target 放在导入路径首位。
HTTP 验收走真实 localhost socket；上游使用离线回放，**不是 Pearson/Cambridge live 采集验收**。

正常场景 4 skips：3 个明确 live 上游用例；1 个 Windows symlink 创建权限不足（WinError 1314）。
空库另有 57 个语料/分类依赖跳过，总计 61；合成回归与真实 PDF probe 仍执行。
每套有同一个 Starlette/httpx 弃用 warning；没有为通过测试放开 live 开关或放宽业务断言。

## 未完成与边界

1. 官方答案来源文档（MS 等）重解析目前保守拒绝，避免将旧官方内容错误视作新来源结果；尚未完成来源更新、答案再生及审核内容迁移的闭环。受保护题目正文变化/改号/歧义会回滚，不能声称支持自动迁移所有人工内容。
2. 相似题仍为 `deferred`，没有按 document 安全范围重建；taxonomy 缺种子初始化和 MS-only 依赖题智能层重建仍未完成。
3. 独立 parse pipeline 失败 ParseRun 完整审计未完成；保存点回滚不撤销已写文件产物，失败时可能留下无数据库引用的内容寻址文件。PostgreSQL 未验证。
4. content_classify/pdfdoc 的前两页分类、避免重复整本读取、资产诊断与历史 finding 生命周期等交接项未全面处理；本批仅让已 resolved/ignored 的 finding 不再维持 blocking 状态。
5. 单响应/解码阶段及 robots 有界，不等于请求总体预算或进程内存保证；多 PDF/PNG/ZIP/base64 aggregate budget 尚未完成，跨主机 redirect 专项仍需补证。
6. Edexcel 达到发现上限是 fail-closed，不代表穷尽 Pearson 全量；Cambridge 发现失败链路的静默空响应审查仍未闭环。
7. Windows 真实 symlink 用例需有创建权限环境补测；其他平台路径语义、真实上游与 PostgreSQL 未验证。
8. 未执行 Kander 的独立 PM/QA/CSA/Hacker commit 审核：工具要求干净且已提交的审核目标，本工作树未获提交授权。不能标正式审核 PASS，也未为了审核擅自提交。
9. 本记录按交接范围核验，尚未把最初全仓发现全部逐条判定已修/不成立/证据不足；不能以测试全绿代替全仓审计闭环。

## 数据与收尾

开发库只作只读备份/核验，未用作任何测试写入目标：4182016 bytes，SHA256
`d0f59c2a6ab918c8dbd0f6aafba1a4da538687d7606b30830004d074080a6c3f`，与交接基线一致。
只读计数：document=79、question=751、paper=16、parse_run=239。

`examples/browser.html`：SHA256
`fad2bca3920ecf13801c68770f398c571edf84c473b395d741a2b5a888a156b5`，与交接基线一致；保留用户原修改。
没有提交或推送。保留验收 wheel、日志及私有测试库/安装目标/副本；临时 HTTP 服务已退出。自动审批审查拒绝清理私有目录（返回 blocked by policy），所以没有声称目录已清理。pytest 管理的临时 fixture 按其保留策略留存；其他历史目录及归属未确认进程未动。
