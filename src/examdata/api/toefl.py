"""TOEFL 网关（/api/v1/toefl）：把托福聚合器收进统一 API 服务。

存在的理由：CIE 与 Edexcel 已有 `/api/v1` 网关（`unified.py`），雅思有
`/api/v1/ielts` 网关代理仓库旁的 Node 聚合器；托福（TOEFL TPO 与公开第三方
索引）同样不在 examdata 数据库里——它是仓库旁的独立 Node 聚合器
（`<repo>/toefl-api/toefl-cli.mjs`，零 npm 依赖），把考满分（toefl.kmf.com）
索引、FindSimilarTPO、ddy-ddy 等公开源合并成统一 JSON。本模块把该聚合器的
命令映射成 HTTP 路由，使同一台服务、同一套 `/api/v1` 前缀下可以同时访问
CIE、Edexcel、IELTS 与 TOEFL。

设计取舍：
- **纯增量**。不触碰既有端点与 `unified.py`、`ielts.py` 的任何行为；
  本模块只新增路由。
- 每次请求用 `node toefl-cli.mjs <cmd> …` 起一个短命子进程，并限制并发，
  stdout 的 JSON 原样透传（顶层补 `board: "toefl"` 便于跨局调用方识别）。
  聚合器通常以 `ok:false` 表达业务失败：这类失败与正常响应一样是 200，
  调用方看 `ok` 字段；基础设施故障才由本网关映射为 503/504/502。
- **只有基础设施错误才用 HTTP 错误码**：找不到 node 或聚合器目录 → 503；
  子进程超时 → 504；非零退出或输出不是合法 JSON → 502。错误体沿用本服务
  其它端点的 FastAPI `{"detail": …}` 形状。
- 聚合器目录可用 `EXAMDATA_TOEFL_DIR`（或 `TOEFL_API_DIR`）覆盖；
  node 可执行文件可用 `EXAMDATA_NODE` 覆盖；全部超时可用
  `EXAMDATA_TOEFL_TIMEOUT`（秒）整体覆盖。

启动：
    examdata serve --host 127.0.0.1 --port 8000
    curl http://127.0.0.1:8000/api/v1/toefl/info
    curl "http://127.0.0.1:8000/api/v1/toefl/sets?era=tpo-51-54&page-size=2"
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

router = APIRouter(prefix="/api/v1/toefl", tags=["toefl"])

_SCRIPT_NAME = "toefl-cli.mjs"
_gates: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _gate() -> asyncio.Semaphore:
    # Keep running/queued requests on the same gate without retaining closed
    # event loops used by TestClient or embedding applications.
    loop = asyncio.get_running_loop()
    ref = _gates.get(loop)
    semaphore = ref() if ref else None
    if semaphore is None:
        try:
            capacity = int(os.environ.get("EXAMDATA_TOEFL_MAX_CONCURRENT", "4"))
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
        queue_timeout = float(os.environ.get("EXAMDATA_TOEFL_QUEUE_TIMEOUT", "5"))
        if not 0 < queue_timeout <= 60:
            queue_timeout = 5.0
    except ValueError:
        queue_timeout = 5.0
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=queue_timeout)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=503, detail="TOEFL 并发已满，请稍后重试") from exc
    try:
        return await _run_process(cmd, *args, timeout=timeout)
    finally:
        semaphore.release()


def _candidate_dirs() -> list[Path]:
    """聚合器目录候选：显式环境变量优先，其次仓库默认布局。"""
    env = os.environ.get("EXAMDATA_TOEFL_DIR") or os.environ.get("TOEFL_API_DIR")
    if env:
        return [Path(env).expanduser()]
    here = Path(__file__).resolve()
    # 本文件在 <repo>/examdata/src/examdata/api/ 下，parents[4] 即 <repo>。
    return [
        here.parents[4] / "toefl-api",
        here.parents[3] / "toefl-api",
        Path.cwd() / "toefl-api",
    ]


def _find_dir() -> Path | None:
    for directory in _candidate_dirs():
        if (directory / _SCRIPT_NAME).is_file():
            return directory
    return None


def _timeout(default: float) -> float:
    raw = os.environ.get("EXAMDATA_TOEFL_TIMEOUT")
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return default


async def _run_process(cmd: str, *args: Any, timeout: float = 120.0) -> dict[str, Any]:
    """起一个短命 node 子进程执行 toefl-cli 命令，返回其 JSON。"""
    directory = _find_dir()
    if directory is None:
        tried = "、".join(str(p) for p in _candidate_dirs())
        raise HTTPException(
            status_code=503,
            detail=f"TOEFL 聚合器未找到（缺少 {_SCRIPT_NAME}）；已尝试：{tried}",
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
            status_code=504, detail=f"TOEFL 聚合器超时（>{limit:g}s）：{cmd}"
        ) from exc

    if proc.returncode != 0:
        tail = err.decode("utf-8", errors="replace").strip().replace("\n", " ")[:300]
        raise HTTPException(
            status_code=502, detail=f"toefl-cli 退出码 {proc.returncode}：{tail}"
        )
    try:
        data = json.loads(out)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="toefl-cli 输出不是合法 JSON") from exc
    if isinstance(data, dict):
        data.setdefault("board", "toefl")
        return data
    return {"board": "toefl", "ok": True, "data": data}


# --------------------------------------------------------------------------
# 能力发现
# --------------------------------------------------------------------------


@router.get("/info", summary="TOEFL 网关能力清单（范围、路由、源）")
def toefl_info() -> dict[str, Any]:
    """无参数。静态清单（不走子进程）；实时覆盖数字见 /coverage。"""
    routes = [
        {"path": "/api/v1/toefl/info", "does": "本清单"},
        {"path": "/api/v1/toefl/coverage", "does": "源覆盖自检（离线；逐 TPO 计数、缺口、重复）"},
        {"path": "/api/v1/toefl/sets?tpo=&era=&section=&tpo-min=&tpo-max=&page=&page-size=", "does": "按编号分区与考试形式筛选套次（元数据）"},
        {"path": "/api/v1/toefl/get?set=tpo-N&section=&file=&refresh=", "does": "单套元数据视图；file 时返回该原文文件（网络+缓存）"},
        {"path": "/api/v1/toefl/questions?set=tpo-N&section=reading|listening&item=&limit=&refresh=&url=", "does": "抓取该套/该 Section 的真实题目（题干/选项/答案，kmf 源）"},
        {"path": "/api/v1/toefl/detail?url=&refresh=", "does": "单条 kmf 详情页内容（read/listen 逐题；speak 题干+音频；write 材料/题干文本；TPO 与机经通用）"},
        {"path": "/api/v1/toefl/search?q=&limit=&sources=", "does": "关键词检索（ddy 全文/FindSimilar 缓存/kmf 索引/kmf 缓存页）"},
        {"path": "/api/v1/toefl/jj?section=&batch=&free=&locked=&list=&page=&page-size=&url=&refresh=", "does": "机经真题板块（/jj/order/27..30；索引 325 条，免费 213/锁定 112；url 时抓详情）"},
    ]
    return {
        "board": "toefl",
        "name": "TOEFL（托福 TPO / 公开第三方索引）",
        "schema": "toefl.v1",
        "aggregator": "toefl-api/toefl-cli.mjs（Node ≥18，零 npm 依赖）",
        "exam_family": "toefl",
        "tpo_range": "1–54（可用套次以 /sets 与 /coverage 的实时统计为准）",
        "exam_forms": {
            "sections": ["reading", "listening", "speaking", "writing"],
            "note": "TPO 无官方逐年发布日；时间维度用编号分区（eras）表达；questions 支持 reading/listening 逐题内容（kmf 源有题有答案）；speaking/writing 索引见 kmf 源，内容用 detail 抓取（speak=题干+音频；write=材料/题干文本）。",
        },
        "eras": [
            {"id": "tpo-01-10", "tpo_min": 1, "tpo_max": 10, "note": "编号分区，非官方年份"},
            {"id": "tpo-11-20", "tpo_min": 11, "tpo_max": 20, "note": "编号分区，非官方年份"},
            {"id": "tpo-21-30", "tpo_min": 21, "tpo_max": 30, "note": "编号分区，非官方年份"},
            {"id": "tpo-31-40", "tpo_min": 31, "tpo_max": 40, "note": "编号分区，非官方年份"},
            {"id": "tpo-41-50", "tpo_min": 41, "tpo_max": 50, "note": "编号分区，非官方年份"},
            {"id": "tpo-51-54", "tpo_min": 51, "tpo_max": 54, "note": "编号分区，非官方年份"},
        ],
        "format_revision_reference": {
            "note": "格式改版参考信息；不支持按 pre/post-2023-07 筛选或映射套次（无逐套改版身份数据）。",
            "revisions": [
                {"id": "pre-2023-07", "label": "旧版 TOEFL iBT（阅读/听力/口语/写作 4 科）"},
                {"id": "post-2023-07", "label": "2023-07 改版后（独立写作→学术讨论写作；TPO 编号仍连续）"},
            ],
        },
        "routes": routes,
        "sources": [
            {"id": "kmf", "name": "考满分 toefl.kmf.com", "role": "索引（read/listen/speak/write）+ 详情内容（read/listen 逐题题干/选项/答案；speak 题干+音频；write 材料/题干文本）"},
            {"id": "kmf-jj", "name": "考满分机经真题板块 /jj/order/27..30", "role": "索引 325 条（read 50/listen 125/speak 100/write 50；免费 213/锁定 112）；免费条目详情并入 kmf 缓存供检索"},
            {"id": "find-similar-tpo", "name": "SAOHPRWHG/FindSimilarTPO（GitHub）", "role": "TPO 阅读原文与听力原文，无题目答案"},
            {"id": "ddy-ddy", "name": "ddy-ddy/TOEFL-TPO（GitHub）", "role": "TPO 30–54 结构化阅读（标题+段落）"},
        ],
        "env": {
            "EXAMDATA_TOEFL_DIR / TOEFL_API_DIR": "聚合器目录（默认 <repo>/toefl-api）",
            "EXAMDATA_NODE": "node 可执行文件（默认从 PATH 找）",
            "EXAMDATA_TOEFL_TIMEOUT": "所有 TOEFL 路由的子进程超时（秒）",
        },
        "notes": [
            "通常业务失败是 HTTP 200 + ok:false（含未知 section、超出收录范围的 tpo-N）；基础设施错误用 HTTP 错误码（node 缺失 503 / 并发排队超时 503 / 子进程超时 504 / 非零退出或输出非 JSON 502）。",
            "题目/答案来自第三方公开整理（考满分），仅供学习检索；受版权保护的原文不提交进 git，按需实时抓取并缓存到 .data/，请遵守源站 robots 与限速。",
            "本网关不读 examdata 数据库，纯代理；CIE/Edexcel/IELTS 的既有端点行为不受影响。",
        ],
    }


# --------------------------------------------------------------------------
# 索引与套次
# --------------------------------------------------------------------------


@router.get("/coverage", summary="源覆盖自检（离线；逐 TPO 计数）")
async def toefl_coverage() -> dict[str, Any]:
    return await _run("coverage", timeout=300)


@router.get("/sets", summary="按编号分区与考试形式筛选套次（元数据）")
async def toefl_sets(
    tpo: int | None = Query(None, description="单个 TPO 编号（1–54）"),
    era: str | None = Query(None, description="编号分区（如 tpo-51-54；见 /info.eras）"),
    section: str | None = Query(None, description="只返回该 Section（reading/listening/speaking/writing）"),
    tpo_min: int | None = Query(None, alias="tpo-min", description="编号下限"),
    tpo_max: int | None = Query(None, alias="tpo-max", description="编号上限"),
    page: int = Query(1, description="页码（1–1000）"),
    page_size: int = Query(20, alias="page-size", description="每页条数（1–100）"),
) -> dict[str, Any]:
    args: list[Any] = []
    for key, value in (("tpo", tpo), ("era", era), ("section", section), ("tpo-min", tpo_min), ("tpo-max", tpo_max)):
        if value is not None:
            args.append(f"--{key}={value}")
    args.append(f"--page={page}")
    args.append(f"--page-size={page_size}")
    return await _run("sets", *args, timeout=60)


# --------------------------------------------------------------------------
# 单套 / 逐题
# --------------------------------------------------------------------------


@router.get("/get", summary="单套元数据视图（或原文文件）")
async def toefl_get(
    set_id: str = Query(..., alias="set", description="套次 ID（tpo-N，例：tpo-30）"),
    section: str | None = Query(None, description="只返回该 Section（reading/listening/speaking/writing）"),
    file: str | None = Query(None, description="FindSimilarTPO 原文文件名（如 1-1.txt）；返回该文件解析结果"),
    refresh: int = Query(0, description="file 时强制重抓（1=是；默认读缓存）"),
) -> dict[str, Any]:
    args: list[Any] = [f"--set={set_id}"]
    if section is not None:
        args.append(f"--section={section}")
    if file is not None:
        args.append(f"--file={file}")
        if refresh:
            args.append("--refresh=1")
    return await _run("get", *args, timeout=120)


@router.get("/questions", summary="逐题内容（题干/选项/答案；kmf 源）")
async def toefl_questions(
    set_id: str = Query(..., alias="set", description="套次 ID（tpo-N）"),
    section: str = Query(..., description="reading 或 listening（speaking/writing 内容请用 /detail）"),
    item: int = Query(1, description="Passage/Set 序号（从 1 起）"),
    limit: int = Query(0, description="最多抓取题目数（0=全部；调试时可设小）"),
    refresh: int = Query(0, description="强制重抓、忽略页面缓存（1=是）"),
    url: str | None = Query(None, description="直接指定 kmf 题目页 URL（覆盖索引查找；高级用法）"),
) -> dict[str, Any]:
    args: list[Any] = [f"--set={set_id}", f"--section={section}", f"--item={item}"]
    if limit:
        args.append(f"--limit={limit}")
    if refresh:
        args.append("--refresh=1")
    if url:
        args.append(f"--url={url}")
    return await _run("questions", *args, timeout=240)


# --------------------------------------------------------------------------
# 详情页（任意 kmf 详情：read/listen 逐题；speak/write 整页内容）
# --------------------------------------------------------------------------


@router.get("/detail", summary="单条 kmf 详情页内容（TPO 与机经通用）")
async def toefl_detail(
    url: str = Query(..., description="kmf 详情页 URL（/detail/{read|listen|speak|write}/{hash}.html）"),
    refresh: int = Query(0, description="强制重抓、忽略页面缓存（1=是）"),
) -> dict[str, Any]:
    args: list[Any] = [f"--url={url}"]
    if refresh:
        args.append("--refresh=1")
    return await _run("detail", *args, timeout=240)


# --------------------------------------------------------------------------
# 检索
# --------------------------------------------------------------------------


@router.get("/search", summary="关键词检索（跨源）")
async def toefl_search(
    q: str = Query(..., description="关键词/短语（大小写不敏感）"),
    limit: int = Query(20, description="最多返回命中数（1–200）"),
    sources: str | None = Query(None, description="逗号分隔的源子集（ddy-ddy,find-similar-tpo,kmf-index,kmf-cache）"),
) -> dict[str, Any]:
    args: list[Any] = [f"--q={q}", f"--limit={limit}"]
    if sources is not None:
        args.append(f"--sources={sources}")
    return await _run("search", *args, timeout=300)


# --------------------------------------------------------------------------
# 机经真题板块（jj）
# --------------------------------------------------------------------------


@router.get("/jj", summary="机经真题板块（索引与详情）")
async def toefl_jj(
    section: str | None = Query(None, description="read/listen/speak/write（可空=汇总）"),
    batch: int | None = Query(None, description="机经期数 1–25（25 最新）"),
    free: int = Query(0, description="只看免费条目（1=是）"),
    locked: int = Query(0, description="只看锁定条目（1=是）"),
    list_all: int = Query(0, alias="list", description="列出条目（1=是）"),
    page: int = Query(1, description="页码（1–1000）"),
    page_size: int = Query(50, alias="page-size", description="每页条数（1–200）"),
    url: str | None = Query(None, description="直接抓取某条详情页（read/listen 全题；speak/write 整页文本）"),
    refresh: int = Query(0, description="url 时强制重抓（1=是）"),
) -> dict[str, Any]:
    args: list[Any] = []
    if url:
        args.append(f"--url={url}")
        if refresh:
            args.append("--refresh=1")
        return await _run("jj", *args, timeout=240)
    if section is not None:
        args.append(f"--section={section}")
    if batch is not None:
        args.append(f"--batch={batch}")
    if free:
        args.append("--free=1")
    if locked:
        args.append("--locked=1")
    if list_all:
        args.append("--list=1")
    args.append(f"--page={page}")
    args.append(f"--page-size={page_size}")
    return await _run("jj", *args, timeout=60)
