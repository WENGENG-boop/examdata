# CIE Zone 5 考试时间表（历年）：调研与接口报告

- 生成日期：2026-10-05
- 机器可读数据：`src/examdata/timetable/data/zone5/index.json` + 25 个单季 `YYYY-MM.json`
- 临时原件：原存于 `tmp_materials_probe/downloads/zone5_final/` 的 18 份源 PDF 与 `zone5_gap7/` 的 7 份（2013–2016 旧版式）源 PDF，验证后已按约定清理（不入库）；逐季 sha256 见 index.json 与 `tmp_materials_probe/evidence/gap7_downloads.json`
- 相关接口：`GET /api/v1/timetable/seasons`、`GET /api/v1/timetable`、`GET /api/v1/timetable/windows`

## 1. 结论摘要

- 已落盘 **25 个考季**（2013-11 … 2026-11），共 **8307 条结构化事件**、**737 个单元考试日期窗口**；每季 `unparsed_count=0`。
- **2 个不可得考季（已穷尽检索）**：官网在线 + Wayback CDX 多模式/按文件 ID 全量扫描/归档目录页/旧域名检索后确认无可取回文件，逐条给证据（2019-06、2020-11，见 §4）。
- 2013–2016 七季经旧域名 CDX 检索补回（legacy 版式，走 `_parse_legacy_pdf` 解析分支）。
- 最新可得考季 = 2026-11（官方现行 PDF）；历年起点 = 2013-11。
- 抽样核对（2 季 × 6 条 + legacy 季 9709 全 7 条，日期/科目/卷号/时长/场次）与来源原件完全一致（§5）。
- 接口实测：`/api/v1/timetable/seasons` 与 2026 Nov 9709 查询 200；2013 Nov 9709 查询 200（7 条）；不可得考季 404、未收录年份 422（§6）。

## 2. 范围与方法

- 来源：CIE 官方站点（现行可下载）+ Wayback Machine 存档（历年下架文件）；每季记录 URL、source_kind（official / wayback）、sha256、页数。
- 解析：源 PDF 为 Office 导出、表格框线完整；用 pymupdf `find_tables()` 按列头定位语义列。事件只从 **Weekly view** 抽取（唯一同时给出日期、时段、单元代码与时长的视图）；Syllabus view 仅用于核对。
- Legacy 版式（2013-11 / 2014-06 / 2014-11）：无表格框线，日期由页面左侧的"日方括号"（矢量图形）分组；自动路由到 `_parse_legacy_pdf`，行按 y 坐标落入的日块归属日期标签，该分支不产出日期窗口（`date_windows` 为空；三季源 PDF 本身不含 Test date windows 节）。2015-06 起的 PDF 版式含完整表格结构，走通用表格解析（含 Test date windows 页）。
- 日期规则：表上方横幅只含日月，年份由考季推断（6 月考季落在 1–7 月、11 月考季落在 8–12 月）；越界日期不静默改年，只在事件上打 `date_note`。
- 不可确信归属的行进入 `unparsed_rows`（每季上限 50 条），不猜测、不丢弃——本次 25 季 `unparsed_count` 全为 0。
- 上游请求走仓库 Fetcher 约束（robots、限速、单工作线程）。

## 3. 覆盖明细（25 季）

