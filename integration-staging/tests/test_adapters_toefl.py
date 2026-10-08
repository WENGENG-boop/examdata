"""A08: the TOEFL read adapters keep identities distinct and never request a URL."""
from __future__ import annotations

from pathlib import Path

from examdata_integration.adapters.source_reader import SourceProblemCode
from examdata_integration.adapters.toefl import (
    TOEFLCacheAdapter,
    TOEFLQuestionSetAdapter,
    TOEFLReadingIndexAdapter,
)
from examdata_integration.contracts.enums import (
    AnswerMatchingMethod,
    ContainerKind,
    QuestionType,
)

STAGING = Path(__file__).resolve().parents[1]
FIXTURES = STAGING / "fixtures"
READING_INDEX = FIXTURES / "copied" / "toefl" / "ddy-index.json"
QUESTION_SETS = FIXTURES / "synthetic" / "ielts-toefl" / "toefl-questions-synthetic.json"
BAD_CACHE = FIXTURES / "synthetic" / "ielts-toefl" / "toefl-bad-cache-synthetic.json"


def _codes(bundle):
    return [p.code for p in bundle.problems]


def _by_id(bundle):
    return {q.native_id: q for q in bundle.questions}


# -- copied reading index --------------------------------------------------- #
def test_reading_index_maps_one_container_per_passage():
    bundle = TOEFLReadingIndexAdapter(READING_INDEX).bundle()
    assert len(bundle.containers) == 72
    assert all(c.kind is ContainerKind.SET for c in bundle.containers)
    ids = {c.public_id for c in bundle.containers}
    assert len(ids) == 72  # every passage keeps a distinct identity


def test_reading_index_never_claims_completeness():
    bundle = TOEFLReadingIndexAdapter(READING_INDEX).bundle()
    assert bundle.source["declared_total"] == 72
    assert bundle.source["items_read"] == 72
    assert bundle.source["coverage_claimed"] is False
    assert all(c.coverage is None for c in bundle.containers)


def test_reading_index_reports_the_duplicate_hash_and_title_as_unresolved():
    bundle = TOEFLReadingIndexAdapter(READING_INDEX).bundle()
    unresolved = [p for p in bundle.problems
                  if p.code == SourceProblemCode.UNRESOLVED_IDENTITY.value]
    assert [p.native_ref for p in unresolved] == ["tpo-38-2", "tpo-38-2"]
    assert any("KMF hash" in p.detail for p in unresolved)
    assert any("title" in p.detail for p in unresolved)
    # the duplicated passages are never merged
    assert len(bundle.containers) == 72


def test_reading_index_accepts_every_real_kmf_link():
    bundle = TOEFLReadingIndexAdapter(READING_INDEX).bundle()
    assert SourceProblemCode.INVALID_KMF_URL.value not in _codes(bundle)


# -- synthetic question sets ------------------------------------------------ #
def test_question_sets_keep_official_tpo_and_jj_identities_distinct():
    bundle = TOEFLQuestionSetAdapter(QUESTION_SETS).bundle()
    assert sorted(c.native_code for c in bundle.courses) == ["jj", "official", "tpo"]
    kinds = sorted(c.native_identity["source_kind"] for c in bundle.containers)
    assert kinds == ["jj", "official", "tpo", "tpo"]
    assert len({c.public_id for c in bundle.containers}) == 4


def test_table_choice_keeps_rows_columns_and_the_answer_cell():
    bundle = TOEFLQuestionSetAdapter(QUESTION_SETS).bundle()
    t1 = _by_id(bundle)["T1"]
    assert t1.question_type is QuestionType.TABLE_CHOICE
    assert len(t1.payload.columns) == 3
    assert len(t1.payload.rows) == 2
    assert [(c.row, c.column) for c in t1.payload.answer_cells] == [(2, 3)]


def test_multiple_choice_keeps_the_option_count_and_selection():
    bundle = TOEFLQuestionSetAdapter(QUESTION_SETS).bundle()
    t2 = _by_id(bundle)["T2"]
    assert t2.question_type is QuestionType.MULTIPLE_CHOICE
    assert [o.key for o in t2.payload.options] == ["A", "B", "C", "D", "E"]
    answer = t2.answers[0]
    assert answer.matching_method is AnswerMatchingMethod.IN_ANY_ORDER
    assert answer.original_value == "A"
    assert answer.alternatives == ["C"]
    assert "selection_count=2" in answer.lineage.note
    assert answer.verification == "unverified"


