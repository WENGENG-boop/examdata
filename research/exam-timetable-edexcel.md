# Edexcel 考试时间表（历年）：调研与接口报告

- 生成日期：2026-10-05
- 机器可读数据：`src/examdata/timetable/data/edexcel/index.json` + 106 个单季 JSON（`gcse/`、`intgcse/`、`ial/`、`gce/` 四个子目录，含 13 份 R 卷 `-r.json`）
- 探针与原件（不入库）：`tmp_edexcel_tt_probe/`——`downloads/edexcel/<family>/` 源 PDF、`downloads/edexcel_manifest.json` 抓取清单、`validate_round3.txt` 全量解析验证输出
- 相关接口：`GET /api/v1/timetable/seasons`、`GET /api/v1/timetable`、`GET /api/v1/timetable/windows`（均带 `board=edexcel&family=…`）

## 1. 结论摘要

- 已落盘 **106 个考季**，共 **8479 条结构化事件**、**23 个日期窗口**；四族谱：UK GCSE 22 季 / 2127 条，International GCSE 37 季 / 2129 条（含 13 份 R 卷），International A Level 34 季 / 2224 条，GCE A-level 13 季 / 1999 条。
- **6 个考季因 COVID-19 取消**（2020/2021 夏季系列，逐条给官方口径，见 §4）；**15 个考季经穷尽检索后确认不可得**（逐条给理由与检索证据，见 §5）。
- 时间跨度：2015-01（IntGCSE R 卷）… 2027-06（现行官网文件）；来源为 Wayback 存档 97 季 + Pearson 官网直连 9 季（2026-11 起最新三季）。
- 未解析行仅 **4 条（条目级）**，均因源 PDF 自身缺代码/拼写错/时长对不齐，原样记录、不猜测（见 §6）；全量零事件的考季：无。
- 抽样核对（IAL / GCSE / GCE / 最新 live 季共 4 处 20+ 行）与来源原件完全一致（见 §7）。
- 接口实测：`board=edexcel` 各端点 200，取消季 404（带 cancelled 标记）、不可得季 404（带 reason/evidence）、非法参数 422（见 §8）。

## 2. 范围与方法

- 来源：Pearson 官网现行可下载文件（`live`）+ Wayback Machine 存档（历年下架文件）；每季记录 URL、fetch_url、source_kind、sha256、页数、label（final/provisional 共 102/4；另有 3 季在 `extra_sources` 记录了同季 provisional 文件）。
- 族谱与键：`<family>|<year>|<month>`，如 `ial|2026|06`；IntGCSE 部分季有 R 卷变体，键加 `|R`（如 `intgcse|2015|01|R`），对应独立的 `-r.json` 快照与 `r_paper=true` 查询参数。
- 解析（`src/examdata/timetable/edexcel_parser.py`）：pymupdf `find_tables()` 按表头语义列定位；按版式自动分支——早期 `old_grid`（无框线旧网格）、中期 `index_tables`（含目录页与噪声表）、近期 `modern`（2020-11 起新版式）；R 卷文件走同一解析器。
- 日期规则：表内"日 + 月"（如 `Friday 22 May`）结合考季年份与月分组推断；无法解析的日期单元格进入 `unparsed_rows`。
- 时长：`0h 25m` / `1h 30m` 等原文 → `duration_minutes`；当年份与**考试条目数**不一致时不整体丢弃，而是把该行整体记入 `unparsed_rows`（时长置空）。
- 上游请求走仓库 Fetcher 约束（robots、限速、单工作线程）。

## 3. 覆盖明细（106 季）

### gcse —— 22 季 / 2127 事件 / 0 窗口

