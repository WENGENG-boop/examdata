"""数据源协议与共用的 PDF 下载校验。

两个考试局的解析规则完全不同（一个靠 POST 目录接口，一个靠 servlet），
但"把一份 PDF 安全地取回来"是同一件事，所以放在这里共用。

下载校验按顺序做五件事，任何一步失败都抛错而不是返回可疑字节：
重定向/401/403 视为受限；非 2xx 视为上游故障；声明和实际正文大小校验；
`%PDF-` 魔数校验；PyMuPDF 能真正打开（光有魔数可能是个截断文件）。
自定义 Fetcher 返回的字节也必须通过大小校验。
"""

from __future__ import annotations

from typing import Protocol

import pymupdf

from ...core.fetch import MAX_RESPONSE_BYTES, Fetcher
from ..errors import AccessDenied, UpstreamError
from ..models import Document, Request


class Source(Protocol):
    def resolve(self, request: Request) -> list[Document]: ...
    def download(self, document: Document) -> bytes: ...


def download_pdf(fetcher: Fetcher, document: Document) -> bytes:
    response = fetcher.get(document.url, expect_binary=True, follow_redirects=False)
    if 300 <= response.status < 400 or response.status in {401, 403}:
        raise AccessDenied("Document is restricted or redirects; download refused")
    if not response.ok or not response.content:
        raise UpstreamError(f"PDF download failed (HTTP {response.status})")
    data = response.content
    try:
        declared_length = getattr(response, "content_length", None)
        oversized = len(data) > MAX_RESPONSE_BYTES or (
            declared_length is not None and declared_length > MAX_RESPONSE_BYTES
        )
    except (TypeError, ValueError):
        raise UpstreamError("Upstream PDF body is invalid") from None
    if oversized:
        raise UpstreamError("Upstream PDF exceeds response size limit")
    if not isinstance(data, bytes) or not data.startswith(b"%PDF-"):
        raise UpstreamError("Upstream returned a non-PDF document")
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass or not pdf.page_count:
                raise ValueError("Unreadable PDF")
    except Exception as exc:
        raise UpstreamError("Upstream PDF cannot be opened") from exc
    return data
