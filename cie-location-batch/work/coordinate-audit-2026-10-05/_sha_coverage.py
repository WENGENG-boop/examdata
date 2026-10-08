"""比对：各卷当前索引 sha256 vs verification.jsonl 中绑定的 index_sha256。

输出：哪些卷的视觉验收记录仍对当前索引有效（可进入 import/cleanup），
哪些已陈旧（需重验），哪些完全无绑定记录。
"""
import collections
import glob
import hashlib
import json
import os

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = r"C:/Users/weo/Desktop/api/cie-location-batch"


def sh(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


cur = {}
for p in glob.glob(os.path.join(B, "indexes/*/*/cie-index.json")):
    parts = p.replace("\\", "/").split("/")
    subj = parts[-3]
    y, s, pa = parts[-2].split("-")
    cur[f"{subj}/{y}/{s}/{pa}"] = sh(p)

v = collections.defaultdict(collections.Counter)
for line in open(os.path.join(B, "verification.jsonl"), encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    k = r.get("key") or r.get("paper")
    v[k][r.get("index_sha256") or "NO_SHA"] += 1

match, stale, nosha = [], [], []
for k, s in sorted(cur.items()):
    if k not in v:
        nosha.append(k)
        continue
    if s in v[k]:
        match.append((k, v[k][s]))
    elif len(v[k]) == 1 and "NO_SHA" in v[k]:
        nosha.append(k)
    else:
        stale.append((k, s[:12], sorted(x[:12] for x in v[k])))

print("indexes:", len(cur))
print()
print(f"=== A. 绑定 sha == 当前索引（视觉验收对当前索引有效）: {len(match)} ===")
for k, n in match:
    print("  ", k, n)
print()
print(f"=== B. 有绑定记录但已陈旧（需重验）: {len(stale)} ===")
for k, s, vs in stale:
    print("  ", k, "now", s, "bound", vs)
print()
print(f"=== C. 无 sha 绑定记录（仅历史 OCR 或完全无记录）: {len(nosha)} ===")
for k in nosha:
    print("  ", k, dict(v.get(k, {})))
