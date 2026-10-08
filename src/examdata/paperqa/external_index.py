"""Immutable external CIE question locations, validated against exact PDFs."""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

import pymupdf
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Identity(StrictModel):
    subject: str = Field(pattern=r"^\d{4}$")
    year: int = Field(ge=2000, le=2099, strict=True)
    season: Literal["Mar", "Jun", "Nov"]
    paper: str = Field(pattern=r"^\d{1,2}$")


class Document(StrictModel):
    role: Literal["qp", "ms"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Region(StrictModel):
    page: int = Field(ge=1, strict=True)
    bbox: tuple[float, float, float, float]


class Question(StrictModel):
    question: str = Field(pattern=r"^[1-9]\d{0,2}(?:\([a-z]\)(?:\([ivx]+\))?)?$")
    parent: str | None = None
    text: str = Field(max_length=50000)
    marks: int | None = Field(default=None, ge=0, le=1000, strict=True)
    qp: list[Region] = Field(min_length=1, max_length=25)
    ms: list[Region] = Field(default_factory=list, max_length=25)
    uncertain: bool = True
    notes: str = Field(default="", max_length=2000)


class ExternalIndex(StrictModel):
    schema_version: Literal["1"] = "1"
    board: Literal["cie"] = "cie"
    identity: Identity
    coordinate_system: Literal["unrotated_pdf_points_top_left"]
    page_base: Literal[1]
    documents: list[Document] = Field(min_length=1, max_length=2)
    questions: list[Question] = Field(min_length=1, max_length=1000)


def import_index(manifest: Path, qp: Path, ms: Path | None, destination: Path) -> dict:
    if manifest.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Index exceeds 16 MiB")
    model = ExternalIndex.model_validate_json(manifest.read_bytes())
    documents = {d.role: d for d in model.documents}
    if len(documents) != len(model.documents) or "qp" not in documents:
        raise ValueError("Require one qp and at most one ms document")
    if (ms is not None) != ("ms" in documents):
        raise ValueError("Manifest ms and --ms must agree")
    names = {q.question for q in model.questions}
    if len(names) != len(model.questions):
        raise ValueError("Duplicate question number")
    for q in model.questions:
        parent = q.question.rsplit("(", 1)[0] if "(" in q.question else None
        if q.parent != parent or (parent is not None and parent not in names):
            raise ValueError(f"Invalid parent for {q.question}")
        if q.ms and "ms" not in documents:
            raise ValueError("MS regions require an MS PDF")
    for role, path in (("qp", qp), ("ms", ms)):
        if path is None:
            continue
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("PDF exceeds 64 MiB")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != documents[role].sha256:
            raise ValueError(f"{role} PDF sha256 mismatch")
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if not 1 <= len(pdf) <= 400:
                raise ValueError("PDF page limit exceeded")
            for question in model.questions:
                for region in getattr(question, role):
                    if region.page > len(pdf):
                        raise ValueError("Page outside PDF")
                    page = pdf[region.page - 1]
                    bounds = page.rect * page.derotation_matrix
                    x0, y0, x1, y1 = region.bbox
                    if not (bounds.x0 <= x0 < x1 <= bounds.x1
                            and bounds.y0 <= y0 < y1 <= bounds.y1):
                        raise ValueError("BBox outside unrotated PDF")
    payload = model.model_dump(mode="json")
    payload.update(method="external_ai", reviewed=False)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    directory = destination / "question_indexes" / "cie"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{documents['qp'].sha256}.json"
    with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(encoded)
    try:
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.is_symlink() or target.read_bytes() != encoded:
                raise ValueError("Different index already exists; explicit review required")
    finally:
        temporary.unlink(missing_ok=True)
    return {"sha256": documents["qp"].sha256, "questions": len(model.questions),
            "reviewed": False, "path": str(target)}


def read_index(destination: Path, sha256: str, question: str | None = None) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise ValueError("Invalid PDF sha256")
    directory = (destination / "question_indexes" / "cie").resolve()
    target = directory / f"{sha256}.json"
    if target.is_symlink() or target.resolve().parent != directory:
        raise ValueError("Unsafe index path")
    if target.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Index exceeds 16 MiB")
    payload = json.loads(target.read_bytes())
    if question is not None:
        rows = [q for q in payload["questions"] if q["question"] == question]
        if not rows:
            raise FileNotFoundError("Question not indexed")
        payload["questions"] = rows
    return payload


def fetch_question(destination: Path, sha256: str, question: str, mode="qp", *, fetcher=None):
    """Re-fetch exact original PDFs and render saved regions in memory only."""
    from .api import query
    from .errors import AmbiguousDocument, InvalidRequest, NotFound
    from .models import OutputFile
    if mode not in {"qp", "ms", "both"}:
        raise InvalidRequest("mode must be qp, ms or both")
    payload = read_index(destination, sha256, question)
    entry = payload["questions"][0]
    roles = {"qp", "ms"} if mode == "both" else {mode}
    expected = {d["role"]: d["sha256"] for d in payload["documents"]}
    if any(role not in expected or not entry[role] for role in roles):
        raise NotFound("Requested question or answer regions are not indexed")
    identity = payload["identity"]
    result = query("cie", identity["subject"], identity["year"], identity["season"],
                   identity["paper"], mode=mode, fetcher=fetcher)
    originals = {file.role: file for file in result.files}
    if any(role not in originals or originals[role].sha256 != expected[role] for role in roles):
        raise AmbiguousDocument("Original PDF changed; re-parse before using stored locations")
    files = []
    for role in sorted(roles):
        with pymupdf.open(stream=originals[role].data, filetype="pdf") as pdf:
            for number, region in enumerate(entry[role], 1):
                page = pdf[region["page"] - 1]
                rect = pymupdf.Rect(region["bbox"])
                # Analysis coordinates are unrotated; rendering uses rotated page space.
                clip = rect * page.rotation_matrix
                import math
                result.budget.charge(math.ceil(clip.width * 1.5) * math.ceil(clip.height * 1.5) * 4,
                                     "indexed question raster")
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), clip=clip, alpha=False)
                png = pixmap.tobytes("png")
                del pixmap
                result.budget.charge(len(png), "indexed question PNG")
                files.append(OutputFile(f"{sha256[:12]}-{role}-{number}.png", png, "image/png", role,
                                        page=region["page"], bbox=tuple(region["bbox"])))
    result.budget.check_files(len(files))
    result.files = files
    return result, {"question": question, "index_sha256": sha256,
                    "source_documents": payload["documents"], "reviewed": False,
                    "uncertain": entry["uncertain"]}
