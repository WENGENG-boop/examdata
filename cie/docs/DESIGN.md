# CIE 真题抓取与解析系统：设计与开发文档

> 版本 v0.3 · 2026-10-07 · 语言：Python（抓取 API）+ Go（解析器 `cieparse`）
> 原则：**不依赖 OCR**。所有结构（题号、分值、公式、图表、表格、评分代码）都从 PDF 自带的文字坐标和矢量路径用算法还原。

---

## 1. 总体思路

剑桥（CIE/CAIE）的 PDF 都是排版软件（InDesign / Word）直接导出的“原生 PDF”，不是扫描件，里面有三类信息可以直接读出来：

| 信息 | 来源工具 | 用途 |
|---|---|---|
| 带版式的纯文本 | `pdftotext -layout` | 题号、分值 `[n]`、评分标准表格的列 |
| 每个字符的坐标、字体、字号 | `mutool draw -F stext` | 分式、上下标、根号、图表标签 |
| 矢量路径（线段、矩形、曲线） | `mutool trace` | 分数线、表格线、坐标轴、柱状图、曲线 |

OCR 只在“文字被画成图片”时才需要，而 CIE 2010 年以后的试卷几乎没有这种情况。所以思路是：

1. **文件名即元数据**：`0580_s22_qp_11.pdf` → 科目 0580、2022 年 May/June、试卷、Paper 1 Variant 1。
2. **版式文本做骨架**：题号顺序递增 + 行尾 `[n]` 分值，求和后与封面 “The total mark for this paper is N” 对比，作为**自校验**。
3. **坐标做精细结构**：分数线 = 短而细的水平线，上方有分子、下方有分母；上标 = 字号更小且基线抬高。
4. **矢量做图表**：一组等间距的数字刻度 = 坐标轴，最小二乘拟合得到“像素→数值”的换算，矩形高度即柱状图数值。
5. **学科层做语义**：同一套底层算法，按科目代码分发到学科解析器（数学看 M1/A1，物理看单位和 C1，经济看分级评分）。
6. **每一步都有校验**：试卷分值合计 = 总分；评分标准分值合计 = 总分；坐标轴拟合 r² ≥ 0.995；表格至少一半单元格有字。校验不通过的结果要标出来，而不是静默输出。

---

## 2. 数据源比较与结论

| 数据源 | 接口 | 直接 PDF 链接 | 覆盖 | 评价 |
|---|---|---|---|---|
| 剑桥官网 cambridgeinternational.org | 无 JSON，HTML 里的 `/Images/*.pdf` | 是 | 每科只有最近 1 季 + 样卷 | 权威但太少 |
| PapaCambridge | 无 JSON，HTML 页面里 `upload/<文件名>.pdf` | **是**，`https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/0580_s22_qp_11.pdf` | IGCSE 138 科、AS/A 110 科、O Level，2001–2026 | **覆盖最全** |
| Frank 的 CIE 工坊 cie.fraft.cn | **有 JSON 接口**（POST） | **是**，`https://cie.fraft.cn/obj/Common/Fetch/redir/0580_s22_qp_11.pdf` 直接返回 `application/pdf` | 43 个常用科目，2001–2026 | **接口最干净、速度快**，PDF 是重新压缩版（体积约 1/5，文字层一致） |

fraft 接口（无需登录）：

```
POST https://cie.fraft.cn/obj/Common/Subject/combo          (需带 Content-Length: 0)
  → [{"value":"0580","text":"0580 - 数学 (IGCSE)"}, ...]
POST https://cie.fraft.cn/obj/Common/Fetch/renum   body: subject=0580&year=2022&season=Jun   (season: Mar|Jun|Nov)
  → {"total":26,"rows":[{"file":"0580_s22_qp_11.pdf","lessons":[]},...]}
GET  https://cie.fraft.cn/obj/Common/Fetch/redir/<file>     → PDF 本体
```

**结论**：
- 43 个主流科目（数学、物理、化学、生物、经济、计算机等）**优先用 fraft**：JSON 列表 + 小体积 PDF。
- fraft 没有的科目、或 fraft 不可用时，**回退到 PapaCambridge**。
- 官网只用来校验最新一季。
- 注意：fraft 的 PDF 被 Acrobat 重新生成过，项目符号 `●` 会变成 `Ɣ`（`FixGlyph` 已处理），页面尺寸从 A4 变成 Letter；坐标算法都用相对比例，不受影响。
- 请控制抓取频率（建议并发 ≤ 4、带缓存），这两个都是个人/社区站点。

