"""构建 CIE 逐科「考试发放资料」机器可读 JSON。

输入（只读）：
  - examdata/.data/syllabuses.json                     官方枚举 198 科
  - examdata/.data/discovery.json                      官方站点发现快照 2767 资源 / 196 科
  - tmp_materials_probe/evidence/addmaterials_by_subject.json   Nov 2026 附加材料清单解析（207 科）
  - tmp_materials_probe/evidence/verify_public_materials.json   官网 CI/Pre-Release 实测取回记录

输出：
  - examdata/src/examdata/materials/data/subjects_cie.json
"""

import collections
import json
from pathlib import Path

ROOT = Path(r"C:/Users/weo/Desktop/api")
EVID = ROOT / "tmp_materials_probe" / "evidence"
OUT = ROOT / "examdata" / "src" / "examdata" / "materials" / "data" / "subjects_cie.json"

CANDIDATE_LABELS = {
    "geometrical_instruments": "几何工具",
    "tracing_paper": "描图纸",
    "calculator": "计算器",
    "ruler": "直尺",
    "protractor": "量角器",
    "pair_of_compasses": "圆规",
    "plain_paper": "草稿纸",
    "coloured_pencils": "彩色铅笔",
    "standard_drawing_equipment": "标准绘图工具",
    "soft_pencil": "软铅笔（B/HB）",
    "eraser": "橡皮",
    "pen": "笔",
    "scissors": "剪刀",
    "sewing_equipment": "缝纫工具",
    "sewing_threads": "缝纫线",
    "tape_measure": "卷尺",
    "pattern_by_centre": "中心自备纸样",
}