| 考季 | 事件数 | 日期窗口 | 未解析 | 来源 | 页数 | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| 2013-11 | 407 | 0 | 0 | wayback | 24 | e4350f15bb5c… |
| 2014-06 | 337 | 0 | 0 | wayback | 14 | aa4025ccb74f… |
| 2014-11 | 404 | 0 | 0 | wayback | 24 | 16f0d01a90fb… |
| 2015-06 | 341 | 79 | 0 | wayback | 17 | e5f1a416b81c… |
| 2015-11 | 369 | 37 | 0 | wayback | 17 | 4eabedb7c4d6… |
| 2016-06 | 346 | 38 | 0 | wayback | 17 | 4b42213638c7… |
| 2016-11 | 364 | 33 | 0 | wayback | 17 | da896edcb6e0… |
| 2017-06 | 347 | 38 | 0 | wayback | 17 | fa35ad22819e… |
| 2017-11 | 371 | 35 | 0 | wayback | 17 | d52b4910d585… |
| 2018-06 | 350 | 36 | 0 | official | 17 | 9609619d79b2… |
| 2018-11 | 366 | 30 | 0 | wayback | 16 | 351d46d93240… |
| 2019-11 | 358 | 32 | 0 | wayback | 13 | f2100664cb57… |
| 2020-06 | 297 | 35 | 0 | wayback | 13 | 414a1de625cd… |
| 2021-06 | 307 | 35 | 0 | official | 12 | 6ac6572de7cc… |
| 2021-11 | 333 | 27 | 0 | wayback | 14 | eea10b57a8bd… |
| 2022-06 | 300 | 33 | 0 | wayback | 13 | 21ac1d9861ac… |
| 2022-11 | 326 | 25 | 0 | official | 14 | 3b46f60d4a5d… |
| 2023-06 | 306 | 34 | 0 | wayback | 13 | 7733f10413a0… |
| 2023-11 | 326 | 24 | 0 | official | 13 | 236275e1c2aa… |
| 2024-06 | 306 | 34 | 0 | wayback | 14 | c61e354a9685… |
| 2024-11 | 279 | 22 | 0 | official | 13 | 281c3be8ad58… |
| 2025-06 | 306 | 33 | 0 | official | 14 | d335cc74e122… |
| 2025-11 | 280 | 22 | 0 | wayback | 13 | c53bb2281367… |
| 2026-06 | 303 | 33 | 0 | official | 14 | aa373c9bdd9d… |
| 2026-11 | 278 | 22 | 0 | official | 13 | 73fafa286a20… |

合计：**25 季 / 8307 事件 / 737 窗口 / 0 未解析**。注：2013-11 / 2014-06 / 2014-11 三季为 legacy 版式（源 PDF 无日期窗口节，`date_windows_count=0`）。

## 4. 不可得考季（已穷尽，逐条证据）

穷尽检索口径（探针 D-3/D-5/D-6 与旧域名补扫；证据 `tmp_materials_probe/evidence/cdx_exam_timetables.json`、`cdx_extra_zone5.json`、`cdx_gap_urls.json`、`cdx_zone5_images.json`、`gap7_unobtainable_oldsite.json`）：

1. **CDX 多模式全量候选**：`zone-5` / `zone5` / `zone 5` 大小写与 `/images` 前缀各模式查询，候选逐个测试官网在线状态；
2. **按文件 ID 扫描 Wayback 全部快照**（D-6）：CIE 惯例复用同一 Image URL 每季覆盖，故按快照时点还原各年份版本，逐季核验；
3. **归档目录页提取**（D-5）：从 Wayback 存档的 exam-timetables 目录页 HTML 中提取当季 zone-5 链接并逐一尝试 replay；
4. **旧域名 CDX 检索**：`cie.org.uk` / `www.cie.org.uk` 与 `Images`/`images` 两形态——2013–2016 七季由此取回，2019-06、2020-11 为零结果。

第 1–4 类检索后，以下 2 季均无有效文件可取回（仅 404 记录 / 从未被存档 / 同 URL 被后续年份覆盖），判定为**已穷尽**；如后续出现新存档可按同流程补入。注：2013-11 … 2016-11 七季为本轮经第 4 类检索新增取回（此前被列为不可得或未跟踪）。

| 考季 | 证据 |
| --- | --- |
| 2019-06 | 文件 513557-june-2019-timetable-zone-5.pdf 从未被有效存档：新域名 CDX 仅 1 条 2024-06-16 404 记录；旧域名 cie.org.uk 四主机变体检索 0 条；同 ID 于 2020/2021 被覆盖 |
| 2020-11 | 该季文件 469286 在 2020 时点无任何 Wayback 抓取，旧域名 cie.org.uk 四主机变体检索 0 条；后续同 URL 内容已被 2021/2022 覆盖；官网无历年归档版 |

