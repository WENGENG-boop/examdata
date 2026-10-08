import json
from pathlib import Path
from collections import Counter

p = Path(__file__).parent            # work/coordinate-audit-2026-10-05
batch = p.parents[1]                 # cie-location-batch
d = json.loads((p / 'evidence.json').read_text(encoding='utf-8'))
papers = json.loads((batch / 'papers.json').read_text(encoding='utf-8'))
summary = json.loads((batch / 'summary.json').read_text(encoding='utf-8'))
ck = json.loads((batch / 'checkpoint.json').read_text(encoding='utf-8'))

entries = d['entries']
svc = d['service']
counts = d['counts']
stage = d['stage_counts']
kc = d['kind_counts']
n = lambda x: f'{x:,}'

# ---- 逐科聚合 ----
by = Counter(v['subject'] for v in papers.values())
indexed = Counter(r['subject'] for r in entries)
gate = Counter(r['subject'] for r in entries if r['visual_gate_passed'])

# ---- QP/MS 文件条目数 ----
qp_files = sum(len(v.get('qp') or []) for v in papers.values())
ms_files = sum(len(v.get('ms') or []) for v in papers.values())

# ---- 视觉证据聚合（对当前 63 卷逐条求和）----
def vs(e):
    return e.get('verification') or {}

miss = sum(vs(e).get('missing', 0) for e in entries)
vem = sum(vs(e).get('visual_evidence_missing', 0) for e in entries)
sdu = sum(vs(e).get('self_declared_unverified', 0) for e in entries)
gate_pass = sum(1 for e in entries if e.get('visual_gate_passed'))
gate_fail = len(entries) - gate_pass

# ---- 逐份重读本地索引，核对坐标声明与 QP/MS 摘要 ----
decl_ok, decl_bad = 0, []
for e in entries:
    try:
        idx = json.loads(Path(e['local_index']).read_text(encoding='utf-8'))
        roles = {doc.get('role') for doc in (idx.get('documents') or [])}
        if (idx.get('coordinate_system') == 'unrotated_pdf_points_top_left'
                and idx.get('page_base') == 1 and {'qp', 'ms'} <= roles):
            decl_ok += 1
        else:
            decl_bad.append(e['key'])
    except Exception as exc:
        decl_bad.append(f"{e['key']}({exc})")

# ---- 题号连续性问题 ----
num_problems = [(e['key'], pr) for e in entries
                for pr in (e.get('verification_problems') or []) if '题号' in pr]

# ---- 服务冲突 ----
diff = [e for e in entries if e.get('comparison') == 'different']

# ---- 覆盖边界（取自 summary.json / checkpoint.json 当前值）----
su = summary['subject_universe']
cc = summary['catalogue_cells']
union_codes = su['union_codes']
listed = su['third_party_listed']
unavail = su['official_only']
cells_done = ck['totals']['cells_done']
requested = cc['actually_requested']
inferred = cc['inferred_not_requested']
pct = 100.0 * len(entries) / d['papers_total']

