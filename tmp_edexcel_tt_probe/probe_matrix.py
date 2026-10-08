"""把 4 个文件夹的 CDX 快照归类成 (family, series, year) 覆盖矩阵。

输出：evidence/coverage_matrix.json + 控制台表格。
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")
EV = OUT / "evidence"


def load_rows():
    rows = []
    # IAL: list of dicts
    p = EV / "cdx_all_captures.json"
    if p.exists():
        for rec in json.loads(p.read_text(encoding="utf-8")):
            rows.append(rec)
    # others: raw arrays with header
    for name in ("cdx_Examination_timetables_for_Edexcel_International_GCSE.json",
                 "cdx_Examination_timetables_for_UK_Edexcel_GCSE.json",
                 "cdx_Examination_timetables.json"):
        p = EV / name
        if not p.exists():
            continue
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not raw:
            continue
        header = raw[0]
        for row in raw[1:]:
            rows.append(dict(zip(header, row)))
    return rows


def best_per_url(rows):
    best = {}
    for rec in rows:
        url = rec["original"]
        ts = rec["timestamp"]
        try:
            length = int(rec.get("length") or 0)
        except (TypeError, ValueError):
            length = 0
        st = str(rec.get("statuscode"))
        cur = best.get(url)
        key = (st == "200", length)
        if cur is None or key > cur["key"]:
            best[url] = {"url": url, "timestamp": ts, "status": st, "length": length, "key": key}
    return list(best.values())


MONTHS = {
    "jan": 1, "january": 1, "june": 6, "jun": 6, "summer": 6, "may": 6,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
}
YYMM_RE = re.compile(r"(?:^|[-_ (])(\d{2})(0[16]|10|11)(?:[-_ .)]|$)")


def classify(url):
    """返回 (family, series_month, year) 或 None。"""
    name = url.rsplit("/", 1)[-1].lower()
    name = re.sub(r"\.(pdf|xlsx)$", "", name)
    name = re.sub(r"%20", " ", name)

    fam = None
    if "international-advanced-levels" in url.lower() or "ial" in name or "int-a-level" in name or "int_a_level" in name:
        fam = "ial"
    elif "international-gcse" in url.lower() or "intgcse" in name or "int_gcse" in name or "igcse" in name or "int-gcse" in name:
        fam = "intgcse"
    elif "uk-edexcel-gcse" in url.lower() or re.search(r"(^|[-_])gcse([-_]|$)", name):
        fam = "gcse"
    elif re.search(r"(^|[-_])gce([-_]|$)", name) or "a-level" in name or "a_level" in name:
        fam = "gce"
    if fam is None:
        return None

    month = None
    year = None

    # explicit month words
    for word, m in MONTHS.items():
        if re.search(rf"(?:^|[-_ (]){word}(?:[-_ .)]|$)", name):
            month = m
            break
    # explicit 4-digit year
    m4 = re.search(r"(20\d{2})", name)
    if m4:
        year = int(m4.group(1))
    # yymm code
    if year is None:
        m = YYMM_RE.search(name)
        if m:
            yy, mm = int(m.group(1)), int(m.group(2))
            year = 2000 + yy
            if month is None and mm in (1, 6, 10, 11):
                month = mm
    if month is None or year is None:
        return None
    if month == 5:
        month = 6
    if month not in (1, 6, 10, 11):
        return None
    return fam, month, year


def main():
    rows = load_rows()
    print("total capture rows:", len(rows))
    best = best_per_url(rows)
    print("unique urls:", len(best))

    matrix = defaultdict(list)
    unclassified = []
    for rec in best:
        cls = classify(rec["url"])
        if cls is None:
            unclassified.append(rec)
            continue
        fam, month, year = cls
        matrix[(fam, year, month)].append(rec)

    print("\n== coverage (family, year, month) -> best candidate ==")
    for key in sorted(matrix):
        fam, year, month = key
        cands = sorted(matrix[key], key=lambda r: (-r["key"][1]))
        print(f"{fam:8s} {year} {month:02d}  n={len(cands)}")
        for c in cands[:3]:
            print(f"    {c['status']} {c['length']:>9} {c['timestamp']} {c['url'].rsplit('/',1)[-1][:70]}")

    print("\n== unclassified (first 60) ==")
    for rec in sorted(unclassified, key=lambda r: r["url"])[:60]:
        print(f"  {rec['status']} {rec['url'].rsplit('/',1)[-1][:90]}")

    out = {
        "matrix": {f"{f}|{y}|{m:02d}": v for (f, y, m), v in matrix.items()},
        "unclassified": unclassified,
    }
    (EV / "coverage_matrix.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nsaved coverage_matrix.json")


if __name__ == "__main__":
    sys.exit(main())
