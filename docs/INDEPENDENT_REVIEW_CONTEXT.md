# 独立审核上下文

目标：审查现有未提交修复，尤其官方来源重解析迁移、人工与审核数据保护、范围相似题、失败审计与文件回滚、请求累计预算和 PostgreSQL 可移植性。

基线 HEAD：d8e64a690b4e8f1b7cb8dac32d6fc2325252d80e。包含此前未提交修复；用户已有 examples/browser.html 改动必须保留，不属于本次修复。

用户决定：原工作树继续，不 reset/stash/checkout，不写开发库、不擅自 commit/push。官方答案变化不能无声覆盖审核状态；不能用历史或局部通过数宣布全库完成。

审核验收关注：跨 QP/MS 唯一映射及失败原子性，approved/rejected/pending/manual 数据与 ID 引用，撤销 override 历史，范围外相似关系，PostgreSQL 保存点与 JOIN/锁，新增/共享文件的回滚竞争，跨主机重定向与累计分配边界；API requires_review 与 CLI 退出码必须反映真实状态。

实现与测试证据见 REMAINING_WORK_RESULTS.md。41 项 PostgreSQL 核心回归及 wheel CLI/HTTP 不等于完整 PostgreSQL 全套；HTTP 上游为离线回放。预算不是 RSS 硬限制，跨介质崩溃原子性未实现；其他无解析器的官方来源受保守拒绝保护。正式审核尚未启动，不存在独立 PASS。

Kander 要求干净 commit 目标；需用户允许隔离副本的本地快照提交后才能执行。原工作树/分支保留，不推送。审核员应独立检查，不以此文结论替代审查。
