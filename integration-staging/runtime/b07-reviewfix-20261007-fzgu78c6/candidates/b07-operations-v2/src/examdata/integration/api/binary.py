"""Staged binary transport primitives (plan 5.3): store, ranges, budgets.

The five binary routes (syllabus/material/asset content and question crop)
serve small, immutable, synthetic fixture samples. This module owns everything
that does not need the web framework: the manifest-backed :class:`ContentStore`,
byte-range parsing, entity tags and the response budgets; ``app.py`` wires it
to routes and maps the failures onto the plan's statuses.

Integrity rules:

* every sample is verified at load time - file presence, real sha256, byte
  size, media whitelist, magic bytes matching the declared media type - and a
  failing entry is dropped into :attr:`ContentStore.problems`, never served;
* reads re-verify the sha256 and raise :class:`ContentDrift` on mismatch;
* the manifest keeps the fixture-side *declared* identity (the placeholder
  hash the frozen provider fixtures declare) apart from the real hash of the
  synthetic bytes, so nothing fabricated is ever promoted to verified.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

MANIFEST_SCHEMA = "examdata.integration.content-manifest/1"

#: The staged transport serves these formats only; a manifest that claims
#: more (or an entry that declares one of them) is rejected.
MEDIA_WHITELIST: tuple[str, ...] = ("application/pdf", "image/png")
MEDIA_EXTENSIONS: dict[str, str] = {"application/pdf": "pdf", "image/png": "png"}

DEFAULT_MAX_TOTAL_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_CROP_BYTES = 2 * 1024 * 1024
CHUNK_SIZE = 64 * 1024

UNSATISFIABLE = "unsatisfiable"

_PDF_MAGIC = b"%PDF-"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RESERVED_STEMS = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{n}" for n in range(1, 10)}
    | {f"LPT{n}" for n in range(1, 10)}
)


def _safe_sample_name(name: object) -> bool:
    """True when *name* is a single, safe file name - never a path.

    Rejects path separators, drive letters, UNC prefixes, URLs, NUL, the
    `.`/`..` segments and the Windows reserved device names (with or without
    an extension), so a manifest can never address a file outside the root.
    """
    if not isinstance(name, str) or not name:
        return False
    if not _SAFE_NAME_RE.fullmatch(name):
        return False
    if name in {".", ".."} or name != name.strip() or name.endswith("."):
        return False
    if name.split(".", 1)[0].upper() in _RESERVED_STEMS:
        return False
    return True


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def _magic_matches(media_type: str, blob: bytes) -> bool:
    if media_type == "application/pdf":
        return blob.startswith(_PDF_MAGIC)
    if media_type == "image/png":
        return blob.startswith(_PNG_MAGIC)
    return False


@dataclass(frozen=True)
class ContentLimits:
    """Response budgets for the binary transport (plan 5.2: 413)."""

    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    max_crop_bytes: int = DEFAULT_MAX_CROP_BYTES


@dataclass(frozen=True)
class Sample:
    """One verified manifest entry plus its file location."""

    kind: str  # "document" | "syllabus" | "material" | "crop"
    rel: str
    path: Path
    media_type: str
    byte_size: int
    sha256: str  # real hash of the bytes on disk
    declared_sha256: str | None = None  # fixture-side identity, never real
    system: str | None = None
    role: str | None = None
    public_id: str | None = None
    native_id: str | None = None
    page: int | None = None

    @property
    def etag(self) -> str:
        return etag_for(self.sha256)

    @property
    def extension(self) -> str:
        return MEDIA_EXTENSIONS[self.media_type]


class ContentDrift(RuntimeError):
    """The bytes on disk no longer match the verified manifest entry."""


class BudgetExceeded(Exception):
    """A sample exceeds its request-time response budget (plan 5.2: 413)."""

    def __init__(self, code: str, *, limit: int, actual: int) -> None:
        super().__init__(f"{code}: {actual} bytes exceed the {limit}-byte budget")
        self.code = code
        self.limit = limit
        self.actual = actual


@dataclass(frozen=True)
class ByteRange:
    """A satisfiable single byte range; both ends inclusive."""

    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_range_header(value: object, size: int) -> ByteRange | None | str:
    """Parse a single-range ``Range`` header value.

    Returns a :class:`ByteRange` for a satisfiable range, ``None`` when the
    header must be ignored (absent, empty, another unit, multi-range or
    malformed - the response stays a 200), or :data:`UNSATISFIABLE` when the
    range names no octets of a ``size``-byte entity (the response becomes 416).
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or not text.lower().startswith("bytes="):
        return None
    spec = text[len("bytes="):].strip()
    if not spec or "," in spec:
        return None
    if spec.startswith("-"):
        digits = spec[1:]
        if not digits.isdigit():
            return None
        length = int(digits)
        if size <= 0 or length == 0:
            return UNSATISFIABLE
        if length >= size:
            return ByteRange(0, size - 1)
        return ByteRange(size - length, size - 1)
    start_text, dash, end_text = spec.partition("-")
    if not dash or not start_text.isdigit():
        return None
    start = int(start_text)
    if start >= size:
        return UNSATISFIABLE
    if end_text == "":
        return ByteRange(start, size - 1)
    if not end_text.isdigit():
        return None
    end = int(end_text)
    if end < start:
        return None
    return ByteRange(start, min(end, size - 1))


