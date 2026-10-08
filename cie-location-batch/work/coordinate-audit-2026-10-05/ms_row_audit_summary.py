"""Summarise deliverables/ms-row-audit.json into a defect table + dangling-region list.

Read-only. Reclassifies `region_without_row_*` findings by whether the region's own
text_inside carries substantive content, so header-band dangling regions are
separated from writing-paper level-descriptor tables (which legitimately have no
numbered rows).

Writes: deliverables/ms-row-audit-summary.json
"""
import json
import re
import collections
import os

A = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(A, "deliverables", "ms-row-audit.json")
OUT = os.path.join(A, "deliverables", "ms-row-audit-summary.json")

HEADERISH = re.compile(
    r"^(PUBLISHED|©|Page \d+ of \d+|\d{4}/\d+$|Cambridge International|"
    r"May/June \d{4}$|October/November \d{4}$|Question$|Answer$|Marks$|"
    r"Descriptor$|Guidance$|Task completion$|Range$|Accuracy$|Content$)")

# findings that always count as a real defect
HARD = {"row_without_region", "region_wrong_row", "region_multi_row",
        "row_covered_by_other_branch"}


def substantive(lines):
    return [t for t in lines if len(t) >= 30 and not HEADERISH.match(t)]


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    per_paper = {}
    totals = collections.Counter()
    dangling = []          # region covers no substantive text -> deletion candidate
    content_no_row = []    # region covers content but page/region has no numbered row
    unauditable = []       # page has no usable text layer -> needs visual check
    for key, v in sorted(d.items()):
        if v.get("skipped"):
            per_paper[key] = {"skipped": v["skipped"]}
            continue
        hard = collections.Counter()
        dan = []
        cnr = []
        una = []
        for f in v.get("findings") or []:
            t = f.get("type")
            if t in HARD:
                hard[t] += 1
                totals[t] += 1
            elif t == "region_unauditable_no_text":
                una.append(f)
            elif t.startswith("region_without_row"):
                # 审计脚本按区域自身条带内的实质正文行数分类；缺失时回退到 text_inside 抽样。
                n = f.get("substantive_inside")
                if n is None:
                    n = len(substantive(f.get("text_inside") or []))
                if n > 0:
                    cnr.append(f)
                else:
                    f = dict(f)
                    rows = (v.get("page_rows") or {}).get(str(f.get("page"))) or []
                    rb = f.get("bbox") or [0, 0, 0, 0]
                    below = sorted((lb[1], t) for t, lb in rows if lb[1] >= rb[3] - 1)
                    f["rows_below_band"] = [t for _, t in below[:3]]
                    f["next_row_below"] = below[0][1] if below else None
                    f["above_all_rows"] = all(lb[1] >= rb[3] - 1 for _, lb in rows)
                    dan.append(f)
        per_paper[key] = {
            "hard_defects": dict(hard),
            "hard_total": sum(hard.values()),
            "dangling_regions": len(dan),
            "content_regions_without_row": len(cnr),
            "unauditable_regions": len(una),
            "empty_ms": v.get("questions_with_empty_ms") or [],
            "pages_without_question_column": v.get("pages_without_question_column") or [],
            "pages_text_unauditable": v.get("pages_text_unauditable") or [],
            "dangling_detail": dan,
            "content_no_row_detail": cnr,
            "unauditable_detail": una,
        }
        dangling.extend((key, f) for f in dan)
        content_no_row.extend((key, f) for f in cnr)
        unauditable.extend((key, f) for f in una)
    totals["dangling_regions"] = len(dangling)
    totals["content_regions_without_row"] = len(content_no_row)
    totals["unauditable_regions"] = len(unauditable)
    summary = {
        "source": os.path.relpath(SRC, A).replace("\\", "/"),
        "papers": len(d),
        "auditable": sum(1 for v in d.values() if not v.get("skipped")),
        "skipped": [k for k, v in d.items() if v.get("skipped")],
        "totals": dict(totals),
        "per_paper": per_paper,
    }
    json.dump(summary, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("totals:", json.dumps(dict(totals), ensure_ascii=False))
    print()
    print("== per paper: hard / dangling / content-no-row / unauditable / emptyMS ==")
    rows = [(k, p) for k, p in per_paper.items() if "hard_defects" in p]
    rows.sort(key=lambda r: -(r[1]["hard_total"] + r[1]["dangling_regions"]))
    for k, p in rows:
        if (p["hard_total"] or p["dangling_regions"] or p["content_regions_without_row"]
                or p["unauditable_regions"]):
            print(f'{k:26s} hard={p["hard_total"]:3d} dangling={p["dangling_regions"]:3d} '
                  f'content_no_row={p["content_regions_without_row"]:3d} '
                  f'unauditable={p["unauditable_regions"]:3d} '
                  f'emptyMS={len(p["empty_ms"])} {p["hard_defects"]}')
    print()
    print("== unauditable pages per paper (no usable text layer) ==")
    for k, p in rows:
        if p["pages_text_unauditable"]:
            print(f'  {k:26s} pages={p["pages_text_unauditable"]}')
    print()
    print("== dangling regions (region covers no substantive text) ==")
    for k, f in dangling:
        flag = "BEFORE-FIRST-ROW" if f.get("above_all_rows") else "MID-PAGE"
        print(f'{k:26s} p{f.get("page"):>3} q={f.get("q"):12s} bbox={f.get("bbox")} '
              f'{flag:16s} next_row={f.get("next_row_below")} text={f.get("text_inside")}')
    print()
    print("== content-bearing regions with no numbered row (judge per paper) ==")
    byk = collections.Counter(k for k, _ in content_no_row)
    for k, n in byk.most_common():
        print(f"  {k:26s} {n}")
    print()
    print("written", OUT)


if __name__ == "__main__":
    main()
