# API 项目总文档

更新日期：2026-10-05（北京时间）。工作区：`C:/Users/weo/Desktop/api`。

本文件汇总项目结构、各模块当前进度、证据与续作入口。接口参数以 [统一 API 指南](../examdata/docs/API.md) 为准，部署方法见 [部署指南](../examdata/docs/DEPLOY.md)。

后续整体整合方案见 [所有 API 与整体项目整合计划](PROJECT_INTEGRATION_PLAN.md)。该计划尚待实施，与本文件记录的实际完成状态分开。

## 1. 当前结论与证据口径

项目已包含 CIE、Edexcel、IELTS、TOEFL、考试发放资料与时间表接口。高考目前为来源可获取性验证。代码实现、数据覆盖、答案正确性、音频对齐与运行服务分别验收；项目尚未整体完成。

本次更新读取了对应工作区的 Kimi 会话、代码注册、报告、检查点及测试日志，没有重新抓取上游、重跑全套测试、写数据库或重启服务。下列测试数字为已有日志结果，视觉门槛数字为当前汇总记录，不代表本次重新逐图核验。旧交接文件中的数字保留历史用途。

## 2. 目录与接口入口

| 目录 | 用途 | 文档入口 |
| --- | --- | --- |
| `examdata/` | Python 主服务、CIE/Edexcel 检索、试卷与单题取回、标签和治理 | [README](../examdata/README.md)、[API](../examdata/docs/API.md) |
| `ielts-api/`、`ielts-data/` | Node 雅思聚合器与独立数据根；网关 `/api/v1/ielts` | [实施结果](ielts/IELTS_IMPLEMENTATION_RESULT.md)、[缺口](ielts/IELTS_REMAINING_GAPS.md) |
| `toefl-api/` | Node 托福聚合器；网关 `/api/v1/toefl` | [实施结果](toefl/TOEFL_IMPLEMENTATION_RESULT.md)、[缺口](toefl/TOEFL_REMAINING_GAPS.md) |
| `cie-location-batch/` | CIE 目录发现、定位、验证、导入与临时文件清理 | [最新汇总](../cie-location-batch/summary.json)、[检查点](../cie-location-batch/checkpoint.json) |
| `examdata/src/examdata/materials/` | 考试发放资料目录与取回；`/api/v1/materials` | [CIE 调研](../examdata/research/exam-materials-cie.md)、[Edexcel 调研](../examdata/research/exam-materials-edexcel.md) |
| `examdata/src/examdata/timetable/` | 考试时间表（CIE Zone 5 + Edexcel）：结构化考试事件；`/api/v1/timetable` | [CIE 调研](../examdata/research/exam-timetable-cie-zone5.md)、[Edexcel 调研](../examdata/research/exam-timetable-edexcel.md) |
| `frontend/` | 查询前端 | [说明](../frontend/README.md) |
| `gaokao-feasibility/` | 各省高考试卷来源抽样验证 | [报告](../gaokao-feasibility/REPORT.md) |

## 3. 各模块进度与限制

### Edexcel

[最终报告 v1.2](../examdata/tmp_edexcel_final_report.md)记录：IAL 21 科、2490 个 spec 内容点、99 个单元、1818 张 QP、1870 张 MS；43856 题全部有标签，未标注 0，答案关联 38828/43856（88.5%）。一致性审计 3171 标签码无冲突，累计复核 181 题，32 项错标修正后复验通过。

最新 `examdata/tmp_pytest_r13.log` 为 **1179 passed / 6 skipped / 1 warning**。较早 TOEFL 缺口报告中的 provenance 单测失败已在后续 Edexcel 轮次修复，并有全量通过日志；不能把旧失败当作当前未修状态。

覆盖边界：阿拉伯语 38 张 QP 为不可读扫描版，未形成题目；2026 新计算机科目库内无试卷。答案关联率与标签覆盖率不证明所有答案和标签逐题人工核验正确。

### CIE

截至 `summary.json` 的 **2026-10-05 16:36:52**：科目范围并集 205 个代码，当前第三方源列出且已扫描 43 科，其余 162 科标记不可用。目录发现 13877 卷（QP/MS 成对 13274、仅 QP 522、仅 MS 81）。目录单元扫描完成不等于逐卷定位完成。

服务索引 63 个，本地与服务一致 62 个、不同 1 个；当前视觉门槛通过 19 卷。历史 cleaned 为 61 卷，其中 42 卷仍需视觉重验。索引冲突为 `0472/2026/Jun/41`。