---

## 3. 代码结构

```
cie/
├── cie_api.py            抓取 API（CLI + HTTP 服务），数据源 fraft（默认）/ papa / official
├── cieparse/             Go 解析器
│   ├── main.go           CLI、文件名解析、按类型/学科分发
│   ├── parsers.go        通用：表头 header、试卷 ParseQP、分数线 ParseGT、考官报告 ParseER
│   ├── ms_col.go         通用：按列位置解析评分标准表 ParseMSCol
│   ├── checks.go         校验块 `checks`：布尔结论 + warnings（§6.1）
│   ├── optional.go       选做组：封面指令 → `optional_groups` / `effective_total`
│   ├── geom.go           几何引擎：字符坐标 + 矢量路径 + Symbol 字体修复
│   ├── mathlayout.go     公式还原：分式、根号、上下标 → 线性文本 + LaTeX
│   ├── mathfix.go        表格线识别（避免误判成分数线）
│   ├── diagram.go        图表：区域聚类、坐标轴标定、柱状图、曲线
│   ├── table.go          矢量表格 → 二维单元格
│   ├── subj_econ.go      经济（0455 0987 2281 9708）+ 选择题通用算法 + 学科注册表
│   ├── subj_phys.go      物理（0625 0972 5054 9702）
│   ├── subj_math.go      数学（0580 0980 0606 0607 4024 4037 9709 9231）
│   └── *_test.go         单元测试（parsers / ms_col / optional / subj_econ）
├── testdata/
│   ├── manifest.json     回归样本清单：6 科 × 3 季 × variant 1，共 199 份
│   └── pdf/<科目>/       样本 PDF（不入库，用 tools/fetch_testdata.py 拉取）
├── tools/
│   ├── fetch_testdata.py 按 manifest 下载样本
│   ├── run_regression.py 跑全量样本 → docs/TEST_REPORT.md + testdata/report.json
│   └── cmp.py            单份 qp × ms 逐题对照
└── docs/
    ├── DESIGN.md         本文档
    ├── DEV_MASTER_PROMPT.md  里程碑与验收标准
    ├── TEST_REPORT.md    回归报告（脚本生成，勿手改）
    └── SUBJECT_PROMPTS.md  其余学科的开发提示词
```

处理流程：

```
PDF ──ParseFilename──▶ FileMeta(科目/年/季/类型/卷号)
   │
   ├─ subjectParsers[科目] 存在？ ──是──▶ 学科解析器（可返回 false 交回通用）
   │                                  └─ 内部复用：ParseQP / ParseMSCol / ParseMCQQP / ParseMCQKey
   └─ 否 ─▶ 通用：qp→ParseQP  ms→ParseMSCol  gt→ParseGT  er→ParseER  其它→原始文本

独立模式：cieparse -math file.pdf     （公式 LaTeX）
          cieparse -diagram file.pdf  （图表/表格 JSON）
```

---

## 4. 通用算法详解

### 4.1 文件名解析 `ParseFilename`
正则 `^(\d{4})_([msw])(\d{2})_([a-z]+)(?:_(\w+))?\.pdf$`。
- 季：`m`=Feb/March，`s`=May/June，`w`=Oct/Nov
- 类型：qp 试卷、ms 评分标准、er 考官报告、gt 分数线、in 附页、ci 保密说明、pm 预发材料、sf 源文件、sp/sm 样卷
- 组件 `41` → paper=4，variant=1；单数字 `1` → paper=1 无 variant（早年试卷）

