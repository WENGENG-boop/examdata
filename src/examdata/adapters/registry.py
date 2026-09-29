"""适配器注册表。

新增考试局**不需要改这个文件**：`_load_builtin()` 自动发现
adapters/ 下的所有子包并导入，每个子包在 import 时用 @register 自行登记。

这条自动发现很关键。如果每加一个考试局都要回来往 _load_builtin 里加一行，
那"核心系统无需改动"就变成了一句空话——注册表本身也是核心。
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .base import BoardAdapter

_REGISTRY: dict[str, type["BoardAdapter"]] = {}


def register(cls: type["BoardAdapter"]) -> type["BoardAdapter"]:
    if not cls.key:
        raise ValueError(f"{cls.__name__} 必须定义 key")
    if cls.key in _REGISTRY:
        raise ValueError(f"适配器 key 重复: {cls.key}")
    _REGISTRY[cls.key] = cls
    return cls


def get_adapter_class(key: str) -> type["BoardAdapter"]:
    if key not in _REGISTRY:
        raise KeyError(f"未注册的适配器: {key}（已注册: {sorted(_REGISTRY)}）")
    return _REGISTRY[key]


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)


def _load_builtin() -> list[str]:
    """导入 adapters/ 下的每个子包以触发注册。返回导入失败的包名。"""
    package = importlib.import_module("examdata.adapters")
    failures: list[str] = []
    for info in pkgutil.iter_modules(package.__path__):
        if not info.ispkg or info.name.startswith("_"):
            continue
        try:
            importlib.import_module(f"examdata.adapters.{info.name}")
        except Exception as exc:  # noqa: BLE001
            # 一个适配器导入失败不应拖垮其他适配器：
            # 需求要求"同步任务发生局部错误时，不应影响其他考试局继续运行"。
            failures.append(f"{info.name}: {type(exc).__name__}: {exc}")
    return failures


LOAD_FAILURES = _load_builtin()
