# 雅思完整题库与匹配算法修改计划（逐步执行版）

日期：2026-10-03。输入报告：同目录 `IELTS_COMPLETENESS_AUDIT_20261003.md`。

## 0. 执行约定与完成定义

本计划给只按步骤工作的Agent使用。**按S01到S17顺序执行，不跳过附件、旧版、组题、分类、失败路径或文档同步。** 报告A01–A16的对应关系在末尾。当前任务是实现和验证；遇到无法获得的资源、无法核实的官方答案、无法验证的音频时间轴，写明blocked/partial和原因，继续可独立完成的步骤，不伪造“全题完整”。

主工作区固定 `C:/Users/weo/Desktop/api`，主业务代码为 `ielts-api/`，FastAPI仅改 `examdata/src/examdata/api/ielts.py` 及雅思专用测试。另一副本固定 `C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api`，仅在S16同步明确本次修改的共有业务文件，不能删除对方独有文件。

允许新增以下范围：`ielts-api/tools/`、`ielts-api/tests/fixtures/`、`ielts-api/tests/*ielts*.test.mjs`、下文明确的 `.mjs`模块、`examdata/tests/test_ielts_*.py`、`docs/ielts/`和运行产物`ielts-data/`。如需依赖清单，新增ielts-api的package.json/lock或局部alignment依赖清单；如已有则保留原依赖并增量修改。允许根`.gitignore`新增仅`ielts-data/`及局部虚拟环境规则。

不修改CIE/Edexcel业务、生产数据库、现有前端或历史证据；不清理原PDF/图片/冲突文件；不重启8000现有服务；验证新网关用TestClient或独立可用端口。现有前端没有雅思完整练题流程，本次API/算法任务不顺带制作前端。无推送、部署和外部消息动作。

最终必须分别给出：

1. 实现状态：代码、接口、测试、同步是否完成。
2. 数据状态：每册/每技能/每套的expected/observed/verified/gaps。
3. 答案状态：identity_linked、source_verified、official_verified、conflict、missing的分布。
4. 音频状态：URL候选、已下载解码、内容身份验证、Section匹配、逐题verified对齐的分布。

只有实际检查过的维度才可标为verified。开放写作/口语不适用唯一答案，不能作为缺标准答案扣分，也不能编造标准答案。

## S01. 建立备份、基线和任务账本

执行目录根路径。在PowerShell运行：

```powershell
Set-Location 'C:/Users/weo/Desktop/api'
rg --files -g AGENTS.md
Get-Command node,py,python -ErrorAction SilentlyContinue
node --version
```

读取适用AGENTS（若有）；读取报告及所有A项对应的代码，尤其pte/cam21/lfs/ito/iprog/zhan、ielts-api/CLI、FastAPI网关及现有测试。读取 `tmp_audit_ielts/completeness_20261003/summary.json`、`offline-findings.json`、`local-checks.json`、最新repair报告与45项裁决。不得重跑旧扫描脚本覆写历史文件；其中很多写死另一个副本或原证据路径。

新增 `ielts-api/tools/baseline.mjs`，生成 `ielts-data/runs/<UTC时间>-repair/baseline.json`：node/Python可用版本、工作区、共有文件SHA256、副本差异、实际网关目录配置（只读必要非敏感配置）、既有git状态（非git仓库照实记）、现有8000的/info快照。复制**每个将修改的文件**到本次run的backup相同相对路径；后续首次改新文件前继续补备份。

新增 `docs/ielts/EXECUTION_CHECKLIST.md`，每步字段固定：id、status=pending/running/done/partial/blocked、files、command、exit_code、evidence、gaps、next_action。每完成一步立即更新。开始时跑基线：

同时生成 `protected-files-baseline.json`：读取实际CIE/Edexcel代码目录并登记文件清单与SHA256，登记生产数据库路径、大小、mtime及可安全读取的hash；不扫描密钥或输出数据库内容。S16用此基线检查非干涉。运行中的数据库可能独立变化，记录该边界；本任务禁止写入其路径。

```powershell
node --test .\ielts-api\tests\contract.test.mjs
$env:EXAMDATA_DATABASE_URL='sqlite:///:memory:'
$env:EXAMDATA_DATA_DIR='C:/Users/weo/Desktop/api/ielts-data/test-examdata'
$env:EXAMDATA_IELTS_DIR='C:/Users/weo/Desktop/api/ielts-api'
$env:EXAMDATA_TEST_LIVE='0'
& .\examdata\.venv\Scripts\python.exe -m pytest .\examdata\tests\test_api_ielts.py .\examdata\tests\test_ielts_concurrency.py -q
```

保存stdout/stderr/退出码；环境变量只在执行进程内设置，不永久改系统配置。当前参考为9个不同Node测试通过、Python6通过1跳过；以实际基线为准。失败先记既有失败，不删除测试或掩盖错误。S01产物齐才进入S02。

## S02. 先建立可验证的预期清单和覆盖分母

新增 `ielts-api/catalog.mjs`、`ielts-api/schema.mjs`、`ielts-api/data/expected-manifest.json`、`ielts-api/tools/build-manifest.mjs`。

清单每项包含：book、edition、variant=academic/general/shared、skill=reading/listening/writing/speaking、test、part/passage、expected_numbers（明确数组）、expected_groups、expected_assets、evidence（PDF哈希、1-based文件页与印刷页、标题/来源段落）、status=verified/unverified/not_in_book、reason。

