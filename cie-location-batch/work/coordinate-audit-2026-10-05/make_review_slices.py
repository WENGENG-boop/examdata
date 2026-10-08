"""为任意卷生成"页对图 + 逐区域目视核验工作清单"（纯离线，通用版）。

前置：先跑 render_regions.py <key> [scale]（需要原件已在 tmp/），本脚本读它的 manifest.json。

输出：
  pairs/<paperdir>/<role>-pair-AA-BB.png     两整页并排对照图（阅读方向渲染）
  pairs/manifest.json                        合并写回（其他卷条目保留）
  review/worklist-<slug>-<role>[-N].json     每片 <= --cap 个区域 + 该片负责的页对图

用法: python make_review_slices.py <subject>/<year>/<season>/<paper> [--cap 80] [--scale S]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os

import fitz

ROOT = r"C:/Users/weo/Desktop/api"
BATCH = os.path.join(ROOT, "cie-location-batch")
AUD = os.path.join(BATCH, "work/coordinate-audit-2026-10-05")
VIS = os.path.join(AUD, "visual")
PAIRS = os.path.join(AUD, "pairs")
REVIEW = os.path.join(AUD, "review")
BASE = "http://127.0.0.1:8792/work/coordinate-audit-2026-10-05/"

GAP = 20
TOP = 60
MAX_W = 1920.0   # 页对图目标最大宽度（浏览器快照 2000x1125）
MAX_H = 1040.0


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def index_path(key: str) -> str:
    subject, year, season, paper = key.split("/")
    return os.path.join(BATCH, "indexes", subject, f"{year}-{season}-{paper}",
                        "cie-index.json")


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
        else:
            token += ch
    if token.isdigit():
        out.append(int(token))
    elif token:
        out.append(token)
    return out


def imgsize(path: str) -> tuple[int, int]:
    pm = fitz.Pixmap(path)
    return pm.width, pm.height


def sheet(out: str, items: list[tuple[str, str]], gap: int = GAP,
          top: int = TOP) -> tuple[int, int]:
    """把若干整页图按自然像素并排合成一张对照图，顶部写标签。不改比例、不缩放。"""
    sizes = [imgsize(p) for p, _ in items]
    width = sum(w for w, _ in sizes) + gap * (len(items) - 1)
    height = top + max(h for _, h in sizes)
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    x = 0
    for (path, label), (w, h) in zip(items, sizes):
        page.insert_image(fitz.Rect(x, top, x + w, top + h), filename=path)
        page.insert_text((x + 8, top - 18), label, fontsize=34, fontname="hebo")
        x += w + gap
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
    pix.save(out)
    doc.close()
    return pix.width, pix.height


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--cap", type=int, default=80)
    ap.add_argument("--scale", type=float, default=None,
                    help="整页渲染缩放；默认按浏览器视口自适应")
    args = ap.parse_args()
    key = args.key
    subject, year, season, paper = key.split("/")
    paperdir = key.replace("/", "_")
    vdir = os.path.join(VIS, paperdir)
    vman_path = os.path.join(vdir, "manifest.json")
    if not os.path.isfile(vman_path):
        print(f"缺少 {vman_path}；请先运行: render_regions.py {key}")
        return 2
    man = json.load(open(vman_path, encoding="utf-8"))
    idx_path = index_path(key)
    index = json.load(open(idx_path, encoding="utf-8"))

    tmpdir = os.path.join(BATCH, "tmp", subject, f"{year}-{season}-{paper}")
    by_sha = {sha256_file(p): p for p in glob.glob(os.path.join(tmpdir, "*.pdf"))}
    docs = {}
    for d in index["documents"]:
        if d["sha256"] in by_sha:
            docs[d["role"]] = by_sha[d["sha256"]]
        else:
            print(f"  原件缺失 {d['role']} sha={d['sha256'][:12]}… 跳过页对图")

    outdir = os.path.join(PAIRS, paperdir)
    os.makedirs(outdir, exist_ok=True)
    pm_path = os.path.join(PAIRS, "manifest.json")
    pm = (json.load(open(pm_path, encoding="utf-8"))
          if os.path.isfile(pm_path) else {})
    entries = []
    for role in ("qp", "ms"):
        path = docs.get(role)
        if not path:
            continue
        doc = fitz.open(path)
        for a in range(1, doc.page_count + 1, 2):
            pages = [p for p in (a, a + 1) if p <= doc.page_count]
            imgs = []
            for pn in pages:
                rect = doc[pn - 1].rect   # 已应用 /Rotate，即阅读方向
                s = args.scale or min(MAX_W / 2 / rect.width,
                                      MAX_H / rect.height, 2.0)
                full = os.path.join(vdir, f"{role}-p{pn}-full.png")
                doc[pn - 1].get_pixmap(matrix=fitz.Matrix(s, s)).save(full)
                imgs.append((full, f"{key} {role} p{pn}"))
            name = f"{role}-pair-{pages[0]:02d}-{pages[-1]:02d}.png"
            w, h = sheet(os.path.join(outdir, name), imgs)
            entries.append({"file": f"pairs/{paperdir}/{name}", "role": role,
                            "pages": pages, "sheet_px": [w, h]})
            print(f"  pair {role} p{pages[0]}-{pages[-1]} -> {name} {w}x{h}")
        doc.close()
    pm[paperdir] = entries
    with open(pm_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(pm, fh, ensure_ascii=False, indent=1)

    sha = sha256_file(idx_path)
    os.makedirs(REVIEW, exist_ok=True)
    made = []
    for role in ("qp", "ms"):
        regs = [r for r in man["regions"] if r.get("crop") and r["role"] == role]
        if not regs:
            print(f"  {role}: 无可核验区域")
            continue
        regs.sort(key=lambda r: (r["page"], qkey(r["question"])))
        nch = max(1, math.ceil(len(regs) / args.cap))
        size = math.ceil(len(regs) / nch)
        chunks = [regs[i:i + size] for i in range(0, len(regs), size)]
        plist = [p for p in pm.get(paperdir, []) if p["role"] == role]
        for k, chunk in enumerate(chunks):
            sid = f"{paperdir}-{role}" + (f"-{k + 1}" if len(chunks) > 1 else "")
            items = []
            seq = 0
            for r in chunk:
                seq += 1
                view = r.get("crop_display") or r["crop"]
                items.append({
                    "seq": seq, "kind": "region",
                    "file": f"visual/{paperdir}/{view}",
                    "url": BASE + f"visual/{paperdir}/{view}",
                    "question": r["question"], "role": role, "page": r["page"],
                    "bbox": r["bbox"], "crop_sha_note": r["crop"],
                    "page_rotation_original": r.get("page_rotation_original"),
                })
            pmax = chunk[-1]["page"]
            mine = [p for p in plist
                    if next((i for i, ch in enumerate(chunks)
                             if ch[-1]["page"] >= p["pages"][0]),
                            len(chunks) - 1) == k]
            del pmax
            for p in mine:
                seq += 1
                items.append({"seq": seq, "kind": "page_pair", "file": p["file"],
                              "url": BASE + p["file"], "pages": p["pages"],
                              "role": role})
            out = {"slice": sid, "paper": key, "role": role,
                   "index_sha256": sha,
                   "counts": {"regions": len(chunk), "page_pairs": len(mine),
                              "items": len(items)},
                   "page_range": [chunk[0]["page"], chunk[-1]["page"]],
                   "items": items}
            with open(os.path.join(REVIEW, f"worklist-{sid}.json"), "w",
                      encoding="utf-8", newline="\n") as fh:
                json.dump(out, fh, ensure_ascii=False, indent=1)
            made.append((sid, out["counts"], out["page_range"]))
            print(f"  worklist {sid}: {out['counts']} pages {out['page_range']}")
    print(json.dumps({"key": key, "index_sha256": sha[:12], "slices": [m[0] for m in made],
                      "pairs": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
