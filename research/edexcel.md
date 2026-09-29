# Phase 0 研究证据：Pearson Edexcel

> 状态：初稿（基于本次实测）。所有结论均标注实测来源；标 `[待补]` 的项在 Phase 0 收尾前补齐。
> 采集工具：`.venv\Scripts\python.exe scripts\probe_edexcel.py`（httpx，`trust_env=False`，UA 为
> `Mozilla/5.0 (compatible; examdata-research/0.1; +https://example.invalid/bot)`，请求间隔 1.1s，robots 前置判定）。
> 复现命令：`$env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe scripts\probe_edexcel.py`

## 1. 结论摘要

**Pearson Edexcel 的公开真题可以采集，但有两个硬约束：**

1. **发现链路不是 HTML 锚点，而是两个 JSON API。** 所有 subject / past-papers / course-materials 页面
   都是 AngularJS 空壳，服务端 HTML 里**没有任何 PDF 锚点**（实测 `.coursematerials.html` 与 `.html`
   页面 `href="...pdf"` 计数为 **0**）。资源清单只能通过 XHR 接口拿到。
2. **相当一部分档是登录墙内的。** 实测 IGCSE 家族 `Exam-materials` 类共 9,272 条，其中 972 条
   （约 10.5%）URL 位于 `/content/dam/secure/silver/`，**robots.txt 明确 Disallow `*/silver/*`**，
   且实际请求会 302 到 `edexcelonline.com` 登录页。这部分必须排除。

- 科目枚举入口：Algolia 索引上的 `cq:Page` 记录（`type:"cq:Page"` + 家族 facet）
- 实测可枚举 **258 个科目页**（IGCSE 75 + IAL 24 + GCE A Level 66 + GCSE 93）
- 资源清单入口：`/services/pearson/algolia/GET.servlet?fq=<facet 标签 AND ...>`
- 单个 IGCSE 科目（Economics 2017）实测返回 **173 条记录**，其中 **149 条公开 / 24 条门禁**
- 覆盖文件类型：Question Paper、Mark Scheme、Examiner Report、Modified Question Paper、
  Specimen Paper & Mark Scheme、Exemplar Material、Listening MP3、Data Files 等
- robots.txt 允许 `/en/qualifications/**`、`/services/pearson/**`、`/content/dam/pdf/**`；
  **禁止 `*/secure/*`、`*/silver/*`、`*/gold/*`** → 门禁档必须整体跳过

## 2. robots.txt（实测）

来源：`https://qualifications.pearson.com/robots.txt`（**HTTP 200**，7,317 字节）

### 2.1 与真题采集直接相关的规则（原文）

```
User-agent: *
Disallow: /templates/
Disallow: */secure/*
Disallow: */gold/*
Disallow: */silver/*
Disallow: */endorsed-resources/*
Disallow: */events/*
Disallow: */case-studies/*
Disallow: */contact-list/*
Disallow: */faq-landing/*

Disallow: /en/qualifications/edexcel-gcses/mathematics-2015/mathematics-live-papers-2018.html
Disallow: /en/qualifications/edexcel-gcses/sciences-2016/science-live-papers-2018.html
Disallow: /content/dam/pdf/gcse/gcse-science-summer-2018-exam-papers.zip
Disallow: /content/dam/pdf/gcse/gcse-maths-summer-2018-exam-papers.zip
... (大量 BTEC / NVQ 科目页 Disallow，与真题无关，此处省略)
Disallow: /en/vocational-fees

SITEMAP: https://qualifications.pearson.com/en/sitemap1.xml
SITEMAP: https://qualifications.pearson.com/en/sitemap1.xml?type=pdf&offset=0
SITEMAP: ... (offset=5000, 10000, 15000, 20000, 25000, 30000)
```

### 2.2 逐路径 robots 判定（`urllib.robotparser` 实测）

| 路径 | robots | 说明 |
|---|---|---|
| `/en/qualifications/edexcel-international-gcses.html` | ✅ 允许 | 家族落地页 |
| `/en/qualifications/{family}/{subject}.html` | ✅ 允许 | 科目页 |
| `/services/pearson/subjectlistaz/GET.servlet` | ✅ 允许 | 科目枚举 API（但见 §3.1，实际不可用） |
| `/services/pearson/algolia/GET.servlet` | ✅ 允许 | **资源清单 API（主入口）** |
| `/content/dam/pdf/past-papers.json` | ✅ 允许 | 旧版 facet 索引 |
| `/content/dam/pdf/International%20GCSE/.../4ec1-01-que-20220525.pdf` | ✅ 允许 | 公开 PDF |
| `/content/dam/secure/silver/.../4ec1-01-pef-20260122.pdf` | ❌ **禁止** | 命中 `*/secure/*` 与 `*/silver/*` |

