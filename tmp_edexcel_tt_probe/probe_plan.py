"""构建下载计划：对每个 (family, year, month, variant) 选最优 Wayback 快照。

输入：evidence/coverage_matrix.json + evidence/cdx_all_captures.json 等
输出：evidence/download_plan.json
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")
EV = OUT / "evidence"

MONTHS = {"jan": 1, "january": 1, "june": 6, "jun": 6, "summer": 6, "oct": 10,
          "october": 10, "nov": 11, "november": 11}


def load_rows():
    rows = []
    p = EV / "cdx_all_captures.json"
    if p.exists():
        for rec in json.loads(p.read_text(encoding="utf-8")):
            rows.append(rec)
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
        try:
            length = int(rec.get("length") or 0)
        except (TypeError, ValueError):
            length = 0
        st = str(rec.get("statuscode"))
        cur = best.get(url)
        key = (st == "200", length)
        if cur is None or key > cur["key"]:
            best[url] = {"url": url, "timestamp": rec["timestamp"], "status": st,
                         "length": length, "key": key}
    return list(best.values())


def variant_of(name):
    if re.search(r"(?:^|[-_ (])r(?:[-_ .)]|$)", name) or "r_paper" in name or "r-paper" in name:
        return "R"
    return "standard"


def classify(url):
    """返回 (family, year, month, variant) 或 None。"""
    name = url.rsplit("/", 1)[-1].lower()
    name = re.sub(r"\.(pdf|xlsx)$", "", name)
    name = name.replace("%20", " ")
    var = variant_of(name)

    fam = None
    if re.search(r"international-advanced-levels|(^|[-_ (])ial([-_ .)]|$)|int-a-level|int_a_level", name) or \
       "international-advanced-levels" in url.lower():
        fam = "ial"
    elif re.search(r"international-gcse|intgcse|int_gcse|igcse|int-gcse", name):
        fam = "intgcse"
    elif re.search(r"(^|[-_ (])gcse([-_ .)]|$)", name):
        fam = "gcse"
    elif re.search(r"(^|[-_ (])gce([-_ .)]|$)|a-level|a_level", name):
        fam = "gce"
    if fam is None:
        return None

    month = None
    year = None
    for word, m in MONTHS.items():
        if re.search(rf"(?:^|[-_ (]){word}(?:[-_ .)]|20\d\d|$)", name):
            month = m
            break
    m4 = re.search(r"(20\d{2})", name)
    if m4:
        year = int(m4.group(1))
    if year is None or month is None:
        # YYMM codes like 1901/1906/1910/1911/1810/2001/2006
        for m in re.finditer(r"(?:^|[-_ (])(\d{2})(0[16]|10|11)(?:[-_ .)]|$)", name):
            yy = int(m.group(1))
            if 15 <= yy <= 27:
                year = 2000 + yy
                if month is None:
                    month = int(m.group(2))
                break
    if month == 5:
        month = 6
    if year is None or month not in (1, 6, 10, 11):
        return None
    return fam, year, month, var


def score(rec, name):
    """候选打分：final > 非final；pdf > xlsx；200 > 其他。"""
    s = 0
    if rec["status"] == "200":
        s += 100
    if "final" in name:
        s += 10
    if name.endswith(".pdf"):
        s += 3
    if "provisional" in name or "prov" in name:
        s -= 5
    s += min(rec["length"], 10**7) / 10**7
    return s


def main():
    rows = load_rows()
    best = best_per_url(rows)
    groups = defaultdict(list)
    unclassified = []
    for rec in best:
        cls = classify(rec["url"])
        if cls is None:
            unclassified.append(rec)
            continue
        groups[cls].append(rec)

    plan = {}
    print("== plan ==")
    for key in sorted(groups):
        fam, year, month, var = key
        cands = groups[key]
        cands.sort(key=lambda r: -score(r, r["url"].rsplit("/", 1)[-1].lower()))
        chosen = cands[0]
        name = chosen["url"].rsplit("/", 1)[-1]
        plan[f"{fam}|{year}|{month:02d}|{var}"] = {
            "family": fam, "year": year, "month": month, "variant": var,
            "url": chosen["url"], "timestamp": chosen["timestamp"],
            "status": chosen["status"], "length": chosen["length"], "name": name,
            "n_candidates": len(cands),
        }
        print(f"{fam:8s} {year}-{month:02d} {var:8s} {chosen['status']} {chosen['length']:>9} {name[:66]}")

    print(f"\nclassified groups: {len(plan)}; unclassified urls: {len(unclassified)}")
    print("\n== unclassified that mention timetable-ish keywords ==")
    for rec in sorted(unclassified, key=lambda r: r["url"]):
        n = rec["url"].rsplit("/", 1)[-1].lower()
        if re.search(r"ial|gcse|gce|a-level|igcse", n):
            print(f"  {rec['status']} {rec['length']:>9} {n[:90]}")

    (EV / "download_plan.json").write_text(
        json.dumps({"plan": plan, "unclassified": [u["url"] for u in unclassified]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nsaved download_plan.json")


if __name__ == "__main__":
    sys.exit(main())