先登记1–21册每册4套的Academic阅读和共用听力84+84组合；**每套的expected_numbers从原书和独立目录核验，不直接40循环代替官方结构。** 剑1T2听力先录1–41，PDF文件第45页为Q40–41证据。其余老版也要核查题号与Part范围，不默认四段各10题。每套Academic阅读的三篇、听力四Part的存在和题号范围独立记录；四套编号也是预期，不靠某个来源目录成功来删掉失败套。

同时逐册登记General Reading、Writing两任务、Speaking各部分的实际书内范围。若整书不包含该技能/版本，用有证据的not_in_book；如果资料未查清用unverified，不能当not_in_book。早版A/G共书与后版分书不得混身份。不假定所有册都有同样口语套数，不拿外部2026题库冒充剑桥原书。与本报告21×4范围以外的mini-ielts等单列external，不混入剑桥覆盖分母。

采用节点身份：`series=cambridge_ielts + edition + book + variant + skill + test + question_number`；Part/Passage为该节点属性，组ID与assetID另定义。公开稳定ID示例 `cambridge:17:academic:reading:T4:Q38:<edition>`。版次未知不能与已知版合并；shared听力不能因A/G目录重复计数。

schema定义枚举状态：missing/partial/available/verified/conflict/unverified/not_applicable；verified必须有证据引用。运行时schema校验拒绝重复ID、非预期题号、引用不存在的group/asset、错误skill/type组合；发现缺题不靠schema抛掉整份可用结果，返回validation_errors与coverage。

验收：manifest测试包含41题旧版、不同Part范围、共享听力、A/G隔离、unverified分母、不存在技能；任何unknown不被算作complete。

## S03. 建立不可变raw与版本化结果存储

新增 `ielts-api/data-store.mjs`、`ielts-api/fetch-source.mjs`。默认数据目录为工作区`ielts-data/`，支持独立 `EXAMDATA_IELTS_DATA_DIR`覆盖，**不可复用EXAMDATA_DATA_DIR**。

目录固定：

```text
ielts-data/
  raw/<source>/<sha256>.body
  raw/<source>/<sha256>.meta.json
  pdf/<sha256>.pdf
  audio/<sha256>.<extension>
  assets/<sha256>.<extension>
  normalized/<schema_version>/<dataset_revision>/<test_id>.json
  indexes/<dataset_revision>/questions.json
  manifests/<dataset_revision>/coverage.json
  decisions/<decision_id>.json
  runs/<run_id>/{checkpoint.json,requests.jsonl,errors.jsonl,backup/}
```

meta保存source URL/最终URL、UTC拉取时间、HTTP状态、content type、etag/last-modified、字节数、SHA256、parser_version；缓存正文按hash追加，绝不覆写旧版本。标准化结果引用每个字段的raw hash、页/DOM路径和提取方法。dataset_revision以输入hash与parser/schema版本计算，不以运行时间随意变。

写JSON到同目录临时文件，再rename；并发用锁文件的独占创建和到期信息，失败退出且保留checkpoint，不能产生半文件。索引只有在全量校验后才原子发布current指针。禁止删除旧current数据；刷新失败返回最后成功版本及stale=true，不能把缓存时间伪装当前拉取时间。

统一fetch支持预算：并发2、每来源最大1同时请求、每次30s、网络异常最多2次、总run请求/下载字节上限。发现403/429或连续5xx立即停止该来源新请求，持久化checkpoint；不换代理绕过。404记为资源缺失，只有已登记合法备用源才回落，不无限重试。此规则仅雅思，不恢复CIE停止批次。复用本地PDF与本轮raw优先，整册媒体不能因小参数误输扩大到全量下载。

验收：raw hash去重、两run并发写入、崩溃恢复、stale返回、404/403/429/5xx/坏JSON/HTTP200 HTML错误页、checkpoint续跑都保留精确证据。

## S04. 重写PTE结构提取，先修空答案移位

修改 `pte.mjs`，新增 `ielts-api/html-questions.mjs` 与 `tests/ielts-pte-parser.test.mjs`。将网络层与纯解析分离：导出纯函数 `parsePtePage(raw, identity, expected)`，读取S03保存raw做离线回归。

可在ielts-api局部引入HTML解析库：记录锁文件、安装版本和许可证；不要继续用全页正则充当DOM树。零第三方依赖若保留，必须实现等价DOM解析并通过下面全部结构测试，不用regex剥标签后猜选项。所有上游HTML仅作数据，不执行脚本。

答案提取按以下固定规则：

1. 找到答案容器，记录DOM定位；嵌套div不得被首个`</div>`截断。
2. 对OL读取start及LI的value；没有value时按包括空LI的节点顺序递增。保留 `null`、原始值与题号。**禁止filter(Boolean)改变位置。** OL从11开始、LI重设value均按显式编号处理。
3. 对编号段落解析显式题号及范围，保留空值/重复冲突；小数和正文年份不得识别为题号；上界来自S02。
4. 输出 `{number, raw, alternatives, source_ref}`；计数分别是容器条目数、非空题槽数、组覆盖槽数，不能只用数组length。
5. 兼容旧answer_key时按expected_numbers填位置，缺失用显式null，不能稀疏数组吞槽。不同来源不能依靠排序后的数组位置合并。