REGISTRY = {
    "mf19_formulae_tables": {
        "name_zh": "数学公式与统计表（MF19）",
        "name_en": "Formulae & Tables (MF19)",
        "candidate_facing": True,
        "form_zh": "独立 PDF（官网公开发布）；考前随行政材料发到考点，考试时考点发给考生",
        "public_obtainable": "yes",
        "public_note_zh": "官网公开 PDF 可下载（实测 HTTP 200，sha256 复算一致）；统一接口可按需取回",
        "integrated": "yes",
        "integration_zh": "catalog 条目 cie-mf19-formulae-and-statistical-tables（access=public）；content 端点实测取回",
        "version_note_zh": "MF19 自 2020 年起适用（PDF 首页 'For use from 2020 in all papers'）；9709 syllabus 2023-2025 与 2026-2027 均引用 MF19，未见 2020 后换版证据",
        "evidence": [
            {
                "kind": "official-download",
                "ref": "MF19 官方 PDF（图片编号 417318，本地实拿）",
                "url": "https://www.cambridgeinternational.org/Images/417318-list-of-formulae-and-statistical-tables.pdf",
                "http": 200,
                "bytes": 311234,
                "sha256": "c075388ec7227fea086358f4332592a395a3c8d9c82b75890346f84cfc749d90",
                "pages": 16,
                "verified_at": "2026-10-04",
                "quote": "List MF19 / List of formulae and statistical tables / Cambridge International AS & A Level Mathematics (9709) and Further Mathematics (9231) / For use from 2020 in all papers for the above syllabuses.",
            },
            {
                "kind": "help-article",
                "ref": "help.cambridgeinternational.org 20756798012562",
                "url": "https://help.cambridgeinternational.org/hc/en-gb/articles/20756798012562-Which-list-of-formulae-do-candidates-use-for-the-AS-A-Level-examinations",
                "quote": "Candidates for the AS and A Level examination use the List of Formulae and Tables of the Normal Distribution (MF19) ... The MF19 list is sent out to Centres as needed in an administrative dispatch prior to the examination.",
            },
            {
                "kind": "syllabus-quote",
                "ref": "9709 syllabus 2026-2027 §1.4（本地文本）",
                "quote": "A list of formulae and statistical tables (MF19) is supplied in examinations for the use of candidates.",
            },
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：73 行涉及 9709/9231 各组件",
                "quote": "Formulae & Tables (MF19)",
            },
        ],
    },
    "answer_booklet_insert": {
        "name_zh": "随卷答题册（Answer Booklet provided with the QP）",
        "name_en": "Answer Booklet provided with the QP（含 RTL 变体）",
        "candidate_facing": True,
        "form_zh": "随试卷发放的答题册（部分以 insert 形式与 QP 绑定）；Nov 2026 清单 504 行 / 62 科",
        "public_obtainable": "partial",
        "public_note_zh": "官方对部分系列公开发布 insert/source material PDF（发现快照 179 份，例：0990 June 2024 Insert Paper 11 实测 HTTP 200）；并非每份答题册都有单独公开文件，逐组件核验未完成",
        "integrated": "partial",
        "integration_zh": "insert 类动态通道 /api/v1/materials/cie/in-paper（role=in|ir|ci）；逐卷可得性未验证",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单（抽样）",
                "quote": "Answer Booklet provided with the QP / RTL Answer Booklet provided with the QP",
            },
            {
                "kind": "official-download",
                "ref": "0990 June 2024 Insert Paper 11（官网实拿）",
                "url": "https://www.cambridgeinternational.org/Images/603004-june-2024-insert-paper-11.pdf",
                "http": 200,
                "bytes": 729313,
                "sha256": "5b7a729b1f44d7293354557ac53291e21659572cfef985cc38ff1fc9f027d2da",
                "pages": 8,
                "quote": "INSERT ... This insert contains the reading texts.",
            },
        ],
    },
    "mc_answer_sheet": {
        "name_zh": "选择题答题卡（Multiple Choice Answer Sheet）",
        "name_en": "Multiple Choice Answer Sheet",
        "candidate_facing": True,
        "form_zh": "考务材料：Cambridge 随卷发到考点；通用表格（Supplementary Multiple Choice Answer Sheet, Exam Day – Form 2a）官方提供电子版供下载打印",
        "public_obtainable": "yes",
        "public_note_zh": "通用表格官方可下载（实测 HTTP 200，129066B，sha256 复算一致）；非按科目文件（无 subject 级定位语义），统一接口按通用条目取回",
        "integrated": "yes",
        "integration_zh": "catalog 条目 cie-mc-answer-sheet（access=public，subjects=[]）；content 端点实测取回 129066B",
        "evidence": [
            {
                "kind": "official-download",
                "ref": "Form 2a 通用表格（实测取回）",
                "url": "https://www.cambridgeinternational.org/Images/86445-supplementary-multiple-choice-answer-sheet-exam-day-form-2a.pdf",
                "http": 200,
                "bytes": 129066,
                "sha256": "0e0156de5eca0d144805628d3bd0f3e8e54d7643d52bb6a3d58bda59596bacdc",
                "verified_at": "2026-10-05",
                "quote": "Supplementary Multiple Choice Answer Sheet (Exam Day - Form 2a)",
            },
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：265 行 / 52 科",
                "quote": "Multiple Choice Answer Sheet",
            },
            {
                "kind": "help-article",
                "ref": "help.cambridgeinternational.org 29566949506322",
                "url": "https://help.cambridgeinternational.org/hc/en-gb/articles/29566949506322-What-do-I-do-if-I-haven-t-received-Multiple-Choice-Answer-Sheets",
                "quote": "there are electronic copies of the Supplementary Multiple Choice Answer Sheet (Exam Day – Form 2) available to download and print from our website",
            },
        ],
    },
    "listening_file_alf": {
        "name_zh": "听力音频文件（Listening File ALF）",
        "name_en": "Listening File ALF",
        "candidate_facing": True,
        "form_zh": "听力考试音频（随考务发到考点播放）；Nov 2026 清单 85 行 / 24 科",
        "public_obtainable": "uncertain",
        "public_note_zh": "官方站点发现快照（2767 资源）未见音频文件条目；公开可得性未证实",
        "integrated": "no",
        "integration_zh": "未接入（无公开音频通道）",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：85 行 / 24 科",
                "quote": "Listening File ALF",
            },
            {
                "kind": "discovery-snapshot",
                "ref": "examdata/.data/discovery.json（2767 资源）",
                "quote": "doc_type 直方图无音频类条目（specimen/question/mark_scheme/source_material/examiner_report/confidential_instructions/other）",
            },
        ],
    },
    "instructions": {
        "name_zh": "说明文件（Instructions，随卷发放）",
        "name_en": "Instructions",
        "candidate_facing": None,
        "form_zh": "随卷发放的说明文件（多见于实践/实验与食品等组件）；具体用途未逐一核实",
        "public_obtainable": "uncertain",
        "public_note_zh": "未在公开发现快照中找到对应文件；是否公开未证实",
        "integrated": "no",
        "integration_zh": "未接入",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：93 行 / 22 科（含 0620/9701/9700/0610 等理科实践相关）",
                "quote": "Instructions",
            }
        ],
    },
    "role_play_cards": {
        "name_zh": "口语角色扮演卡（Role Play Cards）",
        "name_en": "Role Play Cards",
        "candidate_facing": True,
        "form_zh": "口语考试材料，考点领用（随卷/考前发放）；Nov 2026 清单 13 行 / 7 科",
        "public_obtainable": "no",
        "public_note_zh": "历年 Teachers' Notes/材料在 School Support Hub（需登录），非公开直取；发现快照未见对应公开文件",
        "integrated": "no",
        "integration_zh": "未接入（受登录保护，不绕行）",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：13 行 / 7 科（0510/0511/0991/0993/1120/8027/8028）",
                "quote": "Role Play Cards",
            },
            {
                "kind": "help-article",
                "ref": "help.cambridgeinternational.org 23016800587794",
                "url": "https://help.cambridgeinternational.org/hc/en-gb/articles/23016800587794-How-does-the-candidate-use-the-10-minute-preparation-time-for-the-Speaking-test",
                "quote": "You may find it helpful to view the past teachers notes booklets from previous series 2024 ... These can all be found on the School Support Hub.",
            },
        ],
    },
    "teachers_notes": {
        "name_zh": "教师用说明（Teacher's Notes）",
        "name_en": "Teacher's Notes",
        "candidate_facing": False,
        "form_zh": "口语考试教师材料（考点领用）；Nov 2026 清单 13 行 / 7 科",
        "public_obtainable": "no",
        "public_note_zh": "与 Role Play Cards 同源；School Support Hub 需登录",
        "integrated": "no",
        "integration_zh": "未接入（受登录保护，不绕行）",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：13 行 / 7 科",
                "quote": "Teacher's Notes",
            }
        ],
    },
    "pre_release": {
        "name_zh": "考前预发材料（Pre-Release）",
        "name_en": "Pre-Release（含 Clean Copy / SSH 等版本）",
        "candidate_facing": True,
        "form_zh": "定时公开的前置材料；Nov 2026 清单 13 行 / 3 科（0411 戏剧 / 0454 / 0994）；官方 xlsx（761208）逐组件确认 Pre-release 组件：0411/11-13、0454/11-13、0994/12",
        "public_obtainable": "yes",
        "public_note_zh": "官方站点公开发布 PDF（发现快照 5 份；0411 June 2024 Paper 11 实测 HTTP 200）；Pre-Release 属按考季定时释放的时间性文件",
        "integrated": "no",
        "integration_zh": "未接入：时间性文件（考前定时释放）；历史系列可经站点/发现快照取回，后续可扩展",
        "evidence": [
            {
                "kind": "official-download",
                "ref": "0411 June 2024 Paper 11 Pre-Release Material（实测取回）",
                "url": "https://www.cambridgeinternational.org/Images/521274-june-2024-paper-11-pre-release-material.pdf",
                "http": 200,
                "bytes": 1040666,
                "sha256": "f2e00ba0e2f425c52736a43e70f90c6828f345011fe422db6d06d5302ad69265",
                "verified_at": "2026-10-05",
            },
            {
                "kind": "discovery-snapshot",
                "ref": "发现快照列出 0411/0994/0454 的 Pre-Release Material PDF（例：703463-june-2024-paper-12-pre-release-material.pdf）",
                "quote": "June 2024 Paper 12 Pre-Release Material",
            },
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：13 行 / 3 科",
                "quote": "Pre-Release - Clean Copy / Pre-Release SSH",
            },
            {
                "kind": "official-xlsx",
                "ref": "Early question papers and pre-release material - November 2026（xlsx 761208，按单元格引用重解析）",
                "url": "https://www.cambridgeinternational.org/Images/761208-early-question-papers-and-pre-release-material-november-2026.xlsx",
                "http": 200,
                "bytes": 14926,
                "sha256": "186ff111ea60f85bb27794e4d1256507a7084c60e4b9437a5ede4dd19f52e037",
                "quote": "Type=Pre-release 组件：0411/11、0411/12、0411/13（SSH 日期 2026-02-01）；0454/11-13（DFD=Yes）；0994/12（SSH 2026-02-01）",
                "verified_at": "2026-10-05",
            },
        ],
    },
    "qp_special_format": {
        "name_zh": "特殊格式试卷（DFD / DIR / SSH 等）",
        "name_en": "Question Paper DFD / DIR / SSH",
        "candidate_facing": True,
        "form_zh": "按考务需求的特殊格式试卷（缩写全称未在公开清单给出）；Nov 2026 清单 15 行 / 9 科",
        "public_obtainable": "no",
        "public_note_zh": "按需提供，不在公开渠道发布",
        "integrated": "no",
        "integration_zh": "未接入",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：15 行 / 9 科（0400/6005/6089/6090/7048/9479/9481/9700/9709）",
                "quote": "Question Paper DFD / Question Paper DIR / Question Paper SSH",
            }
        ],
    },
    "cispecimens": {
        "name_zh": "实践样检材料（CISpecimens）",
        "name_en": "CISpecimens",
        "candidate_facing": None,
        "form_zh": "9700/31 生物学实践卷发放项；词义未在公开文档中核实",
        "public_obtainable": "uncertain",
        "public_note_zh": "未见公开文件；可能与保密须知（CI）通道相关，未验证",
        "integrated": "partial",
        "integration_zh": "或可经 CI 通道 /api/v1/materials/cie/in-paper（role=ci）覆盖；未逐项验证",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：9700/31 共 12 行",
                "quote": "CISpecimens",
            }
        ],
    },
    "source_file": {
        "name_zh": "源文件（Source File，ICT/计算机类）",
        "name_en": "Source File",
        "candidate_facing": True,
        "form_zh": "随卷发放的源文件；Nov 2026 清单 7 行 / 3 科（0417/0983/9618）；官方 xlsx（761208）另列 9626，标注考日前三天释放",
        "public_obtainable": "uncertain",
        "public_note_zh": "发现快照中 9618 等未见对应公开 source file；官方 xlsx（761208）标注 Source file（0417/0983/9618/9626）'Released three days before the test date*'（DFD 通告，需 final entries）——属考务定时释放，长期公开性未证实",
        "integrated": "no",
        "integration_zh": "未接入（无公开取回证据）",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：7 行 / 3 科",
                "quote": "Source File",
            },
            {
                "kind": "official-xlsx",
                "ref": "Early question papers and pre-release material - November 2026（xlsx 761208，按单元格引用重解析）",
                "url": "https://www.cambridgeinternational.org/Images/761208-early-question-papers-and-pre-release-material-november-2026.xlsx",
                "http": 200,
                "bytes": 14926,
                "sha256": "186ff111ea60f85bb27794e4d1256507a7084c60e4b9437a5ede4dd19f52e037",
                "quote": "Source file 行（0417/02、0417/03、0983/02、0983/03、9618/41-43、9626/02、9626/04）：'Released three days before the test date*'",
                "verified_at": "2026-10-05",
            },
        ],
    },
    "candidate_arf": {
        "name_zh": "考生记录表（Candidate ARF）",
        "name_en": "Candidate ARF",
        "candidate_facing": True,
        "form_zh": "考生填写/提交的记录表；Nov 2026 清单 4 行 / 2 科（0417/0983）",
        "public_obtainable": "no",
        "public_note_zh": "考务表单，不在公开渠道发布",
        "integrated": "no",
        "integration_zh": "未接入",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：4 行 / 2 科",
                "quote": "ICT Candidate ARF",
            }
        ],
    },
    "dvd": {
        "name_zh": "DVD 素材（媒体研究）",
        "name_en": "DVD",
        "candidate_facing": True,
        "form_zh": "随卷发放的音视频素材；Nov 2026 清单 6 行 / 1 科（9607 媒体研究）",
        "public_obtainable": "no",
        "public_note_zh": "不在公开渠道发布",
        "integrated": "no",
        "integration_zh": "未接入",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单：6 行 / 1 科",
                "quote": "DVD",
            }
        ],
    },
    "periodic_table_in_paper": {
        "name_zh": "元素周期表（印在试卷内）",
        "name_en": "Periodic Table (printed in question papers)",
        "candidate_facing": True,
        "form_zh": "理论卷与多选卷末尾印刷（随试卷 PDF 取回）；实践卷不发（官方问答口径，见下注）",
        "public_obtainable": "via-qp",
        "public_note_zh": "无独立文件；随试卷 PDF 一并公开（试卷本体经既有 papers 通道可取）",
        "integrated": "partial",
        "integration_zh": "catalog 条目 cie-periodic-table（delivery=in-paper；无独立 content 端点）",
        "conflict_note_zh": "官方口径并列（不调和，按原文记录）：帮助中心 19811608119826 说实践卷不含周期表；20295231545746 说 'All papers will contain ... a Periodic Table'（语境为 A Level Chemistry 理论卷）",
        "evidence": [
            {
                "kind": "help-article",
                "ref": "help.cambridgeinternational.org 19811608119826",
                "url": "https://help.cambridgeinternational.org/hc/en-gb/articles/19811608119826-Do-candidates-get-a-Periodic-Table-in-every-paper-Can-we-provide-candidates-with-additional-periodic-tables-to-save-time-in-an-exam",
                "quote": "A copy of the periodic table of elements is included at the back of the theory question papers and multiple-choice papers, but not the practical question papers. No additional copies of the periodic table can be provided in the exam.",
            },
            {
                "kind": "question-paper-cover",
                "ref": "0620_s24_qp11 封面（实测文本）",
                "quote": "The Periodic Table is printed in the question paper.",
            },
            {
                "kind": "question-paper-cover",
                "ref": "9701_s24_qp11 封面（实测文本）",
                "quote": "The Periodic Table is printed in the question paper.",
            },
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单（清单扉页声明）",
                "quote": "The additional exam materials list does not cover ... specific materials for use in science exams. You will find these in the relevant syllabus booklet or in the confidential instructions that come with the question papers.",
            },
        ],
    },
    "chemistry_data_booklet": {
        "name_zh": "化学数据手册（Chemistry Data Booklet，AS/A Level）",
        "name_en": "Chemistry Data Booklet (Cambridge International AS and A Level)",
        "candidate_facing": True,
        "form_zh": "按指定组件随考发放（官方问答 203545612：每考生一本，需用组件见 Additional Materials database）；另有问答（20295231545746）称理论卷 1、2、4 不再随卷发放、数据随题给出——兼容解读：仅指定组件发放",
        "public_obtainable": "no",
        "public_note_zh": "无独立公开的官方数据手册 PDF（站点检索与三份系列清单全文 grep 'Data Booklet' 均 0 次：Nov 2026 2164 行/207 科、Nov 2024 1931 行/213 科、June 2024 2328 行/193 科）；9701 数据以 syllabus Data section 附录形式公开",
        "integrated": "no",
        "integration_zh": "未接入（无官方公开文件可取回）；替代路径：syllabus Data section 附录",
        "conflict_note_zh": "口径并存（兼容解读，非矛盾）：203545612 说 'Chemistry Data booklet ... One book to be issued per candidate'（组件见 Additional Materials database）；20295231545746 说 'No. Data Booklets are no longer provided with paper 1, 2 and 4.' —— 即仅『指定组件』随卷发放，理论卷不另发",
        "evidence": [
            {
                "kind": "help-article",
                "ref": "help.cambridgeinternational.org 203545612",
                "url": "https://help.cambridgeinternational.org/hc/en-gb/articles/203545612-Component-specific-materials-for-use-in-the-exam-room",
                "quote": "Chemistry Data booklet (Cambridge International AS and A Level) ... One book to be issued per candidate. ... The components that require the data book are listed in the Additional Materials database.",
            },
            {
                "kind": "help-article",
                "ref": "help.cambridgeinternational.org 20295231545746",
                "url": "https://help.cambridgeinternational.org/hc/en-gb/articles/20295231545746-Will-candidates-receive-a-Data-Booklet-for-the-Theory-papers-in-the-exam",
                "quote": "No. Data Booklets are no longer provided with paper 1, 2 and 4. Where data are required these will be provided with the question.",
            },
            {
                "kind": "additional-materials-list",
                "ref": "三份系列清单全文 grep 'Data Booklet' = 0（Nov 2026 / Nov 2024 / June 2024）",
                "quote": "未出现 Data Booklet 条目",
            },
        ],
    },
    "graph_paper": {
        "name_zh": "图表纸（Graph paper）",
        "name_en": "Graph paper",
        "candidate_facing": True,
        "form_zh": "考务材料：Cambridge 随考务提供——每次需要的考试每考生两张（考务包裹 183A 含 Chart/Graph Paper）；适用组件见 Additional Materials database",
        "public_obtainable": "no",
        "public_note_zh": "非公开文件（无独立 PDF）。注：三份系列清单全文 grep 'graph paper' 均 = 0；考点侧按考务包裹发放（help 203545612 称适用考试列于 Additional Materials database）",
        "integrated": "no",
        "integration_zh": "未接入（无官方公开文件可取回）",
        "evidence": [
            {
                "kind": "help-article",
                "ref": "help.cambridgeinternational.org 203545612",
                "url": "https://help.cambridgeinternational.org/hc/en-gb/articles/203545612-Component-specific-materials-for-use-in-the-exam-room",
                "quote": "Graph paper ... Two sheets per candidate are provided for each exam that requires graph paper. These exams are listed in the Additional Materials database.",
            },
            {
                "kind": "help-article",
                "ref": "help.cambridgeinternational.org 29566602394898（183A 考务包裹内容）",
                "url": "https://help.cambridgeinternational.org/hc/en-gb/articles/29566602394898-Despatch-notification-references",
                "quote": "'183A' contains: ... Chemistry Data Booklet Graph Paper Formulae & Statistics Tables",
            },
        ],
    },
    "tracing_paper_centre": {
        "name_zh": "描图纸（部分数学卷，考点提供）",
        "name_en": "Tracing paper (for some mathematics papers)",
        "candidate_facing": True,
        "form_zh": "Nov 2026 清单『Materials you must provide』：部分数学卷考点应提供描图纸；清单 85 处 'tracing' 提及（含考生自备项）",
        "public_obtainable": "no",
        "public_note_zh": "非文件类材料，考点自备",
        "integrated": "no",
        "integration_zh": "未接入",
        "evidence": [
            {
                "kind": "additional-materials-list",
                "ref": "Nov 2026 国际版清单扉页",
                "quote": "for some mathematics papers, candidates may have been taught using tracing paper for transformations. Where this is the case, you should provide candidates with tracing paper.",
            }
        ],
    },
    "official_insert_source_material": {
        "name_zh": "官方公开发布的 Insert / Source material PDF",
        "name_en": "Insert / source material (official site publications)",
        "candidate_facing": True,
        "form_zh": "官网按系列/科目公开发布的 insert（阅读文本、来源材料、地图等）；发现快照 179 份",
        "public_obtainable": "yes",
        "public_note_zh": "公开 PDF 可下载（例：0990 June 2024 Insert Paper 11 实测 200；镜像 0500_s24_in_11 / 9701_s19_in_33 实测 200）",
        "integrated": "yes",
        "integration_zh": "动态通道 /api/v1/materials/cie/in-paper（role=in，按 subject/year/season/paper 定位）；catalog 条目 cie-inserts",
        "evidence": [
            {
                "kind": "discovery-snapshot",
                "ref": "examdata/.data/discovery.json",
                "quote": "doc_type=source_material 共 179 份（含 specimen insert / june insert 等）",
            },
            {
                "kind": "mirror-download",
                "ref": "0500_s24_in_11.pdf（镜像实拿）",
                "url": "https://cie.fraft.cn/obj/Common/Fetch/redir/0500_s24_in_11.pdf",
                "http": 200,
                "bytes": 114871,
                "sha256": "7d49097cb30c27e4f6f640aef77d845ca192206e41b51d728b8aae739cb805c4",
                "pages": 8,
            },
        ],
    },
    "official_confidential_instructions": {
        "name_zh": "保密须知（Confidential Instructions，考务/教师用）",
        "name_en": "Confidential Instructions",
        "candidate_facing": False,
        "form_zh": "随卷给考点的保密考务文件（明文不得接触考生）；官网对部分系列（如 June 2024）公开发布 PDF，发现快照 37 份",
        "public_obtainable": "yes",
        "public_note_zh": "公开链接实测可取回（0620 June 2024 Paper 51、9701 June 2024 Paper 31 均 HTTP 200 真 PDF）；语义上是过期系列的归档公开",
        "integrated": "partial",
        "integration_zh": "动态通道 /api/v1/materials/cie/in-paper（role=ci|ir）；catalog 条目 cie-confidential-instructions",
        "evidence": [
            {
                "kind": "official-download",
                "ref": "0620 June 2024 CI Paper 51（实测取回）",
                "url": "https://www.cambridgeinternational.org/Images/649924-june-2024-confidential-instructions-paper-51.pdf",
                "http": 200,
                "bytes": 1064877,
                "sha256": "5909d16ea5f4be7f2ac23ac6a9a712137ef4d5b3b36ae148cf73baaa72b2572b",
                "verified_at": "2026-10-05",
            },
            {
                "kind": "official-download",
                "ref": "9701 June 2024 CI Paper 31（实测取回）",
                "url": "https://www.cambridgeinternational.org/Images/567187-june-2024-confidential-instructions-paper-31.pdf",
                "http": 200,
                "bytes": 1813136,
                "sha256": "71ffa69f0341e80d906c4aee52d9b43847d12415289fd5bf07b44d89c7906729",
                "verified_at": "2026-10-05",
            },
            {
                "kind": "mirror-download",
                "ref": "0620_s24_ci_51.pdf（镜像实拿，2024 系列）",
                "url": "https://cie.fraft.cn/obj/Common/Fetch/redir/0620_s24_ci_51.pdf",
                "http": 200,
                "bytes": 183081,
                "sha256": "76ed956704f21dd778c607d1a92c37e377b68ef4e0dc98d409b1fe6ef2f97b01",
            },
            {
                "kind": "mirror-download",
                "ref": "0620_s16_ir_51.pdf（镜像实拿，2016 旧 ir 代码）",
                "url": "https://cie.fraft.cn/obj/Common/Fetch/redir/0620_s16_ir_51.pdf",
                "http": 200,
                "bytes": 166037,
                "sha256": "84562eea2297289e4e4c07074127fa8100051f03f0e3ec0749d37eb8a7e96c56",
            },
        ],
    },
}

