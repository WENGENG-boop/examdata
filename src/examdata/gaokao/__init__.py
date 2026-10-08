"""gaokao board：高考真题聚合器（board=gaokao）。

三个渠道分流：``github`` (成卷 PDF) / ``eol`` (文章图片) / ``hf`` (题目级 CSV)。
"""

from __future__ import annotations

__all__ = ["provinces", "inventory", "adapter", "channels"]


def __getattr__(name):
    # 惰性导出 Channels / 子模块
    import types
    if name == "channels":
        import sys
        return sys.modules[__name__ + ".channels"]
    raise AttributeError(name)