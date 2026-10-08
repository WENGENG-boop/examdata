"""paperqa 对外入口：解析清单、按需下载、按需裁剪。

`resolve()` 只解析清单（不下载），`query()` 解析后把文件取回内存。
两者都不落盘，只有显式传 `out_dir` 才写文件，且已存在的文件不覆盖——
重复调用不会悄悄改掉用户手里的原件。

HTTP 层只暴露这两个函数的只读形态：单文件直接返回字节，多文件在内存里
打 ZIP；处理不了二进制的客户端可以改走 `json_payload()`——同一套 schema，
但载荷以 base64 内联。写入类操作刻意不开放匿名接口。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import json
from urllib.parse import quote
from zipfile import ZipFile, ZIP_DEFLATED

from ..core.config import Settings
from ..core.fetch import Fetcher
from .errors import AmbiguousDocument, InvalidRequest, UpstreamError
from .budget import RequestBudget, BudgetedFetcher, MAX_DOCUMENTS
from .locator import crop_question, index_questions
from .models import Request, Result, OutputFile
from .sources.cie_fraft import CieFraftSource
from .sources.pearson import PearsonSource


def _run(request: Request, fetcher: Fetcher, download: bool) -> Result:
    budget = RequestBudget()
    counted = BudgetedFetcher(fetcher, budget)
    source = CieFraftSource(counted) if request.board == "cie" else PearsonSource(counted)
    result = Result(request, source.resolve(request), budget=budget)
    if len(result.documents) > MAX_DOCUMENTS:
        raise UpstreamError("Request document limit exceeded")
    if download:
        for document in result.documents:
            data = source.download(document)
            if request.question is not None:
                # 裁剪结果自带来源（1 起页码 + PDF 用户空间 bbox），
                # 一并带进 Result，调用方才能回到原件复核这一小块。
                for crop in crop_question(data, request.question, document.role, budget=result.budget):
                    label = request.question.replace("(", "-").replace(")", "")
                    name = f"{document.name[:-4]}-q{label}-p{crop.page}.png"
                    result.files.append(
                        OutputFile(
                            name, crop.png, "image/png", document.role,
                            page=crop.page, bbox=crop.bbox,
                        )
                    )
            else:
                result.files.append(OutputFile(document.name, data, document.media_type, document.role))
            result.budget.check_files(len(result.files))
    return result


def resolve(board, subject, year, season, paper=None, question=None, mode=None, *, fetcher=None) -> Result:
    request = Request.parse(board, subject, year, season, paper, question, mode)
    if fetcher is not None:
        return _run(request, fetcher, False)
    with Fetcher(Settings()) as owned:
        return _run(request, owned, False)


def index_paper(subject, year, season, paper, mode="both", *, fetcher=None) -> dict:
    """Edexcel-only geometric QP/MS index; source content is not an AI answer."""
    if mode not in {"qp", "ms", "both"}:
        raise InvalidRequest("index mode must be qp, ms or both")
    result = query("edexcel", subject, year, season, paper, mode=mode, fetcher=fetcher)
    if len({document.paper for document in result.documents}) != 1:
        raise AmbiguousDocument("Index requires one exact paper variant")
    documents = []
    questions = {}
    for file in result.files:
        rows = index_questions(file.data, file.role)
        documents.append({"name": file.name, "role": file.role, "sha256": file.sha256})
        for row in rows:
            entry = questions.setdefault(row["question"], {
                "question": row["question"], "qp": [], "ms": [],
            })
            entry[file.role].extend({**region, "sha256": file.sha256} for region in row["regions"])
    payload = {"schema_version": "1", "board": "edexcel", "request": {
        "subject": result.request.subject, "year": year, "season": result.request.season,
        "paper": result.request.paper, "mode": mode,
    }, "coordinate_system": "unrotated_pdf_points_top_left", "page_base": 1,
        "method": "left_column_algorithm", "reviewed": False,
        "documents": documents, "questions": list(questions.values())}
    result.budget.charge(len(json.dumps(payload).encode("utf-8")), "question index")
    return payload


def query(board, subject, year, season, paper=None, question=None, mode=None, out_dir=None, *, fetcher=None) -> Result:
    request = Request.parse(board, subject, year, season, paper, question, mode)
    if fetcher is not None:
        result = _run(request, fetcher, True)
    else:
        with Fetcher(Settings()) as owned:
            result = _run(request, owned, True)
    if out_dir is not None:
        directory = Path(out_dir).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        for file in result.files:
            if not re.fullmatch(r"[A-Za-z0-9_. -]+", file.name) or file.name in {".", ".."}:
                raise InvalidRequest("Unsafe output filename")
            target = directory / file.name
            if target.is_symlink() or target.resolve().parent != directory:
                raise InvalidRequest("Output path escapes destination")
            with target.open("xb") as stream:
                stream.write(file.data)
    return result


def response_payload(result: Result) -> OutputFile:
    """把结果压成"一个可下载的东西"：单文件原样返回，多文件内存 ZIP。

    ZIP 只存在于内存，不落盘；成员名就是各自的 `Result.files` 名称。
    """
    budget = result.budget or RequestBudget()
    budget.check_files(len(result.files))
    if len(result.files) == 1:
        return result.files[0]
    class BoundedBuffer(BytesIO):
        def write(self, data):
            growth = max(0, self.tell() + len(data) - len(self.getbuffer()))
            budget.charge(growth, "ZIP serialization")
            return super().write(data)
    buffer = BoundedBuffer()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for file in result.files:
            archive.writestr(file.name, file.data)
    return OutputFile("paper-qa.zip", buffer.getvalue(), "application/zip", "bundle")


def content_disposition(name: str) -> str:
    """RFC 6266 附件头：引号/控制字符消毒，非 ASCII 名附 `filename*`。

    名字直接拼进 `filename="..."` 会出两类问题：引号或换行破坏头部结构
    （可注入），非 ASCII 字符让 Starlette 以 latin-1 编码响应头时抛错
    （500）。回退名只保留可打印 ASCII，原名以 RFC 5987 的百分号编码
    放进 `filename*`，兼容的客户端优先用它。
    """
    fallback = re.sub(r'[^\x20-\x7e]|["\\]', "_", name).strip() or "download"
    if fallback == name:
        return f'attachment; filename="{fallback}"'
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def json_payload(result: Result) -> dict:
    """二进制出口的等价 JSON 形态：同一套 schema + 内联 base64 载荷。

    给处理不了 `application/pdf` / `application/zip` 的客户端用（浏览器脚本、
    只接受 JSON 的网关等）。不做 ZIP 打包——每个文件独立 base64，客户端可以
    按 `name`/`role`/`page` 自行取舍。
    """
    return result.metadata(inline_data=True)
