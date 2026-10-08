#!/usr/bin/env python3
"""A13 frontend provenance: reconcile the staged frontend copy with the original.

Usage:
  python a13_frontend_provenance.py           # (re)generate both manifests
  python a13_frontend_provenance.py --check   # verify manifests against disk; rc!=0 on drift

Manifests:
  integration-staging/frontend/PROVENANCE.json          (copied/modified/new files)
  integration-staging/frontend/fixtures/PROVENANCE.json (synthetic fixtures)
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
TOOLS = HERE.parent            # integration-staging/tools
STAGING = TOOLS.parent         # integration-staging
PROJECT = STAGING.parent       # project root
STAGED_FRONTEND = STAGING / 'frontend'
SOURCE_FRONTEND = PROJECT / 'frontend'
STAGED_FIXTURES = STAGED_FRONTEND / 'fixtures'

MANIFEST = STAGED_FRONTEND / 'PROVENANCE.json'
FIXTURE_MANIFEST = STAGED_FIXTURES / 'PROVENANCE.json'

COPIED = [
    ('index.html', 'modified_copy'),
    ('app.js', 'modified_copy'),
    ('styles.css', 'copied_snapshot'),
    ('search.mjs', 'copied_snapshot'),
    ('README.md', 'modified_copy'),
    ('tests/search.test.mjs', 'modified_copy'),
]
NEW_FILES = [
    'client.mjs',
    'fixture-server.mjs',
    'tests/client.test.mjs',
    'tests/flow.test.mjs',
]
FIXTURES = ['catalog.json', 'syllabi.json', 'resources.json']

# staged relative path -> original source file (default: frontend/<name>)
SOURCE_OVERRIDES = {
    'tests/search.test.mjs': SOURCE_FRONTEND / 'search.test.mjs',
}

CHANGES = {
    'app.js': [
        "added import {searchDocuments,clientEnabled} from './client.mjs'",
        "removed dead const params and the unused async api() helper that fetched '/gateway'",
        "liveSearch() calls searchDocuments() (per-season fan-out); honors the examdata.v2-client flag; results note labels staged fixture validation origin",
        "detail() source label shows 'STAGED FIXTURE \u00b7 \u5408\u6210\u5939\u5177' for rows with quality==='synthetic_fixture'",
    ],
    'index.html': [
        'inserted #staged-banner notice after the site header (staged fixture validation wording)',
    ],
    'README.md': [
        'rewritten as staged-copy notes (staged != merged, offline run, Phase B merge requirements); shares only the file name with the original document, which the merge must reconcile',
    ],
    'tests/search.test.mjs': [
        'keeps the 10 subject/paper normalization tests verbatim (original lines 1-14); module import repointed to ../search.mjs; the resources.mjs test block (original lines 15-39) is retired with the staged copy; line endings normalised to LF',
    ],
}

NEW_FILE_NOTES = {
    'client.mjs': 'staged v2 API client: envelope parsing, typed errors, per-season fan-out, resource->document mapping',
    'fixture-server.mjs': 'offline fixture server speaking the staged /api/v2 envelope over private fixtures',
    'tests/client.test.mjs': 'client.mjs unit tests over injected fetch (envelope, errors, fan-out, mapping)',
    'tests/flow.test.mjs': 'end-to-end flow tests against the in-process fixture server',
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build_manifest() -> dict:
    files = []
    for name, kind in COPIED:
        staged = STAGED_FRONTEND / name
        source = SOURCE_OVERRIDES.get(name) or SOURCE_FRONTEND / name
        files.append({
            'path': name,
            'kind': kind,
            'source_path': source.relative_to(PROJECT).as_posix(),
            'source_sha256': sha256_file(source),
            'staged_sha256': sha256_file(staged),
            'changes': CHANGES.get(name, []),
        })
    for name in NEW_FILES:
        staged = STAGED_FRONTEND / name
        files.append({
            'path': name,
            'kind': 'new_file',
            'source_path': None,
            'source_sha256': None,
            'staged_sha256': sha256_file(staged),
            'changes': [NEW_FILE_NOTES[name]],
        })
    return {
        'provenance_version': 'frontend-provenance/1',
        'generated_by': 'tools/a13_frontend_provenance.py',
        'generated_at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),
        'source_root': 'frontend',
        'staged_root': 'integration-staging/frontend',
        'files': files,
    }


def build_fixture_manifest() -> dict:
    files = []
    for name in FIXTURES:
        path = STAGED_FIXTURES / name
        files.append({
            'path': name,
            'sha256': sha256_file(path),
            'size_bytes': path.stat().st_size,
        })
    return {
        'provenance_version': 'fixture-provenance/1',
        'fixture_kind': 'synthetic',
        'generated_by': 'tools/a13_frontend_provenance.py',
        'generated_at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),
        'files': files,
    }


def write_json(path: Path, payload: dict) -> None:
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write('\n')


def check() -> int:
    problems: list[str] = []
    if not MANIFEST.exists():
        print(f'A13_FRONTEND_PROVENANCE: FAIL\n- missing manifest {MANIFEST}')
        return 1
    if not FIXTURE_MANIFEST.exists():
        print(f'A13_FRONTEND_PROVENANCE: FAIL\n- missing manifest {FIXTURE_MANIFEST}')
        return 1

    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if manifest.get('provenance_version') != 'frontend-provenance/1':
        problems.append(f'frontend manifest version unexpected: {manifest.get("provenance_version")!r}')
    expected_front = {name for name, _ in COPIED} | set(NEW_FILES)
    got_front = {e.get('path') for e in manifest.get('files', [])}
    if got_front != expected_front:
        problems.append(
            'frontend manifest file set mismatch: '
            f'missing {sorted(expected_front - got_front)}, extra {sorted(got_front - expected_front)}'
        )

    counts = {'copied': 0, 'new': 0}
    for entry in manifest.get('files', []):
        name = entry.get('path')
        staged = STAGED_FRONTEND / name
        if not staged.exists():
            problems.append(f'{name}: staged file missing')
            continue
        staged_hash = sha256_file(staged)
        if staged_hash != entry.get('staged_sha256'):
            problems.append(f'{name}: staged sha256 drifted from manifest')
        source_path = entry.get('source_path')
        if source_path:
            source = PROJECT / source_path
            if not source.exists():
                problems.append(f'{name}: source {source_path} missing')
            else:
                source_hash = sha256_file(source)
                if source_hash != entry.get('source_sha256'):
                    problems.append(f'{name}: source {source_path} changed since manifest was written')
                if entry.get('kind') == 'copied_snapshot' and source_hash != staged_hash:
                    problems.append(f'{name}: copied_snapshot no longer byte-identical to source')
            counts['copied'] += 1
        elif entry.get('kind') == 'new_file':
            counts['new'] += 1
        else:
            problems.append(f'{name}: unknown kind {entry.get("kind")!r}')

    fixture_manifest = json.loads(FIXTURE_MANIFEST.read_text(encoding='utf-8'))
    if fixture_manifest.get('provenance_version') != 'fixture-provenance/1':
        problems.append(f'fixture manifest version unexpected: {fixture_manifest.get("provenance_version")!r}')
    if fixture_manifest.get('fixture_kind') != 'synthetic':
        problems.append('fixture manifest is not marked synthetic')
    got_fixtures = {e.get('path') for e in fixture_manifest.get('files', [])}
    if got_fixtures != set(FIXTURES):
        problems.append(
            'fixture manifest file set mismatch: '
            f'missing {sorted(set(FIXTURES) - got_fixtures)}, extra {sorted(got_fixtures - set(FIXTURES))}'
        )
    fixtures_ok = 0
    for entry in fixture_manifest.get('files', []):
        path = STAGED_FIXTURES / entry.get('path', '')
        if not path.exists():
            problems.append(f'fixtures/{entry.get("path")}: missing')
            continue
        if sha256_file(path) != entry.get('sha256') or path.stat().st_size != entry.get('size_bytes'):
            problems.append(f'fixtures/{entry.get("path")}: drifted from manifest')
            continue
        fixtures_ok += 1

    if problems:
        print('A13_FRONTEND_PROVENANCE: FAIL')
        for p in problems:
            print(f'- {p}')
        return 1
    print(
        f'A13_FRONTEND_PROVENANCE: PASS '
        f'({counts["copied"]} copied, {counts["new"]} new, {fixtures_ok} fixtures)'
    )
    return 0


def main() -> int:
    if '--check' in sys.argv[1:]:
        return check()
    write_json(MANIFEST, build_manifest())
    write_json(FIXTURE_MANIFEST, build_fixture_manifest())
    print(f'wrote {MANIFEST.relative_to(PROJECT).as_posix()}')
    print(f'wrote {FIXTURE_MANIFEST.relative_to(PROJECT).as_posix()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
