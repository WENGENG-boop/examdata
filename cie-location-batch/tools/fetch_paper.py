"""通过统一 API 下载当前一卷的 QP（paired 再下 MS）。

- 只处理当前一卷，一次只保留一组原件
- 流式写 .part，校验通过才改 .pdf
- 校验：HTTP 200、%PDF- 魔数、大小上限、PyMuPDF 可开、非加密非空
- 任何 HTTP 错误先落盘 checkpoint 再停止，不自动重试
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import uuid
from pathlib import Path

import batchlib as B
import paperlib as P

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CHUNK = 1 << 20
HARD_STATUS = {403, 404, 409, 502}
# JSON 封装里 data_base64 比原始字节大约 4/3，留一倍余量再按解码后大小复核。
STREAM_LIMIT = P.MAX_PDF_BYTES * 2

# 只记录非敏感响应头子集，用于区分 uvicorn 直答与外部代理层。
_SAFE_HEADER_KEYS = ("content-type", "content-length", "server", "date",
                     "x-request-id", "connection")
_STAGE_FRAGMENTS = (
    ("catalogue", ("CIE catalogue unavailable", "Invalid or incomplete CIE catalogue")),
    ("restricted", ("restricted or redirects",)),
    ("download", ("PDF download failed", "Upstream PDF body is invalid",
                  "Upstream PDF exceeds response size limit",
                  "Upstream returned a non-PDF document",
                  "cannot be opened", "non-PDF")),
)


def _classify_stage(text) -> str:
    for stage, fragments in _STAGE_FRAGMENTS:
        if any(frag in (text or "") for frag in fragments):
            return stage
    return "unknown"


def _upstream_status(text):
    match = re.search(r"\(HTTP (\d{3})\)", text or "")
    return int(match.group(1)) if match else None


def _safe_headers(response) -> dict:
    return {key: response.headers[key] for key in _SAFE_HEADER_KEYS
            if key in response.headers}


def _extract_json_pdf(raw: bytes):
    """API 也可能返回 JSON 封装而不是裸 PDF；解出 data_base64 并核对 sha256。"""
    import base64
    import json as _json

    try:
        doc = _json.loads(raw.decode("utf-8"))
    except Exception:
        return None, "response is not JSON"
    if not isinstance(doc, dict):
        return None, "JSON envelope is not an object"
    files = doc.get("files")
    cand = None
    if isinstance(files, list) and files and isinstance(files[0], dict):
        cand = files[0]
    elif isinstance(doc.get("data_base64"), str):
        cand = doc
    if cand is None:
        return None, "JSON envelope has no files[].data_base64"
    b64 = cand.get("data_base64")
    if not isinstance(b64, str) or not b64:
        return None, "JSON envelope data_base64 missing or empty"
    try:
        data = base64.b64decode(b64, validate=False)
    except Exception as exc:
        return None, f"data_base64 not decodable: {exc}"
    expect = cand.get("sha256")
    if isinstance(expect, str) and expect:
        got = B.sha256_bytes(data)
        if got.lower() != expect.lower():
            return None, f"sha256 mismatch: envelope {expect} != decoded {got}"
    return data, None


def download_one(entry: dict, role: str, filename: str, dest: Path) -> dict:
    import httpx

    params = {
        "board": "cie", "subject": entry["subject"], "year": entry["year"],
        "season": entry["season"], "paper": entry["paper"], "mode": role,
    }
    url = f"{B.BASE_URL}/api/v1/paper"
    part = dest.with_suffix(dest.suffix + ".part")
    part.unlink(missing_ok=True)
    started = time.time()
    request_id = uuid.uuid4().hex
    # trust_env=False: loopback API must not go through the Windows system proxy (Clash 127.0.0.1:7897
    # returns empty-body 502 for loopback targets; httpx ignores ProxyOverride).
    with httpx.Client(timeout=180.0, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", url, params=params) as response:
            if response.status_code != 200:
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > 2000:
                        break
                part.unlink(missing_ok=True)
                text = body[:500].decode("utf-8", "replace")
                detail = None
                try:
                    doc = json.loads(body.decode("utf-8", "replace"))
                except Exception:
                    doc = None
                if isinstance(doc, dict) and isinstance(doc.get("detail"), str):
                    detail = doc["detail"]
                probe = detail or text
                return {"ok": False, "http_status": response.status_code,
                        "error_class": f"http_{response.status_code}",
                        "error": f"HTTP {response.status_code}",
                        "body_head": text,
                        "detail": detail,
                        "stage": _classify_stage(probe),
                        "upstream_status": _upstream_status(probe),
                        "resp_headers": _safe_headers(response),
                        "http_version": response.http_version,
                        "request_id": request_id,
                        "seconds": round(time.time() - started, 2),
                        "url": str(response.url)}
            with open(part, "wb") as fh:
                total = 0
                for chunk in response.iter_bytes(CHUNK):
                    total += len(chunk)
                    if total > STREAM_LIMIT:
                        fh.close()
                        part.unlink(missing_ok=True)
                        return {"ok": False, "http_status": 200,
                                "error_class": "size_limit",
                                "error": "response exceeds size limit",
                                "stage": "download", "upstream_status": None,
                                "request_id": request_id,
                                "seconds": round(time.time() - started, 2)}
                    fh.write(chunk)

    raw = part.read_bytes()
    if not raw.startswith(b"%PDF-"):
        data, why = _extract_json_pdf(raw)
        if data is None:
            part.unlink(missing_ok=True)
            return {"ok": False, "http_status": 200,
                    "error_class": "unusable_body",
                    "error": f"response is neither PDF nor a usable JSON envelope: {why}",
                    "stage": "download", "upstream_status": None,
                    "body_head": raw[:300].decode("utf-8", "replace"),
                    "request_id": request_id,
                    "seconds": round(time.time() - started, 2),
                    "url": url}
        part.write_bytes(data)

    try:
        info = P.validate_pdf(part)
    except Exception as exc:
        head = raw[:200].decode("utf-8", "replace")
        part.unlink(missing_ok=True)
        return {"ok": False, "http_status": 200,
                "error_class": "invalid_pdf",
                "error": f"invalid PDF: {exc}",
                "stage": "download", "upstream_status": None,
                "body_head": head,
                "request_id": request_id,
                "seconds": round(time.time() - started, 2),
                "url": url}

    dest.unlink(missing_ok=True)
    part.replace(dest)
    return {"ok": True, "filename": filename, "path": str(dest),
            "http_status": 200, "seconds": round(time.time() - started, 2),
            "request_id": request_id, "url": url, **info}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("key", help="subject/year/season/paper，如 9709/2024/Jun/11")
    parser.add_argument("--force", action="store_true",
                        help="跳过「扫描进行中」检查（互斥体仍然生效）")
    args = parser.parse_args()
    key = args.key

    checkpoint = B.read_json(B.CHECKPOINT, {}) or {}
    if checkpoint.get("needs_user_resume"):
        print("[停止] 现有断点要求用户明确允许联网续跑；本命令不发送请求。")
        return 2

    if not args.force:
        scan = B.scan_active()
        if scan.get("active"):
            print(f"[拒绝] 目录扫描进行中（{scan.get('stage')} @ {scan.get('cell')}，"
                  f"{scan.get('age_seconds')}s 前更新）；扫描与下载不能并发访问上游")
            return 3

    entry = P.load_paper(key)
    if not entry:
        print(f"papers.json 中没有 {key}")
        return 1
    if entry.get("kind") == "ms_only":
        print(f"{key} 是 ms_only，不为没有 QP 的身份下载")
        return 1

    dest_dir = P.paper_tmp(key)
    dest_dir.mkdir(parents=True, exist_ok=True)
    P.set_stage(key, "downloading", download_started_at=B.now_iso())
    B.set_checkpoint(stage="downloading", current_paper=key, last_progress_at=B.now_iso())

    results = {}
    roles = [("qp", entry["qp"][0])]
    if entry.get("kind") == "paired":
        roles.append(("ms", entry["ms"][0]))

    with B.upstream_lock():
        for role, filename in roles:
            dest = dest_dir / filename
            try:
                outcome = download_one(entry, role, filename, dest)
            except Exception as exc:  # noqa: BLE001
                import traceback as _tb

                dest.with_suffix(dest.suffix + ".part").unlink(missing_ok=True)
                name = type(exc).__name__
                net = isinstance(exc, OSError) or name in {
                    "TimeoutException", "ReadTimeout", "ConnectTimeout", "WriteTimeout",
                    "PoolTimeout", "ConnectError", "ReadError", "WriteError",
                    "RemoteProtocolError", "LocalProtocolError", "ProxyError",
                    "NetworkError", "TransportError", "UnsupportedProtocol",
                }
                outcome = {
                    "ok": False, "http_status": None,
                    "error_class": "network" if net else "unexpected",
                    "error": f"{name}: {exc}",
                    "traceback_tail": _tb.format_exc()[-1200:],
                    "url": f"{B.BASE_URL}/api/v1/paper",
                }
            results[role] = outcome
            if not outcome["ok"]:
                B.append_jsonl(B.ERRORS, {
                    "kind": "download_error", "paper": key, "role": role,
                    "detail": outcome, "at": B.now_iso()})
                P.set_stage(key, "download_failed", download_error=outcome)
                B.set_checkpoint(stage="stopped", current_paper=key,
                                 stop_reason="download_error",
                                 needs_user_resume=True,
                                 stopped_at=B.now_iso(),
                                 resume_policy="联网重试需用户明确允许续跑；已下载原件的本地阶段不受影响",
                                 stop_detail={"paper": key, "role": role,
                                              "error": outcome.get("error"),
                                              "error_class": outcome.get("error_class")},
                                 last_progress_at=B.now_iso())
                print(f"[停止] {key} {role} 下载失败: {outcome.get('error')}")
                return 2
            print(f"  {role} {filename} {outcome['bytes']}B "
                  f"{outcome['sha256'][:16]} pages={outcome['pages']} "
                  f"{outcome['seconds']}s")

    fields = {"downloaded_at": B.now_iso(), "tmp_dir": str(dest_dir)}
    fields["qp_document"] = {"role": "qp", **results["qp"]}
    if "ms" in results:
        fields["ms_document"] = {"role": "ms", **results["ms"]}
    P.set_stage(key, "downloaded", **fields)
    print(f"下载完成 {key}: {', '.join(results)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        import traceback as _tb

        _tb.print_exc()
        raise SystemExit(4)
