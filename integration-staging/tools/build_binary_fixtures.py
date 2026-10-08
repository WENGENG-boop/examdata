#!/usr/bin/env python3
"""Build the A11 binary fixtures (plan 5.3, plan section 11/A11).

Deterministic, dependency-free generator for the small immutable binary
samples the staged v2 binary transport serves: four single-page PDFs shaped
like question papers and mark schemes, two small diagrams, one syllabus PDF,
one material PDF and three question-crop PNGs (plan 5.3: "use synthetic
PDF/image/audio fixtures").

Every sample is synthetic: the payloads are hand-built here, contain invented
text and patterns only, and carry no upstream bytes. `manifest.json` records
both the fixture-side *declared* identity (the hash the provider fixtures
declare, for example the CIE question paper 2222...2) and the *real*
sha256/byte-size of the bytes on disk, so the transport can verify integrity
without ever fabricating a hash. `PROVENANCE.json` lists every file.

    python tools/build_binary_fixtures.py           # write the fixtures
    python tools/build_binary_fixtures.py --check   # verify, write nothing

Nothing outside `integration-staging/fixtures/synthetic/binary/` is written;
no original path is read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

sys.dont_write_bytecode = True

STAGING = Path(__file__).resolve().parents[1]
OUT_DIR = STAGING / "fixtures" / "synthetic" / "binary"
TOOL_REL = "integration-staging/tools/build_binary_fixtures.py"

CREATED_AT_LOCAL = "2026-10-05T23:30:00+08:00"
CREATED_AT_UTC = "2026-10-05T15:30:00+00:00"
CREATED_BY = "Phase A executor (packet A11)"

MEDIA_WHITELIST = ("application/pdf", "image/png")

#: fixture-side declared hashes, exactly as the frozen provider fixtures declare
#: them (A03). Each 64-char string repeats one digit on purpose: these are
#: placeholder identities, never real upstream document hashes.
SHA_CIE_QP = "2" * 64
SHA_CIE_MS = "3" * 64
SHA_CIE_IMAGE = "4" * 64
SHA_EDEXCEL_QP = "5" * 64
SHA_EDEXCEL_MS = "6" * 64
SHA_IELTS_IMAGE = "0" * 64


# --------------------------------------------------------------------------- #
# PDF rendering: one page, built here, xref offsets computed as we go
# --------------------------------------------------------------------------- #
def _pdf_escape(text: str) -> bytes:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)").encode("ascii")


def _pdf_text_ops(lines: list[str]) -> bytes:
    parts: list[bytes] = [b"BT /F1 12 Tf 72 780 Td"]
    for index, line in enumerate(lines):
        if index:
            parts.append(b"0 -16 Td")
        parts.append(b"(" + _pdf_escape(line) + b") Tj")
    parts.append(b"ET")
    return b"\n".join(parts)


def build_pdf(lines: list[str]) -> bytes:
    """A minimal, structurally valid single-page PDF with text lines only."""
    stream = _pdf_text_ops(lines)

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
         b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n").encode("ascii")
    return bytes(out)


# --------------------------------------------------------------------------- #
# PNG rendering: one image, built here, filter-0 scanlines + zlib + CRC
# --------------------------------------------------------------------------- #
def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def build_png(width: int, height: int, seed: int) -> bytes:
    """A small deterministic RGB PNG; the pattern is a pure integer function."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0
        for x in range(width):
            raw += bytes((
                (x * 7 + y * 11 + seed * 29) % 256,
                (x * 13 + seed * 17) % 256,
                (y * 19 + seed * 23) % 256,
            ))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", header)
            + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _png_chunk(b"IEND", b""))


# --------------------------------------------------------------------------- #
# the fixture set
# --------------------------------------------------------------------------- #
def _pdf_samples() -> dict[str, bytes]:
    return {
        "cie-qp.pdf": build_pdf([
            "Synthetic CIE question paper (fixture)",
            "Subject 9999 - Paper 11 - June 2024",
            "Question 1 (page 2), Question 2 (page 3), Question 3 (page 4)",
            "Invented text only. No real examination content.",
        ]),
        "cie-ms.pdf": build_pdf([
            "Synthetic CIE mark scheme (fixture)",
            "Subject 9999 - Paper 11 - June 2024",
            "Invented marking notes only.",
        ]),
        "edexcel-qp.pdf": build_pdf([
            "Synthetic Edexcel question paper (fixture)",
            "Unit SYN-WMA11 - Paper 01 - 2024-Jun",
            "Invented text only. No real examination content.",
        ]),
        "edexcel-ms.pdf": build_pdf([
            "Synthetic Edexcel mark scheme (fixture)",
            "Unit SYN-WMA11 - Paper 01 - 2024-Jun",
            "Invented marking notes only.",
        ]),
    }


