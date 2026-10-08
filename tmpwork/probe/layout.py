import re, json
import httpx, pymupdf

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
CIE = "https://cie.fraft.cn"

print("### CIE combo")
with httpx.Client(timeout=30, headers={"User-Agent": UA}) as c:
    r = c.get(f"{CIE}/obj/Common/Subject/combo")
    print("combo", r.status_code, r.text[:300])

print("\n### CIE renum 9709 / 2026 / Mar")
with httpx.Client(timeout=30, headers={"User-Agent": UA}) as c:
    r = c.post(f"{CIE}/obj/Common/Fetch/renum",
               data={"subject": "9709", "year": 2026, "season": "Mar"})
    print("renum", r.status_code)
    data = r.json()
    print("keys:", list(data.keys()), "total:", data.get("total"))
    rows = data.get("rows", [])
    print("rows:", len(rows))
    for row in rows[:12]:
        print("   ", row.get("file"), "| lessons=", repr(row.get("lessons"))[:60])
    files = [row.get("file") for row in rows]

print("\n### CIE redir download 9709_m26_qp_12.pdf")
tgt = next((f for f in files if f and "qp_12" in f), None)
print("target:", tgt)
with httpx.Client(timeout=60, headers={"User-Agent": UA}) as c:
    r = c.get(f"{CIE}/obj/Common/Fetch/redir/{tgt}")
    print("redir", r.status_code, len(r.content), r.content[:8])
    open("tmpwork/probe/cie_qp.pdf", "wb").write(r.content)

print("\n### CIE QP token positions")
doc = pymupdf.open("tmpwork/probe/cie_qp.pdf")
print("pages", len(doc), "size", doc[0].rect)
for pno in range(min(4, len(doc))):
    page = doc[pno]
    t = page.get_text()
    alnum = sum(1 for ch in t if ch.isalnum())
    print(f"-- p{pno} alnum={alnum/max(len(t),1):.3f} drawings={len(page.get_drawings())}")
    for w in sorted(page.get_text("words"), key=lambda w:(round(w[1]/3), w[0]))[:18]:
        print(f"     x0={w[0]:6.1f} y0={w[1]:6.1f} {w[4]!r}")
