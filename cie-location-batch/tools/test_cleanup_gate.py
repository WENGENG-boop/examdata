"""清理闸门的离线回归：证明「自述未做视觉核验」的区域确实会挡住删除。

不联网、不碰真实 verification.jsonl：把 B.VERIFICATION 指到临时文件，
构造一个区域，分别喂「通过 / 失败 / 自述没做视觉核验」三种记录，看
`verification_state` 是否按预期返回问题。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import batchlib as B
import cleanup_paper as C

REGIONS = {("1(a)", "qp", 2, (40.0, 80.0, 550.0, 220.0))}


def run_case(records: list[dict]) -> tuple[list[str], dict]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "verification.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
                        encoding="utf-8")
        saved_v, saved_r, saved_vb, saved_sha = B.VERIFICATION, C.index_regions, C.voided_before, C.current_index_sha256
        B.VERIFICATION = path
        C.index_regions = lambda key: set(REGIONS)
        C.voided_before = lambda key: []
        C.current_index_sha256 = lambda key: "a" * 64
        try:
            return C.verification_state("0000/2000/Jun/11", ["1", "1(a)"])
        finally:
            B.VERIFICATION, C.index_regions, C.voided_before = saved_v, saved_r, saved_vb
            C.current_index_sha256 = saved_sha


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"{'PASS' if cond else 'FAIL'}  {name}{'' if cond else '  <- ' + detail}")
        if not cond:
            failures.append(name)

    base = {"key": "0000/2000/Jun/11", "question": "1(a)", "role": "qp", "page": 2,
            "bbox": [40.0, 80.0, 550.0, 220.0], "checked_at": "2026-10-01T20:00:00+0800",
            "method": "browser_visual_snapshot",
            "index_sha256": "a" * 64,
            "checks": {"observed": "合成复核记录：题干、图形及边界完整，区域对应本题",
                       "content_complete": True, "boundary_checked": True, "role_matches": True}}

    problems, stats = run_case([dict(base, issues=[])])
    check("通过记录不挡清理", problems == [] and stats["failed"] == 0, str(problems))

    for previous_hash in (None, "b" * 64):
        problems, stats = run_case([dict(base, issues=[], index_sha256=previous_hash)])
        check(f"相同bbox但缺失或旧索引哈希不放行：{previous_hash}",
              bool(problems) and stats["visual_evidence_missing"] == 1, str(problems))

    problems, stats = run_case([dict(base, issues=["bbox 混入下一题"])])
    check("失败记录挡住清理", any("未通过" in p for p in problems), str(problems))

    problems, stats = run_case([dict(base, issues=["未做视觉核验：浏览器快照 PAGE_NOT_READY"],
                                     method=None)])
    check("自述未做视觉核验挡住清理",
          any("自述未做视觉核验" in p for p in problems) and stats["self_declared_unverified"] == 1,
          f"{problems} stats={stats}")

    problems, stats = run_case([dict(base, issues=[], notes="本轮未做视觉核验，仅按文字层推导")])
    check("notes 里自述未核验也挡住",
          any("自述未做视觉核验" in p for p in problems) and stats["self_declared_unverified"] == 1,
          f"{problems} stats={stats}")

    problems, stats = run_case([dict(base, issues=["PAGE_NOT_READY"], method=None)])
    check("issues 里出现 PAGE_NOT_READY 挡住",
          stats["self_declared_unverified"] == 1, f"{problems} stats={stats}")

    problems, stats = run_case([dict(base, issues=[]),
                                dict(base, issues=["未做视觉核验"], checked_at="2026-10-01T21:00:00+0800")])
    check("同一区域取最新一条（新的没核验则挡住）",
          stats["self_declared_unverified"] == 1, f"{problems} stats={stats}")

    problems, stats = run_case([dict(base, issues=["未做视觉核验"], checked_at="2026-10-01T19:00:00+0800"),
                                dict(base, issues=[], checked_at="2026-10-01T21:00:00+0800")])
    check("旧的不核验记录被新通过记录覆盖",
          problems == [] and stats["self_declared_unverified"] == 0, f"{problems} stats={stats}")

    for method in (None, "local_crop+ocr",
                   "local_crop+Windows.Media.Ocr(zh-Hans-CN); 未做 page.visual.snapshot"):
        problems, stats = run_case([dict(base, issues=[], method=method)])
        check(f"OCR 或缺失来源不放行：{method}", bool(problems)
              and stats["visual_evidence_missing"] == 1, str(problems))
    for field in ("observed", "content_complete", "boundary_checked", "role_matches"):
        checks = dict(base["checks"])
        checks.pop(field)
        problems, stats = run_case([dict(base, issues=[], checks=checks)])
        check(f"缺失目视检查证据不放行：{field}", bool(problems), str(problems))

    print()
    print("ALL PASS" if not failures else f"FAILURES: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
