#!/usr/bin/env python3
"""A08 read-adapter probe: exercise the IELTS and TOEFL adapters offline.

Offline, stdlib-only, private staged fixtures and copied snapshots. Reads the A08
synthetic fixtures and the copied snapshots plus a handful of in-memory edge
cases, and prints a stable transcript to stdout; the closing-checks tool captures
it to `docs/integration/execution/evidence/A08/adapters_stdout.txt`. Exits
non-zero if any scenario fails.

Nothing original is read, no database or network is touched, no URL is requested,
and no answer, page, date or alignment is ever promoted past its evidence.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
SYNTH = STAGING / "fixtures" / "synthetic" / "ielts-toefl"
COPIED = STAGING / "fixtures" / "copied"
A03_IELTS = STAGING / "fixtures" / "synthetic" / "ielts" / "questions-synthetic.json"
SCRATCH = STAGING / "runtime" / "tmp" / "a08-probe"

sys.path.insert(0, str(SRC))
# R04: product code resolves its deployment root explicitly (never by directory name).
os.environ.setdefault("EXAMDATA_INTEGRATION_ROOT", str(STAGING))

from examdata_integration.adapters.ielts import (  # noqa: E402
    IELTSAudioAdapter,
    IELTSQuestionsAdapter,
    IELTSRevisionAdapter,
    IELTSPagesAdapter,
)
from examdata_integration.adapters.source_reader import (  # noqa: E402
    SourceKind,
    SourceProblemCode,
    classify_path,
    iter_cache_entries,
    read_source,
    validate_kmf_url,
)
from examdata_integration.adapters.toefl import (  # noqa: E402
    TOEFLCacheAdapter,
    TOEFLQuestionSetAdapter,
    TOEFLReadingIndexAdapter,
)

IELTS_QUESTIONS = SYNTH / "ielts-questions-a08-synthetic.json"
IELTS_AUDIO = SYNTH / "ielts-audio-synthetic.json"
TOEFL_SETS = SYNTH / "toefl-questions-synthetic.json"
TOEFL_BAD_CACHE = SYNTH / "toefl-bad-cache-synthetic.json"
READING_INDEX = COPIED / "toefl" / "ddy-index.json"
PRINTED_PAGES = COPIED / "ielts" / "printed-pages.json"
PDF_PROVENANCE = COPIED / "ielts" / "pdf-provenance.json"
INDEXES = COPIED / "ielts" / "indexes-current.json"
MANIFESTS = COPIED / "ielts" / "manifests-current.json"

failures: list[str] = []


def expect(name: str, condition: bool, detail: str = "") -> None:
    print(f"[{'ok' if condition else 'FAIL'}] {name}{(' :: ' + detail) if detail else ''}")
    if not condition:
        failures.append(name)


def codes(bundle) -> list[str]:
    return [p.code for p in bundle.problems]


def by_id(bundle) -> dict:
    return {q.native_id: q for q in bundle.questions}


def main() -> int:
    print("=== A08 read-adapter probe ===")
    print("synthetic fixtures:", SYNTH)
    print("copied snapshots:", COPIED)
    required = [IELTS_QUESTIONS, IELTS_AUDIO, TOEFL_SETS, TOEFL_BAD_CACHE,
                READING_INDEX, PRINTED_PAGES, PDF_PROVENANCE, INDEXES, MANIFESTS]
    if not all(p.is_file() for p in required):
        print("A08_PROBE: FAIL (a staged source is missing)")
        return 1
    SCRATCH.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------- source reader --
    print("\n-- source reader --")
    expect("read.classify_kinds",
           classify_path(READING_INDEX) is SourceKind.COPIED_SNAPSHOT
           and classify_path(IELTS_QUESTIONS) is SourceKind.SYNTHETIC
           and classify_path(WS / "examdata" / "README.md") is SourceKind.OUTSIDE_STAGING)
    data, kind, problems = read_source(WS / "examdata" / "README.md")
    expect("read.outside_staging_not_opened",
           data is None and kind is SourceKind.OUTSIDE_STAGING
           and [p.code for p in problems] == [SourceProblemCode.OUTSIDE_STAGING.value])
    data, kind, problems = read_source(READING_INDEX, allowed_kinds=(SourceKind.SYNTHETIC,))
    expect("read.wrong_kind_rejected",
           data is None and [p.code for p in problems]
           == [SourceProblemCode.WRONG_SOURCE_KIND.value])
    expect("read.kmf_url_shape",
           validate_kmf_url("https://toefl.kmf.com/detail/read/51ehlj.html/1")[0]
           and not validate_kmf_url("http://mirror.example/detail/read/x.html")[0])
    entries = iter_cache_entries(
        {"entries": [{"native_id": "a"}, "x", {"native_id": "a"}]}, source_name="mem")
    expect("read.cache_entries_reported",
           [e.native_id for e in entries] == ["a", None, "a"]
           and sum(1 for e in entries if e.problem) == 2)

    # --------------------------------------------------- IELTS questions --
    print("\n-- IELTS question set (A03 book fixture) --")
    a03 = IELTSQuestionsAdapter(A03_IELTS).bundle()
    ids = by_id(a03)
    expect("ielts.q41_missing_slot_preserved",
           ids["Q41"].answers == [] and ids["Q41"].payload.raw["answer_slot"] == 41
           and ids["Q41"].quality.answer_presence.value == "missing"
           and SourceProblemCode.MISSING_ANSWER_SLOT.value in codes(a03))
    expect("ielts.grouped_alternatives",
           [o.key for o in ids["Q2"].payload.options] == ["B", "A", "C", "D"]
           and ids["Q2"].answers[0].matching_method.value == "grouped")
    expect("ielts.table_structure",
           len(ids["Q4"].payload.columns) == 3 and len(ids["Q4"].payload.rows) == 2
           and [(c.row, c.column) for c in ids["Q4"].payload.answer_cells] == [(2, 3)])
    expect("ielts.question_hierarchy",
           [c.native_id for c in ids["Q3"].children] == ["Q3.i", "Q3.ii"]
           and ids["Q3"].parent_ref is None
           and SourceProblemCode.UNRESOLVED_IDENTITY.value in codes(a03))
    expect("ielts.answer_conflict_preserved",
           len(ids["Q5"].answers[0].conflicts) == 2
           and ids["Q5"].answers[0].manual_decision is None
           and SourceProblemCode.ANSWER_CONFLICT.value in codes(a03))
    expect("ielts.no_answer_upgraded",
           all(a.verification == "unverified" for a in a03.answers))

    print("\n-- IELTS question set (A08 variant fixture) --")
    a08 = IELTSQuestionsAdapter(IELTS_QUESTIONS).bundle()
    ids = by_id(a08)
    expect("ielts.variant_kept", a08.source["variant"] == "academic")
    expect("ielts.edition_unresolved",
           a08.containers[0].sections[0]["edition_uncertain"] is True
           and SourceProblemCode.UNRESOLVED_EDITION.value in codes(a08))
    expect("ielts.special_numbering_kept",
           "numbering=7(b)(ii)" in ids["S2Q7"].lineage.note
           and ids["S2Q7"].answers[0].source.locator["raw_source_id"]
           == "synthetic-src-0007")

    # ------------------------------------------------------ IELTS audio --
    print("\n-- IELTS audio alignment --")
    tracks, audio_problems = IELTSAudioAdapter(IELTS_AUDIO).tracks()
    effective = {t.native_id: t.alignment_effective for t in tracks}
    declared = {t.native_id: t.alignment_declared for t in tracks}
    expect("audio.verified_claim_capped",
           declared["track-1"] == "verified" and effective["track-1"] == "unverified"
           and [p.native_ref for p in audio_problems
                if p.code == SourceProblemCode.UNVERIFIED_CONTENT.value] == ["track-1"])
    expect("audio.states_distinct",
           effective["track-2"] == "unverified" and effective["track-3"] == "unknown"
           and effective["track-4"] == "not_applicable")
    expect("audio.no_offset_invented",
           [t for t in tracks if t.native_id == "track-2"][0].segments
           == [{"question": "Q2", "start": None, "end": None}]
           and [p.native_ref for p in audio_problems
                if p.code == SourceProblemCode.MISSING_TIME_WINDOW.value] == ["track-2"])

    # ------------------------------------------------- IELTS copied pages --
    print("\n-- IELTS copied page map + provenance --")
    pages = IELTSPagesAdapter(PRINTED_PAGES, PDF_PROVENANCE).bundle()
    unresolved = [p for p in pages.problems
                  if p.code == SourceProblemCode.UNRESOLVED_PAGE.value]
    expect("pages.unresolved_reported",
           pages.source["printed_pages_total"] == 664
           and pages.source["printed_pages_unresolved"] == len(unresolved) == 137)
    expect("pages.hashes_mapped",
           len(pages.assets) == 133
           and sum(1 for a in pages.assets if a.media_type == "application/pdf") == 9)
    revisions = IELTSRevisionAdapter(INDEXES, MANIFESTS).bundle()
    expect("pages.revision_pointer",
           revisions.source["revisions"]["indexes"] == "rev-8b21015ab64bb73c"
           and revisions.problems == [])

    # ------------------------------------------------------- TOEFL index --
    print("\n-- TOEFL copied reading index --")
    index = TOEFLReadingIndexAdapter(READING_INDEX).bundle()
    dup = [p for p in index.problems
           if p.code == SourceProblemCode.UNRESOLVED_IDENTITY.value]
    expect("toefl.index_one_container_per_passage",
           len(index.containers) == 72
           and len({c.public_id for c in index.containers}) == 72)
    expect("toefl.index_no_coverage_claim",
           index.source["declared_total"] == 72 and index.source["coverage_claimed"] is False
           and all(c.coverage is None for c in index.containers))
    expect("toefl.index_unresolved_identity",
           [p.native_ref for p in dup] == ["tpo-38-2", "tpo-38-2"])
    expect("toefl.index_real_urls_accepted",
           SourceProblemCode.INVALID_KMF_URL.value not in codes(index))

    # ------------------------------------------------------ TOEFL sets --
    print("\n-- TOEFL synthetic question sets --")
    sets = TOEFLQuestionSetAdapter(TOEFL_SETS).bundle()
    ids = by_id(sets)
    expect("toefl.identity_classes_distinct",
           sorted(c.native_code for c in sets.courses) == ["jj", "official", "tpo"]
           and len({c.public_id for c in sets.containers}) == 4)
    expect("toefl.table_rows",
           len(ids["T1"].payload.columns) == 3 and len(ids["T1"].payload.rows) == 2
           and [(c.row, c.column) for c in ids["T1"].payload.answer_cells] == [(2, 3)])
    expect("toefl.multiple_choice_count",
           [o.key for o in ids["T2"].payload.options] == ["A", "B", "C", "D", "E"]
           and ids["T2"].answers[0].matching_method.value == "in_any_order"
           and ids["T2"].answers[0].alternatives == ["C"])
    expect("toefl.missing_options_table",
           ids["T3"].payload.options == [] and ids["T4"].payload.rows == []
           and SourceProblemCode.MISSING_OPTIONS.value in codes(sets)
           and SourceProblemCode.MISSING_TABLE.value in codes(sets))
    expect("toefl.locked_jj_metadata_only",
           [c for c in sets.containers
            if c.native_identity["source_kind"] == "jj"][0].question_refs == []
           and SourceProblemCode.RESTRICTED_SOURCE.value in codes(sets))
    expect("toefl.unknown_dates",
           sorted(p.native_ref for p in sets.problems
                  if p.code == SourceProblemCode.UNKNOWN_DATE.value)
           == ["synthetic-badurl-1", "synthetic-jj-set-1", "synthetic-tpo-set-1"])
    expect("toefl.bad_url_reported",
           [p.native_ref for p in sets.problems
            if p.code == SourceProblemCode.INVALID_KMF_URL.value] == ["synthetic-badurl-1"])

    # -------------------------------------------------------- TOEFL cache --
    print("\n-- TOEFL cache reparse --")
    report = TOEFLCacheAdapter(TOEFL_BAD_CACHE).report()
    expect("toefl.cache_bad_entries_reported",
           len(report.entries) == 5
           and [e.native_id for e in report.usable] == ["cache-1", "cache-3"]
           and sum(1 for p in report.problems
                   if p.code == SourceProblemCode.BAD_CACHE_ENTRY.value) == 3)

    # --------------------------------------------------------- provenance --
    print("\n-- provenance --")
    for fixture in (IELTS_QUESTIONS, IELTS_AUDIO, TOEFL_SETS, TOEFL_BAD_CACHE):
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        expect(f"prov.synthetic.{fixture.stem}", payload.get("fixture_kind") == "synthetic")
        expect(f"prov.no_upgrade.{fixture.stem}",
               (payload.get("verification") or {}).get("status") == "synthetic")

    shutil.rmtree(SCRATCH, ignore_errors=True)

    print(f"\nA08_PROBE: {'PASS' if not failures else 'FAIL'} ({len(failures)} failing)")
    if failures:
        for name in failures:
            print(f"  failing: {name}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
