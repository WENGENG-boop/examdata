# Phase 0 研究证据：Cambridge International

> 状态：初稿（基于 2026-02 实测）。所有结论均标注实测来源；标 `[待补]` 的项在 Phase 0 收尾前补齐。
> 采集工具：直连 HTTP（`Invoke-WebRequest`，UA 为常规浏览器）。注意：本机 DNS 将 `cambridgeinternational.org` 解析到 `198.18.2.215`（保留段），
> 因此**必须**用直连方式采集，`web_fetch` 类代理会因"非公网 IP"拒绝。

## 1. 结论摘要

**Cambridge International 的公开真题可以完整采集，无需任何登录。**

- 公开入口：`https://www.cambridgeinternational.org/programmes-and-qualifications/{syllabus-slug}/past-papers`
- 枚举入口：`https://www.cambridgeinternational.org/programmes-and-qualifications/{family}/{qualification}/subjects/`
- 实测可枚举 **198 个 syllabus**（IGCSE 104 + AS/A Level 59 + O Level 35）
- 每个 syllabus 页公开 **19–27 份 PDF**，估算公开档总量 **4,000–6,000 份**
- 覆盖文件类型：Question Paper、Mark Scheme、Examiner Report、Specimen Paper、Specimen Mark Scheme、Insert/Source Material、Confidential Instructions
- 完整历史档案在 School Support Hub（登录墙）→ 列为可选认证档，不在首期必达范围

## 2. robots.txt（实测全文要点）

来源：`https://www.cambridgeinternational.org/robots.txt`（HTTP 200）

```
User-Agent: *
Disallow: /beta.cie.org.uk/
Disallow: /prd.cie.org.uk/
Disallow: /search
Disallow: /images/310861-cambridge-appeals-regulations-and-guidance.pdf
Disallow: /sitemap/site-map-hidden.aspx
Disallow: /Images/cambridge-samples-database.xls
Disallow: /images/cambridge-samples-database.xls
Disallow: /Images/168168-cambridge-guide-making-entries-march-series.pdf
Disallow: /uzbekistan-university-admissions-2021/
Disallow: /Images/635441-uzbekistan-university-admissions-2021-list.pdf
Disallow: /why-choose-us/information-for-schools-in-indonesia/
Disallow: /covid/portfolio-of-evidence/results-and-enquiries-about-results/guidance-for-schools/
Disallow: /covid/june-2023-exam-series/running-exams/supporting-schools-in-china/
Sitemap: http://www.cambridgeinternational.org/sitemap_seo.xml
Sitemap: http://www.cambridgeinternational.org/recognition-sitemap-xml.xml
```

**合规判定**
- `/programmes-and-qualifications/...` 与 `/Images/...pdf` **未被禁止** → 公开真题采集在 robots 允许范围内。
- `/search` 被禁止 → **禁止使用站内搜索**（`/search/gcsearch.aspx`）做枚举。这一点很重要：页面上有
  `data-resultsUrl="/search/gcsearch.aspx"`，实现时**必须避开**。
- 抓取器必须实现 robots 强制层，并在命中 Disallow 前缀时拒绝请求（含上表 4 个具体 PDF）。

## 3. 发现链路（三层，均已实测）

### 3.1 第一层：家族 → syllabus 枚举

页面模式：`/programmes-and-qualifications/{family}/{qualification}/subjects/`

| 家族 | 实测 URL | 状态 | 实测 syllabus 数 |
|---|---|---|---|
| Cambridge IGCSE | `/programmes-and-qualifications/cambridge-upper-secondary/cambridge-igcse/subjects/` | 200，title `Cambridge IGCSE subjects` | **104** |
| Cambridge AS & A Level | `/programmes-and-qualifications/cambridge-advanced/cambridge-international-as-and-a-levels/subjects/` | 200 | **59** |
| Cambridge O Level | `/programmes-and-qualifications/cambridge-upper-secondary/cambridge-o-level/subjects/` | 200 | **35** |
| Cambridge Primary | `/programmes-and-qualifications/cambridge-primary/subjects/` | **404** | [待补] |
| Cambridge Lower Secondary | `/programmes-and-qualifications/cambridge-lower-secondary/subjects/` | **404** | [待补] |

抽取正则：`/programmes-and-qualifications/([a-z0-9\-]+-[0-9]{4})/`

