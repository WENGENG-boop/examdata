# -*- coding: utf-8 -*-
"""One-off read-only audit digest for cie-location-batch. Not part of the pipeline."""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = r"C:/Users/weo/Desktop/api/cie-location-batch"


def rd(p):
    with open(os.path.join(B, p), encoding="utf-8") as f:
        return f.read()


def jload(p):
    return json.loads(rd(p))


print("=== file sizes ===")
for fn in ("subjects.json", "catalogue-grid.json", "papers.json", "checkpoint.json",
           "errors.jsonl", "verification.jsonl", "cleanup.jsonl", "summary.json"):
    fp = os.path.join(B, fn)
    if os.path.exists(fp):
        print(f"  {fn}: {os.path.getsize(fp):,} B")
    else:
        print(f"  {fn}: MISSING")

print()
print("=== summary.json ===")
try:
    s = jload("summary.json")
    print(json.dumps(s, ensure_ascii=False, indent=1)[:6000])
except Exception as e:
    print("ERR", e)

print()
print("=== papers.json ===")
p = jload("papers.json")
print("top:", type(p).__name__, "len:", len(p))
recs = []
if isinstance(p, dict):
    for k, v in p.items():
        if isinstance(v, dict):
            recs.append((k, v))
elif isinstance(p, list):
    for v in p:
        if isinstance(v, dict):
            recs.append((v.get("key"), v))
if recs:
    k0, v0 = recs[0]
    print("first key:", k0)
    print("first rec keys:", sorted(v0.keys()))
    for field in ("stage", "status"):
        print(f"{field}:", dict(Counter(v.get(field) for _, v in recs).most_common()))
    for field in sorted(v0.keys()):
        vals = Counter(v.get(field) for _, v in recs if isinstance(v.get(field), str))
        if any(x in ("paired", "qp_only", "ms_only") for x in vals):
            print(f"kind field '{field}':", dict(vals.most_common()))
    for field in ("readback_verified",):
        if any(field in v for _, v in recs):
            print(f"{field}:", dict(Counter(bool(v.get(field)) for _, v in recs).most_common()))
    ks = sorted(k for k, v in recs if v.get("stage") == "cleaned" and k)
    print(f"cleaned keys ({len(ks)}):")
    for k in ks:
        print("   ", k)
    for stage in ("validation_partial", "conflict", "download_failed", "download_interrupted"):
        ks2 = sorted(k for k, v in recs if v.get("stage") == stage and k)
        print(f"{stage} ({len(ks2)}):", "; ".join(ks2))
    print("--- validation_partial record fields ---")
    for k, v in recs:
        if v.get("stage") == "validation_partial" and k:
            extra = {f: v[f] for f in v if f != "stage" and isinstance(v[f], (str, int, bool)) and len(str(v[f])) < 160}
            print(f"  {k}:", json.dumps(extra, ensure_ascii=False)[:400])
else:
    print("no records parsed")

print()
print("=== cleanup.jsonl ===")
n = tf = tb = 0
stages = Counter()
for line in rd("cleanup.jsonl").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    n += 1
    stages[r.get("stage")] += 1
    for f in ("files", "file_count", "deleted_files", "count"):
        if isinstance(r.get(f), int):
            tf += r[f]
            break
    for f in ("freed_bytes", "bytes", "total_bytes"):
        if isinstance(r.get(f), int):
            tb += r[f]
            break
print("records:", n, "files:", tf, "bytes:", f"{tb:,}")
print("stages:", dict(stages.most_common()))

print()
print("=== errors.jsonl ===")
ek = Counter()
en = 0
last = None
for line in rd("errors.jsonl").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    en += 1
    ek[r.get("kind")] += 1
    last = r
print("records:", en)
print("kinds:", dict(ek.most_common()))
print("last:", json.dumps(last, ensure_ascii=False)[:600])

print()
print("=== verification.jsonl ===")
vn = 0
vk = set()
vi = 0
by_ident = defaultdict(lambda: {"n": 0, "issues": Counter()})
for line in rd("verification.jsonl").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    vn += 1
    ident = r.get("identity") or r.get("key")
    norm = json.dumps(ident, ensure_ascii=False, sort_keys=True) if isinstance(ident, dict) else str(ident)
    vk.add(norm)
    iss = r.get("issues")
    if iss:
        vi += 1
    e = by_ident[norm]
    e["n"] += 1
    if iss:
        for x in (iss if isinstance(iss, list) else [iss]):
            e["issues"][str(x)[:160]] += 1
print("records:", vn, "distinct idents:", len(vk), "with_issues:", vi)
glob_iss = Counter()
for e in by_ident.values():
    glob_iss.update(e["issues"])
print("top issue strings:", dict(glob_iss.most_common(12)))
vp = sorted(k for k, v in recs if v.get("stage") == "validation_partial" and k)
print("--- per validation_partial key verification digest ---")
for k in vp:
    parts = [x for x in str(k).replace("-", "/").split("/") if x]
    hits = [norm for norm in by_ident if all(x in norm for x in parts)]
    if not hits:
        print(f"  {k}: no verification records matched")
        continue
    e = {"n": 0, "issues": Counter()}
    for h in hits:
        e["n"] += by_ident[h]["n"]
        e["issues"].update(by_ident[h]["issues"])
    top = "; ".join(f"{t} x{c}" for t, c in e["issues"].most_common(3))
    print(f"  {k}: records={e['n']} issues: {top[:300]}")

