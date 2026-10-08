"""A12 static legacy contracts + node-CLI bridge envelopes (plan 5.5).

Two layers:

* ``test_static_contract``: one parametrized case per baseline route. Every
  non-deferred row is re-derived from the frozen static extraction (handler,
  line, parameter names and simple defaults) and its contract text is checked
  to be populated and free of ``pending_A12``. Deferred rows are checked by
  existence only - their source is owned by the active session and is never
  parsed in Phase A.
* the bridge envelope tests: synthetic ``RunResult``-shaped objects (no
  subprocess) are mapped back through ``legacy.bridge.decide`` and compared
  against the verbatim gateway strings, including the disclosed staged
  divergences.

Nothing runs node, reads the original tree (except existence checks) or opens
a socket.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from examdata_integration.legacy import bridge, decisions
from examdata_integration.runtime.classification import RunnerOutcome

STAGING = Path(__file__).resolve().parents[1]
WORKSPACE = STAGING.parent
EXTRACT_PATH = (WORKSPACE / "docs" / "integration" / "execution" / "evidence" /
                "A12" / "legacy_shape_extract.json")

ROWS = decisions.rows()
ROW_IDS = [row["row_id"] for row in ROWS]


@pytest.fixture(scope="module")
def extract_routes() -> dict[tuple[str, str], dict]:
    payload = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    return {(r["method"], r["path"]): r for r in payload["routes"]}


# ---------------------------------------------------------------------------
# static per-route contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("row", ROWS, ids=ROW_IDS)
def test_static_contract(row, extract_routes):
    if row["mechanism"] == "deferred_active_owner":
        assert (WORKSPACE / row["source_file"]).is_file()
        assert row["handler"], "deferred rows keep their A01 handler name"
        assert row["native_parameters"] == "", "protected source must not be parsed"
        assert row["owner"] == "kimi_active"
        return

    route = extract_routes[(row["method"], row["legacy_path"])]
    assert row["handler"] == route["handler"]
    assert row["line"] == route["line"]

    params_text = row["native_parameters"]
    for param in route["params"]:
        pattern = rf"(?:^|, ){re.escape(param['name'])}(?:=|,|$)"
        assert re.search(pattern, params_text), \
            f"{row['row_id']}: parameter {param['name']!r} missing from {params_text!r}"
        if param.get("default") == "None" and param["name"] in ("board", "subject"):
            assert f"{param['name']}=None" in params_text

    assert row["legacy_success_shape"], f"{row['row_id']} has no success shape"
    assert row["legacy_error_shape"], f"{row['row_id']} has no error shape"
    assert row["binary_behavior"] not in ("", "pending_A12"), row["row_id"]
    assert "pending_A12" not in row["legacy_success_shape"]
    assert "pending_A12" not in row["legacy_error_shape"]
    assert row["notes"].startswith("staged_pass:")
    assert "merged" not in row["notes"].split("remain")[0], \
        "the notes may mention merge only as deferred-to-Phase-B"


def test_mechanism_texts_are_internally_consistent(extract_routes):
    for row in ROWS:
        if row["mechanism"] == "bridge_node_cli_keep_legacy_payload":
            assert "node CLI" in row["legacy_success_shape"]
            assert "并发已满" in row["legacy_error_shape"]
            assert row["binary_behavior"] == "json_via_node_cli"
        if row["mechanism"] == "keep_legacy_namespace":
            assert "nested legacy namespace" in row["notes"]
        if row["mechanism"] == "keep_legacy_only":
            assert "no v2 route is claimed" in row["notes"]


def test_keep_legacy_only_rows_have_no_v2_claim():
    rows = [r for r in ROWS if r["mechanism"] == "keep_legacy_only"]
    assert len(rows) == 16
    for row in rows:
        assert row["v2_target"] == ""
        assert row["legacy_success_shape"]
        assert row["fixture_ids"] == []
        assert any("test_keep_legacy_only_rows_have_no_v2_claim" in t
                   for t in row["test_ids"])


def test_namespace_rows_preserved():
    rows = [r for r in ROWS if r["mechanism"] == "keep_legacy_namespace"]
    assert len(rows) == 7
    for row in rows:
        assert row["v2_target"] == ""
        assert row["legacy_path"].startswith("/api/v1/ielts/v2/")
        assert any("test_namespace_rows_preserved" in t for t in row["test_ids"])
    asset = decisions.row_by_id("GET__api_v1_ielts_v2_asset_asset_id")
    assert asset["binary_behavior"].startswith("binary_file_response: inline")


def test_deferred_active_owner_rows():
    rows = [r for r in ROWS if r["mechanism"] == "deferred_active_owner"]
    assert len(rows) == 7
    for row in rows:
        assert row["status"] == "deferred_active_owner"
        assert "Phase A must not read" in row["notes"]
        assert any("test_deferred_active_owner_rows" in t for t in row["test_ids"])
        assert row["deferred_reason"] == row["notes"]


# ---------------------------------------------------------------------------
# node-CLI bridge envelope
# ---------------------------------------------------------------------------

def stub(outcome: RunnerOutcome, *, payload=None, exit_code: int | None = None,
         stderr_text: str | None = None, error=None) -> SimpleNamespace:
    return SimpleNamespace(outcome=outcome, payload=payload, exit_code=exit_code,
                           stderr_text=stderr_text, error=error)


def test_verbatim_board_profile_strings():
    ielts = bridge.BOARD_PROFILES["ielts"]
    toefl = bridge.BOARD_PROFILES["toefl"]
    assert ielts.queue_full_detail == "IELTS 并发已满，请稍后重试"
    assert toefl.queue_full_detail == "TOEFL 并发已满，请稍后重试"
    assert ielts.runtime_missing_detail == "找不到 node 可执行文件（可用 EXAMDATA_NODE 指定）"
    assert ielts.invalid_json_detail == "ielts-cli 输出不是合法 JSON"
    assert toefl.invalid_json_detail == "toefl-cli 输出不是合法 JSON"
    assert bridge.BOARD_PROFILES["ielts"].script == "ielts-cli.mjs"
    assert bridge.BOARD_PROFILES["toefl"].script == "toefl-cli.mjs"
    assert bridge.legacy_tail("  a\nb  ") == "a b"
    assert len(bridge.legacy_tail("x" * 500)) == 300


@pytest.mark.parametrize("board", ["ielts", "toefl"])
def test_node_bridge_envelope(board):
    profile = bridge.BOARD_PROFILES[board]

    ok = bridge.decide(board, stub(RunnerOutcome.OK, payload={"board": "kept", "n": 1}),
                       command="coverage")
    assert ok.status_code == 200 and ok.body() == {"board": "kept", "n": 1}

    decorated = bridge.decide(board, stub(RunnerOutcome.OK, payload={"n": 1}), command="x")
    assert decorated.body() == {"n": 1, "board": board}

    wrapped = bridge.decide(board, stub(RunnerOutcome.OK, payload=[1, 2]), command="x")
    assert wrapped.body() == {"board": board, "ok": True, "data": [1, 2]}

    business = bridge.decide(board, stub(RunnerOutcome.BUSINESS_FAILURE,
                                         payload={"ok": False, "error": "boom"}), command="x")
    assert business.status_code == 200
    assert business.body()["ok"] is False

    full = bridge.decide(board, stub(RunnerOutcome.QUEUE_FULL), command="x")
    assert full.status_code == 503 and full.body() == {"detail": profile.queue_full_detail}

    missing = bridge.decide(board, stub(RunnerOutcome.MISSING_COMPONENT), command="x",
                            tried=["/a", "/b"])
    assert missing.status_code == 503
    assert missing.body()["detail"] == (
        f"{profile.display} 聚合器未找到（缺少 {profile.script}）；已尝试：/a、/b")

    runtime = bridge.decide(board, stub(RunnerOutcome.MISSING_RUNTIME), command="x")
    assert runtime.status_code == 503
    assert runtime.body()["detail"] == "找不到 node 可执行文件（可用 EXAMDATA_NODE 指定）"

    startup = bridge.decide(board, stub(RunnerOutcome.STARTUP_FAILURE,
                                        error={"message": "could not start node: boom"}),
                            command="x")
    assert startup.status_code == 503
    assert startup.body()["detail"] == "无法启动 node：boom"

    timeout = bridge.decide(board, stub(RunnerOutcome.TIMEOUT), command="coverage", limit=120)
    assert timeout.status_code == 504
    assert timeout.body()["detail"] == f"{profile.display} 聚合器超时（>120s）：coverage"

    nonzero = bridge.decide(board, stub(RunnerOutcome.NONZERO_EXIT, exit_code=3,
                                        stderr_text="\n boom \n"), command="x")
    assert nonzero.status_code == 502
    assert nonzero.body()["detail"] == f"{profile.cli} 退出码 3：boom"

    invalid = bridge.decide(board, stub(RunnerOutcome.INVALID_JSON), command="x")
    assert invalid.status_code == 502
    assert invalid.body()["detail"] == profile.invalid_json_detail
    assert invalid.staged_note and "non-object stdout" in invalid.staged_note

    multi = bridge.decide(board, stub(RunnerOutcome.MULTIPLE_JSON_VALUES), command="x")
    assert multi.status_code == 502 and multi.body() == {"detail": profile.invalid_json_detail}

    overflow = bridge.decide(board, stub(RunnerOutcome.OUTPUT_OVERFLOW), command="x")
    assert overflow.status_code == 502
    assert "输出超过上限" in overflow.body()["detail"]
    assert overflow.staged_note and "staged-only" in overflow.staged_note

    denied = bridge.decide(board, stub(RunnerOutcome.COMPONENT_NOT_ALLOWED), command="x")
    assert denied.status_code == 503
    assert "配置被拒绝" in denied.body()["detail"]
    assert denied.staged_note

    cancelled = bridge.decide(board, stub(RunnerOutcome.CANCELLED), command="x")
    assert cancelled.status_code is None and cancelled.cancelled
    assert cancelled.staged_note == "legacy produced no response for a cancelled request"


def test_every_runner_outcome_is_mapped():
    for outcome in RunnerOutcome:
        response = bridge.decide("ielts", stub(outcome, exit_code=1), command="x", limit=60)
        assert isinstance(response, bridge.LegacyResponse), outcome


def test_timeout_without_limit_is_disclosed():
    response = bridge.decide("ielts", stub(RunnerOutcome.TIMEOUT), command="coverage")
    assert response.status_code == 504
    assert response.staged_note and "timeout not supplied" in response.staged_note


def test_staged_divergences_are_disclosed():
    topics = {item["topic"] for item in bridge.STAGED_DIVERGENCES}
    assert topics == {"stderr_redaction", "non_object_stdout", "stdout_budget",
                      "whitelist_rejections", "cancellation"}
    for item in bridge.STAGED_DIVERGENCES:
        assert item["legacy"] and item["staged"] and item["phase_b"]


def test_success_payloads_are_copies_not_aliases():
    original = {"n": 1}
    response = bridge.decide("ielts", stub(RunnerOutcome.OK, payload=original), command="x")
    response.payload["n"] = 99
    assert original["n"] == 99, "decorate_success edits the caller's dict in place, as legacy did"