**合规判定**
- 公开档（`/content/dam/pdf/**`）在 robots 允许范围内 → 可采集。
- **门禁档（`/content/dam/secure/**`）被 robots 明确禁止** → 抓取器必须在发出请求前拦截。
  这一点比 Cambridge 更硬：Cambridge 只是部分 PDF 被 Disallow，Edexcel 是**整类路径**被禁。
- 本机探测脚本已实现前置判定：命中 Disallow 时记录 `SKIPPED robots-disallowed` 并**不发出请求**
  （实测输出 `robots 拦截: 1 条`）。
- `SITEMAP` 声明 `sitemap1.xml?type=pdf&offset=*`，但实测该 URL 返回的仍是**页面** sitemap
  （5,618 条 `<loc>`，全为 `.html`），**不含 PDF 条目**。sitemap 因此只能作为科目页的旁证，
  不能作为资源枚举入口。

## 3. 发现链路（三层，均已实测）

### 3.1 第一层：家族 → 科目枚举

**⚠️ 关键坑：URL 路径段与 Algolia facet 家族名不同名。**

| 家族 | URL 路径段 | Algolia facet 取值 |
|---|---|---|
| International GCSE | `edexcel-international-gcses` | `International-GCSE` |
| International A Level | `edexcel-international-advanced-levels` | `International-Advanced-Level` |
| GCE A Level | `edexcel-a-levels` | `A-Level` |
| GCSE | `edexcel-gcses` | `GCSE` |

混用会得到 **0 结果**（实测：用 URL 段拼 facet 查询，servlet 返回 **60 字节**的空响应）。

#### 入口 A（推荐，四家族通用）：Algolia `cq:Page`

```
GET https://qualifications.pearson.com/services/pearson/algolia/GET.servlet
      ?fq=type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/{FACET_FAMILY}"
      &hitsPerPage=2000
```

返回 `searchResults.algoliaRecords[]`，过滤 `url` 匹配
`^/en/qualifications/{family}/[a-z0-9-]+\.html$` 即得科目页。

实测计数：

| 家族 | Algolia cq:Page 命中 | sitemap1.xml 命中 |
|---|---|---|
| International GCSE | **75** | 47 |
| International A Level | **24** | 14 |
| GCE A Level | **66** | 42 |
| GCSE | **93** | 41 |
| **合计** | **258** | 144 |

> sitemap 覆盖不全（漏掉 2023/2024 modular 与 2026/2027 新版），Algolia 是唯一完整入口。
> 实测 Algolia 结果里的科目页 URL 抽检返回 200（`biology-2018.html`、`chemistry-2018.html`、
> `english-language-2015.html` 等）。

#### 入口 B（实测不可用，仅作记录）：`subjectlistaz` servlet

页面上的 AngularJS 组件：

```html
<div class="col-xs-12 subjectStyling azSubjectList" id="sortaz"
     data-ng-controller="subjectsCtrl"
     data-ng-init="initSubjectList('/content/demo/en/qualifications/edexcel-international-gcses','')"
     ng-cloak></div>
```

它调用的接口是：

```
GET /services/pearson/subjectlistaz/GET.servlet?currentPage={cms-path}
```

**实测缺陷：`currentPage` 参数被服务端忽略。** 无论传
`.../edexcel-international-gcses`、`.../edexcel-a-levels`、`.../edexcel-gcses`、
`.../edexcel-international-advanced-levels`，甚至一个不存在的
`/content/demo/en/qualifications/totally-bogus-path-xyz`，返回的都是**同一份 52 个顶层 IGCSE 科目**。
（`page` / `path` / `contentPath` / `pagePath` / `cmsPath` / `root` 等参数名同样无效。）

结论：该接口**只能用于 IGCSE**（返回 51 个去重后的科目页），不能作为通用枚举入口。
本脚本把它作为**对照组**跑，以显式暴露这个不一致。

#### 抽取正则（已实测）

```python
# 落地页 -> cms-path
re.compile(r"""initSubjectList\(\s*'([^']+)'\s*,""", re.I)
# 落地页 HTML 中不存在任何科目链接（#sortaz 是空 div），不要试图用锚点抽取
```

