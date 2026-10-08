"""检查候选模式对 183 行分类失败记录的覆盖情况。"""
import json
import re
from collections import Counter, defaultdict

PATTERNS = {
    "before_entering": r"before entering your candidate information",
    "write_name_here": r"write your name here",
    "no_other_materials": r"you do not need any other materials",
    "instr_cand_teach": r"instructions to (?:the )?(?:teacher/examiner|candidate)\b",
    "paper_reference": r"paper reference",
    "transcript_listening": r"transcript of (?:the )?listening test",
    "speaking_materials": r"speaking materials",
    "teacher_examiner_booklet": r"teacher/examiner booklet",
    "candidate_version": r"candidate version",
    "teacher_version": r"teacher/examiner version",
}

fails = []
for line in open('tmp_classify_scan.log', encoding='utf-8'):
    m = re.match(r"FAIL doc=(\d+) (\S+) (.*) err=(.*) pages=(\d+)", line.strip())
    if m:
        fails.append({'doc': int(m.group(1)), 'subject': m.group(2), 'title': m.group(3), 'err': m.group(4)})
print(f"failure rows parsed: {len(fails)}")

# corpus text by doc_id: join all rows of same doc
texts = defaultdict(list)
for line in open('tmp_corpus_text.jsonl', encoding='utf-8'):
    r = json.loads(line)
    texts[r['doc_id']].append(re.sub(r"\s+", " ", r['text']))

comp = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}

uncovered = []
covered_by = Counter()
err_counter = Counter()
for f in fails:
    t = " || ".join(texts.get(f['doc'], []))
    hits = [k for k, rx in comp.items() if rx.search(t)]
    err_counter[f['err']] += 1
    if hits:
        for h in hits:
            covered_by[h] += 1
    else:
        uncovered.append(f)

print("\ncovered_by counts (rows):", dict(covered_by))
print("errors:", dict(err_counter))
print(f"\nUNCOVERED rows: {len(uncovered)}")
for f in uncovered:
    t = " || ".join(texts.get(f['doc'], []))[:120]
    print(f"  doc={f['doc']} {f['subject']} err={f['err']} title={f['title'][:60]!r} text={t!r}")
