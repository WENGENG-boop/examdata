"""Spec 解析：把考试局官方 specification 解析成可入库的内容点树。

数据模型见 `models.py`（ParsedSpec/SpecUnit/SpecNode），
通用工具见 `common.py`，逐科解析器见 `subjects/`，批处理入口 `runner.py`。
"""

from .models import SCHEMA_VERSION, ParsedSpec, SpecNode, SpecUnit

__all__ = ["SCHEMA_VERSION", "ParsedSpec", "SpecNode", "SpecUnit"]
