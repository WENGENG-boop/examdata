"""A04 - JSON-schema generation, subset coverage, and example validation.

Every generated example validates against its generated schema; no schema uses a
keyword outside the supported subset (the subset is deliberate - see the A04
report); and the generator's ``--check`` mode is byte-stable (regenerating
changes nothing), which is what makes the schemas trustworthy evidence.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from examdata_integration.contracts.jsonschema_lite import unsupported_keywords, validate

STAGING = Path(__file__).resolve().parents[1]
CONTRACTS = STAGING / "contracts"
SCHEMA_DIR = CONTRACTS / "schema"
EXAMPLES = CONTRACTS / "examples"
GENERATOR = STAGING / "tools" / "a04_generate_schemas.py"


def _schema_filename(schema_id: str) -> str:
    parts = [p for p in schema_id.split("/") if not p.isdigit()]
    return "-".join(parts) + ".schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _all_schemas() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("*.schema.json"))


def test_all_generated_schemas_exist():
    schemas = _all_schemas()
    assert len(schemas) == 28
    for schema in schemas:
        doc = _load(schema)
        assert "$defs" in doc and "$schema" in doc
        assert doc["x-generated-by"].startswith("a04_generate_schemas.py sha256:")


def test_no_schema_uses_an_unsupported_keyword():
    for schema in _all_schemas():
        problems = unsupported_keywords(_load(schema))
        assert problems == [], f"{schema.name}: {problems}"


def test_every_example_validates_against_its_schema():
    index = _load(EXAMPLES / "INDEX.json")
    entries = index["examples"]
    assert entries, "no examples were generated"
    # identity-registry/1 is a container of IdentityRecords, not a contract model,
    # so the generator emits no JSON schema for it; its round-trip is asserted by
    # test_contracts_identity.py instead.
    non_model_schemas = {"identity-registry/1"}
    failures = []
    checked = 0
    for entry in entries:
        example = _load(EXAMPLES / entry["file"])
        assert example["schema"] == entry["schema"]
        if entry["schema"] in non_model_schemas:
            continue
        schema_path = SCHEMA_DIR / _schema_filename(entry["schema"])
        assert schema_path.is_file(), f"missing schema for {entry['schema']}"
        schema = _load(schema_path)
        problems = validate(example, schema)
        checked += 1
        if problems:
            failures.append(f"{entry['file']}: {problems}")
    assert not failures, "\n".join(failures)
    assert checked == len(entries) - 3  # three identity-registry examples


def test_every_entity_kind_has_an_example():
    index = _load(EXAMPLES / "INDEX.json")
    schemas = {e["schema"] for e in index["examples"]}
    required = {"container/1", "course/1", "question/1", "answer/1", "asset/1", "coverage/1",
                "region/1", "timetable-event/1", "timetable-window/1", "syllabus/1", "tag/1",
                "material/1", "examination-system/1", "job-status/1"}
    assert required <= schemas, sorted(required - schemas)


def test_identity_keys_and_quality_transitions_are_published():
    keys = _load(CONTRACTS / "identity-keys.json")
    assert keys["schema"] == "identity-keys/1"
    assert keys["normalisation"]["digest_bytes"] == 20
    assert keys["normalisation"]["absent_encoding"] == "\\x00"
    assert keys["normalisation"]["explicit_unknown_encoding"] == "\\x01"
    assert len(keys["kinds"]) == 14

    qt = _load(CONTRACTS / "quality-transitions.json")
    assert qt["schema"] == "quality-transitions/1"
    assert qt["transitions"]
    assert "fixture_implies_real" in qt["forbidden_basis"]


def test_generator_check_mode_is_stable():
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([sys.executable, str(GENERATOR), "--check"],
                          cwd=str(STAGING), env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CHECK: PASS (30/30)" in proc.stdout
