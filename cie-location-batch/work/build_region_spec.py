"""从索引 JSON 生成 stacksheet 用的区域 spec（qp 与 ms 各一份）。

用法：python work/build_region_spec.py <subject>/<year>/<season>/<paper>
输出：work/spec-<slug>-qp.json / work/spec-<slug>-ms.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import import_index as I  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    key = sys.argv[1]
    index_path = I.index_path(key)
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    slug = key.replace("/", "-")
    specs = {"qp": [], "ms": []}
    for q in idx["questions"]:
        name = q["question"]
        for role in ("qp", "ms"):
            regions = q.get(role) or []
            for i, r in enumerate(regions, 1):
                label = name if len(regions) == 1 else f"{name}#{i}"
                specs[role].append({"label": label, "role": role,
                                    "page": r["page"], "bbox": r["bbox"]})
    for role, items in specs.items():
        out = ROOT / "work" / f"spec-{slug}-{role}.json"
        out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{role}: {len(items)} 个区域 -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
