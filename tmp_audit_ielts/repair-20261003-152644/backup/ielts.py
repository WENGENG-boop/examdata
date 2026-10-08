"""IELTS 网关（/api/v1/ielts）：把雅思聚合器收进统一 API 服务。

存在的理由：CIE 与 Edexcel 已有 `/api/v1` 网关（`unified.py`），但雅思
（IELTS 剑桥雅思 1–21）的题源不在 examdata 数据库里——它是仓库旁的独立
Node 聚合器（`<repo>/ielts-api/ielts-cli.mjs`，零 npm 依赖），把多个公开
第三方索引合并成统一 JSON。本模块把该聚合器的命令映射成 HTTP 路由，
使同一台服务、同一套 `/api/v1` 前缀下可以同时访问 CIE、Edexcel 与 IELTS。

设计取舍：
- **纯增量**。不触碰既有端点与 `unified.py` 的任何行为；本模块只新增路由。
- 每次请求用 `node ielts-cli.mjs <cmd> …` 起一个短命子进程，并限制并发，
  stdout 的 JSON 原样透传（顶层补 `board: "ielts"` 便于跨局调用方识别）。
  聚合器自身"永不抛异常"：它失败时返回 `ok:false` 对象——这种业务失败与
  正常响应一样是 200，调用方看 `ok` 字段。
- **只有基础设施错误才用 HTTP 错误码**：找不到 node 或聚合器目录 → 503；
  子进程超时 → 504；非零退出或输出不是合法 JSON → 502。错误体沿用本服务
  其它端点的 FastAPI `{"detail": …}` 形状。
- 聚合器目录可用 `EXAMDATA_IELTS_DIR`（或 `IELTS_API_DIR`）覆盖；
  node 可执行文件可用 `EXAMDATA_NODE` 覆盖；全部超时可用
  `EXAMDATA_IELTS_TIMEOUT`（秒）整体覆盖。

启动：
    examdata serve --host 127.0.0.1 --port 8000
    curl http://127.0.0.1:8000/api/v1/ielts/info
    curl http://127.0.0.1:8000/api/v1/ielts/aggregate/20/1
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import weakref
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/ielts", tags=["ielts"])

_SCRIPT_NAME = "ielts-cli.mjs"
_gates: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _gate() -> asyncio.Semaphore:
    # Keep running/queued requests on the same gate without retaining closed
    # event loops used by TestClient or embedding applications.
    loop = asyncio.get_running_loop()
    ref = _gates.get(loop)
    semaphore = ref() if ref else None
    if semaphore is None:
        try:
            capacity = int(os.environ.get("EXAMDATA_IELTS_MAX_CONCURRENT", "4"))
            if not 1 <= capacity <= 64:
                capacity = 4
        except ValueError:
            capacity = 4
        semaphore = asyncio.Semaphore(capacity)
        _gates[loop] = weakref.ref(semaphore)
    return semaphore


async def _run(cmd: str, *args: Any, timeout: float = 120.0) -> dict[str, Any]:
    semaphore = _gate()
    try:
        queue_timeout = float(os.environ.get("EXAMDATA_IELTS_QUEUE_TIMEOUT", "5"))
        if not 0 < queue_timeout <= 60:
            queue_timeout = 5.0
    except ValueError:
        queue_timeout = 5.0
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=queue_timeout)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=503, detail="IELTS 并发已满，请稍后重试") from exc
    try:
        return await _run_process(cmd, *args, timeout=timeout)
    finally:
        semaphore.release()


def _candidate_dirs() -> list[Path]:
    """聚合器目录候选：显式环境变量优先，其次仓库默认布局。"""
    env = os.environ.get("EXAMDATA_IELTS_DIR") or os.environ.get("IELTS_API_DIR")
    if env:
        return [Path(env).expanduser()]
    here = Path(__file__).resolve()
    # 本文件在 <repo>/examdata/src/examdata/api/ 下，parents[4] 即 <repo>。
    return [
        here.parents[4] / "ielts-api",
        here.parents[3] / "ielts-api",
        Path.cwd() / "ielts-api",
    ]


def _find_dir() -> Path | None:
    for directory in _candidate_dirs():
        if (directory / _SCRIPT_NAME).is_file():
            return directory
    return None


def _timeout(default: float) -> float:
    raw = os.environ.get("EXAMDATA_IELTS_TIMEOUT")
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return default


async def _run_process(cmd: str, *args: Any, timeout: float = 120.0) -> dict[str, Any]:
    """起一个短命 node 子进程执行 ielts-cli 命令，返回其 JSON。"""
    directory = _find_dir()
    if directory is None:
        tried = "、".join(str(p) for p in _candidate_dirs())
        raise HTTPException(
            status_code=503,
            detail=f"IELTS 聚合器未找到（缺少 {_SCRIPT_NAME}）；已尝试：{tried}",
        )
    node = os.environ.get("EXAMDATA_NODE") or shutil.which("node")
    if not node:
        raise HTTPException(
            status_code=503, detail="找不到 node 可执行文件（可用 EXAMDATA_NODE 指定）"
        )

    argv = [node, str(directory / _SCRIPT_NAME), cmd, *(str(a) for a in args)]
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(directory),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"无法启动 node：{exc}") from exc

    limit = _timeout(timeout)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=limit)
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        try:
            proc.kill()
            await proc.wait()
        except OSError:
            pass
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise HTTPException(
            status_code=504, detail=f"IELTS 聚合器超时（>{limit:g}s）：{cmd}"
        ) from exc

    if proc.returncode != 0:
        tail = err.decode("utf-8", errors="replace").strip().replace("\n", " ")[:300]
        raise HTTPException(
            status_code=502, detail=f"ielts-cli 退出码 {proc.returncode}：{tail}"
        )
    try:
        data = json.loads(out)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="ielts-cli 输出不是合法 JSON") from exc
    if isinstance(data, dict):
        data.setdefault("board", "ielts")
        return data
    return {"board": "ielts", "ok": True, "data": data}


# --------------------------------------------------------------------------
# 能力发现
# --------------------------------------------------------------------------


@router.get("/info", summary="IELTS 网关能力清单（书目范围、路由、源）")
def ielts_info() -> dict[str, Any]:
    """无参数。调用方据此知道雅思侧能调什么、覆盖到哪。"""
    routes = [
        {"path": "/api/v1/ielts/books/{book}", "does": "单册目录（pteBook：阅读/听力 slug 表）"},
        {"path": "/api/v1/ielts/reading/{book}/{test}?passage=", "does": "阅读题目+答案（passage 1–3，默认 1）"},
        {"path": "/api/v1/ielts/listening/{book}/{test}", "does": "听力题目+答案"},
        {"path": "/api/v1/ielts/aggregate/{book}/{test}", "does": "整卷聚合（阅读+听力+原文+音频+PDF，单册单套的完整视图）"},
        {"path": "/api/v1/ielts/coverage", "does": "全源覆盖自检（较慢）"},
        {"path": "/api/v1/ielts/cam21/reading/{test}", "does": "剑桥21 阅读（160 答案源）"},
        {"path": "/api/v1/ielts/cam21/listening/{test}", "does": "剑桥21 听力（147 答案源）"},
        {"path": "/api/v1/ielts/cam21/coverage", "does": "剑桥21 自检"},
        {"path": "/api/v1/ielts/ito/script/{book}/{test}", "does": "听力原文（ieltstrainingonline 交叉源，剑10–21）"},
        {"path": "/api/v1/ielts/ito/coverage", "does": "交叉源自检（较慢）"},
        {"path": "/api/v1/ielts/listening-script/{book}", "does": "整册听力原文（4 套）"},
        {"path": "/api/v1/ielts/listening-audio/{book}/{test}?part=", "does": "听力音频直链（part 1–4，默认 1）"},
        {"path": "/api/v1/ielts/pdf/{book}", "does": "整本 PDF 下载信息（Git LFS，剑1–20）"},
        {"path": "/api/v1/ielts/lfs-coverage", "does": "LFS 整本 PDF 覆盖自检"},
        {"path": "/api/v1/ielts/iprog/listening/{book}/{test}", "does": "剑3 听力答案兜底源（ieltsprogress.com）"},
        {"path": "/api/v1/ielts/iprog/coverage", "does": "剑3 听力答案自检"},
        {"path": "/api/v1/ielts/pdf21", "does": "剑桥21 整本 PDF（全网红唯一公开源）"},
        {"path": "/api/v1/ielts/zhan/reading/{book}/{test}?passage=", "does": "剑20/21 阅读逐句中英对照（passage 1–3，默认 1）"},
        {"path": "/api/v1/ielts/zhan/coverage", "does": "剑20/21 精读自检"},
    ]
    return {
        "board": "ielts",
        "name": "IELTS（剑桥雅思）",
        "aggregator": "ielts-api/ielts-cli.mjs（Node ≥18，零 npm 依赖）",
        "books": {"range": "1–21", "tests_per_book": 4, "note": "book/test 均为整数，越界时返回 ok:false 而不是 HTTP 错误"},
        "routes": routes,
        "sources": [
            "practicepteonline.com（阅读/听力题库，剑1–21）",
            "userheyy/ielts-reader（听力原文逐句+时间戳，剑1–19）",
            "ieltstrainingonline.com（听力原文交叉源，剑10–21）",
            "maqsudjon-cell/cambridge-21（剑21 阅读/听力/音频/原文）",
            "Git LFS 整本 PDF（剑1–20）+ aqinaq/agylshyn（剑21 整本 PDF）",
            "ieltsprogress.com（剑3 听力 T2–T4 答案兜底）",
            "top.zhan.com（剑20/21 阅读逐句中英对照）",
        ],
        "env": {
            "EXAMDATA_IELTS_DIR / IELTS_API_DIR": "聚合器目录（默认 <repo>/ielts-api）",
            "EXAMDATA_NODE": "node 可执行文件（默认从 PATH 找）",
            "EXAMDATA_IELTS_TIMEOUT": "所有 IELTS 路由的子进程超时（秒）",
        },
        "notes": [
            "聚合器\"永不抛异常\"：业务失败是 HTTP 200 + ok:false；只有基础设施错误（node 缺失 503 / 超时 504 / 解析失败 502）才用 HTTP 错误码。",
            "本网关不读 examdata 数据库，纯代理；CIE/Edexcel 的既有端点行为不受影响。",
        ],
    }


# --------------------------------------------------------------------------
# 单册 / 单套
# --------------------------------------------------------------------------


@router.get("/books/{book}", summary="单册目录（pteBook）")
async def ielts_book(book: int) -> dict[str, Any]:
    return await _run("pte-book", book, timeout=90)


@router.get("/reading/{book}/{test}", summary="阅读题目+答案")
async def ielts_reading(
    book: int, test: int, passage: int = Query(1, description="Passage 1–3，默认 1")
) -> dict[str, Any]:
    return await _run("reading", book, test, passage, timeout=90)


@router.get("/listening/{book}/{test}", summary="听力题目+答案")
async def ielts_listening(book: int, test: int) -> dict[str, Any]:
    return await _run("listening-qa", book, test, timeout=180)


@router.get(
    "/aggregate/{book}/{test}",
    summary="整卷聚合（阅读+听力+原文+音频+PDF）",
    description=(
        "单册单套的完整视图，等价于 CLI `node ielts-cli.mjs aggregate <book> <test>`。"
        "返回 `parts.reading` / `parts.listening_qa` / `parts.listening_script` / "
        "`parts.reading_enriched` / `parts.pdf` 等分片，`score` 给出完整度，"
        "`warnings` 列出缺口。注意：与 CLI 相同，本响应没有顶层 `ok` 字段。"
    ),
)
async def ielts_aggregate(book: int, test: int) -> dict[str, Any]:
    return await _run("aggregate", book, test, timeout=300)


@router.get("/coverage", summary="全源覆盖自检（较慢，可能数分钟）")
async def ielts_coverage() -> dict[str, Any]:
    return await _run("coverage", timeout=600)


# --------------------------------------------------------------------------
# 剑桥21 专属
# --------------------------------------------------------------------------


@router.get("/cam21/reading/{test}", summary="剑桥21 阅读")
async def ielts_cam21_reading(test: int) -> dict[str, Any]:
    return await _run("cam21-reading", test, timeout=90)


@router.get("/cam21/listening/{test}", summary="剑桥21 听力")
async def ielts_cam21_listening(test: int) -> dict[str, Any]:
    return await _run("cam21-listening", test, timeout=90)


@router.get("/cam21/coverage", summary="剑桥21 自检")
async def ielts_cam21_coverage() -> dict[str, Any]:
    return await _run("cam21-coverage", timeout=300)


# --------------------------------------------------------------------------
# 听力原文 / 音频
# --------------------------------------------------------------------------


@router.get("/ito/script/{book}/{test}", summary="听力原文（ieltstrainingonline 交叉源）")
async def ielts_ito_script(book: int, test: int) -> dict[str, Any]:
    return await _run("ito-script", book, test, timeout=120)


@router.get("/ito/coverage", summary="交叉源自检（较慢）")
async def ielts_ito_coverage() -> dict[str, Any]:
    return await _run("ito-coverage", timeout=300)


@router.get("/listening-script/{book}", summary="整册听力原文（4 套）")
async def ielts_listening_script(book: int) -> dict[str, Any]:
    return await _run("listening-script", book, timeout=300)


@router.get("/listening-audio/{book}/{test}", summary="听力音频直链")
async def ielts_listening_audio(
    book: int, test: int, part: int = Query(1, description="Part 1–4，默认 1")
) -> dict[str, Any]:
    return await _run("listening-audio", book, test, part, timeout=90)


# --------------------------------------------------------------------------
# 整本 PDF
# --------------------------------------------------------------------------


@router.get("/pdf/{book}", summary="PDF 下载信息（Git LFS，剑1–19整本、剑20分册）")
async def ielts_pdf(book: int) -> dict[str, Any]:
    return await _run("pdf", book, timeout=600)


@router.get("/lfs-coverage", summary="LFS 整本 PDF 覆盖自检")
async def ielts_lfs_coverage() -> dict[str, Any]:
    return await _run("lfs-coverage", timeout=300)


@router.get("/pdf21", summary="剑桥21 整本 PDF（社区镜像）")
async def ielts_pdf21() -> dict[str, Any]:
    return await _run("pdf21", timeout=300)


# --------------------------------------------------------------------------
# 剑3 听力答案兜底 / 剑20–21 精读
# --------------------------------------------------------------------------


@router.get("/iprog/listening/{book}/{test}", summary="剑3 听力答案兜底（ieltsprogress.com）")
async def ielts_iprog_listening(book: int, test: int) -> dict[str, Any]:
    return await _run("iprog-listening", book, test, timeout=90)


@router.get("/iprog/coverage", summary="剑3 听力答案自检")
async def ielts_iprog_coverage() -> dict[str, Any]:
    return await _run("iprog-coverage", timeout=90)


@router.get("/zhan/reading/{book}/{test}", summary="剑20/21 阅读逐句中英对照")
async def ielts_zhan_reading(
    book: int, test: int, passage: int = Query(1, description="Passage 1–3，默认 1")
) -> dict[str, Any]:
    return await _run("zhan-reading", book, test, passage, timeout=120)


@router.get("/zhan/coverage", summary="剑20/21 精读自检")
async def ielts_zhan_coverage() -> dict[str, Any]:
    return await _run("zhan-coverage", timeout=180)
