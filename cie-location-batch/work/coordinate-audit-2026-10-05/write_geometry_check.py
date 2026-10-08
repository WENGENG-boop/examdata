"""对本地仍存有原件的卷，用原 PDF 做真实几何核验（纯离线）。

GOAL-SPEC 要求检查：坐标系统 unrotated_pdf_points_top_left、page_base=1、bbox 有限数值、
正宽高、页码不超过页数、页内边界合法、旋转页正确反旋转。

本地 tmp 下实际只剩 0472/2026/Jun/41 的 QP/MS 原件，其余卷原件已清理；本脚本对
有原件的卷逐区域核验，无原件的卷记 not_run（originals_unavailable），不推测。

输出：deliverables/geometry-check.json
"""
from __future__ import annotations

import datetime
import glob
import hashlib
import json
import math
import os

import fitz  # PyMuPDF

ROOT = r"C:/Users/weo/Desktop/api"
BATCH = os.path.join(ROOT, "cie-location-batch")
OUT = os.path.join(BATCH, "work/coordinate-audit-2026-10-05/deliverables")
SERVICE_DIR = os.path.join(ROOT, "examdata/.pytest_cache/callable-api/question_indexes/cie")

TOL = 0.5  # pt，允许边界取整误差


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def page_info(doc) -> list:
    out = []
    for page in doc:
        rect = page.rect            # 已应用 /Rotate
        mb = page.mediabox          # 未旋转的 MediaBox
        out.append({
            "page": page.number + 1,
            "rotation": page.rotation,
            "mediabox": [mb.x0, mb.y0, mb.x1, mb.y1],
            "mediabox_size": [mb.width, mb.height],
            "rect_size": [rect.width, rect.height],
        })
    return out


def check_regions(regions, pages, role, qid):
    issues = []
    n = len(pages)
    for i, r in enumerate(regions or []):
        tag = f"{role}[{i}]"
        page = r.get("page")
        if not isinstance(page, int) or page < 1 or page > n:
            issues.append(f"{tag} 页码非法 {page!r}（页数 {n}）")
            continue
        bbox = r.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            issues.append(f"{tag} bbox 形状非法 {bbox!r}")
            continue
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in bbox):
            issues.append(f"{tag} bbox 非有限数值 {bbox!r}")
            continue
        x0, y0, x1, y1 = bbox
        if not (x1 > x0 and y1 > y0):
            issues.append(f"{tag} bbox 宽高非正 {bbox!r}")
            continue
        mb = pages[page - 1]["mediabox"]
        w, h = mb[2] - mb[0], mb[3] - mb[1]
        if x0 < -TOL or y0 < -TOL or x1 > w + TOL or y1 > h + TOL:
            issues.append(
                f"{tag} bbox 越出未旋转页边界 {bbox!r}（页 {page} 未旋转尺寸 {w:.1f}x{h:.1f}）")
    return issues


