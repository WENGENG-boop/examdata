"""Parse EOL gaokao 真题 pages (2023-2026) into a clean CSV.

Output: logs/eol-article-index2.csv
Columns: year,section_id,section_name,regions,subject,kind,url
Where kind in {qp,ans,expl}; url empty means the page shows no link (grey text).
"""
import csv
import html as htmllib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs" / "eol"

PAGES = {
    2023: LOGS / "2023st.html",
    2024: LOGS / "2024st.html",
    2025: LOGS / "2025st.html",
    2026: LOGS / "2026st.html",
}


def text(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return htmllib.unescape(s).strip()


def parse(path: Path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r'(?=<div class="test")', raw)
    for b in blocks:
        sm = re.match(r'<div class="test"\s+id="(st\d+)"', b)
        if not sm:
            continue
        sid = sm.group(1)
        nm = re.search(r'<div class="head-fl clearfix">\s*<span>(.*?)</span>', b, re.S)
        name = text(nm.group(1)) if nm else ""
        rm = re.search(r'<div class="head-mid">\s*(.*?)</div>', b, re.S)
        regions = text(rm.group(1)) if rm else ""
        # subject items
        for item in re.findall(r'<div class="word-xueke">(.*?)</li>', b, re.S):
            tm = re.match(r'(.*?)</span>', item, re.S)
            subj = text(tm.group(1)) if tm else ""
            if not subj:
                continue
            kinds = re.findall(r'<a href="([^"]*)"><font color="[^"]*">(真题|答案|解析)</font></a>', item)
            urls = {}
            for href, kind in kinds:
                urls[kind] = href
            for kind, key in (("真题", "qp"), ("答案", "ans"), ("解析", "expl")):
                yield {
                    "year": "",
                    "section_id": sid,
                    "section_name": name,
                    "regions": regions,
                    "subject": subj,
                    "kind": key,
                    "url": urls.get(kind, ""),
                }


def main():
    out = ROOT / "logs" / "eol-article-index2.csv"
    rows = []
    for year, path in PAGES.items():
        if not path.exists():
            print(f"missing {path}", file=sys.stderr)
            continue
        for r in parse(path):
            r["year"] = year
            rows.append(r)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["year", "section_id", "section_name", "regions", "subject", "kind", "url"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} rows={len(rows)}")
    # quick stats
    by_year = {}
    for r in rows:
        by_year.setdefault(r["year"], [0, 0])
        by_year[r["year"]][0] += 1
        if r["url"]:
            by_year[r["year"]][1] += 1
    for y, (tot, linked) in sorted(by_year.items()):
        print(f"  {y}: cells={tot} linked={linked}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