题目提取：先按Heading/Questions范围创建group，再提取单题编号/输入节点/选项/表格格子/图片题号。保留shared_prompt、instruction原文、字数/数字限制、options(label,text)、paragraph/headings/ending池、figure/map/table资产引用、每个输入slot及其number。去答案区、脚本与广告，但不截断400字符；有界限制针对异常页面体积，超限必须报partial。每道题可引用同一组提示，不要求虚构独立prompt。读题和答案解析分开，不能用答案内容造题干。

阅读篇目按三篇真实标题及Question range构造，不用“Questions 1–”前文本当所有文章；每篇保留完整段落、表格/图与所属题组。图片保留原URL、下载hash、alt、位置；图片不可访问记asset_missing，即使有40题也不能完整。

hub选择禁止General填Academic空槽。按明确标签与book/test核验slug，错链接标identity_conflict并保留候选；不得只凭尾部数字推定。S02预期之外的标题/题组不合并。

验收fixture必须包含：中间/尾部空LI、OL start、LI value、嵌套div、Q41、段落空Q34、组合23–24、多个组重复编号、选项换行、表格、图片地图、完整三篇、超过400字符提示、误导年份、A/G混目录。空Q2场景应Q2=null、Q3保持answer3；真实剑10T1Q34仍为空时明确missing，不填猜测。

## S05. 修复cam21及其余适配器的组题和标准输出

修改 `cam21.mjs`：reading解析GROUPS/HEADINGS/ENDINGS/QUESTIONS/ANSWERS并连接g/p/id；T2Q20多选组和Q21 slot按原始组定义恢复，保存组指令与选项。listening从PARTS DOM提取填空、radio/checkbox、data-q与组题范围，不能全部标gap。multiCorrect.inputs建立显式group与slots，保留accept集合及required_count，不把`join('')`后的字母串当普通单题答案。TRANSCRIPTS保留原始文本、time单位和说话人缺失，不能从source名称推定“官方且完整”。

修改reader/TaroFlink/ITO/iprog/zhan包装：统一number/q_num、part/section、type、instruction、accepted variants、audio引用与provenance。无题目的iprog输出skill=listening/answer_only，不能ok=true就成为完整QA。zhan提供精读，不提升为答案权威；ITO宽泛数字正则改为答案区域明确编号提取。保留TaroFlink timestamps但默认alignment_status=unverified，待S10核验音频hash。

cam21的JS数据解析器继续仅解析受限数据字面量。不得eval/执行上游JS；对模板表达式、函数、正则等非数据表达式报unsupported_literal并保留raw。加注释、转义、Unicode、尾逗号、括号嵌套、`__proto__`键测试，使用Map或安全字典防原型污染。

验收：剑21四套听力147个答案组键通过slots精确覆盖各40题；所有选择题有选项且type正确；T2阅读组slots覆盖Q20/Q21，组提示可呈现。若源本身缺内容必须从下一步骤补，不能为了计数创建假条目。

## S06. 从已有PDF补题并独立提取官方答案

新增 `ielts-api/tools/pdf_extract.py`、`ielts-api/pdf-adapter.mjs`、`ielts-api/tools/import-pdf.mjs`、`tests/fixtures/pdf-expected/`。Python先使用已有 `.venv`中PyMuPDF；若需要OCR，在`ielts-data/tools/`建立局部环境及锁定依赖，不修改examdata共享环境。记录依赖版本；已有文本层先读取布局，不对所有页盲目OCR。

按S02 manifest定位：书内标题→Test→skill→Part/Passage→Questions范围→题组/图表→官方答案页。页数只作为定位辅助，file page与printed page分别保存。扫描页OCR输出字框与置信度，结果必须与页图/官方答案独立核验；纯图像无法核实的内容保持needs_review。

题干、选项、题组指令与图表从**题目页**提取；答案从**答案页**提取；transcript不能替代试卷题干。PDF图表/地图保留原页或裁剪资产、旋转与bbox坐标系统，检测跨页组和表格续行。对现有CIE bbox实现可只读参考，不修改它。

必须补以下明确清单：

- 剑3T2–T4完整听力题干、组选项、图表和四Part范围；iprog仅答案候选。
- 剑1T2听力Q40/Q41及其图表、官方答案，独立核验该套全部expected slots。
- 剑10T1阅读Q34官方答案与选项，解决源空值；无法核实时保留missing。
- 本轮live-matrix所有missing slots；先查是否组题覆盖，再查原HTML/PDF真实题目，不能把组题重复成多份。
- 剑21阅读T2组题及四套听力选择题，与JS原始结构交叉核对。
- manifest登记的所有Writing/Speaking/GT书内内容，见S08。

本地book1–19已存在优先复用并重新hash。book20本地仅Test1；通过BOOK20_TESTS获取2–4候选，逐分册校验LFS oid（若有）、PDF magic、可读页和Test身份、题目/答案/原文范围；四分册完整不自动等于所有附录齐。剑21镜像需要真实下载/读取验证或标unverified，不能信硬编码146页。所有下载明确目标和字节预算，不默认重新下20册。

把旧 `official_pdf_cmp_v3.py` 当提取参考；其错误比较器不要作为验收裁判。新增独立gold fixtures，每个答案/题组有PDF哈希+页+上下文；测试期待值不得由被测parser生成。抽取器适配需覆盖老版、双栏、续行、扫描页、字母选项、无序多选，不强制一个OCR全局字符替换规则。

