import fitz, json, os

BOOKS_DIR = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"
OUT = r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/scratch/s18/g14b-textlayer-hits.json"
WORDS = ["costwise", "argus", "holman", "743002", "international finest", "roof garden",
         "electric wire", "wooden post", "fibre optic", "fiber optic", "glass cap",
         "acrylic rod", "permanent marker", "beach erosion", "jeffress", "bythwaite"]

out = []
for n in range(1, 21):
    p = os.path.join(BOOKS_DIR, f"book_{n}.pdf")
    if not os.path.exists(p):
        out.append({"book": n, "error": "missing"})
        print(f"book{n}: MISSING", flush=True)
        continue
    try:
        doc = fitz.open(p)
    except Exception as e:
        out.append({"book": n, "error": str(e)})
        print(f"book{n}: ERROR {e}", flush=True)
        continue
    npages = len(doc)
    pages_with_text = 0
    hits = []
    for i in range(npages):
        t = doc[i].get_text()
        if t.strip():
            pages_with_text += 1
        low = t.lower()
        for w in WORDS:
            idx = low.find(w)
            while idx != -1:
                ctx = t[max(0, idx - 40):idx + len(w) + 40].replace("\n", " ")
                hits.append({"page": i + 1, "word": w, "ctx": ctx})
                idx = low.find(w, idx + 1)
    doc.close()
    out.append({"book": n, "pages": npages, "pages_with_text": pages_with_text, "hits": hits})
    print(f"book{n}: pages={npages} text_pages={pages_with_text} hits={len(hits)}", flush=True)
    for h in hits[:8]:
        print("   ", h["page"], h["word"], "|", h["ctx"][:110], flush=True)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("DONE ->", OUT)