### 3.2 第二层：科目页 → facet 标签集

科目页 URL 规律：

```
https://qualifications.pearson.com/en/qualifications/{family}/{subject-slug}.html
```

实测 slug 样本（IGCSE）：
- `international-gcse-economics-2017`
- `international-gcse-accounting-2017`
- `accounting-2023-modular`（modular 变体，无 `international-gcse-` 前缀）
- `biology-2024-modular`
- `english-as-a-second-language-2023`

> 注意：slug 末尾 4 位数字是**资格版本起始年**（`-2017`），**不是科目代码**。科目代码
> （`4EC1`、`4MA1` 等）只出现在 PDF 文件名与 `Pearson-UK:Specification-Code` facet 里。

科目页 HTML 中，`facetListCtrl` 指令携带完整 facet 标签集：

```html
<div class="content-coursematerials" id="courseMaterialsFacets_1151319745"
     data-ng-controller="facetListCtrl"
     data-ng-init="init('coursematerials', '[Pearson-UK:Qualification-Family/International-GCSE, Pearson-UK:Qualification-Subject/Economics, Pearson-UK:Specification-Code/igcse-economics-2017, Pearson-UK:Accreditation-From-date/2017]', 'normal', '' , '','en')"
     data-ng-cloak>
```

抽取正则（已实测）：

```python
RE_NG_INIT_FACETS = re.compile(
    r"""data-ng-controller="facetListCtrl"[^>]*data-ng-init="init\('([^']*)',\s*'\[([^\]]*)\]'""",
    re.I | re.S)
```

实测抽出的标签（Economics 2017）：
```
Pearson-UK:Qualification-Family/International-GCSE
Pearson-UK:Qualification-Subject/Economics
Pearson-UK:Specification-Code/igcse-economics-2017
Pearson-UK:Accreditation-From-date/2017
```

#### ⚠️ 关键坑：标签集里的 `Specification-Code` 变体**互斥**

A Level 数学 2017 的页面实测抽出 **9 个标签**，其中 6 个是 `Specification-Code` 变体：

```
Pearson-UK:Specification-Code/A-Level/2017/al17-maths      <- 最具体（3 段）
Pearson-UK:Specification-Code/al17-maths
Pearson-UK:Specification-Code/A-Level/2017
Pearson-UK:Specification-Code/2017
Pearson-UK:Specification-Code/A-level/2017/maths-2017-as-al
Pearson-UK:Specification-Code/maths-2017-as-al
Pearson-UK:Qualification-Subject/Mathematics
Pearson-UK:Accreditation-From-date/2017
Pearson-UK:Qualification-Family/A-Level
```

**全部 AND 起来只剩 1 条**（只匹配到科目页自身），因为没有任何文档同时带全部变体。
实测的互斥对（每一对 AND 后都只剩 1 条）：

| 标签 A | 标签 B | AND 结果 |
|---|---|---|
| `Specification-Code/A-Level/2017/al17-maths` | `Specification-Code/A-Level/2017` | 1 |
| `Specification-Code/A-Level/2017/al17-maths` | `Specification-Code/2017` | 1 |
| `Specification-Code/A-Level/2017` | `Specification-Code/maths-2017-as-al` | 1 |
| `Specification-Code/2017` | `Qualification-Subject/Mathematics` | 1 |

单标签命中数（实测）：

| 标签 | 命中 |
|---|---|
| `Specification-Code/A-Level/2017/al17-maths` | **27** ← 最具体，正确 |
| `Specification-Code/al17-maths` | 27 |
| `Specification-Code/A-Level/2017` | 2（过窄） |
| `Specification-Code/2017` | 10（过窄） |
| `Specification-Code/maths-2017-as-al` | 815（过宽，混入 GCSE/A-Level 其他年份） |
| `Specification-Code/A-level/2017/maths-2017-as-al` | 701（过宽） |

**实测可行的选择规则**（已实现为 `select_facet_tags`）：

```python
family  = [t for t in tags if t.startswith("Pearson-UK:Qualification-Family/")]
subject = [t for t in tags if t.startswith("Pearson-UK:Qualification-Subject/")]
spec    = [t for t in tags if t.startswith("Pearson-UK:Specification-Code/")]
picked  = family + subject
if spec:
    # 最具体 = 斜杠最多；同段数时取字符串最短（避开 "A-Level/2017" 这类泛化前缀）
    picked.append(max(spec, key=lambda t: (t.count("/"), -len(t))))
```