def _image_samples() -> dict[str, bytes]:
    return {
        "cie-diagram.png": build_png(28, 18, seed=4),
        "ielts-diagram.png": build_png(32, 20, seed=0),
    }


def _syllabus_samples() -> dict[str, bytes]:
    return {
        "syllabus-synthetic-cie-0580.pdf": build_pdf([
            "Synthetic syllabus fixture for course 9999",
            "This is not a real syllabus.",
        ]),
    }


def _material_samples() -> dict[str, bytes]:
    return {
        "material-synthetic-cie-ins.pdf": build_pdf([
            "Synthetic insert fixture for CIE",
            "This is not a real insert.",
        ]),
    }


def _crop_samples() -> dict[str, bytes]:
    return {
        "crop-cie-1-page2.png": build_png(44, 30, seed=12),
        "crop-cie-2-page3.png": build_png(44, 30, seed=23),
        "crop-cie-3-page4.png": build_png(44, 30, seed=34),
    }


def _entry(rel: str, blob: bytes) -> dict:
    return {"file": rel, "media_type": None, "byte_size": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest()}


def render_all() -> dict[str, bytes]:
    """Render every fixture file (samples, manifest, PROVENANCE) in memory."""
    documents = _pdf_samples() | _image_samples()
    syllabuses = _syllabus_samples()
    materials = _material_samples()
    crops = _crop_samples()
    samples = {**documents, **syllabuses, **materials, **crops}

    doc_entries = [
        {"file": "cie-qp.pdf", "media_type": "application/pdf",
         "system": "cie", "role": "qp", "declared_sha256": SHA_CIE_QP,
         "note": "shaped like the CIE synthetic question paper (declared 2222...2)"},
        {"file": "cie-ms.pdf", "media_type": "application/pdf",
         "system": "cie", "role": "ms", "declared_sha256": SHA_CIE_MS,
         "note": "shaped like the CIE synthetic mark scheme (declared 3333...3)"},
        {"file": "cie-diagram.png", "media_type": "image/png",
         "system": "cie", "role": "graph", "declared_sha256": SHA_CIE_IMAGE,
         "note": "shaped like question 3's required diagram (declared 4444...4)"},
        {"file": "edexcel-qp.pdf", "media_type": "application/pdf",
         "system": "edexcel", "role": "qp", "declared_sha256": SHA_EDEXCEL_QP,
         "note": "shaped like the Edexcel synthetic question paper (declared 5555...5)"},
        {"file": "edexcel-ms.pdf", "media_type": "application/pdf",
         "system": "edexcel", "role": "ms", "declared_sha256": SHA_EDEXCEL_MS,
         "note": "shaped like the Edexcel synthetic mark scheme (declared 6666...6)"},
        {"file": "ielts-diagram.png", "media_type": "image/png",
         "system": "ielts", "role": "diagram", "declared_sha256": SHA_IELTS_IMAGE,
         "note": "shaped like IELTS question 5's required diagram (declared 0000...0)"},
    ]
    for entry in doc_entries:
        blob = documents[entry["file"]]
        entry["byte_size"] = len(blob)
        entry["sha256"] = hashlib.sha256(blob).hexdigest()

    syllabus_entries = [
        {"public_id": "syl_synthetic_cie_0580",
         "file": "syllabus-synthetic-cie-0580.pdf",
         "media_type": "application/pdf",
         "note": "content sample for the labelled synthetic syllabus fixture"},
    ]
    material_entries = [
        {"public_id": "mat_synthetic_cie_ins",
         "file": "material-synthetic-cie-ins.pdf",
         "media_type": "application/pdf",
         "note": "content sample for the labelled synthetic material fixture"},
    ]
    crop_entries = [
        {"file": "crop-cie-1-page2.png", "media_type": "image/png",
         "system": "cie", "native_id": "1", "page": 2,
         "declared_document_sha256": SHA_CIE_QP,
         "note": "crop sample for CIE question 1 on page 2 of the declared qp"},
        {"file": "crop-cie-2-page3.png", "media_type": "image/png",
         "system": "cie", "native_id": "2", "page": 3,
         "declared_document_sha256": SHA_CIE_QP,
         "note": "crop sample for CIE question 2 on page 3 of the declared qp"},
        {"file": "crop-cie-3-page4.png", "media_type": "image/png",
         "system": "cie", "native_id": "3", "page": 4,
         "declared_document_sha256": SHA_CIE_QP,
         "note": "crop sample for CIE question 3 on page 4 of the declared qp"},
    ]
    for entry in syllabus_entries + material_entries + crop_entries:
        blob = samples[entry["file"]]
        entry["byte_size"] = len(blob)
        entry["sha256"] = hashlib.sha256(blob).hexdigest()

    tool_sha = hashlib.sha256((STAGING.parent / TOOL_REL).read_bytes()).hexdigest()
    manifest = {
        "schema": "examdata.integration.content-manifest/1",
        "created_by": CREATED_BY,
        "created_at_local": CREATED_AT_LOCAL,
        "created_at_utc": CREATED_AT_UTC,
        "generator": TOOL_REL,
        "generator_sha256": tool_sha,
        "note": ("Synthetic binary samples for the staged transport. 'declared_sha256' "
                 "is the fixture-side placeholder identity from the frozen provider "
                 "fixtures; 'sha256'/'byte_size' describe the bytes on disk."),
        "media_whitelist": list(MEDIA_WHITELIST),
        "documents": doc_entries,
        "syllabuses": syllabus_entries,
        "materials": material_entries,
        "crops": crop_entries,
    }
    manifest_bytes = _json_bytes(manifest)

    provenance_files = [*sorted(samples), "manifest.json"]
    provenance = {
        "schema": "fixture-provenance/1",
        "scope": "A11 synthetic binary samples for the staged content/crop transport",
        "note": ("Hand-built deterministic binary samples (PDF/PNG). No upstream "
                 "bytes, no real examination content, no real document hashes."),
        "created_by": CREATED_BY,
        "created_at_local": CREATED_AT_LOCAL,
        "entries": [],
    }
    for rel in provenance_files:
        blob = manifest_bytes if rel == "manifest.json" else samples[rel]
        provenance["entries"].append({
            "path": f"integration-staging/fixtures/synthetic/binary/{rel}",
            "kind": "synthetic",
            "label": "synthetic_fixture",
            "created_by": CREATED_BY,
            "created_at_local": CREATED_AT_LOCAL,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
            "note": "deterministic synthetic binary sample" if rel != "manifest.json"
                    else "content manifest for the synthetic binary samples",
        })
    provenance["summary"] = {"entries": len(provenance["entries"]),
                             "synthetic": len(provenance["entries"])}
    provenance_bytes = _json_bytes(provenance)

    return {**samples, "manifest.json": manifest_bytes,
            "PROVENANCE.json": provenance_bytes}


