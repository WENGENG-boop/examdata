"""Render current-index regions of the 6 pending volumes into flat crops + codex sheets.

Reads only local PDFs/indexes; no network. Outputs:
- tmp/<subject>/<year>-<season>-<paper>/crops/v-<role>-p<NN>-r<NN>.png   (per region)
- tmp/<subject>/<year>-<season>-<paper>/crops/v-sheet-<role>-p<NN>[-sK].png (per role-page sheet)
- work/codex_verify/<key-slug>-manifest.json

Geometry matches paperlib: clip = bbox * page.rotation_matrix, clamped to page.rect.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import batchlib as B
import paperlib as P
import pymupdf

OUT_DIR = B.WORK / "codex_verify"
SHEET_MAX_H = 3600
LABEL_H = 24
GAP = 8
PAD = 0.4
ZOOM = 1.65

KEYS = [
    "0413/2026/Jun/11",
    "0509/2026/Jun/11",
    "8386/2026/Jun/11",
    "9396/2023/Nov/11",
    "9709/2024/Jun/11",
    "9715/2023/Nov/21",
]


def render_volume(key: str) -> dict:
    subject, year, season, paper = key.split("/")
    tmp = P.paper_tmp(key)
    idx_path = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    data = json.loads(idx_path.read_text(encoding="utf-8"))
    entry = P.load_paper(key)
    pdf_paths: dict[str, Path] = {}
    for role in ("qp", "ms"):
        docs = entry.get(role) or []
        if docs:
            name = docs[0] if isinstance(docs[0], str) else docs[0]["filename"]
            pdf_paths[role] = tmp / name

    crops_dir = tmp / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    for old in list(crops_dir.glob("v-*.png")):
        old.unlink()

    docs = {role: pymupdf.open(path) for role, path in pdf_paths.items()}
    doc_info = {role: {"path": str(path), "sha256": B.sha256_file(path),
                       "pages": docs[role].page_count} for role, path in pdf_paths.items()}

    regions: list[dict] = []
    groups: dict[tuple, list[dict]] = {}
    counter = 0
    for q in data["questions"]:
        for role in ("qp", "ms"):
            for r in q.get(role) or []:
                counter += 1
                rid = f"A{counter:03d}"
                page_no = int(r["page"])
                bbox = list(r["bbox"])  # verbatim from index; record_key rounds for matching
                page = docs[role][page_no - 1]
                visible = pymupdf.Rect(bbox) * page.rotation_matrix
                clip = pymupdf.Rect(
                    max(page.rect.x0, visible.x0 - PAD),
                    max(page.rect.y0, visible.y0 - PAD),
                    min(page.rect.x1, visible.x1 + PAD),
                    min(page.rect.y1, visible.y1 + PAD),
                )
                pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=clip, alpha=False)
                seq = len(groups.get((role, page_no), [])) + 1
                cpath = crops_dir / f"v-{role}-p{page_no:02d}-r{seq:02d}.png"
                pix.save(cpath)
                reg = {"id": rid, "question": str(q["question"]), "role": role,
                       "page": page_no, "bbox": bbox,
                       "crop": str(cpath.resolve()), "crop_sha256": B.sha256_file(cpath),
                       "w": pix.width, "h": pix.height}
                regions.append(reg)
                groups.setdefault((role, page_no), []).append(reg)

    sheets: list[dict] = []
    for (role, page_no), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        parts: list[list[dict]] = []
        cur: list[dict] = []
        used = 0
        for reg in items:
            cost = LABEL_H + reg["h"] + GAP
            if cur and used + cost > SHEET_MAX_H:
                parts.append(cur)
                cur, used = [], 0
            cur.append(reg)
            used += cost
        if cur:
            parts.append(cur)
        for pi, part in enumerate(parts, 1):
            width = max(900, max(r["w"] for r in part) + 24)
            height = 6 + sum(LABEL_H + r["h"] + GAP for r in part)
            sheet = pymupdf.open()
            sp = sheet.new_page(width=width, height=height)
            y = 6
            for reg in part:
                sp.insert_text((12, y + 16), f"ID {reg['id']} | {reg['role'].upper()} p{reg['page']}",
                               fontsize=12, fontname="helv", color=(0, 0, 0))
                y += LABEL_H
                sp.insert_image(pymupdf.Rect(12, y, 12 + reg["w"], y + reg["h"]),
                                filename=reg["crop"], keep_proportion=False)
                y += reg["h"] + GAP
            suffix = f"-s{pi}" if len(parts) > 1 else ""
            spath = crops_dir / f"v-sheet-{role}-p{page_no:02d}{suffix}.png"
            sp.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False).save(spath)
            sheet.close()
            for reg in part:
                reg["sheet"] = str(spath.resolve())
            sheets.append({"path": str(spath.resolve()), "role": role, "page": page_no,
                           "part": pi, "ids": [r["id"] for r in part],
                           "width": width, "height": height})
    for d in docs.values():
        d.close()

    manifest = {"key": key, "index_path": str(idx_path), "index_sha256": B.sha256_file(idx_path),
                "generated_at": B.now_iso(), "documents": doc_info,
                "regions": regions, "sheets": sheets}
    out = OUT_DIR / (key.replace("/", "-") + "-manifest.json")
    B.atomic_write_json(out, manifest)
    print(f"{key}: regions={len(regions)} sheets={len(sheets)} "
          f"max_sheet_h={max((s['height'] for s in sheets), default=0)} -> {out.name}", flush=True)
    return manifest


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    keys = sys.argv[1:] or KEYS
    for k in keys:
        t0 = time.time()
        render_volume(k)
        print(f"   done in {time.time() - t0:.1f}s", flush=True)
