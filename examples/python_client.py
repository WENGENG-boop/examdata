#!/usr/bin/env python3
"""examdata 统一网关（``/api/v1``）的 Python 客户端示例。

演示四件事：

1. 能力发现：``GET /api/v1/boards``——有哪些考试局、各自的科目形态与取卷模式；
2. 跨考试局检索：``GET /api/v1/search``——只读本地数据库，不访问上游站点；
3. 统一取卷：``GET /api/v1/paper``——解析清单 / 下载二进制 / 取 base64 JSON；
4. 单题聚合：``GET /api/v1/question/{id}``——题目 + 所属试卷定位 + 可回填的取卷链接。

HTTP 后端优先用 ``requests``；本机没装时自动退回项目自带的 ``httpx``
（两者在本脚本用到的接口上一致），所以只有项目依赖的环境也能直接跑。
``--verbose`` 会打印实际请求的 URL。

用法（工作目录是仓库根）::

    # 终端 A：起服务
    examdata serve --port 8000

    # 终端 B：
    python examples/python_client.py boards
    python examples/python_client.py search --subject 0580 --leaves-only --limit 5
    python examples/python_client.py paper --subject 0580 --year 2024 --season Jun --paper 11 --no-download
    python examples/python_client.py paper --subject 0580 --year 2024 --season Jun --paper 11 --out /tmp/examdata-out
    python examples/python_client.py question --id 1
    python examples/python_client.py demo          # 依次跑上面四类

base URL 默认 ``http://127.0.0.1:8000``，可用 ``--base-url`` 或环境变量
``EXAMDATA_BASE_URL`` 覆盖。服务端设了 ``EXAMDATA_API_KEY`` 时，用 ``--api-key``
或环境变量 ``EXAMDATA_API_KEY`` 传同一个值，客户端会放进 ``X-API-Key`` 头；
服务端没设该变量时这个头会被忽略，不影响调用。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_BASE_URL = os.environ.get("EXAMDATA_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_API_KEY = os.environ.get("EXAMDATA_API_KEY", "")
DEFAULT_TIMEOUT = 120.0

try:  # 优先 requests；缺失时退回 httpx（项目依赖，必定可用）
    import requests

    BACKEND = "requests"
except ImportError:  # pragma: no cover - 取决于运行环境
    import httpx

    BACKEND = "httpx"

# Content-Disposition: attachment; filename="xxx.pdf" —— 取服务端给的文件名。
RE_FILENAME = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.IGNORECASE)


def normalize_base_url(base_url: str) -> str:
    """规范化 base URL：去掉尾部斜杠，并容忍把 ``/api/v1`` 前缀一起写进来。

    本脚本自己会拼 ``/api/v1/...``，调用方直接抄文档里的
    ``http://<主机>/api/v1`` 也不会拼成双前缀。
    """
    normalized = (base_url or "").strip().rstrip("/")
    if normalized.endswith("/api/v1"):
        normalized = normalized[: -len("/api/v1")]
    return normalized


class ApiError(RuntimeError):
    """HTTP 4xx/5xx。``detail`` 是 FastAPI 错误体里的原始说明。"""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class Client:
    """极简 HTTP 客户端：统一 base URL、API Key 与错误语义。"""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = normalize_base_url(base_url)
        self.api_key = api_key
        self.timeout = timeout
        self.verbose = False
        if BACKEND == "requests":
            self._session = requests.Session()
        else:
            # httpx 默认不跟随重定向，显式打开，行为与 requests 对齐。
            self._session = httpx.Client(follow_redirects=True)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def _headers(self, accept: str) -> dict[str, str]:
        headers = {"Accept": accept}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def get(self, path: str, params: dict | None = None, *, accept: str = "application/json"):
        """GET 一次；非 2xx 抛 ``ApiError``。params 里值为 None 的键会被丢掉。"""
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        url = self.base_url + path
        if self.verbose:
            query = "&".join(f"{k}={v}" for k, v in clean.items())
            print(f"[verbose] GET {url}{'?' + query if query else ''}", file=sys.stderr)
        response = self._session.get(
            url, params=clean, headers=self._headers(accept), timeout=self.timeout
        )
        if response.status_code >= 400:
            detail = response.text
            try:
                payload = response.json()
                if isinstance(payload, dict) and "detail" in payload:
                    detail = payload["detail"]
            except ValueError:
                pass
            raise ApiError(response.status_code, str(detail))
        return response

    def get_json(self, path: str, params: dict | None = None) -> dict:
        return self.get(path, params).json()


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------


def _print_json(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_boards(client: Client, args: argparse.Namespace) -> int:
    """能力发现：列出考试局、别名、科目形态与可用模式。"""
    data = client.get_json("/api/v1/boards")
    if args.json:
        _print_json(data)
        return 0
    print(f"schema_version = {data.get('schema_version')}")
    detect = data.get("auto_detect") or {}
    if detect:
        print(f"auto_detect    = {json.dumps(detect, ensure_ascii=False)}")
    for board in data.get("boards", []):
        print(f"\n[{board.get('board')}] {board.get('name')}")
        print(f"  别名       : {', '.join(board.get('aliases', []))}")
        print(f"  上游       : {board.get('upstream')}")
        print(f"  科目形态   : {board.get('subject_hint')}")
        print(f"  考季       : {', '.join(board.get('seasons', []))}")
        print(f"  模式       : {', '.join(board.get('modes', []))}（默认 {board.get('default_mode')}）")
        print(f"  按题裁剪   : {'支持' if board.get('question_crop') else '不支持'}")
    return 0


def _search_params(args: argparse.Namespace) -> dict:
    return {
        "keyword": args.keyword,
        "subject": args.subject,
        "board": args.board,
        "year": args.year,
        "session": args.session,
        "paper": args.paper,
        "marks_min": args.marks_min,
        "marks_max": args.marks_max,
        "leaves_only": "true" if args.leaves_only else None,
        "has_answer": "true" if args.has_answer else None,
        "limit": args.limit,
        "offset": args.offset,
    }


def cmd_search(client: Client, args: argparse.Namespace) -> int:
    """跨考试局检索：一次请求同时给出两个考试局的命中数。"""
    data = client.get_json("/api/v1/search", _search_params(args))
    if args.json:
        _print_json(data)
        return 0
    by_board = data.get("by_board") or {}
    print(
        f"命中 {data.get('total')} 题（cambridge={by_board.get('cambridge', 0)}, "
        f"edexcel={by_board.get('edexcel', 0)}）"
        f"  limit={data.get('limit')} offset={data.get('offset')}"
    )
    for item in data.get("items", []):
        stem = (item.get("stem_text") or "").replace("\n", " ")
        if len(stem) > 60:
            stem = stem[:60] + "…"
        print(
            f"  #{item.get('question_id'):<6} {item.get('board'):<10} "
            f"{item.get('subject_code') or '-':<6} {item.get('year') or '-'} "
            f"{item.get('paper_code') or '-':<8} {item.get('number_path') or '-':<8} "
            f"{item.get('marks') if item.get('marks') is not None else '-'} 分  {stem}"
        )
    return 0


def _paper_params(args: argparse.Namespace) -> dict:
    return {
        "subject": args.subject,
        "year": args.year,
        "season": args.season,
        "board": args.board,
        "paper": args.paper,
        "question": args.question,
        "mode": args.mode,
    }


def _save(out_dir: Path, name: str, data: bytes) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / name
    target.write_bytes(data)
    return target


def cmd_paper(client: Client, args: argparse.Namespace) -> int:
    """统一取卷：download=false 只解析清单；download=true 取字节或 base64。"""
    params = _paper_params(args)
    if args.no_download:
        data = client.get_json("/api/v1/paper", {**params, "download": "false"})
        if args.json:
            _print_json(data)
            return 0
        counts = data.get("counts") or {}
        print(
            f"board={data.get('board')}（{data.get('board_source')}）"
            f"  documents={counts.get('documents')} files={counts.get('files')}"
        )
        for doc in data.get("documents", []):
            print(f"  [{doc.get('role')}] {doc.get('name')}  {doc.get('url')}")
        return 0

    if args.format == "json":
        data = client.get_json("/api/v1/paper", {**params, "download": "true", "format": "json"})
        counts = data.get("counts") or {}
        print(
            f"board={data.get('board')}（{data.get('board_source')}）"
            f"  files={counts.get('files')} bytes={counts.get('bytes')}"
        )
        for item in data.get("files", []):
            print(f"  {item.get('name')}  {item.get('size')} 字节  sha256={str(item.get('sha256'))[:12]}")
            payload = item.get("data_base64")
            if payload and args.out:
                target = _save(Path(args.out), item["name"], base64.b64decode(payload))
                print(f"    -> 已保存 {target}")
        if args.out is None and any(item.get("data_base64") for item in data.get("files", [])):
            print("  （加 --out <目录> 可把 base64 载荷落盘）")
        return 0

    response = client.get(
        "/api/v1/paper", {**params, "download": "true"}, accept="application/octet-stream"
    )
    disposition = response.headers.get("Content-Disposition", "")
    match = RE_FILENAME.search(disposition)
    name = match.group(1) if match else "paper.bin"
    data = response.content
    print(
        f"{name}  {len(data)} 字节  "
        f"Content-Type={response.headers.get('Content-Type')}  "
        f"Content-Length={response.headers.get('Content-Length')}"
    )
    if args.out:
        target = _save(Path(args.out), name, data)
        print(f"-> 已保存 {target}")
    else:
        print("（加 --out <目录> 落盘；或改用 --format json 走 base64）")
    return 0


def cmd_question(client: Client, args: argparse.Namespace) -> int:
    """单题聚合视图：题目本身 + 所属试卷定位 + 可直接调用的取卷链接。"""
    data = client.get_json(f"/api/v1/question/{args.id}")
    if args.json:
        _print_json(data)
        return 0
    source = data.get("source") or {}
    bundle = data.get("bundle") or {}
    question = bundle.get("question") or bundle
    print(f"question_id = {data.get('question_id')}  board = {data.get('board')}")
    print(
        f"  source: {source.get('subject_code')} / {source.get('year')} "
        f"{source.get('session')} / paper {source.get('paper_code')}"
        f"  (board_canonical={source.get('board_canonical')})"
    )
    print(f"  取卷链接: {source.get('paper_endpoint')}")
    print(
        f"  题目: {question.get('number_path')}  {question.get('marks')} 分  "
        f"kind={question.get('kind')}"
    )
    stem = (question.get("stem_text") or "").strip().replace("\n", " ")
    print(f"  题干: {stem[:120]}{'…' if len(stem) > 120 else ''}")
    children = bundle.get("children") or []
    if children:
        print(f"  子题: {', '.join(str(c.get('number_path')) for c in children)}")
    print(f"  bundle 顶层字段: {', '.join(sorted(bundle.keys()))}")
    return 0


def cmd_demo(client: Client, args: argparse.Namespace) -> int:
    """依次跑四类调用。任何一步失败都会打印原因，最后以退出码汇报。"""
    steps = [
        ("能力发现 /api/v1/boards", lambda: cmd_boards(client, args)),
        ("跨局检索 /api/v1/search", lambda: cmd_search(client, args)),
    ]
    failures = 0
    for title, run in steps:
        print(f"\n=== {title} ===")
        try:
            failures += run()
        except ApiError as exc:
            failures += 1
            print(f"!! 失败: {exc}")

    print("\n=== 单题聚合 /api/v1/question/{id} ===")
    try:
        data = client.get_json("/api/v1/search", {**_search_params(args), "limit": 1})
        items = data.get("items") or []
        if not items:
            print("（检索没有命中，跳过；换一组过滤条件再试）")
        else:
            args.id = items[0]["question_id"]
            failures += cmd_question(client, args)
    except ApiError as exc:
        failures += 1
        print(f"!! 失败: {exc}")

    print("\n=== 统一取卷 /api/v1/paper（只解析清单）===")
    try:
        failures += cmd_paper(client, args)
    except ApiError as exc:
        failures += 1
        print(f"!! 失败: {exc}")

    print(f"\n完成：{4 - failures}/4 步成功")
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------


def common_options() -> argparse.ArgumentParser:
    """顶层与各子命令共用的选项。

    同名选项在子命令前后都能写：子命令里的副本默认值取 ``SUPPRESS``，
    没显式传时不会覆盖顶层已经解析出来的值。
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--base-url",
        default=argparse.SUPPRESS,
        help=f"服务地址，默认 {DEFAULT_BASE_URL}（也可用环境变量 EXAMDATA_BASE_URL）",
    )
    common.add_argument(
        "--api-key",
        default=argparse.SUPPRESS,
        help="服务端 EXAMDATA_API_KEY 的值，放进 X-API-Key 头；未启用鉴权时可省略",
    )
    common.add_argument(
        "--timeout", type=float, default=argparse.SUPPRESS, help="单请求超时秒数"
    )
    common.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="打印完整 JSON 而不是摘要"
    )
    common.add_argument(
        "--verbose", action="store_true", default=argparse.SUPPRESS, help="打印实际请求的 URL"
    )
    return common


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python_client.py",
        description="examdata 统一网关（/api/v1）客户端示例",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python examples/python_client.py boards\n"
            "  python examples/python_client.py search --subject 0580 --limit 5\n"
            "  python examples/python_client.py paper --subject 0580 --year 2024 --season Jun "
            "--paper 11 --no-download\n"
            "  python examples/python_client.py paper --subject 0580 --year 2024 --season Jun "
            "--paper 11 --out /tmp/examdata-out\n"
            "  python examples/python_client.py question --id 1\n"
            "  python examples/python_client.py          # 不给子命令等于 demo\n"
            "\n--base-url / --api-key / --timeout / --json / --verbose 放在子命令前后都行。\n"
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"服务地址，默认 {DEFAULT_BASE_URL}（也可用环境变量 EXAMDATA_BASE_URL）",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help="服务端 EXAMDATA_API_KEY 的值，放进 X-API-Key 头；未启用鉴权时可省略",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="单请求超时秒数")
    parser.add_argument("--json", action="store_true", help="打印完整 JSON 而不是摘要")
    parser.add_argument("--verbose", action="store_true", help="打印实际请求的 URL")

    common = common_options()
    subs = parser.add_subparsers(dest="command")

    subs.add_parser("boards", parents=[common], help="GET /api/v1/boards（能力发现）")

    search = subs.add_parser(
        "search", parents=[common], help="GET /api/v1/search（跨考试局检索）"
    )
    search.add_argument("--keyword", help="题干关键词")
    search.add_argument("--subject", help="科目代码，如 0580；Edexcel 传科目名如 Economics")
    search.add_argument("--board", help="cie / cambridge / ca / edexcel / edx / pearson / ial")
    search.add_argument("--year", type=int, help="年份")
    search.add_argument("--session", help="考季")
    search.add_argument("--paper", help="试卷代码")
    search.add_argument("--marks-min", type=int, help="分值下限")
    search.add_argument("--marks-max", type=int, help="分值上限")
    search.add_argument("--leaves-only", action="store_true", help="只要可独立作答的叶子题")
    search.add_argument("--has-answer", action="store_true", help="只要带官方答案的题")
    search.add_argument("--limit", type=int, default=20, help="返回条数，1..500，默认 20")
    search.add_argument("--offset", type=int, default=0, help="偏移，默认 0")

    paper = subs.add_parser("paper", parents=[common], help="GET /api/v1/paper（统一取卷）")
    paper.add_argument("--subject", required=True, help="科目（CIE 四位数字，Edexcel 科目名）")
    paper.add_argument("--year", required=True, type=int, help="年份")
    paper.add_argument("--season", required=True, help="考季，如 Mar / Jun / Nov")
    paper.add_argument("--board", help="显式指定考试局；不传则按科目形态自动判定")
    paper.add_argument("--paper", help="试卷代码，如 11 / wec11-01")
    paper.add_argument("--question", help="题号（仅 Edexcel question/qa 模式）")
    paper.add_argument("--mode", help="cie: qp/ms/both；edexcel: paper/question/qa")
    paper.add_argument("--no-download", action="store_true", help="只解析清单，不下载文件")
    paper.add_argument(
        "--format", choices=["binary", "json"], default="binary", help="下载形态，默认 binary"
    )
    paper.add_argument("--out", help="保存目录；不给则只打印信息")

    question = subs.add_parser("question", help="GET /api/v1/question/{id}（单题聚合）")
    question.add_argument("--id", type=int, required=True, help="题目 ID")

    demo = subs.add_parser("demo", help="依次跑 boards / search / question / paper 清单")
    demo.add_argument("--subject", default="0580", help="检索与取卷用的科目，默认 0580")
    demo.add_argument("--keyword", default=None, help="检索关键词")
    demo.add_argument("--board", default=None, help="检索用的考试局别名")
    demo.add_argument("--year", type=int, default=2024, help="取卷年份，默认 2024")
    demo.add_argument("--season", default="Jun", help="取卷考季，默认 Jun")
    demo.add_argument("--session", default=None, help="检索用的考季")
    demo.add_argument("--paper", default="11", help="取卷试卷代码，默认 11")
    demo.add_argument("--marks-min", type=int, default=None)
    demo.add_argument("--marks-max", type=int, default=None)
    demo.add_argument("--leaves-only", action="store_true", default=True)
    demo.add_argument("--has-answer", action="store_true")
    demo.add_argument("--limit", type=int, default=3)
    demo.add_argument("--offset", type=int, default=0)
    demo.add_argument("--no-download", action="store_true", default=True, help="（demo 只解析清单）")
    demo.add_argument("--format", default="binary")
    demo.add_argument("--out", default=None)
    demo.add_argument("--question", default=None)
    demo.add_argument("--mode", default=None)
    demo.add_argument("--id", type=int, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.command = args.command or "demo"
    if args.command == "demo":
        # demo 里 paper 步骤走清单模式，避免示例默认触发大文件下载。
        args.no_download = True

    handlers = {
        "boards": cmd_boards,
        "search": cmd_search,
        "paper": cmd_paper,
        "question": cmd_question,
        "demo": cmd_demo,
    }
    if args.command == "question" and args.id is None:
        parser.error("question 需要 --id")

    with Client(args.base_url, args.api_key, args.timeout) as client:
        client.verbose = args.verbose
        if args.verbose:
            print(f"[verbose] HTTP 后端 = {BACKEND}", file=sys.stderr)
        try:
            return handlers[args.command](client, args)
        except ApiError as exc:
            print(f"请求失败: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # 连不上、JSON 解析失败等
            print(f"调用失败: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main())