### 4.2 试卷骨架 `ParseQP`
1. 按 `\f` 分页，跳过封面。
2. 题号识别：行首 `^(\d{1,2})(\s+.*)?$`，**且必须等于“下一个期望题号”**（next++）。这样页码、图上的数字、表格里的数字都不会被当成题号。
3. 小题：`(a)` 缩进 1–12 列，`(i)` 缩进 1–16 列，罗马小题挂在当前字母小题下（`a(i)`）。
4. 分值：行尾 `[n]`，累加到当前小题和题目。
5. 噪声行过滤：`© UCLES`、`Page x of y`、`[Turn over`、`BLANK PAGE`、`DO NOT WRITE IN THIS MARGIN`。
6. **校验**：`marks_sum == header.total_mark` → 顶层 `marks_match_total`（旧语义，保持不变）。
7. **选做组**：封面 `Answer all questions` → 无选做；`Section B: answer one question` / `Answer any two questions` → `optional_groups`（`section` / `choose` / `questions` / `marks_each`），正文 `Section X` 标题决定组内题号。据此算 `effective_total` = 必做题 + Σ(choose × marks_each)，写入 `effective_total`。已验证 9708_s22_qp_22 = 40、0455_s22_qp_22 = 90（原始 `marks_sum` 分别是 80 / 110）。
   - 封面有两种版式：指令与组标题同行（`Section B: answer two questions.`），以及**组标题单独一行、指令在下一行**（2018 年前后常见）。`coverSectionDirectives` 两种都认；修复前 `9708_s18_qp_41` 会漏掉 `Section B` 而算成 50，现在 = 70，`0455_s18_qp_21` = 90。
8. **封面总分**：`totalRe` 同时认 `The total mark for this paper is N` 与 `The maximum mark for this paper is N`；评分标准封面另认 `Maximum Mark: N`；**选择题卷不印数字总分**，只写 `There are forty questions on this paper` 加 `each correct answer will score one mark`，由 `countWords` 换算成 40。
9. **校验块 `checks`**：`checks.marks_match_total` 用 `effective_total`（无选做时即 `marks_sum`）比对封面总分；封面没有总分、合计不符、题号缺号都追加到 `checks.warnings`（`missingQuestions` 只报 1..max 中的空缺，因题号必须顺序递增，实际解析一般不会触发）。
10. **旧卷不印数字总分**：2018 年及更早的封面只写 "The number of marks is given in brackets [ ] ..."，`total_mark` 为空并写 `total mark not found on the cover` warning。这是**正确行为**：回归测试把「空总分 + 有 warning」判为通过，只把「空总分 + 无 warning」判为失败（§6.1）。

### 4.3 评分标准表 `ParseMSCol`（按列位置）
纯文本按“两个以上空格”切列在多行单元格时会错位，所以改为**按表头字符列号切列**：
1. 每页找到 `Question  Answer  Marks` 表头行，记录 `Question` 结束列、`Marks` 起止列。
2. 每行切成单词并记录列号；落在 Marks 列 ±5 列内、匹配 `\d{1,2}|\*?D?[MABC]\d|DB\d|SC\d` 的词是分数。
3. 例外：`M1 for ...`（紧跟 for）属于“部分给分说明”列，不算分。
4. 同一行可有多个代码（`A1 A1`），连续吸收。
5. 行首在 Question 列内、匹配 `\d{1,2}(\([a-z]+\)|\([ivx]+\))*` 的是新题号。
6. **备选解法**：出现 `Alternative method for question N` 后，同题号的后续行标 `alternative=true`，不计入合计。
7. **小计行**：一串代码后，Marks 列单独出现的数字 = 该小题总分（A-Level 格式），写入 `question_totals` 并覆盖代码求和。
8. 数字型分数后又出现数字：若该行有文字（IGCSE 理科“每行一个得分点”）→ 追加；否则视为正文里的数字。
9. **校验**：合计 == 封面 `Maximum Mark`，结论写在 `checks.ms_match_total`。回归报告 `docs/TEST_REPORT.md` 给出每份样本的真实数字。2026-10 的 199 样本回归（82 份 ms）显示，**没有一份 ms 样本通过自校验**：54 份 `WARN`（分值列解析不全，合计数偏小）、24 份 `NOC`（`mcq_key` / 经济结构化 MS，payload 不带 `checks` 块）、3 份 `DIFF`（经济卷，分级给分口径不同）、1 份 `KNOWN`（`0625_w23_ms_31`，封面斜杠被字体子集破坏）。对照 qp 侧 82 份中有 11 份 `PASS`——**分值列解析是当前最大的缺口**。
10. **校验块 `checks`**：`checks.ms_match_total` 给出结论，合计与封面总分不符、以及整行没有分值的行都追加到 `checks.warnings`（无分值的行最多列举 5 个题号，`alternative` 行不算）。
11. **已知缺口一：分值列比表头词靠右**。0580 2023 的表头是四列 `Question  Answer  Marks  ...  Partial Marks`：`Marks` 词左对齐在第 46 列，分值却右对齐在第 58 列，超出「`Marks` 词尾 + 4 列」的判定范围 → 分值被当成正文并入 `answer`，`marks` 留空。`0580_s23_ms_11` 因此只解析出 11/56，并写 `23 rows have no marks` 与 `mark scheme sum 11 does not match total mark 56` 两条 warning（warning 让它成为 WARN 而不是静默通过）。修法：分值单元格右界取到**下一个表头词的列号**，并要求单元格内除分值记号外没有别的词——`3 B2 for 4` 这类部分给分说明必须排除。
12. **已知缺口二：表头跨行**。0625 / 9702 / 0455 的 MS 把 `Question`、`Marks`、`Answer` 印在**三行**上，`msHdr2` 匹配不到，分值列位置未知（`unknown`）。此时只把「另起一个单元格」的记号当分值：宁可少算也不多算——不加这条限制，`0625_s18_ms_41` 会在一份 80 分的卷上收出 344 分。该卷仍为 0/80，同样带 warning。**同一缺口也会过收**：`0625_w23_ms_41` 在 80 分卷上收出 190 分（`11 rows have no marks` 与合计不符并存），说明「另起单元格」的判定在部分版式下会把正文里的数字也收进来；两个方向都要在重设计单元格边界时一起验证。
13. **已知缺口三：选择题答案表**（`ParseMCQKey`，见 §5.1）：`mcqKeyRe` 要求行尾带分值，`0625_*_ms_11` 因此只解析出 18/40，且 payload 无 `checks` 块，回归里既不是 PASS 也不是 FAIL，记为 `NOC`。

