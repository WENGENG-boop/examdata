"""Edexcel 解析器冒烟测试：对已知样例季逐季核对事件/窗口/未解析数量。"""

import json
import sys

sys.path.insert(0, "../examdata/src")
from examdata.timetable.edexcel_parser import parse_pdf  # noqa: E402

BASE = "downloads/edexcel"

# (family, year, month, r_paper, 期望事件数或 None)
TARGETS = [
    ("intgcse", 2022, 1, False, 24),
    ("ial", 2020, 1, False, 63),
    ("intgcse", 2020, 1, False, 35),
    ("intgcse", 2020, 6, True, 47),
    ("intgcse", 2020, 1, True, 26),
    ("gce", 2015, 6, False, None),
    ("gce", 2016, 6, False, None),
    ("gce", 2017, 6, False, None),
    ("gce", 2018, 6, False, None),
    ("ial", 2018, 1, False, None),
    ("intgcse", 2017, 6, False, None),
    ("ial", 2021, 6, False, None),
    ("intgcse", 2021, 6, False, None),
    ("intgcse", 2021, 11, False, None),
]

results = {}
print("=" * 100)
for family, year, month, r_paper, expected in TARGETS:
    name = f"{year:04d}-{month:02d}" + ("-r" if r_paper else "")
    path = f"{BASE}/{family}/{name}.pdf"
    result = parse_pdf(path, family, year, month, r_paper=r_paper)
    results[f"{family}/{name}"] = result
    stats = result["stats"]
    event_count = len(result["events"])
    window_count = len(result["date_windows"])
    unparsed_count = len(result["unparsed_rows"])
    if expected is None:
        flag = ""
    elif event_count == expected:
        flag = "OK"
    else:
        flag = f"!! expected {expected}"
    print(
        f"{family}/{name}: events={event_count} windows={window_count} unparsed={unparsed_count} "
        f"dup={stats['duplicates_removed']} cond={stats['condensed_tables']} "
        f"uncl={stats['unclassified_tables']} notes={stats['date_notes']} {flag}"
    )
    kinds = [
        (key, stats[key])
        for key in (
            "modern_tables",
            "modern_notime_tables",
            "old_grid_tables",
            "window_tables",
            "master_tables",
            "rotated_tables",
            "index_tables",
            "noise_tables",
        )
        if stats[key]
    ]
    print("    tables:", ", ".join(f"{k}={v}" for k, v in kinds))
    if stats["unclassified_samples"]:
        print("    unclassified:", json.dumps(stats["unclassified_samples"], ensure_ascii=False)[:400])
    for item in result["unparsed_rows"][:4]:
        print("    unparsed:", json.dumps(item, ensure_ascii=False)[:260])

print("=" * 100)
print("### intgcse/2022-01 前 3 个事件")
for event in results["intgcse/2022-01"]["events"][:3]:
    print(json.dumps(event, ensure_ascii=False))
print("### intgcse/2022-01 事件总数", len(results["intgcse/2022-01"]["events"]))

print("### gce/2018-06 全部窗口")
for window in results["gce/2018-06"]["date_windows"]:
    print(json.dumps(window, ensure_ascii=False))
print("### gce/2015-06 全部窗口")
for window in results["gce/2015-06"]["date_windows"]:
    print(json.dumps(window, ensure_ascii=False))
print("### ial/2018-01 全部窗口")
for window in results["ial/2018-01"]["date_windows"]:
    print(json.dumps(window, ensure_ascii=False))

print("### intgcse/2021-11 前 3 个事件")
for event in results["intgcse/2021-11"]["events"][:3]:
    print(json.dumps(event, ensure_ascii=False))
print("### ial/2021-06 前 3 个事件")
for event in results["ial/2021-06"]["events"][:3]:
    print(json.dumps(event, ensure_ascii=False))
print("### intgcse/2021-06 前 3 个事件（notime）")
for event in results["intgcse/2021-06"]["events"][:3]:
    print(json.dumps(event, ensure_ascii=False))
print("### ial/2020-01 前 3 个事件")
for event in results["ial/2020-01"]["events"][:3]:
    print(json.dumps(event, ensure_ascii=False))
print("### intgcse/2020-01-r 前 3 个事件")
for event in results["intgcse/2020-01-r"]["events"][:3]:
    print(json.dumps(event, ensure_ascii=False))
print("### intgcse/2020-06-r 前 3 个事件")
for event in results["intgcse/2020-06-r"]["events"][:3]:
    print(json.dumps(event, ensure_ascii=False))
