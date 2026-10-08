"""A07: the CIE adapter maps a raw index without losing source information."""
from __future__ import annotations

import json
from pathlib import Path

from examdata_integration.adapters import CIEIndexAdapter
from examdata_integration.adapters.problems import ProblemCode

STAGING = Path(__file__).resolve().parents[1]
FIXTURE = STAGING / "fixtures" / "synthetic" / "adapters" / "cie-index-adapters.json"


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _bundle():
    return CIEIndexAdapter(FIXTURE).bundle()


def _codes(bundle):
    return [p.code for p in bundle.problems]


def test_bundle_counts_match_the_fixture():
    bundle = _bundle()
    counts = bundle.to_dict()["counts"]
    assert counts["courses"] == 1
    assert counts["containers"] == 1
    assert counts["questions"] == 4
    assert counts["regions"] == 6
    assert counts["assets"] == 2
    assert counts["answers"] == 7


def test_course_preserves_native_code_and_alias():
    course = _bundle().courses[0]
    assert course.native_code == "8888"
    assert course.aliases == ["adapter-subject"]
    assert course.system.value == "cie"


def test_container_native_identity_matches_the_fixture():
    fixture = _fixture()
    container = _bundle().containers[0]
    for key in ("subject", "year", "season", "paper", "date"):
        assert container.native_identity[key] == fixture["identity"].get(key)
    assert container.native_identity["date"] is None


def test_question_hierarchy_is_preserved():
    questions = {q.native_id: q for q in _bundle().walk_questions()}
    assert set(questions) == {"1", "1(a)", "1(b)", "2", "3", "3(a)", "4"}
    assert [c.native_id for c in questions["1"].children] == ["1(a)", "1(b)"]
    assert questions["1(a)"].number_path == ["1", "1(a)"]
    assert questions["1(a)"].parent_ref == "1"
    assert questions["4"].parent_ref is None


def test_question_stems_and_marks_match_the_fixture():
    fixture = _fixture()
    questions = {q.native_id: q for q in _bundle().walk_questions()}
    for raw in fixture["questions"]:
        native = str(raw["question"])
        assert questions[native].stem == raw["text"]
        assert questions[native].marks == raw["marks"]


def test_descendants_answer_is_derived_from_the_parts_in_order():
    questions = {q.native_id: q for q in _bundle().walk_questions()}
    answer = questions["1"].answers[0]
    assert answer.alternatives == ["answer-a", "answer-b"]
    assert answer.matching_method.value == "descendants"


def test_exact_and_ancestor_answers_are_resolved_as_declared():
    questions = {q.native_id: q for q in _bundle().walk_questions()}
    assert questions["1(a)"].answers[0].original_value == "answer-a"
    assert questions["1(a)"].answers[0].matching_method.value == "exact"
    assert questions["2"].answers[0].original_value == "answer-2"
    inherited = questions["3(a)"].answers[0]
    assert inherited.original_value == "answer-3-parent"
    assert inherited.matching_method.value == "ancestor"
    assert inherited.lineage.parent_refs == ["3"]


def test_documents_map_to_resources_and_assets_without_rewriting_hashes():
    fixture = _fixture()
    bundle = _bundle()
    container = bundle.containers[0]
    assert container.resources == [
        {"role": d["role"], "sha256": d["sha256"]} for d in fixture["documents"]]
    assert [a.sha256 for a in bundle.assets] == [d["sha256"] for d in fixture["documents"]]
    assert [a.media_type for a in bundle.assets] == ["application/pdf", "application/pdf"]


def test_multi_region_and_rotation_metadata_are_preserved():
    regions = _bundle().regions
    assert [r.page for r in regions] == [2, 2, 3, 9, 3, 4]
    assert [r.bbox for r in regions][:2] == [[40.0, 100.0, 300.0, 160.0],
                                             [40.0, 180.0, 300.0, 240.0]]
    assert regions[0].rotation_transform == [0, 1, -1, 0, 0, 0]
    assert regions[3].rotation_transform is None
    assert regions[5].rotation_transform == [-1, 0, 0, -1, 595, 842]


def test_conflicting_region_hash_is_preserved_verbatim():
    fixture = _fixture()
    cited = fixture["questions"][3]["regions"][0]["document_sha256"]
    regions = _bundle().regions
    assert regions[5].document_sha256 == cited
    assert cited != fixture["documents"][0]["sha256"]


def test_problem_codes_are_exactly_the_fixture_irregularities():
    codes = sorted(_codes(_bundle()))
    assert codes == sorted([ProblemCode.MISSING_MS.value, ProblemCode.UNKNOWN_DATE.value,
                            ProblemCode.UNKNOWN_ROTATION.value, ProblemCode.HASH_CONFLICT.value])


def test_problems_map_to_frozen_contract_gaps():
    gaps = {g.code for g in _bundle().gaps()}
    assert gaps == {"missing_document_hash", "unknown_date", "unverified_content"}


def test_everything_stays_synthetic_and_unverified():
    bundle = _bundle()
    for question in bundle.walk_questions():
        assert question.content_class.value == "synthetic"
        for answer in question.answers:
            assert answer.verification == "unverified"
            assert answer.content_class.value == "synthetic"
    for region in bundle.regions:
        assert region.evidence_status == "unverified"


def test_public_ids_are_deterministic_across_reads():
    first = [q.public_id for q in _bundle().walk_questions()]
    second = [q.public_id for q in _bundle().walk_questions()]
    assert first == second
    assert all(pid.startswith("q_") for pid in first)


def test_question_public_ids_are_unique():
    ids = [q.public_id for q in _bundle().walk_questions()]
    assert len(set(ids)) == len(ids)


def test_container_lists_every_question_reference():
    bundle = _bundle()
    refs = set(bundle.containers[0].question_refs)
    assert refs == {q.public_id for q in bundle.walk_questions()}


def test_missing_index_yields_an_empty_bundle_with_one_problem():
    bundle = CIEIndexAdapter(FIXTURE.parent / "nope.json").bundle()
    assert bundle.courses == [] and bundle.questions == []
    assert _codes(bundle) == [ProblemCode.MISSING_INDEX.value]