| 考季 | 事件 | 窗口 | 未解析 | 来源 | 页 | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| 2015-06 | 147 | 0 | 0 | wayback | 25 | 60b6c90ed732… |
| 2015-11 | 14 | 0 | 0 | wayback | 7 | 5f8f02072353… |
| 2016-06 | 146 | 0 | 1 | wayback | 25 | c1a2d90c4ba5… |
| 2017-06 | 148 | 0 | 0 | wayback | 25 | b2a35f157a36… |
| 2017-11 | 8 | 0 | 0 | wayback | 7 | 9f72bf5ee995… |
| 2018-01 | 12 | 0 | 0 | wayback | 8 | 8a89888ca6b7… |
| 2018-06 | 130 | 0 | 0 | wayback | 28 | 11e3982c7588… |
| 2019-06 | 141 | 0 | 0 | wayback | 26 | 7e003451ed58… |
| 2019-11 | 8 | 0 | 1 | wayback | 7 | e0a653780333… |
| 2020-11 | 167 | 0 | 0 | wayback | 29 | d79de0bb76e8… |
| 2021-11 | 172 | 0 | 0 | wayback | 29 | b8bb02447df3… |
| 2022-06 | 174 | 0 | 0 | wayback | 30 | a7148d13fa25… |
| 2022-11 | 10 | 0 | 0 | wayback | 7 | 7863776149e9… |
| 2023-06 | 162 | 0 | 0 | wayback | 29 | 3f37017a287e… |
| 2023-11 | 10 | 0 | 0 | wayback | 7 | 7201d0e260d4… |
| 2024-06 | 162 | 0 | 0 | wayback | 30 | 854c1d0d6837… |
| 2024-11 | 10 | 0 | 0 | wayback | 7 | 9da2796bb25d… |
| 2025-06 | 162 | 0 | 0 | wayback | 28 | 26ad39850513… |
| 2025-11 | 10 | 0 | 0 | wayback | 7 | a368e285580d… |
| 2026-06 | 162 | 0 | 0 | wayback | 28 | ca2d7ea6b8cd… |
| 2026-11 | 10 | 0 | 0 | live | 7 | a16ae71d3c6f… |
| 2027-06 | 162 | 0 | 0 | live | 28 | dd43f8fbbe7b… |

### intgcse —— 37 季 / 2129 事件 / 2 窗口（`|R` 为 R 卷变体）

