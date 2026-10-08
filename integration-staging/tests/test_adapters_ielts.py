"""A08: the IELTS read adapters preserve slots, variants, conflicts and alignment."""
from __future__ import annotations

from pathlib import Path

from examdata_integration.adapters.ielts import (
    AudioTrack,
    IELTSAudioAdapter,
    IELTSQuestionsAdapter,
    IELTSRevisionAdapter,
    IELTSPagesAdapter,
)
from examdata_integration.adapters.source_reader import SourceProblemCode
from examdata_integration.contracts.enums import (
    AnswerMatchingMethod,
    ContainerKind,
    ContentClass,
    QuestionType,
    QualityAnswerPresence,
    QualityAudioAlignment,
)

STAGING = Path(__file__).resolve().parents[1]
FIXTURES = STAGING / "fixtures"
A03_IELTS = FIXTURES / "synthetic" / "ielts" / "questions-synthetic.json"
A08_IELTS = FIXTURES / "synthetic" / "ielts-toefl" / "ielts-questions-a08-synthetic.json"
A08_AUDIO = FIXTURES / "synthetic" / "ielts-toefl" / "ielts-audio-synthetic.json"
PAGES = FIXTURES / "copied" / "ielts" / "printed-pages.json"
PROVENANCE = FIXTURES / "copied" / "ielts" / "pdf-provenance.json"
INDEXES = FIXTURES / "copied" / "ielts" / "indexes-current.json"
MANIFESTS = FIXTURES / "copied" / "ielts" / "manifests-current.json"


def _codes(bundle):
    return [p.code for p in bundle.problems]


def _by_id(bundle):
    return {q.native_id: q for q in bundle.questions}


# -- question set (A03 book fixture) ---------------------------------------- #
def test_a03_bundle_counts_and_container_kind():
    bundle = IELTSQuestionsAdapter(A03_IELTS).bundle()
    counts = bundle.to_dict()["counts"]
    assert counts["courses"] == 1
    assert counts["containers"] == 1
    assert counts["questions"] == 6
    assert counts["answers"] == 5
    assert counts["assets"] == 1
    assert bundle.containers[0].kind is ContainerKind.BOOK
    assert bundle.containers[0].content_class is ContentClass.SYNTHETIC


def test_missing_answer_slot_q41_is_preserved_and_never_fabricated():
    bundle = IELTSQuestionsAdapter(A03_IELTS).bundle()
    q41 = _by_id(bundle)["Q41"]
    assert q41.question_type is QuestionType.UNKNOWN
    assert q41.answers == []
    assert q41.quality.answer_presence is QualityAnswerPresence.MISSING
    assert [g.code for g in q41.quality.gaps] == ["missing_answer_slot"]
    assert SourceProblemCode.MISSING_ANSWER_SLOT.value in _codes(bundle)
    # the slot number itself is kept
    assert q41.payload.raw["answer_slot"] == 41


def test_grouped_alternatives_become_options_with_a_grouped_answer():
    bundle = IELTSQuestionsAdapter(A03_IELTS).bundle()
    q2 = _by_id(bundle)["Q2"]
    assert q2.question_type is QuestionType.SINGLE_CHOICE
    assert [o.key for o in q2.payload.options] == ["B", "A", "C", "D"]
    assert q2.answers[0].matching_method is AnswerMatchingMethod.GROUPED
    assert q2.answers[0].alternatives == ["A", "C", "D"]


def test_table_choice_keeps_columns_rows_and_the_answer_cell():
    bundle = IELTSQuestionsAdapter(A03_IELTS).bundle()
    q4 = _by_id(bundle)["Q4"]
    assert q4.question_type is QuestionType.TABLE_CHOICE
    assert q4.payload.columns == ["Synthetic column A", "Synthetic column B",
                                  "Synthetic column C"]
    assert len(q4.payload.rows) == 2
    assert [(c.row, c.column) for c in q4.payload.answer_cells] == [(2, 3)]


