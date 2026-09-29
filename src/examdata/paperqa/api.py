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
from zipfile import ZipFile, ZIP_DEFLATED

from ..core.config import Settings
from ..core.fetch import Fetcher
from .errors import InvalidRequest
from .locator import crop_question
from .models import Request, Result, OutputFile
from .sources.cie_fraft import CieFraftSource
from .sources.pearson import PearsonSource


def _run(request: Request, fetcher: Fetcher, download: bool) -> Result:
    source = CieFraftSource(fetcher) if request.board == "cie" else PearsonSource(fetcher)
    result = Result(request, source.resolve(request))
    if download:
        for document in result.documents:
            data = source.download(document)
            if request.mode in {"question", "qa"}:
                # 裁剪结果自带来源（1 起页码 + PDF 用户空间 bbox），
                # 一并带进 Result，调用方才能回到原件复核这一小块。
                for crop in crop_question(data, request.question, document.role):
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
    return result


def resolve(board, subject, year, season, paper=None, question=None, mode=None, *, fetcher=None) -> Result:
    request = Request.parse(board, subject, year, season, paper, question, mode)
    if fetcher is not None:
        return _run(request, fetcher, False)
    with Fetcher(Settings()) as owned:
        return _run(request, owned, False)


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
    if len(result.files) == 1:
        return result.files[0]
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for file in result.files:
            archive.writestr(file.name, file.data)
    return OutputFile("paper-qa.zip", buffer.getvalue(), "application/zip", "bundle")


def json_payload(result: Result) -> dict:
    """二进制出口的等价 JSON 形态：同一套 schema + 内联 base64 载荷。

    给处理不了 `application/pdf` / `application/zip` 的客户端用（浏览器脚本、
    只接受 JSON 的网关等）。不做 ZIP 打包——每个文件独立 base64，客户端可以
    按 `name`/`role`/`page` 自行取舍。
    """
    return result.metadata(inline_data=True)
