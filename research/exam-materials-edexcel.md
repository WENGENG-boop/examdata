# Edexcel（培生爱德思）考试发放资料：全科目调研报告

- 生成日期：2026-10-05
- 机器可读数据：`src/examdata/materials/data/subjects_edexcel.json`（233 科逐科结论，schema_version=1）
- 临时证据目录：`tmp_materials_probe/evidence/`（edexcel_*.json 证据链；大体积版权原件已按约定清理）
- 相关接口：`GET /api/v1/materials`、`GET /api/v1/materials/{id}`、`GET /api/v1/materials/{id}/content`

## 1. 结论摘要

- 范围全集：**实测 258 个科目页 → 233 个唯一 slug**（233 科全部落盘结论）。
- 已接入统一接口 2 类（均为公开 PDF 实测取回、SHA256 对上）：
  - IAL 数学公式与统计表 Issue 2（来源科 page slug `mathematics-2018`）；
  - IAL 化学数据手册 Issue 1 March 2019（来源科 page slug `chemistry-2018`）。
- 记录级补实测（2026-10-05，经仓库 Fetcher 逐份取回，均 HTTP 200；证据 `evidence/edexcel_gap3_supplement.json`）：A Level 化学数据手册 9CH0（Issue 2 Summer 2017，12 页）+ 8CH0 AS（Issue 1 Summer 2016，8 页）；元素周期表独立文件 1 页（`chemistry-2008` 唯一记录行）；物理数据/公式清单 9PH0（Issue 3 Nov 2022，8 页）+ 8PH0 AS（Issue 2 Nov 2022，4 页）；统计公式与表格 4 行（主版 32 页 + A3 24pt 大字版 257 页 + A4 18pt 大字版 257 页 + psychology-2015 amended 8 页）。以上均只补实测证据、未扩 catalog（`integrated=no`），明细见 §4.1。
- 随卷 insert / source booklet（83 行）与 pre-release（99 行）为 partial：部分行位于 secure/silver 门禁，一律**只登记不请求**。
- 原 2 个 dead 页（无可用 facet）经记录级复核均为**非科目信息页**（2016/2017 更新新闻页、视频教程页），已排除出科目材料口径——不构成缺口。

## 2. 范围全集与调研方法

范围全集 = Pearson 官网实测可达的 **258 个科目页**，去重后 **233 个唯一 slug** 作为逐科单位。

逐科结论由四类实测证据合成：

1. **第一遍逐页抓取 + servlet 基查询**：150 页成功（`first_pass_ok`），83 页失败；其中 3 页为 capped 终稿三科，在最终来源分布中改计 capped（`first_pass` 终计 147）；
2. **83 失败页的 servlet `cq:Page` 记录级恢复**：25 个 live（`live_ok`，原始页仍在但首遍未取到材料行）+ 58 个 dead（404；其中 56 页经记录恢复、2 页经记录级复核为非科目信息页，已排除）；
3. **3 个 capped 科递归分区查询终稿**（`edexcel-a-level-geography-2015`、`history-2015`、`mathematics-2018`，共 7 次终稿查询，`complete_all=true`）；首遍行数分别 55 / 4 / 200 被终稿取代；
4. **20 个 slug 的 25 个家族变体页补齐**（25/25 ok；331 材料行）：第一遍去重按 (family, slug) 首条胜出，25 个变体页此前从未处理，本次补齐并保留在 `dup_variants`。

材料行来自 servlet algolia 记录（title / url / gated / doc_type / series 等）；**门禁（secure/silver）URL 只登记不请求**。`integrated_items` 由材料行 URL 与 catalog 条目 URL 归一后匹配得出；注册表逐项给出证据等级：记录级全集经 Fetcher 实测取回标 yes（见 §4.1），未逐份实测的材料类按记录级标 partial，门禁类只登记，未臆断。上游请求走仓库 Fetcher 约束（robots、限速、单工作线程）。

## 3. 覆盖数字

