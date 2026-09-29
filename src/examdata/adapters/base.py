"""适配器契约。

统一抽象使核心系统无需理解任何考试局站点的具体结构。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from ..core.fetch import Fetcher


@dataclass
class SyllabusRef:
    """一个可被巡检的 syllabus（科目 + 资格）。"""

    slug: str
    code: str
    title: str
    qualification_key: str
    qualification_name: str
    source_url: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoveredResource:
    """从官方页面发现的一个文件。"""

    url: str
    label: Optional[str]
    doc_type: str
    confidence: float
    # 统一字段：year, series, paper_code, component, variant, level, subject_code ...
    meta: dict[str, Any] = field(default_factory=dict)
    # 分类证据：各信号及命中情况
    evidence: dict[str, Any] = field(default_factory=dict)
    # 该资源所属的页面
    page_url: Optional[str] = None


@dataclass
class PageSnapshot:
    """一次页面抓取的结果，含离线重放所需的原始 HTML。"""

    url: str
    status: int
    html: Optional[str]
    error: Optional[str] = None


class BoardAdapter(ABC):
    """考试局适配器基类。"""

    key: str = ""
    board_name: str = ""
    homepage: str = ""
    # public / partial_public / login_walled / unsupported_public
    accessibility: str = "public"

    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher

    # -- 发现 ------------------------------------------------------------

    @abstractmethod
    def index_sources(self) -> list[tuple[str, str]]:
        """返回 (kind, url) 列表：适配器需要巡检的入口页面。"""

    @abstractmethod
    def discover_syllabuses(self) -> Iterable[SyllabusRef]:
        """枚举该考试局当前公开的 syllabus。"""

    @abstractmethod
    def discover_resources(self, syllabus: SyllabusRef) -> Iterable[DiscoveredResource]:
        """枚举某个 syllabus 下公开的资源文件。"""

    # -- 分类与解析（子类按需覆盖） --------------------------------------

    def classify(self, label: str, url: str) -> tuple[str, float, dict[str, Any]]:
        """由锚文本与 URL 判定文件类型。返回 (doc_type, confidence, evidence)。"""
        raise NotImplementedError

    def normalize_metadata(self, resource: DiscoveredResource) -> dict[str, Any]:
        """把考试局特有元数据映射为统一概念，同时保留原始属性。"""
        return dict(resource.meta)
