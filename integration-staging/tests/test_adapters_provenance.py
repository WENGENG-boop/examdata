"""A07: every adapter fixture carries provenance and stays synthetic."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

STAGING = Path(__file__).resolve().parents[1]
FIXTURE_DIR = STAGING / "fixtures" / "synthetic" / "adapters"
MANIFEST = FIXTURE_DIR / "PROVENANCE.json"
CAPTURE_TOOL = STAGING / "tools" / "a07_capture_adapter_fixtures.py"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_exists_and_has_entries():
    manifest = _manifest()
    assert manifest["schema"] == "fixture-provenance/1"
    assert manifest["entries"]
    assert manifest["summary"]["entries"] == len(manifest["entries"])


def test_every_adapter_fixture_is_listed():
    listed = {Path(e["path"]).name for e in _manifest()["entries"]}
    present = {p.name for p in FIXTURE_DIR.glob("*.json") if p.name != "PROVENANCE.json"}
    assert listed == present


def test_listed_hashes_match_the_files_on_disk():
    for entry in _manifest()["entries"]:
        path = STAGING.parent / entry["path"]
        assert path.is_file(), entry["path"]
        assert _sha256(path) == entry["sha256"]
        assert path.stat().st_size == entry["bytes"]


def test_entries_are_labelled_synthetic():
    for entry in _manifest()["entries"]:
        assert entry["kind"] == "synthetic"
        assert entry["label"] == "synthetic_fixture"
        data = json.loads((STAGING.parent / entry["path"]).read_text(encoding="utf-8"))
        assert data["fixture_kind"] == "synthetic"


def test_capture_tool_check_mode_is_clean():
    result = subprocess.run(
        [sys.executable, str(CAPTURE_TOOL), "--check"],
        cwd=STAGING, capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "A07_PROVENANCE: PASS" in result.stdout


def test_fixture_readme_is_present():
    assert (FIXTURE_DIR / "README.md").is_file()
