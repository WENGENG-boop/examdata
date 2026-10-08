"""考试时间表：PDF 解析、离线快照与 `/api/v1` 路由。

覆盖两个考试局：

- CIE Zone 5：`parser` 抽结构化事件与单元考试日期窗口，`build` 把 25 个考季
  （2013-11 … 2026-11）解析成 `data/zone5/` 离线快照；
- Edexcel：`edexcel_parser` / `build_edexcel` 覆盖 gcse / intgcse / ial / gce
  四族谱共 106 个考季（含 R 卷变体），快照在 `data/edexcel/`。

`router`：`/api/v1/timetable*`，只读快照，运行时不联网、不查库。
"""

from __future__ import annotations

from .parser import normalize_series, parse_pdf, season_key
from .router import router

__all__ = ["normalize_series", "parse_pdf", "router", "season_key"]