| 指标 | 数值 |
| --- | --- |
| 科目页级 | 258 = 233 逐科单位（第一遍 150 ok + 83 失败）+ 25 家族变体页 |
| 唯一 slug / 逐科单位 | 233 |
| 家族分布（页级 258 / 科目级 233） | 页级：International-GCSE 75、International-Advanced-Level 24、A-Level 66、GCSE 93；科目级：A-Level 66、International-GCSE 73、International-Advanced-Level 16、GCSE 78 |
| 恢复 | live_ok 25、dead_ok 56、dead_gap 2（复核均为非科目页） |
| capped 终稿 | 3（queries_used 7，unresolved 0） |
| 家族变体补齐 | 25 页 / 20 slug / 331 行 |
| 最终来源分布 | first_pass 147 + capped 3 + recovery_live 25 + recovery_dead_ok 56 + gap 2 = **233**（其中 gap 2 为非科目页） |
| 材料行合并 | 1491 行 → 去重 1479，唯一 URL 1449；门禁行 370（唯一 URL 366） |
| 有 servlet 记录的科目 | 231 / 233（`n_records`>0；其余 2 项经复核为非科目页） |
| 有材料记录的科目 | 112 / 233（材料行非空；其中 5 科仅家族变体页有行：gujarati-2018、persian-2018、portuguese-2018、turkish-2018、urdu-2009） |
| 无材料证据（科目级） | 0；JSON `no_material_evidence` 列表的 2 项即上述非科目页（已排除口径，非缺口） |

## 4. 材料类型注册表（9 项）

| key | 名称 | 公开获取 | 已接入 | 记录行数 |
| --- | --- | --- | --- | --- |
| ial18_maths_formula_book | IAL 数学公式与统计表 Issue 2 | yes | yes | 1（mathematics-2018） |
| ial18_chemistry_data_booklet | IAL 化学数据手册 Issue 1 March 2019 | yes | yes | 1（chemistry-2018） |
| al15_chemistry_data_booklet | A Level 化学数据手册（9CH0 / 8CH0） | yes（逐份实测） | no | 2（chemistry-2015） |
| chemistry_periodic_table | 元素周期表（独立文件） | yes（逐份实测） | no | 1（chemistry-2008，2008 老 spec） |
| physics_data_formulae_list | 物理数据、公式与关系式清单 | yes（逐份实测） | no | 2（physics-2015：A level + AS） |
| statistics_formulae_tables | 统计公式与表格（含 A3/A4 大字版） | yes（逐份实测） | no | 4（psychology-2015、statistics-2017 ×3） |
| source_booklet_insert | 随卷 insert / source booklet | partial | no | 83 |
| pre_release_materials | 考前预发材料 | partial | no | 99 |
| gated_policy_note | 门禁材料（secure/silver）处理策略 | no | 不适用 | 0（策略项） |

### 4.1 记录级补实测明细（2026-10-05，Fetcher 逐份取回 HTTP 200）

| 项 | 版本 / 来源 | 字节 | 页 | sha256（前 16） |
| --- | --- | --- | --- | --- |
| al15_chemistry_data_booklet | 9CH0 Data Booklet Issue 2 Summer 2017 | 1006191 | 12 | `09b40d7fe3f477e8` |
| al15_chemistry_data_booklet | 8CH0 AS Data Booklet Issue 1 Summer 2016 | 489551 | 8 | `b26d3ca37233d9ac` |
| chemistry_periodic_table | The Periodic Table of Elements（chemistry-2008 唯一行） | 957645 | 1 | `59361a42365664bb` |
| physics_data_formulae_list | 9PH0 Issue 3 November 2022 | 299004 | 8 | `3677323b1a40147f` |
| physics_data_formulae_list | 8PH0 AS Issue 2 November 2022 | 550902 | 4 | `99623bd0e4e22606` |
| statistics_formulae_tables | 8ST0/9ST0 Statistical formulae and tables | 1550546 | 32 | `ff83bed07cb46bf3` |
| statistics_formulae_tables | A3 24pt 大字版 | 499900 | 257 | `a7a2b87d085978fc` |
| statistics_formulae_tables | A4 18pt 大字版 | 752580 | 257 | `cd49f9f7a10c6c1c` |
| statistics_formulae_tables | psychology-2015 amended（May-June 2026 起） | 118548 | 8 | `59d502e972923584` |

完整 URL / sha256 / 首页文本见 `tmp_materials_probe/evidence/edexcel_gap3_supplement.json`（9 条）；PDF 版权原件验证后已清理。

## 5. 已接入项（逐项证据）

### 5.1 IAL 数学公式与统计表 Issue 2