INTEGRATED_ITEMS_BY_KEY = {
    "mf19_formulae_tables": ["cie-mf19-formulae-and-statistical-tables"],
    "answer_booklet_insert": ["cie-inserts"],
    "mc_answer_sheet": ["cie-mc-answer-sheet"],
    "official_insert_source_material": ["cie-inserts"],
    "official_confidential_instructions": ["cie-confidential-instructions"],
    "periodic_table_in_paper": ["cie-periodic-table"],
}

# 缺口 1 补证：以下 10 码在四份清单快照（June 2024 / Nov 2024 / Nov 2025 / Nov 2026 国际版）
# 中均无行。证据显示均为新版 syllabus（发现快照仅有 specimen / specimen mark scheme 材料、
# 无任何历年真题与成绩报告），specimen 年份即首考年，与 2024-2026 各系列缺席自洽。
# page_sentences 取自 syllabus 页面定向提取（gap1_syllabus_sentences.json；0715/8101/8102/9981/9982
# 页面无可用性句，仅样本卷年份佐证）。
NEW_SYLLABUS_EVIDENCE = {
    "0265": {"first_exam": 2029, "specimen_year": 2029,
             "page_sentences": ["Example Candidate Responses will be available following the first examination in 2029."]},
    "0266": {"first_exam": 2027, "specimen_year": 2027,
             "page_sentences": ["In the June series this syllabus is available in zones 2, 3, 4 & 5.",
                                 "In the November series this syllabus is available in all time zones."]},
    "0479": {"first_exam": 2027, "specimen_year": 2027,
             "page_sentences": ["In 2027 this syllabus is available in Administrative Zones 3 and 4 in the June series.",
                                 "From 2028 this syllabus is available in Administrative zones 3, 4, 5 and 6 in the June series."]},
    "0715": {"first_exam": 2028, "specimen_year": 2028, "page_sentences": []},
    "0716": {"first_exam": 2027, "specimen_year": 2027,
             "page_sentences": ["Example Candidate Responses will be available following the first examination in 2027."]},
    "8101": {"first_exam": 2027, "specimen_year": 2027, "page_sentences": []},
    "8102": {"first_exam": 2027, "specimen_year": 2027, "page_sentences": []},
    "8293": {"first_exam": 2028, "specimen_year": 2028,
             "page_sentences": ["Example Candidate Responses will be available following the first examination in 2028."]},
    "9981": {"first_exam": 2027, "specimen_year": 2027, "page_sentences": []},
    "9982": {"first_exam": 2027, "specimen_year": 2027, "page_sentences": []},
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    syll = load(ROOT / "examdata" / ".data" / "syllabuses.json")
    disc = load(ROOT / "examdata" / ".data" / "discovery.json")
    byl = load(EVID / "addmaterials_by_subject.json")["subjects"]

    series_specs = [
        ("june_2024", "June 2024（国际版）", "addmaterials_rows_june-2024.json"),
        ("nov_2024", "November 2024（国际版）", "addmaterials_rows_november-2024.json"),
        ("nov_2025", "November 2025（国际版）", "addmaterials_rows_november-2025.json"),
    ]
    series_meta = []
    series_by_code = collections.defaultdict(dict)
    for skey, slabel, fname in series_specs:
        d = load(EVID / fname)
        agg = collections.defaultdict(
            lambda: {
                "rows": 0,
                "components": set(),
                "provided": collections.Counter(),
                "titles": set(),
                "qualifications": set(),
            }
        )
        for row in d.get("rows", []):
            c = str(row.get("code") or "").strip()
            if not c:
                continue
            a = agg[c]
            a["rows"] += 1
            if row.get("component"):
                a["components"].add(str(row["component"]))
            for p in row.get("provided") or []:
                a["provided"][p.get("key") or p.get("text") or "unknown"] += 1
            if row.get("title"):
                a["titles"].add(row["title"])
            if row.get("qualification"):
                a["qualifications"].add(row["qualification"])
        for c, a in agg.items():
            series_by_code[c][skey] = {
                "label_zh": slabel,
                "rows": a["rows"],
                "components": sorted(a["components"]),
                "provided": dict(sorted(a["provided"].items())),
                "titles": sorted(a["titles"]),
                "qualifications": sorted(a["qualifications"]),
            }
        src = d.get("source") or {}
        series_meta.append(
            {
                "key": skey,
                "label_zh": slabel,
                "path": "tmp_materials_probe/evidence/" + fname,
                "url": src.get("url"),
                "capture": src.get("capture"),
                "sha256": src.get("sha256"),
                "bytes": src.get("bytes"),
                "pages": src.get("pages"),
                "rows": d.get("row_count"),
                "subjects": len(agg),
                "note_zh": "Wayback 快照（国际版清单同 URL 历年归档）；2023-03/June 2022/Nov 2022 三份因 Wayback 服务端 1 MiB 截断未解析",
            }
        )

    syll_by_code = {}
    for s in syll:
        code = str(s.get("code") or "").strip()
        if code:
            syll_by_code[code] = s

    disc_by_code = collections.defaultdict(list)
    for r in disc["resources"]:
        code = str(r.get("subject_code") or "").strip()
        if code:
            disc_by_code[code].append(r)

    doc_type_totals = collections.Counter(r.get("doc_type") for r in disc["resources"])

    codes = sorted(set(syll_by_code) | set(disc_by_code) | set(byl.keys()) | set(series_by_code))

    subjects = {}
    coverage = {
        "subjects_total_union": len(codes),
        "syllabuses": len(syll_by_code),
        "discovery_subject_codes": len(disc_by_code),
        "nov2026_list_subjects": len(byl),
        "series_list_subjects": {m["key"]: m["subjects"] for m in series_meta},
        "with_nov2026_list_rows": 0,
        "with_series_list_rows": 0,
        "with_public_insert_source_material": 0,
        "with_public_confidential_instructions": 0,
        "with_public_pre_release": 0,
        "no_material_evidence": [],
        "no_material_evidence_note_zh": "无任何清单条目（Nov 2026 与三份系列快照全文均无该码行），且发现快照无 insert/CI 记录",
    }

    for code in codes:
        s = syll_by_code.get(code, {})
        entry = {}
        titles = []
        quals = set()
        slug = s.get("slug")
        source_url = s.get("source_url")
        if s:
            if s.get("title"):
                titles.append(s["title"])
            if s.get("qualification_key"):
                quals.add(str(s["qualification_key"]))

        lst = byl.get(code)
        rows_provided = {}
        rows_candidate = {}
        rows_policy = {}
        if lst:
            coverage["with_nov2026_list_rows"] += 1
            for t in (lst.get("titles") or {}):
                titles.append(t)
            for q in (lst.get("qualifications") or {}):
                quals.add(q)
            rows_provided = lst.get("provided") or {}
            rows_candidate = lst.get("candidate") or {}
            rows_policy = lst.get("policy") or {}

        s_lists = series_by_code.get(code) or {}
        if s_lists:
            coverage["with_series_list_rows"] += 1
            for rec in s_lists.values():
                for t in rec.get("titles") or []:
                    titles.append(t)
                for q in rec.get("qualifications") or []:
                    quals.add(q)

        ressources = disc_by_code.get(code, [])
        by_type = collections.Counter(r.get("doc_type") for r in ressources)
        examples = {
            "source_material": [
                {"label": r.get("label"), "url": r.get("url"), "series": r.get("series"), "year": r.get("year")}
                for r in ressources
                if r.get("doc_type") == "source_material"
            ][:6],
            "confidential_instructions": [
                {"label": r.get("label"), "url": r.get("url"), "series": r.get("series"), "year": r.get("year")}
                for r in ressources
                if r.get("doc_type") == "confidential_instructions"
            ][:6],
            "pre_release": [
                {"label": r.get("label"), "url": r.get("url"), "doc_type": r.get("doc_type")}
                for r in ressources
                if "pre-release" in ((r.get("label") or "") + (r.get("url") or "")).lower()
            ][:6],
        }
        if by_type.get("source_material"):
            coverage["with_public_insert_source_material"] += 1
        if by_type.get("confidential_instructions"):
            coverage["with_public_confidential_instructions"] += 1
        if examples["pre_release"]:
            coverage["with_public_pre_release"] += 1

        # per-subject materials list
        materials = []
        for key, meta in sorted(rows_provided.items()):
            reg = REGISTRY.get(key, {})
            materials.append(
                {
                    "key": key,
                    "name_zh": (reg.get("name_zh") or meta.get("label")),
                    "form_zh": reg.get("form_zh"),
                    "public_obtainable": reg.get("public_obtainable"),
                    "integrated": reg.get("integrated"),
                    "integration_zh": reg.get("integration_zh"),
                    "hits": meta.get("hits"),
                    "components": (lst.get("components") or []) if lst else [],
                }
            )

        title_join = " ".join(titles).lower()
        if code in ("0620", "9701"):
            materials.append(
                {
                    "key": "periodic_table_in_paper",
                    "name_zh": REGISTRY["periodic_table_in_paper"]["name_zh"],
                    "form_zh": REGISTRY["periodic_table_in_paper"]["form_zh"],
                    "public_obtainable": "via-qp",
                    "integrated": "partial",
                    "integration_zh": REGISTRY["periodic_table_in_paper"]["integration_zh"],
                    "hits": None,
                    "components": None,
                    "verified_cover": True,
                }
            )
        elif "chemistry" in title_join:
            materials.append(
                {
                    "key": "periodic_table_in_paper",
                    "name_zh": REGISTRY["periodic_table_in_paper"]["name_zh"],
                    "form_zh": REGISTRY["periodic_table_in_paper"]["form_zh"],
                    "public_obtainable": "via-qp",
                    "integrated": "partial",
                    "integration_zh": REGISTRY["periodic_table_in_paper"]["integration_zh"],
                    "hits": None,
                    "components": None,
                    "verified_cover": False,
                    "uncertain": "该科未实测封面，周期表形态按官方问答类推，标 uncertain",
                }
            )
        if code == "9701":
            materials.append(
                {
                    "key": "chemistry_data_booklet",
                    "name_zh": REGISTRY["chemistry_data_booklet"]["name_zh"],
                    "form_zh": REGISTRY["chemistry_data_booklet"]["form_zh"],
                    "public_obtainable": REGISTRY["chemistry_data_booklet"]["public_obtainable"],
                    "integrated": "no",
                    "integration_zh": REGISTRY["chemistry_data_booklet"]["integration_zh"],
                    "hits": None,
                    "components": None,
                    "conflict": True,
                }
            )

        if by_type.get("source_material"):
            materials.append(
                {
                    "key": "official_insert_source_material",
                    "name_zh": REGISTRY["official_insert_source_material"]["name_zh"],
                    "form_zh": REGISTRY["official_insert_source_material"]["form_zh"],
                    "public_obtainable": "yes",
                    "integrated": "yes",
                    "integration_zh": REGISTRY["official_insert_source_material"]["integration_zh"],
                    "hits": by_type.get("source_material"),
                    "components": None,
                }
            )
        if by_type.get("confidential_instructions"):
            materials.append(
                {
                    "key": "official_confidential_instructions",
                    "name_zh": REGISTRY["official_confidential_instructions"]["name_zh"],
                    "form_zh": REGISTRY["official_confidential_instructions"]["form_zh"],
                    "public_obtainable": "yes",
                    "integrated": "partial",
                    "integration_zh": REGISTRY["official_confidential_instructions"]["integration_zh"],
                    "hits": by_type.get("confidential_instructions"),
                    "components": None,
                }
            )

        # conclusion
        concl = []
        if lst:
            concl.append(
                "Nov 2026 国际版附加材料清单：{n} 个组件行；发放项 {items}".format(
                    n=len(lst.get("components") or []),
                    items="、".join(sorted(set(rows_provided))) or "（无 provided 列项）",
                )
            )
        else:
            concl.append("未在 Nov 2026 国际版附加材料清单中出现（其余系列快照情况见下）")
        for _skey, srec in sorted(s_lists.items()):
            items = "、".join(
                "{k}×{n}".format(k=k, n=n) for k, n in sorted(srec["provided"].items())
            ) or "（该系列无发放项列）"
            concl.append(
                "{label} 清单：{rows} 行 / {comps} 组件；发放项 {items}".format(
                    label=srec["label_zh"],
                    rows=srec["rows"],
                    comps=len(srec["components"]),
                    items=items,
                )
            )
        if by_type.get("source_material"):
            concl.append("官方发现快照含 {n} 份 insert/source material 公开 PDF".format(n=by_type["source_material"]))
        if by_type.get("confidential_instructions"):
            concl.append("含 {n} 份 Confidential Instructions（官网公开链接，Series 归档）".format(n=by_type["confidential_instructions"]))
        if examples["pre_release"]:
            concl.append("含 {n} 份 Pre-Release 公开材料".format(n=len(examples["pre_release"])))
        if (
            not lst
            and not s_lists
            and not by_type.get("source_material")
            and not by_type.get("confidential_instructions")
        ):
            concl.append("无任何清单条目（Nov 2026 与三份系列快照全文均无该码行）与公开 insert/CI 记录 → 发放资料情况未证实（uncertain）")
            coverage["no_material_evidence"].append(code)
        if "chemistry" in title_join or "physics" in title_join or "biology" in title_join or "science" in title_join:
            concl.append("科学类专属材料不在清单覆盖范围（清单扉页明文，见周期表条目证据）")

        ns_ev = NEW_SYLLABUS_EVIDENCE.get(code) if (not lst and not s_lists) else None
        if ns_ev:
            q = ("；页面句：" + " / ".join(ns_ev["page_sentences"])) if ns_ev["page_sentences"] else ""
            concl.append(
                "四份清单快照（June 2024 / Nov 2024 / Nov 2025 / Nov 2026 国际版）均无该码行；发现快照含 {y} specimen 材料、无历年真题 → 新版 syllabus，首考 {y}{q}".format(
                    y=ns_ev["specimen_year"], q=q
                )
            )

        integrated_items = []
        for m in materials:
            integrated_items.extend(INTEGRATED_ITEMS_BY_KEY.get(m["key"], []))

        entry = {
            "titles": sorted(set(titles)),
            "slug": slug,
            "source_url": source_url,
            "qualifications": sorted(quals),
            "enumeration": sorted(
                k
                for k, v in (
                    ("syllabuses", code in syll_by_code),
                    ("discovery", code in disc_by_code),
                    ("nov2026_list", code in byl),
                    ("series_lists", bool(s_lists)),
                )
                if v
            ),
            "nov2026": (
                {
                    "components": lst.get("components"),
                    "component_count": lst.get("component_count"),
                    "provided": {k: {"hits": v.get("hits"), "sample": v.get("sample")} for k, v in rows_provided.items()},
                    "candidate_must_provide": {
                        k: {
                            "label_zh": CANDIDATE_LABELS.get(k, v.get("label")),
                            "hits": v.get("hits"),
                            "sample": v.get("sample"),
                        }
                        for k, v in rows_candidate.items()
                    },
                    "answer_on_qp": lst.get("answer_on_qp"),
                    "policy": rows_policy or None,
                }
                if lst
                else None
            ),
            "series_lists": s_lists or None,
            "new_syllabus_note_zh": (
                (
                    "新版 syllabus：{y} 年 specimen 材料（首考 {y}，发现快照无历年真题）；".format(y=ns_ev["specimen_year"])
                    + (
                        "页面句：" + " / ".join(ns_ev["page_sentences"])
                        if ns_ev["page_sentences"]
                        else "页面无可用性句，仅 specimen 年份佐证"
                    )
                )
                if ns_ev
                else None
            ),
            "discovery": {
                "total": len(ressources),
                "by_doc_type": dict(by_type),
                "examples": {
                    k: v for k, v in examples.items() if v
                },
            },
            "materials": materials,
            "integrated_items": sorted(set(integrated_items)),
            "conclusion_zh": "；".join(concl) + "。",
        }
        subjects[code] = entry

    out = {
        "schema_version": "1",
        "board": "cie",
        "generated_at": "2026-10-05",
        "scope_zh": (
            "范围全集 = 仓库既有枚举证据的并集：syllabuses.json {ns} 科 ∪ discovery.json {nd} 科 ∪ Nov 2026 国际版附加材料清单解析 {nl} 科 ∪ 三份系列清单快照 {nsl} 科 = {nu} 科。"
            "清单均为系列级快照（Nov 2026 / June 2024 / Nov 2024 / Nov 2025 国际版），不代表未收录系列；"
            "科目未出现在某系列清单不必然代表该系列无发放项（历史系列快照存在 Wayback 截断项，见 sources.series_lists）。"
        ).format(
            ns=len(syll_by_code),
            nd=len(disc_by_code),
            nl=len(byl),
            nsl=len(series_by_code),
            nu=len(codes),
        ),
        "method_zh": (
            "逐科结论由四类实测证据合成：①附加材料清单（Nov 2026 国际版 PDF 解析，逐组件行：发放项/考生自备/答题方式）；"
            "②三份历史系列清单快照（June 2024 / Nov 2024 / Nov 2025 国际版，Wayback 归档原 PDF 解析，同列结构）；"
            "③官方站点发现快照（2767 资源，含 insert=source_material 与 confidential_instructions 的公开 URL）；"
            "④定向实测取回（MF19、0990 insert、0500 镜像 insert、0620/9701 CI、0411 预发材料、通用 MC 答题卡，均记录 HTTP/字节/sha256/页数）。"
            "凡未实测或官方口径冲突处已标注 uncertain，未臆断。"
        ),
        "sources": {
            "syllabuses": {"path": "examdata/.data/syllabuses.json", "count": len(syll_by_code)},
            "discovery": {
                "path": "examdata/.data/discovery.json",
                "resources": len(disc["resources"]),
                "subject_codes": len(disc_by_code),
                "doc_type_counts": dict(doc_type_totals),
            },
            "nov2026_additional_materials": {
                "path": "tmp_materials_probe/evidence/addmaterials_rows.json",
                "url": "https://www.cambridgeinternational.org/Images/651593-additional-exams-material-list-international-.pdf",
                "sha256": "858b0fcbe5d00e92e3b761684adfcfa969fe79216a80899f296999918dbb39a3",
                "bytes": 658660,
                "pages": 222,
                "rows": 2164,
                "subjects": len(byl),
            },
            "series_lists": series_meta,
            "gap1_evidence": {
                "wayback_lists": "tmp_materials_probe/evidence/gap1_wayback_lists.json",
                "syllabus_sentences": "tmp_materials_probe/evidence/gap1_syllabus_sentences.json",
                "note_zh": "23 码核对：June 2024 含 13 码；Nov 2024 含 2 码（0989/0995）；Nov 2025/Nov 2026 含 0 码；其余 10 码为 2027-2029 首考的新版 syllabus（NEW_SYLLABUS_EVIDENCE）",
            },
            "verify_public_materials": "tmp_materials_probe/evidence/verify_public_materials.json",
        },
        "coverage": coverage,
        "new_syllabus_evidence": NEW_SYLLABUS_EVIDENCE,
        "material_registry": REGISTRY,
        "subjects": subjects,
    }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", OUT, OUT.stat().st_size)
    print("subjects:", len(subjects))
    print("coverage:", json.dumps(coverage, ensure_ascii=False)[:800])


if __name__ == "__main__":
    main()
