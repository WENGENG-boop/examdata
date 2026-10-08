"""A11 - integrity of the staged synthetic binary fixtures.

The transport tests prove the routes serve what the manifest says; this
module proves the manifest, the provenance file and the bytes on disk agree
with each other, that the declared identities are the frozen provider-side
placeholders (never real document hashes), and that the generator's own
`--check` mode still passes on the staged fixtures.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from examdata_integration.api import binary
from examdata_integration.api.dataset import FIXTURE_ROOT, STAGING_ROOT

WORKSPACE = Path(__file__).resolve().parents[2]
BINARY_DIR = FIXTURE_ROOT / "binary"
MANIFEST_PATH = BINARY_DIR / "manifest.json"
PROVENANCE_PATH = BINARY_DIR / "PROVENANCE.json"
SECTIONS = ("documents", "syllabuses", "materials", "crops")
PDF_PREFIX = b"%PDF-"
PNG_PREFIX = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def provenance() -> dict:
    return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))


def test_the_binary_directory_holds_exactly_the_manifested_files(manifest) -> None:
    listed = {entry["file"] for section in SECTIONS for entry in manifest[section]}
    assert len(listed) == 11
    on_disk = {p.name for p in BINARY_DIR.iterdir() if p.is_file()}
    assert on_disk == listed | {"manifest.json", "PROVENANCE.json"}
    assert len(on_disk) == 13


def test_every_manifest_entry_matches_the_bytes_on_disk(manifest) -> None:
    for section in SECTIONS:
        for entry in manifest[section]:
            blob = (BINARY_DIR / entry["file"]).read_bytes()
            assert hashlib.sha256(blob).hexdigest() == entry["sha256"], entry["file"]
            assert len(blob) == entry["byte_size"], entry["file"]
            assert entry["media_type"] in manifest["media_whitelist"], entry["file"]
            prefix = PDF_PREFIX if entry["media_type"] == "application/pdf" else PNG_PREFIX
            assert blob.startswith(prefix), entry["file"]


def test_provenance_records_every_file_with_matching_hashes(provenance) -> None:
    assert provenance["schema"] == "fixture-provenance/1"
    assert provenance["summary"] == {"entries": 12, "synthetic": 12}
    assert len(provenance["entries"]) == 12
    assert STAGING_ROOT == WORKSPACE / "integration-staging"
    for entry in provenance["entries"]:
        path = WORKSPACE / entry["path"]
        assert path.is_file(), entry["path"]
        blob = path.read_bytes()
        assert hashlib.sha256(blob).hexdigest() == entry["sha256"], entry["path"]
        assert len(blob) == entry["bytes"], entry["path"]
        assert entry["kind"] == "synthetic"
        assert entry["label"] == "synthetic_fixture"
    covered = {entry["path"] for entry in provenance["entries"]}
    rel = {f"integration-staging/fixtures/synthetic/binary/{p.name}"
           for p in BINARY_DIR.iterdir() if p.is_file()}
    assert covered == rel - {"integration-staging/fixtures/synthetic/binary/PROVENANCE.json"}


def test_declared_identities_are_the_frozen_placeholders(manifest) -> None:
    documents = {(entry["system"], entry["role"]): entry["declared_sha256"]
                 for entry in manifest["documents"]}
    assert documents == {
        ("cie", "qp"): "2" * 64,
        ("cie", "ms"): "3" * 64,
        ("cie", "graph"): "4" * 64,
        ("edexcel", "qp"): "5" * 64,
        ("edexcel", "ms"): "6" * 64,
        ("ielts", "diagram"): "0" * 64,
    }
    crops = [(entry["system"], entry["native_id"], entry["page"],
              entry["declared_document_sha256"]) for entry in manifest["crops"]]
    assert crops == [
        ("cie", "1", 2, "2" * 64),
        ("cie", "2", 3, "2" * 64),
        ("cie", "3", 4, "2" * 64),
    ]
    for value in list(documents.values()) + [crop[3] for crop in crops]:
        assert value == value[0] * 64  # repeated-digit placeholder, never a real hash


def test_the_store_loads_the_staged_fixtures_without_problems() -> None:
    store = binary.ContentStore(BINARY_DIR, MANIFEST_PATH)
    assert store.problems == []
    assert store.ok is True
    assert store.for_asset("cie", "2" * 64) is not None
    assert store.for_asset("ielts", "0" * 64) is not None
    assert store.for_syllabus("syl_synthetic_cie_0580") is not None
    assert store.for_syllabus("syl_synthetic_ielts_book") is None
    assert store.for_material("mat_synthetic_cie_ins") is not None
    assert store.for_material("mat_synthetic_edexcel_gt") is None
    assert store.crop_for("cie", "1") is not None
    assert store.crop_for("cie", "4") is None
    assert len(store.all_samples) == 11


def test_the_fixture_generator_check_passes() -> None:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "tools/build_binary_fixtures.py", "--check"],
        cwd=STAGING_ROOT, capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=120)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "BINARY_FIXTURES: PASS (13 files match a fresh render)" in result.stdout
    assert "[FAIL]" not in result.stdout
