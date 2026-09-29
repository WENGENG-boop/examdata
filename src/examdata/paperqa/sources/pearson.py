"""Pearson 官方站数据源（IAL 试卷）。

走站内 servlet（无需凭据）拿记录，再按公开路径下载。两条硬性约束：

1. **只认固定主机上的公开 PDF 路径**。servlet 记录里的 `url` 是外部输入，
   所以它必须通过 `public_url` 的完整校验——主机、scheme、`/content/dam/pdf/`
   前缀、`.pdf` 后缀、无查询串、无片段、无路径穿越、无 secure/gold/silver
   段、无百分号编码——才能变成下载目标。
2. **门禁靠路径判定，不靠 `gating` 字段**。实测该字段恒为 false，
   连门禁路径也是 false；信它会漏判全部登录墙资源。
"""

import re
from urllib.parse import urlsplit

from ...adapters.edexcel.classify import extract_metadata
from ...adapters.edexcel.servlet import ORIGIN, ServletError, ShardExhausted, iter_records
from ...core.fetch import Fetcher
from ..errors import AccessDenied, AmbiguousDocument, NotFound, UpstreamError
from ..models import Document, Request
from .base import download_pdf


def public_url(raw: str) -> str:
    if not isinstance(raw, str):
        raise AccessDenied("Invalid Pearson PDF URL")
    url = ORIGIN + raw if raw.startswith("/content/") else raw
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise AccessDenied("Invalid Pearson PDF URL") from exc
    if (parts.scheme != "https" or parts.netloc != "qualifications.pearson.com"
            or parts.query or parts.fragment or not parts.path.startswith("/content/dam/pdf/")
            or not parts.path.lower().endswith(".pdf")
            or any(p in {".", "..", "secure", "gold", "silver"} for p in parts.path.lower().split("/"))
            or not re.fullmatch(r"/[A-Za-z0-9_./ -]+", parts.path)):
        raise AccessDenied("Only public Pearson PDF paths are accepted")
    return url


class PearsonSource:
    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    def resolve(self, request: Request) -> list[Document]:
        subject = request.subject
        spec_match = re.fullmatch(r"ial\d{2}-(.+)", subject, re.I)
        title = (spec_match.group(1) if spec_match else subject).replace("-", " ").title()
        spec = subject.lower() if spec_match else "ial18-" + subject.lower().replace(" ", "-")
        tags = [[f"Pearson-UK:Qualification-Subject/{title}", f"Pearson-UK:Specification-Code/{spec}"],
                f"Pearson-UK:Exam-Series/{request.season}-{request.year}"]
        if spec_match or (request.paper and request.paper.startswith("w")):
            tags.insert(0, "Pearson-UK:Qualification-Family/International-Advanced-Level")
        try:
            records = list(iter_records(self.fetcher, tags, label=subject))
        except (ServletError, ShardExhausted) as exc:
            raise UpstreamError(str(exc)) from exc
        roles = {"qp", "ms"} if request.mode == "qa" else {"qp"}
        found: dict[tuple[str, str], Document] = {}
        restricted = False
        for record in records:
            raw = record.get("url") or ""
            categories = record.get("category") or []
            if not isinstance(raw, str) or not isinstance(categories, list):
                raise UpstreamError("Invalid Pearson document metadata")
            meta = extract_metadata(categories, raw)
            role = {"question_paper": "qp", "mark_scheme": "ms"}.get(meta["doc_type"])
            match = re.match(r"([a-z0-9]+-\d{2})[-_]", raw.rsplit("/", 1)[-1], re.I)
            if role not in roles or not match:
                continue
            paper = match.group(1).lower()
            if request.paper and request.paper not in {paper, paper.split("-")[0]}:
                continue
            try:
                url = public_url(raw)
            except AccessDenied:
                restricted = True
                continue
            name = url.rsplit("/", 1)[-1]
            key = (paper, role)
            if key in found and found[key].url != url:
                raise AmbiguousDocument(f"Multiple {role} PDFs match {paper}; cannot select safely")
            found[key] = Document(name, url, role, paper)
        if not found or {d.role for d in found.values()} != roles:
            if restricted:
                raise AccessDenied("Requested Pearson document is not publicly downloadable")
            raise NotFound("Requested Pearson PDFs were not found")
        if request.mode in {"question", "qa"} and len({d.paper for d in found.values()}) != 1:
            raise AmbiguousDocument("Specify an exact paper identifier, such as wec11-01")
        return sorted(found.values(), key=lambda d: d.name)

    def download(self, document: Document) -> bytes:
        public_url(document.url)
        return download_pdf(self.fetcher, document)