### 4.4 分数线 `ParseGT`
不含数字的表头行抽出等级列（A* A B C … G），后续 `Component NN  max  v v v` 和 `选项代码  max  组件列表  v v v` 按等级顺序对齐，`–` 记为 null。

### 4.5 考官报告 `ParseER`
按 `Paper 0580/11` 切卷；卷内按 `Key messages` / `General comments` / `Comments on specific questions` / `Question N` 切段。

### 4.6 几何引擎 `geom.go`
- `mutool draw -F stext`：每个字符的四角坐标 quad、基线 y、字体、字号。
- `mutool trace`：fill_path / stroke_path 及 moveto/lineto/curveto，按 transform 矩阵换算到与 stext 相同的左上角坐标系。
- 细填充矩形（高 < 1.5pt）视为水平线段——Word 导出的分数线就是这种。
- 忽略整页大小的裁剪/背景矩形。
- `FixGlyph`：Symbol/MMGreek 字体及 U+F0xx 私有区码位映射回真实 Unicode（`\uf0b4`→×、`\uf03d`→=、a→α、p→π …），`Ɣ`→`●`。

### 4.7 公式还原 `mathlayout.go`
1. **分数线**：水平、长 3–260pt、线宽 ≤ 1.6，排除表格线（`gridRule`：端点接竖线或同 y 有相邻水平线）。
2. 由短到长处理（嵌套分式从内向外合并）：线上方基线在 1 个字号内 = 分子，下方 0.45–1.5 字号 = 分母；两者宽度要与线长匹配（线长 ≤ 内容宽 + 1.2 字号）。合并成一个 `frac` 记号参与后续排版。
3. **根号**：水平线左端接一条斜线（dy/dx ≥ 0.8，长 < 60）或 `√` 字形，线下内容为被开方数。
4. **上下标**：一行内取主字号字符的基线中位数为参考；字号 < 0.9 主字号且基线抬高 > 0.25 字号 = 上标，降低 > 0.15 字号 = 下标；超过 8 个字符或离前一字符过远则降回正文（防止误把旁注当上标）。
5. **行聚类**：基线差 < 0.45 字号归为一行。
6. 输出每行 `text`（线性：`(1-0.7)/(0.45-0.38)`、`x^2`）和 `latex`（`\frac{}{}`、`^{}`、`\sqrt{}`）。
7. 已验证：`3/7 - 2/21`、`S_∞ = 125/2, 62 1/2`、`7(2xy − y^2)`、`(v − 3)/(−5)`。

