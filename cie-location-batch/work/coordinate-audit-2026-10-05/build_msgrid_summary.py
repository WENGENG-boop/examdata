"""汇总 ms-grid-fix-*.json 为 deliverables/ms-grid-fix-summary.json。"""
import glob
import json
import os
import sys
import time

sys.path.insert(0, r"C:/Users/weo/Desktop/api/cie-location-batch/tools")
import analyze_ms_grid as A  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    logs = sorted(glob.glob(os.path.join(HERE, "deliverables", "ms-grid-fix-*.json")))
    by_key = {}
    for p in logs:
        j = json.load(open(p, encoding="utf-8"))
        if not j.get("index_sha256_after"):
            continue
        by_key.setdefault(j["key"], []).append((p, j))
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "papers": []}
    for k in sorted(by_key):
        p, j = sorted(by_key[k])[-1]
        idx = A.index_path(k)
        cur = A.sha256_file(idx)
        d = json.load(open(idx, encoding="utf-8"))
        out["papers"].append({
            "key": k,
            "ops": j["ops"],
            "changed_questions": len(j["changes"]),
            "sha_after_log": j["index_sha256_after"],
            "sha_current": cur,
            "consistent": cur == j["index_sha256_after"],
            "ms_regions_now": sum(len(q.get("ms") or []) for q in d["questions"]),
            "questions": len(d["questions"]),
            "log": p.replace("\\", "/"),
            "backup": j.get("backup"),
        })
    out["n_papers"] = len(out["papers"])
    outp = os.path.join(HERE, "deliverables", "ms-grid-fix-summary.json")
    json.dump(out, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("papers", out["n_papers"])
    for r in out["papers"]:
        print(" ", r["key"], r["ops"], "q", r["questions"],
              "ms_now", r["ms_regions_now"], "consistent", r["consistent"])
    print("->", outp.replace("\\", "/"))


if __name__ == "__main__":
    main()
