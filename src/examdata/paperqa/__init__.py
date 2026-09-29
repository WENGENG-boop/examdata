"""按考试局取回真题文件。

CIE（工坊）返回**完整 PDF**：`qp` / `ms` / `both`。
Edexcel（官方站）返回 `paper`（整份 QP PDF）/ `question`（题目 PNG）/
`qa`（题目 PNG + 从 Mark Scheme 裁出的答案 PNG）。

不注册为 `BoardAdapter`：适配器契约面向"发现并入库"，而这里面向
"按需取回一份文件"，两者的失败语义与生命周期都不同。共用的是
`adapters/edexcel/servlet.py` 那条只读查询通道。
"""

from .api import query, resolve
from .errors import PaperQAError
from .models import Document, OutputFile, Result

__all__ = ["query", "resolve", "PaperQAError", "Document", "OutputFile", "Result"]