新增 `ielts-api/tools/compare-official.mjs` 调用S07严格比较器，接收PDF候选与normalized答案并输出逐题match/conflict/unverified；CLI与新审计工具全部改用它。旧脚本位于历史证据目录，保留不覆写，在新文档明确标为历史提取参考、禁止用于新的正确性验收；不得留下新工具继续调用旧match_one的路径。

验收：上述固定缺口有对应真实页证据；PDF无法核实的所有项逐项写review队列。不得删除官方提取与来源冲突的原始值。

## S07. 实现题目—答案连接与冲突裁决算法

新增 `ielts-api/answer-matcher.mjs`、`ielts-api/adjudications.mjs`、`tests/ielts-answer-matcher.test.mjs`。

接口固定 `matchAnswers({questions,groups,answerCandidates,identity,expected,decisions})`，返回每题/组答案、状态、rule_id、候选、source_refs、conflicts和coverage。

算法顺序固定：

1. identity gate：edition/book/variant/skill/test完全一致，question number位于expected及其group；不一致候选拒绝并保留rejection原因。源标签缺版次用unverified，不跨版本自动串联。
2. 显式number或group.inputs关联。无显式编号的顺序答案仅允许该DOM容器顺序已验证、start/value正确、空位保留且长度符合manifest时挂接；不满足时order_unverified，不靠下一个非空值补位。
3. 保存raw。规范化只做Unicode NFKC、trim、重复空白、弯直引号、可配置大小写；可选词、单复数、数字/单位、日期变体必须由该答案键的明确允许形式或可追溯规则生成。不得任意删数字、单位、词语或模糊纠错。
4. 选择题字母仅与题组options标签严格比较。答案文本只有与该组选项全文规范化相等且唯一时映射到字母。单字母E不能因为单词含e判相同，禁止子串包含及token子集判正确。
5. TFNG与YNNG分别标准化枚举，不互相混同；Roman heading标签单独处理。
6. 多选/无序配对保存 `group_id, input_numbers, accepted_sets, required_count, ordered, allow_reuse, scoring`。无序按明确规则比较集合/多重集合，保留数量和重复约束；不排序后硬分配唯一正确题号；ordered组才逐位置比较。组结果引用所有输入槽，组计一次但covered_numbers按各slot算。
7. 来源优先级：有视觉核验的原书答案键/裁决 > 已核验该版次的结构化来源 > 未核验来源。OCR候选不能因名叫official就直接覆盖。优先级只选display candidate，冲突未裁决前status=conflict，不能改verified。多个镜像同一上游不算独立双源证明。
8. 保留已有45条裁决与7条修正，按完整identity+raw hash/原值守卫应用；新增decision含question/group IDs、from/to、PDF哈希/页、理由、验证者类型与验证方法、时间。上游值变动则decision_stale，保留旧记录，不能继续强套修正。

区分 `identity_linked`（题号连接）、`source_verified`（来源结构与身份检查）、`official_verified`（独立原书核验）。答案挂上了不等于答案正确。暴露原值、显示值、accepted variants及适用字数限制；组评分可支持练题，但开放题不走此算法。

验收必测：空LI不移位；Q34/Q41；E与research methods不匹配；A与uncooperative landlord不匹配；真实完整选项文本能映射；6/Six需有允许变体；IN ANY ORDER准确数量和重复；both required与任选不同；A/G同题号不互串；source hash变化使修正失效；无答案题不伪造；错OCR不自动成权威。

## S08. 完成分类、完整呈现与其他书内技能

新增 `ielts-api/taxonomy.mjs`、`ielts-api/question-index.mjs`、`tests/ielts-taxonomy.test.mjs`。

统一基础字段：id、identity、skill、variant、book/test、part/passage、number、group_id、prompt、shared_prompt_ref、instruction、constraints、options、assets、answer_ref、audio_alignment_ref、source_refs、content_status、answer_status、classification_status。

type枚举固定：multiple_choice_single/multiple_choice_multiple/true_false_not_given/yes_no_not_given/matching_headings/matching_information/matching_features/matching_sentence_endings/form_completion/note_completion/table_completion/flow_chart_completion/summary_completion/sentence_completion/diagram_labeling/map_plan_labeling/short_answer/writing_task1/writing_task2/speaking_part1/speaking_part2/speaking_part3/unknown。

分类优先依据来源明确type+组指令，映射为taxonomy；冲突不靠答案格式猜。不能自动判断的unknown带原因进入review。topic标签可选且标source/inferred，不能成为题型完整性的依据。分类索引按以上技能、variant、册、套、Part/Passage、type、状态过滤；返回分页及total，不扫描后错误分页。

Writing从题目页提取完整任务指令、图/表/地图和字数要求，Task1/2分开；model/sample answer独立标sample，answer_mode=open_response，不参与标准答案正确性统计。Speaking提取P1真实问题、P2 cue card所有bullet与时间要求、P3问题，保留同一话题关系；书内无该内容需manifest证据。General Reading有独立篇/section与题号结构、独立API variant，不能挪Academic数据充数。

题目完整呈现的校验规则：选择题必须有可呈现选项，匹配题有选项池，图表题有可访问本地asset，填空有提示和输入slot，组题有共享instruction/constraints，阅读引用完整正文。question.prompt为空但有完整可呈现的group共享内容可有效；二者均无则missing_prompt。PDF页图可作为完整视觉来源，但需标presentation=page_image，结构化slots未恢复时仍partial。

