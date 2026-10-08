# 按已存定位取题与真实调用验收（2026-10-01）

补充 UNIFIED_WORKFLOW_ACCEPTANCE.md：此前只有 CIE 定位索引读接口，没有按坐标取题接口；本轮已补 `/api/v1/indexes/cie/{qp_sha256}/question?question=...&mode=qp|ms|both&format=binary|json`。

保存的仍是 JSON，不保存分题图片。服务根据 identity 重新拉原 PDF，QP/MS 的 SHA256 必须分别匹配索引，否则 409；缺失对应题号/评分区域 404。匹配后按 1 起页码、未旋转 PDF points 坐标在内存渲染，可多页。JSON 附原件摘要与题号，files 附原页码/bbox；PNG/ZIP 只作为当前响应，不落盘。此实现依赖上游原件仍可获取，没有本地原件缓存读取。

本机服务实际启动在 http://127.0.0.1:8000 ，PID 44024；运行数据目录 `.pytest_cache/callable-api`，数据库为该目录独立 SQLite，不是开发库。导入 CLI 的 EXAMDATA_DATA_DIR 必须设置为与服务相同目录；服务器重启也须保留这一配置。此为本机服务，未暴露公网。

真实上游 HTTP 结果：

| 调用 | 实际结果 |
| --- | --- |
| CIE 9709 / 2024 / Jun / 12 / qp | 200 PDF，251104 bytes |
| Edexcel Economics / 2024 / Jun / wec11-01 / qp | 200 PDF，358629 bytes |
| 同一 Edexcel 卷 / mode=both / index | 200，19 个题号 |
| 同一 Edexcel 卷 / question=1 / both / JSON | 200，QP 页2、MS 页4 |
| 同一 Edexcel 卷 / question=2(a) / both | 422：Question 2(a) could not be located reliably |

索引的 12(d)/12(e) 只有 QP，没有 MS 区域；这些情况不应宣称答案关联齐全。调用方应先读索引实际题号。上述两个下载请求记录在 .pytest_cache/unified-real-upstream.json；这是指定样本证据，不保证所有资格/科目/考季/版式覆盖。

新增回归：CIE 按已导入区域取图、文件目录前后完全一致（无图片持久化）、原件改变拒绝旧坐标、没有 MS 不生成答案；HTTP JSON/二进制及缺失 MS 的 404。源码全套 768 passed / 4 skipped，日志 .pytest_cache/unified-index-retrieval-full.log；最新 wheel 全套记录于 .pytest_cache/index-retrieval-wheel-full.log。

提示词已补充最终取题复核步骤；它要求外部 AI 保存原件身份及每道题的 QP/MS 页码和矩形，不将截图作为持久化解析结果。未执行真实 CIE AI 识别任务；合成索引能证明请求链路，不能证明 AI 识别准确率。reviewed=false，正式独立审核仍未完成。
