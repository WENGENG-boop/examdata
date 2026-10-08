"""上线自检：一条命令确认部署好的 examdata API 到底通没通。

只用标准库（`urllib` / `json` / `argparse` / `ssl`），**不依赖 requests**，
所以任何装了 Python 3.11+ 的机器都能直接跑——VPS 本机、你的笔记本、
或者临时开的跳板机都行，不需要先装项目依赖。

用法：
    python scripts/smoke_public_api.py --base-url https://<你的域名>
    python scripts/smoke_public_api.py --base-url http://127.0.0.1:8000
    python scripts/smoke_public_api.py --base-url https://<你的域名> --api-key <KEY>
    python scripts/smoke_public_api.py --base-url https://<你的域名> --skip-download
    python scripts/smoke_public_api.py --base-url https://<你的域名> --json > report.json

参数：
    --base-url       必填。API 根地址，如 https://exam.example.com（结尾斜杠可有可无）。
    --api-key        可选。以 `X-API-Key` 头发送（部署层若用别的头，请自行调整）。
                     给了它就额外做第 9 项：不带 key 的请求必须被拒。
    --timeout        可选。单次请求超时秒数，默认 30。第 7 项下载另有下限 180s：
                     服务端要先把上游多份 PDF 取回并打完 ZIP 才发第一个字节，
                     0580/2024/Jun 的 qp 整包（12 份 PDF、约 2.4MB）本机实测 15–50s，
                     沿用 30s 会把正常部署误判成超时。
    --json           可选。只输出机器可读 JSON，不打印人类可读文本（便于接监控）。
    --insecure       可选。跳过 TLS 证书校验，给自签证书的临时域名用。
    --skip-download  可选。跳过第 7 项真实下载检查，省流量（第 6 项仍会解析上游清单）。

检查项（逐项打印 PASS/FAIL 与关键数值）：
    1. GET /health                       存活探针，`status` 必须是 `ok`。
    2. GET /api/v1/boards                能力发现，`cie` 与 `edexcel` 都要在。
    3. GET /api/v1/search?limit=1        跨考试局检索，`total > 0`。
    4. GET /api/v1/timetable/seasons     时间表快照：CIE 25 个考季（另验 Edexcel ial 34 个）。
    5. GET /api/v1/materials             考试资料目录，`count > 0`。
    6. GET /api/v1/paper?download=false  清单解析，`counts.documents > 0`（不下载）。
    7. GET /api/v1/paper?mode=qp         真实下载：Content-Type / Content-Length / 文件头。
    8. 打一个不存在的路径                错误语义必须是 404。
    9. 不带 key 的请求（仅当传了 --api-key）  必须被拒 401。

退出码：全部通过 0；有任一失败非 0（跳过项不算失败）。
第 6、7 项会真的访问上游（Cambridge 走 cie.fraft.cn），上游临时不可用时它们会 FAIL，
提示里会说明是上游问题而不是你的部署问题。
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

# 冒烟固定组合：0580（Cambridge IGCSE 数学）2024 年 6 月卷。
# 选它是因为当前数据库里这个组合覆盖最完整，清单与下载都能稳定命中。
SMOKE_SUBJECT = "0580"
SMOKE_YEAR = 2024
SMOKE_SEASON = "Jun"

# 时间表快照随仓库一起发布（离线自带，运行时不联网）。这两个数字与仓库里的
# 快照数据同步：重建快照后（如新增考季）请同步更新，否则自检会报"快照不匹配"。
SMOKE_TIMETABLE_CIE_SEASONS = 25
SMOKE_TIMETABLE_EDEXCEL_IAL_SEASONS = 34

# /api/v1/boards 里每个 board 至少该给出的字段（网关契约）。
BOARD_REQUIRED_FIELDS = (
    "aliases",
    "name",
    "upstream",
    "subject_hint",
    "subject_pattern",
    "seasons",
    "modes",
    "question_crop",
    "default_mode",
)

# 连接层失败时按分类给出的下一步；`_classify` 的说明已经讲清了原因，
# 这里只补"该动手改什么"，避免两句话重复。
CONNECT_HINTS = {
    "tls": "这是证书问题、不是服务问题：自签证书加 --insecure 重跑（仅用于自检），"
    "正式环境请把证书链配全。",
    "timeout": "目标在超时时间内没响应：确认域名能解析、端口已放行、服务没卡住，"
    "或用 --timeout 调大。",
    "dns": "域名解析失败：检查 --base-url 的拼写，以及在当前机器上 nslookup 该域名。",
    "connect": "连接被拒绝：服务没在监听该端口，或防火墙 / 安全组没放行。",
    "reset": "连接被重置：反向代理可能直接掐断了连接，看 nginx 的 error.log。",
}

# 下载检查期望的媒体类型：单文件 PDF，或多文件内存 ZIP。
DOWNLOAD_MEDIA_TYPES = ("application/pdf", "application/zip")

# 下载检查的超时下限。服务端要先把上游的多份 PDF 全部取回、在内存里打完 ZIP
# 才发第一个字节，所以"等第一个字节"的时间远大于普通 JSON 请求；本机实测
# 0580/2024/Jun 的 qp 整包（12 份 PDF、约 2.4MB）要 50s 左右。若沿用
# --timeout 的默认 30s，部署正常也会被误判成超时，所以给下载单独一个下限。
# 连接层失败时第 1 项就会中止后续检查，因此这里放宽不会拖慢"服务没起来"的排查。
DOWNLOAD_TIMEOUT_FLOOR = 180.0


def _short(value: Any, limit: int = 240) -> str:
    """把任意值压成一行短文本，给人类读的输出用。"""
    if isinstance(value, bytes):
        # 错误体是原始字节：先按 UTF-8 解码，否则会打印成 b'\\xe6\\x9c\\xaa…'。
        text = value.decode("utf-8", "replace")
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    elif value is None:
        text = ""
    else:
        text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _http_hint(status: int | None) -> str:
    """按状态码给一句可执行的排查提示。"""
    if status is None:
        return ""
    if status == 401:
        return "鉴权未通过：确认 --api-key 与部署层配置一致。"
    if status == 403:
        return "被拒绝：可能是部署层鉴权，也可能是上游把该资源判为非公开。"
    if status == 404:
        return "路径或资源不存在：确认部署的是最新代码，且上游确有该年份/季度的文件。"
    if status == 422:
        return "参数不被接受：确认部署版本的 /api/v1 契约与本脚本一致。"
    if status in (502, 503, 504):
        return "上游或服务不可用：稍后重试；VPS 必须能出网访问上游站点。"
    if status >= 500:
        return "服务端错误：看服务日志（systemd 部署是 journalctl -u <服务名>）。"
    return ""


@dataclass
class HttpResult:
    """一次 HTTP 调用的结果。

    `status is None` 表示连接层就失败了（超时 / DNS / TLS / 拒绝连接），
    此时 `error` 是中文说明、`error_kind` 是机器可读的分类。
    """

    status: int | None
    headers: dict[str, str]
    body: bytes
    elapsed: float
    error: str = ""
    error_kind: str = ""

    @property
    def connected(self) -> bool:
        return self.error == ""

    def json(self) -> Any:
        """尽力解析 JSON；不是 JSON 就返回 None，由调用方自行判断。"""
        if not self.body:
            return None
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    def error_detail(self) -> str:
        """从错误体里取出 FastAPI 的 `{"detail": ...}`，取不到就返回截断的原文。"""
        body = self.json()
        if isinstance(body, dict) and "detail" in body:
            return _short(body["detail"])
        return _short(self.body)


def _classify(exc: BaseException) -> tuple[str, str]:
    """把连接层异常翻成（分类, 中文说明）。分类用于给出可执行的下一步。"""
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLCertVerificationError):
        return (
            "tls",
            f"TLS 证书校验失败：{_short(reason)}。"
            "自签证书或证书链不全时，加 --insecure 跳过校验（仅用于自检）。",
        )
    if isinstance(reason, ssl.SSLError):
        return "tls", f"TLS 握手失败：{_short(reason)}。确认域名与证书匹配。"
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return "timeout", f"请求超时：{_short(reason) or '目标未在超时时间内响应'}。可用 --timeout 调大。"
    if isinstance(reason, socket.gaierror):
        return "dns", f"域名解析失败：{_short(reason)}。检查 --base-url 的域名拼写与 DNS。"
    if isinstance(reason, ConnectionRefusedError):
        return "connect", "连接被拒绝：服务没在监听该端口，或防火墙/安全组没放行。"
    if isinstance(reason, ConnectionResetError):
        return "reset", "连接被重置：反向代理可能直接掐断了连接。"
    if isinstance(reason, OSError):
        return "os", f"网络错误：{_short(reason)}。"
    return "other", f"请求失败：{_short(reason)}。"


class Client:
    """极简 HTTP 客户端：显式 opener 才能让 --insecure 真正生效。"""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        timeout: float = 30.0,
        insecure: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        context = ssl.create_default_context()
        if insecure:
            # 只影响本次自检进程，不动系统信任库。
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context)
        )

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        use_key: bool = True,
        timeout: float | None = None,
    ) -> HttpResult:
        url = self.base_url + path
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/json, */*",
            "User-Agent": "examdata-smoke/1.0",
        }
        if use_key and self.api_key:
            headers["X-API-Key"] = self.api_key
        return self._request(url, headers, self.timeout if timeout is None else timeout)

    def _request(self, url: str, headers: dict[str, str], timeout: float) -> HttpResult:
        request = urllib.request.Request(url, method="GET")
        for name, value in headers.items():
            request.add_header(name, value)
        started = time.monotonic()
        try:
            with self._opener.open(request, timeout=timeout) as response:
                body = response.read()
                return HttpResult(
                    status=response.status,
                    headers={k.lower(): v for k, v in response.headers.items()},
                    body=body,
                    elapsed=time.monotonic() - started,
                )
        except urllib.error.HTTPError as exc:
            # 4xx/5xx 也是"连上了"：把错误体读出来交给调用方判断。
            try:
                body = exc.read()
            except Exception:  # noqa: BLE001 - 读不到错误体不影响状态码判定
                body = b""
            return HttpResult(
                status=exc.code,
                headers={k.lower(): v for k, v in (exc.headers or {}).items()},
                body=body,
                elapsed=time.monotonic() - started,
            )
        except urllib.error.URLError as exc:
            kind, message = _classify(exc)
            return HttpResult(None, {}, b"", time.monotonic() - started, message, kind)
        except (ssl.SSLError, OSError, TimeoutError) as exc:
            kind, message = _classify(exc)
            return HttpResult(None, {}, b"", time.monotonic() - started, message, kind)


@dataclass
class Check:
    """一项检查的结果。连接层失败由 `Smoke._aborted` 统一记，不再逐项标记。"""

    key: str
    title: str
    status: str = SKIP
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    hint: str = ""


class Smoke:
    """按顺序跑检查项，边跑边打印（`--json` 时静默，最后统一吐 JSON）。"""

    def __init__(
        self,
        client: Client,
        *,
        api_key: str = "",
        skip_download: bool = False,
        quiet: bool = False,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.skip_download = skip_download
        self.quiet = quiet
        self._aborted = False

    # ---------- 输出 ----------

    def _say(self, text: str = "") -> None:
        if not self.quiet:
            print(text, flush=True)

    def _record(self, check: Check) -> None:
        self._say(f"      {check.status}  {check.detail}")
        if check.hint and check.status == FAIL:
            self._say(f"      提示：{check.hint}")

    def _fatal(self, check: Check, result: HttpResult) -> Check:
        check.status = FAIL
        check.detail = result.error
        check.metrics = {"error_kind": result.error_kind}
        check.hint = CONNECT_HINTS.get(
            result.error_kind,
            "先确认 --base-url 能连上、服务已启动、端口已放行。",
        )
        self._aborted = True
        return check

    # ---------- 检查项 ----------

    def check_health(self) -> Check:
        check = Check("health", "存活探针 GET /health")
        result = self.client.get("/health")
        if not result.connected:
            return self._fatal(check, result)
        body = _as_dict(result.json())
        status_field = body.get("status")
        check.metrics = {
            "status_code": result.status,
            "status": status_field,
            "papers": body.get("papers"),
        }
        if result.status != 200:
            check.status = FAIL
            check.detail = f"HTTP {result.status}（期望 200）{result.error_detail()}"
            check.hint = _http_hint(result.status)
        elif status_field != "ok":
            check.status = FAIL
            check.detail = f"HTTP 200 但 status={status_field!r}（期望 'ok'）"
            check.hint = "服务活着但数据库探针没过：看 /health 的响应与服务日志。"
        else:
            check.status = PASS
            check.detail = f"HTTP 200  status=ok  papers={body.get('papers')}"
        return check

    def check_boards(self) -> Check:
        check = Check("boards", "能力发现 GET /api/v1/boards")
        result = self.client.get("/api/v1/boards")
        if not result.connected:
            return self._fatal(check, result)
        if result.status != 200:
            check.status = FAIL
            check.detail = f"HTTP {result.status}（期望 200）{result.error_detail()}"
            check.hint = _http_hint(result.status)
            return check

        body = _as_dict(result.json())
        raw_boards = body.get("boards")
        # 上游可能给 null 或非数组：这里只挑出字典项，剩下的走"缺 board"分支报 FAIL，
        # 不让一个畸形响应把脚本打成 traceback。
        boards = [b for b in raw_boards if isinstance(b, dict)] if isinstance(raw_boards, list) else []
        names = [b.get("board") for b in boards]
        missing_boards = [name for name in ("cie", "edexcel") if name not in names]
        missing_fields: dict[str, list[str]] = {}
        for board in boards:
            absent = [key for key in BOARD_REQUIRED_FIELDS if key not in board]
            if absent:
                missing_fields[str(board.get("board"))] = absent

        check.metrics = {
            "status_code": result.status,
            "schema_version": body.get("schema_version"),
            "boards": names,
            "missing_boards": missing_boards,
            "missing_fields": missing_fields,
        }
        summary = (
            f"HTTP 200  boards={','.join(str(n) for n in names) or '(空)'}"
            f"  schema_version={body.get('schema_version')}"
        )
        if missing_boards or missing_fields:
            check.status = FAIL
            check.detail = summary
            if missing_boards:
                check.detail += f"  缺少 board: {','.join(missing_boards)}"
            if missing_fields:
                check.detail += f"  缺字段: {_short(missing_fields)}"
            check.hint = "部署的版本可能没挂上统一网关（/api/v1），确认代码已更新并重启服务。"
        else:
            check.status = PASS
            check.detail = summary
        return check

    def check_search(self) -> Check:
        check = Check("search", "跨考试局检索 GET /api/v1/search?limit=1")
        result = self.client.get("/api/v1/search", params={"limit": 1})
        if not result.connected:
            return self._fatal(check, result)
        if result.status != 200:
            check.status = FAIL
            check.detail = f"HTTP {result.status}（期望 200）{result.error_detail()}"
            check.hint = _http_hint(result.status)
            return check

        body = _as_dict(result.json())
        total = body.get("total")
        by_board = _as_dict(body.get("by_board"))
        items_raw = body.get("items")
        check.metrics = {
            "status_code": result.status,
            "total": total,
            "by_board": by_board,
            "items": len(items_raw) if isinstance(items_raw, list) else 0,
        }
        detail = f"HTTP 200  total={total}  by_board={_short(by_board)}"
        if isinstance(total, int) and total > 0:
            check.status = PASS
            check.detail = detail
        else:
            check.status = FAIL
            check.detail = f"{detail}（期望 total > 0）"
            check.hint = "库里没数据：确认数据库已灌入并指向正确的 EXAMDATA_DATABASE_URL。"
        return check

    def check_timetable(self) -> Check:
        check = Check(
            "timetable",
            "考试时间表 GET /api/v1/timetable/seasons（CIE 与 Edexcel ial）",
        )
        result = self.client.get("/api/v1/timetable/seasons")
        if not result.connected:
            return self._fatal(check, result)
        if result.status != 200:
            check.status = FAIL
            check.detail = f"HTTP {result.status}（期望 200）{result.error_detail()}"
            check.hint = _http_hint(result.status)
            return check

        body = _as_dict(result.json())
        totals = _as_dict(body.get("totals"))
        cie_seasons = totals.get("available_seasons")
        check.metrics = {
            "status_code": result.status,
            "board": body.get("board"),
            "zone": body.get("zone"),
            "cie_available_seasons": cie_seasons,
            "cie_events": totals.get("events"),
        }
        detail = (
            f"HTTP 200  board={body.get('board')}  zone={body.get('zone')}"
            f"  totals.available_seasons={cie_seasons}"
        )
        if cie_seasons != SMOKE_TIMETABLE_CIE_SEASONS:
            check.status = FAIL
            check.detail = f"{detail}（期望 {SMOKE_TIMETABLE_CIE_SEASONS}）"
            check.hint = (
                "时间表快照缺失或与仓库不同步：确认部署包带上 timetable 数据目录"
                "（快照离线自带、无需联网）；若是快照更新，请同步改脚本顶部的 "
                "SMOKE_TIMETABLE_* 常量。"
            )
            return check

        # 第二个请求验证 Edexcel：family=ial 应只返回 ial 系列（34 季，少于
        # 该考试局总数），顺带确认 family 过滤没有被忽略。
        result = self.client.get(
            "/api/v1/timetable/seasons", params={"board": "edexcel", "family": "ial"}
        )
        if not result.connected:
            return self._fatal(check, result)
        if result.status != 200:
            check.status = FAIL
            check.detail = f"HTTP {result.status}（期望 200）{result.error_detail()}"
            check.hint = _http_hint(result.status)
            return check

        body = _as_dict(result.json())
        counts = _as_dict(body.get("counts"))
        totals = _as_dict(body.get("totals"))
        ial_seasons = counts.get("seasons")
        board_total = totals.get("available_seasons")
        check.metrics.update(
            {
                "edexcel_ial_seasons": ial_seasons,
                "edexcel_available_seasons": board_total,
            }
        )
        detail += (
            f" | edexcel family=ial counts.seasons={ial_seasons}"
            f"（期望 {SMOKE_TIMETABLE_EDEXCEL_IAL_SEASONS}，该局总数 {board_total}）"
        )
        check.detail = detail
        if ial_seasons == SMOKE_TIMETABLE_EDEXCEL_IAL_SEASONS:
            check.status = PASS
        else:
            check.status = FAIL
            check.hint = (
                "Edexcel 时间表不匹配：确认部署包含 edexcel 时间表快照"
                f"（ial {SMOKE_TIMETABLE_EDEXCEL_IAL_SEASONS} 季）；"
                "若是快照更新，请同步改脚本顶部的 SMOKE_TIMETABLE_* 常量。"
            )
        return check

    def check_materials(self) -> Check:
        check = Check("materials", "考试资料 GET /api/v1/materials")
        result = self.client.get("/api/v1/materials")
        if not result.connected:
            return self._fatal(check, result)
        if result.status != 200:
            check.status = FAIL
            check.detail = f"HTTP {result.status}（期望 200）{result.error_detail()}"
            check.hint = _http_hint(result.status)
            return check

        body = _as_dict(result.json())
        count = body.get("count")
        items = body.get("items")
        check.metrics = {
            "status_code": result.status,
            "count": count,
            "items": len(items) if isinstance(items, list) else 0,
        }
        detail = f"HTTP 200  count={count}"
        if isinstance(count, int) and count > 0:
            check.status = PASS
            check.detail = detail
        else:
            check.status = FAIL
            check.detail = f"{detail}（期望 count > 0）"
            check.hint = (
                "资料目录为空或缺失：确认部署包含 materials 数据文件"
                "（src/examdata/materials/data/catalog.json）。"
            )
        return check

    def check_manifest(self) -> Check:
        check = Check(
            "manifest",
            "清单解析 GET /api/v1/paper?download=false（不下载）",
        )
        params = {
            "subject": SMOKE_SUBJECT,
            "year": SMOKE_YEAR,
            "season": SMOKE_SEASON,
            "download": "false",
        }
        result = self.client.get("/api/v1/paper", params=params)
        if not result.connected:
            return self._fatal(check, result)
        if result.status != 200:
            check.status = FAIL
            check.detail = f"HTTP {result.status}（期望 200）{result.error_detail()}"
            check.hint = _http_hint(result.status)
            return check

        body = _as_dict(result.json())
        counts = _as_dict(body.get("counts"))
        documents = counts.get("documents")
        check.metrics = {
            "status_code": result.status,
            "documents": documents,
            "files": counts.get("files"),
            "board": body.get("board"),
            "board_source": body.get("board_source"),
        }
        detail = (
            f"HTTP 200  counts.documents={documents}  counts.files={counts.get('files')}"
            f"  board={body.get('board')}  board_source={body.get('board_source')}"
        )
        if isinstance(documents, int) and documents > 0:
            check.status = PASS
            check.detail = detail
        else:
            check.status = FAIL
            check.detail = f"{detail}（期望 counts.documents > 0）"
            check.hint = (
                "上游清单里没有这个组合，或上游暂时不可用；"
                f"先确认 VPS 能访问 cie.fraft.cn，再试 subject={SMOKE_SUBJECT} "
                f"year={SMOKE_YEAR} season={SMOKE_SEASON}。"
            )
        return check

    def check_download(self) -> Check:
        check = Check(
            "download",
            f"真实下载 GET /api/v1/paper?mode=qp（{SMOKE_SUBJECT}/{SMOKE_YEAR}/{SMOKE_SEASON}）",
        )
        if self.skip_download:
            check.status = SKIP
            check.detail = "已按 --skip-download 跳过（不消耗流量）"
            return check

        params = {
            "subject": SMOKE_SUBJECT,
            "year": SMOKE_YEAR,
            "season": SMOKE_SEASON,
            "mode": "qp",
        }
        # 这一项要等服务端把上游整包取回，超时下限单独放宽，理由见
        # DOWNLOAD_TIMEOUT_FLOOR 处的注释。
        budget = max(self.client.timeout, DOWNLOAD_TIMEOUT_FLOOR)
        result = self.client.get("/api/v1/paper", params=params, timeout=budget)
        if not result.connected:
            self._fatal(check, result)
            if result.error_kind == "timeout":
                check.hint = (
                    f"等待 {budget:g}s 仍没拿到第一个字节：服务端要先从上游取回整包"
                    "（mode=qp 是多份 PDF 打成的 ZIP），上游慢就会这样。"
                    "可加大 --timeout，或加 --skip-download 只做清单检查。"
                )
            return check
        if result.status != 200:
            check.status = FAIL
            check.detail = f"HTTP {result.status}（期望 200）{result.error_detail()}"
            check.hint = _http_hint(result.status)
            return check

        content_type = result.headers.get("content-type", "").split(";")[0].strip().lower()
        declared = result.headers.get("content-length", "")
        received = len(result.body)
        magic_pdf = result.body[:5] == b"%PDF-"
        magic_zip = result.body[:2] == b"PK"
        disposition = result.headers.get("content-disposition", "")

        problems: list[str] = []
        if content_type not in DOWNLOAD_MEDIA_TYPES:
            problems.append(f"Content-Type={content_type or '(缺失)'}，期望 pdf 或 zip")
        if not declared:
            problems.append("响应头缺 Content-Length")
        elif not declared.isdigit() or int(declared) != received:
            problems.append(f"Content-Length={declared} 与实收 {received} 字节不一致")
        if not (magic_pdf or magic_zip):
            problems.append(f"文件头不是 %PDF- 也不是 PK（实收 {result.body[:8]!r}）")
        if received == 0:
            problems.append("实收 0 字节")

        check.metrics = {
            "status_code": result.status,
            "content_type": content_type,
            "content_length_header": declared or None,
            "received_bytes": received,
            "magic": "pdf" if magic_pdf else ("zip" if magic_zip else "unknown"),
            "content_disposition": disposition or None,
            "elapsed_seconds": round(result.elapsed, 2),
            "timeout_seconds": budget,
        }
        detail = (
            f"HTTP 200  {content_type or '(无 Content-Type)'}"
            f"  Content-Length={declared or '(缺失)'}"
            f"  实收={received}B  文件头={'%PDF-' if magic_pdf else ('PK' if magic_zip else '未知')}"
            f"  耗时={result.elapsed:.2f}s"
        )
        if problems:
            check.status = FAIL
            check.detail = f"{detail}  问题: {'; '.join(problems)}"
            check.hint = "下载链路（上游取字节 → 内存 ZIP → 响应头）有问题，看服务日志确认。"
        else:
            check.status = PASS
            check.detail = detail
        return check

    def check_not_found(self) -> Check:
        check = Check("not_found", "错误语义：不存在的路径必须 404")
        result = self.client.get("/api/v1/__smoke_public_api_not_found__")
        if not result.connected:
            return self._fatal(check, result)
        check.metrics = {"status_code": result.status, "body": result.error_detail()}
        if result.status == 404:
            check.status = PASS
            check.detail = "HTTP 404  detail=" + (result.error_detail() or "(空)")
        else:
            check.status = FAIL
            check.detail = f"HTTP {result.status}（期望 404）{result.error_detail()}"
            if result.status in (401, 403):
                check.hint = (
                    "请求在鉴权层就被拦下了，没走到路由："
                    "确认 --api-key 与部署层配置一致（本服务的头是 X-API-Key）。"
                )
            else:
                check.hint = (
                    "未知路径被改写成了别的状态码："
                    "常见原因是反向代理配了兜底路由或登录页，请检查 nginx 配置。"
                )
        return check

    def check_auth(self) -> Check:
        check = Check("auth", "鉴权：不带 key 的请求必须被拒（401）")
        result = self.client.get("/api/v1/boards", use_key=False)
        if not result.connected:
            return self._fatal(check, result)
        check.metrics = {"status_code": result.status, "body": result.error_detail()}
        if result.status == 401:
            check.status = PASS
            check.detail = f"HTTP 401  {result.error_detail() or '未授权'}"
        elif result.status == 403:
            check.status = FAIL
            check.detail = f"HTTP 403（鉴权生效了，但规范期望 401）{result.error_detail()}"
            check.hint = "部署层（nginx / 网关）用 403 拒绝的；改成 401 才与本脚本的契约一致。"
        else:
            check.status = FAIL
            check.detail = (
                f"HTTP {result.status}（期望 401）"
                f"不带 key 也能访问，响应片段 {_short(result.body, 120)}"
            )
            check.hint = (
                "鉴权没生效。本服务自带 API Key 中间件"
                "（src/examdata/api/security.py，环境变量 EXAMDATA_API_KEY，"
                "命中返回 401）；若不用它，请在 nginx / 网关上限制。"
            )
        return check

    # ---------- 主流程 ----------

    def plan(self) -> list[tuple[str, str, Callable[[], Check]]]:
        """（标题, key, 检查函数）三元组，顺序就是打印顺序。"""
        steps: list[tuple[str, str, Callable[[], Check]]] = [
            ("存活探针 GET /health", "health", self.check_health),
            ("能力发现 GET /api/v1/boards", "boards", self.check_boards),
            ("跨考试局检索 GET /api/v1/search?limit=1", "search", self.check_search),
            (
                "考试时间表 GET /api/v1/timetable/seasons（CIE 与 Edexcel ial）",
                "timetable",
                self.check_timetable,
            ),
            ("考试资料 GET /api/v1/materials", "materials", self.check_materials),
            (
                "清单解析 GET /api/v1/paper?download=false（不下载）",
                "manifest",
                self.check_manifest,
            ),
            (
                f"真实下载 GET /api/v1/paper?mode=qp"
                f"（{SMOKE_SUBJECT}/{SMOKE_YEAR}/{SMOKE_SEASON}）",
                "download",
                self.check_download,
            ),
            ("错误语义：不存在的路径必须 404", "not_found", self.check_not_found),
        ]
        if self.api_key:
            steps.append(("鉴权：不带 key 的请求必须被拒（401）", "auth", self.check_auth))
        return steps

    def run(self) -> list[Check]:
        steps = self.plan()
        total = len(steps)
        results: list[Check] = []
        for index, (title, key, step) in enumerate(steps, start=1):
            self._say(f"[{index}/{total}] {title}")
            if self._aborted:
                # 连接层已经失败，后面几项再打也只是重复同一条错误。
                check = Check(key, title, SKIP, "连接层已失败，不再发起后续请求")
            else:
                try:
                    check = step()
                except Exception as exc:  # noqa: BLE001 - 自检工具不该因单项异常整体崩掉
                    check = Check(key, title, FAIL, f"检查内部异常：{type(exc).__name__}: {exc}")
                    check.hint = (
                        "这通常是响应结构与 /api/v1 契约不符（缺字段、类型不对）；"
                        "把该端点的原始响应抓下来对照 docs/API.md。"
                    )
                else:
                    check.key = key
                    check.title = title
            self._record(check)
            self._say()
            results.append(check)
        return results


def build_report(
    checks: list[Check], *, base_url: str, elapsed: float, api_key_used: bool
) -> dict[str, Any]:
    passed = sum(1 for c in checks if c.status == PASS)
    failed = sum(1 for c in checks if c.status == FAIL)
    skipped = sum(1 for c in checks if c.status == SKIP)
    return {
        "tool": "examdata-smoke",
        "schema_version": "1",
        "base_url": base_url,
        "api_key_used": api_key_used,
        "ok": failed == 0,
        "elapsed_seconds": round(elapsed, 2),
        "summary": {
            "total": len(checks),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "checks": [
            {
                "key": c.key,
                "title": c.title,
                "status": c.status,
                "detail": c.detail,
                "metrics": c.metrics,
                "hint": c.hint,
            }
            for c in checks
        ],
    }


def render_human(report: dict[str, Any], *, insecure: bool) -> None:
    summary = report["summary"]
    line = "=" * 68
    print(line)
    print(
        f"通过 {summary['passed']} / {summary['total']}"
        f"（失败 {summary['failed']}，跳过 {summary['skipped']}）"
        f"，耗时 {report['elapsed_seconds']}s"
    )
    if insecure:
        print("注意：本次用 --insecure 跳过了 TLS 证书校验，结论只代表服务本身可用。")
    failures = [c for c in report["checks"] if c["status"] == FAIL]
    if failures:
        print("失败项：")
        for check in failures:
            print(f"  - {check['title']}：{check['detail']}")
        print(f"结论：有 {len(failures)} 项未通过，请按上面的提示排查。")
    elif summary["skipped"]:
        print(
            f"结论：已跑的检查全部通过（{summary['skipped']} 项被跳过、未验证）。"
        )
    else:
        print("结论：全部通过，API 已就绪。")
    print(line)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="smoke_public_api.py",
        description="examdata 上线自检：逐项确认部署好的 API 是否真的可用。",
        epilog="示例：python scripts/smoke_public_api.py --base-url https://exam.example.com",
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="API 根地址，如 https://exam.example.com（结尾斜杠可有可无）",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="可选：以 X-API-Key 头发送；给了它就会额外检查不带 key 是否被拒 401",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help=f"单次请求超时秒数，默认 30；下载检查另有下限 {DOWNLOAD_TIMEOUT_FLOOR:g}s",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="只输出机器可读 JSON（不打印人类可读文本）",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="跳过 TLS 证书校验（自签证书的临时域名用）",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="跳过真实下载检查，省流量（清单解析仍会做）",
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    base_url = args.base_url.strip().rstrip("/")
    note = ""
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
        note = f"未写协议，按 https:// 处理：{base_url}"

    if args.json:
        if note:
            print(note, file=sys.stderr)
    else:
        print("examdata 上线自检")
        print(f"目标      {base_url}")
        print(f"超时      {args.timeout:g}s（下载检查另有下限 {DOWNLOAD_TIMEOUT_FLOOR:g}s）")
        print(f"鉴权      {'X-API-Key 已提供' if args.api_key else '未提供（不检查鉴权）'}")
        print(f"下载检查  {'跳过' if args.skip_download else '执行'}")
        if note:
            print(f"说明      {note}")
        print("-" * 68)

    client = Client(
        base_url,
        api_key=args.api_key,
        timeout=args.timeout,
        insecure=args.insecure,
    )
    smoke = Smoke(
        client,
        api_key=args.api_key,
        skip_download=args.skip_download,
        quiet=args.json,
    )

    started = time.monotonic()
    checks = smoke.run()
    elapsed = time.monotonic() - started
    report = build_report(
        checks, base_url=base_url, elapsed=elapsed, api_key_used=bool(args.api_key)
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        render_human(report, insecure=args.insecure)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
