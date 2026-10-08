"""A13 frontend staged copy (plan section 11/A13).

The staged frontend under integration-staging/frontend is a copy-only Phase A
proposal: the original frontend/ tree stays byte-identical, modified copies are
pinned by the provenance manifest, staged-only files never exist in the
original tree, and the fixtures are synthetic. Nothing here runs the original
application, touches the network, or writes outside the staging root.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from examdata_integration.testing.guards import is_within

STAGING = Path(__file__).resolve().parents[1]
PROJECT = STAGING.parent
STAGED = STAGING / "frontend"
SOURCE = PROJECT / "frontend"
TOOL = STAGING / "tools" / "a13_frontend_provenance.py"
MANIFEST = STAGED / "PROVENANCE.json"
FIXTURE_MANIFEST = STAGED / "fixtures" / "PROVENANCE.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_provenance_check_mode_is_clean():
    result = subprocess.run(
        [sys.executable, str(TOOL), "--check"],
        cwd=STAGING, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "A13_FRONTEND_PROVENANCE: PASS (6 copied, 4 new, 3 fixtures)" in result.stdout


def test_original_frontend_sources_are_untouched():
    manifest = _manifest()
    sourced = [e for e in manifest["files"] if e.get("source_path")]
    assert len(sourced) == 6
    mismatches = []
    for entry in sourced:
        source = PROJECT / entry["source_path"]
        if not source.is_file():
            mismatches.append(f"{entry['source_path']}: missing")
        elif sha256_file(source) != entry["source_sha256"]:
            mismatches.append(f"{entry['source_path']}: hash changed")
    assert not mismatches, mismatches


def test_copied_snapshots_are_byte_identical():
    manifest = _manifest()
    snapshots = [e for e in manifest["files"] if e["kind"] == "copied_snapshot"]
    assert snapshots
    for entry in snapshots:
        source = (PROJECT / entry["source_path"]).read_bytes()
        staged = (STAGED / entry["path"]).read_bytes()
        assert staged == source, f"{entry['path']} is not a byte-identical snapshot"


def test_modified_copies_carry_exactly_the_staged_edits():
    manifest = _manifest()
    entries = {e["path"]: e for e in manifest["files"]}
    for name in ("app.js", "index.html", "README.md", "tests/search.test.mjs"):
        assert entries[name]["kind"] == "modified_copy", name
        assert entries[name]["changes"], f"{name}: changes list must not be empty"

    staged_app = (STAGED / "app.js").read_text(encoding="utf-8")
    original_app = (SOURCE / "app.js").read_text(encoding="utf-8")
    assert "from './client.mjs'" in staged_app
    assert "searchDocuments(" in staged_app
    assert "STAGED FIXTURE" in staged_app
    assert "/gateway" not in staged_app
    assert "from './client.mjs'" not in original_app
    assert "/gateway" in original_app

    staged_html = (STAGED / "index.html").read_text(encoding="utf-8")
    original_html = (SOURCE / "index.html").read_text(encoding="utf-8")
    assert 'id="staged-banner"' in staged_html
    assert "staged fixture validation" in staged_html
    assert "staged-banner" not in original_html

    staged_readme = (STAGED / "README.md").read_text(encoding="utf-8")
    assert "Staged, not merged" in staged_readme


def test_new_files_are_staged_only():
    manifest = _manifest()
    new_files = [e for e in manifest["files"] if e["kind"] == "new_file"]
    names = {e["path"] for e in new_files}
    assert names == {"client.mjs", "fixture-server.mjs",
                     "tests/client.test.mjs", "tests/flow.test.mjs"}
    for entry in new_files:
        staged = STAGED / entry["path"]
        assert staged.is_file(), f"{entry['path']}: staged file missing"
        assert sha256_file(staged) == entry["staged_sha256"]
        assert not (SOURCE / entry["path"]).exists(), \
            f"{entry['path']} unexpectedly exists in the original tree"


def test_fixture_manifest_reconciles_and_stays_synthetic():
    manifest = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["fixture_kind"] == "synthetic"
    listed = {e["path"] for e in manifest["files"]}
    assert listed == {"catalog.json", "syllabi.json", "resources.json"}
    for entry in manifest["files"]:
        path = STAGED / "fixtures" / entry["path"]
        assert path.is_file()
        assert is_within(path, STAGED / "fixtures")
        assert path.stat().st_size == entry["size_bytes"]
        assert sha256_file(path) == entry["sha256"]


def test_unavailable_resources_never_carry_a_content_link():
    resources = json.loads(
        (STAGED / "fixtures" / "resources.json").read_text(encoding="utf-8"))
    unavailable = [i for i in resources["items"] if i.get("content_available") is False]
    available = [i for i in resources["items"] if i.get("content_available") is True]
    assert unavailable and available
    for item in unavailable:
        assert item.get("content_link") is None, item["public_id"]
        assert "content" not in (item.get("links") or {}), item["public_id"]
