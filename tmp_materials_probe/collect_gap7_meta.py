"""Collect matrix metadata for the 7 gap PDFs: pages, series label, sha256."""

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "examdata/src")
import pymupdf  # noqa: E402

from examdata.timetable.parser import parse_pdf  # noqa: E402

GAP = Path("tmp_materials_probe/downloads/zone5_gap7")
EV = Path("tmp_materials_probe/evidence/gap7_downloads.json")
downloads = json.loads(EV.read_text(encoding="utf-8"))["downloads"]

rows = {}
for name, year, series in [
    ("2013-11", 2013, "Nov"),
    ("2014-06", 2014, "Jun"),
    ("2014-11", 2014, "Nov"),
    ("2015-06", 2015, "Jun"),
    ("2015-11", 2015, "Nov"),
    ("2016-06", 2016, "Jun"),
    ("2016-11", 2016, "Nov"),
]:
    path = GAP / f"{name}.pdf"
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    doc = pymupdf.open(path)
    pages = doc.page_count
    head = "\n".join(doc[i].get_text() for i in range(min(3, pages)))
    doc.close()
    match = re.search(
        r"(?:Final Exam(?:ination)? Timetable|Exam(?:ination)? Timetable),?\s+"
        r"((?:June|November|March|May|October)\s+20\d\d)",
        head,
        re.IGNORECASE,
    )
    if not match:
        match = re.search(r"\b((?:June|November|March|May|October)\s+20\d\d)\b", head)
    detected = match.group(1).title() if match else None
    expected = {"Jun": "June", "Nov": "November"}[series] + f" {year}"
    res = parse_pdf(path, year, series)
    ev = downloads[name]
    rows[name] = {
        "pages": pages,
        "bytes": len(raw),
        "sha256": sha,
        "sha_matches_evidence": sha == ev["sha256"],
        "bytes_matches_evidence": len(raw) == ev["bytes"],
        "series_detected": detected,
        "series_expected": expected,
        "match": detected == expected,
        "events": len(res["events"]),
        "windows": len(res["date_windows"]),
        "unparsed": len(res["unparsed_rows"]),
        "legacy": res["stats"].get("legacy_layout", False),
    }

print(json.dumps(rows, indent=2, ensure_ascii=False))
