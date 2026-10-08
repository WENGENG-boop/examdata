import json, sqlite3, re, unicodedata

BASE = "examdata/.data/tagging/review-export/ial-psychology"
con = sqlite3.connect("examdata/.data/examdata.db")
cur = con.cursor()

def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\s\.\u2026]+", " ", s).strip().lower()
    s = re.sub(r"\(total for question \d+ = \d+ marks\)", "", s)
    return s

# 1. batch-001 paper info
b1 = [json.loads(l) for l in open(f"{BASE}/batches/batch-001.jsonl", encoding="utf-8")]
print("=== batch-001 paper info ===")
for r in b1:
    qid = r["question_id"]
    row = cur.execute("""select p.id, p.paper_no, d.title from question q
      join paper p on p.id=q.paper_id join document d on d.id=p.document_id where q.id=?""", (qid,)).fetchone()
    print(qid, r["paper_code"], row)

# 2. duplicates: batch-001 vs all other batches
print("\n=== duplicate stems (batch-001 vs other batches) ===")
other = {}
import glob
for f in sorted(glob.glob(f"{BASE}/batches/batch-*.jsonl")) + [f"{BASE}/decisions/applied.jsonl"]:
    if "batch-001" in f:
        continue
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        qid = r.get("question_id")
        stem = r.get("stem")
        if stem is None:
            row = cur.execute("select stem_text from question where id=?", (qid,)).fetchone()
            stem = row[0] if row else ""
        other.setdefault(norm(stem), []).append((qid, f.split("/")[-1], r.get("decision")))

b1stems = {}
for r in b1:
    b1stems.setdefault(norm(r["stem"]), []).append(r["question_id"])
for s, qids in b1stems.items():
    if s in other and len(s) > 20:
        print("batch001:", qids, "|| other:", other[s], "|| stem:", s[:90])

# 3. the 4 suspects
print("\n=== 64522/64525/64531/64532 info ===")
for qid in (64522, 64525, 64531, 64532):
    row = cur.execute("""select p.id, p.paper_no, d.title, q.number_label, substr(q.stem_text,1,90) from question q
      join paper p on p.id=q.paper_id join document d on d.id=p.document_id where q.id=?""", (qid,)).fetchone()
    print(qid, row)
    for l in open(f"{BASE}/decisions/applied.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r.get("question_id") == qid:
            print("   applied:", json.dumps(r, ensure_ascii=False))

# 4. batch-001 current tags from DB (for decision reasons)
print("\n=== batch-001 current DB tags ===")
for r in b1:
    qid = r["question_id"]
    rows = cur.execute("""select tn.code, tn.name from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
      where qt.question_id=? order by tn.code""", (qid,)).fetchall()
    print(qid, "|".join(f"{c}" for c, n in rows))