def rotated_space_violations(regions, pages):
    """若把 bbox 当成已旋转（rect）空间的坐标来解释，会越界的区域数。

    坐标系统声明为 unrotated_pdf_points_top_left，所以 bbox 应当只在未旋转
    MediaBox 内合法。若存在「未旋转内合法、旋转空间内越界」的区域，即证明这些
    坐标确实写在未旋转空间，与声明一致（反之则说明用了旋转空间，属错误）。
    """
    out = []
    for i, r in enumerate(regions or []):
        page = r.get("page")
        if not isinstance(page, int) or not (1 <= page <= len(pages)):
            continue
        p = pages[page - 1]
        if p["rotation"] % 360 == 0:
            continue
        bbox = r.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        rw, rh = p["rect_size"]
        if bbox[2] > rw + TOL or bbox[3] > rh + TOL:
            out.append({"region_index": i, "page": page, "bbox": bbox,
                        "rotated_space_size": [rw, rh]})
    return out


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    results = []
    for path in sorted(glob.glob(os.path.join(BATCH, "indexes", "**", "cie-index.json"),
                                 recursive=True)):
        index = json.load(open(path, encoding="utf-8"))
        ident = index["identity"]
        key = "/".join(str(ident[k]) for k in ("subject", "year", "season", "paper"))
        tmp_dir = os.path.join(BATCH, "tmp", str(ident["subject"]),
                               f"{ident['year']}-{ident['season']}-{ident['paper']}")
        pdfs = {os.path.basename(p): p for p in glob.glob(os.path.join(tmp_dir, "*.pdf"))}
        docs = {d["role"]: d for d in index["documents"]}
        if len(pdfs) < len(docs):
            results.append({
                "key": key, "status": "not_run",
                "reason": "originals_unavailable",
                "detail": f"tmp 下原件 {len(pdfs)} 份，索引声明 {len(docs)} 份",
            })
            continue
        entry = {"key": key, "status": "checked", "index_sha256": sha256_file(path),
                 "documents": {}}
        for role, doc in docs.items():
            sha = doc["sha256"]
            matches = [p for p in pdfs.values() if sha256_file(p) == sha]
            if not matches:
                entry["documents"][role] = {
                    "status": "sha256_mismatch",
                    "expected": sha,
                    "tmp_files": {os.path.basename(p): sha256_file(p) for p in pdfs.values()},
                }
                continue
            docpdf = fitz.open(matches[0])
            pages = page_info(docpdf)
            regions_by_q = {}
            rot_viol = {}
            for q in index["questions"]:
                issues = check_regions(q.get(role) or [], pages, role, q["question"])
                if issues:
                    regions_by_q[q["question"]] = issues
                rv = rotated_space_violations(q.get(role) or [], pages)
                if rv:
                    rot_viol[q["question"]] = rv
            entry["documents"][role] = {
                "status": "ok",
                "file": os.path.basename(matches[0]),
                "sha256_matches_index": True,
                "page_count": docpdf.page_count,
                "rotated_pages": [p["page"] for p in pages if p["rotation"] % 360],
                "pages": pages,
                "region_issues": regions_by_q,
                "rotated_space_violations": rot_viol,
                "rotated_space_violation_count": sum(len(v) for v in rot_viol.values()),
                "regions_checked": sum(len(q.get(role) or []) for q in index["questions"]),
            }
            docpdf.close()
        entry["total_region_issues"] = sum(
            len(v.get("region_issues", {})) for v in entry["documents"].values())
        entry["geometry_ok"] = entry["total_region_issues"] == 0 and all(
            v.get("status") == "ok" for v in entry["documents"].values())
        results.append(entry)

    checked = [r for r in results if r["status"] == "checked"]
    payload = {
        "generated_at": datetime.datetime.now().astimezone()
            .replace(microsecond=0).isoformat(),
        "tolerance_points": TOL,
        "coordinate_system_expected": "unrotated_pdf_points_top_left",
        "page_base_expected": 1,
        "papers_total": len(results),
        "papers_checked": len(checked),
        "papers_not_run_originals_unavailable": len(results) - len(checked),
        "geometry_ok_papers": sum(r.get("geometry_ok") for r in checked),
        "note": ("几何核验用真实原件；边界按未旋转 MediaBox 判定（坐标系统为 "
                 "unrotated_pdf_points_top_left）。本项不等于视觉核验：未看内容、未判漏题。"),
        "source": "本次实测（原 PDF + PyMuPDF）",
        "entries": results,
    }
    tmp = os.path.join(OUT, "geometry-check.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(OUT, "geometry-check.json"))
    print(json.dumps({k: v for k, v in payload.items() if k != "entries"},
                     ensure_ascii=False))
    for r in checked:
        print(' ', r["key"], "geometry_ok=", r["geometry_ok"],
              "issues=", r["total_region_issues"],
              {k: (v.get("page_count"), v.get("rotated_pages"), v.get("regions_checked"),
                   len(v.get("region_issues", {})))
               for k, v in r["documents"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
