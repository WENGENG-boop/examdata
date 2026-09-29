"""CIE 工坊（cie.fraft.cn）数据源。

只做两件事：POST 目录接口拿文件清单，再按文件名下载整份 PDF。
**不解析 PDF 文本层、不做 OCR**——实测该站的 PDF 文本层是坏的
（字母数字占比 0.03~0.05，抽出来全是乱码 token），任何基于文本的
裁剪都只会产出垃圾。用户要的也正是完整 PDF。

目录接口只接受 POST（空 body 返回 411），且返回体自带 `total`；
`total` 与 `rows` 长度不符即视为清单被截断，直接报错，不猜。
"""

import json
import re

from ...core.fetch import Fetcher
from ..errors import NotFound, UpstreamError, AccessDenied
from ..models import Document, Request
from .base import download_pdf

ORIGIN = "https://cie.fraft.cn"
FILE = re.compile(r"(?P<subject>\d{4})_(?P<season>[msw])(?P<year>\d{2})_(?P<role>qp|ms)_(?P<paper>\d{1,2})\.pdf")


class CieFraftSource:
    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    def resolve(self, request: Request) -> list[Document]:
        response = self.fetcher.post_form(f"{ORIGIN}/obj/Common/Fetch/renum", {
            "subject": request.subject, "year": request.year, "season": request.season,
        }, follow_redirects=False)
        if not response.ok:
            raise UpstreamError(f"CIE catalogue unavailable (HTTP {response.status})")
        try:
            payload = json.loads(response.text or "")
            rows = payload["rows"]
            if not isinstance(rows, list) or int(payload["total"]) != len(rows):
                raise ValueError("Incomplete catalogue")
        except (ValueError, TypeError, KeyError) as exc:
            raise UpstreamError("Invalid or incomplete CIE catalogue") from exc
        roles = {"qp", "ms"} if request.mode == "both" else {request.mode}
        documents = {}
        for row in rows:
            name = row.get("file", "") if isinstance(row, dict) else ""
            match = FILE.fullmatch(name) if isinstance(name, str) else None
            if not match:
                continue
            m = match.groupdict()
            if (m["subject"] != request.subject or int(m["year"]) != request.year % 100
                    or m["season"] != {"Mar": "m", "Jun": "s", "Nov": "w"}[request.season]
                    or m["role"] not in roles or (request.paper and m["paper"] != request.paper)):
                continue
            documents[name] = Document(name, f"{ORIGIN}/obj/Common/Fetch/redir/{name}", m["role"], m["paper"])
        if not documents or {d.role for d in documents.values()} != roles:
            raise NotFound("Requested CIE PDFs were not found")
        if request.mode == "both":
            papers = {d.paper for d in documents.values()}
            if any({d.role for d in documents.values() if d.paper == p} != roles for p in papers):
                raise NotFound("A matching CIE QP/MS pair is missing")
        return sorted(documents.values(), key=lambda d: d.name)

    def download(self, document: Document) -> bytes:
        if not FILE.fullmatch(document.name) or document.url != f"{ORIGIN}/obj/Common/Fetch/redir/{document.name}":
            raise AccessDenied("Untrusted CIE document URL")
        return download_pdf(self.fetcher, document)