## 5. 抽样核对（接口事件 vs 来源原件）

方法：从源 PDF 的 Weekly view / Syllabus view 表格人工提取行，与 API 事件逐字段比对。

**A. 2026-11（源：`zone5_final/2026-11.pdf`，sha256 `73fafa28…`）——科目 9709，6 条全对：**

| 接口事件 | 原件行 |
| --- | --- |
| 2026-10-13 Tue AM 9709/13 1h50m（AS） | Mathematics (Pure Mathematics 1) 9709/13 1h 50m Tuesday 13 October 2026 AM |
| 2026-10-15 Thu AM 9709/53 1h15m（AS） | Mathematics (Probability & Statistics 1) 9709/53 1h 15m Thursday 15 October 2026 AM |
| 2026-10-19 Mon AM 9709/23 1h15m（AS） | Mathematics (Pure Mathematics 2) 9709/23 1h 15m Monday 19 October 2026 AM |
| 2026-10-19 Mon AM 9709/43 1h15m（AS） | Mathematics (Mechanics) 9709/43 1h 15m Monday 19 October 2026 AM |
| 2026-10-19 Mon AM 9709/63 1h15m（AL） | Mathematics (Probability & Statistics 2) 9709/63 1h 15m Monday 19 October 2026 AM |
| 2026-10-21 Wed AM 9709/33 1h50m（AL） | Mathematics (Pure Mathematics 3) 9709/33 1h 50m Wednesday 21 October 2026 AM |

**B. 2026-06（源：`zone5_final/2026-06.pdf`，sha256 `aa373c9b…`）——科目 0620，6 条全对：**

| 接口事件 | 原件行 |
| --- | --- |
| 2026-04-28 Tue PM 0620/32 1h15m | Chemistry (Core) 0620/32 1h 15m Tuesday 28 April 2026 PM |
| 2026-04-28 Tue PM 0620/42 1h15m | Chemistry (Extended) 0620/42 1h 15m Tuesday 28 April 2026 PM |
| 2026-05-07 Thu PM 0620/52 1h15m | Chemistry (Practical) 0620/52 1h 15m Thursday 07 May 2026 PM |
| 2026-05-07 Thu PM 0620/62 1h | Chemistry (Alternative to Practical) 0620/62 1h Thursday 07 May 2026 PM |
| 2026-06-09 Tue PM 0620/12 45m | Chemistry (Multiple Choice - Core) 0620/12 45m Tuesday 09 June 2026 PM |
| 2026-06-09 Tue PM 0620/22 45m | Chemistry (Multiple Choice - Extended) 0620/22 45m Tuesday 09 June 2026 PM |

**C. 2013-11（源：`zone5_gap7/2013-11.pdf`，sha256 `e4350f15…`；legacy 版式）——科目 9709，7 条全对：**

方法：用页面左侧日期方括号（矢量图形）确定每条原文行所属的日期标签，与接口日期比对，全部一致。

| 接口事件 | 原件行（页 / y）与所在日块 |
| --- | --- |
| 2013-10-15 Tue AM 9709/13 1h45m（AS） | p6 y=436.3，日块 "Tuesday 15 Oct"；字面 `\uf06e`(AS) · Mathematics 13 · 9709/13 · 1h45m |
| 2013-10-18 Fri AM 9709/23 1h15m（AS） | p7 y=448.0，日块 "Friday 18 Oct"；`\uf06e` · Mathematics 23 · 9709/23 · 1h15m |
| 2013-10-18 Fri AM 9709/43 1h15m（AS） | p7 y=459.6，日块 "Friday 18 Oct"；`\uf06e` · Mathematics 43 · 9709/43 · 1h15m |
| 2013-10-25 Fri AM 9709/33 1h45m（AL） | p9 y=540.0，日块 "Friday 25 Oct"；`\uf070`(AL) · Mathematics 33 · 9709/33 · 1h45m |
| 2013-11-05 Tue AM 9709/63 1h15m（AS） | p11 y=461.2，日块 "Tuesday 5 Nov"；`\uf06e` · Mathematics 63 · 9709/63 · 1h15m |
| 2013-11-05 Tue AM 9709/53 1h15m（AL） | p11 y=495.7，日块 "Tuesday 5 Nov"；`\uf070` · Mathematics 53 · 9709/53 · 1h15m |
| 2013-11-11 Mon AM 9709/73 1h15m（AL） | p13 y=259.8，日块 "Monday 11 Nov"；`\uf070` · Mathematics 73 · 9709/73 · 1h15m |