验收：各type至少一个有独立期望的fixture；分类搜索中文/英文skill/type名称映射到固定枚举；GT与Academic隔离；开放题answer_mode正确；失效资产、丢选项、unknown分类进入缺口，不算fully_complete。

## S09. 音频下载验证与整套/Part身份匹配

新增 `ielts-api/audio-catalog.mjs`、`ielts-api/tools/verify-audio.mjs`、`tests/ielts-audio-catalog.test.mjs`。

建立audio记录：audio_id、identity、scope=full_test/part、part、raw URL/备用URL、content_sha256、bytes、container/codec、sample_rate/channels/duration、fetched_at、file_path、identity_status、verification_refs。链接构造只返回candidate；下载解码成功只到available；内容身份经录音开头/Section转场与题本核验后才能verified。

本机工具查找ffprobe/ffmpeg（PATH及Codex bundled路径）；没有时在局部tools目录准备工具或明确blocked，不将HEAD Content-Length冒充可播放。验证实际字节、magic/容器、解码、时长、非HTML/零长度，支持HTTP206但必须检查Content-Range/内容不能把300字节探测当整文件。全文件哈希与decode属于完整下载检查；小Range仅probe状态。

音频选源：剑21用cam21的对应Section音频；1–20优先已核验分Part的maslow，备选PTE整套音频与book20其他候选。若只可用整套，在源音频上建立四Part区间，不能把同一全套URL当四个独立Part成功。URI/CDN不同但hash相同合并同一audio_id；不同hash分别核验，旧对齐不得自动继承。

匹配顺序：身份标签/路径核验 → 开头Book/Test/Section语音或可信题本+原文首尾锚点 → transcript与实际音频内容的一致性 → 确认该Part实际question range。路径相同/文件名相同不够验证内容；两个相似话题也不能互替。官方题号和回答位置只能来自S02/S06。

下载按需只对S02期待音频与明确候选执行，最大2任务并行，持久checkpoint；优先复用已有样本与hash正确文件。先跑剑1T2、剑3T2–T4、剑20T2P4、剑21T1/T2，再全量84套/各Part。记录每Part至少一个可播放且身份verified的资源，否则本套audio_complete=false。

验收：剑21通用路由选对音频；4个ok:false数组不能算成功；mp3 URL返回HTML/404/错误书/同一URL四次/音频被替换/只有头部字节都不能标完整。

## S10. 实现音频—原文—逐题的对齐算法

新增 `ielts-api/audio-matcher.mjs`、`ielts-api/tools/align-audio.py`、`ielts-api/alignment-provider.mjs`、`tests/ielts-audio-matcher.test.mjs`、`ielts-api/tests/fixtures/alignment-gold.json`。

接口 `alignQuestions({identity,questions,groups,audio,transcript,candidateTimestamps,config})`。输出每题/组：audio_id、part、intervals=[{start_sec,end_sec,role=instruction/question_context/answer_evidence}]、status=unverified/section_only/needs_review/verified/missing、method、confidence、evidence_refs、model_version。**无法对齐返回null/needs_review，禁止按题号均分音频时长。** 同一个无序组可共享interval而不强分到每字母。

执行顺序：

1. S09身份verified且hash固定才能进入对齐；S06题组/Part及范围确定。Section级关联来自题本而非固定Q1–10规则。
2. 将来源时间戳登记为候选，明确sec/millisecond及part-local/full-test时钟。使用多个真实内容锚点校验时间递增、duration边界、首尾词与录音相符。TaroFlink与reader的audio字段对应文件hash未确认前不直接接受timestamps。
3. full_test↔part音频采用首/中/尾至少3个文本/语音锚点估计offset；若播放速度不同用 `t_target = a*t_source+b` 最小二乘或分段映射，保存锚点残差。残差>1秒、非单调或不足3锚点则不迁移timestamp；不得只减固定开头提示秒数。
4. 没有可信时间轴时，用本地受控对齐工具得到word start/end。推荐实施入口固定Python工具协议：输入JSON包含本地audio路径、原文、language=en，输出JSON含words/start/end/confidence、模型与音频hash。工具通过create_subprocess_exec/spawn参数数组调用，不拼shell。全局API不上传题本或音频，不依赖付费AI服务。
5. 本地对齐环境单独建立于`ielts-data/tools/alignment-venv`；检测兼容Python（优先已有3.11/3.12），在局部环境安装并锁定经过测试的WhisperX及依赖，模型revision/hash写model-lock.json。先dry-run解析依赖，再安装，不改examdata现有Python环境。模型文件下载需明确来源及字节预算；工具/模型缺失或平台不支持写alignment_setup_blocked，算法和mock测试可继续，但不能宣称真实逐题对齐完成。禁止把占位返回当forced alignment运行证据。
6. 用局部ASR转录核查候选原文是否与audio相符，再对可靠原文forced align；若原文截断、遗漏或音频内容不同，不能强迫整份原文对齐。保留失败区间和coverage。只对已核验Part做词级对齐。
7. 从题组instruction、题干关键词和明确官方script `(Qn)`标记构造候选窗口； `(Qn)`只作候选位置，必须确认该标记来源。填空答案精确/允许变体出现在窗口内可作为证据，但多次出现必须联合上下文与题序。选择题使用选项语义及官方证据句，不把口播的诱饵选项当答案；若只有同词出现无可核实上下文，needs_review。
8. 多候选采用动态规划在同一Part内选择非递减窗口：代价=上下文匹配代价+与可信锚点距离+逆序/跳段惩罚。组共享区间允许重叠，单题不要强制互斥；分Part重置题序。保留候选及落选原因，不能靠单词命中直接verified。
9. confidence组成明确保存：identity_valid、clock_valid、text_anchor_score、aligner_word_confidence、ambiguity_margin。起始自动筛选门槛：锚点相似度≥0.90、关键对齐词confidence≥0.80、时间残差≤1s、最佳候选比次佳高≥0.15；这些只是needs_review筛选，**不是verified证明**，需要S10 gold集校准并记录阈值版本。
10. 在gold中覆盖至少12个真实Part（旧版/新版、full-test/part、四种题型、含组题/多次出现/口播干扰），每Part至少3个独立核验question/group窗口，覆盖首中末。标注人/工具身份如实写，Agent监听后核对不得称真人验收；没有可信独立标签不能升verified。要求verified窗口命中相关证据且没有跨题串位，gold起止误差≤1s；无答案的问答语境段以标注窗口为准。遗漏/不确定另外报告。

