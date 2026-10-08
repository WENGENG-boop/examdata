"""离线回归测试：几何往返、校验器拒绝项、清理拒绝、状态镜像、导入比较。

全部离线，不联网、不改共享状态：
- 临时产物写在 `tmp/_test_pipeline/` 下；
- 需要伪造状态的用例用合成 key，并且只写 `work/state.json` 镜像，跑完删掉；
- 清理用例把 `B.INDEXES` 临时指向临时目录，绝不触碰真实 `indexes/`。

两种跑法都支持：
    $PY -m pytest tools/test_pipeline.py -q
    $PY tools/test_pipeline.py
"""
from __future__ import annotations

import io
import json
import shutil
import statistics
import sys
import traceback
from pathlib import Path

import batchlib as B
import paperlib as P
import pipelinestate as S
import validate_index as V
import import_index as I
import cleanup_paper as C
import propose as R
import sheet as H

KEY = "9709/2024/Jun/11"
REFERENCE = Path("C:/Users/weo/Desktop/api/cie-index-batch-2026-10-01"
                 "/9709/2024-Jun-11/cie-index.json")
SCRATCH = B.TMP / "_test_pipeline"
PROPOSAL = B.WORK / "proposals" / "9709" / "2024-Jun-11.json"
MIN_INK_STD = 20.0

_PROPOSAL: dict = {}


def proposal() -> dict:
    if not _PROPOSAL:
        if not PROPOSAL.is_file():
            code = R.build(KEY, False)
            assert code == 0, f"propose.build({KEY}) 返回 {code}"
        _PROPOSAL.update(json.loads(PROPOSAL.read_text(encoding="utf-8")))
    return _PROPOSAL


