# CIE（剑桥国际）考试发放资料：全科目调研报告

- 生成日期：2026-10-05（缺口复查后的更新版）
- 机器可读数据：`src/examdata/materials/data/subjects_cie.json`（272 科逐科结论，schema_version=1）
- 临时证据目录：`tmp_materials_probe/evidence/`（工作区临时产物；大体积版权原件已按约定清理，证据 JSON 保留）
- 相关接口：`GET /api/v1/materials`、`GET /api/v1/materials/{id}`、`GET /api/v1/materials/{id}/content`、`GET /api/v1/materials/cie/in-paper`

## 1. 结论摘要

- 范围全集 **272 科**（= syllabuses.json 198 ∪ discovery.json 196 ∪ Nov 2026 国际版附加材料清单 207 ∪ 三份系列清单快照 252）；共登记 **19 类** 发放/使用材料。
- 可公开获取且已接入统一接口：MF19 公式与统计表（9709/9231）、insert / source material（76 科，动态通道）、保密须知 CI（20 科，动态通道）、元素周期表（5 科，经试卷本体）、Nov 2026 附加材料清单本体、通用选择题答题卡（Form 2a）。
- 不可公开获取（有据）：口语角色扮演卡、教师说明、特殊格式试卷（DFD/DIR/SSH）、考生记录表、DVD、图表纸（考务包裹 183A 发放，非独立公开文件）与描图纸（考点自备）。
- 未证实公开可得（uncertain）：听力音频 ALF（24 科）、Instructions（22 科）、源文件 Source File（3 科）、CISpecimens（1 科）。
- 化学数据手册（9701）判定 **不可公开获取（no）**：官方无独立公开 PDF（站点检索与三份系列清单全文 grep 均 0 次），9701 数据以 syllabus Data 附录形式公开；两处官方问答口径的兼容解读见 §5。
- 10 科无任何材料证据（见 §3），均为 2027–2029 首考的新版 syllabus，属时间线上的必然缺席，而非调研缺口。

## 2. 范围全集与调研方法

范围全集取仓库既有枚举证据的并集（系列级快照，不代表其他系列）：

| 来源 | 数量 | 位置 |
| --- | --- | --- |
| 官方 syllabus 枚举 | 198 科 | `examdata/.data/syllabuses.json` |
| 官方站点发现快照 | 196 科（2767 资源） | `examdata/.data/discovery.json` |
| Nov 2026 国际版附加材料清单（PDF 解析） | 207 科（2164 组件行） | `tmp_materials_probe/evidence/addmaterials_rows.json` |
| 三份系列清单快照（June 2024 / Nov 2024 / Nov 2025 国际版） | 252 科 | `tmp_materials_probe/evidence/addmaterials_rows_*.json` |
| **并集合计** | **272 科** | 见 `subjects_cie.json` → `coverage` |

系列清单快照元数据（Wayback 归档同 URL 清单 PDF，系列名按 PDF 首页文本核对）：

| 系列 | capture | 字节 | 页 | 行 | 科 | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| June 2024（国际版） | 20240703193603 | 777515 | 234 | 2328 | 193 | `406ceeb64894…` |
| November 2024（国际版） | 20250505095707 | 662015 | 210 | 1931 | 213 | `9e733dcfa859…` |
| November 2025（国际版） | 20251014160116 | 650303 | 219 | 2130 | 208 | `daa76149778a…` |

- Wayback 截断说明：同一 URL 的 2023-03、June 2022、Nov 2022 三份捕获均为 1 MiB（1048576B）服务端截断、0 页可解析，未纳入统计；截断记录保留于 `evidence/gap1_wayback_lists.json`。

逐科结论由四类实测证据合成：

1. **附加材料清单 PDF（Nov 2026 国际版）**：`https://www.cambridgeinternational.org/Images/651593-additional-exams-material-list-international-.pdf`，实测 658660B、222 页、sha256 `858b0fcb…`；按组件行解析出发放项 / 考生自备 / 答题方式。
2. **三份系列清单快照**（见上表）：对原 23 个「无证据」码逐年核对（结论见 §3）。
3. **官方站点发现快照**（2767 条）：doc_type 分布 specimen_paper 760、specimen_mark_scheme 558、examiner_report 173、mark_scheme 482、question_paper 466、source_material 179、other 112、confidential_instructions 37。
4. **定向实测取回**：MF19、0990/0500 insert、0620/9701 保密须知、0411 预发材料、Form 2a 答题卡、官方 xlsx 等，逐项记录 HTTP / 字节 / sha256 / 页数。

