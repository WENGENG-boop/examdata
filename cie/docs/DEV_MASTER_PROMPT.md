# CIE 全学科解析算法：开发与测试总提示词（Master Prompt）

> 用法：把本文件**整份**发给 AI 编程助手（或开发同学），并附上 `cie_parser_package.zip`。
> 它是自包含的：读完就能开工，不需要再看聊天记录。
> 配套文档：`docs/DESIGN.md`（算法原理）、`docs/SUBJECT_PROMPTS.md`（各学科要点速查）。

---

## 0. 你的角色与最终目标

你是一名资深 Go 工程师，负责把 `cieparse`（剑桥 CIE/CAIE 真题 PDF 解析器）从目前的 **数学 / 物理 / 经济 三科**，扩展到 **所有学科**，并为每个学科建立可重复运行的自动化测试。

交付完成的定义（Definition of Done）：
1. 每个学科都有 `subj_<学科>.go`，并在 `init()` 中注册该学科的全部科目代码。
2. 每个学科至少 **3 个考试季 × 该科全部 Paper** 的 qp + ms 通过自校验（见第 6 节）。
3. 每个学科在 `testdata/manifest.json` 中有测试样本清单，`go test ./...` 全部通过。
4. `docs/DESIGN.md` 第 5 节为每个学科追加一小节（题型、算法、校验结果、已知问题）。
5. 输出一份 `docs/TEST_REPORT.md`：全部学科 × 全部样本的校验结果表。
6. 现有三科（数学 0580/9709、物理 0625/9702、经济 0455/9708）的已通过结果**不允许退化**。

---

## 1. 绝对规则（违反任何一条都视为未完成）

1. **禁止 OCR**。只能使用 PDF 自带的文字层（`pdftotext -layout`）、字符坐标（`mutool draw -F stext`）和矢量路径（`mutool trace`）。文字被画成图片的情况，只记录图片位置并在 `warnings` 中说明。
2. **禁止为了让校验通过而硬编码**某份试卷的题号、分值或答案。所有规则必须对同一科的其他年份同样成立；硬编码特例必须写成带注释的通用规则，并说明适用条件。
3. **不重写已有的通用函数**（见第 3 节）。需要改通用函数时：先写回归测试证明现有三科不受影响，再改。
4. **校验失败不能静默**：输出 `warnings: []string`，写明哪项校验失败、期望值、实际值。绝不能丢弃数据或伪造字段来凑数。
5. 学科解析器遇到不认识的文件类型，返回 `(nil, false)`，交回通用解析器。
6. JSON 字段 `snake_case`，空值 `omitempty`；新增字段不能改变已有字段的含义。
7. 抓取 PDF 时控制频率：并发 ≤ 4，命中本地缓存不重复下载，失败重试 ≤ 3 次。
8. 每完成一个学科就提交一次（或打一次 zip），不要攒到最后。

---

## 2. 环境

| 项目 | 说明 |
|---|---|
| 语言 | Go 1.23（解析器），Python 3（抓取与测试辅助脚本） |
| 依赖 | `poppler-utils`（pdftotext、pdfinfo）、`mupdf-tools`（mutool） |
| 安装 | Alpine：`apk add go poppler-utils mupdf-tools python3`；macOS：`brew install go poppler mupdf-tools` |
| 构建（普通机器） | `cd cie/cieparse && go build -o /tmp/cieparse .` |
| 构建（iSH/低内存） | `GOMAXPROCS=1 GOFLAGS=-p=1 CGO_ENABLED=0 GOGC=50 go build -o /tmp/cieparse .`（多线程编译会崩） |
| 运行 | `/tmp/cieparse -j 2 -o out.json <pdf或目录>`；`-math -page N`；`-diagram`；`-name` |
| 注意 | iSH 中 `/var/minis/workspace` 下的二进制无法执行，一律输出到 `/tmp` |

