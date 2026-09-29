"""paperqa 的请求与结果模型。

请求解析（`Request.parse`）是所有入口的**唯一**校验点：CLI、HTTP、Python
调用都经过它，所以非法参数在任何路径下都得到同一种错误，不会出现
"CLI 拦住了但 HTTP 放过去"的缺口。校验同时承担两层职责——通用的
类型/范围检查，以及每个考试局各自的取值域（CIE 只认整份 PDF，
Edexcel 的 question/qa 必须给出 paper+question）。

下载的文件一律是内存字节（`OutputFile.data`），不落盘；`Result.files`
为空表示"只解析了清单，没下载"。

`Result.metadata()` 是所有出口（HTTP JSON、CLI `--json`）共用的**唯一**
序列化形态：CLI 与 HTTP 拿到的字段名、层级、类型完全一致，调用方不必
为两条通道写两套解析。版本号放在顶层 `schema_version`，字段增删时调用方
可以据此判断。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import base64
import hashlib
import re

from .errors import InvalidRequest

# 序列化格式版本。只要 metadata() 的字段语义发生不兼容变化就必须递增，
# 调用方据此决定是否继续解析。
SCHEMA_VERSION = "1"

# 各考试局的考季别名表。CIE 只有三个考季；Edexcel 用月份名，
# 且实测 servlet 里的考季写成 "June-2024" 这种形式。
# 注意 CIE 的 "Jan" 不在表内——早期版本把它错映射成 Mar，导致取错考季。
CIE_SEASONS: dict[str, str] = {
    "mar": "Mar",
    "march": "Mar",
    "jun": "Jun",
    "june": "Jun",
    "nov": "Nov",
    "november": "Nov",
}
EDEXCEL_SEASONS: dict[str, str] = {
    "jan": "January",
    "january": "January",
    "winter": "January",
    "jun": "June",
    "june": "June",
    "summer": "June",
    "oct": "October",
    "october": "October",
    "nov": "November",
    "november": "November",
}
CIE_MODES = {"qp", "ms", "both"}
EDEXCEL_MODES = {"paper", "question", "qa"}

ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x")

RE_SUBJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9 -]{0,79}")
RE_PAPER = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?")
RE_QUESTION = re.compile(r"[1-9]\d{0,2}(?:\([a-z]\)(?:\([ivx]+\))?)?")
# 原 paper_qa 的 CLI 把题号写成 "1 / 1(a) / 1a / 1(a)(i)"，短写 `1a`/`1ai`
# 是它对外承诺的输入。这里只做补写，不做新语义：`1ai` 与 `1(a)(i)` 同义。
RE_QUESTION_SHORT = re.compile(
    r"([1-9]\d{0,2})([a-z])(" + "|".join(sorted(ROMAN, key=len, reverse=True)) + r")?"
)
RE_CIE_SUBJECT = re.compile(r"\d{4}")
RE_CIE_PAPER = re.compile(r"\d{1,2}")


@dataclass(frozen=True)
class Request:
    board: str
    subject: str
    year: int
    season: str
    paper: str | None
    question: str | None
    mode: str

    @classmethod
    def parse(cls, board, subject, year, season, paper=None, question=None, mode=None):
        board = str(board).lower()
        if board == "cambridge":
            board = "cie"
        if board not in {"cie", "edexcel"}:
            raise InvalidRequest("board must be cie or edexcel")

        subject = str(subject).strip()
        if not RE_SUBJECT.fullmatch(subject):
            raise InvalidRequest("Invalid subject")

        try:
            if isinstance(year, bool) or str(int(year)) != str(year):
                raise ValueError
            year = int(year)
        except (TypeError, ValueError):
            raise InvalidRequest("year must be an integer") from None
        if not 2000 <= year <= 2099:
            raise InvalidRequest("year must be between 2000 and 2099")

        seasons = CIE_SEASONS if board == "cie" else EDEXCEL_SEASONS
        season = seasons.get(str(season).lower())
        if season is None:
            raise InvalidRequest("Unsupported season for this board")

        mode = str(mode or ("qp" if board == "cie" else "paper")).lower()
        if mode == "qp+ms":
            mode = "both"
        if mode not in (CIE_MODES if board == "cie" else EDEXCEL_MODES):
            raise InvalidRequest("Unsupported mode for this board")

        paper = str(paper).lower().replace("/", "-") if paper is not None else None
        if paper is not None and not RE_PAPER.fullmatch(paper):
            raise InvalidRequest("Invalid paper identifier")

        question = str(question).lower().replace(" ", "") if question is not None else None
        if question is not None and not RE_QUESTION.fullmatch(question):
            short = RE_QUESTION_SHORT.fullmatch(question)
            if short is None:
                raise InvalidRequest("question must be a number such as 12 or 12(a)(ii)")
            part, roman = short.group(2), short.group(3)
            question = f"{short.group(1)}({part})" + (f"({roman})" if roman else "")

        if board == "cie":
            if not RE_CIE_SUBJECT.fullmatch(subject) or (
                paper is not None and not RE_CIE_PAPER.fullmatch(paper)
            ):
                raise InvalidRequest("CIE requires a four-digit subject and one/two-digit paper")
            if question is not None:
                raise InvalidRequest(
                    "CIE supports whole PDFs only; question selection is unavailable"
                )
        elif mode in {"question", "qa"}:
            if question is None or paper is None:
                raise InvalidRequest("question and paper are required for question/qa mode")
        elif question is not None:
            raise InvalidRequest("paper mode does not accept question")

        return cls(board, subject, year, season, paper, question, mode)


@dataclass(frozen=True)
class Document:
    """一份已解析出来、但还没下载的官方文件。"""

    name: str
    url: str
    role: str
    paper: str
    media_type: str = "application/pdf"


@dataclass(frozen=True)
class OutputFile:
    """已取回内存的文件。`data` 是唯一载荷，不指向任何磁盘位置。

    `page` / `bbox` 只对"从 PDF 裁剪出来的"文件有意义：记录它取自原件的
    第几页（1 起）与 PDF 用户空间坐标，调用方据此能回到原件复核那一小块。
    整份 PDF 没有裁剪来源，两者为 None。

    `sha256` 由 `data` 派生（构造时自动算好），调用方拿到 base64 或落盘后
    都能用同一摘要校验完整性；也便于判断两次调用是否返回了同一份内容。
    """

    name: str
    data: bytes
    media_type: str
    role: str
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    sha256: str = field(default="")

    def __post_init__(self):
        # frozen dataclass 只能用 object.__setattr__ 赋值；空串表示"还没算"，
        # 这样显式传入摘要的调用方（如果有）不会被覆盖。
        if not self.sha256:
            object.__setattr__(self, "sha256", hashlib.sha256(self.data).hexdigest())


@dataclass
class Result:
    request: Request
    documents: list[Document]
    files: list[OutputFile] = field(default_factory=list)

    def metadata(self, *, inline_data: bool = False):
        """可 JSON 序列化的清单——CLI 与 HTTP JSON 共用的同一套 schema。

        默认只给元数据（尺寸/摘要/裁剪来源），不回传文件字节；`inline_data=True`
        时每个文件额外带 `data_base64`，让处理不了二进制的客户端也能拿到载荷。
        无论是否内联，`data_base64` 键始终存在（未内联时为 null），
        这样两种出口的字段集合完全一致。
        """
        files = []
        for f in self.files:
            files.append(
                {
                    "name": f.name,
                    "media_type": f.media_type,
                    "role": f.role,
                    "size": len(f.data),
                    "sha256": f.sha256,
                    "page": f.page,
                    "bbox": list(f.bbox) if f.bbox is not None else None,
                    "data_base64": (
                        base64.b64encode(f.data).decode("ascii") if inline_data else None
                    ),
                }
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "request": asdict(self.request),
            "counts": {
                "documents": len(self.documents),
                "files": len(self.files),
                "bytes": sum(len(f.data) for f in self.files),
            },
            "documents": [asdict(d) for d in self.documents],
            "files": files,
        }