实测效果（A Level 数学 2017）：**全 AND → 1 条；压缩后 → 27 条**。
IGCSE Economics 2017 只有 1 个 `Specification-Code`，压缩后 4 → 3 个标签，结果不变（173 条）。

**`course-materials` 页（`.coursematerials.html`）不含 facet 标签**，只有
`data-ng-init="startConfig('coursematerials','','','en')"`（参数为空）。
**必须用 `.html` 科目页，不能用 `.coursematerials.html`。**

### 3.3 第三层：facet 标签 → 资源清单

```
GET https://qualifications.pearson.com/services/pearson/algolia/GET.servlet
      ?fq=category:"tag1" AND category:"tag2" AND ...
```

返回 `searchResults.algoliaRecords[]`，每条记录的字段（实测）：

```json
{
  "title": "Question paper - Paper 1R - June 2022",
  "url": "/content/dam/pdf/International GCSE/English Language A/2016/exam-materials/4ea1-01r-que-20220519.pdf",
  "extension": "PDF",
  "size": "932.5 KB",
  "gating": false,
  "id": "/content/dam/pdf/International GCSE/English Language A/2016/exam-materials/4ea1-01r-que-20220519.pdf",
  "description": "Paper 1R - Written Paper",
  "datecreated": "2023-07-31T09:45:23.159Z",
  "category": [
    "Pearson-UK:secure-content/silver",
    "Pearson-UK:Qualification-Family/International-GCSE",
    "Pearson-UK:Qualification-Subject/English-Language-A",
    "Pearson-UK:Document-Type/Question-paper",
    "Pearson-UK:Exam-Series/June-2022",
    "Pearson-UK:Specification-Code/igcse16-eng-langa",
    "Pearson-UK:Category/Exam-materials",
    "Pearson-UK:Unit/Paper-1R"
  ]
}
```

**元数据全部结构化，不需要从锚文本解析。** 这是与 Cambridge 最大的区别：Cambridge 必须
`parse_label` + `parse_slug` 交叉校验，Edexcel 直接读 facet 数组即可。

实测 Economics 2017（173 条）的类型分布：

| Document-Type | 条数 |
|---|---|
| Question-paper | 46 |
| Mark-scheme | 44 |
| Examiner-report | 44 |
| Past-training-content | 11 |
| Modified-question-paper | 8 |
| Exemplar-material | 4 |
| Specimen-paper-and-mark-scheme | 4 |
| 其他（Scheme-of-work / Specification / Notice / Sample-assessment-material 等） | 12 |

考季覆盖（实测）：June 2019–2026、January 2020/2023、November 2020/2021/2023/2024/2025。

### 3.4 分页

**servlet 的 `page` 参数被忽略**（实测 `page=0/1/2` 返回完全相同的 5 条记录）。
`hitsPerPage` **有效**（实测 `hitsPerPage=5` → 5 条；`hitsPerPage=1000` → 1000 条；
不传时默认上限也是 1000）。`size` / `limit` 参数无效。

→ 实现时必须显式传 `hitsPerPage`，且**单次上限 1000**。超过 1000 条的科目需要
拆查询（按 `Document-Type` 或 `Exam-Series` 细分）。IGCSE 全家族 9,272 条就必须拆分。

### 3.5 直连 Algolia（可选旁路）

页面 HTML 内嵌 Algolia 凭据（实测）：

```html
<input type="hidden" value="L639T95U5A" class="algoliaAppId"/>
<input type="hidden" value="f79c7a8352e9ffbdaec387bf43612ee6" class="algoliaAPIKey"/>
<input type="hidden" value="qualifications-uk_LIVE_master-content" class="algoliaIndexName"/>
```

可直接 POST `https://L639T95U5A-dsn.algolia.net/1/indexes/qualifications-uk_LIVE_master-content/query`，
支持 `facets`、`filters`、`page`、`hitsPerPage`，**分页正常**（`nbPages` 正确返回）。
本脚本**默认不使用**这条路径——它绕过了站点的 servlet 层，属于对第三方服务的直接调用；
servlet 已能满足需求。记录在此仅供后续评估。

## 4. 文件 URL 规律与身份

### 4.1 路径前缀（IGCSE 全家族 9,272 条实测全量统计）