| 考季 | 事件 | 窗口 | 未解析 | 来源 | 页 | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| 2015-01\|R | 6 | 0 | 0 | wayback | 6 | 70d2feb5c47c… |
| 2015-06 | 62 | 0 | 0 | wayback | 24 | 5879e9130262… |
| 2016-01 | 30 | 0 | 0 | wayback | 12 | 81b0cd8dc6ab… |
| 2016-06 | 62 | 0 | 0 | wayback | 24 | 3006a7b08751… |
| 2017-01 | 30 | 0 | 0 | wayback | 13 | 8eaa2a70c7fd… |
| 2017-06 | 61 | 1 | 0 | wayback | 24 | bb53528a5078… |
| 2018-01 | 30 | 0 | 0 | wayback | 14 | 0c3c54290c64… |
| 2018-06\|R | 36 | 0 | 0 | wayback | 13 | 4f5ce409b934… |
| 2018-06 | 72 | 1 | 0 | wayback | 23 | 292f0bdfd15d… |
| 2019-01 | 41 | 0 | 0 | wayback | 14 | 140a6854e2b3… |
| 2020-01\|R | 26 | 0 | 0 | wayback | 4 | 98d811f2e333… |
| 2020-01 | 35 | 0 | 0 | wayback | 5 | 28cf5283c7e6… |
| 2020-06\|R | 47 | 0 | 0 | wayback | 5 | 03e90495a183… |
| 2020-11\|R | 47 | 0 | 0 | wayback | 17 | ed646e9d5ebf… |
| 2021-01 | 15 | 0 | 0 | wayback | 10 | 3721ea93a396… |
| 2021-06\|R | 49 | 0 | 0 | wayback | 18 | 37fde5242511… |
| 2021-06 | 72 | 0 | 0 | wayback | 18 | a42e580b6a56… |
| 2021-11 | 60 | 0 | 0 | wayback | 19 | 182d4d3f029e… |
| 2022-01\|R | 22 | 0 | 0 | wayback/provisional | 12 | 3b1ed22f4e27… |
| 2022-01 | 24 | 0 | 0 | wayback | 17 | 75ac47af9e4b… |
| 2022-06\|R | 49 | 0 | 0 | wayback | 19 | 174eebad2e06… |
| 2022-06 | 78 | 0 | 0 | wayback | 22 | 03e06d30943d… |
| 2023-01\|R | 26 | 0 | 0 | wayback/provisional | 11 | 4888c4d4c4ed… |
| 2023-01 | 35 | 0 | 0 | wayback | 14 | 07fc5727e882… |
| 2023-06 | 76 | 0 | 0 | wayback | 21 | f7245dec2883… |
| 2023-11 | 51 | 0 | 0 | wayback | 18 | 58457b550065… |
| 2024-06\|R | 61 | 0 | 0 | wayback | 20 | 67a71415ef60… |
| 2024-06 | 102 | 0 | 0 | wayback | 23 | c29cc0b29e42… |
| 2024-11 | 65 | 0 | 0 | wayback | 18 | ebd7f9d58c02… |
| 2025-06\|R | 80 | 0 | 0 | wayback | 21 | 8430744fb0db… |
| 2025-06 | 121 | 0 | 0 | wayback | 25 | a2676bc38d7d… |
| 2025-11 | 82 | 0 | 0 | wayback | 19 | 246a225e7987… |
| 2026-06\|R | 78 | 0 | 0 | wayback/provisional | 20 | 194b29f191f5… |
| 2026-06 | 119 | 0 | 0 | wayback | 25 | 5e31fc8f731f… |
| 2026-11 | 82 | 0 | 0 | live | 19 | 1d00c971116e… |
| 2027-06\|R | 78 | 0 | 0 | live | 20 | 83ba5bf237fe… |
| 2027-06 | 119 | 0 | 0 | live | 23 | 95250a958e9b… |

### ial —— 34 季 / 2224 事件 / 11 窗口

| 考季 | 事件 | 窗口 | 未解析 | 来源 | 页 | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| 2016-01 | 37 | 0 | 0 | wayback | 13 | 1e8fe13674fc… |
| 2016-06 | 51 | 0 | 0 | wayback | 18 | 2ad177e6f719… |
| 2016-10 | 27 | 0 | 0 | wayback | 16 | 7347b00dd8f8… |
| 2017-01 | 53 | 0 | 0 | wayback | 14 | 5d415e432c5c… |
| 2017-06 | 71 | 1 | 1 | wayback | 22 | 58e98b6872df… |
| 2017-10 | 44 | 0 | 0 | wayback | 17 | 2bb72379bd9d… |
| 2018-01 | 66 | 6 | 0 | wayback | 18 | 3a6cc844eaf1… |
| 2018-06 | 72 | 2 | 1 | wayback | 21 | e18ba819238c… |
| 2018-10 | 44 | 0 | 0 | wayback | 17 | 4e91eff4d901… |
| 2019-01 | 73 | 0 | 0 | wayback | 16 | c554054353cd… |
| 2019-06 | 90 | 2 | 0 | wayback | 22 | 6643dd2e4077… |
| 2019-10 | 46 | 0 | 0 | wayback | 17 | 233b4b56eea3… |
| 2020-01 | 63 | 0 | 0 | wayback | 9 | 2f70711a90d0… |
| 2020-10 | 74 | 0 | 0 | wayback | 15 | 8d737b5bacab… |
| 2021-01 | 72 | 0 | 0 | wayback | 18 | 536d01710c7b… |
| 2021-06 | 78 | 0 | 0 | wayback | 18 | 648a93742c62… |
| 2021-10 | 48 | 0 | 0 | wayback | 13 | 9e0b7d95a2f8… |
| 2022-01 | 84 | 0 | 0 | wayback | 18 | 140c5148ca53… |
| 2022-06 | 90 | 0 | 0 | wayback | 20 | 54462acd4380… |
| 2022-10 | 36 | 0 | 0 | wayback | 11 | fdb3a2f86bd3… |
| 2023-01 | 82 | 0 | 0 | wayback | 17 | 7605f25d245a… |
| 2023-06 | 90 | 0 | 0 | wayback | 20 | f30255e3ef21… |
| 2023-10 | 36 | 0 | 0 | wayback | 11 | 951c77e8fe69… |
| 2024-01 | 82 | 0 | 0 | wayback | 17 | fe1b8ea30bea… |
| 2024-06 | 90 | 0 | 0 | wayback | 20 | e0647f9ca7de… |
| 2024-10 | 36 | 0 | 0 | wayback | 12 | db46fc064097… |
| 2025-01 | 81 | 0 | 0 | wayback/provisional | 15 | 09ff6f99a7e7… |
| 2025-06 | 90 | 0 | 0 | wayback | 20 | ee8b81c26303… |
| 2025-10 | 36 | 0 | 0 | wayback | 12 | 135451727b5f… |
| 2026-01 | 82 | 0 | 0 | wayback | 17 | e665b38f151a… |
| 2026-06 | 90 | 0 | 0 | wayback | 20 | dedc35e0aba8… |
| 2026-10 | 36 | 0 | 0 | live | 12 | 842ed812925f… |
| 2027-01 | 82 | 0 | 0 | live | 18 | cc3f49f342f0… |
| 2027-06 | 92 | 0 | 0 | live | 20 | 05bfe109b218… |

