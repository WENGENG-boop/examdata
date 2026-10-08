"""capped 三科终稿：递归分区枚举，替代"残差验证"（对 nbHits 钳位免疫）。

背景：verify_capped_residual.py 的残差法不可靠——首查 1000 被截断且 nbHits 被
钳到 1000，残差只排除"已见类型"，未覆盖同类型 >1000 的部分；geography-2015 还因
NOT 子句过长 HTTP 414（见 evidence/edexcel_capped_verify.json）。

方法：对基查询递归分区——
  enum(fq)：hitsPerPage=1000；
    len(recs)<1000 → 叶子完整，收下；
    len==1000 → 取未用过的、能真正切分的最高频 category 串 X
      （Document-Type → Exam-Series → 任意），递归
      enum(fq AND category:"X") 与 enum(fq AND NOT category:"X")；
    无可用串 / 超深度 / 超 URL 长度 / 预算耗尽 → unresolved（如实记，不谎称完整）。
记录按 url/objectID 去重汇总；每个叶子"完整返回"即证该子集覆盖，不依赖 nbHits。

基查询（决策出处：失败页记录与第一遍 sweep picked；geography-2015 页 facet 残缺
只有 Accreditation+Family，al15-geography 查询 0 条，改用兄弟页 geography-2016 的
spec al16-geography（同 9GE0，300 条未饱和））：
  edexcel-a-level-geography-2015 → .../A-Level/2016/al16-geography
  history-2015                   → .../A-Level/2015/al15-history
  mathematics-2018               → .../International-Advanced-Level/2018/ial18-mathematics

护栏：查询预算 ≤300、深度 ≤35、单请求 URL ≤1900 字符（防 414）。输出
evidence/edexcel_capped_final.json。全部请求走仓库 Fetcher（单线程）。
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")

from examdata.adapters.edexcel.classify import category_value, is_gated  # noqa: E402
from examdata.core.config import Settings  # noqa: E402
from examdata.core.fetch import Fetcher  # noqa: E402

EV = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
OUT = EV / "edexcel_capped_final.json"
SERVLET = "https://qualifications.pearson.com/services/pearson/algolia/GET.servlet"
HITS = 1000
MAX_QUERIES = 300
MAX_DEPTH = 35
MAX_URL = 1900

DOC_TYPE_PREFIX = "Pearson-UK:Document-Type/"
SERIES_PREFIX = "Pearson-UK:Exam-Series/"

KW_REGEX = re.compile(
    r"formula|formulae|statistic|periodic|booklet|insert|equation|data[\s\-_]?sheet|pre[\s\-_]?release",
    re.I,
)

SUBJECTS = [
    {
        "key": "edexcel-a-level-geography-2015",
        "slug": "edexcel-a-level-geography-2015",
        "family": "A-Level",
        "base_tag": "Pearson-UK:Specification-Code/A-Level/2016/al16-geography",
        "base_note": (
            "页 facet 残缺（仅 Accreditation-From-date + Family）；al15-geography 查询 0 条；"
            "改用兄弟页 geography-2016 的 spec al16-geography（同 9GE0）"
        ),
    },
    {
        "key": "history-2015",
        "slug": "history-2015",
        "family": "A-Level",
        "base_tag": "Pearson-UK:Specification-Code/A-Level/2015/al15-history",
        "base_note": "第一遍 picked 中最具体 spec（同页 facet）",
    },
    {
        "key": "mathematics-2018",
        "slug": "mathematics-2018",
        "family": "International-Advanced-Level",
        "base_tag": (
            "Pearson-UK:Specification-Code/International-Advanced-Level/2018/ial18-mathematics"
        ),
        "base_note": "第一遍 picked 中最具体 spec（同页 facet）",
    },
]


def make_url(fq: str) -> str:
    return f"{SERVLET}?fq={quote(fq)}&hitsPerPage={HITS}"


def probe(fetcher: Fetcher, fq: str) -> tuple[list[dict], int, int, bool]:
    """返回 (records, http, nbHits, ok)。ok=False 表示传输/形状失败，不自动重试。"""
    res = fetcher.get_text(make_url(fq))
    if not res.ok or res.status == 206 or not isinstance(res.text, str) or not res.text:
        return [], res.status, -1, False
    try:
        data = json.loads(res.text)
    except ValueError:
        return [], res.status, -1, False
    if not isinstance(data, dict) or not isinstance(data.get("searchResults"), dict):
        return [], res.status, -1, False
    sr = data["searchResults"]
    recs = sr.get("algoliaRecords")
    if not isinstance(recs, list):
        return [], res.status, -1, False
    nb = sr.get("nbHits")
    if isinstance(nb, bool) or not isinstance(nb, int):
        nb = -1
    return recs, res.status, nb, True


def dedupe_key(rec: dict) -> str:
    return str(rec.get("url") or "") or str(rec.get("objectID") or "")


def pick_split(recs: list[dict], used: frozenset[str]) -> str | None:
    """选一个能真正切分当前集合的 category 串；优先 Document-Type、其次 Exam-Series。

    必须 0 < count < len(recs)（全量覆盖的分类切不开，会死循环）。
    """
    counts_t: Counter[str] = Counter()
    counts_s: Counter[str] = Counter()
    counts_a: Counter[str] = Counter()
    for rec in recs:
        for c in rec.get("category") or []:
            if not isinstance(c, str) or c in used:
                continue
            counts_a[c] += 1
            if c.startswith(DOC_TYPE_PREFIX):
                counts_t[c] += 1
            elif c.startswith(SERIES_PREFIX):
                counts_s[c] += 1
    n = len(recs)
    for counter in (counts_t, counts_s, counts_a):
        cands = [(cnt, c) for c, cnt in counter.items() if 0 < cnt < n]
        if cands:
            cands.sort(key=lambda kv: (-kv[0], kv[1]))
            return cands[0][1]
    return None


def summarize(records: list[dict]) -> dict:
    types: dict[str, int] = {}
    public = gated = 0
    materials: dict[str, dict] = {}
    for rec in records:
        t = (category_value(rec.get("category") or [], "Pearson-UK:Document-Type") or "").strip() or "(none)"
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
                materials[key] = {
                    "title": rec.get("title"),
                    "url": url,
                    "gated": is_gated(url),
                    "size": rec.get("size"),
                    "extension": rec.get("extension"),
                    "doc_type": t,
                    "series": category_value(rec.get("category") or [], "Pearson-UK:Exam-Series"),
                    "unit": category_value(rec.get("category") or [], "Pearson-UK:Unit"),
                    "spec_code": category_value(rec.get("category") or [], "Pearson-UK:Specification-Code"),
                    "matched_by": "capped_final",
                }
    return {
        "doc_types": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "public_count": public,
        "gated_count": gated,
        "materials": sorted(materials.values(), key=lambda m: str(m.get("title") or "")),
    }


def subject_keyword(slug: str) -> str:
    k = re.sub(r"-\d{4}(-modular)?$", "", slug, flags=re.I)
    k = re.sub(r"^international-gcse-", "", k, flags=re.I)
    return k.replace("-", " ")


def run_subject(fetcher: Fetcher, subj: dict, budget: dict) -> dict:
    base_fq = f"category:{json.dumps(subj['base_tag'])}"
    state: dict = {
        "queries": 0,
        "leaves": [],
        "unresolved": [],
        "log": [],
        "records": {},
    }

    def enum(fq: str, depth: int, used: frozenset[str]) -> None:
        url = make_url(fq)
        if len(url) > MAX_URL:
            state["unresolved"].append({"fq": fq, "reason": "url_limit", "url_len": len(url), "depth": depth})
            return
        if depth > MAX_DEPTH:
            state["unresolved"].append({"fq": fq, "reason": "depth_limit", "depth": depth})
            return
        if budget["used"] >= MAX_QUERIES:
            state["unresolved"].append({"fq": fq, "reason": "query_budget", "depth": depth})
            return
        budget["used"] += 1
        state["queries"] += 1
        recs, status, nb, ok = probe(fetcher, fq)
        state["log"].append({"fq": fq, "depth": depth, "http": status, "n": len(recs), "nbHits": nb})
        if not ok:
            # 传输/形状错误：不自动重试，如实记缺口
            state["unresolved"].append({"fq": fq, "reason": f"probe_failed_http_{status}", "depth": depth})
            return
        if len(recs) < HITS:
            state["leaves"].append({"fq": fq, "n": len(recs), "depth": depth, "nbHits": nb})
            for r in recs:
                key = dedupe_key(r)
                if key:
                    state["records"][key] = r
            return
        x = pick_split(recs, used)
        if not x:
            state["unresolved"].append({"fq": fq, "reason": "no_split_key", "n": len(recs), "depth": depth})
            return
        enum(fq + f" AND category:{json.dumps(x)}", depth + 1, used | {x})
        enum(fq + f" AND NOT category:{json.dumps(x)}", depth + 1, used | {x})

    enum(base_fq, 0, frozenset())
    records = list(state["records"].values())
    info: dict = {
        "slug": subj["slug"],
        "family": subj["family"],
        "base_tag": subj["base_tag"],
        "base_fq": base_fq,
        "base_note": subj["base_note"],
        "queries": state["queries"],
        "leaves": state["leaves"],
        "unresolved": state["unresolved"],
        "queries_log": state["log"],
        "n_records": len(records),
        "complete": not state["unresolved"],
    }
    info.update(summarize(records))
    kw = subject_keyword(subj["slug"])
    toks = [t for t in kw.split() if len(t) >= 4]
    if toks:
        info["subject_tokens"] = toks
        info["subject_match_n"] = sum(
            1
            for r in records
            if all(t in (str(r.get("title") or "") + " " + str(r.get("url") or "")).lower() for t in toks)
        )
    return info


def main() -> None:
    fetcher = Fetcher(Settings())
    t0 = time.time()
    out: dict = {
        "generated_at": None,
        "method": "recursive partition enumeration; leaf complete when <1000 returned",
        "budget": {"max_queries": MAX_QUERIES, "used": 0, "max_depth": MAX_DEPTH, "max_url": MAX_URL},
        "subjects": {},
    }

    def flush() -> None:
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        out["budget"]["used"] = budget["used"]
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    budget = {"used": 0}
    for i, subj in enumerate(SUBJECTS, 1):
        info = run_subject(fetcher, subj, budget)
        out["subjects"][subj["key"]] = info
        print(
            f"[{i}/3] {subj['key']}: n={info['n_records']} queries={info['queries']}"
            f" leaves={len(info['leaves'])} unresolved={len(info['unresolved'])}"
            f" complete={info['complete']} ({time.time()-t0:.0f}s)",
            flush=True,
        )
        flush()

    fetcher.close()
    print("done", flush=True)


if __name__ == "__main__":
    main()
