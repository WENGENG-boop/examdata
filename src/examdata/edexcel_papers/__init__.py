"""Edexcel IAL 试卷管道：枚举资源、下载原卷、切分题号与评分区域。

子模块不在包级重导出：``enumerate`` 需要网络、``pipeline`` 需要 pymupdf，
导入本包本身应当没有副作用。命令行入口见
``python -m examdata.edexcel_papers``。
"""
