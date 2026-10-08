"""生成 Edexcel 时间表快照（`data/edexcel/`）。

用法：
    python -m examdata.timetable.build_edexcel --pdf-dir <edexcel 下载目录> \
        --manifest <edexcel_manifest.json>

产物：
    data/edexcel/index.json                    考季索引（含 cancelled 与不可得考季证据）
    data/edexcel/<family>/YYYY-MM[-r].json     单季事件、日期窗口、未解析行

PDF 目录与抓取清单默认从本仓库旁的 tmp_edexcel_tt_probe 取，可用 `--pdf-dir` /
`--manifest` 或环境变量 `EXAMDATA_EDEXCEL_PDF_DIR` / `EXAMDATA_EDEXCEL_MANIFEST`
覆盖。构建脚本只在离线环境使用，不进 API 运行时。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .edexcel_parser import iter_seasons, month_name, parse_pdf, season_key

SCHEMA_VERSION = "1"
BOARD = "edexcel"
DATA_DIR = Path(__file__).resolve().parent / "data" / "edexcel"

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _default_pdf_dir() -> Path:
    env = os.environ.get("EXAMDATA_EDEXCEL_PDF_DIR")
    if env:
        return Path(env)
    return _REPO_ROOT.parent / "tmp_edexcel_tt_probe" / "downloads" / "edexcel"


def _default_manifest() -> Path:
    env = os.environ.get("EXAMDATA_EDEXCEL_MANIFEST")
    if env:
        return Path(env)
    return _REPO_ROOT.parent / "tmp_edexcel_tt_probe" / "downloads" / "edexcel_manifest.json"


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _split_key(key: str) -> tuple[str, int, int, bool]:
    """解析清单考季键 `family|YYYY|MM[|R]`。"""
    parts = str(key).split("|")
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        raise ValueError(f"非法考季键: {key!r}")
    return parts[0], int(parts[1]), int(parts[2]), len(parts) > 3 and parts[3].upper() == "R"


def _parse_one(task: tuple[str, str, int, int, bool]) -> dict[str, Any]:
    path, family, year, month, r_paper = task
    return parse_pdf(Path(path), family, year, month, r_paper=r_paper)


def _source_from_manifest(season: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    manifest_source = meta.get("source") or {}
    return {
        "file": season["file"],
        "sha256": season["sha256"],
        "pages": season["pages"],
        "url": manifest_source.get("url"),
        "fetch_url": manifest_source.get("fetch_url"),
        "source_kind": manifest_source.get("kind"),
        "label": meta.get("label"),
    }


def _extra_sources(meta: dict[str, Any]) -> list[dict[str, Any]]:
    extra = meta.get("extra") or None
    if not extra:
        return []
    source = extra.get("source") or {}
    return [
        {
            "file": Path(str(extra.get("file", ""))).name,
            "label": extra.get("label"),
            "url": source.get("url"),
            "fetch_url": source.get("fetch_url"),
            "source_kind": source.get("kind"),
        }
    ]


def _unobtainable_entry(key: str, reason: str, evidence: Any) -> dict[str, Any] | None:
    try:
        family, year, month, r_paper = _split_key(key)
    except ValueError:
        return None
    return {
        "family": family,
        "year": year,
        "month": month,
        "season": month_name(month),
        "variant": "R" if r_paper else "standard",
        "key": key,
        "reason": reason,
        "evidence": evidence,
        "search_exhausted": True,
    }


def _season_payload(season: dict[str, Any], generated_at: str, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "board": BOARD,
        "key": season["key"],
        "family": season["family"],
        "year": season["year"],
        "month": season["month"],
        "season": month_name(season["month"]),
        "variant": season["variant"],
        "generated_at": generated_at,
        "source": source,
        "count": len(season["events"]),
        "events": season["events"],
        "date_windows": season["date_windows"],
        "unparsed_rows": season["unparsed_rows"],
        "stats": season["stats"],
    }


def build(pdf_dir: Path, manifest_path: Path, data_dir: Path, *, workers: int = 4) -> dict[str, Any]:
    """解析全部 PDF 并写出索引与单季 JSON，返回索引字典。"""
    seasons = list(iter_seasons(pdf_dir))
    if not seasons:
        raise SystemExit(f"{pdf_dir} 下没有 YYYY-MM[-r].pdf 形态的时间表 PDF")
    tasks = [
        (str(path), family, year, month, r_paper)
        for path, family, year, month, r_paper in seasons
    ]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        parsed = list(pool.map(_parse_one, tasks))
    parsed.sort(key=lambda item: item["key"])

    manifest = _load_manifest(manifest_path)
    manifest_seasons = manifest.get("seasons") or {}
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    data_dir.mkdir(parents=True, exist_ok=True)
    generated_from: dict[str, Any] = {}
    index_seasons: list[dict[str, Any]] = []
    total_events = 0
    total_windows = 0
    for season in parsed:
        key = season["key"]
        meta = manifest_seasons.get(key) or {}
        source = _source_from_manifest(season, meta)
        generated_from[key] = dict(source)
        family_dir = data_dir / season["family"]
        family_dir.mkdir(parents=True, exist_ok=True)
        suffix = "-r" if season["variant"] == "R" else ""
        file_name = f"{season['year']:04d}-{season['month']:02d}{suffix}.json"
        payload = _season_payload(season, generated_at, source)
        (family_dir / file_name).write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        index_seasons.append(
            {
                "family": season["family"],
                "year": season["year"],
                "month": season["month"],
                "season": month_name(season["month"]),
                "variant": season["variant"],
                "key": key,
                "available": True,
                "events_count": len(season["events"]),
                "date_windows_count": len(season["date_windows"]),
                "unparsed_count": len(season["unparsed_rows"]),
                "source": source,
                "extra_sources": _extra_sources(meta),
            }
        )
        total_events += len(season["events"])
        total_windows += len(season["date_windows"])

    cancelled: list[dict[str, Any]] = []
    for key, meta in sorted((manifest.get("cancelled") or {}).items()):
        try:
            family, year, month, _ = _split_key(key)
        except ValueError:
            continue
        cancelled.append(
            {
                "family": family,
                "year": year,
                "month": month,
                "season": month_name(month),
                "key": key,
                "reason": meta.get("reason"),
            }
        )

    unobtainable_by_key: dict[str, dict[str, Any]] = {}
    for key, meta in sorted(manifest_seasons.items()):
        if meta.get("status") != "unobtainable":
            continue
        attempts = meta.get("attempts") or []
        evidence = [
            f"{attempt.get('kind')}: {attempt.get('name')} → "
            f"{attempt.get('result') or attempt.get('status')}"
            for attempt in attempts[:12]
        ] or None
        entry = _unobtainable_entry(
            key, "穷尽候选（Wayback + 官网直连）后无可用 PDF（非 PDF 或校验失败）", evidence
        )
        if entry:
            unobtainable_by_key[entry["key"]] = entry
    for group in ("known_unobtainable", "r_unobtainable"):
        for key, meta in sorted((manifest.get(group) or {}).items()):
            entry = _unobtainable_entry(key, meta.get("reason") or "", meta.get("evidence"))
            if not entry:
                continue
            previous = unobtainable_by_key.get(entry["key"])
            if previous and not entry.get("evidence"):
                entry["evidence"] = previous.get("evidence")
            unobtainable_by_key[entry["key"]] = entry
    unobtainable = sorted(unobtainable_by_key.values(), key=lambda item: item["key"])

    available_keys = {item["key"] for item in index_seasons}
    for item in cancelled + unobtainable:
        if item["key"] in available_keys:
            raise SystemExit(
                f"清单一致性错误：{item['key']} 同时有可用快照与取消/不可得记录"
            )

    index = {
        "schema_version": SCHEMA_VERSION,
        "board": BOARD,
        "generated_at": generated_at,
        "generated_from": generated_from,
        "seasons": index_seasons,
        "cancelled": cancelled,
        "unobtainable": unobtainable,
        "totals": {
            "available_seasons": len(index_seasons),
            "events": total_events,
            "date_windows": total_windows,
            "cancelled_seasons": len(cancelled),
            "unobtainable_seasons": len(unobtainable),
        },
    }
    (data_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 Edexcel 时间表快照")
    parser.add_argument("--pdf-dir", type=Path, default=_default_pdf_dir())
    parser.add_argument("--manifest", type=Path, default=_default_manifest())
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    index = build(args.pdf_dir, args.manifest, args.data_dir, workers=max(1, args.workers))
    totals = index["totals"]
    print(
        f"OK: {totals['available_seasons']} seasons, {totals['events']} events, "
        f"{totals['date_windows']} date windows, "
        f"{totals['cancelled_seasons']} cancelled, "
        f"{totals['unobtainable_seasons']} unobtainable"
    )
    for season in index["seasons"]:
        print(f"  {season['key']}: {season['events_count']} events, {season['date_windows_count']} windows")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
