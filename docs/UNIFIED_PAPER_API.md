# 两步统一试卷 API

第一步：两家统一 `GET /api/v1/paper`，共同参数 board、subject、year、season、paper、mode、format。mode 使用 qp（试卷）、ms（评分标准）、both（两份）；format=json 返回逐文件 base64/摘要，默认单份 PDF 或多份 ZIP。download=false 仅返回清单。

```
/api/v1/paper?board=cie&subject=9709&year=2026&season=Mar&paper=12&mode=both&format=json
/api/v1/paper?board=edexcel&subject=Economics&year=2024&season=Jun&paper=wec11-01&mode=both&format=json
```

Edexcel 加 `question=2(a)` 时按算法分别裁剪试卷和评分标准，返回 PNG 或 ZIP/JSON：

```
/api/v1/paper?board=edexcel&subject=Economics&year=2024&season=Jun&paper=wec11-01&mode=both&question=2(a)&format=json
/api/v1/paper/index?board=edexcel&subject=Economics&year=2024&season=Jun&paper=wec11-01&mode=both
```

整卷 index 返回检测到的题号层级、QP/MS 区域（1 起页码、未旋转 PDF 左上原点 points）和原件 SHA256。某题只有 QP 或 MS 时另一侧为空；算法结果 reviewed=false。扫描件、无可靠编号或不支持版式明确 422，不伪造定位。裁剪的是原始评分标准，不是自动生成答案。范围主要沿用现有 Pearson IAL 来源，不能宣称覆盖所有 Edexcel 资格。

CIE 第一阶段不走自动定位：带 question 参数或者请求算法 index 返回 422；整份 PDF 获取保持可用。历史 paper/question/qa 模式继续兼容。

第二步：把 [全学科完整执行提示词](CIE_ALL_SUBJECTS_EXECUTION_PROMPT.md) 和 [JSON Schema](schemas/cie-question-index.schema.json) 交给另一个 AI。操作者通过 `examdata import-cie-index ... --qp ... --ms ...` 本地导入 JSON；核对原件摘要、题号唯一性、父子层级、页码和 bbox。存储在配置 data_dir/question_indexes/cie/{qp_sha256}.json，接口 `/api/v1/indexes/cie/{sha256}?question=...` 只读检索。

相同索引重复导入幂等，不同索引拒绝覆盖。JSON 文件是独立的外部定位存储，尚未接入旧 `/questions` 数据库检索/知识点/人工审核系统；reviewed 永远为 false。原始 PDF 仍需操作者保留，本索引不会另复制原件。无匿名写入接口。

按位置直接取题：`GET /api/v1/indexes/cie/{qp_sha256}/question?question=1(a)&mode=both&format=json`。mode 为 qp/ms/both。服务器根据索引内 identity 拉取原 PDF，核对每份原件 SHA256，再按该题各页 bbox 在内存渲染，返回 PNG（跨页/两份为 ZIP 或 JSON 文件数组）；不会把每道题图片写入存储。JSON 附 question、index_sha256、source_documents、reviewed、uncertain，files 附 page/bbox/图片摘要/base64。原 PDF 内容变化返回 409，缺失题号或 MS 区域返回 404，不使用旧定位或生成答案。

持久化的是试卷身份（考试局/科目/年份/考季/卷号）、QP/MS 原件摘要、每题层级及每份 PDF 的页码/bbox；不是图片。题干文字和分值可随 AI 索引提供。原 PDF 可另行保留，但当前取题接口会重新拉取并校验，尚无离线原件缓存读取路径。

现有服务鉴权/CORS配置继续适用，服务部署和真实上游可用性需另外验收；本地测试不代表公网已上线。
