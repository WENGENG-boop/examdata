# 实现现状：解析、治理与智能层

> 状态：与代码同步（最近一次全量验证：340 项测试通过；Cambridge 35 份文档解析成功，Edexcel 已接入）。
> 本仓库不收录真实试卷，缺少 `tests/fixtures/` 样本时其中 28 项会自动 skip（见 README「测试」）。
> 本文档记录**已实现并能验证**的能力，以及明确尚未实现的部分。
> Phase 0 的站点结构证据见 `cambridge.md`；本文档只讲系统本身。

## 1. 可验证的当前状态

全量解析 35 份 Cambridge 文档（0580 / 9709 / 0620 / 0478）；Edexcel 侧已同步 44 份文档
（`accounting-2023-modular` 试同步，其中仅 1 份公开可下载）。下表数字取自
`scripts/verify_state.py` 的实际输出（含 Edexcel 已登记但未下载的登录墙文档）：

| 项 | 值 |
|---|---|
| 文档 / 版本 / 原件 | 79 / 37 / 37 |
| 试卷 | 16 |
| 题目 | 751 |
| 评分条目 / 已关联 | 580 / 558 |
| 图形资产 | 204 |
| 文件类型判定（含内容级） | 79 |
| 知识点标注 | 1344 条（未标注 207 题） |
| 难度估计 | 751 / 751 |
| 相似题对 | 109（参与 649 题，过短跳过 102） |
| 生成解析 | 508 条，全部 pending |
| 溯源覆盖率 | 100%（题目/评分条目/资产/答案/试卷） |
| 校验发现（error / warning） | 154 / 168 |
| 待检查队列 | 21（`examdata monitor`） |

复现方式：

```powershell
$env:PYTHONIOENCODING='utf-8'
cd <项目目录>
.venv\Scripts\python.exe scripts\reset_derived.py
.venv\Scripts\python.exe -m examdata.cli parse-docs
.venv\Scripts\python.exe -m examdata.cli classify-content --apply
.venv\Scripts\python.exe -m examdata.cli enrich          # 知识点/难度/相似题/生成解析
.venv\Scripts\python.exe -m examdata.cli provenance-rebuild
.venv\Scripts\python.exe scripts\verify_state.py   # 交付前自检
.venv\Scripts\python.exe -m pytest
```

## 2. 文件类型识别：三类信号

需求要求"不能只依赖文件名，还需要结合官方页面信息、文件本身信息以及文档内容"。

| 信号 | 实现位置 | 作用 |
|---|---|---|
| 页面锚文本 | `adapters/cambridge/classify.py` | 主判定 |
| URL slug | 同上 | 交叉校验，不一致则降置信度 |
| **PDF 内容** | `parsing/content_classify.py` | 独立判定 + 与页面判定对账 |

融合规则（`reconcile`）刻意保守：

- 一致 → 高置信度；
- 标签是内容的**具体化**（`specimen_paper` 之于 `question_paper`）→ 采纳更具体的标签，不算冲突；
- **真冲突 → 不自动裁决**：保留页面判定，置信度压到 0.35，并由解析流水线写 `doc_type_content_conflict`（error 级）进待检查队列。

实测：35 份文档全部一致，零误报。

## 3. 人工修正与重新解析（治理层）

### 人工修正

- `governance/override.py`，CLI：`override-set` / `override-list` / `review-list` / `review-resolve`。
- **字段白名单**（`OVERRIDABLE`）而非任意字段可写：解析产物之间有结构约束（如 `depth` 与 `parent_id` 必须自洽），放开任意字段会让数据进入校验规则抓不到的自相矛盾状态。
- 修正必须记录 `author`；撤销不删行（保留审计链），恢复被覆盖的自动值。
- 基线保留：同一字段重复修正时，`source_value` 仍是最初的自动值。

### 重新解析

`governance/reparse.py`，CLI：`reparse`。只读本地内容寻址存储，**不重新下载**。

三个真实踩过的坑，均已修复并有回归测试：

1. **人工修正会丢**：修正挂在题目主键上，重解析重建题目行后主键变化。
   解法：按自然键 `(document_id, number_path)` 重映射。注意自然键**不能**用 `paper_id`——Paper 行本身也会被重建。
   映射不上时报冲突并进待检查，**保留人工值**，绝不静默丢弃。
2. **派生数据静默缺失**：清理派生数据后不重建，重解析过的文档会缺少知识点/难度/相似题（解析统计却显示"成功"）。
   解法：重解析后按依赖顺序重建（知识点 → 难度 → 相似题）。
