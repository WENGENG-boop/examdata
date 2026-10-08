"""考试发放资料目录（catalog）的读取与查询。

`data/catalog.json` 是本模块唯一的数据来源。字段语义：

- `subjects` / `subjects_kind`：资料的适用范围及清单完备性——
  `applicable`（该科适用，已验证）、`examples`（实测样例，非完整清单）、
  `dynamic`（按试卷变化）、`all`（不限定科目）。CIE 科目用四位 syllabus
  代码；Edexcel 用仓库科目 slug（如 `ial18-chemistry`，与
  `.data/edexcel_papers/catalog/` 的命名一致）。
- `access`：`public` = 独立文件可公开下载；`in-paper` = 印在试卷内、随试卷
  取回；`dynamic` = 需按试卷动态定位后实时取回。
- `versions[]`：每个可独立取回的文件版本（URL / sha256 / 字节数 / 页数均为
  实测快照）；`evidence[]`：结论依据（官方文章、清单、实测下载记录）。
- `dynamic`：动态取回的入口与参数（当前仅 CIE 镜像的 in/ir/ci 角色）。

运行时只读文件并按进程缓存，不联网、不查库。
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "1"

_PACKAGE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = _PACKAGE_DIR / "data" / "catalog.json"

_lock = threading.Lock()
_cache: Optional[dict[str, Any]] = None


def load_catalog() -> dict[str, Any]:
    """读取整个目录（进程内缓存）。文件缺失说明部署不完整。"""
    global _cache
    with _lock:
        if _cache is None:
            _cache = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return _cache


def list_items(
    board: Optional[str] = None,
    subject: Optional[str] = None,
    kind: Optional[str] = None,
    candidate_facing: Optional[bool] = None,
) -> list[dict[str, Any]]:
    """按条件过滤资料条目。`subject` 与 `subjects` 全等匹配。"""
    items = list(load_catalog().get("items", []))
    if board is not None:
        items = [item for item in items if item.get("board") == board]
    if subject is not None:
        wanted = str(subject).strip()
        items = [item for item in items if wanted in (item.get("subjects") or [])]
    if kind is not None:
        items = [item for item in items if item.get("kind") == kind]
    if candidate_facing is not None:
        items = [item for item in items if bool(item.get("candidate_facing")) == candidate_facing]
    return items


def get_item(material_id: str) -> Optional[dict[str, Any]]:
    """按 id 取一条资料；不存在返回 None。"""
    for item in load_catalog().get("items", []):
        if item.get("id") == material_id:
            return item
    return None


def version_record(version: dict[str, Any]) -> dict[str, Any]:
    """版本摘要（清单用；detail 会原样返回完整版本记录）。"""
    keys = ("label", "url", "sha256", "bytes", "pages", "verified_at")
    return {key: version.get(key) for key in keys if key in version}


def item_summary(item: dict[str, Any]) -> dict[str, Any]:
    """清单端点用的条目投影：不含 evidence 正文，带可调用的相对 URL。"""
    versions = item.get("versions") or []
    summary: dict[str, Any] = {
        "id": item["id"],
        "board": item["board"],
        "title": item["title"],
        "title_zh": item.get("title_zh"),
        "kind": item["kind"],
        "candidate_facing": bool(item.get("candidate_facing")),
        "delivery": item.get("delivery"),
        "access": item.get("access"),
        "subjects": list(item.get("subjects") or []),
        "subjects_kind": item.get("subjects_kind"),
        "applies_to": item.get("applies_to"),
        "versions": [version_record(version) for version in versions],
        "evidence_count": len(item.get("evidence") or []),
    }
    for key in ("note", "unit_codes", "dynamic"):
        if item.get(key):
            summary[key] = copy.deepcopy(item[key])
    if versions:
        summary["content_endpoint"] = f"/api/v1/materials/{item['id']}/content"
    return summary


def content_endpoint(item: dict[str, Any]) -> Optional[str]:
    """该资料的取回入口；没有独立文件版本时返回 None。"""
    if item.get("versions"):
        return f"/api/v1/materials/{item['id']}/content"
    return None
