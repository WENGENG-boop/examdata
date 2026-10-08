"""为 0472/2026/Jun/41 追加 21 条区域目视核验记录。

这些记录来自 2026-10-06 本会话用浏览器查看实际裁剪图/整页图的逐区域核验
（QP 5 区域 + MS 16 区域）。历史记录（2026-10-01 的 14 条）一律保留，
本脚本只追加更晚的 checked_at，由 cleanup_paper.verification_state 取最新者。

幂等：同 (key, question, role, page, bbox) 且 checked_at >= 2026-10-06 的记录
已存在时跳过该条。写入前复核索引 sha256 与预期一致。
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

BATCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BATCH / "tools"))

import batchlib as B  # noqa: E402

if (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower() != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

KEY = "0472/2026/Jun/41"
EXPECTED_INDEX_SHA = "8ee3309e88d28710bee030ccb7738e939d513777b71d800a666f6d496e85a618"

# (question, role, page, bbox, observed)
REGIONS = [
    ("1", "qp", 2, [71.2, 58.8, 540.4, 500.4],
     "完整：题号 1 与 'You are Eneida Alves…' 情境、'Complete this form.'、表单三行"
     "（Your name: Eneida Alves / Your age / What day you can help）、'Now give more "
     "information.'、Write about 三要点、'Write 20–30 words.'、4 条作答虚线、右下 [5]。"
     "区域顶从页眉条码下缘起，底在 [5] 下方空白；右边距条 DO NOT WRITE IN THIS MARGIN "
     "与页脚 '© Cambridge University Press & Assessment 2026 / [Turn over]' 在区域外。"),
    ("2", "qp", 3, [70.4, 58.8, 541.2, 530.0],
     "完整：题号 2 与写作任务（Write about 三要点、'Write 80–90 words.'）、作答虚线、"
     "右下 [12]。双色探针核验：最后一条作答线与 [12]（约 510–515pt）在底界 530 上方，"
     "530→748.4pt 为纯空白；页脚 '© Cambridge University Press & Assessment 2026  "
     "0472/41/M/J/26  [Turn over]' 与蓝线 748.4 在区域外。内容无截断。"),
    ("3", "qp", 4, [70.8, 58.8, 540.4, 420.0],
     "完整：'3 Answer Question 3(a) or Question 3(b).'、'Write 130–140 words.'、"
     "(a)/(b) 两选项全文（各 5 条 bullet 与各自 [28]）。底界 420.0 在 (b) 的 [28]"
     "（约 409pt）下方空白；其下共享作答线区按原页设计属作答空间，不在任务文本区。"),
    ("3(a)", "qp", 4, [70.8, 107.6, 540.4, 278.8],
     "完整：仅 (a) 块（标题行与 5 条 bullet 全文）及尾部版式符 'OR'；无 (b) 内容混入。"
     "底界 278.8 为 (a)/(b) 的干净分界（OR 版式符归在 3(a) 底）。"),
    ("3(b)", "qp", 4, [70.8, 278.8, 540.4, 420.0],
     "完整：从 '(b) Spending time…' 标题起，含全部 bullet 与 [28]。顶界 278.8 与 (a) "
     "区干净切分，无 (a) 内容混入。"),
    ("1", "ms", 7, [102.0, 56.0, 358.5, 734.0],
     "完整：题号 '1' 与题目复述；'Your age' 与 'What day you can help' 各附 'Award 1 "
     "mark for a correct item that fulfils the communicative purpose of the rubric.'；"
     "'Now give more information.'、Write about 三要点、'Write 20–30 words.'、"
     "'Read the whole answer and award a mark out of 3 using the table below.'、记分 5。"
     "区域为左栏，右栏空白与页脚在区域外。"),
    ("1", "ms", 8, [72.0, 56.0, 265.0, 734.0],
     "完整：Q1 续页 3/2/1/0 分带评分表（Marks/Descriptor/Guidance 三列），从 'All three "
     "points covered appropriately…' 到 'No creditable content.'；Guidance='Examples of "
     "linguistic inaccuracies: lapses in agreements, tenses/time frames, spelling, etc.'。"
     "与 Q1 题干页（p7）相接续。"),
    ("2", "ms", 9, [102.0, 56.0, 231.0, 734.0],
     "完整：题号 '2'、'Favourite celebration' 及 4 条 bullet 要点、'Write 80–90 "
     "words.'、'Read the whole answer…out of 12 using the table below.'、记分 12。"),
    ("2", "ms", 10, [72.0, 56.0, 450.0, 734.0],
     "完整：Q2 续页 10–12/7–9/4–6/1–3/0 五分带评分表与 Guidance（'…and, or, but, "
     "because, then.'）。与 p9 题干页相接续。"),
    ("3", "ms", 11, [102.0, 56.0, 523.0, 734.0],
     "完整：共享抬头、(a) 块、(3)(b) 版式符 OR 与 (b) 块；每选项含 5 条 bullet 与 "
     "'Read the whole answer, award a mark from each of the three tables below and add up "
     "the total. Marks are available for: • task completion (maximum 10 marks) • range "
     "(maximum 10 marks) • accuracy (maximum 8 marks).'，27+1 合计 [28]。首行版式符 OR "
     "属原页版式。"),
    ("3(a)", "ms", 11, [124.8, 56.0, 308.4, 734.0],
     "仅含 (a) 块全文（含 5 条 bullet 与三表说明、[28]），无 (b) 内容；与 3(b) 在 "
     "x=308.4 干净切分，裁剪图对照确认边界无交叉。"),
    ("3(b)", "ms", 11, [308.4, 56.0, 523.0, 734.0],
     "仅含 (b) 块全文（首行版式符 'OR' 属原页版式；含 5 条 bullet 与三表说明、[28]），"
     "无 (a) 内容；与 3(a) 在 x=308.4 干净切分。"),
    ("3", "ms", 12, [72.0, 56.0, 377.5, 734.0],
     "完整：Q3 三个评分表之一 'Task completion'（9–10/7–8/5–6/3–4/1–2/0 六分带）。"
     "为 Q3 的跨页续接评分材料。"),
    ("3", "ms", 13, [72.0, 56.0, 364.5, 734.0],
     "完整：Q3 三个评分表之二 'Range'（同六分带）。为 Q3 的跨页续接评分材料。"),
    ("3", "ms", 14, [72.0, 56.0, 290.5, 734.0],
     "完整：Q3 三个评分表之三 'Accuracy'（7–8/5–6/3–4/1–2/0 五分带）。为 Q3 的跨页"
     "续接评分材料。"),
    ("3(a)", "ms", 12, [72.0, 56.0, 377.5, 734.0],
     "与 3/ms/p12 同一裁剪区域：3(a) 与 3(b) 共用 Task completion 表的同一页；内容为 "
     "9–10/7–8/5–6/3–4/1–2/0 六分带完整表。共用关系已如实注明。"),
    ("3(a)", "ms", 13, [72.0, 56.0, 364.5, 734.0],
     "与 3/ms/p13 同一裁剪区域：3(a)/3(b) 共用 Range 表页；内容为同六分带完整表。"
     "共用关系已如实注明。"),
    ("3(a)", "ms", 14, [72.0, 56.0, 290.5, 734.0],
     "与 3/ms/p14 同一裁剪区域：3(a)/3(b) 共用 Accuracy 表页；内容为 7–8/5–6/3–4/"
     "1–2/0 五分带完整表。共用关系已如实注明。"),
    ("3(b)", "ms", 12, [72.0, 56.0, 377.5, 734.0],
     "与 3/ms/p12 同一裁剪区域：3(b) 与 3(a) 共用 Task completion 表页；内容为 "
     "9–10/7–8/5–6/3–4/1–2/0 六分带完整表。共用关系已如实注明。"),
    ("3(b)", "ms", 13, [72.0, 56.0, 364.5, 734.0],
     "与 3/ms/p13 同一裁剪区域：3(b)/3(a) 共用 Range 表页；内容为同六分带完整表。"
     "共用关系已如实注明。"),
    ("3(b)", "ms", 14, [72.0, 56.0, 290.5, 734.0],
     "与 3/ms/p14 同一裁剪区域：3(b)/3(a) 共用 Accuracy 表页；内容为 7–8/5–6/3–4/"
     "1–2/0 五分带完整表。共用关系已如实注明。"),
]


def main() -> int:
    index_path = B.index_dir("0472", 2026, "Jun", "41") / "cie-index.json"
    sha = B.sha256_file(index_path)
    if sha != EXPECTED_INDEX_SHA:
        print(f"索引 sha256 不符：{sha} != {EXPECTED_INDEX_SHA}")
        return 2

    existing = set()
    for record in B.read_jsonl(B.VERIFICATION):
        if record.get("key") != KEY:
            continue
        stamp = str(record.get("checked_at") or record.get("at") or "")
        if stamp < "2026-10-06":
            continue
        existing.add((str(record.get("question")), str(record.get("role")),
                      int(record.get("page") or 0),
                      tuple(round(float(v), 2) for v in record.get("bbox") or [])))

    written = skipped = 0
    for question, role, page, bbox, observed in REGIONS:
        key_tuple = (question, role, page, tuple(round(float(v), 2) for v in bbox))
        if key_tuple in existing:
            skipped += 1
            continue
        B.append_jsonl(B.VERIFICATION, {
            "key": KEY,
            "question": question,
            "role": role,
            "page": page,
            "bbox": bbox,
            "method": "browser_visual_snapshot",
            "checks": {
                "content_complete": True,
                "boundary_checked": True,
                "role_matches": True,
                "observed": observed,
            },
            "issues": [],
            "checked_at": B.now_iso(),
            "index_sha256": EXPECTED_INDEX_SHA,
        })
        written += 1
    print(f"写入 {written} 条，跳过已存在 {skipped} 条；索引 sha256={sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