| 前缀 | 条数 | robots | 可达性 |
|---|---|---|---|
| `/content/dam/pdf/**` | **8,293** | ✅ 允许 | HTTP 200，`application/pdf` |
| `/content/dam/secure/silver/**` | **972** | ❌ 禁止 | 302 → `edexcelonline.com/Account/Login.aspx` |
| `/content/dam/secure/**`（非 silver） | 7 | ❌ 禁止 | 同上 |

IAL 家族（9,727 条）：`/content/dam/pdf/` 8,577 + `/content/dam/secure/silver/` 1,149 + 1。

### 4.2 路径结构

```
公开：/content/dam/pdf/{Qualification Family}/{Subject}/{Year}/exam-materials/{filename}.pdf
       /content/dam/pdf/{Qualification Family}/{Subject}/{Year}/Exam-materials/{filename}.pdf
门禁：/content/dam/secure/silver/all-uk-and-international/{family-slug}/{subject}/{year}/exam-materials/{filename}.pdf
```

> ⚠️ **目录名大小写不统一**（`exam-materials` 与 `Exam-materials` 并存），
> **空格未编码**（`International GCSE`、`English Language A`）。httpx 会自动编码空格为 `%20`，
> 两种写法实测均返回 200。

### 4.3 文件名文法（两代并存，实测）

**新式（2019 之后）**：`{spec-code}-{paper}-{doctype}-{yyyymmdd}.pdf`

```
4ec1-01-rms-20220825.pdf      Mark scheme - Paper 1 - June 2022
4ec1-02r-que-20220615.pdf     Question paper - Paper 2R - June 2022
4ec1-01-pef-20220825.pdf      Examiner report - Paper 1 - June 2022
4ec1-01-pef-20260122.pdf      Examiner report - Paper 1 - November 2025  [门禁路径下]
4ea1-01r-que-20220519.pdf     Question paper - Paper 1R - June 2022
```

**旧式（2019 及之前）**：`{SPEC}_{PAPER}_{doctype}_{yyyymmdd}.pdf`（大写、下划线分隔）

```
4EC1_01_pef_20190822.pdf      Examiner report - Paper 01 - June 2019
4EC1_01R_rms_20190822.pdf     Mark scheme - Paper 1R - June 2019
4MA1_1HR_pef_20190822.pdf     Examiner report - Paper 1HR - June 2019
4SS0_1P_pef_201908221.pdf     Examiner report - Paper 1P - June 2019
```

### 4.4 文件名后缀 → 文件类型（实测统计，IGCSE 前 1000 条）

| 后缀 | 条数 | 含义 |
|---|---|---|
| `pef` | 332 | Examiner report（Principal Examiner Feedback） |
| `que` | 274 | Question paper |
| `rms` | 226 | Mark scheme（Results/Mark Scheme） |
| `msc` | 9 | Mark scheme（旧式，IAL 更多） |

**但后缀不可靠**，必须优先用 `Pearson-UK:Document-Type` facet。实测存在
`4FA1_01_perf_20190821.pdf`（四字母 `perf`）、`4SP1_01-recording-2206.mp3`、
`International GCSE French MP 7.mp3` 等不符合文法的文件名。

### 4.5 标题（`title` 字段）文法

实测模板：

```
{Question paper|Mark scheme|Examiner report} - Paper {N} - {Series} {YYYY}
{Question paper|Mark scheme|Examiner report} - Unit {N} - {Series} {YYYY}
Listening Examination MP3s - {Series} {YYYY}
Recording - Paper {N} - {Series} {YYYY}
Recording (Extra Time 25%) - Paper {N} - {Series} {YYYY}
Recording Tracked - Paper {N} - {Series} {YYYY}
Modified papers - {spec} - {Series} {YYYY}
```

- `Series` ∈ {January, May, June, October, November, February}（实测全部出现）
- `Paper` 编号有 `1` / `01` / `1R` / `1H` / `1F` / `1HR` / `2CR` / `1B` / `E` 等多种形式
- IAL 与 A Level 更多用 `Unit {N}`

### 4.6 身份键（identity_key）建议

```
sha1(board | qualification | spec_code | exam_series | unit | doc_type)
```

理由：
- `Pearson-UK:Specification-Code` 是稳定的资格标识（如 `igcse-economics-2017`），
  比 slug 可靠，且**不随 URL 变化**。