验收fixture包含：相同answer多处出现、错误音频hash、毫秒/秒混淆、full-test offset、变速、末尾越界、非单调、无时间戳、诱饵选项、多选共享窗口、旧版非10题段。单元测试验证状态和候选排序，真实gold评估验证声音对应；两者不能互相代替。

## S11. 按Part修复原文选择与跨源补缺

修改 `listeningScript`、readerScript、maslowScript、ITO包装与aggregate原文组织。新增 `ielts-api/transcript-matcher.mjs`、`tests/ielts-transcript.test.mjs`。

拉当前Test四Part候选，不为单套请求无条件拉整本全部16段。reader/maslow/ITO/cam21按identity和Part匹配，逐Part比对开头/结尾、章节范围与实际音频内容。文本长度、段数、省略号只是质量信号，不能作为完整证明。保存原文source与hash，完整段优先；补缺源必须身份一致，冲突进入review。

特别处理剑20T2P4：先查ITO对应套原文，再PDFaudioscript与实际Part音频；只找到文本没有音频时两个维度分别标状态。`format=raw, tests={}`必须保持unsegmented，不能生成ok=true空test text。声称16Part完整需各Part内容验证，不以全书≥40k字符判定。

验收：空test/raw、Part缺失、正文截尾、错误套、同Part多源冲突、广告/HTML错误页、四段全有但最后一句缺失；补缺后答案与audio_refs仍保持同版身份。

## S12. 重写统一聚合与完整度算法

新增 `ielts-api/resolver.mjs`、`ielts-api/coverage.mjs`，修改 `ielts-api.mjs`，现有导出尽量保持包装兼容。

resolver统一 `resolveTest(identity)`、`resolveReading(identity,passage?)`、`resolveListening(identity)`、`resolveAudio(identity,part?)`、`resolvePdf(identity)`。来源不适用先跳过，复用hub/raw缓存；pteListening返回的audio不再通过pteAudio重复抓同一页面。reader/zhan精读按三个Passage登记，单P1不能占整卷。

逐字段融合仅用S07 identity gate和裁决，不按来源ok优先整包覆盖更完整来源。阅读整套保留三篇；听力保留四Part、题组、答案、原文、有效音频及对齐；PDF按整册/分套/附录scope输出。失败保存source attempt error、status、raw ref并生成机器可读warnings，不静默吞Promise rejection。

coverage至少输出：expected/observed/verified numbers、missing_numbers、missing_group_members、missing_assets、missing_options、unknown_types、empty_answers、answer_conflicts、official_unverified、script_parts、audio_parts_available、audio_parts_verified、alignment_verified、pdf_scope、identity_conflicts、denominator_verified。

定义：content_complete=所有manifest期待题/组/正文/选项/assets齐且身份正确；answers_complete=标准答案适用slots非空且无冲突；answers_verified=所有适用slots有独立核验；audio_complete=期待Parts有可解码且身份verified音频；alignment_complete=所有期待题/组有verified对齐；fully_complete要求上述适用维度+题型明确+分母verified。未知/未核验一律不能fully_complete。open_response答案维度not_applicable；不存在的技能按manifest证据不进入分母。

旧score如保留改为availability_score并标deprecated；旧score字段仅兼容候选槽位指标，不能继续命名完整度。新增completion对象作为权威。剑3answer-only、reader单篇回落、4个失败音频对象、34页剑20T1不能给整套/整书fully_complete。

验收：上述所有假阳性场景离线端到端测试，以及全量normalized结果逐册coverage汇总。

## S13. 统一CLI、Node HTTP、FastAPI三种入口

修改 `ielts-cli.mjs`、`examdata/src/examdata/api/ielts.py`；新增 `examdata/tests/test_ielts_resolver_contract.py`、`ielts-api/tests/ielts-routes.test.mjs`。

逐入口落实：

