#!/usr/bin/env python3
"""A03 fixture capture (plan section 11/A03): copy small immutable JSON evidence into
staging and write a provenance manifest.

Rules enforced here:
  * sources must live inside the workspace but outside the staging tree (no self-copy);
  * deny list: credentials, databases, caches, virtualenvs, build output, active-owner
    examination material and anything larger than the size cap;
  * every copied fixture records source path, source sha256 before/after, destination
    sha256, sizes, mtime, scope and any access/licence note already present in the file;
  * a source whose hash changes between the before/after reads is UNSTABLE: the copy is
    removed, the entry is marked `deferred_unstable` and the source is not copied again;
  * synthetic fixtures are hand-authored and labelled `synthetic_fixture`.

Reads originals; writes only under integration-staging/fixtures/.

Usage:
  python integration-staging/tools/a03_capture_fixtures.py [--check]
    --check  verify the manifest against the files on disk without copying anything
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

STAGING = Path(__file__).resolve().parents[1]
WS = STAGING.parent
FIXTURES = STAGING / "fixtures"
MANIFEST = FIXTURES / "PROVENANCE.json"
MANIFEST_MD = FIXTURES / "PROVENANCE.md"
SELF_REL = "integration-staging/tools/a03_capture_fixtures.py"

MAX_BYTES = 400 * 1024

DENY_DIR_PARTS = {
    ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".git",
    "site-packages", ".data", "pdf", "audio", "downloads", "raw",
}
DENY_SUFFIXES = (
    ".db", ".sqlite", ".sqlite3", ".duckdb", ".parquet", ".pdf", ".mp3", ".m4a", ".wav",
    ".pem", ".key", ".p12", ".pfx", ".zip", ".tar", ".gz", ".7z",
)
DENY_NAME_RE = re.compile(r"(^\.env|credential|secret|token|password|id_rsa|\.pth$)", re.I)

# Active-owner areas: examination material and historical timetables. Never copied.
DENY_PATH_PREFIXES = (
    "examdata/src",
    "examdata/docs",
    "docs/integration/execution",
    "ielts-data/normalized",
    "ielts-data/derived",
    "ielts-data/indexes/rev-",
    "ielts-data/manifests/rev-",
    "cie-location-batch/work",
)

ACCESS_NOTE_KEYS = ("source", "license", "licence", "access", "board", "generated_at_utc", "checked_at")

COPY_SPECS = [
    {
        "fixture_id": "ielts-indexes-current",
        "source": "ielts-data/indexes/current",
        "destination": "integration-staging/fixtures/copied/ielts/indexes-current.json",
        "scope": "IELTS published dataset revision pointer (dataset_revision, published_at, artifact)",
    },
    {
        "fixture_id": "ielts-manifests-current",
        "source": "ielts-data/manifests/current",
        "destination": "integration-staging/fixtures/copied/ielts/manifests-current.json",
        "scope": "IELTS published manifest revision pointer (dataset_revision, published_at, artifact)",
    },
    {
        "fixture_id": "ielts-pdf-provenance",
        "source": "ielts-data/manifests/pdf-provenance.json",
        "destination": "integration-staging/fixtures/copied/ielts/pdf-provenance.json",
        "scope": "IELTS PDF import provenance manifest: per-book pdf path, sha256 and page numbers (metadata only, no page content)",
    },
    {
        "fixture_id": "ielts-printed-pages",
        "source": "ielts-api/data/printed-pages.json",
        "destination": "integration-staging/fixtures/copied/ielts/printed-pages.json",
        "scope": "IELTS printed-page resolution results (numeric pair -> page map), generated metadata",
    },
    {
        "fixture_id": "edexcel-subjects-source",
        "source": "frontend/edexcel-subjects-source.json",
        "destination": "integration-staging/fixtures/copied/edexcel/subjects-source.json",
        "scope": "Edexcel subject catalogue metadata: title, url, Pearson category labels (no specification content)",
    },
    {
        "fixture_id": "toefl-ddy-index",
        "source": "toefl-api/data/ddy-index.json",
        "destination": "integration-staging/fixtures/copied/toefl/ddy-index.json",
        "scope": "TOEFL TPO index metadata: id, title, upstream file, link, paragraph/char counts (no passage text)",
    },
]

SYNTHETIC_SPECS = [
    {
        "fixture_id": "ielts-questions-synthetic",
        "destination": "integration-staging/fixtures/synthetic/ielts/questions-synthetic.json",
        "scope": "Hand-authored IELTS-shaped question set for identity tests: native ids, aliases, grouped alternatives, parent answers, the missing Q41 slot",
    },
    {
        "fixture_id": "cie-index-synthetic",
        "destination": "integration-staging/fixtures/synthetic/cie/cie-index-synthetic.json",
        "scope": "Hand-authored CIE-shaped paper index for identity tests: question hierarchy, table structure, unknown date, answer conflict, required image, lineage",
    },
    {
        "fixture_id": "edexcel-index-synthetic",
        "destination": "integration-staging/fixtures/synthetic/edexcel/index-synthetic.json",
        "scope": "Hand-authored Edexcel-shaped paper index for identity tests: unit/paper codes, session labels, qualification levels",
    },
]

# Sources inspected and deliberately NOT copied (recorded in the manifest).
DEFERRED_SOURCES = [
    {
        "source": "cie-index-batch-2026-10-01/9709/2024-Jun-11/cie-index.json",
        "reason": "Contains verbatim examination question text extracted from a CIE paper: examination material, and the CIE batch is stopped and off-limits. The CIE adapter will be tested against a schema-shaped synthetic fixture instead.",
        "status": "deferred_examination_material",
    },
    {
        "source": "ielts-data/indexes/rev-8b21015ab64bb73c/questions.json",
        "reason": "15 MB derived question index: exceeds the small-representative-artifact cap and is derived from examination material.",
        "status": "deferred_too_large",
    },
    {
        "source": "toefl-api/data/jj-index.json",
        "reason": "Modified during the same day as this packet (2026-10-05 09:47 local): treated as potentially active, so it is not copied.",
        "status": "deferred_maybe_active",
    },
    {
        "source": "frontend/catalog.json",
        "reason": "577 KB build artifact of the frontend pipeline (regenerable, above the size cap).",
        "status": "deferred_build_artifact",
    },
    {
        "source": "ielts-data/normalized/normalized-v1/rev-8b21015ab64bb73c/cambridge-1-1.json",
        "reason": "~175 KB normalized test content derived from examination material; representative synthetic fixtures are used instead.",
        "status": "deferred_derived_exam_content",
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def is_within(child: Path, parent: Path) -> bool:
    import os
    c, p = os.path.normcase(os.path.realpath(child)), os.path.normcase(os.path.realpath(parent))
    return c == p or c.startswith(p + os.sep)


def rel_ws(p: Path) -> str:
    return p.resolve().relative_to(WS).as_posix()


def deny_reason(rel_source: str) -> str | None:
    lowered = rel_source.lower()
    for prefix in DENY_PATH_PREFIXES:
        if lowered.startswith(prefix.lower()):
            return f"path prefix {prefix!r} is off-limits"
    parts = set(lowered.split("/"))
    bad = parts & DENY_DIR_PARTS
    if bad:
        return f"directory component {sorted(bad)} is on the deny list"
    if DENY_NAME_RE.search(Path(lowered).name):
        return "file name matches the credential/secret deny pattern"
    if lowered.endswith(DENY_SUFFIXES):
        return "file type is on the deny list (database/binary/archive/credential)"
    return None


def access_notes(src: Path) -> dict:
    """Pull access/licence hints that are already present in the source file."""
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        return {}
    notes: dict[str, object] = {}
    candidates = [data] if isinstance(data, dict) else []
    if isinstance(data, list) and data and isinstance(data[0], dict):
        candidates.append(data[0])
    for obj in candidates:
        for key in ACCESS_NOTE_KEYS:
            if key in obj and key not in notes:
                notes[key] = obj[key]
    return notes


def capture_copies() -> list[dict]:
    entries: list[dict] = []
    for spec in COPY_SPECS:
        src = WS / spec["source"]
        dst = WS / spec["destination"]
        entry: dict = {
            "fixture_id": spec["fixture_id"],
            "kind": "copied_snapshot",
            "label": "copied_snapshot",
            "source_path": spec["source"],
            "destination_path": spec["destination"],
            "scope": spec["scope"],
        }
        problem = deny_reason(spec["source"])
        if problem:
            entry.update(status="skipped_denylist", reason=problem, stable=None)
            entries.append(entry)
            continue
        if not src.is_file():
            entry.update(status="skipped_missing_source", stable=None)
            entries.append(entry)
            continue
        if is_within(src, STAGING):
            entry.update(status="skipped_source_inside_staging", stable=None)
            entries.append(entry)
            continue
        size = src.stat().st_size
        if size > MAX_BYTES:
            entry.update(status="skipped_too_large", size_bytes=size, stable=None)
            entries.append(entry)
            continue

        before = sha256_file(src)
        mtime = datetime.fromtimestamp(src.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        payload = src.read_bytes()
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(payload)
        after = sha256_file(src)
        dest_hash = sha256_bytes(dst.read_bytes())
        stable = before == after
        entry.update(
            source_sha256_before=before,
            source_sha256_after=after,
            source_bytes=size,
            source_mtime_local=mtime,
            destination_sha256=dest_hash,
            destination_bytes=dst.stat().st_size,
            content_matches=dest_hash == before,
            stable=stable,
            copied_at_local=now_local(),
            access_notes_from_source=access_notes(src),
        )
        if stable and dest_hash == before:
            entry["status"] = "copied"
        elif not stable:
            dst.unlink(missing_ok=True)
            entry["status"] = "deferred_unstable"
            entry["reason"] = "source hash changed between the before/after reads; copy removed and the source is not copied again"
        else:
            dst.unlink(missing_ok=True)
            entry["status"] = "deferred_copy_mismatch"
            entry["reason"] = "destination hash differs from the source hash"
        entries.append(entry)
    return entries


def record_synthetics() -> list[dict]:
    entries: list[dict] = []
    for spec in SYNTHETIC_SPECS:
        dst = WS / spec["destination"]
        entry: dict = {
            "fixture_id": spec["fixture_id"],
            "kind": "synthetic",
            "label": "synthetic_fixture",
            "source_path": None,
            "destination_path": spec["destination"],
            "scope": spec["scope"],
            "access_notes_from_source": {},
        }
        if not dst.is_file():
            entry.update(status="missing_synthetic_fixture", stable=None)
            entries.append(entry)
            continue
        text = dst.read_text(encoding="utf-8")
        declared = '"fixture_kind": "synthetic"' in text
        entry.update(
            destination_sha256=sha256_bytes(dst.read_bytes()),
            destination_bytes=dst.stat().st_size,
            stable=True,
            content_matches=None,
            synthetic_marker_present=declared,
            status="present" if declared else "present_marker_missing",
        )
        entries.append(entry)
    return entries


def build_manifest(entries: list[dict]) -> dict:
    by_kind: dict[str, int] = {}
    for e in entries:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
    copied_ok = [e for e in entries if e.get("status") == "copied"]
    return {
        "schema": "examdata.integration.fixture-provenance/1",
        "generated_at_local": now_local(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": SELF_REL,
        "generator_sha256": sha256_file(WS / SELF_REL),
        "staging_root": STAGING.as_posix(),
        "workspace_root": WS.as_posix(),
        "policy": {
            "max_bytes": MAX_BYTES,
            "deny_dir_parts": sorted(DENY_DIR_PARTS),
            "deny_suffixes": list(DENY_SUFFIXES),
            "deny_path_prefixes": list(DENY_PATH_PREFIXES),
            "rules": [
                "no credentials, databases, caches, virtualenvs, build output or archives",
                "no examination material and no active-owner (materials/timetable) code or data",
                "sources must be inside the workspace and outside the staging tree",
                "a source whose hash changes across the copy is marked deferred_unstable and removed",
            ],
        },
        "summary": {
            "entries": len(entries),
            "by_kind": by_kind,
            "copied": len(copied_ok),
            "copied_bytes": sum(e.get("destination_bytes") or 0 for e in copied_ok),
            "synthetic": len([e for e in entries if e["kind"] == "synthetic"]),
            "deferred": len([e for e in entries if str(e.get("status", "")).startswith("deferred")]),
            "skipped": len([e for e in entries if str(e.get("status", "")).startswith("skipped")]),
        },
        "entries": entries,
        "deferred_sources": DEFERRED_SOURCES,
    }


def write_markdown(manifest: dict) -> None:
    lines = [
        "# A03 fixture provenance",
        "",
        f"- schema: `{manifest['schema']}`",
        f"- generated: {manifest['generated_at_local']} (local) / {manifest['generated_at_utc']} (UTC)",
        f"- generator: `{manifest['generator']}` (sha256 `{manifest['generator_sha256']}`)",
        f"- summary: {json.dumps(manifest['summary'], sort_keys=True)}",
        "",
        "## Copied fixtures (`copied_snapshot`)",
        "",
        "| fixture | source | source sha256 (before == after) | dest sha256 | bytes | status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for e in manifest["entries"]:
        if e["kind"] != "copied_snapshot":
            continue
        lines.append(
            "| {id} | `{src}` | `{sb}` | `{db}` | {n} | {st} |".format(
                id=e["fixture_id"], src=e.get("source_path"), sb=(e.get("source_sha256_before") or "—")[:16],
                db=(e.get("destination_sha256") or "—")[:16], n=e.get("destination_bytes", "—"),
                st=e.get("status"),
            )
        )
    lines += [
        "",
        "## Synthetic fixtures (`synthetic_fixture`)",
        "",
        "| fixture | destination | bytes | synthetic marker | scope |",
        "| --- | --- | --- | --- | --- |",
    ]
    for e in manifest["entries"]:
        if e["kind"] != "synthetic":
            continue
        lines.append(
            "| {id} | `{dst}` | {n} | {mk} | {sc} |".format(
                id=e["fixture_id"], dst=e["destination_path"], n=e.get("destination_bytes", "—"),
                mk=e.get("synthetic_marker_present"), sc=e.get("scope", ""),
            )
        )
    lines += ["", "## Sources inspected and deferred", "", "| source | status | reason |", "| --- | --- | --- |"]
    for d in manifest["deferred_sources"]:
        lines.append(f"| `{d['source']}` | {d['status']} | {d['reason']} |")
    lines += [
        "",
        "Scope notes:",
        "",
        "- Copied fixtures are byte-identical snapshots of small, non-active JSON metadata files; "
        "they contain no credentials, no database, no examination question text and no timetable data.",
        "- Synthetic fixtures are hand-authored, contain no upstream data, and carry "
        "`\"fixture_kind\": \"synthetic\"` inside the file.",
        "- The manifest is the authority for fixture integrity; "
        "`integration-staging/tests/test_fixture_provenance.py` verifies it against the files on disk.",
        "",
    ]
    MANIFEST_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def run_check() -> int:
    """Verify the manifest against the files on disk without copying anything."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems: list[str] = []
    for e in manifest["entries"]:
        dst = WS / e["destination_path"]
        if not dst.is_file():
            if str(e.get("status", "")).startswith("deferred"):
                continue
            problems.append(f"{e['fixture_id']}: destination missing ({e['destination_path']})")
            continue
        disk = sha256_file(dst)
        if disk != e.get("destination_sha256"):
            problems.append(f"{e['fixture_id']}: destination hash mismatch")
        if not is_within(dst, FIXTURES):
            problems.append(f"{e['fixture_id']}: destination outside the fixture root")
        if e["kind"] == "copied_snapshot" and e.get("status") == "copied":
            src = WS / e["source_path"]
            if src.is_file() and sha256_file(src) != e["source_sha256_before"]:
                problems.append(f"{e['fixture_id']}: source has changed since capture (snapshot still valid)")
    gen = sha256_file(WS / SELF_REL)
    if gen != manifest["generator_sha256"]:
        problems.append("generator hash differs from the manifest (re-run the capture to refresh)")
    print(json.dumps({"check": "a03_fixture_provenance", "entries": len(manifest["entries"]),
                      "problems": problems}, ensure_ascii=False, indent=2))
    return 0 if not problems else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return run_check()

    entries = capture_copies() + record_synthetics()
    manifest = build_manifest(entries)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_markdown(manifest)

    for e in entries:
        print(f"{e['kind']:16s} {e.get('status'):26s} {e['destination_path']}")
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    problems = [e["fixture_id"] for e in entries
                if e.get("status") in ("deferred_copy_mismatch", "missing_synthetic_fixture", "present_marker_missing")]
    print(f"manifest={MANIFEST} entries={len(entries)} problems={problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
