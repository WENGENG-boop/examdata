import fitz, json, sys

DL = "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"
# sample answer-key pages from three books to learn formats
samples = {
    "book_1": [136, 137, 138, 139, 140, 141, 145, 149, 153, 157],
    "book_4": [153, 154, 155, 156],
    "book_10": [144, 145, 146, 148, 149, 150],
    "book_17": [119, 120, 121],
    "book_2": [71, 72, 73, 74, 75, 76, 77],
}
out = {}
for name, pages in samples.items():
    doc = fitz.open(DL + "/" + name + ".pdf")
    out[name] = {}
    for p in pages:
        if p - 1 < doc.page_count:
            t = doc[p - 1].get_text("text")
            out[name][p] = t[:3500]
    doc.close()
with open("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/scratch/ak_samples.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("done", {k: len(v) for k, v in out.items()})