- `Pearson-UK:Exam-Series` 直接给出 `June-2022` 形式，无需从标题解析。
- `Pearson-UK:Unit` 直接给出 `Paper-1R` 形式。
- **禁止用 URL 或 `id` 作身份**：同一份文档在公开/门禁路径下 URL 完全不同
  （实测：Economics 的 June 2022 QP 在 `/content/dam/pdf/`，November 2025 ER 在
  `/content/dam/secure/silver/`），且 Pearson 换路径时 URL 会变。

## 5. 规模与更新节奏

| 项 | 实测 |
|---|---|
| 科目页（Algolia cq:Page，四家族） | **258**（IGCSE 75 + IAL 24 + A Level 66 + GCSE 93） |
| 科目页（sitemap 旁证） | 144（覆盖不全） |
| IGCSE 全家族 `Exam-materials` | 9,272 条（公开 8,293 / 门禁 972） |
| IAL 全家族 `Exam-materials` | 9,727 条（公开 8,577 / 门禁 1,149） |
| A Level 全家族 `Exam-materials` | 16,105 条 |
| GCSE 全家族 `Exam-materials` | 12,762 条 |
| 单科目样本（IGCSE Economics 2017） | 173 条（公开 149 / 门禁 24） |
| 覆盖考季 | June 2005 – June 2026、November 2005 – November 2026、January 2010 – January 2026 |
| 新增时点 | June 系列成绩发布后（约 8 月）、November/January 系列后（约 1–3 月） |

> 注意 `June-2026` / `November-2026` 已出现在索引里（未来考季的预发布档）。

## 6. 登录墙与公开范围

实测 `https://qualifications.pearson.com/en/support/support-topics/exams/past-papers.html` 原文：

> Our easy-to-use past paper search gives you instant access to a large library of past exam papers
> and mark schemes. They're available free to teachers and students, **although only teachers can
> access the most recent papers sat within the past 12 months**.
>
> Question papers, mark schemes and examiner reports for the most recent exam sessions (within the
> last 12 months) can be accessed only by registered centres. If you don't have an Edexcel Online
> account, please contact your Exams Officer.
>
> Past papers and mark schemes **accompanied by a padlock** are not available for students, but only
> for teachers and exams officers of registered centres.

**实测验证：**

| 测试 | 结果 |
|---|---|
| `GET /content/dam/pdf/International GCSE/English Language A/2016/exam-materials/4ea1-01r-que-20220519.pdf` | **HTTP 200**，`application/pdf` |
| `GET /content/dam/secure/silver/all-uk-and-international/a-level/music/2016/exam-materials/p73664-gce-a-music-9mu0-02-brief-assess-tech.pdf` | **HTTP 302** → `https://www.edexcelonline.com/Account/Login.aspx?spid=...&spref=...` |
| `GET /content/dam/secure/gold/x.pdf` | **HTTP 302** → 同上（gold 是更高门禁等级） |

**公开可拿到的类型（实测 IGCSE Economics 2017，149 条公开）：**
- Question Paper（含 Modified Question Paper）
- Mark Scheme
- Examiner Report
- Specimen Paper and Mark Scheme
- Exemplar Material
- Listening Examination MP3
- Data Files / ZIP 打包（`modified-papers-4ec1-june-2021.zip`）
- Scheme of Work / Specification / Qualification Guide（教学材料，非真题）

**拿不到的（门禁，实测 24 条）：**
- 最近 12 个月的 QP / MS / ER（`/content/dam/secure/silver/**`）
- 所有 `Modified papers` 的近期版本
- 决策：列为**可选认证档**。仅当用户提供自有合法会话时启用；未启用时公开档照常工作。
  **不实现任何绕过**，且 robots 已禁止该路径。

## 7. 与 Cambridge 适配器的差异（对实现的直接影响）

| 维度 | Cambridge | Edexcel |
|---|---|---|
| 枚举入口 | HTML 锚点正则 | **JSON API**（Algolia servlet） |
| 科目数 | 198 | 258 |
| 资源清单 | HTML `<a href="/Images/*.pdf">` | **JSON `algoliaRecords[]`** |
| 元数据来源 | 锚文本 + URL slug 交叉校验 | **facet 数组直接给出**（无需解析） |
| 文件 URL | `/Images/{id}-{slug}.pdf` | `/content/dam/pdf/{Family}/{Subject}/{Year}/exam-materials/{name}.pdf` |
| 门禁 | School Support Hub（独立域名） | **同一域名下的 `/content/dam/secure/**`** |
| robots 风险 | `/search` 被禁 | **`*/secure/*` 整类被禁** |
| 分页 | 单页全量 | **servlet 忽略 `page`，`hitsPerPage` 上限 1000** |