3. **评分条目关联永久丢失**：清题目时因外键必须断开 `MarkSchemeEntry.question_id`，而 Mark Scheme 文档通常不在重解析范围内，不会自己恢复。
   解法：重解析后主动重新关联未挂接的条目。

### 新旧对比

`diff()` 只把"变差"标为回归（题数骤降、分值对不上、重复题号、关联归零），改善和中性变化只记录。
不比较具体题号字符串——算法升级时题号本来就会变，把"变了"当错误报会淹没真正的回归。

## 4. 溯源

`governance/provenance.py`，CLI：`provenance-rebuild` / `provenance-trace`。

**设计取舍：溯源做成投影，不另写一遍。**
题目 → `parse_run` → `document_revision` →（`source_url`, artifact sha256, document）
这条链在解析时已完整落库；再手写一份来源只会多出一份可能不一致的副本。

- 幂等：删空重跑结果完全一致（有测试）。
- 覆盖率按**去重主体**计数，不按边数（一个资产可被多题引用，按边数会算出 >100%）。

## 5. 智能层

全部确定性、可复现，不依赖外部模型服务。

| 能力 | 模块 | 方法标识 |
|---|---|---|
| 知识点分类 | `intelligence/taxonomy.py` | `keyword-v1`，置信度 = 0.65×绝对分 + 0.35×相对分 |
| 难度估计 | `intelligence/difficulty.py` | `heuristic-v1`，分值/长度/子题数/层级/图形/知识点加权 |
| 相似题 | `intelligence/similarity.py` | `tfidf-ngram-v1`，字符 3-gram 余弦，阈值 0.62 |

- 官方难度与系统估计难度**分表分源**存储（`source` 字段），官方值永不被覆盖。
- 相似题排除同卷祖先/同根题对（`_is_ancestor_pair`），否则 `3` 与 `3(b)` 会被判为"相似"。
- 知识点种子为**两层**（topic / subtopic），只覆盖 4 个已同步科目，不虚构更细层级。

### 生成解析（`intelligence/explanation.py`）

**必须说清楚它是什么：** 本机没有可用的模型服务，所以这里是**从官方 Mark Scheme 派生的规则式脚手架**，
不是真正的数学推理。它把官方给出的评分点、分值分配、ECF 提示重新组织成学生可读的结构。

因此如实标注：`provider="rule-based"`、`model=None`（没有模型参与就不编一个模型名）、
`is_official=False`、`review_status="pending"`（默认不可信，需人工审核）。
只在**有官方依据**（评分条目或官方答案）时生成——没有依据就返回 None，不造空壳。

隔离性有测试保证：生成器无论怎么跑都不能写出 `is_official=True` 的行，也不能改动官方答案。

## 6. 检索与 API

`api/app.py`，20 条业务路由，只读（不计 OpenAPI/docs）：

`/health`、`/papers`、`/questions`、`/questions/{id}`、`/questions/{id}/similar`、
`/questions/{id}/provenance`、`/questions/{id}/explanation`、`/taxonomy`、`/papers/{id}/tree`、
`/sample`、`/monitor`、`/review`、`/overrides`、`/classifications`、`/provenance/coverage`、
`/explanations/review-queue`、`/assets/{id}`、`/assets/{id}/provenance`、
`GET /paper-qa/resolve`（仅文档元数据）、`GET /paper-qa/query`（内存 PDF/PNG/ZIP）。

### PaperQA（2026-09-29）

独立 `examdata.paperqa` 模块，不注册 BoardAdapter，不依赖数据库，不添加 OCR 依赖。
`query(board, subject, year, season, paper=None, question=None, mode=None, out_dir=None)` 返回
`Result(request, documents, files)`；每个文件（`OutputFile`）带
`name / data(bytes) / media_type / role`，裁剪产物另带 `page`（1 起）/
`bbox`（PDF 用户坐标 `(x0,y0,x1,y1)`）/ `sha256`（由 `data` 派生，构造时算好）。
默认不落盘；显式 `out_dir` 或 CLI `--out` 才保存，已有文件不覆盖。

- CIE：`qp/ms/both`，`qp+ms` 等价 `both`；仅整份 PDF，传 question 直接拒绝。
  来源 `cie.fraft.cn` 的 POST renum + redir 文件接口，不解析其损坏文本。
  subject 为四位代码；season 为 Mar/Jun/Nov，Jan 不映射成 Mar。
