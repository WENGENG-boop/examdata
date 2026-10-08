# 可直接复制给执行Agent的提示词

下面横线之间为完整提示词。三份文件必须保持在相同目录；执行Agent应能访问整个工作区及已保存的本地证据。

---

请在 `C:/Users/weo/Desktop/api` 实际实现雅思完整题库、分类、题目与答案匹配以及听力音频与题目匹配。你是执行Agent，要改代码、跑验证、输出真实结果，不是只提出建议。

首先完整读取以下两份Markdown，不要只读摘要：

1. `C:/Users/weo/Desktop/api/docs/ielts/IELTS_COMPLETENESS_AUDIT_20261003.md`
2. `C:/Users/weo/Desktop/api/docs/ielts/IELTS_REPAIR_IMPLEMENTATION_PLAN.md`

以计划S01–S17为操作顺序，每一步都落实文件、算法、数据、测试和证据。用 `docs/ielts/EXECUTION_CHECKLIST.md` 持续记录进度；遇到限制保存checkpoint、列出精确缺口，继续完成不依赖该限制的步骤，不自行删减范围。无需重复询问已在计划中确定的目录、数据范围、接口语义或技术边界。

必须解决报告A01–A16全部问题，尤其：

- 全部21册每册4套的Academic阅读/听力，及原书实际包含的General Reading、Writing、Speaking；逐册建立有证据的预期清单，不能默认所有版次都是40题，也不能因抓不到某套就从分母删除它。
- 空LI/缺答案不移位；剑1T2听力41题、剑3T2–T4完整试卷题目、剑10T1阅读Q34空答案；所有题组、选项、三篇正文、地图/图表资产与字数限制。
- 剑21多选组的inputs/accepted sets和真实题型；147个答案键不能直接称为147题，不能凭数组长度凑160个答案。
- 统一分类和查询；题目—答案按完整身份、编号、组语义、原文依据连接，严格拒绝单字母子串匹配，保留跨源冲突、原值及裁决来源。
- 听力音频先验证实际文件和题本身份，再匹配Part和题号；时间戳必须校验音频hash及时间基准。逐题对齐使用计划中的候选/上下文/动态规划与本地对齐工具协议，不按题号均分时长，不以答案同词出现冒充正确证据。缺工具、模型或可靠标签时记未验，不生成假的verified区间。
- 修复标准CLI、Node HTTP、FastAPI雅思路由选源；剑21音频、剑20PDF分册、阅读单篇与整卷语义必须一致；四个失败音频对象、空questions或单篇回落不能再算完整。
- 修复原文逐Part回落及截尾检查，建立持久raw/provenance/cache/checkpoint，保留完整的题目→答案→音频→证据版本链条。
- 保留此前45条裁决和7条窄修正，不破坏已修复的参数校验、并发及取消回收。历史报告不是当前全题通过证据。

数据与操作边界必须遵守：主业务在 `C:/Users/weo/Desktop/api/ielts-api`，FastAPI只改雅思模块和雅思测试；雅思新数据用独立 `ielts-data`及 `EXAMDATA_IELTS_DATA_DIR`。不要改CIE/Edexcel、生产数据库、现有前端或历史证据，不恢复CIE停止批次，不重启8000现有服务，不推送或部署。新服务验证用TestClient或独立端口。下载优先复用本地PDF/raw/音频，严格执行请求与字节预算、来源失败停止和恢复规则。

另一副本 `C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api` 仅按S16逐文件备份与同步；如它出现新的独立修改，保留并记录冲突，不整目录mirror、不删对方独有文件。

不要生成占位题目、猜测标准答案、全局替换OCR字符、放宽比较器、复制同一个音频四次或只改文档来“做满”完成度。Writing/Speaking为开放题，样例答案不能标唯一标准答案。缺少原书内容时明确source_missing/unverified，需要外部资源或独立核验时列出具体identity、页、题、音频及原因。

完成后必须交付：

1. 按计划修改后的实际代码、受控刷新/审计工具和规范化接口。
2. `docs/ielts/EXECUTION_CHECKLIST.md`，S01–S17逐项状态、命令、退出码、证据。
3. `docs/ielts/IELTS_IMPLEMENTATION_RESULT.md`，A01–A16逐项修复结果、两副本hash、测试与独立进程实测。
4. `docs/ielts/IELTS_REMAINING_GAPS.md`，逐册逐套逐题/组/Part的缺失、冲突、未官方核验、未音频对齐项及可执行下一步。
5. 全量coverage JSON/Markdown、逐题答案状态、音频身份及对齐状态、原始证据与恢复checkpoint，并给出准确路径。

最终回复分清代码实现完成度、真实数据完成度、答案正确性核验和音频逐题对齐完成度。所有指定算法/接口回归必须执行；真实媒体与官方全题核验未完成就标partial/not_run，不把mock、链接可生成、HTTP200、数组长度或score5/5写成全量验收通过。报告问题对照表有漏项就继续工作或明确blocked，不能无说明结束。

现在从S01开始执行。

---