样本 slug：
- `cambridge-igcse-9-1-computer-science-0984`
- `cambridge-igcse-accounting-0452`
- `cambridge-igcse-english-second-language-oral-endorsement-0510`
- `cambridge-international-as-and-a-level-accounting-9706`
- `cambridge-o-level-accounting-7707`

注意：family 页（`.../cambridge-igcse/`）本身**不含** syllabus 链接（实测 slugs=0），必须走 `/subjects/`。

### 3.2 第二层：syllabus → 资源清单

页面模式：`/{syllabus-slug}/past-papers`（带不带尾斜杠均 200）

实测页面正文（0580）：
> You can download one or more past question papers below. These question papers may not reflect the content of the current syllabus.
> ... **Unlock more content** — This is only a selection of our papers. Registered Cambridge International Schools can access a wide range of teaching and learning materials and examination resources through our School Support Hub.

PDF 锚点抽取正则：`<a[^>]+href="(/Images/[^"]+\.pdf)"[^>]*>(.*?)</a>`

### 3.3 第三层：锚文本 → 结构化元数据

**实测样本（0580 Cambridge IGCSE Mathematics）**

| 锚文本 | 实际 href |
|---|---|
| June 2024 Question Paper 11 | `/Images/569923-june-2024-question-paper-11.pdf` |
| June 2024 Mark Scheme Paper 11 | `/Images/569919-june-2024-mark-scheme-paper-11.pdf` |
| June 2024 Question Paper 21 | `/Images/569924-june-2024-question-paper-21.pdf` |
| June 2024 Mark Scheme Paper 21 | `/Images/569920-june-2024-mark-scheme-paper-21.pdf` |
| June 2024 Question Paper 31 | `/Images/569925-june-2024-question-paper-31.pdf` |
| June 2024 Mark Scheme Paper 31 | `/Images/569921-june-2024-mark-scheme-paper-31.pdf` |
| June 2024 Question Paper 41 | `/Images/671439-june-2024-question-paper-41.pdf` |
| June 2024 Mark Scheme Paper 41 | `/Images/671437-june-2024-mark-scheme-paper-41.pdf` |
| June 2024 Examiner Report | `/Images/569918-june-2024-examiner-report.pdf` |
| 2025 Specimen Paper 1 | `/Images/663662-2025-specimen-paper-1.pdf` |
| 2025 Specimen Paper 1 Mark Scheme | `/Images/663670-2025-specimen-paper-1-mark-scheme.pdf` |

**实测样本（9709 Cambridge International AS & A Level Mathematics）** — 25 个 PDF 锚点

| 锚文本 | 实际 href |
|---|---|
| June 2024 Question Paper 11 | `/Images/567744-june-2024-question-paper-11.pdf` |
| June 2024 Mark Scheme Paper 11 | `/Images/567738-june-2024-mark-scheme-paper-11.pdf` |
| June 2024 Question Paper 21/31/41/51/61 | `/Images/567745…`、`567746…`、`673793…`、`673795…`、`673797…` |
| June 2024 Mark Scheme Paper 21/31/41/51/61 | `567739`、`567740`、`673787`、`673789`、`673791` |
| June 2024 Examiner Report | `/Images/567737-june-2024-examiner-report.pdf` |
| 2020 Specimen Paper 1..6 | `/Images/751747…` … `751752` |
| 2020 Specimen Mark Scheme Paper 1..6 | `/Images/751735…` … `751740` |

**实测样本（0610 Biology）** — 27 个 PDF，含额外类型：
- `/Images/520423-june-2024-confidential-instructions-paper-51.pdf` → **Confidential Instructions**
- `/Images/520425-june-2024-examiner-report.pdf`
- `/Images/520429-june-2024-mark-scheme-paper-11.pdf`

**实测样本（0500 English First Language）** — 19 个 PDF，含：
- `/Images/414805-2020-specimen-paper-1-insert.pdf` → **Insert / Source Material**
- `/Images/414811-2020-specimen-paper-2-mark-scheme.pdf`

**实测样本（9702 Physics）** — 23 个 PDF，含跨考季：`June 2023` 与 `June 2024`。

### 3.4 命名文法（用于分类，实测归纳）

```
{series} {year} {doc_type} {paper_code}.pdf          # 常规
{year} Specimen Paper {n}.pdf                        # 样卷
{year} Specimen Paper {n} Mark Scheme.pdf            # 样卷评分标准
{year} Specimen Paper {n} Insert.pdf                 # 样卷材料
{series} {year} Examiner Report.pdf                  # 考官报告（整卷级）
{series} {year} Confidential Instructions Paper {n}.pdf
```