### 4.8 图表 `diagram.go`
1. **区域聚类**：路径包围盒外扩 4pt 后相交即合并，过滤 < 30×30pt 的碎片和整页边框。
2. **区域内文字**：外扩 18pt 收集；所在文本行远超出图宽的视为正文，排除。
3. **坐标轴**：数字词中，同基线的一组 = x 轴刻度，右对齐（X1 相同）的一组 = y 轴刻度。要求 ≥ 3 个、数值等差、像素等距（误差 15%），最小二乘拟合 `value = a·pix + b`，r² ≥ 0.995。
4. **柱状图**：区域内矩形路径，顶边用 y 轴换算得到数值，正下方最近的非数字词是类别名。已验证 0580/11 Q1：Climbing=7、Swimming=4、Woodcraft=6。
5. **曲线/数据**：非横平竖直的路径作为 series；两轴都标定时坐标换成数据单位，最多抽样 60 点。
6. **类型**：bar_chart / graph / graph_grid / table / diagram（电路、光路、受力图：输出标签和小曲线形状数量）。

### 4.9 表格 `table.go`
区域内只有横竖线时：竖线 x、横线 y 各自聚类（容差 2pt）得到网格边界，每个词按中心点落入单元格；有字单元格 ≥ 50% 才认为是表格（坐标纸网格大多为空，被排除）。已验证 0580/11 概率表、频数表，0625/42 逻辑门真值表，9702/22 不确定度表。

---

## 5. 学科算法

学科解析器通过 `register("科目代码…", fn)` 注册，`fn(meta, text)` 返回 `(data, ok)`；`ok=false` 时回落到通用解析器。

### 5.1 选择题（所有学科共用，位于 subj_econ.go）
- `ParseMCQKey`：评分标准 `题号  字母  分值` 三列，≥ 15 行即判为选择题答案。
- `ParseMCQQP`：题号顺序递增；选项必须按 A→B→C→D 顺序出现，防止图里的 A/B/W/X 标签被当选项；支持同一行多个选项（`A W and X   B X and Y …`）。
- `isMCQ`：≥ 15 题且一半以上有 4 个选项。
- 已知问题：选项全是图（0455/12 Q7、Q17）或表格中的 ✓/✗ 符号（9708/12 Q4，字体为 Wingdings 码位 \x16/\x1a）时选项为空或乱码 → 待做：用 `-diagram` 按选项字母位置切图；Wingdings 映射表（\x16→✓，\x1a→✗）。
- **已知缺口：答案表只认「带分值」的行**。`mcqKeyRe = ^\s{0,12}(\d{1,2})\s{2,}([A-D])\s{2,}(\d)\s*$` 要求行尾必须有分值数字，且整行只有这三个字段。实测 `0625_s18_ms_11`（40 题、`Maximum Mark: 40`）只解析出 **18 行**：`Marks` 列在多数行是空的（只印在部分行上），加上 `Page 2 of 3` 页脚与某一行同行输出，把该行也挤掉了。`9702_*_ms_11` 同病（18–20/40）。因为 `mcq_key` payload 不带 `checks` 块，回归报告把这些样本记为 `NOC` 而不是 `PASS`。修法：允许行尾无分值，分值按封面 `each correct answer will score one mark` / 题目数补 1，并在行数 != 封面题数时写 warning。

### 5.2 经济 `subj_econ.go`（0455 0987 2281 9708）
- 评分标准分两类：选择题答案 / 结构化题。
- 结构化题每行：题干原文（首个空行前）→ `command_word`（Identify/State/Explain/Analyse/Assess/Discuss/Evaluate…）→ 得分点（按空行分块，以 `(1 mark)` / `(Up to 3 marks)` 结尾）→ 上限 `Maximum of 2 marks if …` → 分级 `Level 3  5–6 …` → `AO1–AO4` → Guidance 列。
- 文档开头的通用分级表单独输出到 `levels`。
- 得分点分值：以 `(1 mark)` / `(Up to 3 marks)` 结尾，或**末尾裸 `(1)`**（IGCSE 内联写法，`bareCritRe`，只认句尾，避免吃掉正文里的 `(2)`）。
- 已解决（原“已知问题”两项）：封面选做规则 → `optional_groups` / `effective_total`（9708_s22_qp_22 = 40、0455_s22_qp_22 = 90）；裸 `(1)` 计入该得分点分值。
- 已知问题：0455/22 这类经济卷表头排成两行（`Question  Answer  …  Guidance` 一行、`Marks` 落在下一行，且分值列在 `Marks` 词右侧约 20 列），`msHdr2` 要求四个词同一行 → 只有少数页被识别，多数题目缺失、`marks` 为空、得分点不全；暂未修（要按数据行自适应列位置，风险高）。

