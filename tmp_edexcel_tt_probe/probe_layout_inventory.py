"""全量版式清单：遍历 downloads/edexcel 下全部 PDF，收集表格表头签名。

输出 evidence/layout_inventory.json：
  - signatures: {签名 -> {count, files, sample_rows}}
  - page_types: 每个文件每页的表格数/表头
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent
DL = ROOT / "downloads" / "edexcel"
OUT = ROOT / "evidence" / "layout_inventory.json"


def norm_cell(text) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def header_sig(rows) -> tuple[str, ...]:
    if not rows:
        return ()
    first = rows[0]
    return tuple(norm_cell(c) for c in first)


def main() -> int:
    files = sorted(DL.rglob("*.pdf"))
    print(f"{len(files)} files")
    sig_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "files": [], "sample_rows": []})
    file_types: dict[str, list] = {}
    for fi, path in enumerate(files):
        rel = str(path.relative_to(DL)).replace("\\", "/")
        types = []
        try:
            doc = pymupdf.open(path)
        except Exception as exc:
            types.append({"error": str(exc)})
            file_types[rel] = types
            continue
        for pno, page in enumerate(doc):
            try:
                tables = page.find_tables()
            except Exception as exc:
                types.append({"page": pno + 1, "error": str(exc)})
                continue
            for t in tables.tables:
                rows = t.extract()
                if not rows:
                    continue
                sig = header_sig(rows)
                sig_text = " | ".join(sig)[:200]
                key = sig_text
                entry = sig_stats[key]
                entry["count"] += 1
                if rel not in entry["files"]:
                    entry["files"].append(rel)
                if len(entry["sample_rows"]) < 3:
                    sample = []
                    for row in rows[:4]:
                        sample.append([None if c is None else re.sub(r"\s+", " ", str(c))[:120] for c in row])
                    entry["sample_rows"].append({"file": rel, "page": pno + 1, "rows": sample})
                types.append({"page": pno + 1, "sig": sig_text})
        doc.close()
        file_types[rel] = types
        if (fi + 1) % 20 == 0:
            print(f"  ... {fi + 1}/{len(files)}")

    out = {
        "files": len(files),
        "signatures": dict(sorted(sig_stats.items(), key=lambda kv: -kv[1]["count"])),
        "file_types": file_types,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("signatures:")
    for sig, entry in sorted(sig_stats.items(), key=lambda kv: -kv[1]["count"]):
        print(f"  [{entry['count']:4d}] {sig[:150]}")
        print(f"         files({len(entry['files'])}): {', '.join(entry['files'][:4])}{' ...' if len(entry['files']) > 4 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
