"""Verify production parser handles legacy (2013-2014) and modern gap seasons."""

import sys
from pathlib import Path

sys.path.insert(0, "examdata/src")
import pymupdf  # noqa: E402

from examdata.timetable.parser import parse_pdf, _is_legacy_document  # noqa: E402

GAP = Path("tmp_materials_probe/downloads/zone5_gap7")
FIN = Path("tmp_materials_probe/downloads/zone5_final")

print("== legacy seasons ==")
for name, year, series in [
    ("2013-11", 2013, "Nov"),
    ("2014-06", 2014, "Jun"),
    ("2014-11", 2014, "Nov"),
]:
    res = parse_pdf(GAP / f"{name}.pdf", year, series)
    dates = sorted({e["date"] for e in res["events"]})
    stats = res["stats"]
    print(
        f"{name}: events={len(res['events'])} unparsed={len(res['unparsed_rows'])} "
        f"dup={stats['duplicates_removed']} weekly_pages={stats['weekly_pages']} "
        f"legacy={stats.get('legacy_layout')} dates={dates[0]}..{dates[-1]} "
        f"windows={len(res['date_windows'])}"
    )
    for u in res["unparsed_rows"][:5]:
        print("   unparsed:", u)

print("== gap modern seasons ==")
for name, year, series in [
    ("2015-06", 2015, "Jun"),
    ("2015-11", 2015, "Nov"),
    ("2016-06", 2016, "Jun"),
    ("2016-11", 2016, "Nov"),
]:
    res = parse_pdf(GAP / f"{name}.pdf", year, series)
    stats = res["stats"]
    print(
        f"{name}: events={len(res['events'])} unparsed={len(res['unparsed_rows'])} "
        f"dup={stats['duplicates_removed']} weekly={stats['weekly_pages']} "
        f"windows={len(res['date_windows'])} legacy={stats.get('legacy_layout')}"
    )

print("== modern archive: any legacy-routed? ==")
routed = []
for p in sorted(FIN.glob("*.pdf")):
    doc = pymupdf.open(p)
    if _is_legacy_document(doc):
        routed.append(p.name)
    doc.close()
print("legacy-routed in zone5_final:", routed or "none")
print("done")