def test_parent_answer_keeps_the_hierarchy_and_normalises_a_self_parent():
    bundle = IELTSQuestionsAdapter(A03_IELTS).bundle()
    q3 = _by_id(bundle)["Q3"]
    assert q3.parent_ref is None  # the self-parent is normalised to a root
    assert [c.native_id for c in q3.children] == ["Q3.i", "Q3.ii"]
    assert [c.parent_ref for c in q3.children] == ["Q3", "Q3"]
    assert [q.number_path for q in q3.walk()] == [["Q3"], ["Q3", "Q3.i"],
                                                 ["Q3", "Q3.ii"]]
    # the raw self-parent value is preserved in the lineage note, not as a reference
    assert "raw_parent_native_id=Q3 (self, normalised to root)" in q3.lineage.note
    assert SourceProblemCode.UNRESOLVED_IDENTITY.value in _codes(bundle)


def test_answer_conflict_is_preserved_without_a_decision():
    bundle = IELTSQuestionsAdapter(A03_IELTS).bundle()
    q5 = _by_id(bundle)["Q5"]
    answer = q5.answers[0]
    assert len(answer.conflicts) == 2
    assert answer.manual_decision is None
    assert answer.verification == "unverified"
    assert SourceProblemCode.ANSWER_CONFLICT.value in _codes(bundle)


def test_required_image_without_bytes_is_a_missing_asset():
    bundle = IELTSQuestionsAdapter(A03_IELTS).bundle()
    assert _codes(bundle).count(SourceProblemCode.MISSING_ASSET.value) == 1
    assert bundle.assets[0].sha256 == "0" * 64
    assert bundle.assets[0].storage_mode == "external_only"


def test_every_ielts_answer_stays_unverified_synthetic():
    bundle = IELTSQuestionsAdapter(A03_IELTS).bundle()
    assert bundle.answers
    for answer in bundle.answers:
        assert answer.verification == "unverified"
        assert answer.content_class is ContentClass.SYNTHETIC


# -- question set (A08 variant fixture) ------------------------------------- #
def test_a08_variant_and_unresolved_edition_are_preserved():
    bundle = IELTSQuestionsAdapter(A08_IELTS).bundle()
    assert bundle.source["variant"] == "academic"
    section = bundle.containers[0].sections[0]
    assert section["edition_uncertain"] is True
    assert section["edition"] is not None and section["edition"] != "unknown"
    assert SourceProblemCode.UNRESOLVED_EDITION.value in _codes(bundle)


def test_special_numbering_and_raw_source_id_are_kept_in_lineage():
    bundle = IELTSQuestionsAdapter(A08_IELTS).bundle()
    q7 = _by_id(bundle)["S2Q7"]
    assert "numbering=7(b)(ii)" in q7.lineage.note
    assert "raw_source_id=synthetic-src-0007" in q7.lineage.note
    assert q7.answers[0].source.locator["raw_source_id"] == "synthetic-src-0007"


def test_a08_missing_slot_and_conflict_match_the_a03_treatment():
    bundle = IELTSQuestionsAdapter(A08_IELTS).bundle()
    ids = _by_id(bundle)
    assert ids["S2Q41"].answers == []
    assert ids["S2Q41"].quality.answer_presence is QualityAnswerPresence.MISSING
    assert len(ids["S2Q24"].answers[0].conflicts) == 2
    assert ids["S2Q24"].answers[0].manual_decision is None


# -- copied page map + provenance ------------------------------------------- #
def test_pages_adapter_reports_every_unresolved_page():
    bundle = IELTSPagesAdapter(PAGES, PROVENANCE).bundle()
    unresolved = [p for p in bundle.problems
                  if p.code == SourceProblemCode.UNRESOLVED_PAGE.value]
    assert bundle.source["printed_pages_total"] == 664
    assert bundle.source["printed_pages_unresolved"] == len(unresolved) == 137
    # an unresolved page is never guessed
    assert all(p.detail for p in unresolved)


def test_pages_adapter_maps_document_and_asset_hashes():
    bundle = IELTSPagesAdapter(PAGES, PROVENANCE).bundle()
    assert len(bundle.assets) == 133  # 9 PDF documents + 124 imported assets
    # every copied PDF import records a hash, so no document hash is missing
    assert SourceProblemCode.MISSING_DOCUMENT_HASH.value not in _codes(bundle)
    pdfs = [a for a in bundle.assets if a.media_type == "application/pdf"]
    assert len(pdfs) == 9
    assert all(a.sha256 and len(a.sha256) == 64 for a in pdfs)
    # the imported assets keep their recorded hash even though no media type is stated
    imported = [a for a in bundle.assets if a.media_type is None]
    assert len(imported) == 124
    assert all(a.sha256 for a in imported)


