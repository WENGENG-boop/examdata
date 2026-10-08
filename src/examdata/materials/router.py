"""考试发放资料接口（/api/v1/materials）。

四个端点：

- `GET /materials`：列出资料条目，可按 board / subject / kind /
  candidate_facing 过滤；
- `GET /materials/{material_id}`：单条完整记录（含 evidence 原文）；
- `GET /materials/{material_id}/content`：取回静态资料原件（二进制或
  base64 JSON），`version` 按 label 或 0 起索引区分版本，换版不混用；
- `GET /materials/cie/in-paper`：CIE 镜像动态定位（insert / 保密须知），
  `download=false` 只列清单，`download=true` 取回唯一命中的文件。

错误语义沿用仓库约定：403 robots/受限、404 未找到、409 多命中、422 参数或
无可取版本、502 上游故障。上游一律经仓库 Fetcher（robots、限速）。

board 别名归一复用统一网关的别名表，但**延迟导入**：`examdata.api.__init__`
会执行 `from .app import app`，模块级导入会让"先导入 materials（如独立
测试）"触发 materials -> api.__init__ -> app -> materials 的导入环。
"""

from __future__ import annotations

import base64
import copy
import hashlib
from typing import Any, Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..core.fetch import Fetcher
from ..paperqa.api import content_disposition
from ..paperqa.errors import PaperQAError
from ..paperqa.models import Document

from .catalog import (
    content_endpoint,
    get_item,
    item_summary,
    list_items,
    load_catalog,
    version_record,
)
from .fetch import (
    CIE_ORIGIN,
    CIE_RENUM_URL,
    download_cie_document,
    fetch_material,
    resolve_cie_documents,
    select_version,
    version_filename,
)

# 本模块响应 schema 版本：字段增删（如新增过滤维度/响应头）由这个号标识。
SCHEMA_VERSION = "1"

router = APIRouter(prefix="/api/v1", tags=["materials"])


def get_fetcher() -> Iterator[Fetcher]:
    """每请求一个抓取器，请求结束后释放连接（测试可 dependency_overrides）。"""
    with Fetcher() as fetcher:
        yield fetcher


def _normalize_board(value: Optional[str]) -> Optional[str]:
    """board 别名归一（复用统一网关的唯一别名表）。"""
    if value is None:
        return None
    from ..api.unified import normalize_board

    return normalize_board(value)


def _document_record(document: Document) -> dict[str, Any]:
    return {
        "name": document.name,
        "url": document.url,
        "role": document.role,
        "paper": document.paper,
        "media_type": document.media_type,
    }


@router.get("/materials")
def list_materials(
    board: Optional[str] = Query(
        None, description="考试局：cie/cambridge/ca 或 edexcel/edx/pearson/ial"
    ),
    subject: Optional[str] = Query(
        None, description="科目代码（CIE 四位数字；Edexcel 科目 slug，如 ial18-chemistry）"
    ),
    kind: Optional[str] = Query(
        None, description="资料类别，如 formula-and-statistical-tables / insert"
    ),
    candidate_facing: Optional[bool] = Query(
        None, description="是否面向考生（false 为考务/教师文件）"
    ),
) -> dict[str, Any]:
    """列出资料条目（不含 evidence 正文），可按需过滤。"""
    canonical = _normalize_board(board)
    items = [
        item_summary(item) for item in list_items(canonical, subject, kind, candidate_facing)
    ]
    catalog = load_catalog()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": catalog.get("generated_at"),
        "board": canonical,
        "subject": subject,
        "count": len(items),
        "items": items,
        "dynamic_endpoints": {"cie_in_paper": "/api/v1/materials/cie/in-paper"},
    }