- `reading`、`/api/reading`、FastAPI `/reading/{book}/{test}?passage=1..3`保留单篇语义，改走resolver；1–21都按所请求篇返回，有明确skill/variant和题号范围。整套用aggregate或v2 test，不能忽然将单篇改整套。reader已有enriched字段继续可访问。
- `listening-qa`、Node listening-qa、FastAPI listening全部走resolver listening；TaroFlink改为明确source专用入口/内部函数，别再冒充全范围。gte/pte源专用函数仍保留，返回来源真实状态。
- `listening-audio`三入口都走resolver，支持21；async调用必须await后send；保留part参数默认1，返回scope与验证状态。
- `pdf`三入口改resolver选LFS/zeeklog/cam21。book20返回分册清单或明确scope=test/Test1，不能把Test1 URL当整册。已有pdf-lfs/book20-set继续可用。
- aggregate、coverage和info更新到真实能力与证据时间；非法身份在任何网络请求前拒绝；未知CLI命令退出2；参数校验与有效HTTP语义继续兼容200+ok:false业务失败以及503/504/502基础设施失败。

新增规范化接口命名空间 `/api/v1/ielts/v2/`，独立Node对应 `/api/ielts/v2/`，CLI新增 `test-v2`/`questions-v2`/`coverage-v2`/`question-v2`：

```text
GET /books                    -> 有版次/variant/技能状态的目录
GET /tests/{book}/{test}?variant=academic -> 规范化完整套及coverage
GET /questions?book=&test=&skill=&variant=&part=&passage=&type=&status=&offset=&limit=
GET /questions/{question_id}   -> 题目、组、答案候选、audio alignment、provenance
GET /coverage                 -> 每册/技能/套的expected/observed/verified/gaps
GET /assets/{asset_id}         -> 只读本地受注册的图片/PDF/音频asset；支持音频Range
```

asset仅按注册ID映射文件，禁止任意路径参数；标注mime和hash、Range内容长度；缺失返回明确错误。所有新接口使用S03数据目录，不读写examdata题目数据库。query默认Academic、skill未给返回各技能但分页以question为单位，General必须显式选择；ID URL编码与非法参数测试。API失败状态体示例、字段说明与分页写文档。

本轮不加在线写刷新HTTP端点。数据拉取/刷新由以下受控CLI执行。新的接口未建数据时返回dataset_missing并说明CLI，不重新无界抓全部源。

验收：用离线fixture走CLI实际子进程、Node HTTP独立随机端口、FastAPI TestClient，比较同identity的normalized关键字段/coverage一致。live至少测1/3/10/19/20/21边界及单篇/整套语义、选源失败、非法参数fetch=0。不改既有服务进程。

## S14. 固化全量拉取、恢复和验收工具

新增 `ielts-api/tools/audit-all.mjs`、`ielts-api/tools/refresh.mjs`、`ielts-api/tools/build-index.mjs`。

约定命令（由执行Agent实现后逐项运行）：

```powershell
node .\ielts-api\tools\audit-all.mjs --offline --fixtures .\ielts-api\tests\fixtures --out .\ielts-data\runs\offline-audit
node .\ielts-api\tools\refresh.mjs --books 1,3,10,20,21 --variant academic --skills reading,listening --jobs 2 --max-requests 300 --resume
node .\ielts-api\tools\refresh.mjs --books 1-21 --variant academic --skills reading,listening --jobs 2 --max-requests 1500 --resume
node .\ielts-api\tools\refresh.mjs --books 1-21 --variant general --skills reading,writing,speaking --jobs 2 --max-requests 800 --resume
node .\ielts-api\tools\refresh.mjs --books 1-21 --variant academic --skills writing,speaking --jobs 2 --max-requests 800 --resume
node .\ielts-api\tools\audit-all.mjs --dataset current --verify-assets --verify-audio --out .\ielts-data\runs\full-audit
node .\ielts-api\tools\build-index.mjs --dataset current
```

CLI必须校验组合、枚举、册范围、并发、请求/字节预算，无参数默认只输出usage，**不默认触发全量媒体下载**。补`--max-bytes`并设置明确默认预算；触顶checkpoint/退出非0，不放宽上限继续。resume跳过已验证同hash成功任务，失败任务按规则继续，source变化重新生成revision。

全量必须检查168个Academic阅读/听力组合，且每套三篇/四Part以及所有manifest期待题/组/assets；GT/Writing/Speaking按实际manifest范围，不按数字凑数量。输出矩阵JSON+Markdown、errors、每题provenance与answer/alignment状态。full-audit对真实媒体验证按checkpoint执行，不把URL统计当download验收；媒体下载未跑要标not_run，不得命令退出0误导已验。

全量exit：0=所要求检查全部通过；1=存在真实缺口/冲突/未验证；2=参数/配置错误；3=来源停止/预算中断并有checkpoint。partial可保留成功数据但不能exit0冒充全覆盖。未完成媒体/模型依赖允许其他检查结束，但最终overall=partial。

## S15. 回归矩阵和验收清单

将S04–S13的fixture集中登记 `tests/fixtures/manifest.json`，含用途、独立期望出处、hash和读取入口。新增 `tests/ielts-e2e.test.mjs`、`tools/verify-decisions.mjs`、`tools/check-route-inventory.mjs`。

必须跑且保存退出码：

```powershell
node --test .\ielts-api\tests\*.test.mjs
node .\ielts-api\tools\verify-decisions.mjs
node .\ielts-api\tools\check-route-inventory.mjs
$env:EXAMDATA_TEST_LIVE='0'
$env:EXAMDATA_DATABASE_URL='sqlite:///:memory:'
$env:EXAMDATA_DATA_DIR='C:/Users/weo/Desktop/api/ielts-data/test-examdata'
$env:EXAMDATA_IELTS_DATA_DIR='C:/Users/weo/Desktop/api/ielts-data/test-fixtures'
$env:EXAMDATA_IELTS_DIR='C:/Users/weo/Desktop/api/ielts-api'
& .\examdata\.venv\Scripts\python.exe -m pytest .\examdata\tests\test_api_ielts.py .\examdata\tests\test_ielts_concurrency.py .\examdata\tests\test_ielts_resolver_contract.py -q
```