### gce —— 13 季 / 1999 事件 / 10 窗口

| 考季 | 事件 | 窗口 | 未解析 | 来源 | 页 | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| 2015-06 | 122 | 2 | 0 | wayback | 26 | 6c2f58ad00d8… |
| 2016-06 | 146 | 2 | 0 | wayback | 26 | 54302efbce19… |
| 2017-06 | 196 | 3 | 0 | wayback | 29 | 79da9676ab68… |
| 2018-06 | 192 | 3 | 0 | wayback | 33 | 657043c6d45f… |
| 2019-06 | 187 | 0 | 0 | wayback | 31 | 9f6fbc4482b9… |
| 2020-10 | 173 | 0 | 0 | wayback | 30 | 4de934c772d3… |
| 2021-11 | 119 | 0 | 0 | wayback | 26 | 877880c3368a… |
| 2022-06 | 144 | 0 | 0 | wayback | 30 | 0c41f5d24123… |
| 2023-06 | 144 | 0 | 0 | wayback | 30 | 8d5e6636624f… |
| 2024-06 | 144 | 0 | 0 | wayback | 29 | c05e58a254b8… |
| 2025-06 | 144 | 0 | 0 | wayback | 27 | 7d71907f8a27… |
| 2026-06 | 144 | 0 | 0 | wayback | 27 | 15d2a7854e9b… |
| 2027-06 | 144 | 0 | 0 | live | 28 | 003441fa6b45… |

合计：**106 季 / 8479 事件 / 23 窗口 / 4 未解析条目**。注：GCE 的 2020-06/2021-06 与 IAL、GCSE、IntGCSE 的 2020-06 均为取消季（§4，不出现在上表）。

## 4. 已取消考季（6，COVID-19）

| 考季 | 官方口径（快照 `cancelled[].reason`） |
| --- | --- |
| gce\|2020\|06 | UK GCE A-level summer 2020 series cancelled (COVID-19); grades awarded by centre assessment |
| gce\|2021\|06 | UK GCE A-level summer 2021 series cancelled (COVID-19); teacher-assessed grades |
| gcse\|2020\|06 | UK GCSE summer 2020 series cancelled (COVID-19); grades awarded by centre assessment |
| gcse\|2021\|06 | UK GCSE summer 2021 series cancelled (COVID-19); teacher-assessed grades |
| ial\|2020\|06 | International A Level May/June 2020 series cancelled (COVID-19) |
| intgcse\|2020\|06 | International GCSE May/June 2020 series cancelled (COVID-19) |