- `series` ∈ {June, November, March}（实测出现 June / November / March）
- `year` = 4 位年份
- `doc_type` ∈ {Question Paper, Mark Scheme, Examiner Report, Confidential Instructions, Insert, Specimen Paper, Specimen Mark Scheme}
- `paper_code` = 两位数字（如 `11`、`21`、`61`）

## 4. 文件 URL 与身份

- 形式：`/Images/{opaque-numeric-id}-{descriptive-slug}.pdf`
- **opaque id 无语义**（同一考季同一科目的 id 不连续：`569923` 与 `671439` 同为 0580 QP），
  且**官方替换文件时 id 可能改变** → **禁止把 URL 或 id 作为文档身份**。
- 身份键（identity_key）定义：
  ```
  sha1(board | qualification | subject_code | year | series | paper_code | doc_type)
  ```
  Cambridge 特有：`paper_code` 直接使用页面给出的两位数字串（`11`/`21`/…），
  另存 `component`/`variant` 为**解释结果**（需 syllabus structure 表校验，[待补]）。
- descriptive slug 作为**交叉校验信号**（与锚文本解析结果比对，不一致则降置信度并转人工）。

## 5. 规模与更新节奏

| 项 | 实测/估算 |
|---|---|
| 公开 syllabus 数 | 198（IGCSE 104 + AS/A 59 + O Level 35） |
| 每 syllabus 公开 PDF 数 | 19–27（实测 4 个样本） |
| 公开档总量估算 | **约 4,000–6,000 份 PDF** |
| 公开窗口 | 近 1–2 个考季（实测 June 2024 为主；9702 含 June 2023）+ Specimen |
| 新增时点 | June 系列成绩发布后（约 8 月）、November 系列后（约 1–2 月） |
| 建议巡检 | 常态每周 1 次；8 月与 1–2 月窗口期每日 1 次 |

## 6. 登录墙与可选认证档

- School Support Hub：`https://schoolsupporthub.cambridge.org`（HTTP 200，React SPA，约 4.5KB 壳）
  - 原域名 `schoolsupporthub.cambridgeinternational.org` 302 → `schoolsupporthub.cambridge.org`
  - 需机构账号登录；**不实现任何绕过**
- Cambridge International Direct：`https://direct.cie.org.uk/`
- 决策：列为**可选认证档**。仅当用户提供自有合法会话时启用；未启用时公开档照常工作。

## 7. 解析特征（初步）

[待补] —— 需下载样本 PDF 后分析：
- 题号文法（`1 (a) (i)` 的层级与缩进规律）
- 分值标记形式（`[2]` vs `(2 marks)`）
- 页眉页脚噪声模式（`© UCLES {year}`、`[Turn over`）
- Mark Scheme 表格结构（Question | Answer | Marks | Guidance）
- 是否全部为文本型 PDF（实测 PDF 体积 225KB–3MB，MS 约 200–500KB，初步判断为文本型）

## 8. 未决项（Phase 0 收尾前必须补齐）

1. Cambridge Primary / Lower Secondary 的 subjects 入口（`/subjects/` 返回 404）。
2. 全部 198 个 syllabus 的 syllabus structure 表（用于 component/variant 解释）。
3. 每家族各 3 份 QP + 3 份 MS 的版式与题号文法分析（见 §7）。
4. O Level Mathematics 4024 的 `/past-papers` 页实测失败（slug 可能不同），需确认 slug 映射规则。
5. 各 family 页是否分页/懒加载（当前 104 个 slug 一次性出现在 HTML 中，未见分页）。

## 9. 对本项目的直接影响

1. Cambridge **必须**进入 Phase 2 首批适配器（用户要求 + 已证实可行）。
2. 抓取器**必须**内置 robots 强制，且**禁止**调用 `/search/gcsearch.aspx`。
3. 采集**必须**直连（本机 DNS 将域名解析到保留段），不能依赖通用 fetch 代理。
4. 文档身份**必须**基于 syllabus code + 考季 + doc_type + paper_code，不能基于 URL/id。
5. 分类器**必须**以锚文本为主信号、descriptive slug 为交叉校验，不能只看文件名。
6. 静默失效检测为必达项（依赖页面结构，选择器一变即失效）。
