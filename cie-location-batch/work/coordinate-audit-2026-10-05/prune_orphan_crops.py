"""删除 visual/<paperdir>/ 下不被当前 manifest 引用的孤立裁剪图（删除区域后遗留）。

用法：python prune_orphan_crops.py 8386_2025_Jun_11 8386_2026_Jun_12 8386_2026_Jun_13
纯离线。
"""
from __future__ import annotations

import json
import os
import sys

AUD = r"C:/Users/weo/Desktop/api/cie-location-batch/work/coordinate-audit-2026-10-05"
VIS = os.path.join(AUD, "visual")


def main() -> int:
    for paperdir in sys.argv[1:]:
        d = os.path.join(VIS, paperdir)
        man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
        keep = set()
        for m in man["regions"]:
            for field in ("crop", "crop_display", "page_image"):
                v = m.get(field)
                if v:
                    keep.add(v.replace("\\", "/"))
        removed = []
        for name in sorted(os.listdir(d)):
            if not name.endswith(".png"):
                continue
            if name in keep or name.endswith("-full.png"):
                continue
            os.remove(os.path.join(d, name))
            removed.append(name)
        print(json.dumps({"paperdir": paperdir, "kept": len(keep),
                          "removed": removed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
