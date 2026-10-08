# 其余学科解析算法开发提示词

> 用法：把「通用前置提示词」+ 对应学科的提示词一起发给 AI 编程助手（或作为自己开发的需求清单）。
> 参考实现：`cieparse/subj_math.go`、`subj_phys.go`、`subj_econ.go`。新学科都按这三个文件的写法来。

---

## 0. 通用前置提示词（每个学科都要带上）

```
你在为 Go 项目 cieparse 增加一个学科解析器，文件名 subj_<学科>.go，package main。

已有可复用的函数和类型（不要重写）：
- ParseFilename(path) FileMeta              文件名 → 科目/年/季/类型/卷号
- header(txt) Header                        封面：科目、卷别、考试季、时长、总分
- ParseQP(txt) QPData                       试卷骨架：题号、小题、[n] 分值，带总分校验
- ParseMSCol(txt) MSData                    按列位置解析评分标准表（题号/答案/分数/说明），支持备选解法、小计行
- ParseMCQQP(txt) / ParseMCQKey(txt) / isMCQ  选择题试卷与答案
- physQuestionBlocks(txt, qs) map[int]string 每道题的原始文本块
- LoadPage(pdf, n) *Page                    每个字符的坐标/字体/字号 + 矢量路径
- PageMath(p) []MathLine                    分式/根号/上下标 → 文本 + LaTeX
- PageDiagrams(p) []Diagram                 图表区域、坐标轴、柱状图、曲线、表格
- clean, uniqAdd, msLine, hdrCols, noiseRe, markRe, qStartRe

规则：
1. 用 func init(){ register("科目代码 空格分隔", fn) } 注册；fn(meta FileMeta, txt string) (interface{}, bool)，
   不认识的文件类型返回 false，交回通用解析器。
2. 不准用 OCR，只用文字坐标和矢量路径。
3. 每种输出都要有自校验字段：试卷 marks_sum vs header.total_mark；评分标准合计 vs 满分；
   选做题按封面 “Answer N questions” 规则单独计算。校验不过时输出 warnings，而不是悄悄丢数据。
4. 用真实 PDF 测试：同一季 qp + ms（每个 Paper 至少 1 份）+ gt + er。
   PDF 来源：https://cie.fraft.cn/obj/Common/Fetch/redir/<文件名>
   或 https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/<文件名>
5. 构建：GOMAXPROCS=1 GOFLAGS=-p=1 CGO_ENABLED=0 go build -o /tmp/cieparse .
6. 输出 JSON 字段名用 snake_case，空字段用 omitempty。
7. 交付：代码 + 测试的文件列表 + 每份文件的校验结果 + 已知问题。
```

### 写学科算法的固定步骤（从数学/物理/经济总结出来的）
1. **先看版式**：`pdftotext -layout` 看 qp 和 ms 各 3 页，列出该科的题型（选择题 / 结构化 / 论述 / 实验 / 编程 / 语言阅读写作）。
2. **定分值规则**：评分标准里分数怎么写（数字、M1/A1、C1 补偿、Level 分级、(1) 内联、“any two from”）。先让 `numeric_marks_sum == 满分` 成立，这是最可靠的正确性检查。
3. **定学科特有字段**：比如物理的单位、数学的精度要求、经济的 command word 和分级。
4. **再处理图形**：该科有哪些图（电路、曲线、结构式、地图、流程图），先用 `-diagram` 看输出，缺什么补什么。
5. **最后写已知问题**：哪些题型还抽不出来、原因是什么。

---

