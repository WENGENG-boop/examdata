#!/usr/bin/env python
"""G14b: search OCR sweep results (book9/16/18/19) for pte-4L feature words.

Space/hyphen-insensitive matching over per-page word sequences, with context.
Includes OCR-variant fuzzy patterns for decisive names/numbers.
"""
import json
import re
from pathlib import Path

S18 = Path("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/scratch/s18")

PRIMARY = ["costwise", "costwlse", "costw", "argus", "argo", "holman", "holma",
           "holrnan", "ho1man", "robholman", "northcarolina", "jeffress", "jeffre",
           "743002", "743oo2", "7430o2", "7430", "roofgarden", "electricwire", "woodenpost",
           "fibreoptic", "fiberoptic", "flbreoptic", "opticcable", "optlccable",
           "glasscap", "acrylicrod", "beacherosion", "permanentmarker",
           "internationalfinest", "fixedcamera"]
SECONDARY = ["continent", "geology", "newspaper", "luggage", "pavement", "creditcard",
             "6.15", "erosion", "permanent", "electric", "wooden", "acrylic",
             "optic", "finest", "sydney", "helmet", "echo", "housekeeper",
             "cateringmanager", "conferenceorganizer"]

FILES = ["g14b-scan-book9.json", "g14b-scan-book16.json",
         "g14b-scan-book18.json", "g14b-scan-book19.json",
         "g14b-scan-book20-test1.json", "g14b-scan-book20-test2.json",
         "g14b-scan-book20-test3.json", "g14b-scan-book20-test4.json"]


def norm(s):
    return re.sub(r"[\s\-_]+", "", s.lower())


def search_page(words):
    norm_words = [norm(w["text"]) for w in words]
    joined = "".join(norm_words)
    spans = []
    pos = 0
    for nw in norm_words:
        spans.append((pos, pos + len(nw)))
        pos += len(nw)
    hits = []
    for pat in PRIMARY + SECONDARY:
        start = 0
        while True:
            i = joined.find(pat, start)
            if i < 0:
                break
            wi = next(k for k, (a, b) in enumerate(spans) if a <= i < b)
            ctx = " ".join(w["text"] for w in words[max(0, wi - 6):wi + 7])
            hits.append({"pattern": pat, "word_index": wi, "ctx": ctx})
            start = i + 1
    return hits


primary_hits = []
secondary_hits = []
scanned_info = []
for fn in FILES:
    p = S18 / fn
    if not p.exists():
        print(f"MISSING {fn}", flush=True)
        scanned_info.append(f"{fn}: MISSING")
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    for pg in data["pages"]:
        for h in search_page(pg["words"]):
            rec = {"file": fn, "file_page": pg["file_page"], **h}
            (primary_hits if h["pattern"] in PRIMARY else secondary_hits).append(rec)
    scanned_info.append(f"{fn}: {len(data['pages'])} pages")
    print(f"{fn}: {len(data['pages'])} pages scanned", flush=True)

out_lines = []
out_lines.append("=== G14b search sweep results ===")
out_lines.append(f"files: {FILES}")
out_lines.append(f"scanned: {scanned_info}")
out_lines.append("")
out_lines.append("=== PRIMARY HITS ===")
if not primary_hits:
    out_lines.append("(none)")
for h in primary_hits:
    out_lines.append(f"{h['file']} p{h['file_page']} [{h['pattern']}] {h['ctx'][:220]}")

out_lines.append("")
out_lines.append("=== SECONDARY HITS (context review) ===")
for h in secondary_hits[:150]:
    out_lines.append(f"{h['file']} p{h['file_page']} [{h['pattern']}] {h['ctx'][:160]}")
out_lines.append(f"(secondary total {len(secondary_hits)})")
txt = "\n".join(out_lines)
(S18 / "g14b-search-sweep-results.txt").write_text(txt + "\n", encoding="utf-8")
print(txt)
print("saved -> g14b-search-sweep-results.txt")