所有上游请求走仓库 Fetcher（robots、限速、单工作线程）或等价节流探测脚本；未绕过任何登录墙 / 门禁（如 School Support Hub 需登录材料仅登记"不可公开"）。

## 3. 覆盖数字

- 272 科中 **174 科** `materials` 有至少一类发放项记录；**10 科** 无任何材料证据（四份清单全文无码行、发现快照无 insert/CI 记录）：
  `0265, 0266, 0479, 0715, 0716, 8101, 8102, 8293, 9981, 9982`。该 10 码均为 2027–2029 首考的新版 syllabus（页面句 / specimen 年份佐证，见 `new_syllabus_note_zh`），在全部历史清单中缺席与时间线自洽。
- 原 23 个「无证据」码闭环情况：其中 **13 码** 已在 June 2024 / Nov 2024 系列清单中定位并行级记录——`0262, 0444, 0472, 0480, 0499, 0523, 0539, 0544, 0547, 0772, 7164`（June 2024）及 `0989, 0995`（June 2024 + Nov 2024；Nov 2024 各 2 行）。其余 88 科有清单/发现覆盖但无发放项记录（清单行无 provided 列，或仅标准试卷）。
- 材料类型按引用科目数（`subjects[*].materials` 统计）：

| key | 名称 | 公开获取 | 已接入 | 引用科数 |
| --- | --- | --- | --- | --- |
| official_insert_source_material | Insert / Source material PDF | yes | yes | 76 |
| answer_booklet_insert | 随卷答题册（Answer Booklet） | partial | partial | 62 |
| mc_answer_sheet | 选择题答题卡（通用表格） | yes | yes | 52 |
| listening_file_alf | 听力音频文件 ALF | uncertain | no | 24 |
| instructions | 说明文件（随卷） | uncertain | no | 22 |
| official_confidential_instructions | 保密须知 CI（考务/教师用） | yes | partial | 20 |
| qp_special_format | 特殊格式试卷（DFD/DIR/SSH） | no | no | 9 |
| role_play_cards | 口语角色扮演卡 | no | no | 7 |
| teachers_notes | 教师用说明 | no | no | 7 |
| periodic_table_in_paper | 元素周期表（印在试卷内） | via-qp | partial | 5 |
| pre_release | 考前预发材料 | yes | no | 3 |
| source_file | 源文件（ICT/计算机类） | uncertain | no | 3 |
| candidate_arf | 考生记录表 | no | no | 2 |
| mf19_formulae_tables | 数学公式与统计表 MF19 | yes | yes | 2 |
| chemistry_data_booklet | 化学数据手册（AS/A Level） | no | no | 1 |
| cispecimens | 实践样检材料 | uncertain | partial | 1 |
| dvd | DVD 素材（媒体研究） | no | no | 1 |
| graph_paper | 图表纸（考务包裹 183A 发放） | no | no | 0（清单文本 grep=0） |
| tracing_paper_centre | 描图纸（考点自备） | no | no | 0 |

## 4. 可公开获取且已接入（逐项证据）

### 4.1 MF19 公式与统计表（9709、9231）

- 官方 PDF：`https://www.cambridgeinternational.org/Images/417318-list-of-formulae-and-statistical-tables.pdf`，HTTP 200，311234B，sha256 `c075388ec7227fea086358f4332592a395a3c8d9c82b75890346f84cfc749d90`，16 页。
- 版本：PDF 首页 "For use from 2020 in all papers…"；9709 syllabus 2023–2025 与 2026–2027 均引用 MF19，未发现 2020 年后换版证据（`version_note_zh`）。
- 接入：catalog 条目 `cie-mf19-formulae-and-statistical-tables`（access=public，subjects=['9709','9231']）；`/content` 实测见 §6。

### 4.2 Insert / Source material（76 科）

- 发现快照含 179 份公开 source_material 资源；官方-实测例：0990 June 2024 Insert Paper 11，HTTP 200、729313B、sha256 `5b7a729b…`（`Images/603004-june-2024-insert-paper-11.pdf`）。
- 镜像实测例：`0500_s24_in_11.pdf` HTTP 200、114871B、sha256 `7d49097cb30c27e4…`。
- 接入：动态通道 `GET /api/v1/materials/cie/in-paper`（role=in|ir），按 subject/year/season/paper 定位；catalog 条目 `cie-inserts`（access=dynamic）。
- **逐卷可得性抽样**（镜像目录，26 个「科目×考季」实测，3 个样本无该考季目录未纳入）：
  - 0500：2016/2019 各 qp 9 / ms 9 / **in 9**；2022/2024/2025 各 qp 6 / ms 6 / **in 6** —— in 与 qp 一一对应。
  - 0620：2016 qp 18 / ms 18 / **ir 3**；2019/2022/2024 各 **ci 3**。
  - 0610：2019 **ci 3**。
  - 9701：2019 qp 17 / ms 17 / **ci 5 + in 1**；2022 **ci 5**；2024 qp 17 / ms 17 / **ci 5**。
  - 9702：2019 / 2024 各 **ci 5**。
  - 9709：2017/2019/2021/2023/2025 及 2024 Jun/Nov 共 7 个考季**无 in / ir / ci**；9231 2019 无 in / ci。
  - 结论：抽样范围内 in/ir/ci 与本卷组数一致，未发现清单-镜像矛盾；`partial` 指未对所有科目 × 考季穷举。

