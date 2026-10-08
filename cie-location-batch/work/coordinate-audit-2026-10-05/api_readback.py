"""F 阶段：服务实际回读（抽样声明制）。

对每个 key：
  1. GET /api/v1/indexes/cie/<qp_sha>          → 全量索引 JSON，比对本地索引
                                                （题数/identity/documents/关键字段）
  2. 对 --sample 声明的 (question, mode) 列表调用
     GET /api/v1/indexes/cie/<qp_sha>/question → 实际裁剪 PNG（binary）+ json 元数据
     保存到 api-readback/<subject>-<stem>/ 供浏览器目视

样品的裁剪图必须逐张目视（由我方执行）；本脚本只负责取件、落盘、比对与报告。
输出：api-readback/<subject>-<stem>/report.json 与 manifest 行。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import batchlib as B  # noqa: E402
import cleanup_paper as C  # noqa: E402
import import_index as II  # noqa: E402

SERVICE_BASE = "http://127.0.0.1:8000"


def http_get(url: str, timeout: float = 60.0) -> tuple[int, bytes, dict]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, headers={"Accept": "*/*"})
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def main() -> int:
    parser = argparse.ArgumentParser(description="服务端索引与裁剪回读（抽样）")
    parser.add_argument("key", help="subject/year/season/paper")
    parser.add_argument("--sample", required=True,
                        help='如 "1:both,3:ms,7:qp"（question:mode，逗号分隔）')
    args = parser.parse_args()
    key = args.key
    subject, year, season, paper = key.split("/")

    index_file = II.index_path(key)
    if not index_file.is_file():
        print(f"本地索引不存在：{index_file}")
        return 2
    local = json.loads(index_file.read_bytes().decode("utf-8"))
    local_sha = B.sha256_file(index_file)
    qp_sha = II.document_sha(local, "qp")
    if not qp_sha:
        print("本地索引没有 qp sha256")
        return 2
    current_sha = C.current_index_sha256(key)
    if current_sha != local_sha:
        print(f"索引 sha 变动：{local_sha} != {current_sha}")
        return 2

    outdir = ROOT / "api-readback" / f"{subject}-{year}-{season}-{paper}"
    outdir.mkdir(parents=True, exist_ok=True)
    report: dict = {"key": key, "index_sha256": local_sha, "qp_sha256": qp_sha,
                    "checks": {}, "fetched": [], "errors": [], "at": B.now_iso()}

    # 1) 全量索引 JSON
    status, body, _ = http_get(f"{SERVICE_BASE}/api/v1/indexes/cie/{qp_sha}")
    report["checks"]["index_http"] = status
    if status != 200:
        report["errors"].append(f"索引回读 HTTP {status}: {body[:200]!r}")
        (outdir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
        return 3
    remote = json.loads(body.decode("utf-8"))
    (outdir / "service-index.json").write_bytes(body)
    cmp_errors, cmp_warnings = II.compare_index(local, remote)
    report["checks"]["index_compare_errors"] = cmp_errors
    report["checks"]["index_compare_warnings"] = cmp_warnings
    report["checks"]["remote_questions"] = len(remote.get("questions") or [])
    report["checks"]["local_questions"] = len(local.get("questions") or [])

    # 2) 抽样裁剪
    sample = []
    for piece in args.sample.split(","):
        piece = piece.strip()
        if not piece:
            continue
        q, _, mode = piece.partition(":")
        sample.append((q, mode or "both"))
    report["sample_declared"] = [{"question": q, "mode": m} for q, m in sample]
    for qid, mode in sample:
        url = (f"{SERVICE_BASE}/api/v1/indexes/cie/{qp_sha}/question"
               f"?question={urllib.request.quote(qid)}&mode={mode}")
        status, body, headers = http_get(url)
        ctype = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
        label = f"q{qid.replace('(', '-').replace(')', '')}-{mode}"
        entry = {"question": qid, "mode": mode, "http": status, "bytes": len(body),
                 "content_type": ctype, "files": []}
        # 服务对单区域返回 image/*，对多区域返回 zip（成员为各区域 PNG）
        is_zip = body[:2] == b"PK" or "zip" in ctype.lower()
        if status == 200 and (ctype.startswith("image/") or is_zip):
            entry["sha256"] = B.sha256_bytes(body)
            if is_zip:
                dest = outdir / label
                dest.mkdir(exist_ok=True)
                with zipfile.ZipFile(io.BytesIO(body)) as archive:
                    for member in archive.infolist():
                        if member.is_dir():
                            continue
                        data = archive.read(member)
                        safe = Path(member.filename).name
                        (dest / safe).write_bytes(data)
                        entry["files"].append({"name": f"{label}/{safe}",
                                               "bytes": len(data),
                                               "sha256": B.sha256_bytes(data)})
                entry["file"] = dest.name
            else:
                target = outdir / f"{label}.png"
                target.write_bytes(body)
                entry["file"] = target.name
                entry["files"].append({"name": target.name, "bytes": len(body),
                                       "sha256": B.sha256_bytes(body)})
        else:
            entry["error"] = body[:300].decode("utf-8", "replace")
            report["errors"].append(f"{qid}/{mode}: HTTP {status} {entry['error'][:120]}")
            target = outdir / f"{label}-error.bin"
            target.write_bytes(body)
            entry["file"] = target.name
        # 附带 JSON 元数据（来源页码/bbox/uncertain），失败不致命
        jurl = url + "&format=json"
        jstatus, jbody, _ = http_get(jurl)
        entry["meta_http"] = jstatus
        if jstatus == 200:
            meta = json.loads(jbody.decode("utf-8"))
            entry["meta"] = {k: meta.get(k) for k in
                             ("question", "index_sha256", "source_documents", "uncertain")}
            files = meta.get("files") or []
            entry["regions"] = [{"page": f.get("page"), "bbox": f.get("bbox"),
                                 "role": f.get("role"), "name": f.get("name")}
                                for f in files if isinstance(f, dict)]
            (outdir / f"{label}-meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        report["fetched"].append(entry)
        print(f"  {qid}/{mode}: HTTP {status} {entry['bytes']}B {entry.get('file')}")

    (outdir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print(f"报告：{outdir / 'report.json'}")
    if report["errors"] or cmp_errors:
        print(f"存在问题：{len(report['errors'])} 个取件错误，{len(cmp_errors)} 个索引比对错误")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