def etag_for(sha256: str) -> str:
    """The strong entity tag for a sample: its real content hash."""
    return f'"{sha256}"'


def if_none_match_matches(header_value: object, etag: str) -> bool:
    """Weak-comparison ``If-None-Match`` check for a single entity tag."""
    if header_value is None:
        return False
    text = str(header_value).strip()
    if not text:
        return False
    if text == "*":
        return True
    for candidate in text.split(","):
        candidate = candidate.strip()
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == etag:
            return True
    return False


class ContentStore:
    """The verified, manifest-backed fixture content store.

    Construction loads and verifies every entry; failures are recorded in
    :attr:`problems` and the entry is dropped, so a partially valid manifest
    degrades to fewer servable samples instead of serving bad bytes.
    """

    def __init__(self, root: Path, manifest_path: Path, *,
                 limits: ContentLimits | None = None,
                 temp_root: Path | None = None) -> None:
        self.root = Path(root)
        self.manifest_path = Path(manifest_path)
        self.limits = limits if limits is not None else ContentLimits()
        self.temp_root = (Path(temp_root) if temp_root is not None
                          else Path(tempfile.gettempdir()))
        self.problems: list[str] = []
        self._documents: dict[tuple[str, str], Sample] = {}
        self._syllabuses: dict[str, Sample] = {}
        self._materials: dict[str, Sample] = {}
        self._crops: dict[tuple[str, str], Sample] = {}
        self._samples: dict[str, Sample] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # loading
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"content manifest is unreadable: {exc}") from exc
        if not isinstance(manifest, dict):
            raise ValueError("content manifest must be a JSON object")
        if manifest.get("schema") != MANIFEST_SCHEMA:
            raise ValueError(f"unexpected manifest schema {manifest.get('schema')!r}")
        declared = manifest.get("media_whitelist")
        if declared is not None:
            if (not isinstance(declared, list)
                    or not all(isinstance(item, str) for item in declared)
                    or not set(declared) <= set(MEDIA_WHITELIST)):
                raise ValueError("manifest media_whitelist exceeds the staged formats")
            self.media_whitelist: tuple[str, ...] = tuple(declared)
        else:
            self.media_whitelist = MEDIA_WHITELIST

        for position, entry in enumerate(manifest.get("documents") or []):
            self._load_document(entry, position)
        for position, entry in enumerate(manifest.get("syllabuses") or []):
            self._load_named("syllabus", entry, position)
        for position, entry in enumerate(manifest.get("materials") or []):
            self._load_named("material", entry, position)
        for position, entry in enumerate(manifest.get("crops") or []):
            self._load_crop(entry, position)

    def _checked(self, section: str, entry: object, position: int
                 ) -> tuple[str, Path, str, int, str] | None:
        """The shared per-entry verification; ``None`` records a problem."""
        label = f"{section}[{position}]"
        if not isinstance(entry, dict):
            self.problems.append(f"{label}: entry is not an object")
            return None
        rel = entry.get("file")
        if not _safe_sample_name(rel):
            self.problems.append(f"{label}: unsafe or missing file name {rel!r}")
            return None
        media = entry.get("media_type")
        if media not in self.media_whitelist:
            self.problems.append(f"{label} {rel}: media_type {media!r} is not whitelisted")
            return None
        path = self.root / rel
        if not path.is_file():
            self.problems.append(f"{label} {rel}: file is missing from the fixture root")
            return None
        blob = path.read_bytes()
        digest = hashlib.sha256(blob).hexdigest()
        if entry.get("sha256") != digest:
            self.problems.append(f"{label} {rel}: sha256 does not match the bytes on disk")
            return None
        if entry.get("byte_size") != len(blob):
            self.problems.append(f"{label} {rel}: byte_size does not match the bytes on disk")
            return None
        if not _magic_matches(media, blob):
            self.problems.append(f"{label} {rel}: magic bytes do not match media_type {media!r}")
            return None
        return rel, path, media, len(blob), digest

    def _register(self, sample: Sample, key: object, target: dict) -> None:
        if key in target:
            self.problems.append(f"{sample.kind} {sample.rel}: duplicate key {key!r}")
            return
        target[key] = sample
        self._samples.setdefault(sample.rel, sample)

    def _load_document(self, entry: object, position: int) -> None:
        checked = self._checked("documents", entry, position)
        if checked is None:
            return
        rel, path, media, size, digest = checked
        system = entry.get("system")
        declared = entry.get("declared_sha256")
        if not isinstance(system, str) or not system:
            self.problems.append(f"documents {rel}: missing system")
            return
        if not _is_sha256(declared):
            self.problems.append(f"documents {rel}: missing or invalid declared_sha256")
            return
        sample = Sample(kind="document", rel=rel, path=path, media_type=media,
                        byte_size=size, sha256=digest, declared_sha256=declared,
                        system=system, role=entry.get("role"))
        self._register(sample, (system, declared), self._documents)

    def _load_named(self, kind: str, entry: object, position: int) -> None:
        checked = self._checked(kind + "s", entry, position)
        if checked is None:
            return
        rel, path, media, size, digest = checked
        public_id = entry.get("public_id")
        if not isinstance(public_id, str) or not public_id:
            self.problems.append(f"{kind}s {rel}: missing public_id")
            return
        sample = Sample(kind=kind, rel=rel, path=path, media_type=media,
                        byte_size=size, sha256=digest, public_id=public_id)
        target = self._syllabuses if kind == "syllabus" else self._materials
        self._register(sample, public_id, target)

    def _load_crop(self, entry: object, position: int) -> None:
        checked = self._checked("crops", entry, position)
        if checked is None:
            return
        rel, path, media, size, digest = checked
        system = entry.get("system")
        native_id = entry.get("native_id")
        page = entry.get("page")
        declared = entry.get("declared_document_sha256")
        if not isinstance(system, str) or not system:
            self.problems.append(f"crops {rel}: missing system")
            return
        if not isinstance(native_id, str) or not native_id:
            self.problems.append(f"crops {rel}: missing native_id")
            return
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            self.problems.append(f"crops {rel}: invalid page {page!r}")
            return
        if not _is_sha256(declared):
            self.problems.append(f"crops {rel}: missing or invalid declared_document_sha256")
            return
        sample = Sample(kind="crop", rel=rel, path=path, media_type=media,
                        byte_size=size, sha256=digest, declared_sha256=declared,
                        system=system, native_id=native_id, page=page)
        self._register(sample, (system, native_id), self._crops)

    # ------------------------------------------------------------------ #
    # lookups
    # ------------------------------------------------------------------ #
    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def all_samples(self) -> tuple[Sample, ...]:
        return tuple(self._samples.values())

    def for_asset(self, system: str, sha256: str) -> Sample | None:
        """The content sample for an asset identity (system, declared hash)."""
        return self._documents.get((system, sha256))

    def for_syllabus(self, public_id: str) -> Sample | None:
        return self._syllabuses.get(public_id)

    def for_material(self, public_id: str) -> Sample | None:
        return self._materials.get(public_id)

    def crop_for(self, system: str, native_id: object) -> Sample | None:
        return self._crops.get((system, str(native_id)))

    # ------------------------------------------------------------------ #
    # serving
    # ------------------------------------------------------------------ #
    def sample_bytes(self, sample: Sample) -> bytes:
        """Re-read and re-verify a sample; :class:`ContentDrift` on mismatch."""
        try:
            blob = sample.path.read_bytes()
        except OSError as exc:
            raise ContentDrift(f"{sample.rel}: unreadable ({exc.__class__.__name__})") from exc
        if hashlib.sha256(blob).hexdigest() != sample.sha256:
            raise ContentDrift(f"{sample.rel}: sha256 drifted from the manifest")
        return blob

    def enforce_budget(self, sample: Sample, *, crop: bool = False) -> None:
        """Apply the request-time response budget (plan 5.2: 413)."""
        limit = self.limits.max_crop_bytes if crop else self.limits.max_total_bytes
        if sample.byte_size > limit:
            code = "crop_budget_exceeded" if crop else "response_budget_exceeded"
            raise BudgetExceeded(code, limit=limit, actual=sample.byte_size)