接口语义：对取消季返回 404，body 带 `cancelled: true` 与 `reason`（与"不可得"区分的显式标记）。

## 5. 不可得考季（15，已穷尽检索）

穷尽检索口径（探针 `tmp_edexcel_tt_probe/`：CDX 目录扫描 `probe_cdx_*`、官网直连、快照内容校验 `probe_content_check.py`；证据文件在 `evidence/`）：

1. **CDX 目录页扫描**：四个族谱的 Examination-timetables 目录及其子目录（含 `for-UK-Edexcel-GCSE` / `for-Edexcel-International-GCSE` 等变体）；
2. **Wayback 快照内容校验**：候选逐个 replay 并校验是否为可用 PDF（`not-pdf` / 302 跳转 / 校验失败均记为无效）；
3. **官网直连**：对现行站点上仍可访问的候选逐一尝试；
4. **文件名快照搜索**：在快照索引中按已知文件命名模式（如 `*R*paper*`）搜索到文件名但无 CDX 抓取时，判定为"曾存在但未被抓取"。

| 考季 | 理由（摘要） | 证据 |
| --- | --- | --- |
| gcse\|2016\|01 | 扫描全部 CDX 目录后无 1 月季存档文件 | — |
| gcse\|2016\|11 | 穷尽候选（Wayback + 官网直连）后无可用 PDF（非 PDF 或校验失败） | 4 条 |
| gcse\|2017\|01 | 无 1 月季存档文件 | — |
| gcse\|2018\|11 | 无 2018-11 存档（2015/2017/2019+ 有，2016 仅 302） | — |
| intgcse\|2015\|01 | 仅 R 卷文件被存档，标准卷未捕获 | 1 条 |
| intgcse\|2016\|06\|R | 快照中见过 R 卷文件名（7741_IGCSE_R_Paper_June_2016），无 CDX 抓取 | — |
| intgcse\|2017\|01\|R | 同上（iGCSE-R-paper-Final-Timetable-January-2017） | — |
| intgcse\|2017\|06\|R | 同上（International_GCSE_June_2017_final_timetable_R_code） | — |
| intgcse\|2019\|01\|R | 同上（1901_intGCSER_final） | — |
| intgcse\|2019\|06 | 穷尽候选后无可用 PDF（非 PDF 或校验失败） | 2 条 |
| intgcse\|2019\|06\|R | 无 R 卷文件（标准卷本身仅 302 记录） | — |
| intgcse\|2020\|11 | 穷尽候选后无可用 PDF（非 PDF 或校验失败） | 2 条 |
| intgcse\|2021\|01\|R | 仅见 xlsx 的 302 抓取，无 PDF 存档 | — |
| intgcse\|2022\|11 | 该年未开设 November IntGCSE 系列（非缺档） | — |
| intgcse\|2023\|06\|R | v1/v2 R 卷文件均只有 302 记录（int-gcse-r-paper-summer-2023-final-v2.pdf） | 2 条 |

每条均带 `search_exhausted: true`；如后续出现新存档可按同流程补入。

## 6. 未解析行（4 条，条目级，全部保留原文）

| 考季 | 页 | 内容 | 原因 |
| --- | --- | --- | --- |
| gcse\|2016\|06 | 6 | `Computer Science Paper 1: Principles of Computer Science` 行 | 源 PDF 该条目缺科目代码，无法并入事件 |
| gcse\|2019\|11 | 5 | 日期单元格 `Friday 15 Novmber` | 源 PDF 拼写错误（Novmber），日期无法解析 |
| ial\|2017\|06 | 5 | 2017-05-15 行（WEC01/WCH07/WSP02 + WPS01/WPH07） | 时长 2 项与考试条目 3 项数量不一致，该行时长整体置空 |
| ial\|2018\|06 | 4 | 2018-05-11 行（WBI06） | 时长 2 项与考试条目 1 项数量不一致，该行时长整体置空 |

