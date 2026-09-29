"""身份标识与哈希工具。

设计要点（见 research/cambridge.md §4）：
- **文档身份不依赖 URL**：官方替换文件时 URL 与 numeric id 会变，但 (board, qualification,
  subject_code, year, series, paper_code, doc_type) 不变。
- 内容寻址：artifact 按 sha256 去重，跨来源同一份文件只存一份。
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

# 身份键各字段的分隔符：用不可打印字符避免与字段内容冲突
_SEP = "\x1f"


def _norm(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def identity_key(*parts: object) -> str:
    """由规范化字段拼接后取 sha1，作为 document 的逻辑身份。

    >>> identity_key("cambridge", "igcse", "0580", 2024, "june", "11", "question_paper")
    """
    joined = _SEP.join(_norm(p) for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def short_hash(parts: Iterable[object], length: int = 16) -> str:
    joined = _SEP.join(_norm(p) for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:length]


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    return _SLUG_STRIP.sub("-", value.strip().lower()).strip("-")
