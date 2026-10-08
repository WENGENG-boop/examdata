"""Parse EOL (gaokao.eol.cn) year pages into a province x subject article index."""

import csv
import pathlib
import re

BASE = pathlib.Path(__file__).resolve().parent.parent
YEARS = ("2023", "2024", "2025", "2026")
OUT = BASE / "logs" / "eol-article-index.csv"


def parse_year(year: str):
    path = BASE / "logs" / "eol" / f"{year}st.html"
    if not path.exists():
        return []
    html = path.read_text(encoding="utf-8", errors="ignore")
    names = dict(re.findall(r'<a href="#(st\d+)"[^>]*>([^<]+)</a>', html))
    rows = []
    # split into sections by id="stN"
    parts = re.split(r'<div class="test" id="(st\d+)">', html)
    # parts[0] is preamble; then pairs (id, body)
    for i in range(1, len(parts) - 1, 2):
        sec_id, body = parts[i], parts[i + 1]
        section = names.get(sec_id, sec_id)
        # subject blocks
        for blk in re.split(r'<div class="word-xueke">', body)[1:]:
            m_subj = re.match(r'\s*([^<]+?)\s*<', blk)
            subject = m_subj.group(1).strip() if m_subj else "?"
            links = re.findall(r'<a href="([^"]*)"[^>]*><font[^>]*>([^<]+)</font></a>', blk)
            qp = next((u for u, t in links if t in ("试题", "真题") and u), "")
            ans = next((u for u, t in links if t == "答案" and u), "")
            expl = next((u for u, t in links if t == "解析" and u), "")
            rows.append(
                {
                    "year": year,
                    "section": section,
                    "subject": subject,
                    "qp_url": qp,
                    "ans_url": ans,
                    "expl_url": expl,
                }
            )
        if sec_id and not body:
            break
    return rows


def main() -> None:
    rows = []
    for y in YEARS:
        rows.extend(parse_year(y))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["year", "section", "subject", "qp_url", "ans_url", "expl_url"]
        )
        writer.writeheader()
        writer.writerows(rows)
    for y in YEARS:
        yr = [r for r in rows if r["year"] == y]
        with_qp = [r for r in yr if r["qp_url"]]
        sections = sorted(set(r["section"] for r in yr))
        print(f"{y}: {len(yr)} subject entries, {len(with_qp)} with qp link, "
              f"sections({len(sections)})={sections}")
    print("->", OUT)


if __name__ == "__main__":
    main()
