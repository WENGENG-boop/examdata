# 剩余审查修复实际结果（2026-09-30）

范围：[执行计划](REMAINING_WORK_PLAN.md)。本记录对应现有未提交工作树；未提交、未推送、未重置。正式独立审核尚未完成，不能据测试结果宣布完整审查已闭环。

## 实现结果

1. 官方来源迁移：支持 mark_scheme 来源的 MS-only 和 QP+MS 重解析。按唯一自然键核对原关联，缺失或歧义整批回滚；覆盖重新应用后重建目标来源官方答案。保留人工、approved/rejected 解析及审核引用；官方正文变化产生 official_source_changed 复核任务，API requires_review 为真，重新人工审核后关闭任务。没有对应解析器的其他官方来源类型继续拒绝迁移。
2. 相似题：按目标题目范围替换自动 TF-IDF 关系，保留范围外关系及人工/其他方法关系；禁止跨 board/qualification/subject 比较；空范围不扩为全库，短文本不足也会清理范围内陈旧自动关系。MS-only 刷新关联 QP 的智能数据；仅同步相关学科种子，保留人工/官方 taxonomy。
3. 失败审计与文件回滚：失败解析和批次回滚留下 failed ParseRun 上下文、时间和错误；新增文件采用原子发布，外层事务结束时只清理本轮新建且无 Asset/Artifact 引用的对象。SQLite 使用写锁，PostgreSQL 使用事务 advisory lock；预存文件保留。正常事务回滚已验收；进程崩溃时 DB/文件系统跨介质原子性没有保证，清理错误会记录而非伪报数据库回滚。CLI 普通及 --json 输出遇到 aborted 均退出 1。
4. 总体预算：单请求累计上游响应、PDF、裁剪栅格估算、PNG、ZIP 和 base64 分配预算 256 MiB；最多 64 文档、256 输出文件。分配前检查可预测的大额输出，超限返回 502。预算表示累计工作与输出字节，不能当作进程 RSS 的硬上限。redirect 逐跳重新检查 robots/限速，跨主机授权头不泄漏，终止重定向不重试。
5. PostgreSQL：使用 PostgreSQL 16.15 私有 cluster，localhost:55439，新建专用数据库；每个核心测试独立 UUID schema。发现并修复 SQLite 接受但 PostgreSQL 拒绝的 JOIN 前向引用。源码及 installed-wheel 核心回归各 41 通过；wheel CLI 和本地真实 HTTP 均通过。临时实例已停止，没有测试写入开发数据库或现有 PostgreSQL 服务。
6. 正式独立审核：待授权隔离审核副本的本地快照提交。Kander 基础规则要求干净 Git worktree 和 commit 目标；用户禁止擅自提交，故未启动正式审核，也没有 PASS 结论。复测结果见下表。

## 最终冻结代码验收

| 场景 | 实际结果 | 日志 |
| --- | --- | --- |
| 源码正常语料 | 742 passed / 4 skipped / 0 failed | .pytest_cache/remaining-normal-final.log |
| installed-wheel 正常语料 | 742 passed / 4 skipped / 0 failed | .pytest_cache/remaining-wheel-corpus.log |
| installed-wheel 无源库 | 685 passed / 61 skipped / 0 failed | .pytest_cache/remaining-wheel-missing.log |
| installed-wheel 未建表 | 685 passed / 61 skipped / 0 failed | .pytest_cache/remaining-wheel-uninitialized.log |
| installed-wheel 空 schema | 685 passed / 61 skipped / 0 failed | .pytest_cache/remaining-wheel-empty.log |
| installed-wheel 有文档但未解析 | 685 passed / 61 skipped / 0 failed | .pytest_cache/remaining-wheel-unparsed.log |
| PostgreSQL 核心回归（源码） | 41 passed | .pytest_cache/remaining-postgres-final.log |
| PostgreSQL 核心回归（wheel） | 41 passed | .pytest_cache/remaining-wheel-postgres-tests.log |
| wheel SQLite CLI/真实本地 HTTP | PASS | .pytest_cache/remaining-wheel-http.log |
| wheel PostgreSQL CLI/真实本地 HTTP | PASS | .pytest_cache/remaining-wheel-postgres-http.log |

HTTP 验收包含 initdb/search、health、查询参数 422、资源字节、PDF/JSON base64/ZIP，以及 403/409/502 和累计预算超限。上游使用离线回放，不能视作真实网站验收。正常语料来自开发 SQLite 的只读 backup 和原件副本。

4 项 skip 是 3 项显式真实上游测试及 Windows 无 symlink 权限的 1 项；空库额外 57 项依赖语料跳过。没有执行完整 PostgreSQL 语料全套，仅核心迁移/回滚 41 项及 CLI/HTTP。存在 Starlette/httpx 弃用警告。

最终 wheel：.pytest_cache/remaining-wheel/examdata-0.1.0-py3-none-any.whl；SHA256 `0a53c921690b4a2e3f17622dc2eedc9131620f7227df58be0ceb881432f209f1`。隔离安装后用 python -I 验证 import 指向 remaining-installed，包含 py.typed。

最后补 JSON 退出码后，第一次 no-build-isolation 构建因缺少 setuptools 失败，初轮旧 wheel 导致新增用例失败；该轮不是最终验收。已改用标准隔离构建，并对新 wheel 重新验收，不用失败轮或旧通过数替代最终结果。

保护检查：examples/browser.html SHA256 `fad2bca3920ecf13801c68770f398c571edf84c473b395d741a2b5a888a156b5`；开发库 .data/examdata.db SHA256 `d0f59c2a6ab918c8dbd0f6aafba1a4da538687d7606b30830004d074080a6c3f`，均与接任基线一致。git diff --check 通过。私有日志/测试数据仍保留；此前自动审批拒绝目录清理，未绕过。

尚需：正式独立审核及其反馈修复；若要求完整 PostgreSQL 语料全套、真实上游和 symlink 路径验收，需要另补这些证据。历史 REVIEW_ACCEPTANCE.md 保留作前批结果，勿混用。