@router.get("/materials/cie/in-paper")
def get_cie_in_paper(
    subject: str = Query(..., description="四位 CIE 科目代码，如 0500"),
    year: int = Query(..., description="考季年份，如 2024"),
    season: str = Query(..., description="考季：Mar/June/Nov（大小写不敏感）"),
    paper: Optional[str] = Query(None, description="组件号，如 11；不传则返回命中集"),
    role: str = Query("in", description="角色：in（insert）/ ir / ci（保密须知）"),
    download: bool = Query(False, description="false 只列清单；true 取回文件（唯一命中时）"),
    format: str = Query("binary", pattern="^(binary|json)$"),
    fetcher: Fetcher = Depends(get_fetcher),
) -> Any:
    """按 subject/year/season(/paper/role) 动态定位 CIE 发放资料。

    `download=false`（默认）返回清单：`documents` 列出命中文件
    （name/url/role/paper），`files` 恒为空——与 paperqa 的 resolve 语义
    一致，只回答"对应哪些文件"，不下载。`download=true` 下载文件：命中
    多个（未给 paper）时 409 并列出候选组件；成功时按 `format` 返回二进制
    （带 Content-Disposition 与 X-Material-Sha256）或 base64 JSON。
    """
    role_token = str(role).strip().lower()
    try:
        documents = resolve_cie_documents(fetcher, subject, year, season, paper, role_token)
    except PaperQAError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    request_repr = {
        "subject": str(subject).strip(),
        "year": year,
        "season": season,
        "paper": paper,
        "role": role_token,
    }
    if not download:
        return {
            "schema_version": SCHEMA_VERSION,
            "request": request_repr,
            "counts": {"documents": len(documents), "files": 0, "bytes": 0},
            "documents": [_document_record(document) for document in documents],
            "files": [],
            "source": {"origin": CIE_ORIGIN, "endpoint": CIE_RENUM_URL},
        }
    if len(documents) > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "命中多个发放资料文件，请用 paper 参数指定组件",
                "papers": sorted({document.paper for document in documents}),
                "documents": [document.name for document in documents],
            },
        )
    document = documents[0]
    try:
        data = download_cie_document(fetcher, document)
    except PaperQAError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    digest = hashlib.sha256(data).hexdigest()
    if format == "json":
        return {
            "schema_version": SCHEMA_VERSION,
            "request": request_repr,
            "document": _document_record(document),
            "sha256": digest,
            "size": len(data),
            "media_type": "application/pdf",
            "data_base64": base64.b64encode(data).decode("ascii"),
        }
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition(document.name),
            "Content-Length": str(len(data)),
            "X-Material-Role": document.role,
            "X-Material-Paper": document.paper,
            "X-Material-Sha256": digest,
        },
    )


@router.get("/materials/{material_id}")
def get_material(material_id: str) -> dict[str, Any]:
    """单条资料的完整记录：原样返回目录条目，附 schema 版本与派生入口。"""
    item = get_item(material_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"未知资料: {material_id}")
    payload = copy.deepcopy(item)
    payload["schema_version"] = SCHEMA_VERSION
    payload["content_endpoint"] = content_endpoint(item)
    return payload


@router.get("/materials/{material_id}/content")
def get_material_content(
    material_id: str,
    version: Optional[str] = Query(
        None, description="版本 label（全等）或 0 起索引；缺省取第一项"
    ),
    format: str = Query(
        "binary", pattern="^(binary|json)$", description="binary 返回原件；json 返回 base64"
    ),
    fetcher: Fetcher = Depends(get_fetcher),
) -> Any:
    """取回静态资料原件；没有独立文件版本的条目 422 并给动态入口。

    二进制出口的头部刻意只放 ASCII：`Content-Disposition` 用 URL 派生的
    文件名（RFC 6266 消毒），实测 sha256 与快照对照放进 `X-Material-*`；
    中文版本 label 不进头部（Starlette 用 latin-1 编码头部，非 ASCII 会 500）。
    """
    item = get_item(material_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"未知资料: {material_id}")
    if not item.get("versions"):
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"资料 {material_id} 没有可独立取回的版本",
                "access": item.get("access"),
                "dynamic_endpoint": (item.get("dynamic") or {}).get("endpoint"),
            },
        )
    try:
        selected = select_version(item, version)
        fetched = fetch_material(fetcher, selected)
    except PaperQAError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    filename = version_filename(selected)
    if format == "json":
        return {
            "schema_version": SCHEMA_VERSION,
            "material_id": material_id,
            "version": version_record(selected),
            "sha256": fetched.sha256,
            "sha256_match": fetched.sha256_match,
            "size": len(fetched.data),
            "media_type": "application/pdf",
            "data_base64": base64.b64encode(fetched.data).decode("ascii"),
        }
    return Response(
        content=fetched.data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition(filename),
            "Content-Length": str(len(fetched.data)),
            "X-Material-Id": material_id,
            "X-Material-Sha256": fetched.sha256,
            "X-Material-Sha256-Match": "true" if fetched.sha256_match else "false",
        },
    )