### 4.3 保密须知 CI（20 科，考务/教师用）

- 官方-实测：0620 June 2024 Paper 51，HTTP 200、1064877B、sha256 `5909d16e…`；9701 June 2024 Paper 31，HTTP 200、1813136B、sha256 `71ffa69f…`。
- 镜像抽样：`0620_s24_ci_51.pdf` 200、183081B、sha256 `76ed9567…`；旧代码样本 `0620_s16_ir_51.pdf` 200、166037B、sha256 `84562eea…`。
- 语义：过期系列的归档公开；动态通道 role=ci|ir。

### 4.4 元素周期表（5 科）——印在试卷内

- 无独立文件；证据为官方帮助文章 + 试卷封面标注 + 附加材料清单行。
- 接入：catalog 条目 `cie-periodic-table`（access=in-paper）；`/content` 实测返回 422「没有可独立取回的版本」——获取路径为试卷本体（既有 papers 通道）。

### 4.5 Nov 2026 附加材料清单（清单本体）

- `Images/651593-additional-exams-material-list-international-.pdf`，658660B，222 页，sha256 `858b0fcb…`；覆盖 207 科 / 2164 组件行。
- 接入：catalog 条目 `cie-additional-materials-list`（access=public）。

### 4.6 考前预发材料 Pre-Release（3 科：0411 / 0454 / 0994）

- 0411 June 2024 Paper 11，HTTP 200、1040666B、sha256 `f2e00ba0…`（`Images/521274-june-2024-paper-11-pre-release-material.pdf`）。
- 官方 xlsx「Early question papers and pre-release material - November 2026」（`Images/761208-…-november-2026.xlsx`，HTTP 200、14926B、sha256 `186ff111…`；按单元格引用重解析）逐组件确认：
  - Type=Pre-release 组件：0411/11、0411/12、0411/13（School Support Hub 日期 2026-02-01）；0454/11–13（DFD=Yes）；0994/12（SSH 日期 2026-02-01）。
  - Source file 行：0417/02、0417/03、0983/02、0983/03、9618/41–43、9626/02、9626/04，E 列 "Released three days before the test date\*"。
- 判定 yes（官方公开发布），但属**时间性文件**（考前定时释放）且混合考务通告：**未接入**，集成通道后续可扩展。

### 4.7 通用选择题答题卡（Multiple Choice Answer Sheet，Form 2a）

- 官方 PDF：`https://www.cambridgeinternational.org/Images/86445-supplementary-multiple-choice-answer-sheet-exam-day-form-2a.pdf`，实测 HTTP 200、129066B、sha256 `0e0156de5eca0d144805628d3bd0f3e8e54d7643d52bb6a3d58bda59596bacdc`（复算一致）。
- 语义：**通用表格**（无 subject 级定位）；Nov 2026 清单 265 行 / 52 科引用 "Multiple Choice Answer Sheet"；帮助文章 29566949506322 佐证电子副本可下载打印。
- 接入：catalog 条目 `cie-mc-answer-sheet`（access=public，subjects=[] 标注通用）；E2E `/content` 200、129066B、`X-Material-Sha256-Match: true`（见 §6）。

## 5. 不可公开获取 / 未证实（逐项依据）