report = f'''# CIE 文件解析与坐标完整性检查报告

检查时间：{d['checked_at']}（北京时间）。结论：**没有全部解析、记录完坐标；全量作业远未完成。**

范围是当前 `cie-location-batch` 的第三方 CIE 工坊目录：2000–2026 年、Mar/Jun/Nov。发现清单中的一“卷”是科目/年份/考季/卷号组合，不是一份 PDF；paired 含 QP 和 MS 两份文件。不能把目录扫描 complete=true 当成逐卷解析完成。

本报告所有数字均由本次审计（evidence.json）与当前 `papers.json`、`summary.json`、`checkpoint.json`、63 份索引文件重新计算，未沿用任何旧报告数值。

## 当前实测结果

| 检查项 | 数量/结果 |
|---|---|
| 已发现卷 | {n(d['papers_total'])} |
| paired / qp_only / ms_only | {n(kc.get('paired',0))} / {n(kc.get('qp_only',0))} / {n(kc.get('ms_only',0))} |
| 发现的 QP/MS 文件条目（按卷配对口径） | {n(qp_files+ms_files)}（QP {n(qp_files)}；MS {n(ms_files)}） |
| 本地永久索引 | {len(entries)} 卷，覆盖 {len(indexed)} 科；占发现卷约 {pct:.3f}% |
| 未找到永久索引 | {n(d['missing_indexes'])} 卷；逐卷见 papers-without-index.csv |
| 状态 | {'；'.join(f"{k} {n(v)}" for k, v in stage.items())} |
| 索引中的题目记录 | {n(counts['questions'])}（含父题和子题，并非独立大题数） |
| QP / MS 区域 | {n(counts['qp_regions'])} / {n(counts['ms_regions'])}，共 {n(counts['qp_regions']+counts['ms_regions'])} |
| 缺 QP / 缺 MS 区域的题目记录 | {n(counts['missing_qp'])} / {n(counts['missing_ms'])} |
| uncertain=true | {n(counts['uncertain'])} 条题目记录 |
| Schema 与基础 bbox 检查 | {len(entries)}/{len(entries)} 通过；schema 无效 {d['schema_invalid_indexes']}、bbox 无效 {d['basic_bbox_invalid_indexes']} |
| 指定服务数据目录的索引文件 | {svc['in_service']}/{svc['count']} 存在；{svc['comparison_counts'].get('identical',0)} 一致，{svc['comparison_counts'].get('different',0)} 不一致 |
| 当前索引的已有视觉证据门槛 | {gate_pass} 通过，{gate_fail} 未通过 |
| 无核验记录的当前区域 | {n(miss)} |
| 已有记录但缺完整视觉证据或当前索引摘要绑定 | {n(vem)} 区域 |
| 其中记录自述未做视觉核验 | {n(sdu)} 区域（与上项重叠，不能相加） |

'''
if decl_bad:
    report += f'{decl_ok}/{len(entries)} 份索引声明 `unrotated_pdf_points_top_left`、1-based 页码并含 QP/MS 文档摘要；不合规：{decl_bad}。'
else:
    report += f'{len(entries)} 份索引均声明 `unrotated_pdf_points_top_left`、1-based 页码并含 QP/MS 文档摘要。'
report += f'''所有索引均含 MS 文档，因此 {n(counts['missing_ms'])} 条空 MS 不能仅用“整卷没有 MS”解释；需分别判定父题聚合、共用评分条目、无独立评分或漏定位。现有视觉 gate 只核对索引中存在的区域，**不会自动发现未建立的 MS 区域或漏掉的最后一道题**。{gate_pass} 卷通过不等于这些卷所有题目及 MS 坐标都已独立证实完整。

## 明确问题

'''
# 1. 服务冲突
if diff:
    for e in diff:
        cf = e.get('changed_fields') or {}
        order = [k for k in ('text', 'ms', 'qp', 'notes') if k in cf] + [k for k in cf if k not in ('text', 'ms', 'qp', 'notes')]
        cf_txt = '、'.join(f'{k} {cf[k]} 条' for k in order)
        v = vs(e)
        report += (f"1. `{e['key']}` 本地与服务文件不一致，涉及题号 {'、'.join(e.get('changed_questions') or [])}：{cf_txt}不同。"
                   f"该卷还有 {n(v.get('missing',0))} 个当前区域无核验记录，{n(v.get('visual_evidence_missing',0))} 个区域缺完整视觉证据。"
                   f"不能直接覆盖服务文件，先判定哪一版正确。\n")
else:
    report += '1. 当前无本地与服务索引不一致的卷。\n'
# 2. 题号连续性
if num_problems:
    detail = '；'.join(f"`{k}`：{pr}" for k, pr in num_problems)
    report += f'2. 题号连续性发现：{detail}。以上是结构异常，需原件确认是否为真实漏题或原卷编号例外。\n'
else:
    report += '2. 当前未发现题号连续性异常。\n'
# 3. 停止点
sd = ck.get('stop_detail') or {}
report += (f"3. 当前 checkpoint 停于 `{ck.get('current_paper')}` 的 {sd.get('role')} 下载 {sd.get('error')}，"
           f"时间 {ck.get('stopped_at')}；`needs_user_resume={str(ck.get('needs_user_resume')).lower()}`，"
           f"原因 {ck.get('stop_reason')}。本次检查未访问上游、未重试、未恢复批次。\n")
# 4. 旧报告对照（历史记录）
report += (f"4. 旧 `work/PhaseD-final-report.md`（历史记录，非本次实测）记载 cleaned 62、服务 identical 63、冲突 0、待重验 43。"
           f"当前实测是 cleaned {stage.get('cleaned')}、identical {svc['comparison_counts'].get('identical',0)}、"
           f"different {svc['comparison_counts'].get('different',0)}、未通过视觉 gate {gate_fail}。应使用本次快照，不能沿用旧报告数字。\n")