处置原则：不臆造代码/日期，不丢弃行；`unparsed_rows` 随快照提供。

## 7. 抽样核对（接口事件 vs 来源原件）

方法：从源 PDF 表格逐行提取，与 API 事件逐字段比对（日期/场次/科目/卷号/时长）。

**A. ial\|2026\|06（源：`downloads/edexcel/ial/2026-06.pdf`，sha256 `dedc35e0…`）——2026-05-22 共 3 条全对：**

| 接口事件 | 原件行（p5） |
| --- | --- |
| 2026-05-22 Fri AM YLA1 02 3h00m | L100–105：`Friday 22 May` / `YLA1 02` / Law / `Paper 2: The Law in Action` / `Morning` / `3h 00m` |
| 2026-05-22 Fri PM WGN02 01 2h30m | L106–111：`Friday 22 May` / `WGN02 01` / German / `Unit 2: Understanding and Written Response` / `Afternoon` / `2h 30m` |
| 2026-05-22 Fri PM WPS03 01 1h30m | L112–117：`Friday 22 May` / `WPS03 01` / Psychology / `Unit 3: Applications of psychology` / `Afternoon` / `1h 30m` |

**B. gcse\|2016\|06（源：`downloads/edexcel/gcse/2016-06.pdf`，sha256 `c1a2d90c…`）——德语 4 条目拼接时长修复后全对：**

| 接口事件 | 原件行（p6） |
| --- | --- |
| 2016-06-08 Wed AM 5GN01 `1F Listening Foundation` 25m | L85–86 + L94：`5GN01` / `German Unit 1: 1F Listening Foundation` / `0h 25m` |
| 2016-06-08 Wed AM 5GN01 `1H Listening Higher` 35m | L87–88 + L95：`5GN01` / `…1H Listening Higher` / `0h 35m` |
| 2016-06-08 Wed AM 5GN03 `3F Reading Foundation` 35m | L89–90 + L96：`5GN03` / `…3F Reading Foundation` / `0h 35m` |
| 2016-06-08 Wed AM 5GN03 `3H Reading Higher` 50m | L91–92 + L97：`5GN03` / `…3H Reading Higher` / `0h 50m` |

**C. gce\|2017\|06（源：`downloads/edexcel/gce/2017-06.pdf`，sha256 `79da9676…`）——3 条日期窗口全对（p4：`8–26 May (Window)` / `22-26 May (Window)` 列）：**

| 接口窗口 | 原件行 |
| --- | --- |
| 6957 01 → 2017-05-08 … 2017-05-26 | `6957 01 Information Technology Unit 7: Using Database Software` / `10h 00m` |
| 6959 01 → 2017-05-08 … 2017-05-26 | `6959 01 …Unit 9: Communications and Networks` / `10h 00m` |
| 6953 01 → 2017-05-22 … 2017-05-26 | `6953 01 …Unit 3: The Knowledge Worker` / `2h 30m` |

**D. gcse\|2027\|06（源：官网直连 `gcse-summer-2027final.pdf`，sha256 `dd43f8fb…`，验证 live 抓取链）——1PN0 1H 行全对：**

| 接口事件 | 原件行（p6） |
| --- | --- |
| 2027-05-20 Thu PM 1PN0 1H `Persian Paper 1: …Higher Tier` 45m | L156–160：`1PN0 1H` / Persian / `Paper 1: Listening and understanding in Persian Higher Tier` / `Afternoon` / `0h 45m` |

另：全量复核 `validate_round3.txt` 覆盖 106 季（每季 `events/windows/unparsed/dup/uncl/notes` 计数 + 表格分类计数），零事件季为 0、unclassified 季为 0。

## 8. 统一接口与 E2E 实测

接口（`src/examdata/timetable/router.py`；只读快照，运行时不联网、不查库）：

