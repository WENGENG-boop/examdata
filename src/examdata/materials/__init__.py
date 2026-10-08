"""考试发放资料：目录（catalog）、取回（fetch）与 `/api/v1` 路由。

- `catalog`：`data/catalog.json` 的读取与查询（逐科调研结论的机器可读形态）；
- `fetch`：静态资料（MF19、Edexcel 公式册等）与 CIE 动态资料（镜像
  in / ir / ci 角色）的实时取回，统一经仓库 Fetcher 与 PDF 五重校验；
- `router`：`/api/v1/materials*`。
"""

from __future__ import annotations

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
    MATERIAL_ROLES,
    FetchedStatic,
    download_cie_document,
    fetch_material,
    resolve_cie_documents,
    select_version,
    version_filename,
)
from .router import get_fetcher, router

__all__ = [
    "CIE_ORIGIN",
    "MATERIAL_ROLES",
    "FetchedStatic",
    "content_endpoint",
    "download_cie_document",
    "fetch_material",
    "get_fetcher",
    "get_item",
    "item_summary",
    "list_items",
    "load_catalog",
    "resolve_cie_documents",
    "router",
    "select_version",
    "version_filename",
    "version_record",
]
