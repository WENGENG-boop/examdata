"""Cambridge International 适配器。

公开档（无需登录）：
- 家族 -> syllabus: /programmes-and-qualifications/{family}/{qualification}/subjects/
- syllabus -> 资源: /{syllabus-slug}/past-papers
- 文件: /Images/{opaque-id}-{descriptive-slug}.pdf

详见 research/cambridge.md。
"""

from .adapter import CambridgeAdapter

__all__ = ["CambridgeAdapter"]
