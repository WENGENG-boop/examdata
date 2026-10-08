"""A12 legacy adapter fixture translation (plan 5.5, packet A12).

One parametrized case per adapter row (21). Each case drives the staged
proposal layer with private fixtures only:

* the 14 ``fixture_translation`` rows build the legacy payload through
  ``legacy.translate`` from the staged read dataset (``api.dataset``) or the
  staged binary fixture store, and the top-level key set is compared against
  the frozen static extraction (``evidence/A12/legacy_shape_extract.json``).
  Rows whose legacy handler returns a merge/call/name (no full envelope dict)
  carry their own recorded rule instead of a top-level key set.
* the 7 ``envelope_contract`` rows map an inline offline ``RunResult`` stub
  through ``legacy.bridge.decide`` and assert the legacy 200 envelope, board
  defaulting, the business-failure passthrough and the 503 aggregator detail.

Honesty rules pinned here: an empty fixture stays empty (a missing
classification, answer slot or provenance source is never fabricated), the
binary store resolves an asset only when the declared hash matches the staged
manifest, and every value that reaches a payload comes from the staged
fixtures, the recorded contract text, or the builder's own echo of its
caller's numbers. Nothing imports an original module, spawns a process or
opens a socket.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from examdata_integration.api.binary import ContentStore
from examdata_integration.api.dataset import default_dataset
from examdata_integration.legacy import bridge, decisions, translate
from examdata_integration.runtime.classification import RunnerOutcome

STAGING = Path(__file__).resolve().parents[1]
WORKSPACE = STAGING.parent
EXTRACT_PATH = (WORKSPACE / "docs" / "integration" / "execution" / "evidence" /
                "A12" / "legacy_shape_extract.json")
BINARY_ROOT = STAGING / "fixtures" / "synthetic" / "binary"

ROWS = {row["row_id"]: row for row in decisions.rows()}
ADAPTER_IDS = [row["row_id"] for row in decisions.rows()
               if row["mechanism"] == "add_v2_adapter_keep_legacy_defaults"]

#: `SCHEMA_VERSION` and `AUTO_DETECT` quoted from the legacy gateway by static
#: inspection (`examdata/src/examdata/api/unified.py` L52/L115): the recorded
#: value is reproduced so the staged envelope can be compared with it.
SCHEMA_VERSION_RECORDED = "1"
AUTO_DETECT_RECORDED: dict[str, Any] = {
    "rule": "未显式传 board 时：科目代码去空白后匹配四位数字则判为 cie，否则判为 edexcel",
    "cie_subject_pattern": r"^\d{4}$",
    "fallback_board": "edexcel",
    "explicit_board_wins": True,
}

#: `/api/v1/paper/index` 422 detail, verbatim from the recorded handler.
CIE_INDEX_DETAIL = "CIE uses whole PDFs and an externally imported AI index"

#: `get_question_bundle` top-level keys, recorded by A12 static inspection
#: (registry row `GET__questions_question_id`).
BUNDLE_KEYS = ("question", "paper", "children", "assets", "official_answers",
               "mark_scheme_entries", "taxonomy", "difficulty",
               "similar_questions")

#: `get_paper_tree` key sets, recorded by A12 static inspection (registry row
#: `GET__papers_paper_id_tree`): a paper block and node blocks.
TREE_PAPER_KEYS = ("id", "paper_no", "marks_total", "question_count",
                   "duration_minutes", "page_count", "document_id",
                   "paper_code", "year", "doc_type")
TREE_NODE_KEYS = ("id", "number_path", "label", "depth", "kind", "marks",
                  "page_from", "page_to", "asset_count", "children")

#: A manifest-shaped input for the `download=false` branch. The paperqa
#: manifest is not staged in Phase A, so the input is labelled synthetic and
#: only the merge rule is asserted.
PAPER_MANIFEST_FIXTURE: dict[str, Any] = {
    "fixture": "synthetic_manifest_shape",
    "note": "the paperqa manifest is not staged in Phase A",
    "files": [{"role": "qp", "sha256": "5" * 64}],
}


@lru_cache(maxsize=1)
def _extract() -> dict[tuple[str, str], dict[str, Any]]:
    payload = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    return {(r["method"], r["path"]): r for r in payload["routes"]}


@lru_cache(maxsize=1)
def _dataset():
    return default_dataset()


@lru_cache(maxsize=1)
def _store() -> ContentStore:
    return ContentStore(BINARY_ROOT, BINARY_ROOT / "manifest.json")


def recorded_envelope_keys(row: dict[str, Any]) -> set[str] | None:
    """The recorded top-level dict keys, or `None` when the handler returns a
    merge/name/call instead of a full envelope."""
    entry = _extract().get((row["method"], row["legacy_path"]))
    if entry is None:
        return None
    for ret in entry.get("returns", []):
        if ret.get("kind") == "dict" and "keys" in ret and "**" not in ret.get("expr", ""):
            return set(ret["keys"])
    return None


def _entry(entry) -> dict[str, Any]:
    """The staged JSON rendering of a catalog entry: the UNKNOWN sentinel
    becomes its reserved token, so a "known unknown" never turns into null or
    a fabricated value."""
    return entry.to_dict()


def _pick_question(ds):
    return ds.entries("question")[0]


def _children_of(entries, parent) -> list[dict[str, Any]]:
    parent_native = parent.identity_fields.get("native_id")
    return [_entry(e) for e in entries
            if e.public_id != parent.public_id
            and e.identity_fields.get("parent_native_id") == parent_native]


def _bundle_for(ds, question) -> dict[str, Any]:
    """A bundle-shaped proposal: staged content only; every unstaged slot
    (assets, answers, mark scheme, taxonomy, difficulty, similar questions)
    stays empty/null instead of being filled."""
    entries = ds.entries("question")
    containers = {e.public_id: e for e in ds.entries("container")}
    container = containers.get(question.container_ref)
    return translate.json_copy({
        "question": _entry(question),
        "paper": _entry(container) if container is not None else None,
        "children": _children_of(entries, question),
        "assets": [],
        "official_answers": [],
        "mark_scheme_entries": [],
        "taxonomy": [],
        "difficulty": None,
        "similar_questions": [],
    })


# ---------------------------------------------------------------------------
# fixture_translation builders (staged fixtures only)
# ---------------------------------------------------------------------------

def build_papers(ds, store) -> dict[str, Any]:
    items = [_entry(e) for e in ds.entries("container")]
    payload = translate.legacy_page(items, total=len(items), limit=25, offset=0)
    assert payload["items"] == translate.json_copy(items), "page passes items through unchanged"
    assert payload["limit"] == 25 and payload["offset"] == 0, "echoed verbatim"
    return payload


def build_questions(ds, store) -> dict[str, Any]:
    items = [_entry(e) for e in ds.entries("question")]
    payload = translate.legacy_page(items, total=len(items), limit=50, offset=10)
    assert payload["total"] == len(payload["items"])
    assert payload["limit"] == 50 and payload["offset"] == 10, "echoed verbatim"
    return payload


def build_search(ds, store) -> dict[str, Any]:
    entries = [e for e in ds.entries("question") if e.system in ("cie", "edexcel")]
    items = [_entry(e) for e in entries]
    by_board = {
        "cambridge": sum(1 for e in entries if e.system == "cie"),
        "edexcel": sum(1 for e in entries if e.system == "edexcel"),
    }
    payload = translate.legacy_search_page(items, total=len(items), limit=20, offset=0,
                                           board="cie", by_board=by_board,
                                           board_source="explicit")
    assert set(payload["by_board"]) == {"cambridge", "edexcel"}
    assert sum(payload["by_board"].values()) == payload["total"] == len(payload["items"]), \
        "by_board stays consistent with total, as the legacy expression guarantees"
    assert payload["board"] == "cie" and payload["board_source"] == "explicit"
    return payload


def build_boards(ds, store) -> dict[str, Any]:
    boards = ds.systems()
    payload = translate.boards_payload(schema_version=SCHEMA_VERSION_RECORDED,
                                       auto_detect=AUTO_DETECT_RECORDED, boards=boards)
    assert payload["auto_detect"] == translate.json_copy(AUTO_DETECT_RECORDED)
    assert payload["boards"] == translate.json_copy(boards), "systems pass through unchanged"
    return payload


def build_paper(ds, store) -> dict[str, Any]:
    manifest = translate.json_copy(PAPER_MANIFEST_FIXTURE)
    payload = translate.paper_payload(manifest, board="ielts", board_source="explicit")
    assert set(payload) == set(manifest) | {"board", "board_source"}
    for key, value in manifest.items():
        assert payload[key] == value, f"manifest key {key!r} was rewritten"
    row = ROWS["GET__api_v1_paper"]
    assert "download=false" in row["legacy_success_shape"]
    assert "format=json" in row["legacy_success_shape"]
    assert "raw bytes/ZIP" in row["legacy_success_shape"]
    return payload


def build_paper_index(ds, store) -> dict[str, Any]:
    row = ROWS["GET__api_v1_paper_index"]
    match = re.search(r"422: '([^']+)'", row["legacy_error_shape"])
    assert match and match.group(1) == CIE_INDEX_DETAIL, \
        "the recorded non-edexcel 422 detail must be quoted verbatim"
    body = translate.legacy_error(422, match.group(1))
    assert body == {"status_code": 422, "detail": CIE_INDEX_DETAIL}
    assert "422 preserved" in row["v2_target"]
    return body


def build_question_view(ds, store) -> dict[str, Any]:
    question = _pick_question(ds)
    source = {"board": "ielts", "board_canonical": "ielts",
              "subject_code": question.identity_fields
              .get("container_native_identity", {}).get("book")}
    payload = translate.unified_question_view(
        question_id=question.public_id, board="ielts", board_source="inferred",
        source=source, bundle=_bundle_for(ds, question))
    assert payload["question_id"] == question.public_id, "native-adjacent id preserved"
    assert payload["source"] == translate.json_copy(source)
    return payload


def build_asset_provenance(ds, store) -> dict[str, Any]:
    asset = ds.entries("asset")[0]
    sources = [asset.lineage] if asset.lineage else []
    payload = translate.provenance_payload("asset", asset.public_id, sources)
    assert payload == {"asset_id": asset.public_id, "sources": sources}
    if not sources:
        assert payload["sources"] == [], \
            "a missing provenance source stays missing, never fabricated"
    return payload


def build_classifications(ds, store) -> dict[str, Any]:
    payload = translate.classifications_payload([])
    assert payload == {"count": 0, "conflicts": 0, "items": []}, \
        "no classification decision is staged; the empty list is preserved"
    synthetic = [{"method": "conflict", "note": "synthetic_fixture"},
                 {"method": "manual", "note": "synthetic_fixture"}]
    probe = translate.classifications_payload(synthetic)
    assert probe["count"] == 2 and probe["conflicts"] == 1
    assert probe["items"][0]["method"] == "conflict", "a conflict is counted, never resolved"
    return payload


def build_provenance_coverage(ds, store) -> dict[str, Any]:
    payload = translate.provenance_coverage_payload({})
    assert payload == {"coverage": {}, "complete": True}, \
        "the recorded `all(...)` expression is vacuously true over no rows"
    assert translate.provenance_coverage_payload(
        {"cie": {"ratio": 0.5}})["complete"] is False
    assert translate.provenance_coverage_payload(
        {"cie": {"ratio": 1.0}})["complete"] is True
    return payload


def build_question_bundle(ds, store) -> dict[str, Any]:
    bundle = _bundle_for(ds, _pick_question(ds))
    assert set(bundle) == set(BUNDLE_KEYS), "bundle keys are the recorded set"
    assert bundle["official_answers"] == [] and bundle["mark_scheme_entries"] == [], \
        "missing answer slots stay missing"
    assert bundle["difficulty"] is None and bundle["similar_questions"] == []
    return bundle


def build_paper_tree(ds, store) -> dict[str, Any]:
    containers = ds.entries("container")
    questions = ds.entries("question")
    container = max(containers,
                    key=lambda c: sum(1 for e in questions if e.container_ref == c.public_id))
    qs = [e for e in questions if e.container_ref == container.public_id]
    assert qs, "the frozen fixtures place questions under a container"

    def node(e) -> dict[str, Any]:
        number_path = list(e.identity_fields.get("number_path") or [])
        return {"id": e.public_id,
                "number_path": number_path,
                "label": e.identity_fields.get("native_id"),
                "depth": len(number_path) - 1 if number_path else None,
                "kind": e.kind,
                "marks": None,
                "page_from": None,
                "page_to": None,
                "asset_count": 0,
                "children": []}

    nodes = {e.identity_fields.get("native_id"): node(e) for e in qs}
    roots: list[dict[str, Any]] = []
    for e in qs:
        native = e.identity_fields.get("native_id")
        parent = e.identity_fields.get("parent_native_id")
        if parent in nodes and parent != native:
            nodes[parent]["children"].append(nodes[native])
        else:
            roots.append(nodes[native])

    native_identity = container.identity_fields.get("native_identity") or {}
    document_id = next((r.get("sha256")
                        for r in container.searchable.get("resources") or []
                        if r.get("role") == "qp"), None)
    paper = {"id": container.public_id,
             "paper_no": native_identity.get("paper_no") or native_identity.get("paper"),
             "marks_total": None,
             "question_count": len(qs),
             "duration_minutes": None,
             "page_count": None,
             "document_id": document_id,
             "paper_code": native_identity.get("paper_code"),
             "year": native_identity.get("year"),
             "doc_type": container.searchable.get("kind")}
    tree = translate.json_copy({"paper": paper, "roots": roots})
    assert set(tree) == {"paper", "roots"}
    assert set(tree["paper"]) == set(TREE_PAPER_KEYS)
    assert tree["paper"]["marks_total"] is None, "unstaged fields stay null, never guessed"

    def walk(items):
        for item in items:
            assert set(item) == set(TREE_NODE_KEYS), item.get("id")
            walk(item["children"])

    walk(tree["roots"])
    return tree


def build_assets(ds, store) -> dict[str, Any]:
    row = ROWS["GET__assets_asset_id"]
    assert store.ok, f"binary fixture store must load cleanly: {store.problems}"
    resolved = []
    for entry in ds.entries("asset"):
        sample = store.for_asset(entry.system, entry.identity_fields.get("sha256"))
        if sample is None:
            continue
        blob = store.sample_bytes(sample)
        assert len(blob) == sample.byte_size
        resolved.append({"asset_id": entry.public_id,
                         "media_type": sample.media_type,
                         "byte_size": sample.byte_size,
                         "sha256": sample.sha256})
    assert resolved, "at least one staged asset resolves in the binary fixture store"
    assert store.for_asset("cie", "9" * 64) is None, \
        "an unknown declared hash resolves to nothing; no content is invented"
    assert "attachment" in row["binary_behavior"]
    assert "application/octet-stream" in row["binary_behavior"]
    for status in ("410", "403", "404"):
        assert status in row["legacy_error_shape"], status
    return {"resolved": resolved}


def build_taxonomy(ds, store) -> dict[str, Any]:
    payload = translate.taxonomy_payload([])
    assert payload == {"roots": [], "topic_count": 0}, \
        "no taxonomy is staged; the empty fixture is preserved"
    probe = translate.taxonomy_payload([{"note": "synthetic_fixture"}])
    assert probe["topic_count"] == 1 == len(probe["roots"])
    return payload


DATA_BUILDERS: dict[str, Callable[[Any, ContentStore], dict[str, Any]]] = {
    "GET__api_v1_boards": build_boards,
    "GET__api_v1_paper": build_paper,
    "GET__api_v1_paper_index": build_paper_index,
    "GET__api_v1_question_question_id": build_question_view,
    "GET__api_v1_search": build_search,
    "GET__assets_asset_id": build_assets,
    "GET__assets_asset_id_provenance": build_asset_provenance,
    "GET__classifications": build_classifications,
    "GET__papers": build_papers,
    "GET__papers_paper_id_tree": build_paper_tree,
    "GET__provenance_coverage": build_provenance_coverage,
    "GET__questions": build_questions,
    "GET__questions_question_id": build_question_bundle,
    "GET__taxonomy": build_taxonomy,
}


# ---------------------------------------------------------------------------
# envelope_contract rows (inline offline node-CLI stub)
# ---------------------------------------------------------------------------

def stub(outcome: RunnerOutcome, *, payload=None, exit_code: int | None = None,
         stderr_text: str | None = None, error=None) -> SimpleNamespace:
    return SimpleNamespace(outcome=outcome, payload=payload, exit_code=exit_code,
                           stderr_text=stderr_text, error=error)


def _check_envelope_row(row_id: str) -> None:
    row = ROWS[row_id]
    assert row["v2_target"] == "coverage.get", row_id
    assert row["fixture_ids"] == ["inline:offline_node_stub"], row_id
    board = "toefl" if "_toefl_" in row_id else "ielts"
    profile = bridge.BOARD_PROFILES[board]

    incoming = {"ok": True, "coverage": {"cie": {"ratio": 1.0}}, "total": 1}
    response = bridge.decide(board, stub(RunnerOutcome.OK, payload=dict(incoming)),
                             command="coverage", limit=120)
    assert response.status_code == 200
    assert response.payload["board"] == board, "board is defaulted in (dict payload)"
    assert response.payload["coverage"] == incoming["coverage"], "coverage passes through"
    assert response.payload["ok"] is True

    own = bridge.decide(board, stub(RunnerOutcome.OK, payload={"board": "kept"}),
                        command="coverage")
    assert own.payload["board"] == "kept", "an explicit board is never overwritten"

    business = bridge.decide(
        board, stub(RunnerOutcome.BUSINESS_FAILURE,
                    payload={"ok": False, "error": "synthetic_fixture"}),
        command="coverage")
    assert business.status_code == 200 and business.payload["ok"] is False

    missing = bridge.decide(board, stub(RunnerOutcome.MISSING_COMPONENT),
                            command="coverage", tried=["/staged/fixtures"])
    assert missing.status_code == 503
    assert profile.script in missing.body()["detail"]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("row_id", ADAPTER_IDS)
def test_adapter_fixture_translation(row_id: str) -> None:
    row = ROWS[row_id]
    expected_test_id = (f"tests/test_legacy_adapters.py::"
                        f"test_adapter_fixture_translation[{row_id}]")
    assert expected_test_id in row["test_ids"]

    if row["coverage_kind"] == "envelope_contract":
        _check_envelope_row(row_id)
        return

    assert row["coverage_kind"] == "fixture_translation"
    assert row["fixture_ids"] == ["examdata_integration.api.dataset:default_dataset"]
    built = DATA_BUILDERS[row_id](_dataset(), _store())
    assert isinstance(built, dict)
    expected = recorded_envelope_keys(row)
    if expected is not None:
        assert set(built) == expected, f"{row_id}: top-level keys drifted"


def test_adapter_rows_are_accounted_for() -> None:
    assert len(ADAPTER_IDS) == 21
    data_ids = [i for i in ADAPTER_IDS
                if ROWS[i]["coverage_kind"] == "fixture_translation"]
    envelope_ids = [i for i in ADAPTER_IDS
                    if ROWS[i]["coverage_kind"] == "envelope_contract"]
    assert len(data_ids) == 14 and len(envelope_ids) == 7
    assert set(DATA_BUILDERS) == set(data_ids), "every data row has a builder"


def test_recorded_key_check_skips_merge_and_name_returns() -> None:
    assert recorded_envelope_keys(ROWS["GET__papers"]) == {"total", "limit", "offset", "items"}
    assert recorded_envelope_keys(ROWS["GET__api_v1_paper"]) is None, \
        "the paper handler merges `**manifest`; no fixed key set is recorded"
    assert recorded_envelope_keys(ROWS["GET__questions_question_id"]) is None, \
        "the detail handler returns a name reference, not a dict literal"


def test_staged_dataset_is_the_read_index_for_the_data_rows() -> None:
    ds = _dataset()
    assert ds.entries("question") and ds.entries("container") and ds.entries("asset")
    assert ds.revision.startswith("rev-")
    assert decisions.registry()["schema"] == decisions.SCHEMA