print()
print("=== subjects.json ===")
su = jload("subjects.json")
arr = su.get("subjects") if isinstance(su, dict) else su
if isinstance(su, dict):
    print("top keys:", list(su.keys()))
    for f in ("third_party_completeness", "third_party_source", "source"):
        if f in su:
            print(f, "=", json.dumps(su[f], ensure_ascii=False)[:300])
if isinstance(arr, list):
    print("n subjects:", len(arr))
    if arr and isinstance(arr[0], dict):
        print("first:", json.dumps(arr[0], ensure_ascii=False)[:300])
        print("status:", dict(Counter(x.get("status") for x in arr).most_common()))
        print("third_party_confirmed:", dict(Counter(bool(x.get("third_party_confirmed")) for x in arr).most_common()))

print()
print("=== catalogue-grid.json ===")
g = jload("catalogue-grid.json")
print("top:", type(g).__name__)
cells = None
if isinstance(g, dict):
    print("top keys:", list(g.keys())[:25])
    for cand in ("cells", "grid", "catalogue", "entries"):
        if isinstance(g.get(cand), (dict, list)):
            cells = g[cand]
            print("cells under:", cand)
            break
if cells is None:
    cells = g
vals = list(cells.values()) if isinstance(cells, dict) else (cells if isinstance(cells, list) else [])
print("n cells:", len(vals))
if vals and isinstance(vals[0], dict):
    print("cell keys:", sorted(vals[0].keys()))
    print("status:", dict(Counter(v.get("status") for v in vals).most_common()))
    if any("requested" in v for v in vals):
        print("requested True:", sum(1 for v in vals if v.get("requested") is True),
              "False:", sum(1 for v in vals if v.get("requested") is False),
              "absent:", sum(1 for v in vals if "requested" not in v))

print()
print("=== checkpoint.json ===")
ck = jload("checkpoint.json")
print(json.dumps(ck, ensure_ascii=False, indent=1)[:3000])

print()
print("=== indexes ===")
idx = sorted(glob.glob(B + "/indexes/*/*/cie-index.json"))
print("n:", len(idx), "bytes:", f"{sum(os.path.getsize(x) for x in idx):,}")
subs = sorted({x.replace("\\", "/").split("/indexes/")[1].split("/")[0] for x in idx})
print("subjects with index:", len(subs), subs)
tot_q = 0
bad = 0
for x in idx:
    t = open(x, encoding="utf-8").read()
    if "base64" in t or "data:image" in t:
        bad += 1
    try:
        d = json.loads(t)
        tot_q += len(d.get("questions") or [])
    except Exception:
        pass
print("total questions:", tot_q, "| indexes with base64/image:", bad)
if isinstance(arr, list):
    tpc = sorted(str(x.get("code")) for x in arr if x.get("third_party_confirmed"))
    missing = [c for c in tpc if c not in subs]
    print("third-party codes:", len(tpc))
    print("third-party WITHOUT index:", len(missing), missing)

print()
print("=== tmp ===")
tf_list = []
for root, dirs, files in os.walk(B + "/tmp"):
    for fn in files:
        fp = os.path.join(root, fn)
        tf_list.append((fp.replace("\\", "/"), os.path.getsize(fp)))
print("files:", len(tf_list), "bytes:", f"{sum(s for _, s in tf_list):,}")
print("ext:", dict(Counter(os.path.splitext(f)[1].lower() for f, _ in tf_list).most_common()))
kd = Counter()
kb = Counter()
for f, sz in tf_list:
    rel = f.split("/tmp/")[1]
    parts = rel.split("/")
    k = "/".join(parts[:2]) if len(parts) >= 3 else rel
    kd[k] += 1
    kb[k] += sz
print("dirs with files:", len(kd))
for k in sorted(kd):
    print(f"    {k}: {kd[k]} files {kb[k]:,} B")
parts2 = glob.glob(B + "/**/*.part", recursive=True)
print("part files:", len(parts2))

print()
print("=== disk PDFs/images under C:/Users/weo/Desktop/api (excl .venv) ===")
root = r"C:/Users/weo/Desktop/api"
c2 = Counter(); b2 = Counter(); c4 = Counter(); b4 = Counter(); ci = Counter()
for dp, dn, fn in os.walk(root):
    if ".venv" in dp.split(os.sep):
        continue
    for f in fn:
        fp = os.path.join(dp, f)
        rel = os.path.relpath(fp, root).replace("\\", "/")
        parts = rel.split("/")
        low = f.lower()
        if low.endswith(".pdf"):
            sz = os.path.getsize(fp)
            g2 = "/".join(parts[:2])
            g4 = "/".join(parts[:4])
            c2[g2] += 1; b2[g2] += sz
            c4[g4] += 1; b4[g4] += sz
        elif low.endswith((".png", ".jpg", ".jpeg")):
            ci["/".join(parts[:2])] += 1
print("TOTAL PDFs:", sum(c2.values()), "bytes:", f"{sum(b2.values()):,}")
for g in sorted(c2, key=lambda x: -c2[x]):
    print(f"  {c2[g]:5d} {b2[g]:>13,} {g}")
print("--- examdata deeper (top-4, top 35) ---")
rows = [(g, c4[g], b4[g]) for g in c4]
rows.sort(key=lambda r: -r[1])
for g, nn, bb in rows[:35]:
    print(f"  {nn:5d} {bb:>13,} {g}")
print("--- images by top-2 ---")
for g in sorted(ci, key=lambda x: -ci[x]):
    print(f"  {ci[g]:6d} {g}")
