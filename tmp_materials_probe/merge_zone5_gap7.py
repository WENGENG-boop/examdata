"""把 2013–2016 七季解析结果并入 zone5 快照：新增 7 个单季 JSON 并重写 index.json。

- 7 季 payload / index 条目 / 序列化格式严格复刻 `examdata.timetable.build`；
- 既有 18 个单季 JSON 只读不写（前后逐字节比对）；
- 不可得清单与检索口径取自更新后的证据矩阵与 build.py 常量。
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "examdata" / "src"))

from examdata.timetable.build import (  # noqa: E402
    BOARD,
    DATA_DIR,
    SCHEMA_VERSION,
    UNOBTAINABLE_SEARCH_NOTE_ZH,
    ZONE,
    _split_reason,
)
from examdata.timetable.parser import parse_pdf  # noqa: E402

MATRIX = ROOT / "evidence" / "zone5_final_matrix.json"
PDF_DIR = ROOT / "downloads" / "zone5_gap7"

GAP_SEASONS = [
    ("2013-11", 2013, "Nov"),
    ("2014-06", 2014, "Jun"),
    ("2014-11", 2014, "Nov"),
    ("2015-06", 2015, "Jun"),
    ("2015-11", 2015, "Nov"),
    ("2016-06", 2016, "Jun"),
    ("2016-11", 2016, "Nov"),
]
GAP_KEYS = [key for key, _, _ in GAP_SEASONS]

EXPECTED_NEW = {
    "2013-11": (407, 0),
    "2014-06": (337, 0),
    "2014-11": (404, 0),
    "2015-06": (341, 79),
    "2015-11": (369, 37),
    "2016-06": (346, 38),
    "2016-11": (364, 33),
}
OLD_TOTALS = {"events": 5739, "date_windows": 550, "seasons": 18}
EXPECTED_TOTALS = {"available_seasons": 25, "events": 8307, "date_windows": 737, "unobtainable_seasons": 2}


def main() -> None:
    index_path = DATA_DIR / "index.json"
    old_index = json.loads(index_path.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    matrix_seasons = matrix["seasons"]

    old_files = {
        item["key"]: (DATA_DIR / f"{item['key']}.json").read_bytes()
        for item in old_index["seasons"]
        if item["key"] not in GAP_KEYS
    }
    assert len(old_files) == OLD_TOTALS["seasons"], f"既有单季快照应为 18 份，实际 {len(old_files)}"

    old_seasons = [item for item in old_index["seasons"] if item["key"] not in GAP_KEYS]
    old_generated_from = {
        key: value for key, value in old_index["generated_from"].items() if key not in GAP_KEYS
    }
    old_events = sum(item["events_count"] for item in old_seasons)
    old_windows = sum(item["date_windows_count"] for item in old_seasons)
    assert old_events == OLD_TOTALS["events"], f"既有事件总数漂移: {old_events}"
    assert old_windows == OLD_TOTALS["date_windows"], f"既有窗口总数漂移: {old_windows}"

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_seasons: list[dict] = []
    new_generated_from: dict[str, dict] = {}

    for key, year, series in GAP_SEASONS:
        meta = matrix_seasons[key]
        assert meta["file"] == f"zone5_gap7/{key}.pdf"
        season = parse_pdf(PDF_DIR / f"{key}.pdf", year, series)
        assert season["sha256"] == meta["sha256"], f"{key}: 解析 sha256 与矩阵不符"
        expected_events, expected_windows = EXPECTED_NEW[key]
        assert len(season["events"]) == expected_events, f"{key}: 事件数 {len(season['events'])} != {expected_events}"
        assert len(season["date_windows"]) == expected_windows, f"{key}: 窗口数不符"

        source = {
            "file": season["file"],
            "sha256": season["sha256"],
            "pages": season["pages"],
            "url": meta.get("source_url") or meta.get("wayback_replay_url"),
            "source_kind": meta.get("source_kind"),
        }
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
        (DATA_DIR / f"{key}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        new_generated_from[key] = dict(source)
        new_seasons.append(
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

    unobtainable = []
    for key, raw_reason in sorted((matrix.get("unobtainable") or {}).items()):
        year_text, month = key.split("-")
        reason, evidence = _split_reason(str(raw_reason))
        unobtainable.append(
            {
                "year": int(year_text),
                "season": "Jun" if month == "06" else "Nov",
                "key": key,
                "reason": reason,
                "evidence": evidence,
                "search_exhausted": True,
            }
        )

    index_seasons = new_seasons + old_seasons
    generated_from = {**new_generated_from, **old_generated_from}
    keys = [item["key"] for item in index_seasons]
    assert keys == sorted(keys), "index.seasons 未按考季键排序"

    totals = {
        "available_seasons": len(index_seasons),
        "events": sum(item["events_count"] for item in index_seasons),
        "date_windows": sum(item["date_windows_count"] for item in index_seasons),
        "unobtainable_seasons": len(unobtainable),
    }
    assert totals == EXPECTED_TOTALS, f"汇总不符: {totals}"

    index = {
        "schema_version": SCHEMA_VERSION,
        "zone": ZONE,
        "board": BOARD,
        "generated_at": generated_at,
        "generated_from": generated_from,
        "seasons": index_seasons,
        "unobtainable": unobtainable,
        "unobtainable_search_note_zh": UNOBTAINABLE_SEARCH_NOTE_ZH,
        "totals": totals,
    }
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    reloaded = json.loads(index_path.read_text(encoding="utf-8"))
    assert reloaded["totals"] == EXPECTED_TOTALS
    assert len(reloaded["seasons"]) == 25
    assert [item["key"] for item in reloaded["unobtainable"]] == ["2019-06", "2020-11"]
    for key, before in old_files.items():
        after = (DATA_DIR / f"{key}.json").read_bytes()
        assert after == before, f"{key}.json 被意外改写"
    for key in GAP_KEYS:
        assert (DATA_DIR / f"{key}.json").is_file()

    print("OK: 7 seasons merged; index totals:", json.dumps(totals, ensure_ascii=False))
    for item in new_seasons:
        print(
            f"  + {item['key']}: {item['events_count']} events, "
            f"{item['date_windows_count']} windows, unparsed={item['unparsed_count']}"
        )
    print("unobtainable reasons:")
    for item in reloaded["unobtainable"]:
        print(f"  - {item['key']}: {item['reason']}")


if __name__ == "__main__":
    main()