符号说明：`\uf06e`=AS、`\uf070`=AL（与页首图例一致；完整映射 `\uf074`=IG、`\uf06c`=OL、`\uf0cc`=PR）。

全量复核：2013-11 / 2014-06 / 2014-11 三季共 32 个 legacy 周页（214 个日期标签、4049 条原文行）按同一几何规则逐行核验，0 失败（8 条"末行略低于括号端点"的良性溢出，归属仍正确；含 2014-11 重复副本共 45 页 / 304 标签 / 5519 行亦 0 失败）。

## 6. 统一接口与 E2E 实测

接口（`src/examdata/timetable/router.py`；只读快照，运行时不联网、不查库）：

- `GET /api/v1/timetable/seasons`：考季目录 + 每季计数 + 不可得考季证据（totals: available_seasons / events / date_windows / unobtainable_seasons）
- `GET /api/v1/timetable`：过滤参数 year / season / subject / date / session / level，limit ≤ 2000（默认 200）/ offset
- `GET /api/v1/timetable/windows`：单元考试日期窗口
- 错误语义：404（已收录但不可得考季）/ 422（未收录年份或非法参数）/ 503（数据不可用）

本地统一服务（uvicorn 127.0.0.1:8763）实测（2026-10-05）：

| 调用 | 结果 |
| --- | --- |
| `GET /api/v1/timetable/seasons` | 200；totals {25 季 / 8307 事件 / 737 窗口 / 2 不可得} |
| `GET /api/v1/timetable?year=2026&season=Nov&subject=9709` | 200；6 条（§5A） |
| `GET /api/v1/timetable/windows?year=2026&season=Nov` | 200；22 个日期窗口 |
| `GET /api/v1/timetable?year=2013&season=Nov&subject=9709` | 200；7 条（§5C） |
| `GET /api/v1/timetable?year=2013&season=Nov` | 200；407 条 |
| `GET /api/v1/timetable?year=2019&season=Jun` | 404（不可得考季，证据见 §4） |
| `GET /api/v1/timetable?year=2001&season=Jun` | 422「未收录的考季: 2001-06」 |

## 7. 缺口与字段说明

1. **不可得 2 季（已穷尽，四类检索）**：官网在线与 Wayback 检索（CDX 多模式、按文件 ID 全量快照、归档目录页提取、旧域名检索）均无有效文件（§4）；若后续有存档出现可按同流程补入。
2. **字段范围**：事件含 date / weekday / session / level / subject_code / paper_code / subject_title / duration_raw / duration_minutes / raw 原文行；日期窗口单独由 `/windows` 返回。以来源实际列为准。
3. **date_note**：年份越界等异常不静默修改，会带 `date_note` 标注（本次 25 季无触发）。
4. **legacy 三季无日期窗口**：2013-11 / 2014-06 / 2014-11 的源 PDF 不含 Test date windows 节，`/windows` 对其返回空数组（`count=0`）。
5. **窗口日期解析覆盖率**：737 条窗口全部保留 `window_raw` 原文；`window_start`/`window_end` 解析成功 514 条。其余 223 条为 null：42 条原文为 `N/A`（该组件本无窗口）、175 条为 `d Mon yyyy – d Mon yyyy` 长格式（2015-06 / 2015-11 / 2016-06 / 2016-11 / 2018-06 五季，如 `1 Mar 2015 – 30 Apr 2015`）、6 条为单日期（2016-06，如 `12 Apr 2016`）；后两类未做机器解析，原文与 null 原样保留、不猜测。
