"""A11 - the binary transport primitives: store, ranges, budgets (plan 5.3).

Everything here runs against private tmp_path fixtures built on the spot: a
manifest is written next to hand-made PDF/PNG bytes, and every integrity rule
of :mod:`examdata_integration.api.binary` is exercised - unsafe names, hash
and size drift, media and magic checks, duplicates, range parsing, entity
tags, budgets and the crop temp copy. No staged fixture, no original file and
no network is involved.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from examdata_integration.api import binary
from examdata_integration.api.binary import (
    BudgetExceeded,
    ByteRange,
    ContentLimits,
    ContentStore,
    MANIFEST_SCHEMA,
    UNSATISFIABLE,
    parse_range_header,
)

PNG = b"\x89PNG\r\n\x1a\n"
PDF = b"%PDF-"


def _png(payload: bytes = b"png-payload") -> bytes:
    return PNG + payload


def _pdf(payload: bytes = b"pdf-payload") -> bytes:
    return PDF + payload


def _entry(root: Path, name: str, blob: bytes, media: str) -> dict:
    (root / name).write_bytes(blob)
    return {"file": name, "media_type": media,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "byte_size": len(blob)}


def _write_manifest(root: Path, payload: object) -> Path:
    path = root / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _store(root: Path, payload: object, **kwargs) -> ContentStore:
    return ContentStore(root, _write_manifest(root, payload), **kwargs)


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture()
def good_payload(root: Path) -> dict:
    doc = _entry(root, "cie-qp.pdf", _pdf(), "application/pdf")
    syl = _entry(root, "syl.pdf", _pdf(b"syllabus"), "application/pdf")
    mat = _entry(root, "mat.pdf", _pdf(b"material"), "application/pdf")
    crop = _entry(root, "crop.png", _png(), "image/png")
    return {
        "schema": MANIFEST_SCHEMA,
        "documents": [{**doc, "system": "cie", "role": "qp",
                       "declared_sha256": "2" * 64}],
        "syllabuses": [{**syl, "public_id": "syl_one"}],
        "materials": [{**mat, "public_id": "mat_one"}],
        "crops": [{**crop, "system": "cie", "native_id": "1", "page": 2,
                   "declared_document_sha256": "2" * 64}],
    }


# -- loading and lookups ----------------------------------------------------- #
def test_a_valid_manifest_loads_all_four_sections(root, good_payload) -> None:
    store = _store(root, good_payload)
    assert store.problems == []
    assert store.ok is True
    assert store.media_whitelist == binary.MEDIA_WHITELIST

    doc = store.for_asset("cie", "2" * 64)
    assert doc is not None and doc.kind == "document" and doc.role == "qp"
    assert doc.sha256 == hashlib.sha256(_pdf()).hexdigest()
    assert doc.byte_size == len(_pdf())
    assert doc.declared_sha256 == "2" * 64
    assert store.for_asset("cie", "9" * 64) is None
    assert store.for_asset("edexcel", "2" * 64) is None

    syl = store.for_syllabus("syl_one")
    assert syl is not None and syl.kind == "syllabus"
    assert store.for_syllabus("nope") is None
    mat = store.for_material("mat_one")
    assert mat is not None and mat.kind == "material"
    assert store.for_material("nope") is None

    crop = store.crop_for("cie", "1")
    assert crop is not None and crop.kind == "crop"
    assert (crop.native_id, crop.page) == ("1", 2)
    assert crop.declared_sha256 == "2" * 64
    assert store.crop_for("cie", 1) is not None  # int normalizes to str
    assert store.crop_for("cie", "2") is None
    assert len(store.all_samples) == 4


def test_tags_and_extensions_are_derived_from_the_real_bytes(root, good_payload) -> None:
    store = _store(root, good_payload)
    doc = store.for_asset("cie", "2" * 64)
    assert doc.etag == f'"{doc.sha256}"'
    assert doc.extension == "pdf"
    assert store.for_syllabus("syl_one").extension == "pdf"
    assert store.crop_for("cie", "1").extension == "png"


def test_samples_and_limits_are_frozen(root, good_payload) -> None:
    store = _store(root, good_payload)
    sample = store.for_syllabus("syl_one")
    with pytest.raises(dataclasses.FrozenInstanceError):
        sample.page = 3
    with pytest.raises(dataclasses.FrozenInstanceError):
        store.limits.max_total_bytes = 1
    assert dataclasses.is_dataclass(ContentLimits())


# -- per-entry verification --------------------------------------------------- #
def test_a_missing_file_is_recorded_and_dropped(root) -> None:
    entry = {"file": "missing.pdf", "media_type": "application/pdf",
             "sha256": "0" * 64, "byte_size": 1, "system": "cie",
             "declared_sha256": "2" * 64}
    store = _store(root, {"schema": MANIFEST_SCHEMA, "documents": [entry]})
    assert not store.ok
    assert any("missing from the fixture root" in p for p in store.problems)
    assert store.for_asset("cie", "2" * 64) is None
    assert store.all_samples == ()


def test_a_hash_mismatch_is_recorded_and_dropped(root) -> None:
    blob = _pdf()
    (root / "x.pdf").write_bytes(blob)
    entry = {"file": "x.pdf", "media_type": "application/pdf",
             "sha256": "0" * 64, "byte_size": len(blob), "system": "cie",
             "declared_sha256": "2" * 64}
    store = _store(root, {"schema": MANIFEST_SCHEMA, "documents": [entry]})
    assert any("sha256 does not match" in p for p in store.problems)
    assert store.for_asset("cie", "2" * 64) is None


def test_a_size_mismatch_is_recorded_and_dropped(root) -> None:
    blob = _pdf()
    (root / "x.pdf").write_bytes(blob)
    entry = {"file": "x.pdf", "media_type": "application/pdf",
             "sha256": hashlib.sha256(blob).hexdigest(),
             "byte_size": len(blob) + 1, "system": "cie",
             "declared_sha256": "2" * 64}
    store = _store(root, {"schema": MANIFEST_SCHEMA, "documents": [entry]})
    assert any("byte_size does not match" in p for p in store.problems)


def test_a_non_whitelisted_media_type_is_rejected(root) -> None:
    entry = {"file": "x.html", "media_type": "text/html", "sha256": "0" * 64,
             "byte_size": 1, "system": "cie", "declared_sha256": "2" * 64}
    store = _store(root, {"schema": MANIFEST_SCHEMA, "documents": [entry]})
    assert any("is not whitelisted" in p for p in store.problems)


def test_magic_bytes_must_match_the_declared_media_type(root) -> None:
    entry = _entry(root, "fake.png", _pdf(), "image/png")
    store = _store(root, {"schema": MANIFEST_SCHEMA,
                          "materials": [{**entry, "public_id": "mat_fake"}]})
    assert any("magic bytes do not match" in p for p in store.problems)
    assert store.for_material("mat_fake") is None


@pytest.mark.parametrize("name", [
    "../evil.pdf", "sub/evil.pdf", "C:\\evil.pdf", "\\\\srv\\share\\x.png",
    "con.png", "NUL", "a b.pdf", "trail.", "", ".", "..",
])
def test_unsafe_file_names_are_rejected_without_reading_the_disk(root, name) -> None:
    entry = _entry(root, "probe.pdf", _pdf(), "application/pdf")
    entry["file"] = name
    store = _store(root, {"schema": MANIFEST_SCHEMA,
                          "documents": [{**entry, "system": "cie",
                                         "declared_sha256": "2" * 64}]})
    assert any("unsafe or missing file name" in p for p in store.problems)
    assert store.for_asset("cie", "2" * 64) is None


@pytest.mark.parametrize("name,accepted", [
    ("ok-file.pdf", True), ("crop-cie-1-page2.png", True),
    ("a_b.c-d.pdf", True), ("A.PNG", True), ("x2", True),
    ("", False), (None, False), (42, False), ("a b.pdf", False),
    ("trail.", False), (" lead.pdf", False), ("dir/x.pdf", False),
    ("dir\\x.pdf", False), ("con.png", False), ("nul.png", False),
    ("Com3.jpg", False), ("LPT9.x", False), ("caf\u00e9.pdf", False),
])
def test_safe_sample_name_table(name, accepted) -> None:
    assert binary._safe_sample_name(name) is accepted


@pytest.mark.parametrize("value,accepted", [
    ("0" * 64, True), ("abcdef0123456789" * 4, True),
    ("0" * 63, False), ("0" * 65, False), ("A" * 64, False),
    ("g" * 64, False), ("", False), (None, False), (42, False),
])
def test_is_sha256_table(value, accepted) -> None:
    assert binary._is_sha256(value) is accepted


@pytest.mark.parametrize("media,blob,expected", [
    ("application/pdf", PDF + b"1.7", True),
    ("image/png", PNG + b"x", True),
    ("application/pdf", PNG + b"x", False),
    ("image/png", PDF + b"1.7", False),
    ("text/html", PDF + b"1.7", False),
])
def test_magic_table(media, blob, expected) -> None:
    assert binary._magic_matches(media, blob) is expected


def test_a_document_without_a_valid_declared_hash_is_rejected(root) -> None:
    entry = _entry(root, "doc.pdf", _pdf(), "application/pdf")
    store = _store(root, {"schema": MANIFEST_SCHEMA, "documents": [
        {**entry, "system": "cie", "declared_sha256": "ZZZ"}]})
    assert any("missing or invalid declared_sha256" in p for p in store.problems)


def test_a_named_entry_without_a_public_id_is_rejected(root) -> None:
    entry = _entry(root, "syl.pdf", _pdf(), "application/pdf")
    store = _store(root, {"schema": MANIFEST_SCHEMA, "syllabuses": [entry]})
    assert any("missing public_id" in p for p in store.problems)


@pytest.mark.parametrize("page", [0, -1, "2", True, None])
def test_a_crop_with_an_invalid_page_is_rejected(root, page) -> None:
    entry = _entry(root, "crop.png", _png(), "image/png")
    store = _store(root, {"schema": MANIFEST_SCHEMA, "crops": [
        {**entry, "system": "cie", "native_id": "1", "page": page,
         "declared_document_sha256": "2" * 64}]})
    assert any("invalid page" in p for p in store.problems)
    assert store.crop_for("cie", "1") is None


def test_a_duplicate_identity_keeps_the_first_and_records_a_problem(root) -> None:
    first = _entry(root, "one.pdf", _pdf(b"one"), "application/pdf")
    second = _entry(root, "two.pdf", _pdf(b"two"), "application/pdf")
    docs = [{**first, "system": "cie", "declared_sha256": "2" * 64},
            {**second, "system": "cie", "declared_sha256": "2" * 64}]
    store = _store(root, {"schema": MANIFEST_SCHEMA, "documents": docs})
    assert any("duplicate key" in p for p in store.problems)
    kept = store.for_asset("cie", "2" * 64)
    assert kept is not None and kept.rel == "one.pdf"


def test_the_manifest_whitelist_can_only_narrow_the_staged_formats(root) -> None:
    pdf_entry = _entry(root, "doc.pdf", _pdf(), "application/pdf")
    png_entry = _entry(root, "pic.png", _png(), "image/png")
    payload = {
        "schema": MANIFEST_SCHEMA,
        "media_whitelist": ["image/png"],
        "documents": [{**pdf_entry, "system": "cie", "declared_sha256": "2" * 64}],
        "materials": [{**png_entry, "public_id": "mat_png"}],
    }
    store = _store(root, payload)
    assert store.media_whitelist == ("image/png",)
    assert any("is not whitelisted" in p for p in store.problems)
    assert store.for_material("mat_png") is not None
    assert store.for_asset("cie", "2" * 64) is None


@pytest.mark.parametrize("whitelist", [["image/jpeg"], ["image/png", 3], "image/png"])
def test_a_whitelist_beyond_the_staged_formats_is_rejected(root, whitelist) -> None:
    with pytest.raises(ValueError, match="exceeds the staged formats"):
        _store(root, {"schema": MANIFEST_SCHEMA, "media_whitelist": whitelist})


def test_a_wrong_schema_is_rejected(root) -> None:
    path = _write_manifest(root, {"schema": "other/9"})
    with pytest.raises(ValueError, match="unexpected manifest schema"):
        ContentStore(root, path)


def test_a_non_object_manifest_is_rejected(root) -> None:
    path = _write_manifest(root, ["not", "an", "object"])
    with pytest.raises(ValueError, match="must be a JSON object"):
        ContentStore(root, path)


def test_an_unreadable_manifest_is_rejected(root) -> None:
    with pytest.raises(ValueError, match="unreadable"):
        ContentStore(root, root / "absent.json")


# -- serving primitives ------------------------------------------------------- #
RANGE_CASES = [
    (None, 10, None),
    ("", 10, None),
    ("items=0-1", 10, None),
    ("bytes=", 10, None),
    ("bytes=0-1,3-4", 10, None),
    ("bytes=-", 10, None),
    ("bytes=abc", 10, None),
    ("bytes=3-x", 10, None),
    ("bytes =0-3", 10, None),
    (5, 10, None),
    ("bytes=-0", 10, UNSATISFIABLE),
    ("bytes=10-", 10, UNSATISFIABLE),
    ("bytes=12-20", 10, UNSATISFIABLE),
    ("bytes=0-0", 10, ByteRange(0, 0)),
    ("bytes=0-3", 10, ByteRange(0, 3)),
    ("bytes= 0-3", 10, ByteRange(0, 3)),
    ("BYTES=0-3", 10, ByteRange(0, 3)),
    ("bytes=7-", 10, ByteRange(7, 9)),
    ("bytes=2-99", 10, ByteRange(2, 9)),
    ("bytes=-4", 10, ByteRange(6, 9)),
    ("bytes=-10", 10, ByteRange(0, 9)),
    ("bytes=-20", 10, ByteRange(0, 9)),
    ("bytes=5-3", 10, None),
    ("bytes=0-", 0, UNSATISFIABLE),
    ("bytes=-3", 0, UNSATISFIABLE),
    ("bytes=0-3", 0, UNSATISFIABLE),
]


@pytest.mark.parametrize("value,size,expected", RANGE_CASES)
def test_parse_range_header_table(value, size, expected) -> None:
    assert parse_range_header(value, size) == expected


def test_etag_is_the_strong_hash_tag() -> None:
    assert binary.etag_for("a" * 64) == f'"{"a" * 64}"'


ETAG = '"' + "a" * 64 + '"'


@pytest.mark.parametrize("value,expected", [
    (None, False), ("", False), ("*", True), (ETAG, True),
    (f"W/{ETAG}", True), (f'"other", {ETAG}', True),
    (f"{ETAG}, \"other\"", True), (f"  {ETAG}  ", True),
    ('"other"', False), ("W/\"other\"", False), ("a" * 64, False),
])
def test_if_none_match_table(value, expected) -> None:
    assert binary.if_none_match_matches(value, ETAG) is expected


def test_iter_sample_streams_the_whole_file(root, good_payload) -> None:
    store = _store(root, good_payload)
    sample = store.for_syllabus("syl_one")
    blob = (root / "syl.pdf").read_bytes()
    assert b"".join(binary.iter_sample(sample)) == blob
    assert b"".join(binary.iter_sample(sample, chunk_size=2)) == blob


def test_iter_range_yields_only_the_span(root, good_payload) -> None:
    store = _store(root, good_payload)
    sample = store.for_syllabus("syl_one")
    blob = sample.path.read_bytes()
    assert b"".join(binary.iter_range(sample, 2, 5)) == blob[2:6]
    assert b"".join(binary.iter_range(sample, 1, 1)) == blob[1:2]
    assert b"".join(binary.iter_range(sample, 0, len(blob) - 1)) == blob


def test_iter_crop_copy_copies_then_removes_its_temp_directory(
        root, good_payload, tmp_path) -> None:
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    store = _store(root, good_payload, temp_root=temp_root)
    sample = store.crop_for("cie", "1")
    blob = sample.path.read_bytes()
    stream = binary.iter_crop_copy(sample, temp_root=temp_root)
    first = next(stream)
    assert first
    alive = [p for p in temp_root.iterdir() if p.name.startswith("crop-")]
    assert len(alive) == 1
    assert (alive[0] / sample.rel).read_bytes() == blob
    stream.close()
    assert [p for p in temp_root.iterdir() if p.name.startswith("crop-")] == []


def test_iter_crop_copy_full_stream_and_byte_range(root, good_payload, tmp_path) -> None:
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    store = _store(root, good_payload, temp_root=temp_root)
    sample = store.crop_for("cie", "1")
    blob = sample.path.read_bytes()
    assert b"".join(binary.iter_crop_copy(sample, temp_root=temp_root)) == blob
    got = b"".join(binary.iter_crop_copy(
        sample, temp_root=temp_root, byte_range=ByteRange(2, 5)))
    assert got == blob[2:6]
    assert [p for p in temp_root.iterdir() if p.name.startswith("crop-")] == []


def test_sample_bytes_detects_drift_after_load(root, good_payload) -> None:
    store = _store(root, good_payload)
    sample = store.for_syllabus("syl_one")
    (root / "syl.pdf").write_bytes(_pdf(b"tampered"))
    with pytest.raises(binary.ContentDrift, match="drifted"):
        store.sample_bytes(sample)


def test_sample_bytes_reports_a_deleted_file_as_drift(root, good_payload) -> None:
    store = _store(root, good_payload)
    sample = store.for_syllabus("syl_one")
    (root / "syl.pdf").unlink()
    with pytest.raises(binary.ContentDrift, match="unreadable"):
        store.sample_bytes(sample)


def test_enforce_budget_maps_to_the_two_413_codes(root, good_payload) -> None:
    store = _store(root, good_payload,
                   limits=ContentLimits(max_total_bytes=4, max_crop_bytes=2))
    doc = store.for_syllabus("syl_one")
    assert doc.byte_size > 4
    with pytest.raises(BudgetExceeded) as exc_info:
        store.enforce_budget(doc)
    assert exc_info.value.code == "response_budget_exceeded"
    assert (exc_info.value.limit, exc_info.value.actual) == (4, doc.byte_size)
    crop = store.crop_for("cie", "1")
    with pytest.raises(BudgetExceeded) as crop_info:
        store.enforce_budget(crop, crop=True)
    assert crop_info.value.code == "crop_budget_exceeded"
    assert (crop_info.value.limit, crop_info.value.actual) == (2, crop.byte_size)
    big = _store(root, good_payload)
    big.enforce_budget(big.for_syllabus("syl_one"))  # within the staged defaults
