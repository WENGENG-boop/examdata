"""候选短语在真实语料上的命中分布：按 db_type 统计，识别假阳性风险。"""
import json
import re
from collections import Counter

CANDIDATES = [
    ("qp:before_entering", r"before entering your candidate information"),
    ("qp:write_name_here", r"write your name here"),
    ("qp:no_other_materials", r"you do not need any other materials"),
    ("qp:instr_candidate", r"instructions to (?:the )?candidate\b"),
    ("qp:instr_teacher", r"instructions to (?:the )?(?:teacher/examiner|teacher)\b"),
    ("qp:paper_reference", r"paper reference"),
    ("qp:total_marks_tbl", r"total marks\b"),
    ("qp:centre_number", r"centre number"),
    ("qp:advice", r"\badvice\b\s*\n?\s*read"),
    ("tr:transcript_listening", r"transcript of (?:the )?listening test"),
    ("tr:transcript_of", r"\btranscript\b"),
    ("ms:marks_awarded", r"how the marks should be awarded"),
    ("ms:mark_scheme_norm", r"mark scheme"),
]

rows = [json.loads(l) for l in open('tmp_corpus_text.jsonl', encoding='utf-8')]
print(f"total rows: {len(rows)}")

for name, pat in CANDIDATES:
    rx = re.compile(pat, re.I)
    hits = [r for r in rows if rx.search(re.sub(r"\s+", " ", r['text']))]
    by_type = Counter(r['db_type'] for r in hits)
    print(f"\n=== {name}  hits={len(hits)}")
    print("   by db_type:", dict(by_type))
    risky = [r for r in hits if r['db_type'] not in ('question_paper', 'specimen_paper', None)]
    for r in risky[:12]:
        print(f"   RISK doc={r['doc_id']} {r['subject']} db={r['db_type']} {r['title'][:70]!r}")