- Edexcel：`paper` 为 QP PDF，`question` 为题目 PNG，`qa` 为题目与 MS PNG；
  后两者必须给 paper/question。subject 接受英文名称及 `ial18-economics` 这类 IAL 标签；
  paper 使用 `wec11-01` 或 `wec11`（跨卷歧义报错）。Winter 明确表示 January。
  题号接受 `12`、`12(a)`、`12(a)(ii)` 与短写 `12a`/`12ai`（短写在校验处补成全写，语义完全一致）。
- Pearson 共用 `adapters/edexcel/servlet.py`，科目标签与规格标签 OR，返回上限 1000。
  撞上限按考季/文档类型递归分片；切到深度上限仍饱和或无维度可切时立即失败，
  绝不返回可能被截断的清单。分片维度取自被截断响应出现过的 facet，能降低但
  无法证明穷尽——这一点如实记在模块 docstring 里，不谎报全量。
  下载只允许固定 Pearson 主机的 `/content/dam/pdf/`，拒绝 secure/gold/silver、路径穿越、
  百分号编码、查询参数及重定向；验证 `%PDF-` 与 PyMuPDF 可打开性。
- HTTP 无 out/url 参数；参数错误或定位失败 422、缺失 404、歧义 409、受限 403、上游错误 502。
  单文件直接返回原字节，多文件内存 ZIP，不创建服务器文件。二进制响应带
  `Content-Disposition`（含文件名）与 `Content-Length`，客户端可直接落盘。
- **统一 schema**：所有出口共用 `Result.metadata()`，字段集完全一致——
  顶层 `schema_version`（当前 `"1"`，不兼容变更时递增）/ `request` /
  `counts{documents,files,bytes}` / `documents[]` / `files[]`；每个 file 有
  `name/media_type/role/size/sha256/page/bbox/data_base64`。`data_base64` 键恒存在，
  未内联时为 `null`——CLI `--json` 与 `/paper-qa/resolve` 就是这种，
  因此 CLI 与 HTTP 的字段名、层级、类型逐一对得上，调用方不必写两套解析。
- `/paper-qa/query` 支持 `format=binary|json`（默认 binary）；`format=json` 走
  `json_payload()`，与 `/paper-qa/resolve`、CLI `--json` 同 schema，但 `data_base64`
  内联载荷，供处理不了二进制的客户端使用。非法 format 值 422。

```python
from examdata.paperqa import query
result = query('cie', '9709', 2026, 'Mar', paper='12', mode='both')
result = query('edexcel', 'Economics', 2024, 'Jun', paper='wec11-01', question='12(a)', mode='qa')
print(result.metadata()["counts"], result.files[0].sha256[:12], result.files[0].bbox)
```

```bash
examdata paper-qa --board cie --subject 9709 --year 2026 --season Mar --paper 12 --mode both --out tmpwork/cie --json
examdata paper-qa --board edexcel --subject Economics --year 2024 --season Jun --paper wec11-01 --question '12(a)' --mode qa --out tmpwork/edexcel --json
```

定位使用 PyMuPDF 的左栏编号、主号单调序列与子号层级；重复主号不截断整题，
有后续重复题干的子题摘要被排除；末题在 TOTAL FOR PAPER/Acknowledgements 前结束。
识别到嵌入式 Source Booklet 且题干引用 Extract/Figure 时，附带其正文页（不含致谢）。

裁剪框在原有边界上又叠了三层收敛（2026-09-29 精准化）：

1. **总分行终点**：QP 每题印的 `(Total for Question N = X marks)` 取为精确终点，
   与"下一个同级锚点"取靠前者——整题收在总分行，子题收在自己或父题的总分行。
2. **内容包围盒**：每页裁剪框收紧到该题实际内容的包围盒（word bbox ∪
   **drawing bbox**，图无文字必须计入）外扩 5pt，不再用整页宽的固定窗口。
3. **版式噪声剔除**：逐项识别页边竖排水印 `DO NOT WRITE IN THIS AREA`、
   页脚条码（每页都变，按正则族而非整串）、试卷代码、页码、`Turn over`、
   `©…Pearson`、装饰用私有区字形、整页外框；页顶 `SECTION A/B/C` 横幅要求
   同行右侧跟单字母区号才排除，避免误伤正文的 `TOTAL FOR SECTION A = …`。
   续页因此从真正的第一行内容起步，不带页眉带或页脚带。

实测同一份真题（2024 June wec11）：QP 第 4 题 703→517pt、MS 12(a) 618→154pt、
QP 12(a) 703→206pt、QP 14 从 6 页收敛到 1 页，新增裁剪无页眉/页脚/水印噪声。

