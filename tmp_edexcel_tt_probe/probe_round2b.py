import sys
from collections import Counter
sys.path.insert(0, "../examdata/src")
from examdata.timetable.edexcel_parser import parse_pdf

for fam, y, m in [("ial", 2017, 10), ("gce", 2021, 11), ("intgcse", 2025, 11), ("gcse", 2020, 11)]:
    r = parse_pdf(f"downloads/edexcel/{fam}/{y:04d}-{m:02d}.pdf", fam, y, m)
    months = Counter(e["date"][:7] for e in r["events"])
    print(fam, y, m, "events", len(r["events"]), "| by month:", dict(sorted(months.items())))
    for e in r["events"][:2]:
        print("   ", e["date"], e["subject_code"], e["paper_code"], (e.get("date_note") or "")[:70])