## 1. 化学（0620 0971 5070 9701）
```
参考 subj_phys.go 写 subj_chem.go，注册 "0620 0971 5070 9701"。
题型：P1/P2 选择题（复用 ParseMCQQP/ParseMCQKey）；P3/P4 结构化；P5/P6 实验；A-Level P3 实验、P4/P5 结构化与计划。
试卷字段：
- equations：方程式行（含 →、⇌、+，状态符号 (s)(l)(g)(aq)），下标数字（H2O 中的 2，用 PageMath 的下标识别）还原为 H₂O 和 LaTeX H_2O
- ions：上标电荷（SO4^2−、Na^+），注意 2− 与 −2 的顺序
- 答案线单位：mol、g/dm3、cm3、kJ/mol
- 图：实验装置（diagram）、曲线（graph，如速率、滴定）、周期表（最后一页，固定跳过或单独输出）
- 结构式：路径中 6 条等长线段闭合成正六边形 = 苯环；短线段连接字母 C/H/O = 键；双线平行 = 双键。输出原子标签 + 键列表（邻接表）
评分标准字段：
- M1/M2… 行内编号（0620/42 Q2(d)(iv) 那种 “M1 Mol HCl = …”）拆成分步得分点
- “any two from” / “max N” / “ignore state symbols” / “ecf” 规则
- 方程式答案配平校验：左右原子计数相等（可作为 warning）
校验：0620/42 = 80/80 曾在通用层手测成立（**本回归未复核**：`testdata/manifest.json` 只收 0580 / 9709 / 0625 / 9702 / 0455 / 9708 的 variant 1，不含 0620 / 9701）；新增 P6、9701 P2/P4 的校验。
```

## 2. 生物（0610 0970 5090 9700）
```
写 subj_bio.go，注册 "0610 0970 5090 9700"。
题型：选择题；结构化（大量短答 + 图注）；实验（P5/P6、A-Level P3 绘图题）。
试卷字段：
- label_lines：图上的引线（细直线一端在图内、一端接字母 A/B/C 或空白横线）→ 输出 {标签, 指向坐标}
- 表格（table.go）：实验数据表，表头含单位 “/ s”“/ °C”
- graph：需要学生画图的空坐标纸（graph_grid）单独标 drawing_required=true
- command words：state, describe, explain, suggest, compare, outline
评分标准字段：
- 分号 “;” 分隔的得分点（每个 ; 通常 1 分），配合 “max N”
- “A” = accept，“R” = reject，“I” = ignore，“AW” = alternative wording，“ORA” = or reverse argument：拆成 accept/reject 列表
- 编号得分点 “1 …  2 …  3 …”（max 4）
校验：得分点数 ≥ 该题分值；合计 = 满分。
```

## 3. 综合科学 / 联合科学（0653 0654 5129）
```
写 subj_sci.go，复用 bio/chem/phys 的字段提取函数：按题目文本中关键词判断子学科（生物/化学/物理），再调对应的 enrich 函数。
```

## 4. 计算机（0478 0984 9608 9618 2210）
```
写 subj_cs.go，注册 "0478 0984 9608 9618 2210"。
题型：理论（结构化）、算法与编程（伪代码、流程图、跟踪表 trace table）。
试卷字段：
- code_blocks：等宽字体（CourierNew/Courier 前缀，从 Char.Font 判断）的连续行 = 伪代码，保留缩进（按 x 坐标 / 字宽换算空格数）
- 关键字检测：DECLARE, IF…THEN…ENDIF, FOR…NEXT, WHILE, REPEAT…UNTIL, PROCEDURE, FUNCTION, RETURNS
- trace_table：table.go 输出的表格中表头为变量名的 → trace table，空单元格是待填
- flowchart：diagram 里的矩形/菱形（4 点非矩形且对角线水平垂直 = 菱形）/圆角矩形 + 带箭头线段 → 节点 + 边（箭头端 = 线段终点附近的小三角形填充路径）
- 逻辑门：AND/OR/NOT 图形形状（含曲线的闭合路径）+ 真值表
- 二进制/十六进制数字串保持原样，不要被数字解析
评分标准字段：
- “1 mark per bullet point”、“max N”、程序题 “1 mark for each of the following”
- 代码答案保留缩进；示例答案 “Example answer” 单独字段
```

## 5. 附加数学 / 进一步数学 / 统计（0606 4037 9231 9231 0607 已注册；9709 统计卷 P5/P6）
```
在 subj_math.go 内扩展，不新建文件：
- 统计卷：正态分布表、二项分布参数（B(n, p)），抽 distribution 字段
- 矩阵（9231）：方括号/圆括号由两条竖直曲线路径组成，内部数字按行列网格排 → LaTeX \begin{pmatrix}
- 向量列（0580/0606）：两行数字被大括号包住 → \begin{pmatrix}a\\b\end{pmatrix}
- 积分号 ∫ 与上下限：大字号 ∫ 字形右上/右下的小字号字符 = 上下限
- 求和 ∑ 同理
```