- `GET /api/v1/timetable/seasons?board=edexcel[&family=…]`：考季目录（counts + seasons + cancelled + unobtainable）
- `GET /api/v1/timetable?board=edexcel&family=…&year=&season=[&r_paper=true]`：结构化事件，`month` 别名 `Jan/Jun/Oct/Nov`，可按 `subject`/`date`/`session` 过滤，limit ≤ 2000 / offset
- `GET /api/v1/timetable/windows?board=edexcel&family=…`：日期窗口
- 错误语义：取消季 404（`cancelled: true`）/ 已收录但不可得 404（`reason`/`evidence`）/ 未收录考季或非法参数 422 / 快照缺失 503
- 兼容：`board` 默认 `cie` 行为不变；别名 `edx`/`pearson`；`board=edexcel` 必填 `family`（gcse/intgcse/ial/gce），`level` 仅适用于 CIE。

本地统一服务（uvicorn 127.0.0.1:8791）实测（2026-10-05）：

| 调用 | 结果 |
| --- | --- |
| `GET /api/v1/timetable/seasons?board=edexcel` | 200；counts {106 季 / 6 取消 / 15 不可得}，totals {events 8479, windows 23} |
| `GET /api/v1/timetable/seasons?board=edexcel&family=ial` | 200；counts {34 季 / 1 取消 / 0 不可得} |
| `GET /api/v1/timetable?board=edexcel&family=ial&year=2026&season=June` | 200；90 条（§7A 抽样） |
| `GET /api/v1/timetable/windows?board=edexcel&family=gce&year=2017&season=June` | 200；3 个窗口（§7C） |
| `GET /api/v1/timetable?board=edexcel&family=intgcse&year=2018&season=June&r_paper=true` | 200；variant=R，36 条 |
| `GET /api/v1/timetable?board=edexcel&family=gcse&year=2020&season=June` | 404；`cancelled: true` + COVID-19 reason |
| `GET /api/v1/timetable?board=edexcel&family=intgcse&year=2019&season=June` | 404；reason + 2 条 evidence |
| `GET /api/v1/timetable?board=edexcel&family=ial&year=2026&season=June&level=AS` | 422；「level 仅适用于 CIE 时间表」 |
| `GET /api/v1/timetable/seasons`（CIE 回归） | 200；totals {25 季 / 8307 事件 / 737 窗口 / 2 不可得} |
| `GET /api/v1/timetable?year=2023&season=Nov`（随机抽季回归） | 200；326 条，与 seasons 元数据一致；`subject=9395` 过滤 3 条 |

## 9. 缺口与字段说明

1. **取消 6 季 + 不可得 15 季**：前者为官方取消（§4），后者为穷尽检索无档（§5）；接口对两类都返回 404，但分别带 `cancelled: true` 与 `search_exhausted: true`，语义不混。
2. **字段范围**：事件含 `date` / `weekday` / `session`（AM/PM）/ `subject_code` / `paper_code`（可为 null）/ `subject_title` / `duration_raw` / `duration_minutes` / `session_raw` / `raw` 原文行；日期窗口单独由 `/windows` 返回（`window_raw` + `window_start`/`window_end`，解析失败为 null）。
3. **R 卷变体**：13 份 `-r.json`（IntGCSE），同一考季标准卷与 R 卷是两份独立文件，通过 `r_paper=true` 或键后缀 `|R` 区分；其余族谱无 R 卷。
4. **provisional 文件**：4 季快照采用 provisional 版（`label: provisional`），另 3 季在 `extra_sources` 记录同季 provisional 文件（gce|2018|06、ial|2019|10、intgcse|2018|06）。
5. **未解析 4 条**（§6）与 CIE 一致采用"原样保留 + 不猜测"策略；如需合并进事件，应先补源文件或人工裁定。
6. **日期窗口覆盖较少**（23 条，集中在 gce 与 ial）：Edexcel 多数时间表不设 Test date windows 节，属版式事实而非解析缺口。
