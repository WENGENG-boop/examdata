#!/usr/bin/env python3
"""G14b step3: re-verify feature-word scan on ocr20 + book11 crops JSONs.
Replaces reliance on the earlier g14b-dump-and-search.py claim ("0 hits").
Reads: g14b-ocr20-test{1..4}-p*.json, g14b-book11-p124-crops.json
Writes: g14b-ocr20-crops-recheck.txt
"""
import json, re, os, sys

S18 = os.path.dirname(os.path.abspath(__file__))

PRIMARY = [
    "costwise", "costwlse", "argus", "argo", "holman", "holma",
    "743002", "7430", "roofgarden", "electricwire", "woodenpost",
    "fibreoptic", "fiberoptic", "flbreoptic", "optlccable", "opticcable",
    "glasscap", "acrylic", "permanentmarker", "beacherosion", "internationalfinest",
    "jeffress", "bythwaite",
]
SECONDARY = [
    "continent", "geology", "newspaper", "luggage", "pavement", "creditcard",
    "erosion", "permanent", "electric", "wooden", "optic", "finest",
    "sydney", "helmet", "6.15", "615",
]

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())

def scan_words(words):
    hits = []
    for w in words:
        t = w.get("text", "")
        n = norm(t)
        if not n:
            continue
        for kw in PRIMARY:
            if kw in n:
                hits.append(("PRIMARY", kw, t, w.get("conf"), w.get("x0"), w.get("y0")))
                break
        else:
            for kw in SECONDARY:
                if kw in n:
                    hits.append(("SECONDARY", kw, t, w.get("conf"), w.get("x0"), w.get("y0")))
                    break
    return hits

out = []
files = sorted(f for f in os.listdir(S18) if f.startswith("g14b-ocr20-test") and f.endswith(".json"))
files += ["g14b-book11-p124-crops.json"]

for fname in files:
    path = os.path.join(S18, fname)
    if not os.path.exists(path):
        out.append(f"== {fname} == MISSING")
        continue
    d = json.load(open(path, encoding="utf-8"))
    out.append(f"== {fname} ==")
    out.append(f"pdf: {d.get('pdf')} dpi: {d.get('dpi')}")
    if "pages" in d:
        for pg in d["pages"]:
            hits = scan_words(pg.get("words", []))
            out.append(f"  page {pg.get('file_page')}: {len(pg.get('words', []))} words, {len(hits)} feature hits")
            for kind, kw, t, conf, x0, y0 in hits:
                out.append(f"    [{kind}:{kw}] {t!r} conf={conf} x0={x0:.0f} y0={y0:.0f}")
    elif "strips" in d:
        for st in d["strips"]:
            hits = scan_words(st.get("words", []))
            label = st.get("strip") or st.get("label") or st.get("name")
            out.append(f"  strip {label}: {len(st.get('words', []))} words, {len(hits)} feature hits")
            for kind, kw, t, conf, x0, y0 in hits:
                out.append(f"    [{kind}:{kw}] {t!r} conf={conf} x0={x0} y0={y0}")
    out.append("")

txt = "\n".join(out)
open(os.path.join(S18, "g14b-ocr20-crops-recheck.txt"), "w", encoding="utf-8").write(txt)
print(txt)
