"""考试发放资料的实时取回。

两类资料的取回路径不同，但收口在同一套约束里：

- 静态资料（目录里带 `versions[].url` 的条目，如 MF19、Edexcel 公式册）：
  官方公开 PDF，按 URL 直接取回；
- 动态资料（CIE 镜像的 in / ir / ci 角色，如 insert、保密须知）：
  先 POST 目录接口按 subject / year / season 定位文件名，再按名取回。

三条硬约束：

1. 一律经 `examdata.core.fetch.Fetcher`（robots、限速、重试），不自建通道；
2. 字节必须过 `download_pdf` 的校验（重定向/401/403 → 受限；非 2xx → 上游
   故障；大小上限、`%PDF-` 魔数、PyMuPDF 可打开）；
3. robots 拒绝与采集故障分开报：robots 命中报 403，不当 502（仓库约定：
   robots 拒绝不是"采集故障"，调用方不得混为一谈）。

sha256 语义：目录里的 sha256 是调研时点的快照，只做对照。实测摘要随响应
返回，与快照不一致**不报错**（上游换版是合法事件），由调用方决定是否升级
快照；`FetchedStatic.sha256_match` 只做如实告知。

参数校验沿用 paperqa 的取值域：subject 四位数字、year 2000..2099、考季走
`CIE_SEASONS` 别名表（Mar/March、Jun/June、Nov/November），错误抛
`InvalidRequest`（HTTP 层 422）。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import unquote, urlsplit

from ..core.fetch import Fetcher, RobotsDisallowed
from ..paperqa.errors import AccessDenied, InvalidRequest, NotFound, UpstreamError
from ..paperqa.models import CIE_SEASONS, Document
from ..paperqa.sources.base import download_pdf
from ..paperqa.sources.cie_fraft import ORIGIN as CIE_ORIGIN

CIE_RENUM_URL = f"{CIE_ORIGIN}/obj/Common/Fetch/renum"
CIE_REDIR_URL = f"{CIE_ORIGIN}/obj/Common/Fetch/redir/"

# 镜像里属于"考试发放资料"的角色：in=insert、ir/ci=保密须知（考务文件）。
# qp/ms 归 paperqa 数据源管，这里不看。
MATERIAL_ROLES = ("in", "ir", "ci")
CIE_MATERIAL_FILE = re.compile(
    r"(?P<subject>\d{4})_(?P<season>[msw])(?P<year>\d{2})_(?P<role>in|ir|ci)_(?P<paper>\d{1,2})\.pdf"
)
_SEASON_CODE = {"Mar": "m", "Jun": "s", "Nov": "w"}


@dataclass(frozen=True)
class FetchedStatic:
    """一次静态资料取回的实测结果（字节、摘要与来源版本记录）。"""

    version: dict[str, Any]
    data: bytes
    sha256: str

    @property
    def sha256_match(self) -> bool:
        """实测摘要与目录快照是否一致；目录未记 sha256 时恒为 False。"""
        expected = self.version.get("sha256")
        return bool(expected) and self.sha256 == expected


def select_version(item: dict[str, Any], label: Optional[str]) -> dict[str, Any]:
    """在条目的 `versions` 里挑一个版本；未命中抛 422。

    `label=None` 取第一项（目录里的首选/最新）；纯数字按 0 起索引；其余按
    label 全等匹配。版本必须显式区分（如 MF19 换版不能混用），因此不提供
    模糊匹配。`versions` 为空说明该资料没有独立文件（如印在试卷内），抛 422。
    """
    versions = item.get("versions") or []
    if not versions:
        raise InvalidRequest(f"资料 {item.get('id')} 没有可独立取回的版本")
    if label is None:
        return versions[0]
    token = str(label).strip()
    if re.fullmatch(r"\d+", token):
        index = int(token)
        if 0 <= index < len(versions):
            return versions[index]
        raise InvalidRequest(f"版本索引超出范围（0..{len(versions) - 1}）: {label!r}")
    for version in versions:
        if str(version.get("label")) == token:
            return version
    raise InvalidRequest(
        f"未知版本: {label!r}（可用: {[version.get('label') for version in versions]}）"
    )


def version_filename(version: dict[str, Any]) -> str:
    """从版本 URL 派生下载文件名（百分号解码后的 basename）。"""
    path = urlsplit(str(version.get("url") or "")).path
    return unquote(path.rsplit("/", 1)[-1]) or "material.pdf"


def _guard_robots(fetcher: Fetcher, url: str) -> None:
    """robots 预检：命中 Disallow 直接 403，不把 robots 拒绝当采集故障。

    `download_pdf` 只看 HTTP 结果，robots 拒绝在它眼里是 "HTTP 0 失败"。
    先在抓取器上做一次 `assert_allowed`（策略有进程内缓存，不产生额外请求），
    把这类拒绝翻译成 AccessDenied。
    """
    try:
        fetcher.assert_allowed(url)
    except RobotsDisallowed as exc:
        raise AccessDenied(str(exc)) from exc


def fetch_material(fetcher: Fetcher, version: dict[str, Any]) -> FetchedStatic:
    """取回一个静态资料版本，返回实测字节与 sha256。"""
    url = str(version.get("url") or "").strip()
    if not url:
        raise InvalidRequest("版本缺少 url，无法取回")
    _guard_robots(fetcher, url)
    document = Document(name=version_filename(version), url=url, role="material", paper="")
    data = download_pdf(fetcher, document)
    return FetchedStatic(
        version=dict(version),
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def resolve_cie_documents(
    fetcher: Fetcher,
    subject: str,
    year: int,
    season: str,
    paper: Optional[str] = None,
    role: Optional[str] = None,
) -> list[Document]:
    """POST CIE 镜像目录接口，定位 subject/year/season 下的发放资料文件。

    `role` 限定 in / ir / ci 之一；`paper` 限定组件号（如 11）。返回按文件名
    排序的 `Document` 列表；一个都没命中抛 404。目录响应结构照搬
    `CieFraftSource.resolve`（`total` 与 `rows` 长度不符视为清单被截断）。
    """
    subject_token = str(subject).strip()
    if not re.fullmatch(r"\d{4}", subject_token):
        raise InvalidRequest(f"subject 需为四位 CIE 科目代码: {subject!r}")
    try:
        year_token = int(year)
    except (TypeError, ValueError):
        raise InvalidRequest(f"year 需为整数: {year!r}") from None
    if not 2000 <= year_token <= 2099:
        raise InvalidRequest(f"year 需在 2000..2099: {year!r}")
    canonical = CIE_SEASONS.get(str(season).strip().lower())
    if canonical is None:
        raise InvalidRequest(
            f"不支持的 CIE 考季: {season!r}（可用: Mar/March、Jun/June、Nov/November）"
        )
    role_token: Optional[str] = None
    if role is not None:
        role_token = str(role).strip().lower()
        if role_token not in MATERIAL_ROLES:
            raise InvalidRequest(f"role 只支持 {'/'.join(MATERIAL_ROLES)}: {role!r}")
    paper_token: Optional[str] = None
    if paper is not None:
        paper_token = str(paper).strip()
        if not re.fullmatch(r"\d{1,2}", paper_token):
            raise InvalidRequest(f"paper 需为一到两位数字: {paper!r}")

    response = fetcher.post_form(
        CIE_RENUM_URL,
        {"subject": subject_token, "year": year_token, "season": canonical},
        follow_redirects=False,
    )
    if response.robots_blocked:
        raise AccessDenied(f"robots.txt 禁止抓取 CIE 镜像目录接口: {CIE_RENUM_URL}")
    if not response.ok:
        raise UpstreamError(f"CIE 镜像目录接口不可用（HTTP {response.status}）")
    try:
        payload = json.loads(response.text or "")
        rows = payload["rows"]
        if not isinstance(rows, list) or int(payload["total"]) != len(rows):
            raise ValueError("Incomplete catalogue")
    except (ValueError, TypeError, KeyError) as exc:
        raise UpstreamError("CIE 镜像目录响应无效或不完整") from exc

    season_code = _SEASON_CODE[canonical]
    documents: dict[str, Document] = {}
    for row in rows:
        name = row.get("file", "") if isinstance(row, dict) else ""
        match = CIE_MATERIAL_FILE.fullmatch(name) if isinstance(name, str) else None
        if not match:
            continue
        groups = match.groupdict()
        if (
            groups["subject"] != subject_token
            or int(groups["year"]) != year_token % 100
            or groups["season"] != season_code
            or (role_token is not None and groups["role"] != role_token)
            or (paper_token is not None and groups["paper"] != paper_token)
        ):
            continue
        documents[name] = Document(
            name, f"{CIE_REDIR_URL}{name}", groups["role"], groups["paper"]
        )
    if not documents:
        raise NotFound("未找到匹配的发放资料文件")
    return sorted(documents.values(), key=lambda document: document.name)


def download_cie_document(fetcher: Fetcher, document: Document) -> bytes:
    """下载镜像文件；地址必须与按文件名拼出的信任地址全等，否则 403。"""
    if not CIE_MATERIAL_FILE.fullmatch(document.name) or document.url != f"{CIE_REDIR_URL}{document.name}":
        raise AccessDenied("Untrusted CIE document URL")
    _guard_robots(fetcher, document.url)
    return download_pdf(fetcher, document)
