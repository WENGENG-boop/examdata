"""验证 subject 视图是否为日期视图的重排副本（v2：clean 表头 + 细查差异）。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")

TARGETS = [
    "ial/2017-06.pdf",
    "gce/2020-10.pdf",
    "ial/2021-06.pdf",
    "intgcse/2021-06.pdf",
    "intgcse/2022-01.pdf",
    "gcse/2023-06.pdf",
    "gcse/2021-06.pdf",
    "ial/2019-06.pdf",
]


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


CODE_TOKEN = re.compile(r"\b([0-9][A-Z0-9]{2,5}|[A-Z][0-9A-Z]{3,5})\b")


def tokens_from_text(text):
    out = set()
    for m in CODE_TOKEN.finditer(text):
        tok = m.group(1)
        if re.fullmatch(r"(19|20)\d{2}", tok):
            continue
        out.add(tok)
    return out


def classify(hdr):
    h = [clean(c).lower() for c in hdr]
    while h and h[-1] == "":
        h.pop()
    if not h:
        return "noise"
    first = h[0]
    if first in ("subject", "a subject"):
        return "subject_view"
    if h[:2] == ["date", "examination code"]:
        return "date_view"
    if h[:2] == ["date", "morning"] or h[:2] == ["date", "morning session"]:
        return "old_grid"
    if first == "date" and "length" in h:
        return "window"
    if h[:2] == ["exam date", "exam series"] or h[:2] == ["date", "exam series"]:
        return "master"
    return "other:" + "|".join(h[:3])


for name in TARGETS:
    path = BASE / name
    doc = pymupdf.open(path)
    date_codes, subj_codes, win_codes = set(), set(), set()
    kinds = {}
    for pno in range(doc.page_count):
        page = doc[pno]
        if page.rotation:
            page.set_rotation(0)
        for t in page.find_tables().tables:
            rows = t.extract()
            if not rows:
                continue
            kind = classify(rows[0])
            kinds[kind] = kinds.get(kind, 0) + 1
            if kind == "date_view":
                for r in rows[1:]:
                    r = [clean(c) for c in r]
                    if len(r) > 1 and r[1]:
                        date_codes |= tokens_from_text(r[1])
            elif kind == "old_grid":
                for r in rows[1:]:
                    for idx in (1, 3):
                        if len(r) > idx and r[idx]:
                            date_codes |= tokens_from_text(r[idx])
            elif kind == "window":
                for r in rows[1:]:
                    for idx in (1,):
                        if len(r) > idx and r[idx]:
                            win_codes |= tokens_from_text(r[idx])
            elif kind == "subject_view":
                for r in rows[1:]:
                    cells = [clean(c) for c in r]
                    if not any(cells):
                        continue
                    for c in cells:
                        if re.fullmatch(r"[0-9A-Z]{4,6}(\s+[0-9][0-9A-Z]{0,2}(?:-[0-9A-Za-z]{1,3})?)?", c):
                            subj_codes |= tokens_from_text(c)
                            break
    doc.close()
    only_subj = sorted(subj_codes - date_codes - win_codes)
    only_date = sorted(date_codes - subj_codes)
    print("#", name, dict(sorted(kinds.items())))
    print(f"   date={len(date_codes)} subj={len(subj_codes)} win={len(win_codes)}")
    print(f"   subj-extra(not in date|win)={len(only_subj)} {only_subj[:20]}")
    print(f"   date-only(not in subj)={len(only_date)} {only_date[:20]}")