### PDF 下载源（按优先级）
1. **fraft（43 个常用科目，JSON 接口，PDF 体积小）**
   - 科目列表：`POST https://cie.fraft.cn/obj/Common/Subject/combo`（必须带 `Content-Length: 0`）
   - 某季文件：`POST https://cie.fraft.cn/obj/Common/Fetch/renum`，body `subject=0580&year=2022&season=Jun`（season ∈ Mar/Jun/Nov）
   - PDF：`GET https://cie.fraft.cn/obj/Common/Fetch/redir/<文件名>`
   - 注意：PDF 由 Acrobat 重新生成，`●` 会变成 `Ɣ`，页面是 Letter 尺寸。算法必须用相对比例，不得写死 A4 坐标。
2. **PapaCambridge（最全）**：`https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/<文件名>`
3. **官网**：只用于核对最新一季。

**两个源的同一份 PDF 都要至少抽测 1 份**，确认解析结果一致（字段值相同，坐标可不同）。

---

## 3. 已有代码（直接复用，不要重写）

| 函数 / 类型 | 文件 | 作用 |
|---|---|---|
| `ParseFilename(path) FileMeta` | main.go | 文件名 → syllabus/year/season/type_code/component/paper/variant |
| `header(txt) Header` | parsers.go | 封面：科目、卷号、考试季、时长、总分（`total_mark`） |
| `ParseQP(txt) QPData` | parsers.go | 试卷骨架：题号（必须递增）、小题 (a)/(i)、`[n]` 分值、`marks_match_total` |
| `ParseMSCol(txt) MSData` | ms_col.go | 按表头列位置解析评分标准；支持 M1/A1/*M1/DM1/SC、备选解法、小计行 |
| `ParseGT` / `ParseER` | parsers.go | 分数线、考官报告 |
| `ParseMCQQP` / `ParseMCQKey` / `isMCQ` | subj_econ.go | 选择题试卷与答案（全学科通用） |
| `ParseEconMS` / `parseLevel` | subj_econ.go | 结构化评分标准：command word、得分点 `(n marks)`、上限、Level 分级、AO |
| `ParsePhysQP` / `ParsePhysMS` / `physRowMarks` | subj_phys.go | 图号引用、答案线（符号/单位/分值）、C1 补偿分不累加、单位/有效数字/规则 |
| `ParseMathQP` / `ParseMathMS` / `decodeMarks` | subj_math.go | 精度要求、必须写过程、知识点、答案线类型；给分代码解码 |
| `physQuestionBlocks(txt, qs)` | subj_phys.go | 每道题的原始文本块（学科 enrich 的入口） |
| `LoadPage(pdf, n) *Page` | geom.go | 字符坐标/字体/字号 + 矢量路径 + `FixGlyph` |
| `PageMath(p) []MathLine` | mathlayout.go | 分式/根号/上下标 → 线性文本 + LaTeX |
| `PageDiagrams(p) []Diagram` | diagram.go | 图区域、坐标轴标定、柱状图、曲线、表格（table.go） |
| `register(codes, fn)` | subj_econ.go | 学科注册表 |
| 工具 | `clean` `uniqAdd` `msLine` `hdrCols` `noiseRe` `markRe` `qStartRe` | |

先通读这些文件再动手。新学科照 `subj_math.go`、`subj_phys.go`、`subj_econ.go` 的写法：**通用骨架 + 学科 enrich**。

---

## 4. 每个学科的标准开发流程（严格按顺序）

### 步骤 1：收集样本
- 从 fraft `Subject/combo` 确认科目代码；fraft 没有的用 PapaCambridge。
- 选 **3 个考试季**：最近一年的 s（May/June）、最近一年的 w（Oct/Nov）、5 年前左右的一季（检验旧版式）。如有 m（Feb/March，仅印度区）再加 1 季。
- 每季下载：该科**全部 Paper 的 qp + ms**（每个 Paper 取 variant 1 即可，如 11/21/31/41），加 `gt`、`er`，有 `in`（insert）/`ci`/`pm` 也下。
- 写入 `testdata/manifest.json`（格式见第 7 节）。PDF 放 `testdata/pdf/<科目>/`，**不要提交 PDF 到 git**，用 `tools/fetch_testdata.py` 按 manifest 下载。

### 步骤 2：看版式（必须写下观察结果）
对每个 Paper 运行：
```bash
pdftotext -layout X.pdf - | sed -n '1,200p'
pdffonts X.pdf
/tmp/cieparse X.pdf | head -c 3000          # 当前通用解析结果
/tmp/cieparse -diagram X.pdf | python3 tools/dsum.py /dev/stdin
```
在 `docs/notes/<科目>.md` 记录：
- 题型（选择题 / 结构化 / 论述 / 实验 / 编程 / 阅读 / 写作 / 听力）
- 评分标准的分值写法（数字、M1/A1、C1、Level 区间、`(1)` 内联、`;` 分隔、`any two from`、`max N`）
- 表头列名（Question/Answer/Marks/Guidance，或 AO1/AO2 分列，或无表格）
- 选做规则（封面 “Answer all / Answer N questions / Section A … Section B …”）
- 特殊字体（Symbol、Wingdings、ZapfDingbats、Courier、非拉丁文字）
- 图形类型（电路、曲线、结构式、地图、流程图、照片）

### 步骤 3：让分值校验先通过
这是正确性的“锚点”，必须先于任何学科字段完成：
1. qp：`marks_sum == header.total_mark`（选做题按 `optional_groups` 计，见 6.3）
2. ms：`numeric_marks_sum == header.total_mark`
3. qp 与 ms 逐题对比：`python3 tools/cmp.py qp.pdf ms.pdf` 输出为空

不通过时：先用 `pdftotext -layout` 看出错题号附近的原始文本，判断是**通用层**问题（列切分、小计行、备选解法）还是**学科层**问题（分值写法特殊），再决定改哪里。

### 步骤 4：学科特有字段
至少 3 个，从第 5 节对应学科的要求里选；每个字段必须在 3 季样本上都能抽出（允许个别为空，但要在 notes 说明原因）。

### 步骤 5：图形与公式
- 跑 `-diagram`，检查该科主要图形类型是否被正确分类（kind）、标签是否完整、坐标轴是否标定。
- 跑 `-math`，抽 5 行含公式/化学式/单位上标的文本，确认 LaTeX 正确。
- 缺失的能力：优先写成**通用函数**放进 diagram.go / mathlayout.go（例如“双 y 轴”“苯环”“流程图箭头”），并为其加单元测试。

### 步骤 6：测试与文档
- `go test ./...` 全过；`tools/run_regression.py` 生成报告。
- 更新 DESIGN.md 第 5 节、TEST_REPORT.md、notes。

---

## 5. 输出结构规范（所有学科统一）

每个学科解析器返回的顶层对象必须包含：
```json
{
  "kind": "mcq_paper | mcq_key | structured_paper | structured_ms | levels_ms | insert | transcript | instructions",
  "subject": "chemistry",
  "header": { "syllabus": "0620", "component": "42", "session": "May/June 2022", "duration": "1 hour 15 minutes", "total_mark": 80 },
  "questions": [ ... ] 或 "rows": [ ... ],
  "marks_sum": 80,                 // qp
  "numeric_marks_sum": 80,         // ms
  "optional_groups": [ { "section": "B", "choose": 1, "questions": ["2","3","4"], "marks_each": 20 } ],
  "effective_total": 40,           // 按选做规则计算后的总分
  "checks": { "marks_match_total": true, "ms_match_total": true },
  "warnings": ["Q5: ms sum 9 != qp 10"]
}
```
题目（qp）通用字段：`number, page, text, marks, parts[{label,text,marks}], figures[], command_words[], answer_lines[]`，学科字段追加在后面。
评分行（ms）通用字段：`question, answer, marks, partial_marks, alternative, mark_codes[]`，学科字段追加在后面。

**`checks` 和 `warnings` 是必填的**——测试框架依赖它们。

---

## 6. 校验规则（测试框架据此判定通过/失败）

### 6.1 试卷（qp）
| 检查项 | 规则 | 失败处理 |
|---|---|---|
| `marks_match_total` | 无选做：`marks_sum == header.total_mark`；有选做：`effective_total == header.total_mark` | warning，列出每题分值 |
| 题号连续 | 1..N 递增无缺号（允许某些学科从 Section 重新编号，需在 notes 说明） | warning：缺失题号 |
| 小题分值 | 每个有 `[n]` 的小题 `marks > 0` | warning |
| 封面字段 | `syllabus`、`component`、`session`、`total_mark` 非空 | warning |
| 文件名一致 | `header.syllabus == meta.syllabus` 且 `header.component == meta.component` | warning |

### 6.2 评分标准（ms）
| 检查项 | 规则 |
|---|---|
| `ms_match_total` | `numeric_marks_sum == header.total_mark`（选做按 `effective_total`） |
| 无空分行 | 除 `alternative=true` 的行外，`marks` 不为空 |
| 题号覆盖 | ms 中的大题号集合 == qp 中的大题号集合 |
| 逐题一致 | 每道大题：qp 分值 == ms 分值（`tools/cmp.py` 无输出） |
| 选择题答案 | 题数 == qp 题数，答案 ∈ {A,B,C,D}，合计 == 总分 |

### 6.3 选做题（optional_groups）
1. 从 qp 封面和 Section 标题读取规则：`Answer all questions`、`Answer N questions`、`Section A: answer Question 1. Section B: answer one question.`、`Answer one question from each section`、`Option`/`Depth Study`。
2. 每个 Section 的题号范围由 Section 标题之间的题号确定。
3. `effective_total = Σ必答题分值 + Σ(choose × 该组单题分值)`；组内各题分值不等时取最大值并加 warning。
4. ms 合计同样按组计算。9708/22（40 分）、0455/22（90 分）、历史、文学、地理必须用这个规则通过。

### 6.4 图表与公式（抽样校验，写进 manifest 的 `expect`）
- `diagram`：期望 kind、关键标签、柱状图数值（容差 ±2%）、坐标轴 min/max。
- `math`：期望某页某行 LaTeX 包含的子串（如 `\frac{3}{7}`）。
- `table`：期望行列数和若干单元格值。

---

## 7. 测试框架（需要你新建）

### 7.1 目录
```
cie/
├── testdata/
│   ├── manifest.json          样本清单 + 期望值（提交到 git）
│   └── pdf/<科目>/*.pdf        按 manifest 下载（不提交）
├── tools/
│   ├── fetch_testdata.py      按 manifest 下载：fraft 优先，失败回退 PapaCambridge，校验 %PDF 头
│   ├── run_regression.py      跑全部样本，生成 docs/TEST_REPORT.md 和 report.json
│   ├── cmp.py                 qp vs ms 逐题对比（已有，改成读 JSON 输出也可）
│   └── dsum.py                diagram 输出摘要（已有）
└── cieparse/
    ├── regression_test.go     读 manifest 跑校验（go test）
    └── <模块>_test.go         单元测试（纯函数，用内联文本，不依赖 PDF）
```

### 7.2 manifest.json 格式
```json
{
  "subjects": {
    "0620": {
      "name": "chemistry", "level": "igcse",
      "samples": [
        {"file": "0620_s22_qp_42.pdf", "expect": {"total_mark": 80, "questions": 6}},
        {"file": "0620_s22_ms_42.pdf", "expect": {"total_mark": 80}},
        {"file": "0620_s22_qp_12.pdf", "expect": {"kind": "mcq_paper", "questions": 40}},
        {"file": "0620_s22_ms_12.pdf", "expect": {"kind": "mcq_key", "keys": 40}},
        {"file": "0620_s22_qp_42.pdf", "mode": "math", "page": 5,
         "expect": {"latex_contains": ["H_{2}O"]}},
        {"file": "0620_s22_qp_42.pdf", "mode": "diagram", "page": 3,
         "expect": {"kind": "diagram", "labels_contain": ["thermometer"]}}
      ],
      "known_failures": [
        {"file": "0620_w19_qp_62.pdf", "check": "marks_match_total", "reason": "…", "issue": "#12"}
      ]
    }
  }
}
```
规则：
- 每个学科 ≥ 3 季 × 全部 Paper；`expect` 中至少有 `total_mark`。
- `known_failures` 只允许记录**有原因和后续计划**的失败，测试中跳过但在报告里显示为黄色。数量不得超过该学科样本的 10%。

### 7.3 regression_test.go 要求
- 读取 manifest，对每个样本运行解析（直接调用 `ParseFile` / `PageMath` / `PageDiagrams`，不要 exec 子进程）。
- PDF 不存在时 `t.Skip`（提示先运行 fetch_testdata.py），不能失败。
- 每个样本一个子测试：`t.Run("0620/0620_s22_qp_42", …)`，便于 `go test -run 0620` 只跑一科。
- 断言：第 6 节全部检查 + `expect` 中的字段。
- 在 iSH 中运行：`GOMAXPROCS=1 GOFLAGS=-p=1 CGO_ENABLED=0 go test -run 0620 -v .`

### 7.4 单元测试要求（不依赖 PDF）
为每个新增的纯函数写表驱动测试，至少覆盖：
- 正常例 2 个、边界例 1 个、应拒绝的反例 1 个（例如：表格线不能识别为分数线、图中标签 A/B 不能识别为选项）。
- 文本输入直接内联为 Go 字符串（从 `pdftotext -layout` 复制几行）。
- 几何函数用手工构造的 `Page{Chars, Segs, Paths}`。

### 7.5 run_regression.py 输出（docs/TEST_REPORT.md）
```
| 科目 | 文件 | 类型 | 总分 | qp合计 | ms合计 | 逐题一致 | 学科字段 | 状态 |
|------|------|------|------|--------|--------|----------|----------|------|
| 0620 | 0620_s22_qp_42 | structured_paper | 80 | 80 | – | ✔ | equations=12 | PASS |
```
末尾汇总：每个学科 PASS/FAIL/KNOWN 数量、通过率；以及与上一次报告的对比（新增失败必须为 0）。

---

## 8. 各学科开发任务（逐科执行，每科都按第 4 节流程）

> 每科格式：科目代码 → 题型 → 必须实现的字段 → 必须通过的校验 → 必测样本。
> 「必测样本」中 `XX` 表示你选的 3 个考试季（如 s23、w23、s18）。

### 8.0 先修复现有三科的遗留问题（第一个里程碑）
1. **选做题**：实现 6.3 的 `optional_groups` / `effective_total`（通用函数 `parseOptionalRules(txt) []OptGroup` 放 parsers.go）。验收：9708_s22_qp_22 与 ms_22 的 effective_total = 40，0455_s22_qp_22/ms_22 = 90。
2. **IGCSE 经济 `(1)` 内联计分**：得分点文本中的 `(1)` 计数，配合 `max N`；验收：0455 ms_22 每题 criteria 分值之和 ≥ 题目分值。
3. **符号字体映射**：`FixGlyph` 增加 Wingdings / ZapfDingbats / MMBinary 表（`\x16`→✓、`\x1a`→✗、MMBinary `#`→×）。验收：9708_s22_qp_12 Q4 选项为 ✓/✗ 组合；0580_s22_qp_11 第 10 页表格为 `2.06 × 10^8`。
4. **图片型选项**：选项为空时，用 `PageDiagrams` 中位于字母 A–D 右侧的图区域生成 `options[i].figure_bbox`，并加 warning。验收：0455_s22_qp_12 Q7、Q17 每题 4 个选项都有 bbox。
5. **物理 A-Level 推导式答案**：对 ms 行先过 `PageMath`，取最后一个 `=` 右边做 value/unit。验收：9702_s22_ms_22 中 ≥ 70% 的计算行有 value。
6. **数据源**：`cie_api.py` 增加 `--source fraft` 并设为默认（科目不在 fraft 时自动回退 papa）。验收：`papers 0580 --year 2022 --season s` 两个源文件名集合相同。

### 8.1 化学 0620 0971 5070 9701 → `subj_chem.go`
- 题型：P1/P2 选择题；P3/P4 结构化；P5/P6（9701 P3）实验；9701 P4/P5 结构化与计划。
- 字段：`equations[]`（含 →/⇌、状态符号，下标还原为 `H_{2}O`）；`ions[]`（上标电荷 `SO_{4}^{2-}`）；答案线单位；`structures[]`（苯环 = 6 条等长线段闭合的正六边形；键 = 连接两个元素符号的线段；双键 = 两条平行短线）；周期表页标为 `kind: data_sheet` 并跳过。
- ms：行内 `M1 … M2 …` 拆分步得分点；`any two from`、`max N`、`ignore state symbols`、`ecf`；方程式原子守恒检查（不守恒只加 warning）。
- 校验：qp/ms 合计；结构式抽检 2 个（期望原子数、环数）。
- 样本：0620_XX_qp/ms_12,22,32,42,52,62；9701_XX_qp/ms_12,22,32,42,52。

### 8.2 生物 0610 0970 5090 9700 → `subj_bio.go`
- 字段：`label_lines[]`（引线：一端在图内、一端接字母或空横线 → {label, x, y}）；实验数据表（表头含 `/ s`、`/ °C` 拆出单位）；`drawing_required`（空坐标纸 graph_grid）；command words。
- ms：`;` 分隔得分点、编号得分点 `1 … 2 …`、`max N`；`A`/`R`/`I`/`AW`/`ORA` 拆为 `accept[]`、`reject[]`、`ignore[]`。
- 校验：每题得分点数 ≥ 分值；合计。
- 样本：0610_XX_qp/ms_12,22,32,42,52,62；9700_XX_qp/ms_12,22,33,42,52。

### 8.3 综合/联合科学 0653 0654 5129 → `subj_sci.go`
- 按题目关键词判子学科，调用 chem/bio/phys 的 enrich 函数；输出 `strand: biology|chemistry|physics`。
- 校验：每题 strand 非空；合计。

### 8.4 计算机 0478 0984 9608 9618 2210 → `subj_cs.go`
- 字段：`code_blocks[]`（Courier 类字体连续行，缩进 = (x − 块最小 x)/字宽）；`keywords[]`（DECLARE、IF…ENDIF、FOR…NEXT、WHILE、REPEAT…UNTIL、PROCEDURE、FUNCTION）；`trace_tables[]`（表头为变量名、空格待填）；`flowcharts[]`（矩形/菱形/圆角矩形节点 + 箭头边，箭头 = 线段终点处小三角填充）；`logic_circuits[]`（门形状 + 连线 + 真值表）。
- 二进制/十六进制串原样保留，不得被数值化。
- ms：`1 mark per bullet`、`max N`、代码答案保留缩进、`example_answer` 单独字段。
- 样本：0478_XX_qp/ms_12,22；9618_XX_qp/ms_12,22,32,42。

### 8.5 数学扩展（在 subj_math.go 内）0606 4037 0607 9231 及 9709 P4–P6
- 矩阵（两条竖曲线括号 + 内部数字网格 → `\begin{pmatrix}`）、列向量、∫/∑ 上下限（大字号符号右上/右下的小字号字符）、分布记号 `B(n,p)`、`N(μ,σ^2)`。
- 统计卷附表页标 `data_sheet`。
- 样本：0606_XX_qp/ms_12,22；9231_XX_qp/ms_12,22,32,42；9709_XX_qp/ms_42,52,62。

### 8.6 商科 0450 7115 9609 → `subj_bus.go`；会计 0452 7707 9706 → `subj_acc.go`
- 商科：insert（`_in_`）解析为 `appendices[]`，题目关联 `appendix_refs`；ms 的 AO1–AO4 分列表（扩展 `hdrCols` 识别 AO 列）+ Level；`k/app/an/eval` 标记。
- 会计：`statements[]`（标题 + 行 {label, amount, column}），金额支持千分位、括号负数 `(1 200)`；ms 中 `(1)`、`(1OF)` 计分（OF = own figure）；借贷合计相等检查。
- 样本：0450_XX_qp/ms/in_12,22；9609_XX_qp/ms/in_12,22,32；0452_XX_qp/ms_12,22；9706_XX_qp/ms_12,22,32。

### 8.7 地理 0460 2217 9696 → `subj_geo.go`
- 字段：`grid_refs[]`（GR 4/6 位）、比例尺；图片（照片）只记 bbox + 图号；diagram.go 增加**双 y 轴**（左右各一组刻度，气候图）、人口金字塔（左右对称横柱）、三角图。
- ms：Level 区间、`1 mark per valid point, max N`、`dev`。选做 Section 规则。
- 样本：0460_XX_qp/ms/in_12,22,42；9696_XX_qp/ms/in_12,22,32,42。

### 8.8 历史 0470 2147 9489 → `subj_hist.go`
- 字段：`sources[]`（Source A/B… 正文 + 斜体出处行）；Option/Depth Study 选做组；题目固定结构 (a)(b)(c)。
- ms：Level 1–5 + 区间 + `indicative_content`（复用 parseLevel）。
- 校验：effective_total == 总分。
- 样本：0470_XX_qp/ms_12,22,42；9489_XX_qp/ms_12,22,32,42。

### 8.9 英语与语言 0500 0510 0511 0990 0991 9093 及外语（0509 0520 0525 0530 0547 等）→ `subj_lang.go`
- insert：段落还原（行距 + 首行缩进），**行号剥离**为 `line_numbers`（左侧小字号 5/10/15）；写作题 `word_limit`、`genre`。
- 听力 transcript：按说话人标签切分 `turns[]`。
- 非拉丁：0509 中文保持原序；阿拉伯语按 stext `dir`/`bidi` 反转行内顺序。
- ms：Reading/Writing 两套 Level 表 + 逐题 `Award 1 mark for …`。
- 样本：0500_XX_qp/ms/in_12,22；0510_XX_qp/ms_22,42 + 听力稿；9093_XX_qp/ms/in_12,22；0509_XX_qp/ms_12。

### 8.10 其他论述类 → `subj_essay.go`
体育 0413、社会学 0495/9699、心理学 9990、旅游 0471、环境管理 0680、法律 9084、全球视野 0457 等：ParseQP + 资料块 + Level 表 + `1 mark per point`；心理学关联 Core Study 名称；艺术 0400/9479 只有 ci/pm，输出 `themes[]`；0680 复用 geo 图表与 bio 得分点。

---

## 9. 里程碑与顺序
| 里程碑 | 内容 | 验收 |
|---|---|---|
| M0 | 测试框架（第 7 节）+ 现有三科写入 manifest | `go test` 现有三科全过 |
| M1 | 8.0 遗留问题修复 | 8.0 各项验收 |
| M2 | 化学、生物、综合科学 | 第 6 节全部检查 |
| M3 | 计算机、数学扩展 | 同上 + 代码块/矩阵抽检 |
| M4 | 商科、会计、经济补全 | 同上 + 选做 |
| M5 | 地理、历史 | 同上 + 双 y 轴 |
| M6 | 语言类、其他论述类 | 同上 |
| M7 | 全量回归 + TEST_REPORT.md + 文档 | 通过率 ≥ 95%，新增失败 0 |

## 10. 每次汇报的格式
```
学科：0620 化学   里程碑：M2
样本：18 份（s23 w23 s18 × P1–P6 qp+ms）
校验：PASS 17 / FAIL 0 / KNOWN 1（0620_s18_qp_62：实验表格为图片，已加 warning）
新增字段：equations, ions, structures, data_sheet
修改的通用函数：diagram.go 新增 detectHexagon()（附单元测试 4 例）
现有三科回归：全部 PASS
已知问题与下一步：…
```
不要只说“完成了”——没有校验数字的汇报视为未完成。
