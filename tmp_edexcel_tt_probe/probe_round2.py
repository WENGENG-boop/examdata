import glob, re, pymupdf

print("### 非标准命名文件（iter_seasons 跳过）")
for fam in ("gcse", "intgcse", "ial", "gce"):
    for p in sorted(glob.glob(f"downloads/edexcel/{fam}/*.pdf")):
        stem = p.replace("\\", "/").split("/")[-1][:-4]
        if not re.match(r"^\d{4}-\d{2}(-r)?$", stem):
            print("  SKIP", p)

for path, page in [
    ("downloads/edexcel/gcse/2019-11.pdf", 5),
    ("downloads/edexcel/gcse/2016-06.pdf", 6),
    ("downloads/edexcel/ial/2017-06.pdf", 5),
    ("downloads/edexcel/ial/2018-06.pdf", 4),
    ("downloads/edexcel/intgcse/2020-11-r.pdf", 3),
]:
    doc = pymupdf.open(path)
    print("=" * 90)
    print(path, "page", page, "of", len(doc))
    text = doc[page - 1].get_text()
    print(text[:3500])
    doc.close()
