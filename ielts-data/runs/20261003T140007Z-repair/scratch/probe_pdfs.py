import fitz, json, sys, time, os

DL = "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"
out = {}
for n in range(1, 22):
    p = os.path.join(DL, f"book_{n}.pdf")
    if not os.path.exists(p):
        out[n] = {"missing": True}
        continue
    t0 = time.time()
    try:
        doc = fitz.open(p)
    except Exception as e:
        out[n] = {"error": str(e)}
        continue
    pages = doc.page_count
    text_pages = 0
    total_chars = 0
    ak_pages = []
    ak_re = None
    for i in range(pages):
        try:
            t = doc[i].get_text("text")
        except Exception:
            t = ""
        if len(t.strip()) > 50:
            text_pages += 1
        total_chars += len(t)
        low = t.lower()
        if "answer key" in low or "listening and reading answer keys" in low:
            ak_pages.append(i + 1)
    out[n] = {
        "pages": pages,
        "text_pages": text_pages,
        "total_chars": total_chars,
        "answer_key_pages_1based": ak_pages[:20],
        "n_ak_pages": len(ak_pages),
        "secs": round(time.time() - t0, 1),
        "size": os.path.getsize(p),
    }
    doc.close()
print(json.dumps(out, indent=1))