最新停止：**2026-10-05 16:30:15**，`8238/2025/Jun/32` 的 QP 下载 HTTP 502。检查点记录离线诊断为代理节点故障；这属于记录中的诊断，本次未重新验证网络。`needs_user_resume=true`，联网重试需明确续跑授权，已下载原件的本地阶段可继续。

续作首先读取检查点、summary 和 service-index-manifest；`pending-work.json` 的生成时间为 10 月 4 日，仍含旧断点，不能直接覆盖最新状态。不要重新从头扫描，也不要将历史 cleaned 自动视为验收通过。

### IELTS

当前 revision 为 `rev-8b21015ab64bb73c`。最新缺口报告记录：6724 题，答案关联 6717，缺失 6、空答案 1；coverage 370 units，complete 0、partial 168、not_extracted 154、unverified 48。仍有题干、选项、附件与官方核验缺口。

336 个音频文件通过哈希检查；音频目录中的可用、候选与 verified 状态分别统计，不能用文件数代替内容核验。逐题对齐 33 identity、331 题，66 窗 verified，其余未核验。S16 保存的回归为主副本 Node 309/309，另一副本 307 pass / 2 skip，pytest 19 passed / 1 skipped；全量数据审计仍为 partial。

最新 S18/G14 跟进：剑 11 T4 阅读 Q19–26 仅部分裁决，Q24 保留 C/D 双值，未获得第二印次官方核验；`pte-4L` 来源检索 0 真命中，仍为 unverified。调查收尾不等于补全数据。PDF 册 20 为分册/抢先版缺口，册 21 无本地整册，详见 [剩余缺口](ielts/IELTS_REMAINING_GAPS.md)。

### TOEFL

六项修复已记录完成，包括详情 URL 与重定向校验、错误页拒绝、听力表格题、阅读多选、era 与套次身份。离线复检 4417 缓存页无失败，971 入口重解析无新增失败；14 道表格题、20 道阅读多选修复有逐项证据。

联网验证为四科各 1 项 Official 54 样本，音频为 3×1KB Range 抽样。完整音频下载、解码、试听、跨进程限速与全量在线对照未完成。源索引 Official 至 54；机经免费 213 条、锁定 112 条，锁定内容未抓取；未宣称支持完整 2026 新版题库。详见 [缺口报告](toefl/TOEFL_REMAINING_GAPS.md)。

### 考试资料、时间表与高考

代码已注册 materials/timetable 路由；资料覆盖公式表、数据手册和随卷 insert 等。印在试卷中的资料只登记，不能假定存在独立可下载文件。

CIE Zone 5 文档记录 25 个可得考季和 2 个不可得考季证据。Edexcel 文档记录四族谱 106 个可得考季、6 个疫情取消考季（404 + `cancelled`）与 15 个穷尽检索不可得考季（404 + reason/evidence）。结构化事件使用随仓库离线快照，运行时不联网，不能称为每次请求实时重新获取。Edexcel 时间表接口已交付并验证：106 季 / 8479 事件 / 23 窗口，取消季、不可得季、R 卷、随机季回归与源 PDF 抽样核对均通过（见 [Edexcel 调研](../examdata/research/exam-timetable-edexcel.md)）。

高考报告记录 31 省均找到可下载样本渠道，GitHub 64/64 个样本下载成功；这是来源可行性抽样，尚未构成全省份、全科目、全年份题库或正式 API 数据集。

## 4. Git、运行状态与交接

本次检查时 `examdata/` 最新提交为 `8da3a09`（2026-10-05 15:05，TOEFL 网关与文档）。文档更新前工作树有 48 个已跟踪文件修改、1218 个未跟踪条目，含大量临时脚本、证据与目录；该数字是时点状态，会随其他会话工作变化。

本次检查时 `127.0.0.1:8000` 有进程监听（PID 36036）。未验证运行进程是否加载最新代码、路由或数据，也没有公网部署验收证据；端口监听不能代替接口验收。

Kimi 对应工作区为 `C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5`，检查时共 19 个会话。优先查看最新 `state.json` 与 `agents/main/wire.jsonl`，会话标题只用于定位任务，实际进度以最后消息和产物为准。

后续顺序：先处理 CIE 停止与索引冲突、视觉重验；按 IELTS 缺口逐项补齐；Edexcel 时间表的最后产物与接口运行验证已完成（106 季 / 8479 事件，见 §3 考试资料、时间表与高考），其余测试、抽样、数据覆盖与生产验收仍分别记录、不合并宣称。
