"""robots.txt 获取与强制。

需求文档与 research/cambridge.md 都要求：抓取必须遵守 robots。
Cambridge 的 robots 明确 Disallow /search，因此站内搜索枚举必须被拒绝。
"""

from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse


@dataclass
class RobotsPolicy:
    """某个主机的 robots 规则。"""

    host: str
    robots_url: str
    fetched: bool = False
    allow_all: bool = False
    parser: urllib.robotparser.RobotFileParser | None = None
    raw: str = ""
    sitemaps: list[str] = field(default_factory=list)

    def can_fetch(self, user_agent: str, url: str) -> bool:
        if not self.fetched:
            # 未能获取 robots 时，保守地按"未禁止"处理，但仍受限速约束
            return True
        if self.allow_all:
            return True
        if self.parser is None:
            return True
        return self.parser.can_fetch(user_agent, url)


def parse_robots(host: str, robots_url: str, text: str) -> RobotsPolicy:
    policy = RobotsPolicy(host=host, robots_url=robots_url, fetched=True, raw=text)
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())
    policy.parser = parser
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            policy.sitemaps.append(line.split(":", 1)[1].strip())
    return policy


def robots_url_for(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def origin_of(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}"
