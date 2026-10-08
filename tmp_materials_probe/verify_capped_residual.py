"""对 capped 3 科做真正的不依赖 nbHits 的完整性证明。

背景：第一遍 sweep 用 len(records)>=1000 判 capped；补全脚本 collect() 在
nb0<=len 时直判 complete——但 nbHits 可能被 servlet 钳到 1000，无法区分
「真 1000 条」与「超 1000 条被截」。

本脚本用 NOT-Document-Type 残差收敛做证明：
  - 把首批 1000 条中出现的全部 Document-Type 用 NOT 排除，重查；
  - 残差 <1000（完整返回）或 0 → 关闭，并证明采集覆盖了 base 全集；
  - 残差饱和且出现新类型 → 并入宇宙继续；饱和且无新类型 → 换 Exam-Series 维度分片。
每个请求走仓库 Fetcher（robots+限速、单线程）。结果写 evidence/edexcel_capped_verify.json。
"""

from __future__ import annotations

import json
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
OUT = EV / "edexcel_capped_verify.json"
SERVLET = "https://qualifications.pearson.com/services/pearson/algolia/GET.servlet"
HITS = 1000
DIM_TYPE = "Pearson-UK:Document-Type"
DIM_SERIES = "Pearson-UK:Exam-Series"


def probe(fetcher: Fetcher, fq: str) -> tuple[list[dict], int]:
    url = f"{SERVLET}?fq={quote(fq)}&hitsPerPage={HITS}"
    res = fetcher.get_text(url)
    if not res.ok or not res.text:
        raise RuntimeError(f"HTTP {res.status}")
    data = json.loads(res.text)
    sr = data.get("searchResults") or {}
    recs = sr.get("algoliaRecords")
    if not isinstance(recs, list):
        raise RuntimeError("no algoliaRecords")
    nb = sr.get("nbHits", data.get("nbHits"))
    if not isinstance(nb, int):
        nb = len(recs)
    return recs, nb


def key(rec: dict) -> str:
    return str(rec.get("url") or rec.get("objectID") or "")


def dim_vals(recs: list[dict], dim: str) -> set[str]:
    out: set[str] = set()
    for r in recs:
        v = category_value(r.get("category") or [], dim)
        if v:
            out.add(f"{dim}/{v}")
    return out


def not_clause(vals: set[str]) -> str:
    return " AND ".join(f"NOT category:{json.dumps(v)}" for v in sorted(vals))


def summarize(records: list[dict]) -> dict:
    types: dict[str, int] = {}
    public = gated = 0
    for r in records:
        t = (category_value(r.get("category") or [], DIM_TYPE) or "").strip() or "(none)"
        types[t] = types.get(t, 0) + 1
        if is_gated(str(r.get("url") or "")):
            gated += 1
        else:
            public += 1
    return {
        "doc_types_full": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "public_count_full": public,
        "gated_count_full": gated,
    }


def collect(fetcher: Fetcher, base_fq: str, log: list[str]) -> tuple[dict[str, dict], dict]:
    recs0, nb0 = probe(fetcher, base_fq)
    out: dict[str, dict] = {key(r): r for r in recs0 if key(r)}
    proof: dict = {"nb0": nb0, "first_len": len(recs0)}
    log.append(f"base nbHits={nb0} len={len(recs0)}")
    if nb0 < HITS and nb0 <= len(recs0):
        proof["method"] = "direct (<cap)"
        return out, proof
    universe = dim_vals(recs0, DIM_TYPE)
    rounds = 0
    closed = False
    while rounds < 8:
        rounds += 1
        resid_fq = base_fq + (" AND " + not_clause(universe) if universe else "")
        recs, nb = probe(fetcher, resid_fq)
        log.append(f"resid r{rounds}: nbHits={nb} len={len(recs)} types={len(universe)}")
        if nb == 0:
            closed = True
            proof["residual_closed"] = "zero"
            break
        if nb <= len(recs) and len(recs) < HITS:
            for r in recs:
                if key(r):
                    out[key(r)] = r
            closed = True
            proof["residual_closed"] = "fully-returned"
            break
        extra = dim_vals(recs, DIM_TYPE) - universe
        if extra:
            universe |= extra
            continue
        # 残差饱和且无新 Document-Type：按 Exam-Series 分片（对残差本身）
        series = dim_vals(recs, DIM_SERIES)
        proof["series_split"] = {"series_n": len(series)}
        for sv in sorted(series):
            sub_fq = resid_fq + f" AND category:{json.dumps(sv)}"
            srecs, snb = probe(fetcher, sub_fq)
            log.append(f"  series {sv}: nbHits={snb} len={len(srecs)}")
            for r in srecs:
                if key(r):
                    out[key(r)] = r
        proof["residual_closed"] = "series-split(no-new-type)"
        closed = True
        break
    proof["method"] = "NOT-residual"
    proof["rounds"] = rounds
    proof["closed"] = closed
    proof["collected"] = len(out)
    return out, proof


def main() -> None:
    progress = json.loads((EV / "edexcel_sweep_progress.json").read_text(encoding="utf-8"))["subjects"]
    targets = [s for s, e in progress.items() if e.get("capped")]
    out: dict = {"generated_at": None, "subjects": {}}
    fetcher = Fetcher(Settings())
    t0 = time.time()
    for slug in targets:
        entry = progress[slug]
        base_fq = " AND ".join(f"category:{json.dumps(t)}" for t in entry["picked"])
        log: list[str] = []
        try:
            records, proof = collect(fetcher, base_fq, log)
            summary = summarize(records.values() if isinstance(records, dict) else records)
            result = {
                "slug": slug,
                "n_collected": len(records),
                "proof": proof,
                "log": log,
                **summary,
            }
            print(f"[{slug}] collected={len(records)} proof={proof.get('residual_closed')} ({time.time()-t0:.0f}s)", flush=True)
        except Exception as exc:  # noqa: BLE001
            result = {"slug": slug, "status": "failed", "error": f"{type(exc).__name__}: {exc}", "log": log}
            print(f"[{slug}] FAILED {exc}", flush=True)
        out["subjects"][slug] = result
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("done", flush=True)


if __name__ == "__main__":
    main()
