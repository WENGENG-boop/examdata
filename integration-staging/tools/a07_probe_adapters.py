#!/usr/bin/env python3
"""A07 adapter probe: exercise the CIE and Edexcel read adapters offline.

Offline, stdlib-only, private synthetic fixtures. Reads the two A07 adapter
fixtures plus a handful of in-memory / scratch edge cases and prints a stable
transcript to stdout; the closing-checks tool captures it to
`docs/integration/execution/evidence/A07/adapters_stdout.txt`. Exits non-zero if
any scenario fails.

Nothing original is read, no database or network is touched, and no answer or
region is ever promoted past ``unverified``.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
FIXTURES = STAGING / "fixtures" / "synthetic" / "adapters"
SCRATCH = STAGING / "runtime" / "tmp" / "a07-probe"

sys.path.insert(0, str(SRC))

from examdata_integration.adapters import (  # noqa: E402
    AnswerMode,
    CIEIndexAdapter,
    DocumentTable,
    EdexcelIndexAdapter,
    ProblemCode,
    build_regions,
    document_problems,
    page_rotation_table,
    read_index,
    resolve_answers,
    validate_index,
)
from examdata_integration.contracts.enums import AnswerMatchingMethod  # noqa: E402

CIE_FIXTURE = FIXTURES / "cie-index-adapters.json"
EDEXCEL_FIXTURE = FIXTURES / "edexcel-index-adapters.json"

failures: list[str] = []


def expect(name: str, condition: bool, detail: str = "") -> None:
    print(f"[{'ok' if condition else 'FAIL'}] {name}{(' :: ' + detail) if detail else ''}")
    if not condition:
        failures.append(name)


def codes(bundle) -> list[str]:
    return [p.code for p in bundle.problems]


def main() -> int:
    print("=== A07 adapter probe ===")
    print("fixtures:", FIXTURES)
    if not CIE_FIXTURE.is_file() or not EDEXCEL_FIXTURE.is_file():
        print("A07_PROBE: FAIL (adapter fixtures missing)")
        return 1

    # ------------------------------------------------------------------ CIE --
    print("\n-- CIE read adapter --")
    cie = CIEIndexAdapter(CIE_FIXTURE).bundle()
    expect("cie.system", cie.system.value == "cie")
    expect("cie.counts",
           len(cie.courses) == 1 and len(cie.containers) == 1
           and len(cie.questions) == 4 and len(cie.walk_questions()) == 7
           and len(cie.assets) == 2 and len(cie.regions) == 6 and len(cie.answers) == 7,
           f"counts={cie.to_dict()['counts']}")
    expect("cie.course_identity",
           cie.courses[0].native_code == "8888"
           and cie.courses[0].aliases == ["adapter-subject"])
    expect("cie.container_native_date_kept_unknown",
           cie.containers[0].native_identity.get("date") is None
           and cie.containers[0].native_identity.get("paper") == "21")
    expect("cie.container_resources_roles",
           [r["role"] for r in cie.containers[0].resources] == ["qp", "in"])

    # problem set: missing mark scheme, unknown date, hash conflict, unknown rotation
    got = sorted(codes(cie))
    want = sorted([ProblemCode.MISSING_MS.value, ProblemCode.UNKNOWN_DATE.value,
                   ProblemCode.HASH_CONFLICT.value, ProblemCode.UNKNOWN_ROTATION.value])
    expect("cie.problems_exact", got == want, f"got={got}")

    # gaps: only the problem codes that map to a frozen contract gap
    gaps = sorted(g.code for g in cie.gaps())
    expect("cie.gaps_mapped",
           gaps == sorted(["missing_document_hash", "unknown_date",
                           "unverified_content", "unverified_content"]),
           f"gaps={gaps}")

    # answer resolution semantics
    flat = {q.native_id: q for q in cie.walk_questions()}
    q1 = flat["1"]
    expect("cie.q1_descendants_derived",
           len(q1.answers) == 1
           and q1.answers[0].matching_method is AnswerMatchingMethod.DESCENDANTS
           and q1.answers[0].alternatives == ["answer-a", "answer-b"]
           and q1.answers[0].ordering_rule == "descendant_order"
           and q1.answers[0].original_value is None)
    q1a = flat["1(a)"]
    expect("cie.q1a_own_exact",
           len(q1a.answers) == 1
           and q1a.answers[0].matching_method is AnswerMatchingMethod.EXACT
           and q1a.answers[0].original_value == "answer-a")
    q3a = flat["3(a)"]
    expect("cie.q3a_inherited_ancestor",
           len(q3a.answers) == 1
           and q3a.answers[0].matching_method is AnswerMatchingMethod.ANCESTOR
           and q3a.answers[0].original_value == "answer-3-parent"
           and q3a.answers[0].lineage.parent_refs == ["3"])
    expect("cie.all_answers_unverified",
           all(a.verification == "unverified" and a.content_class.value == "synthetic"
               for a in cie.answers))
    expect("cie.no_missing_answer_in_this_fixture",
           ProblemCode.MISSING_ANSWER.value not in codes(cie))

    # regions: two per question where declared, rotation carried, conflicts preserved
    q2_regions = [r for r in cie.regions if r.lineage.parent_refs == ["2"]]
    expect("cie.q2_two_regions", len(q2_regions) == 2)
    by_page = {r.page: r for r in q2_regions}
    expect("cie.q2_page3_transform", by_page[3].rotation_transform == [1, 0, 0, 1, 0, 0])
    expect("cie.q2_page9_unknown_rotation_none_transform",
           by_page[9].rotation_transform is None
           and by_page[9].evidence_status == "unverified")
    q1_region = [r for r in cie.regions if r.lineage.parent_refs == ["1"]][0]
    expect("cie.q1_page2_transform", q1_region.rotation_transform == [0, 1, -1, 0, 0, 0])
    q4_region = [r for r in cie.regions if r.lineage.parent_refs == ["4"]][0]
    expect("cie.q4_hash_conflict_preserved",
           q4_region.document_sha256 == "c" * 64
           and q4_region.evidence_status == "unverified")
    expect("cie.regions_all_unverified",
           all(r.evidence_status == "unverified" for r in cie.regions))

    # -------------------------------------------------------------- Edexcel --
    print("\n-- Edexcel read adapter --")
    ed = EdexcelIndexAdapter(EDEXCEL_FIXTURE).bundle()
    expect("edexcel.system", ed.system.value == "edexcel")
    expect("edexcel.counts",
           len(ed.courses) == 1 and len(ed.containers) == 3
           and len(ed.questions) == 0 and len(ed.assets) == 4 and len(ed.regions) == 1,
           f"counts={ed.to_dict()['counts']}")
    expect("edexcel.course_aliases",
           ed.courses[0].native_code == "adapter-ial-mathematics"
           and ed.courses[0].aliases == ["WMA", "adapter-maths"]
           and ed.courses[0].specification_version == "SYN-IAL-MATHS-2020")
    ed_codes = codes(ed)
    expect("edexcel.missing_ms_two_units",
           ed_codes.count(ProblemCode.MISSING_MS.value) == 2,
           f"codes={sorted(ed_codes)}")
    expect("edexcel.unknown_dates_four_sessions",
           ed_codes.count(ProblemCode.UNKNOWN_DATE.value) == 4)
    expect("edexcel.hash_conflict_one",
           ed_codes.count(ProblemCode.HASH_CONFLICT.value) == 1)
    expect("edexcel.region_hash_conflict_preserved",
           ed.regions[0].document_sha256 == "2" * 64
           and ed.regions[0].evidence_status == "unverified")
    expect("edexcel.container_unit_codes",
           sorted(c.native_identity["unit_code"] for c in ed.containers)
           == ["WMA21", "WMA22", "WMA23"])

    # ------------------------------------------------------------- edge cases --
    print("\n-- edge cases (in-memory / scratch) --")
    SCRATCH.mkdir(parents=True, exist_ok=True)

    missing, mprobs = read_index(SCRATCH / "does-not-exist.json")
    expect("edge.missing_index",
           missing is None and [p.code for p in mprobs] == [ProblemCode.MISSING_INDEX.value])
    expect("edge.missing_index_gap",
           mprobs[0].to_gap() is not None and mprobs[0].to_gap().code == "deferred_source")

    bad = SCRATCH / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    parsed, bprobs = read_index(bad)
    expect("edge.invalid_json",
           parsed is None and [p.code for p in bprobs] == [ProblemCode.INVALID_JSON.value])

    nonobj = validate_index([1, 2, 3], source_name="list.json")
    expect("edge.non_object_json",
           nonobj[0] is None
           and [p.code for p in nonobj[1]] == [ProblemCode.INVALID_JSON.value])

    wrongkind = validate_index({"fixture_kind": "real", "schema_version": "1"})
    expect("edge.wrong_fixture_kind",
           wrongkind[0] is None
           and [p.code for p in wrongkind[1]] == [ProblemCode.WRONG_FIXTURE_KIND.value])

    badver = validate_index({"fixture_kind": "synthetic", "schema_version": "2"})
    expect("edge.unsupported_schema_version",
           badver[0] is None
           and [p.code for p in badver[1]]
           == [ProblemCode.UNSUPPORTED_SCHEMA_VERSION.value])

    # answer-mode resolution
    unknown_mode = resolve_answers(
        [{"question": "1", "answer_mode": "bogus"}],
        system="cie", container_native={}, source_id="s", provider_id="p",
        fixture_name="mem.json")
    expect("edge.unresolved_answer_mode",
           [p.code for p in unknown_mode.problems]
           == [ProblemCode.UNRESOLVED_ANSWER_MODE.value]
           and unknown_mode.for_question("1") == [])

    no_answer = resolve_answers(
        [{"question": "1", "answer_mode": "exact"}],
        system="cie", container_native={}, source_id="s", provider_id="p",
        fixture_name="mem.json")
    expect("edge.missing_answer_reported",
           [p.code for p in no_answer.problems] == [ProblemCode.MISSING_ANSWER.value]
           and no_answer.for_question("1") == [])

    none_mode = resolve_answers(
        [{"question": "1", "answer": "a", "answer_mode": "none",
          "parts": [{"question": "1(a)", "answer_mode": "none"}]}],
        system="cie", container_native={}, source_id="s", provider_id="p",
        fixture_name="mem.json")
    expect("edge.none_mode_keeps_own_only",
           len(none_mode.for_question("1")) == 1
           and none_mode.for_question("1(a)") == []
           and none_mode.problems == [])

    # region edge cases
    table = DocumentTable([{"role": "qp", "sha256": "a" * 64}])
    rot = page_rotation_table([{"page": 1, "rotation_degrees": 90,
                                "rotation_transform": [0, 1, -1, 0, 0, 0]}])
    no_bbox, nb_probs = build_regions(
        [{"page": 1, "document_role": "qp"}], doc_table=table, coordinate_system="cs",
        rotations=rot, system="cie", container_native={}, provider_id="p",
        fixture_name="mem.json", native_ref="1")
    expect("edge.missing_bbox",
           no_bbox[0].bbox == []
           and ProblemCode.MISSING_REGION_BBOX.value in [p.code for p in nb_probs])

    undeclared, ud_probs = build_regions(
        [{"page": 7, "bbox": [1, 2, 3, 4], "document_role": "qp"}], doc_table=table,
        coordinate_system="cs", rotations=rot, system="cie", container_native={},
        provider_id="p", fixture_name="mem.json", native_ref="1",
        rotations_declared=False)
    expect("edge.undeclared_page_silent",
           undeclared[0].rotation_transform is None and ud_probs == [])

    declared_missing, dm_probs = build_regions(
        [{"page": 7, "bbox": [1, 2, 3, 4], "document_role": "qp"}], doc_table=table,
        coordinate_system="cs", rotations=rot, system="cie", container_native={},
        provider_id="p", fixture_name="mem.json", native_ref="1",
        rotations_declared=True)
    expect("edge.declared_missing_page_unknown_rotation",
           declared_missing[0].rotation_transform is None
           and [p.code for p in dm_probs] == [ProblemCode.UNKNOWN_ROTATION.value])

    conflict_table = DocumentTable([{"role": "qp", "sha256": "a" * 64}])
    expect("edge.document_conflict_detected",
           conflict_table.conflicts_with("qp", "b" * 64)
           and not conflict_table.conflicts_with("qp", "a" * 64)
           and not conflict_table.conflicts_with("ms", "b" * 64))
    expect("edge.document_missing_ms",
           sorted(p.code for p in document_problems(DocumentTable([]), required_roles=("qp", "ms")))
           == sorted([ProblemCode.MISSING_MS.value, ProblemCode.MISSING_DOCUMENT_ROLE.value]))

    # ------------------------------------------------------------- provenance --
    print("\n-- provenance --")
    for fixture in (CIE_FIXTURE, EDEXCEL_FIXTURE):
        data = json.loads(fixture.read_text(encoding="utf-8"))
        expect(f"prov.synthetic.{fixture.stem}", data.get("fixture_kind") == "synthetic")

    # cleanup the scratch edge files (keep the probe side-effect free)
    shutil.rmtree(SCRATCH, ignore_errors=True)

    print(f"\nA07_PROBE: {'PASS' if not failures else 'FAIL'} ({len(failures)} failing)")
    if failures:
        for name in failures:
            print(f"  failing: {name}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
