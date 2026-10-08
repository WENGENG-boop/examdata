"""生成目视核验工作清单（按卷/角色分片），供子代理逐图查看。

输入：visual/<paperdir>/manifest.json（区域清单）、pairs/manifest.json（页对照图）。
输出：review/worklist-sXX.json。每 item 含可直接在浏览器打开的 url。
纯离线。
"""
from __future__ import annotations

import hashlib
import json
import os

ROOT = r"C:/Users/weo/Desktop/api"
BATCH = os.path.join(ROOT, "cie-location-batch")
AUD = os.path.join(BATCH, "work/coordinate-audit-2026-10-05")
VIS = os.path.join(AUD, "visual")
BASE = "http://127.0.0.1:8792/work/coordinate-audit-2026-10-05/"

SLICES = [
    ("s01", "8386_2025_Jun_11", "8386/2025/Jun/11", "qp", None),
    ("s02", "8386_2025_Jun_11", "8386/2025/Jun/11", "ms", None),
    ("s03", "8386_2026_Jun_12", "8386/2026/Jun/12", "qp", None),
    ("s04", "8386_2026_Jun_12", "8386/2026/Jun/12", "ms", None),
    ("s05", "8386_2026_Jun_13", "8386/2026/Jun/13", "qp", None),
    ("s06", "8386_2026_Jun_13", "8386/2026/Jun/13", "ms", None),
    ("s07", "0495_2026_Jun_11", "0495/2026/Jun/11", "qp", None),
    ("s08", "0495_2026_Jun_11", "0495/2026/Jun/11", "ms", (1, 21)),
    ("s09", "0495_2026_Jun_11", "0495/2026/Jun/11", "ms", (22, 99)),
]


def qkey(q: str):
    """1(a)(ii) -> (1,'a','ii') 之类的稳定排序键。"""
    out = []
    token = ""
    for ch in q:
        if ch in "()":
            if token.isdigit():
                out.append(int(token))
            elif token:
                out.append(token)
            token = ""
        elif ch == "":
            continue
        else:
            token += ch
    if token.isdigit():
        out.append(int(token))
    elif token:
        out.append(token)
    return out


def main() -> int:
    review = os.path.join(AUD, "review")
    os.makedirs(review, exist_ok=True)
    pairs = json.load(open(os.path.join(AUD, "pairs/manifest.json"), encoding="utf-8"))

    summary = {}
    for sid, paperdir, key, role, rng in SLICES:
        man = json.load(open(os.path.join(VIS, paperdir, "manifest.json"),
                             encoding="utf-8"))
        regions = [r for r in man["regions"] if r.get("crop") and r["role"] == role]
        if rng:
            regions = [r for r in regions if rng[0] <= r["page"] <= rng[1]]
        regions.sort(key=lambda r: (r["page"], qkey(r["question"])))
        items = []
        seq = 0
        for r in regions:
            seq += 1
            view = (r.get("crop_display") or r["crop"]) if role == "ms" else r["crop"]
            items.append({
                "seq": seq, "kind": "region", "file": f"visual/{paperdir}/{view}",
                "url": BASE + f"visual/{paperdir}/{view}",
                "question": r["question"], "role": role, "page": r["page"],
                "bbox": r["bbox"], "crop_sha_note": r["crop"],
            })
        plist = [p for p in pairs[paperdir] if p["role"] == role]
        if rng:
            # 跨切片边界的页对归入首段所在切片（两页必须都在卷内）
            plist = [p for p in plist if rng[0] <= p["pages"][0] <= rng[1]]
        for p in plist:
            seq += 1
            items.append({
                "seq": seq, "kind": "page_pair", "file": p["file"],
                "url": BASE + p["file"], "pages": p["pages"], "role": role,
            })
        idx = os.path.join(BATCH, "indexes", *key.split("/")[:1], key.split("/")[1] + "-" + key.split("/")[2] + "-" + key.split("/")[3], "cie-index.json")
        sha = hashlib.sha256(open(idx, "rb").read()).hexdigest()
        out = {"slice": sid, "paper": key, "role": role,
               "index_sha256": sha, "counts": {"regions": len(regions),
                                               "page_pairs": len(plist),
                                               "items": len(items)},
               "items": items}
        with open(os.path.join(review, f"worklist-{sid}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        summary[sid] = out["counts"]
        print(sid, key, role, out["counts"], sha[:12])
    with open(os.path.join(review, "slices-summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