def test_pages_adapter_entry_problems_flag_missing_pages_and_assets():
    problems = IELTSPagesAdapter.entry_problems(
        {"key": "synthetic", "missing_pages": [3], "missing_assets": ["figure-1"]})
    codes = sorted(p.code for p in problems)
    assert codes == [SourceProblemCode.MISSING_ASSET.value,
                     SourceProblemCode.UNRESOLVED_PAGE.value]


def test_pages_adapter_works_without_a_provenance_file():
    bundle = IELTSPagesAdapter(PAGES).bundle()
    assert bundle.assets == []
    assert bundle.source["provenance"] is None
    assert bundle.source["printed_pages_unresolved"] == 137


# -- revision pointers ------------------------------------------------------ #
def test_revision_adapter_reports_a_matching_pointer():
    bundle = IELTSRevisionAdapter(INDEXES, MANIFESTS).bundle()
    assert bundle.source["revisions"] == {"indexes": "rev-8b21015ab64bb73c",
                                          "manifests": "rev-8b21015ab64bb73c"}
    assert bundle.problems == []


def test_revision_adapter_flags_a_stale_pointer():
    # the two copied pointers agree; a disagreement must be reported, never accepted
    assert IELTSRevisionAdapter(INDEXES, MANIFESTS).bundle().problems == []
    import examdata_integration.adapters.ielts as mod

    real = mod.read_source

    def fake(path, **kwargs):
        data, kind, problems = real(path, **kwargs)
        if data is not None and path.name.startswith("manifests"):
            data["dataset_revision"] = "rev-stale"
        return data, kind, problems

    mod.read_source = fake
    try:
        bundle = IELTSRevisionAdapter(INDEXES, MANIFESTS).bundle()
        assert SourceProblemCode.UNRESOLVED_IDENTITY.value in _codes(bundle)
    finally:
        mod.read_source = real


# -- audio alignment -------------------------------------------------------- #
def test_audio_tracks_keep_the_three_alignment_states_distinct():
    adapter = IELTSAudioAdapter(A08_AUDIO)
    tracks, _problems = adapter.tracks()
    by_id = {t.native_id: t for t in tracks}
    assert isinstance(by_id["track-1"], AudioTrack)
    assert by_id["track-1"].alignment_declared == "verified"
    # a synthetic claim can never reach verified: it is capped and reported
    assert by_id["track-1"].alignment_effective == QualityAudioAlignment.UNVERIFIED.value
    assert by_id["track-2"].alignment_declared == "unverified"
    assert by_id["track-2"].alignment_effective == QualityAudioAlignment.UNVERIFIED.value
    assert by_id["track-3"].alignment_effective == QualityAudioAlignment.UNKNOWN.value
    assert by_id["track-4"].alignment_effective == \
        QualityAudioAlignment.NOT_APPLICABLE.value


def test_audio_verified_claim_is_reported_as_unverified_content():
    _tracks, problems = IELTSAudioAdapter(A08_AUDIO).tracks()
    capped = [p for p in problems
              if p.code == SourceProblemCode.UNVERIFIED_CONTENT.value]
    assert [p.native_ref for p in capped] == ["track-1"]


def test_audio_missing_time_window_never_invents_offsets():
    tracks, problems = IELTSAudioAdapter(A08_AUDIO).tracks()
    track2 = {t.native_id: t for t in tracks}["track-2"]
    assert track2.segments == [{"question": "Q2", "start": None, "end": None}]
    windows = [p for p in problems
               if p.code == SourceProblemCode.MISSING_TIME_WINDOW.value]
    assert [p.native_ref for p in windows] == ["track-2"]


def test_audio_bundle_assets_carry_the_recorded_hashes():
    bundle = IELTSAudioAdapter(A08_AUDIO).bundle()
    assert len(bundle.assets) == 4
    assert {a.sha256 for a in bundle.assets} == {"a1" * 32, None, "b2" * 32, "c3" * 32}
    assert all(a.storage_mode == "external_only" for a in bundle.assets)


def test_audio_integrity_stays_unverified_under_synthetic_evidence():
    tracks, _problems = IELTSAudioAdapter(A08_AUDIO).tracks()
    for track in tracks:
        assert track.quality.audio_integrity.value == "unverified"
        assert track.quality.audio_alignment.value != "verified"
