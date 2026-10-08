import json, pathlib, hashlib, sys
BATCH = pathlib.Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BATCH / "indexes"
keys = ["8238/2025/Jun/32","8238/2025/Nov/31","8238/2025/Nov/32","8238/2025/Nov/33","8238/2026/Jun/32"]
def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1<<20), b''): h.update(c)
    return h.hexdigest()
for k in keys:
    subj, year, season, paper = k.split('/')
    d = IDX / subj / f"{year}-{season}-{paper}"
    f = d / "cie-index.json"
    print("="*70)
    print(k, "exists:", f.exists())
    if not f.exists(): continue
    j = json.loads(f.read_text(encoding='utf-8'))
    print("  sha256:", sha256_file(f))
    print("  top keys:", list(j.keys()))
    docs = j.get("documents") or []
    print("  documents:", [(x.get("role"), (x.get("sha256") or "")[:12], x.get("path") or x.get("file") or x.get("filename")) for x in docs])
    qs = j.get("questions") or []
    print("  questions:", len(qs))
    for q in qs:
        print("   Q", q.get("id"), "label=", q.get("label"), "regions=", len(q.get("regions") or []))
        for r in (q.get("regions") or []):
            print("      -", r.get("role"), "p", r.get("page"), r.get("bbox"), r.get("notes"))