def test_missing_options_and_table_are_reported_not_invented():
    bundle = TOEFLQuestionSetAdapter(QUESTION_SETS).bundle()
    ids = _by_id(bundle)
    assert ids["T3"].payload.options == []
    assert ids["T4"].payload.columns == [] and ids["T4"].payload.rows == []
    assert ids["T3"].answers == [] and ids["T4"].answers == []
    assert SourceProblemCode.MISSING_OPTIONS.value in _codes(bundle)
    assert SourceProblemCode.MISSING_TABLE.value in _codes(bundle)


def test_required_image_without_a_hash_is_a_missing_asset():
    bundle = TOEFLQuestionSetAdapter(QUESTION_SETS).bundle()
    t5 = _by_id(bundle)["T5"]
    assert [(a.role, a.sha256) for a in t5.required_assets] == [("diagram", None)]
    assert SourceProblemCode.MISSING_ASSET.value in _codes(bundle)


def test_restricted_jj_set_is_metadata_only():
    bundle = TOEFLQuestionSetAdapter(QUESTION_SETS).bundle()
    jj = [c for c in bundle.containers if c.native_identity["source_kind"] == "jj"]
    assert len(jj) == 1
    assert jj[0].sections[0]["restricted"] is True
    assert jj[0].question_refs == []
    assert SourceProblemCode.RESTRICTED_SOURCE.value in _codes(bundle)


def test_a_restricted_set_never_yields_questions_even_when_present():
    import examdata_integration.adapters.toefl as mod

    real = mod.read_source

    def fake(path, **kwargs):
        data, kind, problems = real(path, **kwargs)
        if data is not None:
            for entry in data.get("sets", []):
                if entry.get("restricted"):
                    entry["questions"] = [{"native_id": "LEAK", "kind": "fill_blank",
                                           "prompt": "must never be read"}]
        return data, kind, problems

    mod.read_source = fake
    try:
        bundle = TOEFLQuestionSetAdapter(QUESTION_SETS).bundle()
        assert "LEAK" not in _by_id(bundle)
        assert len(bundle.questions) == 6
        assert SourceProblemCode.RESTRICTED_SOURCE.value in _codes(bundle)
    finally:
        mod.read_source = real


def test_unknown_exam_dates_are_reported_and_kept_null():
    bundle = TOEFLQuestionSetAdapter(QUESTION_SETS).bundle()
    unknown = [p for p in bundle.problems
               if p.code == SourceProblemCode.UNKNOWN_DATE.value]
    assert sorted(p.native_ref for p in unknown) == [
        "synthetic-badurl-1", "synthetic-jj-set-1", "synthetic-tpo-set-1"]
    official = [c for c in bundle.containers
                if c.native_identity["set"] == "synthetic-official-1"][0]
    assert official.sections[0]["exam_date"] == "2026-03-14"


def test_a_bad_kmf_url_is_reported_and_never_requested():
    bundle = TOEFLQuestionSetAdapter(QUESTION_SETS).bundle()
    bad = [p for p in bundle.problems
           if p.code == SourceProblemCode.INVALID_KMF_URL.value]
    assert [p.native_ref for p in bad] == ["synthetic-badurl-1"]
    assert "http" in bad[0].detail or "https" in bad[0].detail


# -- cache reparse ---------------------------------------------------------- #
def test_cache_adapter_reports_each_rejected_entry():
    report = TOEFLCacheAdapter(BAD_CACHE).report()
    assert len(report.entries) == 5
    assert [e.native_id for e in report.usable] == ["cache-1", "cache-3"]
    bad = [p for p in report.problems
           if p.code == SourceProblemCode.BAD_CACHE_ENTRY.value]
    assert len(bad) == 3
    details = " ".join(p.detail for p in bad)
    assert "is not a JSON object" in details
    assert "has no native_id" in details
    assert "repeats native_id" in details


def test_cache_bundle_summarises_usable_and_total_entries():
    bundle = TOEFLCacheAdapter(BAD_CACHE).bundle()
    assert bundle.source == {"fixture": BAD_CACHE.name, "entries": 5, "usable": 2}


def test_cache_adapter_on_a_missing_file_is_a_read_problem():
    bundle = TOEFLCacheAdapter(FIXTURES / "synthetic" / "nope.json").bundle()
    assert bundle.problems
    assert SourceProblemCode.MISSING_SOURCE.value in _codes(bundle)
