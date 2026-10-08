"""只读比较本地与服务索引，以及当前区域的完整目视证据；不访问上游。"""
from __future__ import annotations

import json
from collections import Counter

import batchlib as B
import cleanup_paper as C


def normalise(data: dict) -> dict:
    return {k: v for k, v in data.items() if k not in ("method", "reviewed")}


def build_manifest() -> dict:
    rows = []
    service_dir = B.SERVICE_DATA_DIR / "question_indexes" / "cie"
    for path in sorted(B.INDEXES.rglob("cie-index.json")):
        local = B.read_json(path)
        identity = local["identity"]
        key = "/".join(str(identity[k]) for k in ("subject", "year", "season", "paper"))
        qp_sha = next(d["sha256"] for d in local["documents"] if d["role"] == "qp")
        service_path = service_dir / f"{qp_sha}.json"
        row = {"key": key, **identity, "qp_sha256": qp_sha,
               "local_index": path.as_posix(), "service_index_path": service_path.as_posix(),
               "service_index_exists": service_path.is_file(),
               "questions": len(local["questions"]), "index_sha256": B.sha256_file(path),
               "documents": [d["role"] for d in local["documents"]]}
        if not service_path.is_file():
            row["comparison"] = "missing"
        else:
            try:
                service = B.read_json(service_path)
                if not isinstance(service, dict):
                    raise ValueError("service index must be an object")
                row["comparison"] = ("identical" if normalise(local) == normalise(service)
                                     else "different")
                row["service_reviewed"] = service.get("reviewed")
                local_q = {q["question"]: q for q in local["questions"]}
                service_q = {q["question"]: q for q in service["questions"]}
                row["changed_questions"] = sorted(q for q in local_q.keys() | service_q.keys()
                                                  if local_q.get(q) != service_q.get(q))
                row["changed_fields"] = dict(Counter(
                    field for q in local_q.keys() & service_q.keys()
                    for field in local_q[q].keys() | service_q[q].keys()
                    if local_q[q].get(field) != service_q[q].get(field)))
            except (ValueError, TypeError, KeyError) as exc:
                row["comparison"] = "invalid"
                row["comparison_error"] = str(exc)
        problems, stats = C.verification_state(key, [q["question"] for q in local["questions"]])
        row["verification_problems"] = problems
        row["verification"] = stats
        row["visual_gate_passed"] = not problems
        rows.append(row)
    counts = Counter(r["comparison"] for r in rows)
    return {"generated_at": B.now_iso(), "service_data_dir": B.SERVICE_DATA_DIR.as_posix(),
            "service_index_dir": service_dir.as_posix(), "count": len(rows),
            "in_service": sum(r["service_index_exists"] for r in rows),
            "not_in_service": sum(not r["service_index_exists"] for r in rows),
            "comparison_counts": dict(counts),
            "visual_gate_passed": sum(r["visual_gate_passed"] for r in rows), "entries": rows}


def main() -> int:
    manifest = build_manifest()
    B.atomic_write_json(B.BATCH_ROOT / "service-index-manifest.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != "entries"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