| key | 判定 | 依据（证据摘录） |
| --- | --- | --- |
| role_play_cards / teachers_notes | no | 材料在 School Support Hub（需登录），非公开直取；发现快照无对应公开文件 |
| qp_special_format | no | 按需提供，不在公开渠道发布 |
| candidate_arf | no | 考务表单，不在公开渠道发布 |
| dvd | no | 不在公开渠道发布 |
| graph_paper / tracing_paper_centre | no | 无独立公开 PDF；三份系列清单全文 grep 'graph paper' 均 = 0；考务侧按包裹发放：183A 包裹含 Chart/Graph Paper，帮助文章 203545612 称"每次需要该材料的考试每考生两张"；描图纸为部分数学卷考点自备（清单扉页明文） |
| listening_file_alf | uncertain | 发现快照未见音频条目；公开可得性未证实 |
| instructions | uncertain | 发现快照未找到对应文件 |
| source_file | uncertain | 发现快照未见对应公开文件；官方 xlsx（761208）标注 0417/0983/9618/9626 的 Source file "Released three days before the test date\*"（DFD 通告，需 final entries）——属考务定时释放，长期公开性未证实，未接入 |
| cispecimens | uncertain | 未见公开文件；可能与 CI 通道相关，未验证 |
| chemistry_data_booklet | no | 无独立公开 PDF（站点检索与三份系列清单全文 grep 'Data Booklet' 均 0 次）；口径兼容解读：203545612 称"每考生一本、需用组件见 Additional Materials database"，20295231545746 称理论卷 1/2/4 不再随卷发放——即仅指定组件发放；替代路径：syllabus Data section 附录 |
| mc_answer_sheet | yes | 通用表格官方可下载；已接入（见 §4.7） |
| answer_booklet_insert | partial | 部分以 insert 形式随卷公开（同 §4.2 通道）；并非每份答题册都有单独公开文件，逐卷核验未完成 |

## 6. 统一接口与 E2E 实测

接口（`src/examdata/materials/router.py`）：

- `GET /api/v1/materials`（board / subject / kind / candidate_facing 过滤；响应含 `dynamic_endpoints.cie_in_paper`）
- `GET /api/v1/materials/{id}`；`GET /api/v1/materials/{id}/content`（version=label 或 0 起索引；format=binary|json；响应头 `X-Material-*`）
- `GET /api/v1/materials/cie/in-paper`（subject / year / season∈{Mar,Jun,Nov} / paper / role∈{in,ir,ci} / download / format）
- 错误语义：403 / 404 / 409 / 422 / 502

本地统一服务（uvicorn 127.0.0.1:8763，数据目录 `.pytest_cache/callable-api`）实测（2026-10-04/05，含 2026-10-05 复核重跑）：

| 调用 | 结果 |
| --- | --- |
| `GET /api/v1/materials` | 200，count=8（6 CIE + 2 Edexcel）；含 `dynamic_endpoints` |
| `GET /api/v1/materials/cie-mf19-formulae-and-statistical-tables/content` | 200，311234B，`X-Material-Sha256: c075388e…`，`X-Material-Sha256-Match: true` |
| `GET /api/v1/materials/cie-mc-answer-sheet/content` | 200，129066B，`X-Material-Sha256-Match: true`，`content-disposition: …form-2a.pdf` |
| `GET /api/v1/materials/cie-periodic-table/content` | 422 `{"detail":{"message":"资料 cie-periodic-table 没有可独立取回的版本",…}}` |
| `GET /api/v1/materials/cie/in-paper?subject=0500&year=2024&season=Jun&role=in` | 200，6 份文档（in 11/12/13/21/22/23） |
| `…/in-paper?…&paper=11&download=1` | 首次 502（上游瞬态）→ 间隔后**单次**重试 200，114871B，sha256 `7d49097c…`（`X-Material-Role: in`、`X-Material-Paper: 11`） |
| `GET /api/v1/materials/edexcel-ial-chemistry-data-booklet/content` | 200，2542080B，sha256 `a372a93d…`，match=true（对照见 Edexcel 报告） |
| 旧端点 `/api/v1/boards`、`/api/v1/search` | 200，行为不变（本次实测）；`/api/v1/paper` 等旧端点行为由全量回归测试覆盖（全绿） |

## 7. 缺口与后续

1. **逐组件可得性（partial）**：本轮已补 26 个「科目×考季」镜像抽样（in/ir/ci 与本卷组数一致，§4.2）；未对所有科目穷举，动态通道已支持按卷探测，完整核验留作后续。
2. **化学数据手册**：判定 no（无独立公开 PDF；三份系列清单全文 grep=0；数据在 syllabus Data 附录）；两处官方问答口径已并列记录（§5），未臆断。
3. **未接入项**：pre-release（3 科）与 source_file 均属考务定时释放、无长期公开取回证据，已写明依据未接入；通用选择题答题卡已接入（§4.7）。
4. **10 科无证据**：均为 2027–2029 首考新版（§3），属时间上的必然缺席；13 个旧码已由 June 2024 / Nov 2024 系列快照定位闭环。
5. 上游镜像存在瞬态 502 记录（E2E 间隔后单次人工重试成功）；取回一律经仓库 Fetcher（robots/限速/内置重试），上游故障按既有语义映射为 502。