**新增的抓取器需求：**
1. `Fetcher` 需要支持 **JSON 端点**（当前 `get_text` 已够用，但 `Accept` 头应允许 `application/json`）。
2. robots 强制层要能拦住 `/content/dam/secure/`——当前 `RobotsPolicy` 用
   `urllib.robotparser`，实测能正确判定 `*/secure/*` 与 `*/silver/*`，无需改动。
3. 需要一个**通用的"分片查询"工具**：当 `nbHits > 1000` 时按 facet 维度拆分。

## 8. 未决项（Phase 0 收尾前必须补齐）

1. **`select_facet_tags` 的规则只在 IGCSE Economics + A Level Mathematics 上验证过。**
   需要在全部 258 个科目页上跑一遍，确认：(a) 不会因规则过窄而漏档；
   (b) `Accreditation-From-date` 是否该一并丢弃（当前被丢弃——实测它单独命中 1000+ 条，
   作为 AND 条件会与 `Specification-Code` 冲突）。需要**逐科目对比"压缩后条数"与"人工核对条数"**。
2. **`hitsPerPage` 上限 1000 的拆分策略。** IGCSE 全家族 9,272 条、A Level 16,105 条
   都超限。当前 `fetch_resources` 只在命中上限时打印告警，**尚未实现分片**。
   需要按 `Exam-Series` 或 `Document-Type` 分片，并验证分片并集是否等于全集。
3. **`subjectlistaz` servlet 的 `currentPage` 失效是否为永久性。** 可能是 Pearson 的 CDN
   缓存 bug（返回体对任何参数都相同），也可能是接口已废弃。需在 Phase 0 收尾时复测。
4. **`past-papers.json` 的用途。** 实测 `/content/dam/pdf/past-papers.json`（HTTP 200，233KB）
   只含 `searchResults.facets`（950 个 category 值），**不含任何文档记录**。它是旧版
   past-paper 搜索页的 facet 预热文件，是否还有用待确认。
5. **直连 Algolia 的合规评估。** 索引凭据在页面 HTML 里公开，但直接 POST 第三方 DSN
   绕过了 Pearson 的 servlet 层。需要决定是否允许（当前脚本默认不用）。
6. **`gating` 字段的实际含义。** 实测 IGCSE 全 9,272 条 `gating` 全为 `false`，
   包括门禁路径下的记录。**该字段不能用来判定门禁**，必须用 URL 前缀
   （`/content/dam/secure/`）。原因待查。
7. **`Accreditation-From-date` 与 slug 年份的关系。** slug 的 `-2017` 与 facet 的
   `Accreditation-From-date/2017` 实测一致，但 A Level 有 `-2000` 等更早的 slug，
   需要确认是否都是有效资格。
8. **PDF 内容解析特征**（题号文法、分值标记、Mark Scheme 表格结构）—— 需下载样本后分析。
   本次调研**未下载任何 PDF 内容**（只做 HEAD 验证可达性）。

## 9. 对本项目的直接影响

1. Edexcel **可以进入 Phase 2 首批适配器**，但实现方式与 Cambridge **完全不同**：
   必须走 JSON API，不能复用 Cambridge 的 HTML 锚点正则。
2. **适配器需要新增"facet 查询"抽象**：`discover_resources` 不再是"抓页面 + 抽锚点"，
   而是"抓科目页 + 抽 facet 标签 + 查 servlet"。建议在 `BoardAdapter` 之外加一个
   `FacetAdapter` mixin，或在 Edexcel 适配器内自行封装。
3. **robots 强制必须覆盖 `/content/dam/secure/**`。** 当前 `Fetcher.assert_allowed`
   已能正确判定，但需确认它作用在所有请求上（包括 PDF HEAD）。
4. **文档身份必须基于 `Specification-Code` + `Exam-Series` + `Unit` + `Document-Type`**，
   不能基于 URL 或 `id`（公开/门禁路径不同，且会变）。
5. **必须实现 1000 条分片查询**，否则大科目会静默截断——这是 Edexcel 特有的静默失效模式。
6. **URL 路径段与 Algolia facet 家族名必须分开维护**，混用会得到 0 结果且不报错。
7. `gating` 字段**不可信**，门禁判定必须用 URL 前缀。