### 5.3 物理 `subj_phys.go`（0625 0972 5054 9702）
- 试卷：每题附加 `figures`（Fig. 3.1 / Table 2.1）、`command_words`、`answer_lines`（`energy = ....... J [3]` → 符号、单位、分值）。
- 评分标准：`A3,C1,C1` 表示答对得 3 分，C1 是答错时按公式给的补偿分，**不累加**（`physRowMarks`）；答案去掉 `(E =)` 前缀后拆 `value` + `unit`；抽取有效数字要求、allow/ignore/ecf/owtte 等规则。
- 校验（199 样本回归实测，见 `docs/TEST_REPORT.md`）：选择题答案表 `0625_*_ms_11/21` 只解析出 18–19/40，`9702_*_ms_11` 为 18–20/40，且 payload 无 `checks` 块 → 报告记 `NOC`（见 §5.1 缺口）。结构化评分标准几乎全部未解析出分值列：`0625_*_ms_31/41` 为 0–190/80，`9702_*_ms_21/31/41/51` 为 0/30–100（见 §4.3 缺口二）。**历史手测的 0625/42 = 80/80、9702/22 = 60/60 无法用本回归复核**——清单只收 variant 1（`_11`/`_21`/…），这两个是 variant 2。
- 已知问题：A-Level 答案多是推导式（`v2 = u2 + 2as …`），value/unit 抽不出 → 应先过 `-math` 拿到 LaTeX，取最后一个 `=` 右边。

### 5.4 数学 `subj_math.go`（0580 0980 0606 0607 4024 4037 9709 9231）
- 试卷：精度要求（correct to 4 significant figures）、是否必须写过程、知识点（关键词表）、答案线类型（数值 / `x = …` / 坐标 `( … , … )`）。
- 评分标准：每个代码解码为 `kind`（method/accuracy/independent/compensation/special_case）、`value`、`star`（*M1，后续 D 分依赖它）、`dependent`（DM1/DB1）；注释 oe/cao/ft/isw/nfww/soi/awrt/www/dep/AG。
- 公式：评分标准里的答案交给 `mathlayout` 输出 LaTeX。

---

## 6. 构建与运行（iSH 注意事项）

```bash
apk add go poppler-utils mupdf-tools python3
cd cie/cieparse
GOMAXPROCS=1 GOFLAGS=-p=1 CGO_ENABLED=0 GOGC=50 go build -o /tmp/cieparse .   # iSH 多线程编译会崩
/tmp/cieparse -j 2 -o out.json ../../cie_papers     # 批量解析目录
/tmp/cieparse -math -page 6 file.pdf               # 单页公式
/tmp/cieparse -diagram file.pdf                    # 图表/表格
/tmp/cieparse -name 9709_w23_ms_32.pdf             # 只解析文件名
```
`/var/minis/workspace` 下不能执行二进制，输出到 /tmp。普通 Linux/macOS 直接 `go build` 即可。

## 7. 回归测试方法

样本清单在 `testdata/manifest.json`（PDF 不入库，先跑 `tools/fetch_testdata.py` 下载到 `testdata/pdf/<科目>/`）。当前 199 份 = 6 个学科 × 3 季（s18 / s23 / w23）× variant 1，含 qp / ms / gt / er。

三个命令，各管一件事：

```bash
cd cie/cieparse
go test -skip TestRegression ./...                     # 单元测试（约 6s）
go test -run TestRegression -timeout 30m ./...         # 断言回归：cover 字段、总分、checks 契约
cd cie
python tools/run_regression.py                         # 人读报告 → docs/TEST_REPORT.md + testdata/report.json
python tools/run_regression.py 0580 9709               # 只跑指定科目
python tools/cmp.py testdata/pdf/0580/0580_s23_qp_11.pdf testdata/pdf/0580/0580_s23_ms_11.pdf   # 单份逐题对照
```

`regression_test.go` 是**断言契约**，`run_regression.py` 是**诊断报告**（同一份 PDF 的两个视角，结论应一致）。报告里两类校验必须分清：

