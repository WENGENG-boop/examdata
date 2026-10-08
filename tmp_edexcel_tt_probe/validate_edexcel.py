"""Edexcel 解析器全量验证：扫描 downloads/edexcel 下全部考季，逐季汇总并统计异常。"""

import json
import sys
from collections import Counter

sys.path.insert(0, "../examdata/src")
from examdata.timetable.edexcel_parser import iter_seasons, parse_pdf  # noqa: E402

BASE = "downloads/edexcel"

rows = []
note_samples = Counter()
uncl_samples = []
unparsed_seasons = []
zero_event_seasons = []
for path, family, year, month, r_paper in iter_seasons(BASE):
    name = f"{year:04d}-{month:02d}" + ("-r" if r_paper else "")
    result = parse_pdf(path, family, year, month, r_paper=r_paper)
    stats = result["stats"]
    events = len(result["events"])
    windows = len(result["date_windows"])
    unparsed = len(result["unparsed_rows"])
    rows.append(
        {
            "key": f"{family}/{name}",
            "events": events,
            "windows": windows,
            "unparsed": unparsed,
            "dup": stats["duplicates_removed"],
            "cond": stats["condensed_tables"],
            "uncl": stats["unclassified_tables"],
            "notes": stats["date_notes"],
            "kinds": {k: v for k, v in stats.items() if k.endswith("_tables") and isinstance(v, int) and v},
        }
    )
    for event in result["events"]:
        if "date_note" in event:
            note_samples[f"{family}/{name} :: {event['date_note'][:90]}"] += 1
    if stats["unclassified_samples"]:
        uncl_samples.append((f"{family}/{name}", stats["unclassified_samples"]))
    if unparsed:
        unparsed_seasons.append((f"{family}/{name}", result["unparsed_rows"][:3]))
    if events == 0:
        zero_event_seasons.append(f"{family}/{name}")

print("=" * 110)
print(f"共扫描 {len(rows)} 季")
print("=" * 110)
for row in rows:
    kinds = ", ".join(f"{k}={v}" for k, v in sorted(row["kinds"].items()))
    print(
        f"{row['key']:<22} events={row['events']:<4} windows={row['windows']:<3} "
        f"unparsed={row['unparsed']:<3} dup={row['dup']:<4} cond={row['cond']:<3} "
        f"uncl={row['uncl']:<3} notes={row['notes']:<3} | {kinds}"
    )

print("=" * 110)
total_events = sum(r["events"] for r in rows)
total_windows = sum(r["windows"] for r in rows)
total_unparsed = sum(r["unparsed"] for r in rows)
total_uncl = sum(r["uncl"] for r in rows)
print(f"合计: events={total_events} windows={total_windows} unparsed={total_unparsed} uncl={total_uncl}")
print(f"零事件季: {zero_event_seasons or '无'}")
print(f"有未解析行的季: {[s for s, _ in unparsed_seasons] or '无'}")

print("-" * 110)
print(f"date_note 种类（共 {len(note_samples)} 条唯一）:")
for text, count in note_samples.most_common(40):
    print(f"  [{count}] {text}")

print("-" * 110)
print(f"unclassified 季数: {len(uncl_samples)}")
for key, samples in uncl_samples:
    print(f"  {key}: {json.dumps(samples, ensure_ascii=False)[:500]}")

if unparsed_seasons:
    print("-" * 110)
    print("未解析行样例:")
    for key, samples in unparsed_seasons:
        print(f"  {key}: {json.dumps(samples, ensure_ascii=False)[:400]}")