若PowerShell/Node未展开测试glob，工具枚举具体tests文件传入node，而非漏跑。若Node子进程隔离受环境限制，保留错误再用明确记录的`--test-isolation=none`，不能改测试期待值逃过问题。不要扫描另一个历史备份目录当独立测试套件。

必须覆盖的任务级案例：首次无数据、已有完整cache、坏cache文件、网络离线、刷新失败stale、并发两次刷新、源改内容/hash、题号41、缺答案34、空LI错位、剑3缺题、cam21多选inputs、图表资产失效、GT误映射、原文截尾、音频替换、时间单位/offset错误、错误选择题诱饵、source修正过期、非法CLI/network=0、进程超时/取消、旧接口兼容。

验证新接口的本地实际进程和下载asset Range；不只测试导出函数。听力真实gold运行记录每个Part音频hash、模型和评估结果。对未跑全项目套件照实标not_run，不把雅思绿测声称为整个examdata全通过。

**通过门槛**：所有指定离线算法/接口测试通过；45项裁决与7条修正保留/迁移且有守卫回归；全量清单没有隐瞒unknown/partial；真实音频对齐只有达到证据门槛才verified。资源缺口无法消除时交付功能与剩余清单，禁止声称数据全量验收通过。

## S16. 文档、另一副本和数据边界收尾

修改 `ielts-api/API.md`、`DEVELOPMENT.md`、`examdata/docs/IELTS_API.md`，修正SOURCES及各模块注释。清理“唯一”“1–20全部整本”“147条=147题”“10.7MB”“永不失败”等无证据说法；保留原审查报告作历史，不覆写它的时间和结论。新文档明确路由单篇/整套、A/G、open-response、来源/官方核验状态、完整度分母、音频验证和逐题区间语义，以及模型环境/数据目录/更新命令。

生成 `ielts-data/runs/<run>/changed-files.json`。同步到另一ielts-api副本仅包括本次业务/测试/文档变更文件，新增模块和依赖清单也同步；先逐文件备份对方原文件。如对方自S01基线以来出现新修改，**停止覆盖该文件**，记冲突，其他无冲突文件可继续。不能整目录mirror删除对方独有agg/证据文件，不同步ielts-data与局部模型环境。

同步后比较本次文件SHA256，分别在主副本和另一副本跑雅思Node测试。FastAPI仍指主副本；再次记录CIE/Edexcel受保护业务文件与生产数据库的hash/状态（数据库有运行服务写入时说明干扰，不能用hash变化直接归咎本任务）。检查当前8000仍在运行；不替它重启才能证明新代码，新代码的live校验用独立进程/端口。

## S17. 提交执行报告和未完成项

新增 `docs/ielts/IELTS_IMPLEMENTATION_RESULT.md`、`docs/ielts/IELTS_REMAINING_GAPS.md`，更新EXECUTION_CHECKLIST每步。

结果报告格式固定：实际工作区/数据revision/日期；修改文件；A01–A16逐项before/after/status/evidence；所有测试命令与退出码；逐册逐套覆盖矩阵链接；答案连接与官方核验分布；音频可用/身份/逐题对齐分布；同步hash结果；未运行检查；资源/模型/人工裁决缺口；精确恢复命令。

REMAINING_GAPS每行固定：identity、skill、question/group/Part、gap_kind、expected、observed、source attempts、raw/PDF/audio hashes、reason、next_step、needs_external_resource_or_review。分类unknown、缺选项/图片、未核实版次、未下载音频、未对齐都不能漏。

返回给用户必须同时报告“代码完成度”与“数据完成度”，真实未解决项不能统称resolved。若全部证据齐才写全量验收；否则清晰标partial，给已持久checkpoint和下一步，不要求用户重新描述范围。

## 问题—步骤对照（不得遗漏）

| 审查问题 | 必须执行步骤 |
|---|---|
| A01 通用路由范围失配 | S12、S13、S15 |
| A02 空答案错位 | S04、S07、S15 |
| A03 老版Q41和预期结构 | S02、S04、S06、S12 |
| A04 题干/选项/图表/三篇 | S04、S06、S08、S12 |
| A05 剑3答案-only | S05、S06、S07、S12 |
| A06 cam21及组题 | S04、S05、S07、S08 |
| A07 分类 | S02、S08、S13 |
| A08 空Q34/旧比较器/官方核验 | S06、S07、S14、S15 |
| A09 错音频及虚假可用 | S09、S12、S13、S15 |
| A10 逐题对齐 | S09、S10、S15 |
| A11 截尾/缺Part/raw空text | S06、S10、S11、S12 |
| A12 假完整度 | S02、S12、S14 |
| A13 PDF范围与宣称 | S06、S12、S13、S16 |
| A14 provenance/cache/重复拉取 | S03、S07、S09、S12 |
| A15 Writing/Speaking/General | S02、S06、S08、S13、S14 |
| A16 全链路验收 | S01、S14、S15、S16、S17 |

任何一项缺少对应结果，都不得宣称已经按计划完成。
