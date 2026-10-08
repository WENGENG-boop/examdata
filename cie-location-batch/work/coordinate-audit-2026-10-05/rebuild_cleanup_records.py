"""重建 cleanup-records.json：读取当前 cleanup.jsonl + summary.cleanup + 索引 sha。

只读本地文件，不联网。本轮 4 卷（3x 8386 + 0472/2026/Jun/41）单独列出。
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).parent
BATCH = HERE.parents[1]
OUT = HERE / "deliverables"

TZ = timezone(timedelta(hours=8))
now = datetime.now(TZ).isoformat(timespec="seconds")

THIS_ROUND = [
    "8386/2025/Jun/11",
    "8386/2026/Jun/12",
    "8386/2026/Jun/13",
    "0472/2026/Jun/41",
    "0509/2026/Jun/11",
    "0580/2024/Jun/11",
    "9715/2023/Nov/21",
]


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


rows = read_jsonl(BATCH / "cleanup.jsonl")
summary = json.loads((BATCH / "summary.json").read_text(encoding="utf-8"))
papers = json.loads((BATCH / "papers.json").read_text(encoding="utf-8"))


def index_path(key):
    subj, year, season, paper = key.split("/")
    return BATCH / "indexes" / subj / f"{year}-{season}-{paper}" / "cie-index.json"


this_round = []
for key in THIS_ROUND:
    recs = [r for r in rows if r.get("key") == key and r.get("stage") == "cleaned"]
    last = recs[-1] if recs else None
    ip = index_path(key)
    entry = papers.get(key) or {}
    slug = key.replace("/", "-")
    rb = HERE / "api-readback" / slug / "report.json"
    readback = None
    if rb.is_file():
        r = json.loads(rb.read_text(encoding="utf-8"))
        readback = {
            "report": str(rb),
            "index_http": r["checks"]["index_http"],
            "index_compare_errors": r["checks"].get("index_compare_errors"),
            "samples": [{"question": f["question"], "mode": f["mode"], "http": f["http"],
                         "bytes": f["bytes"]} for f in r.get("fetched", [])],
        }
    this_round.append({
        "key": key,
        "cleaned_at": last.get("at") if last else None,
        "deleted_files": last.get("deleted") if last else None,
        "freed_bytes": last.get("freed_bytes") if last else None,
        "refused": last.get("refused") if last else None,
        "index_path": str(ip),
        "index_sha256": sha256(ip) if ip.is_file() else None,
        "index_sha256_at_import": entry.get("index_sha256"),
        "question_count": entry.get("question_count"),
        "import_succeeded": entry.get("import_succeeded"),
        "readback_verified": entry.get("readback_verified"),
        "stage_now": entry.get("stage"),
        "readback": readback,
        "source": "本次实测",
    })

doc = {
    "generated_at": now,
    "log_path": str(BATCH / "cleanup.jsonl"),
    "log_records": len(rows),
    "by_stage": dict(Counter(r.get("stage") for r in rows)),
    "cleaned_records": sum(1 for r in rows if r.get("stage") == "cleaned"),
    "cleaned_unique_keys": len({r["key"] for r in rows
                                if r.get("stage") == "cleaned" and r.get("key")}),
    "cleanup_pending_unique_keys": len({r["key"] for r in rows
                                        if r.get("stage") == "cleanup_pending" and r.get("key")}),
    "summary_cleanup": summary.get("cleanup"),
    "summary_cleanup_note":
        "summary.cleanup 为历史累计快照（cleaned_papers=63 是曾经清理过的唯一卷数，"
        "含已 refetch 回退为 fetched 的卷）；当前阶段分布见 current_stage_counts。",
    "current_stage_counts": dict(Counter(v.get("stage") for v in papers.values())),
    "this_round_cleaned": this_round,
    "this_round_totals": {
        "papers": len(this_round),
        "deleted_files": sum(x["deleted_files"] or 0 for x in this_round),
        "freed_bytes": sum(x["freed_bytes"] or 0 for x in this_round),
        "source": "本次实测",
    },
    "deleted_originals_retained_policy":
        "仅按 cleanup_paper.py 门槛与白名单清理；未验收原件不删，不删其他工作流文件。",
    "source": "本次实测（读取 cleanup.jsonl + summary.cleanup + 当前索引 sha256）",
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "cleanup-records.json").write_text(
    json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps({
    "log_records": doc["log_records"],
    "cleaned_records": doc["cleaned_records"],
    "cleaned_unique_keys": doc["cleaned_unique_keys"],
    "this_round": doc["this_round_totals"],
}, ensure_ascii=False, indent=2))
