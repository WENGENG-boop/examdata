"""A07: multi-region mapping, rotation metadata and region hash conflicts."""
from __future__ import annotations

from examdata_integration.adapters import DocumentTable, build_regions, page_rotation_table
from examdata_integration.adapters.problems import ProblemCode

QP = "a" * 64
OTHER = "c" * 64
COORD = "unrotated_pdf_points_top_left"


def _build(regions, *, rotations=None, declared=False, doc_rows=None,
           coordinate_system=COORD, native_ref="1"):
    table = DocumentTable(doc_rows if doc_rows is not None else [{"role": "qp", "sha256": QP}])
    return build_regions(regions, doc_table=table, coordinate_system=coordinate_system,
                         rotations=rotations or {}, system="cie",
                         container_native={"subject": "0000"}, provider_id="test_adapter",
                         fixture_name="unit.json", native_ref=native_ref,
                         rotations_declared=declared)


def _codes(problems):
    return [p.code for p in problems]


def test_two_regions_on_one_question_produce_two_distinct_regions():
    regions, problems = _build([
        {"page": 2, "bbox": [0, 0, 10, 10]},
        {"page": 2, "bbox": [20, 20, 30, 30]},
    ])
    assert len(regions) == 2
    assert regions[0].public_id != regions[1].public_id
    assert problems == []


def test_rotation_transform_is_preserved_from_the_page_table():
    rotations = {2: {"rotation_degrees": 90, "rotation_transform": [0, 1, -1, 0, 0, 0]}}
    regions, _ = _build([{"page": 2, "bbox": [0, 0, 10, 10]}], rotations=rotations)
    assert regions[0].rotation_transform == [0, 1, -1, 0, 0, 0]


def test_identity_rotation_is_preserved_as_recorded():
    rotations = {3: {"rotation_degrees": 0, "rotation_transform": [1, 0, 0, 1, 0, 0]}}
    regions, _ = _build([{"page": 3, "bbox": [0, 0, 10, 10]}], rotations=rotations)
    assert regions[0].rotation_transform == [1, 0, 0, 1, 0, 0]


def test_region_on_an_undeclared_page_is_reported_when_pages_are_declared():
    rotations = {2: {"rotation_degrees": 0, "rotation_transform": [1, 0, 0, 1, 0, 0]}}
    regions, problems = _build([{"page": 9, "bbox": [0, 0, 10, 10]}],
                               rotations=rotations, declared=True)
    assert regions[0].rotation_transform is None
    assert _codes(problems) == [ProblemCode.UNKNOWN_ROTATION.value]


def test_region_on_an_undeclared_page_is_quiet_when_no_page_table_exists():
    regions, problems = _build([{"page": 9, "bbox": [0, 0, 10, 10]}],
                               rotations={}, declared=False)
    assert regions[0].rotation_transform is None
    assert problems == []


def test_missing_bounding_box_is_reported():
    regions, problems = _build([{"page": 2}])
    assert regions[0].bbox == []
    assert _codes(problems) == [ProblemCode.MISSING_REGION_BBOX.value]


def test_non_numeric_bounding_box_is_reported():
    regions, problems = _build([{"page": 2, "bbox": [0, 0, "x", 10]}])
    assert regions[0].bbox == []
    assert _codes(problems) == [ProblemCode.MISSING_REGION_BBOX.value]


def test_conflicting_region_hash_is_preserved_and_reported():
    regions, problems = _build([{"page": 2, "bbox": [0, 0, 10, 10],
                                 "document_role": "qp", "document_sha256": OTHER}])
    assert regions[0].document_sha256 == OTHER
    assert _codes(problems) == [ProblemCode.HASH_CONFLICT.value]
    assert regions[0].evidence_status == "unverified"


def test_matching_region_hash_is_not_a_conflict():
    regions, problems = _build([{"page": 2, "bbox": [0, 0, 10, 10],
                                 "document_role": "qp", "document_sha256": QP}])
    assert regions[0].document_sha256 == QP
    assert problems == []


def test_region_without_a_cited_hash_uses_the_table_hash():
    regions, _ = _build([{"page": 2, "bbox": [0, 0, 10, 10], "document_role": "qp"}])
    assert regions[0].document_sha256 == QP


def test_region_citing_an_unknown_role_is_reported():
    regions, problems = _build([{"page": 2, "bbox": [0, 0, 10, 10], "document_role": "in"}])
    assert regions[0].document_sha256 is None
    assert _codes(problems) == [ProblemCode.MISSING_DOCUMENT_ROLE.value]


def test_regions_are_always_unverified():
    regions, _ = _build([{"page": 2, "bbox": [0, 0, 10, 10]}])
    assert regions[0].evidence_status == "unverified"


def test_page_rotation_table_skips_rows_without_a_page():
    table = page_rotation_table([
        {"page": 1, "rotation_degrees": 90, "rotation_transform": [0, 1, -1, 0, 0, 0]},
        {"rotation_degrees": 180},
        {"page": "2", "rotation_transform": [1, 0, 0, 1, 0, 0]},
    ])
    assert set(table) == {1, 2}
    assert table[2]["rotation_transform"] == [1, 0, 0, 1, 0, 0]


def test_page_rotation_table_tolerates_absent_transform():
    table = page_rotation_table([{"page": 1, "rotation_degrees": 90}])
    assert table[1]["rotation_transform"] is None