def iter_sample(sample: Sample, *, chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """Stream a verified sample from its fixture file, chunk by chunk."""
    with open(sample.path, "rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            yield block


def iter_range(sample: Sample, start: int, end: int, *,
               chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """Stream the inclusive byte range ``[start, end]`` of a verified sample.

    Only the requested span is read; ``start``/``end`` are expected to be
    already validated against the sample size by
    :func:`parse_range_header`.
    """
    remaining = end - start + 1
    with open(sample.path, "rb") as handle:
        handle.seek(start)
        while remaining > 0:
            block = handle.read(min(chunk_size, remaining))
            if not block:
                break
            remaining -= len(block)
            yield block


def iter_crop_copy(sample: Sample, *, temp_root: Path,
                   chunk_size: int = CHUNK_SIZE,
                   byte_range: ByteRange | None = None) -> Iterator[bytes]:
    """Stream a crop through a private temp copy, deleting it afterwards.

    The staged pipeline materialises the crop artifact first (in Phase A the
    fixture *is* the crop) so a later real implementation can swap in an
    actual crop step; the temp directory is removed when the response
    generator finishes, including a client disconnect (early ``close()``).

    When ``byte_range`` is given, only that inclusive span of the copied
    artifact is yielded (Range requests on crop responses).
    """
    directory = Path(tempfile.mkdtemp(prefix="crop-", dir=str(temp_root)))
    try:
        target = directory / sample.rel
        shutil.copyfile(sample.path, target)
        with open(target, "rb") as handle:
            remaining: int | None = None
            if byte_range is not None:
                handle.seek(byte_range.start)
                remaining = byte_range.length
            while True:
                if remaining is not None and remaining <= 0:
                    break
                limit = chunk_size if remaining is None else min(chunk_size, remaining)
                block = handle.read(limit)
                if not block:
                    break
                if remaining is not None:
                    remaining -= len(block)
                yield block
    finally:
        shutil.rmtree(directory, ignore_errors=True)


__all__ = [
    "MANIFEST_SCHEMA",
    "MEDIA_WHITELIST",
    "MEDIA_EXTENSIONS",
    "DEFAULT_MAX_TOTAL_BYTES",
    "DEFAULT_MAX_CROP_BYTES",
    "CHUNK_SIZE",
    "UNSATISFIABLE",
    "ContentLimits",
    "Sample",
    "ContentDrift",
    "BudgetExceeded",
    "ByteRange",
    "parse_range_header",
    "etag_for",
    "if_none_match_matches",
    "ContentStore",
    "iter_sample",
    "iter_range",
    "iter_crop_copy",
]
