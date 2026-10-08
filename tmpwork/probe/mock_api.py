"""可配置的假 API：验证 smoke_public_api.py 的各条失败分支是否真的会 FAIL。

只用于本次自检实验，不属于交付物。用 MOCK_MODE 选择行为，MOCK_API_KEY 打开鉴权。
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

MODE = os.environ.get("MOCK_MODE", "good")
API_KEY = os.environ.get("MOCK_API_KEY", "")
PORT = int(os.environ.get("MOCK_PORT", "8131"))
EXEMPT = {"/health", "/docs", "/redoc", "/openapi.json"}

BOARDS = [
    {
        "board": "cie",
        "aliases": ["cie", "cambridge", "ca"],
        "db_key": "cambridge",
        "name": "Cambridge International",
        "upstream": "cie.fraft.cn",
        "subject_hint": "四位数字科目代码，如 0580 / 9709",
        "subject_pattern": r"^\d{4}$",
        "seasons": ["Mar", "Jun", "Nov"],
        "season_aliases": ["mar", "jun", "nov"],
        "modes": ["qp", "ms", "both"],
        "question_crop": False,
        "default_mode": "qp",
    },
    {
        "board": "edexcel",
        "aliases": ["edexcel", "edx", "pearson", "ial"],
        "db_key": "edexcel",
        "name": "Pearson Edexcel",
        "upstream": "qualifications.pearson.com",
        "subject_hint": "Pearson 规格代码或科目名（非四位数字）",
        "subject_pattern": r"^(?!\d{4}$).+$",
        "seasons": ["January", "June", "October", "November"],
        "season_aliases": ["january", "june", "october", "november"],
        "modes": ["paper", "question", "qa"],
        "question_crop": True,
        "default_mode": "paper",
    },
]

ZIP_BYTES = b"PK\x03\x04" + b"\x00" * 4092  # 只是形状对，不是真 ZIP


def boards_payload() -> dict:
    boards = [dict(b) for b in BOARDS]
    if MODE == "boards_missing_board":
        boards = [b for b in boards if b["board"] != "edexcel"]
    if MODE == "boards_missing_fields":
        for b in boards:
            b.pop("question_crop", None)
    return {"schema_version": "1", "auto_detect": {"rule": "x"}, "boards": boards}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # 静音
        pass

    def _send(self, status: int, payload: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, obj: object) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)

        if API_KEY and path not in EXEMPT:
            if self.headers.get("X-API-Key", "") != API_KEY:
                self._json(401, {"detail": "缺少或无效的 X-API-Key 请求头"})
                return

        if path == "/health":
            if MODE == "slow_health":
                time.sleep(5)
            self._json(200, {"status": "ok", "papers": 16})
            return

        if MODE == "server_500":
            self._json(500, {"detail": "boom"})
            return

        if path == "/api/v1/boards":
            self._json(200, boards_payload())
            return

        if path == "/api/v1/search":
            total = 0 if MODE == "search_empty" else 751
            self._json(200, {"total": total, "by_board": {"cambridge": total, "edexcel": 0}, "items": []})
            return

        if path == "/api/v1/paper":
            if MODE == "paper_502":
                self._json(502, {"detail": "上游不可用"})
                return
            if query.get("download", ["true"])[0].lower() in ("false", "0"):
                self._json(
                    200,
                    {
                        "schema_version": "1",
                        "counts": {"documents": 12, "files": 0, "bytes": 0},
                        "files": [],
                        "board": "cie",
                        "board_source": "inferred",
                    },
                )
                return
            if MODE == "download_html":
                self._send(200, b"<html>login</html>", "text/html; charset=utf-8")
                return
            if MODE == "download_nolen":
                # HTTP/1.1 chunked：故意不带 Content-Length
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for chunk in (ZIP_BYTES[:100], ZIP_BYTES[100:]):
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.write(b"0\r\n\r\n")
                return
            if MODE == "download_empty":
                self._send(200, b"", "application/zip")
                return
            if MODE == "download_truncated":
                # 声明 4096 字节却只发 100 字节后关连接：模拟被掐断的响应
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", "4096")
                self.end_headers()
                self.wfile.write(ZIP_BYTES[:100])
                self.wfile.flush()
                self.close_connection = True
                return
            self._send(200, ZIP_BYTES, "application/zip")
            return

        if MODE == "notfound_200":
            self._send(200, b"<html>welcome</html>", "text/html; charset=utf-8")
            return
        self._json(404, {"detail": "Not Found"})


def main() -> None:
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