report += f'''
## 覆盖边界

现有 summary 记录 {union_codes} 科并集，其中第三方列出 {listed} 科，{unavail} 科标为 subject_unavailable；{listed} 科目录格实扫 {n(cells_done)}，另有 {n(inferred)} 格未请求而是推断（实请求 {n(requested)} 格含两格探查）。此部分是当前本地发现记录，未重新请求网站，不能证明第三方资源与剑桥官方全集完全相同。下表逐科核对本地发现卷与实际索引；没有索引的科目仍属于待办。

| 科目 | 发现卷 | 有索引 | 视觉证据 gate 通过 |
|---|---:|---:|---:|
'''
report += '\n'.join(f'| {s} | {by[s]} | {indexed[s]} | {gate[s]} |' for s in sorted(by))
report += '''

## 逐卷已有索引检查清单

“通过”仅表示按仓库当前规则核对已有记录通过；本次未重新逐图查看 PDF。空 MS 列须单独验收。

| 卷 | 题目记录 | 空 MS | uncertain | 服务文件比较 | 视觉 gate |
|---|---:|---:|---:|---|---|
'''
report += '\n'.join(
    f"| {r['key']} | {r['questions']} | {r['missing_ms']} | {r['uncertain']} | {r['comparison']} | "
    f"{'通过' if r['visual_gate_passed'] else '未通过'} |" for r in entries)
report += f'''

## 检查方法与限制

- 从 papers.json 与实际 indexes/**/cie-index.json 做身份集合差集，不按 cleaned 或 summary 推算是否有索引。
- 调用现有 validate_index.validate 检查 Schema/语义，并逐题检查 QP/MS、uncertain、基础 bbox。
- 调用 service_audit.build_manifest 和 cleanup_paper.verification_state：按当前区域、最新记录、作废标记、当前索引 SHA256、视觉内容/边界/角色证据及题号连续性核对。
- 服务比较是指定 `{svc['service_index_dir']}` 的磁盘文件比较，排除服务包装字段 method/reviewed；未调用实时 API、未证明运行进程的数据目录，也未测日后重新下载裁剪链路。
- 未获取原 PDF，无法重新确认页码上限、页面宽高内边界、旋转转换正确性、每页漏题、图表/续页完整性或内容真实性。Schema/坐标存在不等于坐标正确。
- sources_unchanged={str(d['sources_unchanged']).lower()}：检查前后 papers、subjects、catalogue-grid、checkpoint、summary、verification 的 SHA256 一致。仅新增本次脚本及报告证据；未导入、删除、修改批次原始状态。

复现命令（PowerShell，从 C:/Users/weo/Desktop/api 执行）：

```powershell
$env:PYTHONIOENCODING='utf-8'
& .\\examdata\\.venv\\Scripts\\python.exe .\\cie-location-batch\\work\\coordinate-audit-2026-10-05.py
& .\\examdata\\.venv\\Scripts\\python.exe .\\cie-location-batch\\work\\coordinate-audit-2026-10-05\\write_deliverables.py
& .\\examdata\\.venv\\Scripts\\python.exe .\\cie-location-batch\\work\\coordinate-audit-2026-10-05\\write_queue_deliverables.py
& .\\examdata\\.venv\\Scripts\\python.exe .\\cie-location-batch\\work\\coordinate-audit-2026-10-05\\write_audit_deliverables2.py
```

证据：同目录 evidence.json（{len(entries)} 卷详细问题、核验统计、来源摘要、停止状态）、papers-without-index.csv（{n(d['missing_indexes'])} 卷待办）。报告为该时间点快照，后续批次变化需重跑核对。

## 配套交付物

同目录 `deliverables/` 由本次实测生成，含：`stats.json`（机器可读统计）、`resumable-queue.jsonl`（可恢复队列，首行=下一个应处理卷）、`resumable-queue-summary.json`、`blocked-queue.jsonl`、`reverify-queue.json`、`empty-ms-classification.json`（空 MS 逐条分类）、`incomplete-per-paper.jsonl`（逐卷未完成清单）、`source-gaps.json`（来源缺口）、`service-conflicts.json`、`cleanup-records.json`、`resume-checkpoint.json`、`README.md`。每项均标注本次实测 / 历史记录 / not_run。
'''
(p / '检查报告.md').write_text(report, encoding='utf-8')
print(f'wrote {p / "检查报告.md"} ({len(report)} chars); entries={len(entries)} gate={gate_pass}/{gate_fail} miss/vem/sdu={miss}/{vem}/{sdu}')
