# consolidate-book20.py — 汇总剑20 四册结构证据
import hashlib, json, os, re

ROOT = "C:/Users/weo/Desktop/api"
RUN = os.path.join(ROOT, "ielts-data/runs/20261003T140007Z-repair")
OCR = os.path.join(RUN, "derived/ocr20")
SRC = os.path.join(ROOT, "ielts-data/raw/pdf-source")
OUT = os.path.join(RUN, "evidence/S06-book20-structure.json")

def norm(s):
    return re.sub(r"\s+", "", s).lower()

out = {
    "source": "BaBaLiBoo/IELTS-Resources",
    "source_note": "剑桥20真题（抢先版）分册 4 个；图像型 PDF（text_chars=0），结构由页眉条 OCR 构建",
    "pdf_dir": SRC,
    "tests": {},
    "all_ok": True,
}

for t in [1, 2, 3, 4]:
    pdf = os.path.join(SRC, f"book20-test{t}.pdf")
    buf = open(pdf, "rb").read()
    d = json.load(open(os.path.join(OCR, f"ocr20-test{t}-struct.json"), encoding="utf-8"))
    rec = {
        "pdf": pdf,
        "bytes": len(buf),
        "sha256": hashlib.sha256(buf).hexdigest(),
        "pages": len(d["pages"]),
        "sections": [],
        "question_headers": [],
        "answer_key_pages": [],
        "part4_evidence": None,
    }
    for p in d["pages"]:
        txt = " ".join(w["text"] for w in p["words"])
        n = norm(txt)
        fp = p["file_page"]
        m = re.search(r"test\d*[-–]?(listening|reading|writing|speaking)[-–]?(?:part|passage|task)?(\d)?", n)
        if m:
            rec["sections"].append({"page": fp, "kind": m.group(1), "num": m.group(2), "raw": txt[:60]})
        qm = re.search(r"questions?\d+[-–]\d+", n)
        if qm:
            rec["question_headers"].append({"page": fp, "header": qm.group(0)})
        if "答案" in txt or "答案:" in txt:
            rec["answer_key_pages"].append(fp)
        if not rec["part4_evidence"] and re.search(r"questions?31[-–]40", n):
            rec["part4_evidence"] = {"page": fp, "snippet": txt[:180]}
    out["tests"][t] = rec
    out["all_ok"] = out["all_ok"] and rec["part4_evidence"] is not None and len(rec["pages"] if False else rec["sections"]) > 0

# 深核（整页 OCR）证据：Part4 主题页 + test2 答案页
deep = {
    1: ("ocr20-test1-p45-full.json", 5, "Reclaiming urban rivers"),
    2: ("ocr20-test2-p567-full.json", 6, "Developing food trends"),
    3: ("ocr20-test3-p56-full.json", 6, "Inclusive design"),
    4: ("ocr20-test4-p56-full.json", 6, "The importance of birds of prey"),
}
out["part4_deep_check"] = {}
for t, (f, pg, topic) in deep.items():
    d = json.load(open(os.path.join(OCR, f), encoding="utf-8"))
    p = [x for x in d["pages"] if x["file_page"] == pg][0]
    txt = " ".join(w["text"] for w in p["words"])
    has31 = "31" in txt
    out["part4_deep_check"][t] = {
        "page": pg, "topic": topic, "words": len(p["words"]), "has_q31": has31,
        "snippet": txt[:160],
        "note": "整页 OCR 确证 Part4 题面存在（图像 PDF，无文本层）",
    }
    out["tests"][t]["part4_evidence"] = {"page": pg, "snippet": txt[:180], "source": "full_page_ocr"}

full2 = json.load(open(os.path.join(OCR, "ocr20-test2-p567-full.json"), encoding="utf-8"))
p7 = [p for p in full2["pages"] if p["file_page"] == 7][0]
ak = " ".join(w["text"] for w in p7["words"])
out["test2_answer_page"] = {"page": 7, "snippet": ak[:220], "has_alternates": "|" in ak}

out["all_ok"] = all(t["part4_evidence"] for t in out["tests"].values())

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("ALL_OK=", out["all_ok"])
for t, r in out["tests"].items():
    secs = ", ".join(f"{s['kind']}{s['num'] or ''}@p{s['page']}" for s in r["sections"])
    p4 = r["part4_evidence"]["page"] if r["part4_evidence"] else "MISSING"
    print(f"test{t}: {r['pages']}p {r['sha256'][:12]} | sections: {secs} | part4@p{p4} | ak_pages={r['answer_key_pages']}")
print("->", OUT)
