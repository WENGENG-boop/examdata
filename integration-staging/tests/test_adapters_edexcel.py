"""A07: the Edexcel adapter maps a raw subject index without losing information."""
from __future__ import annotations

import json
from pathlib import Path

from examdata_integration.adapters import EdexcelIndexAdapter
from examdata_integration.adapters.problems import ProblemCode

STAGING = Path(__file__).resolve().parents[1]
FIXTURE = STAGING / "fixtures" / "synthetic" / "adapters" / "edexcel-index-adapters.json"


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _bundle():
    return EdexcelIndexAdapter(FIXTURE).bundle()


def _codes(bundle):
    return [p.code for p in bundle.problems]


def test_bundle_counts_match_the_fixture():
    counts = _bundle().to_dict()["counts"]
    assert counts == {"courses": 1, "containers": 3, "questions": 0,
                      "answers": 0, "regions": 1, "assets": 4}


def test_course_preserves_alias_qualification_and_specification():
    course = _bundle().courses[0]
    assert course.native_code == "adapter-ial-mathematics"
    assert course.aliases == ["WMA", "adapter-maths"]
    assert course.qualification == "IAL"
    assert course.specification_version == "SYN-IAL-MATHS-2020"
    assert course.system.value == "edexcel"


def test_container_native_identity_matches_each_unit():
    fixture = _fixture()
    units = [u for s in fixture["subjects"] for u in s["units"]]
    containers = _bundle().containers
    assert [c.native_identity["unit_code"] for c in containers] == \
           [u["unit_code"] for u in units]
    assert [c.native_identity["paper_code"] for c in containers] == \
           [u["paper_code"] for u in units]


def test_sessions_are_preserved_on_the_container():
    fixture = _fixture()
    units = [u for s in fixture["subjects"] for u in s["units"]]
    containers = _bundle().containers
    for container, unit in zip(containers, units):
        assert container.sections[0]["sessions"] == \
               [s["session"] for s in unit["sessions"]]


def test_resources_match_the_documents_of_each_unit():
    fixture = _fixture()
    units = [u for s in fixture["subjects"] for u in s["units"]]
    containers = _bundle().containers
    for container, unit in zip(containers, units):
        assert container.resources == [{"role": d["role"], "sha256": d["sha256"]}
                                       for d in unit["documents"]]


def test_missing_mark_scheme_is_reported_per_unit():
    assert _codes(_bundle()).count(ProblemCode.MISSING_MS.value) == 2


def test_unknown_session_dates_are_reported_and_never_invented():
    bundle = _bundle()
    assert _codes(bundle).count(ProblemCode.UNKNOWN_DATE.value) == 4
    for container in bundle.containers:
        assert container.sections[0]["sessions"]  # labels kept
        assert "date" not in container.native_identity


def test_conflicting_region_hash_is_preserved():
    fixture = _fixture()
    unit = fixture["subjects"][0]["units"][2]
    region = _bundle().regions[0]
    assert region.document_sha256 == unit["regions"][0]["document_sha256"]
    assert region.document_sha256 != unit["documents"][0]["sha256"]
    assert _codes(_bundle()).count(ProblemCode.HASH_CONFLICT.value) == 1


def test_problem_codes_are_exactly_the_fixture_irregularities():
    assert sorted(set(_codes(_bundle()))) == sorted(
        [ProblemCode.MISSING_MS.value, ProblemCode.UNKNOWN_DATE.value,
         ProblemCode.HASH_CONFLICT.value])


def test_no_questions_or_answers_are_invented():
    bundle = _bundle()
    assert bundle.questions == []
    assert bundle.answers == []


def test_everything_stays_synthetic_and_unverified():
    bundle = _bundle()
    for container in bundle.containers:
        assert container.content_class.value == "synthetic"
    for region in bundle.regions:
        assert region.evidence_status == "unverified"


def test_public_ids_are_deterministic_across_reads():
    first = [c.public_id for c in _bundle().containers]
    second = [c.public_id for c in _bundle().containers]
    assert first == second
    assert len(set(first)) == 3


def test_missing_index_yields_an_empty_bundle_with_one_problem():
    bundle = EdexcelIndexAdapter(FIXTURE.parent / "nope.json").bundle()
    assert bundle.courses == [] and bundle.containers == []
    assert _codes(bundle) == [ProblemCode.MISSING_INDEX.value]
