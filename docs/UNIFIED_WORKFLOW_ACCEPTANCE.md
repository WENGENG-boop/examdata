# 统一取卷与外部 CIE 索引验收（2026-10-01）

用户目标：统一 API 拉取 CIE/Edexcel 试卷；第一步 CIE 只整卷，Edexcel 算法分题与评分标准；第二步给外部 AI 提示词，识别 CIE 题号并保存原 PDF 定位。本次采用 JSON + 本地校验导入，API 提供只读查询，不开放匿名写入。

实现和例子见 UNIFIED_PAPER_API.md。提示词见 CIE_AI_PARSE_PROMPT.md，JSON Schema 同时提供仓库文件与 `/api/v1/cie-index-schema`。已有旧模式兼容；新公共模式 qp/ms/both。Edexcel 整卷索引防止把多个卷号变体混在同一题号下。

| 验收 | 当前最终结果 | 日志 |
| --- | --- | --- |
| 源码正常语料全套 | 765 passed / 4 skipped / 0 failed | .pytest_cache/unified-step1-full.log |
| installed-wheel 正常语料全套 | 765 passed / 4 skipped / 0 failed | .pytest_cache/unified-step1-wheel-full.log |
| installed-wheel 无源库全套 | 708 passed / 61 skipped / 0 failed | .pytest_cache/unified-step1-wheel-empty.log |

新增 23 项回归覆盖：两考试局共同模式、Edexcel 单题 QP/MS 裁剪、整卷索引/变体拒绝、CIE 导入幂等与不同结果拒绝覆盖、错误哈希/页码/坐标/NaN/重复题号/父子关系/评分文件/伪造审核字段拒绝、CLI 导入、HTTP 索引和定位查询、CIE 自动 index 拒绝。所有写入使用测试私有目录，未写开发库。

本轮起始的两项旧断言仍规定 Edexcel 不允许 both、能力列表只有旧模式；按新功能契约调整，并增加共享模式正向回归。一次新增假数据误用 Jun，但 fake 的 MS 仅提供 Mar，产生两项 NotFound；修正测试考季后重新完整验收，未关闭校验。

wheel SHA256：`229d5bb2ac8e0db501962fb28b9149f61e6b9d4f32057cee05eb86e095015840`，位于 .pytest_cache/unified-step1-wheel；用 python -I 从 unified-step1-installed 导入运行测试。

4 skip 为 3 项真实上游及 1 项 Windows symlink 权限；无源库另有 57 项依赖语料跳过。HTTP 为 TestClient/离线回放，没有本轮公网部署或实际 AI 识别准确率验收；不以此前 PostgreSQL 41 项代表本轮新接口已在 PostgreSQL 验证（新增索引采用独立 JSON 存储，不写 DB）。正式独立审核仍待隔离副本 commit 授权。

明确边界：Edexcel 算法不保证所有版式/扫描件；评分标准区域原样返回，不生成官方解答。CIE 导入可证明原件摘要、层级和区域有效，不能证明语义识别正确；结果 reviewed=false，没有接入旧 Question/知识点/人工审核数据库。原件需操作者自行保留。已有开发数据库和 browser.html 内容哈希保持不变；工作树未重置、未提交、未推送。
