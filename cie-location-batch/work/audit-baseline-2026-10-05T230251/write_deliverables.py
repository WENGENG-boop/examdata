import json
from pathlib import Path
from collections import Counter
p=Path(__file__).parent
d=json.loads((p/'evidence.json').read_text(encoding='utf-8'))
papers=json.loads((p.parents[1]/'papers.json').read_text(encoding='utf-8'))
by=Counter(v['subject'] for v in papers.values())
indexed=Counter(r['subject'] for r in d['entries'])
gate=Counter(r['subject'] for r in d['entries'] if r['visual_gate_passed'])
report=f'''# CIE 文件解析与坐标完整性检查报告

检查时间：{d['checked_at']}（北京时间）。结论：**没有全部解析、记录完坐标；全量作业远未完成。**

范围是当前 `cie-location-batch` 的第三方 CIE 工坊目录：2000–2026 年、Mar/Jun/Nov。发现清单中的一“卷”是科目/年份/考季/卷号组合，不是一份 PDF；paired 含 QP 和 MS 两份文件。不能把目录扫描 complete=true 当成逐卷解析完成。

## 当前实测结果

| 检查项 | 数量/结果 |
|---|---|
| 已发现卷 | 13,877 |
| paired / qp_only / ms_only | 13,274 / 522 / 81 |
| 发现的 QP/MS 文件条目（按卷配对口径） | 27,151（QP 13,796；MS 13,355） |
| 本地永久索引 | 63 卷，覆盖 18 科；占发现卷约 0.454% |
| 未找到永久索引 | 13,814 卷；逐卷见 papers-without-index.csv |
| 状态 | discovered 13,813；cleaned 61；downloaded 1；download_interrupted 1；download_failed 1 |
| 索引中的题目记录 | 1,855（含父题和子题，并非独立大题数） |
| QP / MS 区域 | 2,155 / 1,783，共 3,938 |
| 缺 QP / 缺 MS 区域的题目记录 | 0 / 384 |
| uncertain=true | 374 条题目记录 |
| Schema 与基础 bbox 检查 | 63/63 通过；无非有限、负起点或非正宽高框 |
| 指定服务数据目录的索引文件 | 63/63 存在；62 一致，1 不一致 |
| 当前索引的已有视觉证据门槛 | 19 通过，44 未通过 |
| 无核验记录的当前区域 | 38 |
| 已有记录但缺完整视觉证据或当前索引摘要绑定 | 2,412 区域 |
| 其中记录自述未做视觉核验 | 2,126 区域（与上项重叠，不能相加） |

63 份索引均声明 `unrotated_pdf_points_top_left`、1-based 页码并含 QP/MS 文档摘要。所有索引均含 MS 文档，因此 384 条空 MS 不能仅用“整卷没有 MS”解释；需分别判定父题聚合、共用评分条目、无独立评分或漏定位。现有视觉 gate 只核对索引中存在的区域，**不会自动发现未建立的 MS 区域或漏掉的最后一道题**。19 卷通过不等于这 19 卷所有题目及 MS 坐标都已独立证实完整。

## 明确问题

1. `0472/2026/Jun/41` 本地与服务文件不一致，涉及题号 1、2、3、3(a)、3(b)：text 5 条、ms 5 条、qp 3 条、notes 5 条不同。该卷还有 19 个当前区域无核验记录，2 个区域缺完整视觉证据。不能直接覆盖服务文件，先判定哪一版正确。
2. 题号连续性发现：`8386/2025/Jun/11`、`8386/2026/Jun/12`、`8386/2026/Jun/13` 均缺顶层题号 1；`0495/2026/Jun/11` 的 2(a)、3(a) 存在仅列 (ii) 的子题缺口。以上是结构异常，需原件确认是否为真实漏题或原卷编号例外。
3. 当前 checkpoint 停于 `8238/2025/Jun/32` 的 QP 下载 HTTP 502，时间 2026-10-05 16:30:15；`needs_user_resume=true`。本次检查未访问上游、未重试、未恢复批次。
4. 旧 `work/PhaseD-final-report.md` 仍写 cleaned 62、服务 identical 63、冲突 0、待重验 43。当前实测是 cleaned 61、identical 62、different 1、未通过视觉 gate 44。应使用本次快照，不能沿用旧报告数字。

## 覆盖边界

现有 summary 记录 205 科并集，其中第三方列出 43 科，162 科标为 subject_unavailable；43 科目录格实扫 3,483，另有 12,798 格未请求而是推断。此部分是当前本地发现记录，未重新请求网站，不能证明第三方资源与剑桥官方全集完全相同。下表逐科核对本地发现卷与实际索引；没有索引的科目仍属于待办。

| 科目 | 发现卷 | 有索引 | 视觉证据 gate 通过 |
|---|---:|---:|---:|
'''
report+='\n'.join(f'| {s} | {by[s]} | {indexed[s]} | {gate[s]} |' for s in sorted(by))
report+='''

## 逐卷已有索引检查清单

“通过”仅表示按仓库当前规则核对已有记录通过；本次未重新逐图查看 PDF。空 MS 列须单独验收。

| 卷 | 题目记录 | 空 MS | uncertain | 服务文件比较 | 视觉 gate |
|---|---:|---:|---:|---|---|
'''
report+='\n'.join(f"| {r['key']} | {r['questions']} | {r['missing_ms']} | {r['uncertain']} | {r['comparison']} | {'通过' if r['visual_gate_passed'] else '未通过'} |" for r in d['entries'])
report+='''

## 检查方法与限制

- 从 papers.json 与实际 indexes/**/cie-index.json 做身份集合差集，不按 cleaned 或 summary 推算是否有索引。
- 调用现有 validate_index.validate 检查 Schema/语义，并逐题检查 QP/MS、uncertain、基础 bbox。
- 调用 service_audit.build_manifest 和 cleanup_paper.verification_state：按当前区域、最新记录、作废标记、当前索引 SHA256、视觉内容/边界/角色证据及题号连续性核对。
- 服务比较是指定 `examdata/.pytest_cache/callable-api/question_indexes/cie` 的磁盘文件比较，排除服务包装字段 method/reviewed；未调用实时 API、未证明运行进程的数据目录，也未测日后重新下载裁剪链路。
- 未获取原 PDF，无法重新确认页码上限、页面宽高内边界、旋转转换正确性、每页漏题、图表/续页完整性或内容真实性。Schema/坐标存在不等于坐标正确。
- sources_unchanged=true：检查前后 papers、subjects、catalogue-grid、checkpoint、summary、verification 的 SHA256 一致。仅新增本次脚本及报告证据；未导入、删除、修改批次原始状态。

复现命令（PowerShell，从 C:/Users/weo/Desktop/api 执行）：

```powershell
$env:PYTHONIOENCODING='utf-8'
& .\examdata\.venv\Scripts\python.exe .\cie-location-batch\work\coordinate-audit-2026-10-05.py
```

证据：同目录 evidence.json（63 卷详细问题、核验统计、来源摘要、停止状态）、papers-without-index.csv（13,814 卷待办）。报告为该时间点快照，后续批次变化需重跑核对。
'''
(p/'检查报告.md').write_text(report,encoding='utf-8')