def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- #
# write / check
# --------------------------------------------------------------------------- #
def _within_out(path: Path) -> bool:
    resolved = path.resolve()
    out = OUT_DIR.resolve()
    return resolved == out or out in resolved.parents


def write(rendered: dict[str, bytes]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    changed = unchanged = 0
    for rel, blob in sorted(rendered.items()):
        target = OUT_DIR / rel
        assert _within_out(target), f"refusing to write outside {OUT_DIR}: {target}"
        current = target.read_bytes() if target.is_file() else None
        if current == blob:
            unchanged += 1
            print(f"[unchanged] {rel}")
        else:
            target.write_bytes(blob)
            changed += 1
            print(f"[{'written' if current is None else 'updated'}] {rel}")
    print(f"BINARY_FIXTURES: {changed} written, {unchanged} unchanged, "
          f"{len(rendered)} total in {OUT_DIR.name}/")
    return 0


def check(rendered: dict[str, bytes]) -> int:
    problems: list[str] = []
    on_disk = {p.name for p in OUT_DIR.iterdir() if p.is_file()} if OUT_DIR.is_dir() else set()
    for rel, blob in sorted(rendered.items()):
        target = OUT_DIR / rel
        if not target.is_file():
            problems.append(f"{rel}: missing")
        elif target.read_bytes() != blob:
            problems.append(f"{rel}: bytes differ from a fresh render")
    for name in sorted(on_disk - set(rendered)):
        problems.append(f"{name}: unexpected file in the fixture directory")
    for name in sorted(on_disk):
        if name not in rendered:
            continue
        if not (OUT_DIR / name).name == name:
            problems.append(f"{name}: unsafe name")
    if problems:
        for problem in problems:
            print(f"[FAIL] {problem}")
        print(f"BINARY_FIXTURES: FAIL ({len(problems)} problem(s))")
        return 1
    print(f"BINARY_FIXTURES: PASS ({len(rendered)} files match a fresh render)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="verify the fixtures without writing anything")
    args = parser.parse_args()
    rendered = render_all()
    return check(rendered) if args.check else write(rendered)


if __name__ == "__main__":
    raise SystemExit(main())
