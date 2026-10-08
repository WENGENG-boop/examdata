"""r7: build agent batches from scope + points. Writes tmp_r7_batches/."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BATCHES = {
    'accounting': [1728, 1737, 1752, 1753],
    'maths-pure': [3250, 3255, 3256, 3270, 3273, 3274, 3290, 3291, 3318],
    'maths-stats-mech': [3257, 3263, 3268, 3271, 3294, 3297, 3319],
    'law-yla0': [3115, 3116, 3117, 3118, 3150, 3155],
    'law-yla1': [3106, 3109, 3112, 3113, 3120, 3121, 3122, 3123,
                 3130, 3143, 3146, 3156, 3157, 3164, 3167, 3168],
    'geo-german': [2342, 2378],
}

DOTS = re.compile(r'\.{8,}')
BLANKS = re.compile(r'\n{3,}')
SPACES = re.compile(r'[ \t]{2,}')


def clean_stem(txt: str, limit: int = 1400) -> str:
    t = (txt or '').replace('\r', '')
    t = DOTS.sub(' … ', t)
    t = SPACES.sub(' ', t)
    t = BLANKS.sub('\n\n', t)
    t = t.strip()
    return t[:limit]


def main() -> None:
    scope = [json.loads(l) for l in (ROOT / 'tmp_r7_scope.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    points = json.loads((ROOT / 'tmp_r7_points.json').read_text(encoding='utf-8'))
    by_doc: dict[int, list[dict]] = {}
    for x in scope:
        by_doc.setdefault(x['doc_id'], []).append(x)

    out_root = ROOT / 'tmp_r7_batches'
    out_root.mkdir(exist_ok=True)
    manifest = {}
    for batch_id, docs in BATCHES.items():
        bdir = out_root / batch_id
        bdir.mkdir(exist_ok=True)
        qs = []
        units = set()
        for did in docs:
            for x in by_doc.get(did, []):
                units.add(x['truth_unit'])
                qs.append({
                    'question_id': x['question_id'],
                    'doc_id': did,
                    'doc_title': x['doc_title'],
                    'truth_unit': x['truth_unit'],
                    'print_code': x['print_code'],
                    'number_label': x['number_label'],
                    'paper_code': x['paper_code'],
                    'current': [r['code'] for r in x['rows']],
                    'stem': clean_stem(x['stem']),
                })
        with open(bdir / 'questions.jsonl', 'w', encoding='utf-8') as fh:
            for q in qs:
                fh.write(json.dumps(q, ensure_ascii=False) + '\n')
        with open(bdir / 'points.txt', 'w', encoding='utf-8') as fh:
            for u in sorted(units):
                pu = points[u]
                fh.write(f'===== {u} ({pu["n_points"]} points) =====\n')
                for p in pu['points']:
                    fh.write(f'{p["code"]} | {p["name"]}\n')
                    if p.get('text'):
                        fh.write(f'    {p["text"].strip()[:400]}\n')
                fh.write('\n')
        instructions = f"""# r7 batch: {batch_id}

你在为 Edexcel IAL 试卷修复“单元错行”：以下 {len(qs)} 道题的现有标签单元与该试卷**打印单元**不一致，
需要你按题目内容，从正确单元的候选点清单中为每题选 **恰好 1 个** 代码。

- 题目文件：`tmp_r7_batches/{batch_id}/questions.jsonl`（每行一题：question_id/number_label/current/stem…）
- 候选点清单：`tmp_r7_batches/{batch_id}/points.txt`（每题只能从**其 truth_unit** 对应的清单里选）
- 答案文件（你来创建）：`tmp_r7_batches/{batch_id}/answers.ans.txt`
  格式：每行 `qid CODE`（两段，空白分隔）；`#` 开头是注释；禁止 `?`；每题必答且只答一次。

工作方法（务必）：
1. 先通读 questions.jsonl 与 points.txt，弄清每个 truth_unit 的候选点。
2. 对每题运行上下文脚本拿同卷兄弟题标签与 MS 线索（每次 4-6 个 qid）：
   `./.venv/Scripts/python.exe -X utf8 tmp_bio_ctx.py QID1 QID2 ...`
   兄弟题里**单元正确**的标签是最强参照：同主题用同一点码。
3. 题干因 PDF 解析残缺时，直接看试卷 PDF 原页：
   `./.venv/Scripts/python.exe -X utf8 tmp_acct_pdf.py <qid> --pages 1-4`（或 --find "关键词"）。
4. 判定规则：内容优先；同卷同主题沿用兄弟题已正确单元的点码；绝不选清单外的代码。
5. 写完答案后自检（必须跑，直到 0 错误）：
   `./.venv/Scripts/python.exe -X utf8 tmp_r7_check_ans.py --batch {batch_id}`
6. 最后汇报：完成题数、自检结果、任何不确定项。

注意：questions.jsonl 里 `current` 是**将被替换的错单元旧标签**，只能当提示，不能直接抄。
"""
        (bdir / 'INSTRUCTIONS.md').write_text(instructions, encoding='utf-8')
        manifest[batch_id] = {
            'docs': docs, 'units': sorted(units), 'n_questions': len(qs),
            'questions_file': f'tmp_r7_batches/{batch_id}/questions.jsonl',
            'points_file': f'tmp_r7_batches/{batch_id}/points.txt',
            'ans_file': f'tmp_r7_batches/{batch_id}/answers.ans.txt',
        }
        print(f'{batch_id}: {len(qs)} questions, docs={docs}, units={sorted(units)}')
    (out_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    print('total:', sum(m['n_questions'] for m in manifest.values()))


if __name__ == '__main__':
    main()