## 6. 商科（0450 7115 9609）与会计（0452 7707 9706）
```
参考 subj_econ.go 写 subj_bus.go / subj_acc.go。
商科：
- 案例材料（insert 文件 _in_）单独解析：Appendix 1/2、表格（table.go），给题目关联 appendix 引用
- 评分标准：Level 1–3 分级 + AO1 Knowledge / AO2 Application / AO3 Analysis / AO4 Evaluation 分列表格（列号用 hdrCols 思路扩展到 AO 列）
- “k” “app” “an” “eval” 行内标记
会计：
- 账户格式（T 型账、试算平衡表、利润表）：table.go 或按列对齐的金额列（右对齐数字、千分位逗号、括号负数 (1 200)）
- 评分标准里金额后的 “(1)” “(1OF)” = own figure 分：OF 类似 ft
- 输出 statements: [{title, rows:[{label, amount, col}]}]，校验借贷合计相等
```

## 7. 地理（0460 2217 9696）
```
写 subj_geo.go。
- insert 里有地图、照片（照片是图片，只记录 image 位置和图号 Fig./Photograph）
- 地形图：网格参考 “GR 123456”、比例尺、指北针 → 抽 grid_refs
- 图表：气候图（柱+线双轴，y 轴左右各一组刻度，diagram.go 需扩展第二条 y 轴）、三角图、人口金字塔（左右对称横向柱）
- 评分标准：Level marking（L1/L2/L3 + 分值区间）、“1 mark per valid point, max N”、“dev” 发展分
```

## 8. 历史（0470 2147 9489）
```
写 subj_hist.go。
- 试卷：Section/Option（Depth Study A–F）选做规则，题目通常 “(a) 4 (b) 6 (c) 10” 固定结构
- Source（Source A/B…）材料块：从 “Source X” 标题到下一个标题之间，附出处行（斜体，Char.Font 含 Italic）
- 评分标准：Level 1–5 描述 + 分值区间 + “Indicative content”，按 Level 解析（复用 parseLevel）
- 选做校验：只按 “Answer N questions” 计满分
```

## 9. 英语与语言类（0500 0510 0511 0990 0991 9093 及外语 0520 0525 0530 0547 等）
```
写 subj_lang.go。
- 阅读材料（insert）：段落还原（按行距与首行缩进合并），保留行号（左侧小字号数字 5、10、15 = 行号，必须从正文剥离并单独输出 line_numbers）
- 写作题：只输出题目要求、字数要求（“200–300 words”）、文体（letter/article/speech）
- 评分标准：Reading / Writing 两张 Level 表（分值区间 + 描述），以及逐题 “Award 1 mark for…” 答案列表
- 听力（0510/0511 P4）：transcript 文件按说话人（V1/V2/M/F 加冒号）切分
- 外语：非拉丁字符（中文 0509、阿拉伯语 RTL：stext 的 bidi/dir 属性）保持原序；阿拉伯语需按 dir=-1 反转行内顺序
```

## 10. 其他（体育 0413、社会学 0495/9699、心理学 9990、艺术 0400、旅游 0471、环境管理 0680、法律 9084 等）
```
统一写 subj_essay.go：
- 试卷：题号 + 小题 + 分值（ParseQP），资料块（Source/Fig./Table）
- 评分标准：Level 表 + 指示内容（indicative content），以及短答题的 “1 mark per point” 列表
- 艺术类只有 ci/pm（考试说明/命题主题）文件：输出主题列表即可
- 心理学：研究名称（Core Study）关键词表，题目关联研究
- 环境管理 0680：复用 geo 的图表与 bio 的得分点规则
```

---

## 11. 交付检查清单（每个学科）
| 项目 | 要求 |
|---|---|
| 注册 | init() 中 register 全部相关科目代码 |
| 试卷 | marks_match_total=true（选做题按规则） |
| 评分标准 | 合计 = 满分；无 marks 为空的行（备选解法除外） |
| 学科字段 | 至少 3 个该科特有字段，并在 3 份不同年份的 PDF 上验证 |
| 图表 | 抽查 2 个图、1 个表格的 -diagram 输出 |
| 文档 | 在 DESIGN.md 第 5 节追加一小节：题型、算法、校验结果、已知问题 |
