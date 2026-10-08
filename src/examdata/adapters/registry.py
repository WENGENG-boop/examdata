"""适配器注册表。

新增考试局**不需要改这个文件**：`_load_builtin()` 自动发现
adapters/ 下的所有子包并导入，每个子包在 import 时用 @register 自行登记。

这条自动发现很关键。如果每加一个考试局都要回来往 _load_builtin 里加一行，
那"核心系统无需改动"就变成了一句空话——注册表本身也是核心。
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .base import BoardAdapter

_REGISTRY: dict[str, type["BoardAdapter"]] = {}
_LOGGER = logging.getLogger(__name__)
LOAD_FAILURES: list[str] = []


def register(cls: type["BoardAdapter"]) -> type["BoardAdapter"]:
    if not cls.key:
        raise ValueError(f"{cls.__name__} 必须定义 key")
    if cls.key in _REGISTRY:
        raise ValueError(f"适配器 key 重复: {cls.key}")
    _REGISTRY[cls.key] = cls
    return cls


def get_adapter_class(key: str) -> type["BoardAdapter"]:
    if key not in _REGISTRY:
        details = f"；加载失败: {'; '.join(LOAD_FAILURES)}" if LOAD_FAILURES else ""
        raise KeyError(f"未注册的适配器: {key}（已注册: {sorted(_REGISTRY)}{details}）")
    return _REGISTRY[key]


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)


def _load_builtin() -> list[str]:
    """导入子包并注册；返回包含包名、异常类型及原因的失败诊断。"""
    package = importlib.import_module("examdata.adapters")
    failures: list[str] = []
    for info in pkgutil.iter_modules(package.__path__):
        if not info.ispkg or info.name.startswith("_"):
            continue
        previous = dict(_REGISTRY)
        try:
            importlib.import_module(f"examdata.adapters.{info.name}")
        except Exception as exc:  # noqa: BLE001
            _REGISTRY.clear()
            _REGISTRY.update(previous)
            diagnostic = f"{info.name}: {type(exc).__name__}: {exc}"
            failures.append(diagnostic)
            _LOGGER.warning("Adapter load failed: %s", diagnostic)
    return failures


LOAD_FAILURES = _load_builtin()
