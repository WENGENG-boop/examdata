"""List remaining review batches (from reconciliation missing list minus done-since)."""
from collections import defaultdict
from pathlib import Path

ROOT = Path(".data/tagging/review-export")
missing = [l.strip() for l in open("tmp_review_missing_items.txt", encoding="utf-8") if l.strip()]

done_since = {
    "ial-psychology/batch-001", "ial-psychology/batch-004", "ial-psychology/batch-007",
    "ial18-business/batch-001", "ial18-business/batch-002", "ial18-business/batch-003",
    "ial18-business/batch-005", "ial18-business/batch-006", "ial18-business/batch-007",
}
remaining = [m for m in missing if m not in done_since]

by_subj = defaultdict(list)
for m in remaining:
    slug, b = m.split("/")
    by_subj[slug].append(b)

tot_b = tot_r = 0
for slug in sorted(by_subj):
    n = 0
    for b in sorted(by_subj[slug]):
        f = ROOT / slug / "batches" / f"{b}.jsonl"
        if not f.exists():
            print("  MISSING FILE:", f)
            continue
        n += sum(1 for l in open(f, encoding="utf-8") if l.strip())
    tot_b += len(by_subj[slug])
    tot_r += n
    print(f"{slug:<22} batches={len(by_subj[slug]):>3}  rows={n:>5}  {','.join(sorted(by_subj[slug]))}")
print(f"TOTAL batches={tot_b} rows={tot_r}")

# also verify no extra batches beyond reconciliation (compare dirs vs items)
print("\n-- batches present in dirs but not in reconciliation items --")
items = set()
for l in open("tmp_review_items.txt", encoding="utf-8"):
    items.add(l.strip())
for d in sorted(ROOT.iterdir()):
    bd = d / "batches"
    if not bd.is_dir():
        continue
    for f in sorted(bd.glob("batch-*.jsonl")):
        key = f"{d.name}/{f.stem}"
        if key not in items:
            print("  EXTRA:", key)