- 官方 PDF：`…/International%20Advanced%20Level/Mathematics/2018/Specification-and-Sample-Assessment/IAL-Mathematics-Formula-Book.pdf`，HTTP 200，1731630B，sha256 `0c30bf2b83910e6ae6053a6c699a049cd05b02f54b6c3417eb9d8905d1a6d8ac`，34 页。
- 版本：Issue 2（2019 年 1 月起首考；servlet 记录 desc=Issue 2、size 1.7 MB、gating=false）；未发现并存旧版。
- 接入：catalog `edexcel-ial-maths-formula-book`（access=public，subjects=['ial18-mathematics','ial-maths']）；来源科 page slug `mathematics-2018`（capped 终稿来源）。

### 5.2 IAL 化学数据手册

- 官方 PDF：`…/International%20Advanced%20Level/Chemistry/2018/Teaching-and-Learning-Materials/IAL_Chemistry%202018_Data_booklet_Issue_1_March%202019.pdf`，HTTP 200，2542080B，sha256 `a372a93daa9716ad902d3e3ea885469b46538ab79218b580027d5638e6d7dee7`，12 页。
- 版本：Issue 1 March 2019（文件名与 PDF 首页一致）；未发现并存旧版。
- 接入：catalog `edexcel-ial-chemistry-data-booklet`（access=public，subjects=['ial18-chemistry']）；来源科 page slug `chemistry-2018`。
- 说明：与目录 URL 归一后完全一致；`/content` 实测见 §6。

## 6. 统一接口与 E2E 实测

- `GET /api/v1/materials` → 200，count=8（CIE 6 + Edexcel 2）；带 `?board=edexcel` 过滤 → 200，count=2（即 §5 两条已接入项；2026-10-05 复核重跑一致）。
- `GET /api/v1/materials/edexcel-ial-chemistry-data-booklet/content` → 200，2542080B，`X-Material-Sha256: a372a93d…`，`X-Material-Sha256-Match: true`。
- `GET /api/v1/materials/edexcel-ial-maths-formula-book/content` → 目录登记 sha256 `0c30bf2b…`（下载实测同值，见 `evidence/edexcel_downloads.json` 第 1 条）。
- 错误语义：无版本 422、未收录 404、上游故障 502、robots 403；sha256 快照不一致不报错，仅如实告知（`sha256_match=false`）。

### 复核记录（本报告定稿时）

调研脚本 `build_subjects_edexcel.py` 中化学数据手册的 URL 与 SHA256 曾误写为另一路径/摘要；定稿复核时已更正为 catalog 实测值（URL 路径段 `Teaching-and-Learning-Materials`、sha256 `a372a93d…dee7`），并重跑生成（首次 1,136,907B）。2026-10-05 缺口补强后再次重生成：`subjects_edexcel.json` 为 1,143,245B（本次新增 §4.1 记录级实测证据与 dead 页改判说明）。随后终校修订结论句式：公开/门禁拆分属记录级口径（`public_count + gated_count == n_records`），原置于「材料 N 行」子句易误读，已移至「记录」子句；重生成后 1,142,804B（coverage 与注册表数字不变，231 条 `conclusion_zh` 文本更新，diff 逐条核对）。

## 7. 缺口与后续

1. ~~2 个 dead 页缺口~~（**已闭环，2026-10-05 复核**）：`international-GCSE-2016-and-2017-updates-int-schools`、`video-tutorial`——记录级复核（`edexcel_page_records.json`）确认两页为非科目信息页（分别 pagetype=information / specification_v2，tags 无 Specification-Code / Qualification-Subject），已排除出 233 科材料口径，不再计为缺口。
2. ~~记录级未实测项~~（**已闭环，2026-10-05 补实测**）：al15 化学数据手册（2 行）、周期表（1 行）、物理清单（2 行）、统计表格（4 行）共 9 条记录行已逐份实测（§4.1，均 HTTP 200）；source booklet insert（83 行）与 pre-release（99 行）仍为记录级（未逐份实测，含门禁行）。如需接入可按实测 URL 加 catalog 条目。
3. **门禁策略**：370 行（366 URL）secure/silver 记录只登记不请求，不绕过登录墙；如需核对需用户提供合法访问途径。
4. **变体处理口径**：25 个家族变体页（20 slug、331 材料行）已补齐为独立 `page_entries`，不与主条目混用；如需可按需去重合并。
5. 与 CIE 不同，Edexcel 的 insert / source booklet 尚无公开镜像动态通道，逐卷定位需后续按 servlet 记录扩展（现为记录级证据）。
