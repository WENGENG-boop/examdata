"""逐科 spec 解析器注册表。

每个解析器模块定义 `SLUG`（如 "ial18-biology"）与 `parse(text, meta) -> ParsedSpec`。
本包扫描目录自动注册，新增科目只需加一个模块文件。
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable

from ..models import ParsedSpec

PARSERS: dict[str, Callable[[str, dict[str, Any] | None], ParsedSpec]] = {}
IMPORT_ERRORS: dict[str, str] = {}


def _discover() -> None:
    pkg_path = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_path)]):
        if info.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{info.name}")
        except Exception as exc:  # noqa: BLE001 - 单科模块出错不拖垮其它科目
            IMPORT_ERRORS[info.name] = f"{type(exc).__name__}: {exc}"
            continue
        slug = getattr(mod, "SLUG", None)
        parse = getattr(mod, "parse", None)
        if slug and callable(parse):
            PARSERS[slug] = parse


_discover()


def all_slugs() -> list[str]:
    return sorted(PARSERS)
