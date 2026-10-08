"""导入前置条件核查：确认 BASE_URL 服务在运行、其数据目录 == SERVICE_DATA_DIR。

只做本地探测（localhost:8000 + 本地文件系统），不访问上游。
证据：
  1. 服务 /health 可用；
  2. SERVICE_DATA_DIR/question_indexes/cie 下全部 N 份索引，逐个经
     GET /api/v1/indexes/cie/<qp_sha256> 取回并与磁盘文件（忽略 method/reviewed）比对；
  3. 不存在的 sha 返回 404；
  4. 其余候选数据目录（examdata/.data、examdata/.pytest_cache/cie-pilot-offline-check）
     的 cie 索引目录内容与磁盘比对结果，用于排除「服务读的是别的目录」。
输出：deliverables/service-precondition.json
"""
from __future__ import annotations

import glob
import json
import os
import urllib.error
import urllib.request

ROOT = r"C:/Users/weo/Desktop/api"
OUT = os.path.join(ROOT, "cie-location-batch/work/coordinate-audit-2026-10-05/deliverables")
SERVICE_DATA_DIR = os.path.join(ROOT, "examdata/.pytest_cache/callable-api")
BASE_URL = "http://127.0.0.1:8000"
OTHER_CANDIDATES = {
    "examdata/.data": os.path.join(ROOT, "examdata/.data"),
    "examdata/.pytest_cache/cie-pilot-offline-check":
        os.path.join(ROOT, "examdata/.pytest_cache/cie-pilot-offline-check"),
}
MISSING_SHA = "0" * 64


def norm(d):
    return {k: v for k, v in d.items() if k not in ("method", "reviewed")}


def get(url, timeout=15):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8")


def probe() -> dict:
    result = {
        "base_url": BASE_URL,
        "service_data_dir_expected": SERVICE_DATA_DIR.replace("\\", "/"),
        "probe_kind": "local_only",
        "upstream_requests_made": 0,
    }

    try:
        status, body = get(f"{BASE_URL}/health")
        result["health_http_status"] = status
        result["health_body"] = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        result["health_http_status"] = None
        result["health_error"] = repr(exc)
        result["service_reachable"] = False
        result["conclusion"] = "service_unreachable"
        return result

    result["service_reachable"] = True

    cie_dir = os.path.join(SERVICE_DATA_DIR, "question_indexes", "cie")
    files = sorted(glob.glob(os.path.join(cie_dir, "*.json")))
    equal, different, errors = 0, [], []
    for path in files:
        sha = os.path.basename(path)[:-5]
        try:
            status, body = get(f"{BASE_URL}/api/v1/indexes/cie/{sha}")
            served = json.loads(body)
            on_disk = json.load(open(path, encoding="utf-8"))
            if norm(served) == norm(on_disk):
                equal += 1
            else:
                different.append(sha)
        except Exception as exc:  # noqa: BLE001
            errors.append({"sha256": sha, "error": repr(exc)})

    result["service_data_dir_index_count"] = len(files)
    result["served_matches_disk"] = equal
    result["served_differs_from_disk"] = different
    result["served_errors"] = errors

    try:
        status, _ = get(f"{BASE_URL}/api/v1/indexes/cie/{MISSING_SHA}")
        result["missing_sha_http_status"] = status
    except urllib.error.HTTPError as exc:
        result["missing_sha_http_status"] = exc.code

    # 判别器：服务实际返回了 SERVICE_DATA_DIR 下的全部 sha；若某候选目录不含这些
    # sha 中的任意一个（尤其 0472 的 qp_sha），则服务不可能读的是该目录。
    served_shas = {os.path.basename(p)[:-5] for p in files}
    candidates = {}
    for name, root in OTHER_CANDIDATES.items():
        other = os.path.join(root, "question_indexes", "cie")
        shas = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(other, "*.json"))}
        candidates[name] = {
            "index_dir": other.replace("\\", "/"),
            "index_count": len(shas),
            "covers_all_served_shas": served_shas <= shas,
            "served_shas_missing_here": len(served_shas - shas),
        }
    result["other_candidate_data_dirs"] = candidates

    confirmed = (
        result["service_reachable"]
        and result["served_matches_disk"] == len(files)
        and len(files) > 0
        and not errors
        and result.get("missing_sha_http_status") == 404
        and all(not v["covers_all_served_shas"] for v in candidates.values())
    )
    result["service_data_dir_confirmed"] = confirmed
    result["conclusion"] = ("import_precondition_satisfied" if confirmed
                            else "import_precondition_not_confirmed")
    return result


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    result = probe()
    path = os.path.join(OUT, "service-precondition.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("health_body", "other_candidate_data_dirs")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
