# Zaxaerith 系及抽样 docx/pdf 文件头抽检（2026-10-04）

方法：`head -c 8 file | xxd`；有效 OOXML/ZIP 以 `PK\x03\x04` 开头；异常头统一为 `59aae78a782daee9`（非 OOXML，无法解压；约 180KB 的同类封装）。

| 仓库 | 文件 | 大小(B) | 头8字节 | 判定 |
|---|---|---|---|---|
| Zaxaerith/GaokaoENG | 2024年新课标I卷英语.docx | 37066 | 504b0304… | 有效 |
| Zaxaerith/GaokaoENG | 2024年新课标II卷英语.docx | 32820 | 504b0304… | 有效 |
| Zaxaerith/GaokaoENG | 2024年浙江1月英语.docx | 69634 | 504b0304… | 有效 |
| Zaxaerith/GaokaoENG | 2024年九省联考英语.docx | 80201 | 504b0304… | 有效 |
| Zaxaerith/GaokaoENG | 2024年甲卷英语.docx | 180059 | 59aae78a782daee9 | **异常** |
| Zaxaerith/GaokaoCHN | 2024年新课标I卷语文.docx | 33886 | 504b0304… | 有效 |
| Zaxaerith/GaokaoCHN | 2024年九省联考语文.docx | 180058 | 59aae78a782daee9 | **异常** |
| Zaxaerith/GaokaoCHN | 2024年新课标II卷语文.docx | 180058 | 59aae78a782daee9 | **异常** |
| Zaxaerith/GaokaoGEO | 2024 全目录 10 个 docx（早前抽检） | ~180KB | 59aae78a782daee9 | **全部异常** |
| qingshuo | 2026西北高考历史.docx | 18414 | 504b0304… | 有效 |

结论：Zaxaerith 系 docx 质量混合——ENG 5 个中 4 有效 1 异常；CHN 3 个中 1 有效 2 异常；GEO 全目录异常。
异常文件**可正常下载**（GitHub API size 与下载一致，仓库原始即如此），但**无法作为文档打开**，属仓库质量问题。
使用建议：批量采集后需逐一校验文件头（`PK`/`%PDF`），剔除异常文件。
