"""汇总离线回归：推断格不冒充请求；旧清单和 cleaned 不冒充验收。"""
import json

import batchlib as B
import build_summary as S
import service_audit as A


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_summary_reads_actual_service_and_keeps_validation_gaps(tmp_path, monkeypatch):
    for name, value in {
        "BATCH_ROOT": tmp_path, "SERVICE_DATA_DIR": tmp_path / "service",
        "INDEXES": tmp_path / "indexes", "TMP": tmp_path / "tmp",
        **{n: tmp_path / f"{n.lower()}.json" for n in
           ("SUBJECTS", "GRID", "PAPERS", "CHECKPOINT", "ERRORS", "VERIFICATION", "CLEANUP")},
    }.items():
        monkeypatch.setattr(B, name, value)
    B.TMP.mkdir()
    write(B.SUBJECTS, {"subjects": [{"code": "9709", "cells_total": 4,
                                    "third_party_confirmed": True}]})
    write(B.GRID, {"a": {"requested": True, "status": "complete"},
                   "b": {"requested": False, "status": "subject_unavailable_inferred"},
                   "c": {"requested": False, "status": "subject_unavailable_inferred"}})
    write(B.PAPERS, {"9709/2024/Jun/11": {"stage": "cleaned", "readback_verified": True}})
    B.CLEANUP.write_text("\n".join(json.dumps(r) for r in [
        {"key": "9709/2024/Jun/11", "stage": "cleanup_pending", "targets": ["x.pdf"]},
        {"key": "9709/2024/Jun/11", "stage": "cleaned", "deleted": 1},
        {"key": "9709/2024/Jun/11", "stage": "cleanup_pending", "targets": []},
        {"key": "9709/2024/Jun/11", "stage": "cleaned", "deleted": 0},
    ]), encoding="utf8")
    local = {"identity": {"subject": "9709", "year": 2024, "season": "Jun", "paper": "11"},
             "documents": [{"role": "qp", "sha256": "a" * 64}],
             "questions": [{"question": "1", "text": "local", "qp": [], "ms": []}]}
    write(B.INDEXES / "9709/2024-Jun-11/cie-index.json", local)
    sp = B.SERVICE_DATA_DIR / f"question_indexes/cie/{'a' * 64}.json"
    write(sp, dict(local, reviewed=False, method="external_ai"))
    write(tmp_path / "service-index-manifest.json", {"count": 99, "in_service": 0})
    monkeypatch.setattr(A.C, "verification_state", lambda *args: (["缺失目视证据"], {"missing": 1}))
    result = S.build()
    assert result["catalogue_cells"]["actually_requested"] == 1
    assert result["catalogue_cells"]["inferred_not_requested"] == 2
    assert result["catalogue_cells"]["unqueried"] == 1
    assert result["service_index"]["in_service"] == 1
    assert result["service_index"]["comparison_counts"] == {"identical": 1}
    assert result["pipeline"]["fully_verified"] == 0
    assert result["pipeline"]["cleaned_needing_reverification"] == 1
    assert result["cleanup"]["cleaned_papers"] == 1
    assert result["cleanup"]["deleted_pdfs"] == 1
    assert result["cleanup"]["pending"] == 0
    changed = json.loads(json.dumps(local))
    changed["questions"][0]["text"] = "older service version"
    write(sp, changed)
    result = S.build()
    assert result["service_index"]["comparison_counts"] == {"different": 1}
    manifest = json.loads((tmp_path / "service-index-manifest.json").read_text(encoding="utf8"))
    assert manifest["entries"][0]["changed_fields"] == {"text": 1}
    sp.unlink()
    assert S.build()["service_index"]["comparison_counts"] == {"missing": 1}
