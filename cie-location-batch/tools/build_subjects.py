"""建立 subjects.json：第三方科目目录 ∪ 官方发现种子。

第三方目录证据来自 cie.fraft.cn 的科目下拉接口；官方种子只用来补科目代码，
不代表第三方有对应资源。
"""
from __future__ import annotations

import io
import json
import re
import sys

import batchlib as B

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def seed_codes() -> tuple[dict[str, dict], dict[str, dict]]:
    """返回 (resources 里的代码 -> 证据, failures 里的代码 -> 证据)。"""
    payload = json.loads(B.SEED_DISCOVERY.read_bytes().decode("utf-8"))
    from_resources: dict[str, dict] = {}
    for row in payload.get("resources") or []:
        code = str(row.get("subject_code") or "").strip()
        if not re.fullmatch(r"\d{4}", code):
            continue
        entry = from_resources.setdefault(code, {"slugs": [], "n": 0})
        slug = row.get("syllabus_slug")
        if slug and slug not in entry["slugs"]:
            entry["slugs"].append(slug)
        entry["n"] += 1
    from_failures: dict[str, dict] = {}
    for item in payload.get("failures") or []:
        text = str(item)
        match = re.search(r"(\d{4})", text.split(":")[0])
        if not match:
            continue
        code = match.group(1)
        slug = text.split(":")[0].strip()
        from_failures.setdefault(code, {"slugs": [], "note": text.split(":", 1)[-1].strip()})
        from_failures[code]["slugs"].append(slug)
    return from_resources, from_failures


def third_party_catalogue() -> tuple[dict[str, str], dict]:
    B.setup_repo_import()
    from examdata.core.config import Settings
    from examdata.core.fetch import Fetcher

    with Fetcher(Settings()) as fetcher:
        response = fetcher.get(B.COMBO_URL)
        if not response.ok:
            raise SystemExit(f"第三方科目目录不可用: HTTP {response.status} {response.error}")
        body = response.content or b""
        rows = json.loads(body.decode("utf-8"))
    names: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("value") or "").strip()
        if re.fullmatch(r"\d{4}", code):
            names[code] = str(row.get("text") or "").strip()
    evidence = {
        "url": B.COMBO_URL,
        "method": "GET",
        "fetched_at": B.now_iso(),
        "http_status": response.status,
        "sha256": B.sha256_bytes(body),
        "entries": len(rows),
        "codes": len(names),
    }
    return names, evidence


def main() -> int:
    B.ensure_dirs()
    third_names, third_evidence = third_party_catalogue()
    seed_res, seed_fail = seed_codes()

    codes = sorted(set(third_names) | set(seed_res) | set(seed_fail))
    subjects = []
    for code in codes:
        in_third = code in third_names
        sources = []
        if in_third:
            sources.append("third_party_catalogue")
        if code in seed_res:
            sources.append("official_seed_resources")
        if code in seed_fail:
            sources.append("official_seed_failures")
        name = None
        name_source = None
        if in_third:
            raw = third_names[code]
            name = raw.split(" - ", 1)[1].strip() if " - " in raw else raw
            name_source = "third_party_catalogue"
        elif code in seed_res and seed_res[code]["slugs"]:
            name = seed_res[code]["slugs"][0]
            name_source = "official_seed_syllabus_slug"
        elif code in seed_fail and seed_fail[code]["slugs"]:
            name = seed_fail[code]["slugs"][0]
            name_source = "official_seed_failure_slug"
        subjects.append({
            "code": code,
            "name": name,
            "name_source": name_source,
            "discovered_from": sources,
            "third_party_confirmed": in_third,
            "third_party_label": third_names.get(code),
            "official_seed_resources": seed_res.get(code, {}).get("n", 0),
            "status": "pending",
            "cells_done": 0,
            "cells_total": len(B.SEASONS) * (B.YEAR_END - B.YEAR_START + 1),
        })

    payload = {
        "generated_at": B.now_iso(),
        "source": B.SOURCE,
        "third_party_catalogue": third_evidence,
        "third_party_completeness": "proven",
        "official_seed": {
            "path": str(B.SEED_DISCOVERY),
            "resource_codes": len(seed_res),
            "failure_codes": sorted(seed_fail),
            "role": "仅补科目代码，不代表第三方有资源",
        },
        "union_codes": len(codes),
        "third_party_only": sorted(set(third_names) - set(seed_res) - set(seed_fail)),
        "official_only": sorted((set(seed_res) | set(seed_fail)) - set(third_names)),
        "year_range": [B.YEAR_START, B.YEAR_END],
        "seasons": list(B.SEASONS),
        "subjects": subjects,
    }
    B.atomic_write_json(B.SUBJECTS, payload)
    print(f"subjects.json: {len(codes)} 科目 "
          f"(第三方 {len(third_names)}, 官方种子 {len(set(seed_res) | set(seed_fail))}, "
          f"交集 {len(set(third_names) & (set(seed_res) | set(seed_fail)))})")
    print("第三方独有:", len(payload["third_party_only"]), "官方独有:", len(payload["official_only"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
