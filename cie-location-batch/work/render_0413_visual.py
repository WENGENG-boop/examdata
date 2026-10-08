"""Render 0413/2026/Jun/11 source pages and the current indexed regions locally.

This helper reads the two preserved PDFs and current local index, then writes
viewable PNGs plus a crop manifest under this paper's tmp directory and work.
It makes no network requests and changes no index or shared batch state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
KEY = "0413/2026/Jun/11"
PAPER = ROOT / "tmp/0413/2026-Jun-11"
INDEX = ROOT / "indexes/0413/2026-Jun-11/cie-index.json"
WORK = ROOT / "work"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    manifest: list[dict] = []
    counts: dict[str, int] = {}
    unique: dict[tuple, str] = {}
    page_dir = PAPER / "pages"
    crop_dir = PAPER / "crops"
    page_dir.mkdir(exist_ok=True)
    crop_dir.mkdir(exist_ok=True)

    for role in ("qp", "ms"):
        pdf_path = PAPER / ("0413_s26_qp_11.pdf" if role == "qp" else "0413_s26_ms_11.pdf")
        with pymupdf.open(pdf_path) as pdf:
            counts[role] = pdf.page_count
            for page_num, page in enumerate(pdf, start=1):
                page_path = page_dir / f"{role}-visual-{page_num:02d}.png"
                page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(page_path)
            for question in data["questions"]:
                qid = str(question["question"])
                for region in question.get(role, []):
                    page_num = int(region["page"])
                    bbox = [round(float(value), 3) for value in region["bbox"]]
                    identity = (role, page_num, tuple(bbox))
                    if identity not in unique:
                        name = f"crop-{len(unique) + 1:03d}-{role}-p{page_num:02d}.png"
                        # Index coordinates are in the unrotated PDF frame.
                        # PyMuPDF's clip argument is in displayed coordinates.
                        clip = pymupdf.Rect(bbox) * pdf[page_num - 1].rotation_matrix
                        pdf[page_num - 1].get_pixmap(
                            matrix=pymupdf.Matrix(2.5, 2.5), clip=clip, alpha=False
                        ).save(crop_dir / name)
                        unique[identity] = name
                    manifest.append({
                        "question": qid,
                        "role": role,
                        "page": page_num,
                        "bbox": bbox,
                        "image": str(crop_dir / unique[identity]),
                    })

    result = {
        "key": KEY,
        "index": str(INDEX),
        "index_sha256": sha256(INDEX),
        "documents": {
            role: {
                "path": str(PAPER / ("0413_s26_qp_11.pdf" if role == "qp" else "0413_s26_ms_11.pdf")),
                "page_count": counts[role],
                "sha256": sha256(PAPER / ("0413_s26_qp_11.pdf" if role == "qp" else "0413_s26_ms_11.pdf")),
            }
            for role in ("qp", "ms")
        },
        "question_nodes": len(data["questions"]),
        "current_regions": len(manifest),
        "unique_current_crops": len(unique),
        "pages": {
            role: [str(page_dir / f"{role}-visual-{n:02d}.png") for n in range(1, counts[role] + 1)]
            for role in ("qp", "ms")
        },
        "regions": manifest,
    }
    (WORK / "0413-current-crop-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: result[k] for k in ("question_nodes", "current_regions", "unique_current_crops", "documents", "index_sha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