版式常量（`_MARGIN_X`/`_HEADER_Y`/`_FOOTER_Y`/`_BANNER_Y`/`_FRAME`）按 Edexcel 实测的
A4(QP)/Letter(MS) 标定，换考试局或纸张比例差异大时需重新标定。这是布局启发式，
并非所有科目/年份的准确性保证；扫描 PDF、无法识别编号或无匹配题号明确失败。
未对所有资格类别做端到端验证，外置材料和未识别的材料布局仍需人工核对。

**写入类操作刻意不开放 HTTP**：人工修正与重新解析走 CLI 与后台任务，
避免"生成内容与官方内容物理隔离"这条约束被匿名写接口绕过。

## 7. 多考试局扩展性

`adapters/` 的契约：新增考试局 = 实现 `BoardAdapter` + 在 registry 注册 + 通过 `tests/conformance`。
核心系统无需改动。

`tests/conformance/test_adapter_contract.py` **参数化遍历 registry**——每注册一个新适配器，
全套契约检查自动对它生效。这一点很关键：如果一致性套件需要为新考试局手写测试，
"新增考试局不需要改核心"就变成了"新增考试局需要改测试"。

`registry` 也改成**自动发现** `adapters/` 下的子包。之前是硬编码 import cambridge，
那样每加一个考试局都要回来改注册表——而注册表本身也是核心。

套件自身也有守卫：`test_suite_rejects_a_broken_adapter` 断言那些检查项确实能拦住不合格的适配器。

**已实证**：新增 Edexcel 适配器时，核心系统（sync / parse / query / api）**一行未改**，
CLI 的 `sync --adapter edexcel` 直接可用。

### 两个适配器的实现差异（证明抽象没漏）

| | Cambridge | Edexcel |
|---|---|---|
| 页面 | 服务端渲染，PDF 在 HTML 锚点里 | AngularJS 空壳，锚点数为 0 |
| 发现机制 | 正则抽锚点 | 站内 Algolia JSON servlet |
| 元数据 | 需从锚文本解析 | category 数组直接结构化 |
| 结果上限 | 无 | hitsPerPage 硬上限 1000；饱和先按考季/文档类型递归分片，切不动才报错 |
| 门禁 | 零星 PDF 被 robots 禁 | 整类路径 `/content/dam/secure/**` 被禁 |
| accessibility | public | partial_public |

一致性套件最初假设了"从落地页 HTML 发现"——那是 Cambridge 的形状。
Edexcel 接入后立刻把它暴露出来，套件已改为**传输中立**（只约束行为，不约束实现路径）。

Edexcel 的门禁判定有个坑：`gating` 字段实测恒为 false（IGCSE 全部 9,272 条），
**必须**用 URL 前缀判定。信这个字段会漏判全部登录墙资源。

## 8. 尚未实现（不虚报）

1. **AP / SAT / IB 适配器**：Cambridge 与 Edexcel 已实现；
   AP（`apcentral.collegeboard.org`）与 SAT（`satsuite.collegeboard.org`）实测可达但未实现；
   IB `ibo.org` 返回 403，需另行评估。
   Edexcel 侧 8 条未决项见 `research/edexcel.md §8`（其中 `select_facet_tags` 只在 2 个科目上验证过，
   需在 258 个科目页全量回归；1000 条截断响应不能证明 facet 穷尽——分片维度取自
   截断响应出现过的 facet，能降低但无法证明覆盖完整，切不动时显式报错，
   不能声称全量可用）。
2. **Alembic 迁移**：仍是 `Base.metadata.create_all` + `db.py` 里的 `_ADDED_COLUMNS` 补列清单。
   后者是过渡方案，能保证升级代码后不必重建数据库，但不是正式迁移。
3. **全量同步**：Cambridge 发现层已枚举 198 个 syllabus，但只同步了 4 个科目
   （0580 / 9709 / 0620 / 0478）；Edexcel 已枚举 258 个科目页，仅试同步 1 个
   （accounting-2023-modular，44 份文档，其中只有 1 份是公开可下载的 PDF，
   其余为登录墙资源或非试题材料）。全量同步尚未执行。
4. **生成解析是规则式而非推理式**：`provider=rule-based`，能重组官方评分结构，
   但**不会真正演算数学题**。要产出真正的解题步骤需要接入模型服务；
   届时 provider/model 字段与 pending 审核流程可直接复用。
5. **分值合计仍有偏差**：12 份文档的 `marks_total_mismatch` 未收敛，最大偏差 0580/41 的 120 vs 130。
   主因是页边距过滤丢掉的 `[n]` 分值标记，以及深层子题路径与 MS 的对齐。
6. **9709 Mark Scheme 关联偏低**：38/60，深层子题路径匹配待改进。
