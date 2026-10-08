"""Legacy (2013-2014) zone5 weekly-page extraction probe.

Validates the geometry-based approach and votes symbol->level mapping
against the code->level reference built from modern seasons.

Usage:
  python legacy_probe.py            # full extraction + vote
  python legacy_probe.py dump FILE PAGE0   # dump all spans of a page (0-indexed)
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import fitz

sys.path.insert(0, "examdata/src")
from examdata.timetable.parser import parse_pdf  # noqa: E402

FULL_WEEKDAYS = {
    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
    "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
}
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
MONTHS_ABBR = {name[:3]: num for name, num in MONTHS.items()}

SYMBOL_RE = re.compile(r"^[\u2666\u25A0\u25CF\u25B2\u25CB\u25A1+\uF000-\uF8FF]+$")
CODE_SEARCH_RE = re.compile(r"\b(\d{4})\s*/\s*([0-9A-Za-z]{1,3})\b")
COMP_TAIL_RE = re.compile(r"^(?P<title>.+?)\s+(?P<comp>\d{1,3})(?P<tail>\s+\(.*\))?$")
TRAILING_NUMS_RE = re.compile(r"^(?P<title>.+?)(?P<nums>(?:\s+\d{1,3})+)(?P<tail>\s+\(.*\))?$")


def strip_comp_tail(title: str, paper: str) -> str | None:
    """Strip trailing component number token(s) when their digit multiset is a
    subset of the paper-number digits; return None when nothing should be stripped."""
    m = TRAILING_NUMS_RE.match(re.sub(r"\)(?=\d)", ") ", title))
    if not m:
        return None
    tail = collections.Counter(ch for ch in m.group("nums") if ch.isdigit())
    pdig = collections.Counter(ch for ch in paper if ch.isdigit())
    if not pdig or any(tail[ch] > pdig[ch] for ch in tail):
        return None
    return clean(m.group("title") + (m.group("tail") or ""))
WEEKDAY_RE = re.compile(
    r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"Tues|Thur|Thurs|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", re.I)
DATE_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)$")
LABEL_DATE_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3,})(?:\s+\d{4})?$")

EXCLUDE_TEXTS = {"Morning session", "Afternoon session", "Morning Session", "Afternoon Session",
                 "FINAL", "Code", "Duration", "Code Duration"}
PAGE_RANGE_RE = re.compile(r"^\d{1,2}\s*[–-]\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}")
LEGEND_TEXTS = {"IGCSE", "IGCSE (9-1)", "O Level", "AS Level", "A Level", "Principal Level",
                "GPR", "GPR Level 3 Cert", "Key:", "Key", "Cambridge IGCSE", "Cambridge O Level"}


def is_noise(text: str) -> bool:
    c = clean(text)
    if c in EXCLUDE_TEXTS or "FINAL" in c:
        return True
    if PAGE_RANGE_RE.match(c):
        return True
    if c in LEGEND_TEXTS:
        return True
    if c.startswith("Key:") or "GPR Level 3 Cert" in c:
        return True
    return False


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace("\uf020", " ")).strip()


def page_spans(page) -> list[tuple[float, float, float, str]]:
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                t = span["text"]
                if clean(t):
                    out.append((round(span["bbox"][1], 1), round(span["bbox"][0], 1), round(span["bbox"][2], 1), t))
    return out


def median(values: list[float]) -> float:
    values = sorted(values)
    return values[len(values) // 2]


def cluster_ys(ys: list[float], tol: float = 4.0) -> list[float]:
    out: list[float] = []
    for y in sorted(ys):
        if out and y - out[-1] <= tol:
            continue
        out.append(y)
    return out


def group_rows(hs: list[tuple[float, float, str]], tol: float = 6.0) -> list[tuple[float, list]]:
    """Cluster (y, x0, text) spans into visual rows by consecutive y gaps <= tol."""
    ys = sorted({y for (y, _, _) in hs})
    clusters: list[list[float]] = []
    cur: list[float] = []
    for y in ys:
        if cur and y - cur[-1] > tol:
            clusters.append(cur)
            cur = []
        cur.append(y)
    if cur:
        clusters.append(cur)
    rows = []
    for c in clusters:
        lo, hi = c[0], c[-1]
        group = sorted([(x0, t) for (y, x0, t) in hs if lo <= y <= hi], key=lambda s: s[0])
        rows.append((lo, hi, group))
    return rows


def parse_label(text: str):
    """Return (weekday|None, day|None, month|None) for a margin label, else None."""
    c = clean(text)
    wd = None
    rest = c
    m = WEEKDAY_RE.match(c)
    if m:
        tok = m.group(1).lower()
        wd = FULL_WEEKDAYS.get(tok[:3])
        rest = c[m.end():].strip()
    day = month = None
    m2 = LABEL_DATE_RE.match(rest)
    if m2:
        mon = MONTHS.get(m2.group(2).lower()) or MONTHS_ABBR.get(m2.group(2).lower()[:3])
        if mon is not None:
            day, month = int(m2.group(1)), mon
    if wd is None and day is None:
        return None
    return (wd, day, month)


def detect_columns(spans, band_ys):
    """Per-page column x positions from the per-day-band header rows."""
    name_L_s, name_R_s = [], []
    code_L_s, code_R_s = [], []
    dur_L_s, dur_R_s = [], []
    for by in band_ys:
        g = sorted([(x0, x1, t) for (y, x0, x1, t) in spans if abs(y - by) <= 4], key=lambda s: s[0])
        syl = [s for s in g if "Syllabus" in s[2]]
        if len(syl) < 2:
            continue
        name_L_s.append(syl[0][0])
        name_R_s.append(syl[1][0])
        split = syl[1][0]
        for (x0, x1, t) in g:
            c = clean(t)
            if "Syllabus" in c:
                continue
            if "Code" in c:
                (code_L_s if x0 < split else code_R_s).append(x0)
            if "Duration" in c and "Code" not in c:
                (dur_L_s if x0 < split else dur_R_s).append(x0)
    if not name_L_s or not name_R_s:
        return None
    name_L = median(name_L_s)
    name_R = median(name_R_s)
    code_L = median(code_L_s) if code_L_s else None
    code_R = median(code_R_s) if code_R_s else None
    dur_L = median(dur_L_s) if dur_L_s else None
    dur_R = median(dur_R_s) if dur_R_s else None
    if code_L is None and code_R is not None:
        code_L = name_L + (code_R - name_R)
    if code_R is None and code_L is not None:
        code_R = name_R + (code_L - name_L)
    if dur_L is None and dur_R is not None and code_L is not None and code_R is not None:
        dur_L = code_L + (dur_R - code_R)
    if dur_R is None and dur_L is not None and code_L is not None and code_R is not None:
        dur_R = code_R + (dur_L - code_L)
    missing = [n for n, v in (("name_L", name_L), ("name_R", name_R), ("code_L", code_L),
                              ("code_R", code_R), ("dur_L", dur_L), ("dur_R", dur_R)) if v is None]
    if missing:
        return {"error": f"missing columns {missing}"}
    return {"cols_L": (name_L, code_L, dur_L), "cols_R": (name_R, code_R, dur_R),
            "band_rows": len(name_L_s)}


def extract_legacy_page(page, debug=False):
    spans = page_spans(page)
    band_spans = [(y, x0, x1, t) for (y, x0, x1, t) in spans if "Syllabus" in t and "Component" in t]
    if not band_spans:
        return None
    band_ys = cluster_ys([y for y, _, _, _ in band_spans])
    colres = detect_columns(spans, band_ys)
    if colres is None or "error" in colres:
        return {"error": (colres or {}).get("error", "no columns"), "band_ys": band_ys}
    cols_L, cols_R = colres["cols_L"], colres["cols_R"]

    def half_of(x0: float) -> str:
        d_l = min(abs(x0 - c) for c in cols_L)
        d_r = min(abs(x0 - c) for c in cols_R)
        return "L" if d_l <= d_r else "R"

    margin, rows, skipped = [], [], []
    for y, x0, x1, t in spans:
        c = clean(t)
        if "Syllabus" in c and "Component" in c:
            continue
        if is_noise(c):
            continue
        if x0 < cols_L[0] - 5:
            lab = parse_label(c)
            if lab is not None:
                margin.append((y, lab, c))
                continue
        if y < band_ys[0] - 5:
            skipped.append((y, c))
            continue
        rows.append((y, half_of(x0), x0, c))

    # cluster rows per half by y
    per_half_rows: dict[str, list] = {"L": [], "R": []}
    row_spread = 0.0
    for half in ("L", "R"):
        hs = [(y, x0, c) for (y, h, x0, c) in rows if h == half]
        for (lo, hi, group) in group_rows(hs, tol=6.0):
            row_spread = max(row_spread, hi - lo)
            per_half_rows[half].append((lo, group))

    # day labels per band block
    label_by_block: dict[int, tuple] = {}
    label_deltas = []
    for (y, lab, c) in sorted(margin):
        idx = None
        for i, by in enumerate(band_ys):
            if y >= by - 12:
                idx = i
        if idx is None:
            continue
        label_deltas.append((c, round(band_ys[idx] - y, 1)))
        prev = label_by_block.get(idx)
        wd, day, month = lab
        wd = wd or (prev[0] if prev else None)
        day = day if day is not None else (prev[1] if prev else None)
        month = month if month is not None else (prev[2] if prev else None)
        label_by_block[idx] = (wd, day, month)

    def block_of(y: float):
        idx = None
        for i, by in enumerate(band_ys):
            if y >= by - 6:
                idx = i
        return idx

    events, unparsed, multisym = [], [], []
    for half in ("L", "R"):
        pending = None
        carry = None  # no-code row that may forward-merge into the next code row
        for (ry, group) in per_half_rows[half]:
            symbols, rest = [], []
            for (x0, c) in group:
                if not rest and SYMBOL_RE.match(c):
                    symbols.append(c)
                else:
                    rest.append(c)
            text = clean(" ".join(rest))
            if not text and not symbols:
                continue
            m = CODE_SEARCH_RE.search(text) if text else None
            if m is None:
                if text and not symbols and pending is not None and ry - pending["last_y"] <= 24:
                    pending["name_parts"].append(text)
                    pending["last_y"] = ry
                    continue
                if carry is not None and carry["text"]:
                    unparsed.append(carry["entry"])
                carry = {"y": ry, "text": text, "symbols": symbols,
                         "entry": {"row": text, "reason": "无代码", "half": half, "y": ry,
                                   "symbols": symbols}}
                continue
            name_raw = clean(text[: m.start()])
            dur_raw = clean(text[m.end():])
            if carry is not None and not symbols and ry - carry["y"] <= 24:
                name_parts = ([carry["text"]] if carry["text"] else []) + [name_raw]
                symbols = carry["symbols"]
                carry = None
            else:
                if carry is not None and carry["text"]:
                    unparsed.append(carry["entry"])
                carry = None
                name_parts = [name_raw]
            if len(symbols) > 1:
                multisym.append({"row": text, "symbols": symbols})
            pending = {"name_parts": name_parts, "code": m.group(0), "dur": dur_raw,
                       "symbol": symbols[0] if symbols else None, "symbols": symbols,
                       "label": label_by_block.get(block_of(ry)), "half": half,
                       "y": ry, "last_y": ry, "text": text,
                       "span_detail": [(round(x0, 1), c) for (x0, c) in group]}
            events.append(pending)
        if carry is not None and carry["text"]:
            unparsed.append(carry["entry"])
        carry = None

    return {"events": events, "unparsed": unparsed, "band_ys": band_ys,
            "cols_L": cols_L, "cols_R": cols_R, "label_by_block": label_by_block,
            "margin": margin, "skipped": skipped, "multisym": multisym,
            "row_spread": round(row_spread, 1), "label_deltas": label_deltas,
            "band_rows": colres["band_rows"]}


def build_reference():
    ref: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    base = Path("examdata/src/examdata/timetable/data/zone5")
    for p in sorted(base.glob("*.json")):
        if p.name == "index.json":
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for e in data["events"]:
            ref[e["subject_code"]][e["level"]] += 1
    for name, year, series in [("2015-06", 2015, "Jun"), ("2015-11", 2015, "Nov"),
                               ("2016-06", 2016, "Jun"), ("2016-11", 2016, "Nov")]:
        res = parse_pdf(f"tmp_materials_probe/downloads/zone5_gap7/{name}.pdf", year, series)
        for e in res["events"]:
            ref[e["subject_code"]][e["level"]] += 1
    return ({code: counter.most_common(1)[0][0] for code, counter in ref.items()},
            {code: dict(counter) for code, counter in ref.items()})


def main():
    args = sys.argv[1:]
    if args and args[0] == "dump":
        fname, pageno = args[1], int(args[2])
        doc = fitz.open(f"tmp_materials_probe/downloads/zone5_gap7/{fname}.pdf")
        print(f"== {fname} page {pageno} (0-idx) of {len(doc)} pages")
        for (y, x0, x1, t) in sorted(page_spans(doc[pageno])):
            print(f"y={y:8.1f} x0={x0:8.1f} x1={x1:8.1f}  {t!r}")
        return

    ref, ref_full = build_reference()
    print("reference codes:", len(ref))
    for fname in ("2013-11", "2014-06", "2014-11"):
        doc = fitz.open(f"tmp_materials_probe/downloads/zone5_gap7/{fname}.pdf")
        all_events, all_unparsed, all_skipped = [], [], []
        pages = 0
        for page in doc:
            text = page.get_text()
            if not (("Morning session" in text or "Morning Session" in text)
                    and ("Syllabus/Component" in text or "Syllabus / Component" in text)):
                continue
            pages += 1
            res = extract_legacy_page(page)
            if res is None or "error" in res:
                print(fname, "page", page.number + 1, "ERROR", res)
                continue
            for ev in res["events"]:
                ev["page"] = page.number + 1
            for u in res["unparsed"]:
                u["page"] = page.number + 1
            all_events.extend(res["events"])
            all_unparsed.extend(res["unparsed"])
            all_skipped.extend(res["skipped"])
            missing_labels = [i for i in range(len(res["band_ys"])) if i not in res["label_by_block"]]
            print(f"  [{fname} p{page.number + 1}] events={len(res['events'])} unparsed={len(res['unparsed'])} "
                  f"colsL=({res['cols_L'][0]:.0f},{res['cols_L'][1]:.0f},{res['cols_L'][2]:.0f}) "
                  f"colsR=({res['cols_R'][0]:.0f},{res['cols_R'][1]:.0f},{res['cols_R'][2]:.0f}) "
                  f"bands={len(res['band_ys'])} labels={len(res['label_by_block'])} "
                  f"missLabels={missing_labels} spread={res['row_spread']} multisym={len(res['multisym'])}")
            if missing_labels:
                print("    labels:", res["label_by_block"], "deltas:", res["label_deltas"])
            if res["multisym"]:
                print("    multisym rows:", res["multisym"][:5])
            if res["skipped"]:
                print("    skipped-above-band:", res["skipped"][:8])
        vote: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        no_ref: collections.Counter = collections.Counter()
        comp_mismatch = []
        no_symbol = []
        for ev in all_events:
            code4 = ev["code"].split("/")[0]
            level = ref.get(code4)
            if level is None:
                no_ref[code4] += 1
            else:
                vote[ev["symbol"] or "(none)"][level] += 1
            if not ev["symbol"]:
                no_symbol.append((ev["page"], ev["y"], ev["half"], ev["text"], ev["span_detail"]))
            title = clean(" ".join(ev["name_parts"]))
            m = TRAILING_NUMS_RE.match(re.sub(r"\)(?=\d)", ") ", title))
            if m:
                paper = ev["code"].split("/")[1] if "/" in ev["code"] else ""
                if strip_comp_tail(title, paper) is None:
                    comp_mismatch.append((ev["page"], ev["y"], title, ev["code"],
                                          m.group("nums").strip(), ev["text"]))
        print(f"\n===== {fname}: legacy pages={pages} events={len(all_events)} unparsed={len(all_unparsed)} "
              f"no_ref={sum(no_ref.values())} no_symbol={len(no_symbol)}")
        for sym, counter in sorted(vote.items()):
            total = sum(counter.values())
            print(f"  symbol {sym!r}: total={total} {dict(counter)}")
        for sym, counter in vote.items():
            if len(counter) > 1:
                detail = collections.defaultdict(collections.Counter)
                for ev in all_events:
                    if (ev["symbol"] or "(none)") == sym:
                        c4 = ev["code"].split("/")[0]
                        detail[c4][ref.get(c4, "?")] += 1
                print(f"  MIXED {sym!r} per-code:")
                for c4, cc in sorted(detail.items(), key=lambda kv: -sum(kv[1].values())):
                    print(f"    {c4}: vote={dict(cc)} ref_full={ref_full.get(c4)}")
        print("  comp mismatches:", len(comp_mismatch))
        for cm in comp_mismatch[:10]:
            print("    ", cm)
        upc = collections.Counter((u["page"], u["half"], u["row"]) for u in all_unparsed)
        print("  unparsed:", upc.most_common(15))
        print("  no_ref top:", no_ref.most_common(15))
        if no_symbol:
            for ns in no_symbol[:5]:
                print("  no_symbol:", ns)
        print("  first events:", [(e["name_parts"], e["code"], e["dur"], e["half"], e["symbol"],
                                   e["label"]) for e in all_events[:4]])
        # name-normalization preview
        stripped, kept_tails, untailed = [], [], []
        for ev in all_events:
            title = clean(" ".join(ev["name_parts"]))
            if "/" not in ev["code"]:
                continue
            paper = ev["code"].split("/")[1]
            base = strip_comp_tail(title, paper)
            if base is not None:
                stripped.append((title, base, ev["code"]))
            elif TRAILING_NUMS_RE.match(re.sub(r"\)(?=\d)", ") ", title)):
                kept_tails.append((title, ev["code"]))
            else:
                untailed.append((title, ev["code"]))
        print("  strip-rule applies:", len(stripped), stripped[:3])
        print("  kept-tails:", len(kept_tails), kept_tails[:8])
        print("  no-trailing-num:", len(untailed), untailed[:8])


if __name__ == "__main__":
    main()