- **自校验**：封面总分 vs 解析出的分值合计。两个数字来自同一份 PDF，只能抓「解析器自相矛盾」，抓不到「解析器看错了卷子」。
- **跨文档校验**（`逐题一致` 列）：qp 与 ms 两份独立 PDF 的逐题分值对照。这才是强校验。

状态语义见报告开头；要点：`PASS` 只表示「校验过且一致」，`WARN` 表示「不一致但解析器写了 warning」，`NOC` 表示「payload 没有 `checks` 块，根本没校验」，`N/A` 表示「gt/er 没有 header，无从校验」。把 `NOC` 当 `PASS` 读是这份报告最容易踩的坑。

### 2026-10 全量结果（199 样本，`docs/TEST_REPORT.md` 为准）

| 状态 | 数量 | 含义 |
|---|---|---|
| PASS | 11 | 82 份 qp 中 11 份自校验一致（含 5 份经济选做题 `effective_total`） |
| WARN | 101 | 90 份合计与封面不符 + 11 份旧卷封面无数字总分（合规） |
| FAIL | 0 | 无「校验失败且无 warning」 |
| KNOWN | 6 | 见 `manifest.json` 的 `known_failures` |
| DIFF | 22 | 自校验 OK 但跨文档逐题对不上（18 份 9709、3 份 0455、1 份 9708） |
| NOC | 24 | 无 `checks` 块：11 份 `mcq_key`、13 份经济结构化 MS |
| N/A | 35 | 17 份 er + 18 份 gt |

分科：0580 0/24、9709 1/19、0625 4/23、9702 1/25、0455 1/4、9708 4/6（PASS/WARN，不含 NOC/N/A）。**82 份 ms 样本没有一份通过自校验**，这是当前最大的缺口（§4.3）。

注意事项：

- `manifest.json` 的 `expect.total_mark` 目前全部为空，`TestRegression` 里的 `total_mark` 断言因此不生效。回填只能由 `--update` 用**封面解析值**写入，属「封面 vs 封面」的同源比较，只能防封面解析回归，不能替代独立基准——需要独立基准时应从数据源元数据或人工核对取得。
- `-math` / `-diagram` 相关输出（§4.7、§4.8）**未纳入本回归**：需要 `mutool`，而本机没有。
- 逐题对照对经济卷不是同一口径（ms 侧是 Level 分级给分），经济样本的 `DIFF` 需另行判断。

## 8. 待办
- ~~fraft 数据源接入 `cie_api.py`（`--source fraft`），并作为默认源~~ → **已完成**：`--source` 默认 fraft，异常自动回退 papa 并在输出里记 `fallback`
- ~~选做题规则（Section B answer one / two）~~ → **已完成**：`optional_groups` / `effective_total`，单行与两行封面版式都支持
- **MS 分值列右界**（§4.3 缺口一）：0580 近年的 `Marks` 列右对齐，超出「词尾 + 4 列」的判定范围，分值被并入 `answer`。修法：分值单元格右界取到下一个表头词的列号，并要求单元格内除分值记号外没有别的词
- **MS 表头跨行**（§4.3 缺口二）：0625 / 9702 / 0455 的 `Question` / `Marks` / `Answer` 印在三行上，分值列位置未知。重设计单元格边界时要同时验证两个方向：`0625_s18_ms_41` 的 344/80（过收）与 `0625_w23_ms_41` 的 190/80（过收）
- **选择题答案表**（§4.3 缺口三 / §5.1）：`mcqKeyRe` 要求行尾带分值，`0625_*_ms_11` 只解析出 18/40。改成允许行尾无分值（按封面「each correct answer will score one mark」补 1），行数 != 封面题数时写 warning
- **经济结构化 MS 无 `checks` 块**：`EconMS` 没有 `Checks` 字段，13 份经济 ms 样本在回归里只能是 `NOC`。若要校验，需要按 Level 制给分口径定义「合计」的含义（现在的 `marks_sum` 对这类卷恒为 0）
- Wingdings / ZapfDingbats 符号映射（9708/12 Q4 的 ✓/✗）
- 选项为图片的选择题：按选项字母坐标切分图形区域
- 物理与 A-Level 推导式答案：先过 `-math` 拿 LaTeX，取最后一个 `=` 右边
- 化学结构式（苯环、键线）识别：路径中 6 条等长线段闭合 = 苯环
- 其余学科见 `SUBJECT_PROMPTS.md`