def sample_std(pix) -> float:
    data = pix.samples
    step = max(1, len(data) // 120000)
    return statistics.pstdev(data[::step])


def base_index() -> dict:
    return {
        "schema_version": "1",
        "board": "cie",
        "identity": {"subject": "9709", "year": 2024, "season": "Jun", "paper": "11"},
        "coordinate_system": "unrotated_pdf_points_top_left",
        "page_base": 1,
        "documents": [{"role": "qp", "sha256": "0" * 64}],
        "questions": [
            {"question": "1", "parent": None, "text": "Find x.", "marks": 2,
             "qp": [{"page": 1, "bbox": [10.0, 10.0, 100.0, 100.0]}],
             "ms": [], "uncertain": False, "notes": "ok"},
            {"question": "1(a)", "parent": "1", "text": "Sub.", "marks": 2,
             "qp": [{"page": 1, "bbox": [10.0, 110.0, 100.0, 200.0]}],
             "ms": [], "uncertain": False, "notes": "ok"},
        ],
    }


def write_index(data: dict, name: str) -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    path = SCRATCH / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def errors_for(data: dict, name: str, **kwargs) -> list[str]:
    report = V.validate(write_index(data, name), **kwargs)
    return report["errors"]


def test_ms_strip_crop_roundtrip() -> None:
    """MS 第 6 页 1(a) 条带：旋转页的裁剪必须按显示方向出图，且非空白。"""
    data = proposal()
    band = next(c for c in data["ms_candidates"]
                if c["page"] == 6 and c["label"] == "1(a)")
    bbox = band["row_bbox"]
    assert band["row_source"] == "rule", band
    assert band["page_has_table_header"] is True, band

    ms = I.locate_pdf(KEY, "ms")
    assert ms is not None, "找不到 MS PDF"
    out = SCRATCH / "ms-p6-1a.png"
    P.crop_region(ms, 6, bbox, out)

    import pymupdf
    pix = pymupdf.Pixmap(str(out))
    want_w = round((bbox[3] - bbox[1]) * P.CROP_ZOOM)
    want_h = round((bbox[2] - bbox[0]) * P.CROP_ZOOM)
    assert abs(pix.width - want_w) <= 2, f"宽 {pix.width} 期望 {want_w}"
    assert abs(pix.height - want_h) <= 2, f"高 {pix.height} 期望 {want_h}"
    assert pix.width > pix.height, "条带应是竖长条（宽>高）"
    std = sample_std(pix)
    assert std > MIN_INK_STD, f"条带疑似空白，std={std:.2f}"


def test_qp_page_crop_roundtrip() -> None:
    """QP（rotation 0）裁剪按原始方向出图。"""
    data = proposal()
    top = next(c for c in data["question_candidates"] if c["question"] == "1")
    bbox = top["bbox"]
    qp = I.locate_pdf(KEY, "qp")
    assert qp is not None
    out = SCRATCH / "qp-p2-q1.png"
    P.crop_region(qp, top["regions"][0]["page"], bbox, out)
    import pymupdf
    pix = pymupdf.Pixmap(str(out))
    assert abs(pix.width - round((bbox[2] - bbox[0]) * P.CROP_ZOOM)) <= 2
    assert abs(pix.height - round((bbox[3] - bbox[1]) * P.CROP_ZOOM)) <= 2
    assert sample_std(pix) > MIN_INK_STD


def test_proposal_matches_reference_question_set() -> None:
    data = proposal()
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    mine = [q["question"] for q in data["question_candidates"]]
    theirs = [q["question"] for q in reference["questions"]]
    assert sorted(mine) == sorted(theirs), (
        f"只在我这：{sorted(set(mine) - set(theirs))}；"
        f"只在参考：{sorted(set(theirs) - set(mine))}")
    assert len(mine) == 32
    assert data["stats"]["top_level"] == 11
    assert data["qp_total_marks"] == 75
    assert data["qp_leaf_marks_total"] == 75
    assert len(data["ms_candidates"]) == 30
    assert data["qp_sha256"] == B.sha256_file(I.locate_pdf(KEY, "qp"))
    assert data["ms_sha256"] == B.sha256_file(I.locate_pdf(KEY, "ms"))


def test_sibling_regions_do_not_overlap() -> None:
    """同一父题下相邻兄弟的区域不得互相重叠（按行聚类修复的回归）。"""
    data = proposal()
    for parent in {q["parent"] for q in data["question_candidates"]}:
        siblings = [q for q in data["question_candidates"] if q["parent"] == parent]
        for i, a in enumerate(siblings):
            for b in siblings[i + 1:]:
                for ra in a["regions"]:
                    for rb in b["regions"]:
                        if ra["page"] != rb["page"]:
                            continue
                        x0, y0, x1, y1 = ra["bbox"]
                        u0, v0, u1, v1 = rb["bbox"]
                        overlap = (min(x1, u1) - max(x0, u0)) * (min(y1, v1) - max(y0, v0))
                        assert overlap <= 0, (
                            f"{a['question']} 与 {b['question']} 在第 {ra['page']} 页重叠")


def test_validator_rejects_missing_qp() -> None:
    data = base_index()
    del data["questions"][0]["qp"]
    assert errors_for(data, "bad-missing-qp.json")


def test_validator_rejects_bad_parent() -> None:
    data = base_index()
    data["questions"][1]["parent"] = "9"
    errors = errors_for(data, "bad-parent.json")
    assert any("parent" in e for e in errors), errors


def test_validator_rejects_duplicate_question() -> None:
    data = base_index()
    data["questions"][1]["question"] = "1"
    data["questions"][1]["parent"] = None
    errors = errors_for(data, "bad-duplicate.json")
    assert any("重复" in e for e in errors), errors


def test_validator_rejects_out_of_bounds_bbox() -> None:
    qp = I.locate_pdf(KEY, "qp")
    assert qp is not None
    data = base_index()
    data["documents"] = [{"role": "qp", "sha256": B.sha256_file(qp)}]
    data["questions"][0]["qp"] = [{"page": 1, "bbox": [10.0, 10.0, 100.0, 5000.0]}]
    errors = errors_for(data, "bad-bbox.json", qp=qp)
    assert any("超出第 1 页分析范围" in e for e in errors), errors


def test_validator_rejects_page_beyond_count() -> None:
    qp = I.locate_pdf(KEY, "qp")
    assert qp is not None
    data = base_index()
    data["documents"] = [{"role": "qp", "sha256": B.sha256_file(qp)}]
    data["questions"][0]["qp"] = [{"page": 99, "bbox": [10.0, 10.0, 100.0, 100.0]}]
    errors = errors_for(data, "bad-page.json", qp=qp)
    assert any("超出 qp 文档页数" in e for e in errors), errors


def test_validator_rejects_extra_field() -> None:
    data = base_index()
    data["questions"][0]["colour"] = "red"
    assert errors_for(data, "bad-extra.json")


def test_validator_rejects_bad_sha256() -> None:
    data = base_index()
    data["documents"][0]["sha256"] = "nothex"
    assert errors_for(data, "bad-sha.json")


def test_validator_rejects_marks_as_string() -> None:
    data = base_index()
    data["questions"][0]["marks"] = "2"
    assert errors_for(data, "bad-marks.json")


def test_validator_rejects_long_notes() -> None:
    data = base_index()
    data["questions"][0]["notes"] = "x" * 2001
    assert errors_for(data, "bad-notes.json")


def test_validator_accepts_base_index() -> None:
    report = V.validate(write_index(base_index(), "good.json"))
    assert report["errors"] == [], report["errors"]


def test_cleanup_refuses_when_verification_incomplete() -> None:
    """条件 (b) 不满足时必须拒绝，且一个文件都不删。"""
    key = "9709/2099/Jun/98"
    scratch_indexes = SCRATCH / "indexes"
    real_indexes = B.INDEXES
    before = sorted(str(p) for p in (B.TMP / "9709").glob("**/*")) if (B.TMP / "9709").is_dir() else []
    B.INDEXES = scratch_indexes
    try:
        index_file = B.index_dir("9709", 2099, "Jun", "98") / "cie-index.json"
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text(json.dumps(base_index(), ensure_ascii=False), encoding="utf-8")
        S.update(key, stage="imported_verified", import_succeeded=True,
                 readback_verified=True, stage_at=B.now_iso())

        problems, info = C.check_conditions(key)
        assert info["state_source"] == "work/state.json", info
        assert any("verification.jsonl" in p for p in problems), problems
        assert not any("stage 不是" in p for p in problems), problems
        assert not any("import_succeeded" in p for p in problems), problems

        report = C.cleanup(key)
        assert report["stage"] == "cleanup_refused", report
        assert report["exit_code"] == C.EXIT_REFUSED
        assert report["deleted"] == []
        assert report["freed_bytes"] == 0
    finally:
        B.INDEXES = real_indexes
        state = S.load_all()
        state.pop(key, None)
        B.atomic_write_json(S.STATE, state)
        shutil.rmtree(scratch_indexes, ignore_errors=True)
    after = sorted(str(p) for p in (B.TMP / "9709").glob("**/*")) if (B.TMP / "9709").is_dir() else []
    assert before == after, "拒绝路径动了临时文件"


def test_cleanup_deletes_only_whitelisted_scratch() -> None:
    """成功路径：只删白名单文件，越界目标一律拒绝。用合成 key，不碰真数据。"""
    key = "9709/2099/Jun/96"
    tmp_dir = P.paper_tmp(key)
    outside = tmp_dir.parent / "outside-96.txt"
    real_log = B.CLEANUP
    B.CLEANUP = SCRATCH / "cleanup.jsonl"
    try:
        (tmp_dir / "pages").mkdir(parents=True, exist_ok=True)
        (tmp_dir / "crops").mkdir(parents=True, exist_ok=True)
        (tmp_dir / "9709_s99_qp_96.pdf").write_bytes(b"%PDF-1.4 fake")
        (tmp_dir / "leftover.part").write_bytes(b"x" * 10)
        (tmp_dir / "pages" / "qp-p001.png").write_bytes(b"p" * 20)
        (tmp_dir / "crops" / "c1.png").write_bytes(b"c" * 30)
        (tmp_dir / "keep.txt").write_text("keep", encoding="utf-8")
        outside.write_text("outside", encoding="utf-8")

        names = sorted(p.name for p in C.collect_targets(key))
        assert names == ["9709_s99_qp_96.pdf", "c1.png", "leftover.part", "qp-p001.png"], names

        report = C.cleanup(key, force=True)
        assert report["stage"] == "cleaned", report
        assert report["residual"] == [], report
        assert report["freed_bytes"] == 10 + 20 + 30 + len(b"%PDF-1.4 fake")
        assert not (tmp_dir / "9709_s99_qp_96.pdf").exists()
        assert not (tmp_dir / "pages").joinpath("qp-p001.png").exists()
        assert (tmp_dir / "keep.txt").exists(), "白名单外的文件被删了"
        assert outside.exists(), "越界文件被删了"

        deleted, refused, freed = C.delete_targets(key, [outside])
        assert deleted == [] and freed == 0
        assert refused and "不在允许的目录内" in refused[0], refused
        assert outside.exists()
    finally:
        B.CLEANUP = real_log
        state = S.load_all()
        state.pop(key, None)
        B.atomic_write_json(S.STATE, state)
        outside.unlink(missing_ok=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_state_mirror_fallback() -> None:
    key = "9709/2099/Jun/97"
    try:
        S.update(key, stage="proposed", import_succeeded=False)
        entry, source = S.entry(key)
        assert source == "work/state.json", source
        assert entry["stage"] == "proposed"
        assert S.load(key)["mirror_at"]
    finally:
        state = S.load_all()
        state.pop(key, None)
        B.atomic_write_json(S.STATE, state)
    assert S.load(key) is None


def test_compare_index_ignores_order_and_format() -> None:
    local = base_index()
    local2 = json.loads(json.dumps(local))
    local2["questions"][1]["qp"].append({"page": 2, "bbox": [1.0, 2.0, 3.0, 4.0]})
    remote2 = json.loads(json.dumps(local2))
    remote2["questions"][1]["qp"].reverse()
    remote2["questions"][1]["qp"][0]["bbox"] = [1, 2, 3, 4]
    remote2["documents"].reverse()
    remote2["method"] = "external_ai"
    remote2["reviewed"] = False

    errors, _warnings = I.compare_index(local2, remote2)
    assert errors == [], errors

    drifted = json.loads(json.dumps(remote2))
    drifted["questions"][1]["marks"] = 99
    errors, _warnings = I.compare_index(local2, drifted)
    assert any("marks 不一致" in e for e in errors), errors

    missing = json.loads(json.dumps(local))
    missing["questions"].pop()
    errors, _warnings = I.compare_index(local, missing)
    assert any("题数不一致" in e for e in errors), errors


def test_sheet_cell_geometry() -> None:
    cell, rows, capacity = H.cell_geometry(2)
    assert cell <= H.CELL_MAX and cell >= H.CELL_MIN, cell
    assert rows * cell <= H.SHEET_PX
    assert capacity == 2 * rows
    assert cell * 2 <= H.SHEET_PX
    try:
        H.cell_geometry(5)
    except ValueError as exc:
        assert "低于" in str(exc)
    else:
        raise AssertionError("cols=5 应被拒绝")


def main() -> int:
    if (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower() != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    tests = [(name, obj) for name, obj in sorted(globals().items())
             if name.startswith("test_") and callable(obj)]
    failed = []
    for name, func in tests:
        try:
            func()
        except Exception:
            failed.append(name)
            print(f"[FAIL] {name}")
            traceback.print_exc()
        else:
            print(f"[PASS] {name}")
    print()
    if failed:
        print(f"回归失败 {len(failed)}/{len(tests)} 项: {failed}")
        return 1
    print(f"全部 {len(tests)} 项回归通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
