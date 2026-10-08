"""生成 CIE Zone 5 时间表快照（`data/zone5/`）。

用法：
    python -m examdata.timetable.build --pdf-dir <zone5_final 目录> \
        --matrix <zone5_final_matrix.json>

产物：
    data/zone5/index.json          考季索引 + 不可得考季证据
    data/zone5/YYYY-MM.json        单季事件、日期窗口、未解析行

PDF 目录与证据矩阵默认从本仓库旁的 tmp_materials_probe 取，可用
`--pdf-dir` / `--matrix` 或环境变量 `EXAMDATA_ZONE5_PDF_DIR` /
`EXAMDATA_ZONE5_MATRIX` 覆盖。构建脚本只在离线环境使用，不进 API 运行时。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .parser import iter_seasons, parse_pdf, season_key

SCHEMA_VERSION = "1"
ZONE = 5
BOARD = "cie"
DATA_DIR = Path(__file__).resolve().parent / "data" / "zone5"

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _default_pdf_dir() -> Path:
    env = os.environ.get("EXAMDATA_ZONE5_PDF_DIR")
    if env:
        return Path(env)
    return _REPO_ROOT.parent / "tmp_materials_probe" / "downloads" / "zone5_final"


def _default_matrix() -> Path:
    env = os.environ.get("EXAMDATA_ZONE5_MATRIX")
    if env:
        return Path(env)
    return _REPO_ROOT.parent / "tmp_materials_probe" / "evidence" / "zone5_final_matrix.json"


def _split_reason(raw: str) -> tuple[str, str]:
    """`unobtainable` 里的说明：短原因 + 完整证据原文。

    只在首个分隔符前的内容足够成句时才切分；像「该季文件（…）」这类
    括号紧跟主语的写法，切分会丢语义，此时原因取全文。
    """
    head = re.split(r"[（(]", raw, maxsplit=1)[0]
    head = re.split(r"[，,；;]", head, maxsplit=1)[0].strip()
    if len(head) < 12:
        head = raw.strip()
    return head or raw.strip(), raw.strip()


UNOBTAINABLE_SEARCH_NOTE_ZH = (
    "不可得考季均经穷尽检索确认无可取回文件："
    "①CDX 多模式（zone-5/zone5/zone 5 与 /images 前缀）候选全量在线测试；"
    "②按文件 ID 扫描 Wayback 全部快照（复用 URL 按快照时点区分考季）；"
    "③从归档的 exam-timetables 目录页 HTML 提取当季链接；"
    "④旧域名 CDX 检索（cie.org.uk / www.cie.org.uk 与 Images/images 两形态）"
    "——2013–2016 七季由此取回，2019-06、2020-11 为零结果。"
    "如后续出现新存档可按同流程补入；详见 research/exam-timetable-cie-zone5.md §4。"
)


def _load_matrix(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_one(args: tuple[str, int, str]) -> dict[str, Any]:
    path, year, series = args
    return parse_pdf(Path(path), year, series)


def build(pdf_dir: Path, matrix_path: Path, data_dir: Path, *, workers: int = 4) -> dict[str, Any]:
    """解析全部 PDF 并写出索引与单季 JSON，返回索引字典。"""
    seasons = list(iter_seasons(pdf_dir))
    if not seasons:
        raise SystemExit(f"{pdf_dir} 下没有 YYYY-06/YYYY-11 形态的时间表 PDF")
    tasks = [(str(path), year, series) for path, year, series in seasons]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        parsed = list(pool.map(_parse_one, tasks))
    parsed.sort(key=lambda item: item["key"])

    matrix = _load_matrix(matrix_path)
    matrix_seasons = matrix.get("seasons") or {}
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    data_dir.mkdir(parents=True, exist_ok=True)
    generated_from: dict[str, Any] = {}
    index_seasons: list[dict[str, Any]] = []
    total_events = 0
    total_windows = 0
    for season in parsed:
        key = season["key"]
        meta = matrix_seasons.get(key) or {}
        url = meta.get("source_url") or meta.get("wayback_replay_url")
        source = {
            "file": season["file"],
            "sha256": season["sha256"],
            "pages": season["pages"],
            "url": url,
            "source_kind": meta.get("source_kind"),
        }
        generated_from[key] = dict(source)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "zone": ZONE,
            "board": BOARD,
            "key": key,
            "year": season["year"],
            "season": season["series"],
            "generated_at": generated_at,
            "source": source,
            "count": len(season["events"]),
            "events": season["events"],
            "date_windows": season["date_windows"],
            "unparsed_rows": season["unparsed_rows"],
            "stats": season["stats"],
        }
        (data_dir / f"{key}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        index_seasons.append(
            {
                "year": season["year"],
                "season": season["series"],
                "key": key,
                "available": True,
                "events_count": len(season["events"]),
                "date_windows_count": len(season["date_windows"]),
                "unparsed_count": len(season["unparsed_rows"]),
                "source": source,
            }
        )
        total_events += len(season["events"])
        total_windows += len(season["date_windows"])

    unobtainable: list[dict[str, Any]] = []
    for key, raw_reason in sorted((matrix.get("unobtainable") or {}).items()):
        try:
            year_text, month = key.split("-")
            series = "Jun" if month == "06" else "Nov"
        except ValueError:
            continue
        reason, evidence = _split_reason(str(raw_reason))
        unobtainable.append(
            {
                "year": int(year_text),
                "season": series,
                "key": key,
                "reason": reason,
                "evidence": evidence,
                "search_exhausted": True,
            }
        )

    index = {
        "schema_version": SCHEMA_VERSION,
        "zone": ZONE,
        "board": BOARD,
        "generated_at": generated_at,
        "generated_from": generated_from,
        "seasons": index_seasons,
        "unobtainable": unobtainable,
        "unobtainable_search_note_zh": UNOBTAINABLE_SEARCH_NOTE_ZH,
        "totals": {
            "available_seasons": len(index_seasons),
            "events": total_events,
            "date_windows": total_windows,
            "unobtainable_seasons": len(unobtainable),
        },
    }
    (data_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 CIE Zone 5 时间表快照")
    parser.add_argument("--pdf-dir", type=Path, default=_default_pdf_dir())
    parser.add_argument("--matrix", type=Path, default=_default_matrix())
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    index = build(args.pdf_dir, args.matrix, args.data_dir, workers=max(1, args.workers))
    totals = index["totals"]
    print(
        f"OK: {totals['available_seasons']} seasons, {totals['events']} events, "
        f"{totals['date_windows']} date windows, "
        f"{totals['unobtainable_seasons']} unobtainable"
    )
    for season in index["seasons"]:
        print(f"  {season['key']}: {season['events_count']} events, {season['date_windows_count']} windows")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
