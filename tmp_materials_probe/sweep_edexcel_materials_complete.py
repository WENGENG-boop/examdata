"""capped 科目补全第二遍：Document-Type（→ Exam-Series）分片 + NOT 残差证明。

背景：servlet hitsPerPage 上限 1000，且实测忽略 query/facets/page 参数。
对第一遍 sat 在 1000 条的科目，本脚本：

  1) 探测 base 查询的 nbHits（真实总数）与首页记录；
  2) 用 `NOT category:"…Document-Type/…"` 把首页出现过的类型全部排除，
     得到「残差」；残差 <1000 时直接收下并纳入类型宇宙，直到残差为 0
     —— 此时类型宇宙被证明完整（每条记录恰属一个类型）；
  3) 对宇宙中每个类型单独查询（仍饱和则递归换 Exam-Series 维度）；
  4) 记录并集 = 全部记录（去重后条数应与 nbHits 相等，>= 即证覆盖），
     在全量并集上做材料关键词扫描与门禁判定。

全部请求走仓库 Fetcher（robots + 限速，单工作线程）。结果写
evidence/edexcel_sweep_completion.json（不覆盖第一遍数据）。
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")

from examdata.adapters.edexcel.classify import category_value, is_gated  # noqa: E402
from examdata.core.config import Settings  # noqa: E402
from examdata.core.fetch import Fetcher  # noqa: E402

EV = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
PROGRESS_FILE = EV / "edexcel_sweep_progress.json"
OUT_FILE = EV / "edexcel_sweep_completion.json"
SERVLET = "https://qualifications.pearson.com/services/pearson/algolia/GET.servlet"
HITS = 1000

KW_REGEX = re.compile(
    r"formula|formulae|statistic|periodic|booklet|insert|equation|data[\s\-_]?sheet|pre[\s\-_]?release",
    re.I,
)

DIM_TYPE = "Pearson-UK:Document-Type"
DIM_SERIES = "Pearson-UK:Exam-Series"


class NotComplete(RuntimeError):
    pass


def probe(fetcher: Fetcher, fq: str) -> tuple[list[dict], int]:
    """单次查询，返回 (records, nbHits)。不判饱和，由调用方决定分片。"""
    url = f"{SERVLET}?fq={quote(fq)}&hitsPerPage={HITS}"
    res = fetcher.get_text(url)
    if not res.ok or not res.text:
        raise NotComplete(f"HTTP {res.status}")
    data = json.loads(res.text)
    sr = data.get("searchResults") or {}
    recs = sr.get("algoliaRecords")
    if not isinstance(recs, list):
        raise NotComplete("no algoliaRecords")
    nb = sr.get("nbHits", data.get("nbHits"))
    if not isinstance(nb, int):
        nb = len(recs)
    return recs, nb


def dim_values(records: list[dict], dim: str) -> set[str]:
    vals: set[str] = set()
    for rec in records:
        v = category_value(rec.get("category") or [], dim)
        if v:
            vals.add(f"{dim}/{v}")
    return vals


def not_clause(vals: set[str]) -> str:
    return " AND ".join(f"NOT category:{json.dumps(v)}" for v in sorted(vals))


def rec_key(rec: dict) -> str:
    return str(rec.get("url") or rec.get("objectID") or "")


def collect(fetcher: Fetcher, fq: str, dims: tuple[str, ...], notes: list[str]) -> tuple[list[dict], dict]:
    """收集 fq 下全部记录；饱和时按 dims[0] 分片并证类型宇宙完整。"""
    recs0, nb0 = probe(fetcher, fq)
    if nb0 <= len(recs0):
        return recs0, {"n_total": nb0, "method": "direct"}
    if not dims:
        raise NotComplete(f"n={nb0} 且没有可用分片维度")

    dim = dims[0]
    universe = dim_values(recs0, dim)
    out: dict[str, dict] = {rec_key(r): r for r in recs0 if rec_key(r)}
    rounds = 0
    while True:
        rounds += 1
        if rounds > 6:
            notes.append("残差循环超过 6 轮，停止")
            break
        resid_fq = fq + (" AND " + not_clause(universe) if universe else "")
        recs, nb = probe(fetcher, resid_fq)
        if nb == 0:
            break  # 类型宇宙被证明完整（残差为空）
        extra = dim_values(recs, dim) - universe
        if nb >= HITS:
            if extra:
                universe |= extra
                continue
            sub, subproof = collect(fetcher, resid_fq, dims[1:], notes)
            for r in sub:
                if rec_key(r):
                    out[rec_key(r)] = r
            notes.append(f"残差饱和转下一维度: {subproof.get('method')}")
            break
        for r in recs:
            if rec_key(r):
                out[rec_key(r)] = r
        if extra:
            universe |= extra
            continue
        notes.append(f"残差 {nb} 条无新的 {dim} 值（可能缺该维度），已直接收集")
        break

    per_dim: dict[str, int] = {}
    for val in sorted(universe):
        sub, subproof = collect(fetcher, fq + f" AND category:{json.dumps(val)}", dims[1:], notes)
        per_dim[val] = subproof.get("n_total", len(sub))
        if subproof.get("method") != "direct":
            notes.append(f"{val} 饱和后经 {dims[1:] or '无维度'} 补齐")
        for r in sub:
            if rec_key(r):
                out[rec_key(r)] = r

    return list(out.values()), {
        "n_total": nb0,
        "method": f"{dim} NOT-residual + per-value",
        "universe_size": len(universe),
        "per_value_n": per_dim,
        "rounds": rounds,
    }


def material_entry(rec: dict) -> dict:
    url = str(rec.get("url") or "")
    return {
        "title": rec.get("title"),
        "url": url,
        "gated": is_gated(url),
        "size": rec.get("size"),
        "extension": rec.get("extension"),
        "doc_type": category_value(rec.get("category") or [], DIM_TYPE),
        "series": category_value(rec.get("category") or [], DIM_SERIES),
        "unit": category_value(rec.get("category") or [], "Pearson-UK:Unit"),
        "spec_code": category_value(rec.get("category") or [], "Pearson-UK:Specification-Code"),
        "matched_by": "list(complete)",
    }


def summarize(records: list[dict]) -> dict:
    types: dict[str, int] = {}
    public = gated = 0
    materials: dict[str, dict] = {}
    for rec in records:
        t = (category_value(rec.get("category") or [], DIM_TYPE) or "").strip() or "(none)"
        types[t] = types.get(t, 0) + 1
        url = str(rec.get("url") or "")
        if is_gated(url):
            gated += 1
        else:
            public += 1
        blob = " ".join(str(rec.get(k) or "") for k in ("title", "url", "description", "extension"))
        if KW_REGEX.search(blob):
            key = url or str(rec.get("objectID") or "")
            if key and key not in materials:
                materials[key] = material_entry(rec)
    return {
        "doc_types_full": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "public_count_full": public,
        "gated_count_full": gated,
        "materials_full": sorted(materials.values(), key=lambda m: str(m.get("title") or "")),
    }


def main() -> None:
    only = set(sys.argv[sys.argv.index("--slug") + 1:]) if "--slug" in sys.argv else None
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    subjects = progress["subjects"]
    targets = [
        slug
        for slug, entry in subjects.items()
        if entry.get("capped") and (only is None or slug in only)
    ]
    print(f"capped subjects: {targets}", flush=True)

    out = {"generated_at": None, "subjects": {}}
    if OUT_FILE.exists():
        out = json.loads(OUT_FILE.read_text(encoding="utf-8"))

    fetcher = Fetcher(Settings())
    t0 = time.time()
    for slug in targets:
        entry = subjects[slug]
        base_fq = " AND ".join(f"category:{json.dumps(t)}" for t in entry["picked"])
        notes: list[str] = []
        try:
            records, proof = collect(fetcher, base_fq, (DIM_TYPE, DIM_SERIES), notes)
            summary = summarize(records)
            n_collected = len(records)
            result = {
                "slug": slug,
                "status": "complete" if n_collected >= proof["n_total"] else "incomplete",
                "n_total": proof["n_total"],
                "n_collected": n_collected,
                "coverage_complete": n_collected >= proof["n_total"],
                "proof": proof,
                "notes": notes + entry.get("notes", []),
                **summary,
            }
            print(
                f"[{slug}] total={proof['n_total']} collected={n_collected}"
                f" complete={result['coverage_complete']} mat={len(summary['materials_full'])}"
                f" ({time.time()-t0:.0f}s)",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            result = {"slug": slug, "status": "failed", "error": f"{type(exc).__name__}: {exc}", "notes": notes}
            print(f"[{slug}] FAILED {exc}", flush=True)
        out["subjects"][slug] = result
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("done", flush=True)


if __name__ == "__main__":
    main()
