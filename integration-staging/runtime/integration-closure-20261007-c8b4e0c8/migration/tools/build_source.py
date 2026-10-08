#!/usr/bin/env python
"""Build one private synthetic SOURCE store for the W5 migration rehearsal.

The store mimics the *documented staged shapes* of the data roots (integration
guide section 6, A09 store decision, A01 data-root inventory) while keeping the
authorities separate - nothing is merged into one mutable file:

======================  =================  ====================================
shape                   owner / authority   representation
======================  =================  ====================================
raw source ownership    source systems      ``raw/<system>/**.json`` + ``ownership.json``
aggregate index         integration         ``index/aggregate-index.db`` (SQLite) and its
                                            derived read-only mirror ``index/aggregate-index.json``
revisions + pointer     integration         built later by ``migrate.py`` in the destination
assets                  source systems      ``assets/<system>/<name>`` (content claim = sha256)
caches                  source systems      ``caches/<system>/*.json`` (rebuildable)
manual decisions        source stores       ``decisions/manual-decisions.json`` (never overwritten)
provenance              integration/source  ``provenance/PROVENANCE.json``
observed checkpoints    source runners      ``observed/run-checkpoint.json`` (read-only, not migrated)
======================  =================  ====================================

Everything here is invented synthetic content with invented native ids and
hashes.  No original tree, database, service or network is touched.  The SQLite
aggregate index is a *modelled* shape: the candidate's A09 decision defers the
real SQLite catalog index, so the rehearsal models the documented legacy-store
shape explicitly (this is stated in the W5 report).

``--variant defects`` plants exactly these defects on top of the clean store,
so the migration/reconcile steps have something real to refuse and to flag:

* ``assets/ielts/audio-syn-ielts-1.mp3`` - file tampered, claim keeps the
  intended hash (``asset_hash_mismatch``);
* ``assets/toefl/diagram-syn-toefl-1.png`` - file deleted, claim kept
  (``missing``);
* ``cie-q-bad-identity`` - question whose identity keys are missing
  (``invalid_identity``, fatal to a publication);
* ``toefl-q2-missing-raw`` - entity whose ``raw_path``/``document_path`` point
  at a payload that does not exist (``missing``, non-fatal) and whose
  ``in_container`` reference points at a non-existent ``container_zzzz...``
  public ID (``unresolved_identity``, fatal to a publication).

Quality claims are consistent with synthetic evidence only: questions and
answers stay ``unverified`` (``source_verified`` needs authoritative evidence,
which ``synthetic_fixture`` is deliberately not), and ``cie-ans-q1`` claims
``manual_adjudicated`` because the preserved manual decision in
``decisions/manual-decisions.json`` backs it - ``migrate.py`` surfaces that
decision through the entry's ``lineage``, exactly the rule the candidate's
trust contract enforces.

Explicit identity unknowns appear only where the candidate documents them:

* ``parent_native_id`` of the three root questions is persisted as the
  ``__unknown__`` token - a *known absence* (not applicable), which the
  migration decodes to the ``UNKNOWN`` sentinel; this exercises the token
  round-trip through publish and read-back;
* ``ielts-q-unplaced`` carries ``__unknown__`` in ``container_native_identity``
  - an unresolved value for an otherwise identified entry.  It stays in the
  catalog with a visible non-fatal ``identity_unresolved`` problem, never
  dropped and never guessed.

Usage:
    python build_source.py --root <dir> [--variant clean|defects] [--force]

``--force`` deletes the target only when it carries this tool's own ownership
marker, so a foreign or already-migrated tree can never be deleted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w5_common as w5  # noqa: E402

MARKER_NAME = ".w5_source_root.json"
MARKER_SCHEMA = "w5.source-root-marker/1"
OWNERSHIP_SCHEMA = "w5.source-ownership/1"

SYSTEMS = ("cie", "ielts", "toefl")

#: The persisted encoding of the explicit-unknown sentinel, identical to
#: ``catalog.model.UNKNOWN_TOKEN``.  A source store persists the token; the
#: migration decodes it back to the sentinel before deriving public IDs.
UNKNOWN_TOKEN = "__unknown__"


def blob(seed: str, size: int) -> bytes:
    """Deterministic synthetic payload bytes (never real content)."""
    out = bytearray()
    counter = 0
    while len(out) < size:
        out.extend(hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest())
        counter += 1
    return bytes(out[:size])


def png_bytes(seed: str) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + blob(f"png:{seed}", 496)


def mp3_bytes(seed: str) -> bytes:
    return b"ID3\x04\x00\x00" + blob(f"mp3:{seed}", 512)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_json(path: Path, payload: Any) -> None:
    w5.write_json(path, payload)


def build(root: Path, variant: str) -> dict[str, Any]:
    api = w5.catalog_api()
    canonical = api["canonical"]
    decode_unknown = api["decode_unknown"]
    EntityKind = api["EntityKind"]
    root.mkdir(parents=True, exist_ok=True)
    # Ownership marker first: even a partially built tree (a failed run) stays
    # provably ours, so ``--force`` can clean it up while foreign trees remain
    # untouchable.
    _write_json(root / MARKER_NAME, {
        "schema": MARKER_SCHEMA,
        "created_by": "migration/tools/build_source.py",
        "variant": variant,
        "note": "ownership marker; --force may delete this root only when this file matches",
    })

    # ------------------------------------------------------------------ raw --
    cie_index = {
        "schema": "source-index/1",
        "system": "cie",
        "qualification": "igcse",
        "native_code": "0580",
        "papers": [{"native_id": "0580/41", "session": "June", "year": 2026,
                    "questions": [{"native_id": "1", "text": "synthetic cie question 1"},
                                  {"native_id": "2", "text": "synthetic cie question 2"}]}],
        "synthetic": True,
    }
    cie_paper = {
        "schema": "source-document/1",
        "system": "cie",
        "role": "qp",
        "native_id": "0580/41",
        "pages": 4,
        "synthetic": True,
    }
    ielts_run = {
        "schema": "source-run-summary/1",
        "system": "ielts",
        "run_id": "synthetic-ielts-run-1",
        "containers": [{"native_id": "SB1", "kind": "book"}],
        "synthetic": True,
    }
    ielts_questions = {
        "schema": "source-document/1",
        "system": "ielts",
        "role": "book_page",
        "container_native_id": "SB1",
        "questions": [{"native_id": "Q1", "text": "synthetic ielts question 1"}],
        "synthetic": True,
    }
    toefl_coverage = {
        "schema": "source-document/1",
        "system": "toefl",
        "role": "screen",
        "container_native_id": "T1",
        "index_entries": 1,
        "synthetic": True,
    }
    raw = {
        "raw/cie/index-cie-0580.json": cie_index,
        "raw/cie/paper-0580-41.json": cie_paper,
        "raw/ielts/run-summary.json": ielts_run,
        "raw/ielts/questions.json": ielts_questions,
        "raw/toefl/coverage.json": toefl_coverage,
    }
    for rel, payload in sorted(raw.items()):
        _write_json(root / rel, payload)

    # --------------------------------------------------------------- assets --
    asset_bytes = {
        "assets/cie/diagram-syn-cie-1.png": png_bytes("cie-1"),
        "assets/ielts/audio-syn-ielts-1.mp3": mp3_bytes("ielts-1"),
        "assets/toefl/diagram-syn-toefl-1.png": png_bytes("toefl-1"),
    }
    for rel, data in sorted(asset_bytes.items()):
        _write(root / rel, data)
    if variant == "defects":
        # planted defect: the file no longer matches the recorded sha256 claim
        _write(root / "assets/ielts/audio-syn-ielts-1.mp3",
               mp3_bytes("ielts-1")[:-1] + b"\x00")
        # planted defect: the toefl asset file is absent altogether
        (root / "assets/toefl/diagram-syn-toefl-1.png").unlink()

    doc_sha = {rel: w5.sha256_bytes((root / rel).read_bytes()) for rel in raw}
    # The recorded asset claim is always the sha256 of the *intended* content.
    # In the defects variant the file on disk was tampered with or deleted
    # above, so the recorded claim no longer matches the bytes on disk - the
    # drift the reconcile step must surface (asset_hash_mismatch / missing).
    asset_sha = {rel: w5.sha256_bytes(data) for rel, data in asset_bytes.items()}

    # ---------------------------------------------------------------- caches --
    _write_json(root / "caches/cie/parse-cache.json",
                {"schema": "source-cache/1", "system": "cie", "entries": 2,
                 "rebuildable": True, "synthetic": True})
    _write_json(root / "caches/ielts/audio-cache.json",
                {"schema": "source-cache/1", "system": "ielts", "entries": 1,
                 "rebuildable": True, "synthetic": True})

    # -------------------------------------------------------------- observed --
    _write_json(root / "observed/run-checkpoint.json",
                {"schema": "source-checkpoint/1", "run_id": "synthetic-run-1",
                 "updated_at": "2026-10-06T12:00:30.500Z", "counters": {"requests": 8, "errors": 0}})

    # --------------------------------------------------------------- entities --
    def question_identity(system: str, container: Any, native_id: str,
                          number_path: list[str], parent: Any) -> dict[str, Any]:
        return {"system": system, "container_native_identity": container,
                "native_id": native_id, "number_path": number_path,
                "parent_native_id": parent}

    cie_container_native = {"native_id": "0580/41", "session": "June", "year": 2026}
    # A container native identity is a flat mapping of concrete native values
    # (the shape the candidate's own CIE adapter builds).  Explicit-unknown is
    # exercised where the contract documents it: the top-level
    # ``parent_native_id`` of a root question (a known absence) and the
    # ``container_native_identity`` of the deliberately unplaced question below
    # (an unresolved value that stays *visible*, never fatal).
    toefl_container_native = {"native_id": "T1"}

    rows: list[dict[str, Any]] = [
        dict(entity_id="cie-es", kind="examination_system", system="cie", scope="mvp",
             native_id="cie", identity={"system": "cie"},
             locator={"kind": "examination_system", "system": "cie"},
             raw_path="raw/cie/index-cie-0580.json", document_path=None,
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-cie-es"),
        dict(entity_id="cie-course-0580", kind="course", system="cie", scope="mvp",
             native_id="0580",
             identity={"system": "cie", "qualification": "igcse", "native_code": "0580",
                       "specification_version": "2026"},
             locator={"kind": "course", "native_code": "0580", "qualification": "igcse"},
             raw_path="raw/cie/index-cie-0580.json", document_path=None,
             quality={"content": "complete"}, labels=["synthetic_fixture"],
             content_class="synthetic", source_revision="src-2026-10-05",
             content_revision="rev-syn-cie-course"),
        dict(entity_id="cie-container-0580-41", kind="container", system="cie", scope="mvp",
             native_id="0580/41",
             identity={"system": "cie", "kind": "paper", "native_identity": cie_container_native},
             locator={"kind": "container", "native_identity": cie_container_native},
             raw_path="raw/cie/index-cie-0580.json", document_path="raw/cie/paper-0580-41.json",
             quality={"content": "complete"}, labels=["synthetic_fixture"],
             content_class="synthetic", source_revision="src-2026-10-05",
             content_revision="rev-syn-cie-container"),
        dict(entity_id="cie-q1", kind="question", system="cie", scope="mvp", native_id="1",
             identity=question_identity("cie", cie_container_native, "1", ["1"],
                                         UNKNOWN_TOKEN),
             locator={"kind": "question", "native_id": "1", "container_native_id": "0580/41"},
             raw_path="raw/cie/index-cie-0580.json", document_path="raw/cie/paper-0580-41.json",
             quality={"content": "complete", "answer_presence": "present",
                      "answer_verification": "unverified"},
             labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-cie-q1"),
        dict(entity_id="cie-ans-q1", kind="answer", system="cie", scope="mvp",
             native_id="0580/41/Q1/ms",
             identity={"system": "cie", "question_native_id": "1", "source": "ms",
                       "native_answer_key": "A1"},
             locator={"kind": "answer", "source": "ms", "native_answer_key": "A1"},
             raw_path="raw/cie/index-cie-0580.json", document_path="raw/cie/paper-0580-41.json",
             quality={"answer_verification": "manual_adjudicated"},
             labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-cie-ans"),
        dict(entity_id="cie-asset-diagram", kind="asset", system="cie", scope="mvp",
             native_id="diagram-syn-cie-1",
             identity={"system": "cie", "media_type": "image/png",
                       "sha256": asset_sha["assets/cie/diagram-syn-cie-1.png"],
                       "storage_mode": "external"},
             locator={"kind": "asset", "path": "assets/cie/diagram-syn-cie-1.png"},
             raw_path="assets/cie/diagram-syn-cie-1.png", document_path=None,
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-cie-asset"),
        dict(entity_id="cie-region-qp-p2", kind="region", system="cie", scope="mvp",
             native_id="qp-p2-r1",
             identity={"system": "cie", "document_role": "qp",
                       "document_sha256": doc_sha["raw/cie/paper-0580-41.json"],
                       "page": 2, "bbox": {"x": 10, "y": 20, "w": 100, "h": 40},
                       "coordinate_system": "pdf_points"},
             locator={"kind": "region", "document": "raw/cie/paper-0580-41.json", "page": 2},
             raw_path="raw/cie/paper-0580-41.json",
             document_path="raw/cie/paper-0580-41.json",
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-cie-region"),
        dict(entity_id="ielts-es", kind="examination_system", system="ielts", scope="full",
             native_id="ielts", identity={"system": "ielts"},
             locator={"kind": "examination_system", "system": "ielts"},
             raw_path="raw/ielts/run-summary.json", document_path=None,
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-ielts-es"),
        dict(entity_id="toefl-es", kind="examination_system", system="toefl", scope="full",
             native_id="toefl", identity={"system": "toefl"},
             locator={"kind": "examination_system", "system": "toefl"},
             raw_path="raw/toefl/coverage.json", document_path=None,
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-toefl-es"),
        dict(entity_id="ielts-course-c1", kind="course", system="ielts", scope="full",
             native_id="C1",
             identity={"system": "ielts", "qualification": "academic", "native_code": "C1",
                       "specification_version": "2026"},
             locator={"kind": "course", "native_code": "C1", "qualification": "academic"},
             raw_path="raw/ielts/run-summary.json", document_path=None,
             quality={"content": "complete"}, labels=["synthetic_fixture"],
             content_class="synthetic", source_revision="src-2026-10-05",
             content_revision="rev-syn-ielts-course"),
        dict(entity_id="ielts-container-sb1", kind="container", system="ielts", scope="full",
             native_id="SB1",
             identity={"system": "ielts", "kind": "book", "native_identity": "SB1"},
             locator={"kind": "container", "native_identity": "SB1"},
             raw_path="raw/ielts/run-summary.json", document_path="raw/ielts/questions.json",
             quality={"content": "complete"}, labels=["synthetic_fixture"],
             content_class="synthetic", source_revision="src-2026-10-05",
             content_revision="rev-syn-ielts-container"),
        dict(entity_id="toefl-container-t1", kind="container", system="toefl", scope="full",
             native_id="T1",
             identity={"system": "toefl", "kind": "test",
                       "native_identity": toefl_container_native},
             locator={"kind": "container", "native_identity": toefl_container_native},
             raw_path="raw/toefl/coverage.json", document_path="raw/toefl/coverage.json",
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-toefl-container"),
        dict(entity_id="ielts-q1", kind="question", system="ielts", scope="full",
             native_id="Q1",
             identity=question_identity("ielts", "SB1", "Q1", ["1"], UNKNOWN_TOKEN),
             locator={"kind": "question", "native_id": "Q1", "container_native_id": "SB1"},
             raw_path="raw/ielts/questions.json", document_path="raw/ielts/questions.json",
             quality={"content": "complete", "answer_presence": "present",
                      "answer_verification": "unverified"},
             labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-ielts-q1"),
        dict(entity_id="toefl-q1", kind="question", system="toefl", scope="full",
             native_id="Q1",
             identity=question_identity("toefl", toefl_container_native, "Q1", ["1"],
                                        UNKNOWN_TOKEN),
             locator={"kind": "question", "native_id": "Q1", "container_native_id": "T1"},
             raw_path="raw/toefl/coverage.json", document_path="raw/toefl/coverage.json",
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-toefl-q1"),
        dict(entity_id="ielts-q-unplaced", kind="question", system="ielts", scope="full",
             native_id="Q99",
             identity=question_identity("ielts", UNKNOWN_TOKEN, "Q99", ["99"], None),
             locator={"kind": "question", "native_id": "Q99"},
             raw_path="raw/ielts/questions.json", document_path=None,
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-ielts-q99"),
        dict(entity_id="ielts-ans-q1", kind="answer", system="ielts", scope="full",
             native_id="SB1/Q1/key",
             identity={"system": "ielts", "question_native_id": "Q1", "source": "key",
                       "native_answer_key": "K1"},
             locator={"kind": "answer", "source": "key", "native_answer_key": "K1"},
             raw_path="raw/ielts/questions.json", document_path="raw/ielts/questions.json",
             quality={"answer_verification": "unverified"},
             labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-ielts-ans"),
        dict(entity_id="toefl-ans-q1", kind="answer", system="toefl", scope="full",
             native_id="T1/Q1/key",
             identity={"system": "toefl", "question_native_id": "Q1", "source": "key",
                       "native_answer_key": "K1"},
             locator={"kind": "answer", "source": "key", "native_answer_key": "K1"},
             raw_path="raw/toefl/coverage.json", document_path="raw/toefl/coverage.json",
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-toefl-ans"),
        dict(entity_id="ielts-asset-audio", kind="asset", system="ielts", scope="full",
             native_id="audio-syn-ielts-1",
             identity={"system": "ielts", "media_type": "audio/mpeg",
                       "sha256": asset_sha["assets/ielts/audio-syn-ielts-1.mp3"],
                       "storage_mode": "external"},
             locator={"kind": "asset", "path": "assets/ielts/audio-syn-ielts-1.mp3"},
             raw_path="assets/ielts/audio-syn-ielts-1.mp3", document_path=None,
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-ielts-asset"),
        dict(entity_id="toefl-asset-diagram", kind="asset", system="toefl", scope="full",
             native_id="diagram-syn-toefl-1",
             identity={"system": "toefl", "media_type": "image/png",
                       "sha256": asset_sha["assets/toefl/diagram-syn-toefl-1.png"],
                       "storage_mode": "external"},
             locator={"kind": "asset", "path": "assets/toefl/diagram-syn-toefl-1.png"},
             raw_path="assets/toefl/diagram-syn-toefl-1.png", document_path=None,
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-toefl-asset"),
        dict(entity_id="ielts-region-p3", kind="region", system="ielts", scope="full",
             native_id="book-p3-r1",
             identity={"system": "ielts", "document_role": "book_page",
                       "document_sha256": doc_sha["raw/ielts/questions.json"],
                       "page": 3, "bbox": {"x": 5, "y": 5, "w": 200, "h": 60},
                       "coordinate_system": "image_px"},
             locator={"kind": "region", "document": "raw/ielts/questions.json", "page": 3},
             raw_path="raw/ielts/questions.json", document_path="raw/ielts/questions.json",
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-ielts-region"),
        dict(entity_id="toefl-region-p1", kind="region", system="toefl", scope="full",
             native_id="screen-p1-r1",
             identity={"system": "toefl", "document_role": "screen",
                       "document_sha256": doc_sha["raw/toefl/coverage.json"],
                       "page": 1, "bbox": {"x": 0, "y": 0, "w": 640, "h": 480},
                       "coordinate_system": "image_px"},
             locator={"kind": "region", "document": "raw/toefl/coverage.json", "page": 1},
             raw_path="raw/toefl/coverage.json", document_path="raw/toefl/coverage.json",
             quality={}, labels=["synthetic_fixture"], content_class="synthetic",
             source_revision="src-2026-10-05", content_revision="rev-syn-toefl-region"),
    ]

    if variant == "defects":
        rows.append(dict(
            entity_id="cie-q-bad-identity", kind="question", system="cie", scope="full",
            native_id="Q9",
            identity={"system": "cie"},  # planted defect: identity keys missing
            locator={"kind": "question", "native_id": "Q9"},
            raw_path="raw/cie/index-cie-0580.json", document_path=None,
            quality={}, labels=["synthetic_fixture"], content_class="synthetic",
            source_revision="src-2026-10-05", content_revision="rev-syn-cie-q9"))
        rows.append(dict(
            entity_id="toefl-q2-missing-raw", kind="question", system="toefl", scope="full",
            native_id="Q2",
            identity=question_identity("toefl", toefl_container_native, "Q2", ["2"], None),
            locator={"kind": "question", "native_id": "Q2", "container_native_id": "T1"},
            raw_path="raw/toefl/questions-missing.json",  # planted defect: absent payload
            document_path="raw/toefl/questions-missing.json",
            quality={}, labels=["synthetic_fixture"], content_class="synthetic",
            source_revision="src-2026-10-05", content_revision="rev-syn-toefl-q2"))

    for row in rows:
        kind = EntityKind.coerce(row["kind"])
        # Derive the ID from the *decoded* identity - the same form the
        # migration will build after reading the persisted token - so the
        # recorded public IDs and refs are exactly what a reader will recompute.
        decoded = decode_unknown(row["identity"])
        try:
            canonical.canonical_identity_string(kind, decoded)
            row["public_id"] = canonical.public_id(kind, decoded)
        except (KeyError, TypeError) as exc:
            if variant != "defects":
                raise
            # Planted defect: identity keys are missing, so no valid public ID
            # exists.  The row stays in the source index with a visibly invalid
            # placeholder ID; the migration must reject it (invalid_identity)
            # instead of inventing an identity.
            row["identity_invalid"] = str(exc)
            row["public_id"] = f"{kind.value}_INVALID"

    refs: list[tuple[str, str, str]] = []
    by_entity = {row["entity_id"]: row for row in rows}
    for entity_id, to_entity, role in (
        ("cie-q1", "cie-container-0580-41", "in_container"),
        ("cie-ans-q1", "cie-q1", "answers"),
        ("cie-asset-diagram", "cie-container-0580-41", "asset_of"),
        ("cie-region-qp-p2", "cie-container-0580-41", "region_of"),
        ("ielts-q1", "ielts-container-sb1", "in_container"),
        ("ielts-ans-q1", "ielts-q1", "answers"),
        ("ielts-asset-audio", "ielts-container-sb1", "asset_of"),
        ("ielts-region-p3", "ielts-container-sb1", "region_of"),
        ("toefl-q1", "toefl-container-t1", "in_container"),
        ("toefl-ans-q1", "toefl-q1", "answers"),
        ("toefl-asset-diagram", "toefl-container-t1", "asset_of"),
        ("toefl-region-p1", "toefl-container-t1", "region_of"),
    ):
        refs.append((by_entity[entity_id]["public_id"], role, by_entity[to_entity]["public_id"]))
    if variant == "defects":
        # planted defect: a container reference that can never resolve.  The
        # role is ``in_container``, so the migration wires it into the entry's
        # ``container_ref`` and the candidate's own reference validation must
        # reject the publication (``unresolved_identity``).
        refs.append((by_entity["toefl-q2-missing-raw"]["public_id"], "in_container",
                     "container_" + "z" * 32))

    # --------------------------------------------------------------- decisions --
    decisions = {
        "schema": "source-manual-decisions/1",
        "owner": "source stores",
        "integration_rule": "preserved and surfaced, never overwritten",
        "decisions": [
            {"decision_id": "md-cie-ans-q1", "system": "cie", "scope": "answer",
             "subject_public_id": by_entity["cie-ans-q1"]["public_id"],
             "subject_native_id": "0580/41/Q1/ms",
             "selected_value": "A", "basis": "manual_review",
             "adjudicator": "synthetic-adjudicator",
             "decided_at": "2026-10-05T00:00:00+00:00",
             "evidence_label": "synthetic_fixture"},
            {"decision_id": "md-ielts-q41-slot", "system": "ielts", "scope": "question",
             "subject_public_id": by_entity["ielts-q1"]["public_id"],
             "subject_native_id": "SB1/Q41",
             "selected_value": None, "basis": "manual_review",
             "adjudicator": "synthetic-adjudicator",
             "decided_at": "2026-10-05T00:00:00+00:00",
             "note": "preserved missing answer slot: no placeholder is invented",
             "evidence_label": "synthetic_fixture"},
        ],
    }
    _write_json(root / "decisions/manual-decisions.json", decisions)

    # ------------------------------------------------------------ ownership --
    ownership = {
        "schema": OWNERSHIP_SCHEMA,
        "note": "synthetic rehearsal store; no real path, database or credential is referenced",
        "systems": {
            system: {
                "raw_roots": [f"raw/{system}", f"assets/{system}", f"caches/{system}"],
                "authority": "source",
            }
            for system in SYSTEMS
        },
        "integration_owned": {
            "aggregate_index": ["index/aggregate-index.db"],
            "derived_mirror": ["index/aggregate-index.json"],
        },
        "observed_read_only": ["observed/run-checkpoint.json"],
        "manual_decisions": ["decisions/manual-decisions.json"],
        "provenance": ["provenance/PROVENANCE.json"],
    }
    _write_json(root / "ownership.json", ownership)

    # ------------------------------------------------------------ sqlite db --
    db_path = root / "index/aggregate-index.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA page_size=4096")
        conn.executescript(
            """
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE entities(
                public_id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                system TEXT NOT NULL,
                kind TEXT NOT NULL,
                scope TEXT NOT NULL,
                native_id TEXT,
                identity_json TEXT NOT NULL,
                locator_json TEXT NOT NULL,
                raw_path TEXT,
                document_path TEXT,
                quality_json TEXT NOT NULL,
                evidence_labels TEXT NOT NULL,
                content_class TEXT NOT NULL,
                source_revision TEXT,
                content_revision TEXT
            );
            CREATE TABLE assets(
                public_id TEXT PRIMARY KEY, entity_id TEXT, media_type TEXT,
                sha256 TEXT, storage_mode TEXT, path TEXT, bytes INTEGER
            );
            CREATE TABLE regions(
                public_id TEXT PRIMARY KEY, entity_id TEXT, document_role TEXT,
                document_sha256 TEXT, page INTEGER, bbox_json TEXT,
                coordinate_system TEXT, document_path TEXT
            );
            CREATE TABLE refs(
                ord INTEGER PRIMARY KEY, from_public_id TEXT NOT NULL,
                role TEXT NOT NULL, to_public_id TEXT NOT NULL
            );
            """
        )
        conn.executemany("INSERT INTO meta VALUES(?,?)", [
            ("schema", "w5.aggregate-index/1"),
            ("variant", variant),
            ("source_root_name", root.name),
        ])
        for row in rows:
            conn.execute(
                "INSERT INTO entities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["public_id"], row["entity_id"], row["system"], row["kind"], row["scope"],
                 row["native_id"], w5.canonical_json(row["identity"]),
                 w5.canonical_json(row["locator"]), row["raw_path"], row["document_path"],
                 w5.canonical_json(row["quality"]), ",".join(row["labels"]),
                 row["content_class"], row["source_revision"], row["content_revision"]))
        for row in rows:
            if row["kind"] == "asset":
                path = row["raw_path"]
                conn.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?)",
                             (row["public_id"], row["entity_id"],
                              row["identity"]["media_type"], row["identity"]["sha256"],
                              row["identity"]["storage_mode"], path,
                              len((root / path).read_bytes()) if (root / path).is_file() else None))
            if row["kind"] == "region":
                conn.execute("INSERT INTO regions VALUES(?,?,?,?,?,?,?,?)",
                             (row["public_id"], row["entity_id"],
                              row["identity"]["document_role"],
                              row["identity"]["document_sha256"], row["identity"]["page"],
                              w5.canonical_json(row["identity"]["bbox"]),
                              row["identity"]["coordinate_system"], row["document_path"]))
        conn.executemany("INSERT INTO refs(ord,from_public_id,role,to_public_id) VALUES(?,?,?,?)",
                         [(i, *ref) for i, ref in enumerate(refs)])
        conn.commit()
    finally:
        conn.close()

    # ------------------------------------------------------ derived mirror ----
    mirror = {
        "schema": "w5.aggregate-index-mirror/1",
        "derived_from": "index/aggregate-index.db",
        "read_only": True,
        "entities": sorted(
            [{"public_id": r["public_id"], "entity_id": r["entity_id"], "system": r["system"],
              "kind": r["kind"], "scope": r["scope"]} for r in rows],
            key=lambda r: r["public_id"]),
        "assets": sorted(
            [{"public_id": r["public_id"], "path": r["raw_path"],
              "sha256": r["identity"]["sha256"]} for r in rows if r["kind"] == "asset"],
            key=lambda r: r["public_id"]),
        "regions": sorted(
            [{"public_id": r["public_id"], "document_path": r["document_path"],
              "page": r["identity"]["page"]} for r in rows if r["kind"] == "region"],
            key=lambda r: r["public_id"]),
        "refs": [{"from_public_id": ref[0], "role": ref[1], "to_public_id": ref[2]}
                 for ref in refs],
    }
    _write_json(root / "index/aggregate-index.json", mirror)

    # ----------------------------------------------------------- provenance --
    entries = []
    for path in w5.iter_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in ("provenance/PROVENANCE.json", MARKER_NAME):
            continue
        entries.append({
            "path": rel,
            "sha256": w5.sha256_file(path),
            "bytes": path.stat().st_size,
            "label": "synthetic_fixture",
            "authority": ("source" if rel.startswith(("raw/", "assets/", "caches/", "decisions/"))
                          else "integration"),
            "created_by": "w5 build_source.py",
            "created_at_utc": "2026-10-05T16:00:00+00:00",
        })
    _write_json(root / "provenance/PROVENANCE.json", {
        "schema": "w5.source-provenance/1",
        "variant": variant,
        "note": ("all bytes are invented synthetic content produced by build_source.py; "
                 "no original tree, database, service or credential was read"),
        "entries": sorted(entries, key=lambda e: e["path"]),
    })

    marker = {
        "schema": MARKER_SCHEMA,
        "created_by": "migration/tools/build_source.py",
        "variant": variant,
        "note": "ownership marker; --force may delete this root only when this file matches",
    }
    _write_json(root / MARKER_NAME, marker)

    return {
        "root": str(root),
        "variant": variant,
        "entities": len(rows),
        "scope_mvp": sum(1 for r in rows if r["scope"] == "mvp"),
        "refs": len(refs),
        "digests": w5.both_digests(root),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="target source-store root (private, new)")
    ap.add_argument("--variant", choices=("clean", "defects"), default="clean")
    ap.add_argument("--force", action="store_true",
                    help="delete the target first, only when it carries the w5 ownership marker")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if root.exists():
        marker = root / MARKER_NAME
        owned = marker.is_file() and w5.read_json(marker).get("schema") == MARKER_SCHEMA
        if not args.force:
            print(json.dumps({"error": "target exists; refusing to touch it",
                              "root": str(root), "w5_owned": owned}, indent=2))
            return 2
        if not owned:
            print(json.dumps({"error": "refusing --force on a tree without the w5 marker",
                              "root": str(root)}, indent=2))
            return 2
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
        root.rmdir()

    w5.dump(build(root, args.variant))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
