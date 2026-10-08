/**
 * adjudications.mjs — S07: 答案裁决的结构化迁移（45 条裁决 = 43 条 diff + 2 条被比较器
 * 单字母子串 bug 掩盖的独立补验项；其中 7 条窄修正 action=correct）。
 *
 * 源（只读历史证据，不修改）：
 *   tmp_audit_ielts/repair-20261003-152644/answer_adjudications.json（2026-10-03T17:12+08:00 生成）
 * 语义：对 practicepteonline 来源值与官方 PDF 答案键（视觉核验）逐条裁决。
 *
 * 迁移规则（S07 算法第 8 条）：
 *  - 每条 decision 含完整 identity（book/test/skill/question[/group]）、from/to、PDF sha256/页、
 *    理由（basis）、验证者类型与方法、时间；
 *  - 应用时以完整 identity + 原值守卫（当前值 === from）为准；上游值变动 -> decision_stale，
 *    保留旧记录、不强套修正；
 *  - book_value 为该题核验后的书内值（选项字母/集合/印刷值）；equivalents 为裁决明确允许的
 *    等价来源形式；artifact_values 为提取器字形伪影（不得当作官方值）；mapping 为字母↔选项文本。
 *  - 本模块不修改来源解析器；由 ielts-api.mjs 与 answer-matcher.mjs 在展示/比较层消费。
 *
 * S08 增补 GROUP_VERIFICATIONS（组级官方核验覆盖，不改动上述 45 条 DECISIONS）：
 *  - 每条含完整 identity（book/variant/skill/test/part/group_id/range）、from（原值）、to（官方值）、
 *    官方 PDF sha256/页、OCR 证据文件清单、验证者；
 *  - 由 question-index.mjs 的 applyGroupVerifications 在构建时应用；from 值不匹配 -> decision_stale，
 *    保留原值并记入 index.verification_issues；答案表示映射写入 answers[qid].official，raw 不动。
 */

export const ADJUDICATIONS_META = {
  "source_file": "tmp_audit_ielts/repair-20261003-152644/answer_adjudications.json",
  "source_generated_at": "2026-10-03T17:12+08:00",
  "source_generated_by": "IELTS repair agent (2026-10-03 独立复审修复)",
  "purpose": "对 official_v3_diffs.json 全部 43 条差异逐条裁决；另含比较器单字母子串 bug 掩盖的 2 条（4-1 Q23/Q29）独立补验。",
  "summary": {
    "total_items": 45,
    "from_diff_file": 43,
    "masked_by_comparator_bug": 2,
    "resolved": 45,
    "unresolved": 0,
    "corrections_applied": 7,
    "no_action": 38
  },
  "sources": {
    "diff_file": "C:/Users/weo/Desktop/api/tmp_audit_ielts/official_v3_diffs.json",
    "official_pdfs": "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_{N}.pdf",
    "pte_refetch_dir": "C:/Users/weo/Desktop/api/tmp_audit_ielts/repair-20261003-152644/evidence/i3/pte_refetch_20261003-163918/",
    "dumps_dir": "C:/Users/weo/Desktop/api/tmp_audit_ielts/repair-20261003-152644/evidence/i3/",
    "visual_batches": "evidence/i3/visual_batchA.png (b4p157,b5p153,b5p155,b5p159), evidence/i3/visual_batchB.png (b6p152,b6p158,b7p161,b7p163)",
    "comparator_bug_proof": "evidence/i3/comparator_bug_proof.txt",
    "live_check": "node ielts-cli/ielts-api.mjs pteListening live call, 2026-10-03 17:0x (见 IELTS_REPAIR_REPORT.md)"
  },
  "pdf_sha256": {
    "book_4.pdf": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed",
    "book_5.pdf": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a",
    "book_6.pdf": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573",
    "book_7.pdf": "a219bf469ba75c39938a2a9d8bfd4bf15caf206e8c249d70d188ff4e36ad3b00",
    "book_12.pdf": "f791300937f11d8380eba7b7997db1da751d66802a96aed996db704947e52407",
    "book_17.pdf": "90ae888c4cd495761fe5639418ca894e63c9e7066382ed9ffad6bd74a409726a"
  },
  "migrated_at": "2026-10-04",
  "migrated_by": "S07 gen-adjudications.py（结构化副本，不修改历史证据）"
};

/** 45 条裁决的结构化副本（顺序与源文件 items 一致） */
export const DECISIONS = [
  {
    "id": "adj-01",
    "identity": {
      "book": 4,
      "test": 1,
      "skill": "listening",
      "question": 24,
      "group_id": null
    },
    "category": "option_mapping",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "B",
    "source": "practicepteonline.com",
    "source_value": "useful",
    "page_raw_value": "选项表 p16: B=useful",
    "basis": "官方键为选项字母（p16 选项表 A-G）；B=useful；pte 给出选项文本 'useful'，映射后一致（book4_p16_options.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_4.pdf",
      "page": 153,
      "sha256": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页选项表逐条映射核对（book4_p16/p17_options.txt）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "B",
    "equivalents": [
      "useful"
    ],
    "artifact_values": [],
    "mapping": {
      "letter": "B",
      "option_text": "useful",
      "options_ref": "选项表 p16: B=useful"
    },
    "group": null
  },
  {
    "id": "adj-02",
    "identity": {
      "book": 4,
      "test": 1,
      "skill": "listening",
      "question": 25,
      "group_id": null
    },
    "category": "option_mapping",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "G",
    "source": "practicepteonline.com",
    "source_value": "don't read",
    "page_raw_value": "选项表 p16: G=don't read",
    "basis": "G=don't read；pte 'don’t read'（弯引号归一化为 ASCII）映射后一致（book4_p16_options.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_4.pdf",
      "page": 153,
      "sha256": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页选项表逐条映射核对（book4_p16/p17_options.txt）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "G",
    "equivalents": [
      "don't read"
    ],
    "artifact_values": [],
    "mapping": {
      "letter": "G",
      "option_text": "don't read",
      "options_ref": "选项表 p16: G=don't read"
    },
    "group": null
  },
  {
    "id": "adj-03",
    "identity": {
      "book": 4,
      "test": 1,
      "skill": "listening",
      "question": 26,
      "group_id": null
    },
    "category": "option_mapping",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "F",
    "source": "practicepteonline.com",
    "source_value": "read conclusion",
    "page_raw_value": "选项表 p16: F=read conclusion",
    "basis": "F=read conclusion；pte 'read conclusion' 映射后一致（book4_p16_options.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_4.pdf",
      "page": 153,
      "sha256": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页选项表逐条映射核对（book4_p16/p17_options.txt）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "F",
    "equivalents": [
      "read conclusion"
    ],
    "artifact_values": [],
    "mapping": {
      "letter": "F",
      "option_text": "read conclusion",
      "options_ref": "选项表 p16: F=read conclusion"
    },
    "group": null
  },
  {
    "id": "adj-04",
    "identity": {
      "book": 4,
      "test": 1,
      "skill": "listening",
      "question": 27,
      "group_id": null
    },
    "category": "option_mapping",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "c",
    "source": "practicepteonline.com",
    "source_value": "limited value",
    "page_raw_value": "选项表 p16: C=limited value",
    "basis": "C=limited value；pte 'limited value' 映射后一致（book4_p16_options.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_4.pdf",
      "page": 153,
      "sha256": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页选项表逐条映射核对（book4_p16/p17_options.txt）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "c",
    "equivalents": [
      "limited value"
    ],
    "artifact_values": [],
    "mapping": {
      "letter": "c",
      "option_text": "limited value",
      "options_ref": "选项表 p16: C=limited value"
    },
    "group": null
  },
  {
    "id": "adj-05",
    "identity": {
      "book": 4,
      "test": 1,
      "skill": "listening",
      "question": 28,
      "group_id": null
    },
    "category": "option_mapping",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "D",
    "source": "practicepteonline.com",
    "source_value": "noisy neighbours",
    "page_raw_value": "选项表 p17: D=noisy neighbours",
    "basis": "第二组选项表（p17，A-H）；D=noisy neighbours；pte 映射后一致（book4_p17_options.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_4.pdf",
      "page": 153,
      "sha256": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页选项表逐条映射核对（book4_p16/p17_options.txt）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "D",
    "equivalents": [
      "noisy neighbours"
    ],
    "artifact_values": [],
    "mapping": {
      "letter": "D",
      "option_text": "noisy neighbours",
      "options_ref": "选项表 p17: D=noisy neighbours"
    },
    "group": null
  },
  {
    "id": "adj-06",
    "identity": {
      "book": 4,
      "test": 1,
      "skill": "listening",
      "question": 30,
      "group_id": null
    },
    "category": "option_mapping",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "B",
    "source": "practicepteonline.com",
    "source_value": "environment",
    "page_raw_value": "选项表 p17: B=environment",
    "basis": "第二组选项表（p17）；B=environment；pte 映射后一致（book4_p17_options.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_4.pdf",
      "page": 153,
      "sha256": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页选项表逐条映射核对（book4_p16/p17_options.txt）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "B",
    "equivalents": [
      "environment"
    ],
    "artifact_values": [],
    "mapping": {
      "letter": "B",
      "option_text": "environment",
      "options_ref": "选项表 p17: B=environment"
    },
    "group": null
  },
  {
    "id": "adj-07",
    "identity": {
      "book": 4,
      "test": 1,
      "skill": "listening",
      "question": 23,
      "group_id": null
    },
    "category": "option_mapping",
    "action": "none",
    "status": "resolved",
    "origin": "masked_by_comparator_bug",
    "official_extracted": "E",
    "source": "practicepteonline.com",
    "source_value": "read research methods",
    "page_raw_value": "官方键行 [009] '23 E'（x=254.3/278.1）；选项表 p16: E=read research methods",
    "basis": "不在 43 条 diff 中——被比较器单字母子串 bug 假匹配掩盖（comparator_bug_proof.txt: match_one('read research methods','E')=True）；经选项表 p16 映射 E=read research methods，语义一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_4.pdf",
      "page": 153,
      "sha256": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页选项表逐条映射核对（book4_p16/p17_options.txt）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "E",
    "equivalents": [
      "read research methods"
    ],
    "artifact_values": [],
    "mapping": {
      "letter": "E",
      "option_text": "read research methods",
      "options_ref": "官方键行 [009] '23 E'（x=254.3/278.1）；选项表 p16: E=read research methods"
    },
    "group": null
  },
  {
    "id": "adj-08",
    "identity": {
      "book": 4,
      "test": 1,
      "skill": "listening",
      "question": 29,
      "group_id": null
    },
    "category": "option_mapping",
    "action": "none",
    "status": "resolved",
    "origin": "masked_by_comparator_bug",
    "official_extracted": "A",
    "source": "practicepteonline.com",
    "source_value": "uncooperative landlord",
    "page_raw_value": "官方键行 [016] '29 A'（x=253.9/277.9）；选项表 p17: A=uncooperative landlord",
    "basis": "不在 43 条 diff 中——被比较器单字母子串 bug 假匹配掩盖（comparator_bug_proof.txt: match_one('uncooperative landlord','A')=True）；经选项表 p17 映射 A=uncooperative landlord，语义一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_4.pdf",
      "page": 153,
      "sha256": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页选项表逐条映射核对（book4_p16/p17_options.txt）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "A",
    "equivalents": [
      "uncooperative landlord"
    ],
    "artifact_values": [],
    "mapping": {
      "letter": "A",
      "option_text": "uncooperative landlord",
      "options_ref": "官方键行 [016] '29 A'（x=253.9/277.9）；选项表 p17: A=uncooperative landlord"
    },
    "group": null
  },
  {
    "id": "adj-09",
    "identity": {
      "book": 4,
      "test": 3,
      "skill": "listening",
      "question": 1,
      "group_id": null
    },
    "category": "representation",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "1112 years",
    "source": "practicepteonline.com",
    "source_value": "1.5 year",
    "page_raw_value": "1½ years",
    "basis": "视觉批 A（visual_batchA.png）：官方印 '1½ years'，½ 字形被提取为 '1112'；pte '1.5 year' 数值相同（1.5），表示法差异（分数/小数、单复数）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_4.pdf",
      "page": 157,
      "sha256": "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "1½ years",
    "equivalents": [
      "1.5 year"
    ],
    "artifact_values": [
      "1112 years"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-10",
    "identity": {
      "book": 5,
      "test": 1,
      "skill": "listening",
      "question": 4,
      "group_id": null
    },
    "category": "source_error",
    "action": "correct",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "Pallisades",
    "source": "practicepteonline.com",
    "source_value": "palisades",
    "page_raw_value": "Pallisades",
    "basis": "视觉批 A：官方答案页 p153 印 'Pallisades'；官方原文 p129 逐字母拼读 'P-A-L-L-I-S-A-0-E-S'（0 为 D 的提取伪影）；pte 小写 'palisades' 为来源错误（专名大写）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 153,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页 + 官方原文行交叉核验（视觉批 + dumpfull + 原文）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": "palisades",
    "to": "Pallisades",
    "book_value": "Pallisades",
    "equivalents": [],
    "artifact_values": [],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-11",
    "identity": {
      "book": 5,
      "test": 2,
      "skill": "listening",
      "question": 9,
      "group_id": null
    },
    "category": "source_error",
    "action": "correct",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "Grantingham",
    "source": "practicepteonline.com",
    "source_value": "grantigham",
    "page_raw_value": "Grantingham",
    "basis": "视觉批 A：官方答案页 p155 印 'Grantingham'；官方原文 p135 'speak to John Grantingham about that'；pte 'grantigham' 拼写错误",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 155,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页 + 官方原文行交叉核验（视觉批 + dumpfull + 原文）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": "grantigham",
    "to": "Grantingham",
    "book_value": "Grantingham",
    "equivalents": [],
    "artifact_values": [],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-12",
    "identity": {
      "book": 5,
      "test": 2,
      "skill": "listening",
      "question": 18,
      "group_id": "g-5-2-18-20"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E",
      "F"
    ],
    "page_raw_value": "18-20 IN ANY ORDER + C/E/F 垂直堆叠（x≈61-62：'c'[026] 'E'[028] 'F'[029]）",
    "basis": "官方键为 '18-20 IN ANY ORDER' 组，字母 C/E/F 垂直堆叠（提取器仅捕获首个字母 'c'，dumpfull_b5_p155.txt）；pte 集合 [C,E,F] 与官方集合一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 155,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E",
      "F"
    ],
    "equivalents": [
      [
        "C",
        "E",
        "F"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-5-2-18-20",
      "input_numbers": [
        18,
        19,
        20
      ],
      "accepted_sets": [
        [
          "C",
          "E",
          "F"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-13",
    "identity": {
      "book": 5,
      "test": 2,
      "skill": "listening",
      "question": 19,
      "group_id": "g-5-2-18-20"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E",
      "F"
    ],
    "page_raw_value": "18-20 IN ANY ORDER + C/E/F 垂直堆叠",
    "basis": "同 Q18：官方 'IN ANY ORDER' 组含 C/E/F；pte 集合一致（dumpfull_b5_p155.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 155,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E",
      "F"
    ],
    "equivalents": [
      [
        "C",
        "E",
        "F"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-5-2-18-20",
      "input_numbers": [
        18,
        19,
        20
      ],
      "accepted_sets": [
        [
          "C",
          "E",
          "F"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-14",
    "identity": {
      "book": 5,
      "test": 2,
      "skill": "listening",
      "question": 20,
      "group_id": "g-5-2-18-20"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E",
      "F"
    ],
    "page_raw_value": "18-20 IN ANY ORDER + C/E/F 垂直堆叠",
    "basis": "同 Q18：官方 'IN ANY ORDER' 组含 C/E/F；pte 集合一致（dumpfull_b5_p155.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 155,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E",
      "F"
    ],
    "equivalents": [
      [
        "C",
        "E",
        "F"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-5-2-18-20",
      "input_numbers": [
        18,
        19,
        20
      ],
      "accepted_sets": [
        [
          "C",
          "E",
          "F"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-15",
    "identity": {
      "book": 5,
      "test": 3,
      "skill": "listening",
      "question": 11,
      "group_id": "g-5-3-11-12"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN EITHER ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E"
    ],
    "page_raw_value": "11 IN EITHER ORDER + C/E 垂直堆叠（'c'[016] x=65.4, 'E'[018] x=65.8）",
    "basis": "官方键为 'IN EITHER ORDER' 组，字母 C/E 垂直堆叠（提取仅捕获 'c'，dumpfull_b5_p157.txt）；pte 集合 [C,E] 一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 157,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E"
    ],
    "equivalents": [
      [
        "C",
        "E"
      ]
    ],
    "artifact_values": [
      "IN EITHER ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-5-3-11-12",
      "input_numbers": [
        11,
        12
      ],
      "accepted_sets": [
        [
          "C",
          "E"
        ]
      ],
      "required_count": 2,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-16",
    "identity": {
      "book": 5,
      "test": 3,
      "skill": "listening",
      "question": 12,
      "group_id": "g-5-3-11-12"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN EITHER ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E"
    ],
    "page_raw_value": "11 IN EITHER ORDER + C/E 垂直堆叠",
    "basis": "同 Q11：官方 'IN EITHER ORDER' 组含 C/E；pte 集合一致（dumpfull_b5_p157.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 157,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E"
    ],
    "equivalents": [
      [
        "C",
        "E"
      ]
    ],
    "artifact_values": [
      "IN EITHER ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-5-3-11-12",
      "input_numbers": [
        11,
        12
      ],
      "accepted_sets": [
        [
          "C",
          "E"
        ]
      ],
      "required_count": 2,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-17",
    "identity": {
      "book": 5,
      "test": 4,
      "skill": "listening",
      "question": 3,
      "group_id": null
    },
    "category": "extraction_artifact",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "I year",
    "source": "practicepteonline.com",
    "source_value": "1 year",
    "page_raw_value": "1 year",
    "basis": "视觉批 A：官方印 '1 year'；数字 1 被提取为 'I'；pte '1 year' 与官方一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 159,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "1 year",
    "equivalents": [
      "1 year"
    ],
    "artifact_values": [
      "I year"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-18",
    "identity": {
      "book": 5,
      "test": 4,
      "skill": "listening",
      "question": 9,
      "group_id": null
    },
    "category": "extraction_artifact",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "lOO",
    "source": "practicepteonline.com",
    "source_value": "100",
    "page_raw_value": "100",
    "basis": "视觉批 A：官方印 '100'（l+O+O 字形伪影）；pte '100' 正确",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 159,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "100",
    "equivalents": [
      "100"
    ],
    "artifact_values": [
      "lOO"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-19",
    "identity": {
      "book": 5,
      "test": 4,
      "skill": "listening",
      "question": 14,
      "group_id": null
    },
    "category": "representation",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "10",
    "source": "practicepteonline.com",
    "source_value": "ten",
    "page_raw_value": "10",
    "basis": "数字 vs 英文单词，值相同（10）；语义一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 159,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "10",
    "equivalents": [
      "ten"
    ],
    "artifact_values": [
      "10"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-20",
    "identity": {
      "book": 5,
      "test": 4,
      "skill": "listening",
      "question": 16,
      "group_id": null
    },
    "category": "representation",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "4",
    "source": "practicepteonline.com",
    "source_value": "four",
    "page_raw_value": "4",
    "basis": "数字 vs 英文单词，值相同（4）；语义一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 159,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "4",
    "equivalents": [
      "four"
    ],
    "artifact_values": [
      "4"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-21",
    "identity": {
      "book": 5,
      "test": 4,
      "skill": "listening",
      "question": 19,
      "group_id": null
    },
    "category": "source_error",
    "action": "correct",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "send (out/the) newsletter(s)",
    "source": "practicepteonline.com",
    "source_value": "end newsletter",
    "page_raw_value": "send (out/the) newsletter(s)",
    "basis": "视觉批 A：官方答案页 p159 印 'send (out/the) newsletter(s)'；官方原文 p149 'send out newsletters to you regularly'；pte 'end newsletter' 丢失 's' 前缀并截断复数",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_5.pdf",
      "page": 159,
      "sha256": "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页 + 官方原文行交叉核验（视觉批 + dumpfull + 原文）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": "end newsletter",
    "to": "send (out/the) newsletter(s)",
    "book_value": "send (out/the) newsletter(s)",
    "equivalents": [],
    "artifact_values": [],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-22",
    "identity": {
      "book": 6,
      "test": 1,
      "skill": "listening",
      "question": 6,
      "group_id": null
    },
    "category": "extraction_artifact",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "I",
    "source": "practicepteonline.com",
    "source_value": "1",
    "page_raw_value": "1",
    "basis": "视觉批 B：官方印 '1'（窄字形 I）；pte '1' 正确",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 152,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "1",
    "equivalents": [
      "1"
    ],
    "artifact_values": [
      "I"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-23",
    "identity": {
      "book": 6,
      "test": 1,
      "skill": "listening",
      "question": 7,
      "group_id": null
    },
    "category": "representation",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "4.30 10 (am), (pm)",
    "source": "practicepteonline.com",
    "source_value": "10 to 4.30",
    "page_raw_value": "10 (am), 4.30 (pm)",
    "basis": "视觉批 B：官方印 '10 (am), 4.30 (pm)'（提取 token 顺序/基线合并伪影）；pte '10 to 4.30' 表示同一时间区间（10am–4.30pm）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 152,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "10 (am), 4.30 (pm)",
    "equivalents": [
      "10 to 4.30"
    ],
    "artifact_values": [
      "4.30 10 (am), (pm)"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-24",
    "identity": {
      "book": 6,
      "test": 1,
      "skill": "listening",
      "question": 38,
      "group_id": "g-6-1-38-40"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E",
      "F"
    ],
    "page_raw_value": "38-40 IN ANY ORDER + C/E/F 垂直堆叠（x≈285：'c'[029] 'E'[030] 'F'[031]）",
    "basis": "官方键为 '38-40 IN ANY ORDER' 组，字母 C/E/F 垂直堆叠（提取仅捕获 'c'，dumpfull_b6_p152.txt）；pte 集合 [C,E,F] 一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 152,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E",
      "F"
    ],
    "equivalents": [
      [
        "C",
        "E",
        "F"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-6-1-38-40",
      "input_numbers": [
        38,
        39,
        40
      ],
      "accepted_sets": [
        [
          "C",
          "E",
          "F"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-25",
    "identity": {
      "book": 6,
      "test": 1,
      "skill": "listening",
      "question": 39,
      "group_id": "g-6-1-38-40"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E",
      "F"
    ],
    "page_raw_value": "38-40 IN ANY ORDER + C/E/F 垂直堆叠",
    "basis": "同 Q38：官方 'IN ANY ORDER' 组含 C/E/F；pte 集合一致（dumpfull_b6_p152.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 152,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E",
      "F"
    ],
    "equivalents": [
      [
        "C",
        "E",
        "F"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-6-1-38-40",
      "input_numbers": [
        38,
        39,
        40
      ],
      "accepted_sets": [
        [
          "C",
          "E",
          "F"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-26",
    "identity": {
      "book": 6,
      "test": 1,
      "skill": "listening",
      "question": 40,
      "group_id": "g-6-1-38-40"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E",
      "F"
    ],
    "page_raw_value": "38-40 IN ANY ORDER + C/E/F 垂直堆叠",
    "basis": "同 Q38：官方 'IN ANY ORDER' 组含 C/E/F；pte 集合一致（dumpfull_b6_p152.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 152,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E",
      "F"
    ],
    "equivalents": [
      [
        "C",
        "E",
        "F"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-6-1-38-40",
      "input_numbers": [
        38,
        39,
        40
      ],
      "accepted_sets": [
        [
          "C",
          "E",
          "F"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-27",
    "identity": {
      "book": 6,
      "test": 2,
      "skill": "listening",
      "question": 18,
      "group_id": "g-6-2-18-20"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "D",
      "G"
    ],
    "page_raw_value": "18-20 IN ANY ORDER + C/D/G 垂直堆叠（x≈66：'c'[025] 'D'[027] 'G'[028]）",
    "basis": "官方键为 '18-20 IN ANY ORDER' 组，字母 C/D/G 垂直堆叠（提取仅捕获 'c'，dumpfull_b6_p154.txt）；pte 集合 [C,D,G] 一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 154,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "D",
      "G"
    ],
    "equivalents": [
      [
        "C",
        "D",
        "G"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-6-2-18-20",
      "input_numbers": [
        18,
        19,
        20
      ],
      "accepted_sets": [
        [
          "C",
          "D",
          "G"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-28",
    "identity": {
      "book": 6,
      "test": 2,
      "skill": "listening",
      "question": 19,
      "group_id": "g-6-2-18-20"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "D",
      "G"
    ],
    "page_raw_value": "18-20 IN ANY ORDER + C/D/G 垂直堆叠",
    "basis": "同 Q18：官方 'IN ANY ORDER' 组含 C/D/G；pte 集合一致（dumpfull_b6_p154.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 154,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "D",
      "G"
    ],
    "equivalents": [
      [
        "C",
        "D",
        "G"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-6-2-18-20",
      "input_numbers": [
        18,
        19,
        20
      ],
      "accepted_sets": [
        [
          "C",
          "D",
          "G"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-29",
    "identity": {
      "book": 6,
      "test": 2,
      "skill": "listening",
      "question": 20,
      "group_id": "g-6-2-18-20"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "D",
      "G"
    ],
    "page_raw_value": "18-20 IN ANY ORDER + C/D/G 垂直堆叠",
    "basis": "同 Q18：官方 'IN ANY ORDER' 组含 C/D/G；pte 集合一致（dumpfull_b6_p154.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 154,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "D",
      "G"
    ],
    "equivalents": [
      [
        "C",
        "D",
        "G"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-6-2-18-20",
      "input_numbers": [
        18,
        19,
        20
      ],
      "accepted_sets": [
        [
          "C",
          "D",
          "G"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-30",
    "identity": {
      "book": 6,
      "test": 3,
      "skill": "listening",
      "question": 2,
      "group_id": null
    },
    "category": "representation",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "27.01.1973",
    "source": "practicepteonline.com",
    "source_value": "27-1-1973",
    "page_raw_value": "27.01.1973",
    "basis": "同一日期不同分隔符（. vs -）与补零；值相同（27/01/1973）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 156,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "27.01.1973",
    "equivalents": [
      "27-1-1973"
    ],
    "artifact_values": [
      "27.01.1973"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-31",
    "identity": {
      "book": 6,
      "test": 3,
      "skill": "listening",
      "question": 10,
      "group_id": null
    },
    "category": "extraction_artifact",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "intemet",
    "source": "practicepteonline.com",
    "source_value": "internet",
    "page_raw_value": "internet",
    "basis": "'rn'→'m' 连字伪影；pte 'internet' 正确",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 156,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "internet",
    "equivalents": [
      "internet"
    ],
    "artifact_values": [
      "intemet"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-32",
    "identity": {
      "book": 6,
      "test": 4,
      "skill": "listening",
      "question": 6,
      "group_id": null
    },
    "category": "source_error",
    "action": "correct",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "conference pack",
    "source": "practicepteonline.com",
    "source_value": "conference park",
    "page_raw_value": "conference pack",
    "basis": "官方答案页 p158 印 'conference pack'；官方原文 p146 'The details are all in our conference pack, which I'll send you.'；pte 'conference park' 拼写错误（park/pack）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 158,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页 + 官方原文行交叉核验（视觉批 + dumpfull + 原文）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": "conference park",
    "to": "conference pack",
    "book_value": "conference pack",
    "equivalents": [],
    "artifact_values": [],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-33",
    "identity": {
      "book": 6,
      "test": 4,
      "skill": "listening",
      "question": 10,
      "group_id": null
    },
    "category": "representation",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "21A",
    "source": "practicepteonline.com",
    "source_value": "21 A",
    "page_raw_value": "21A",
    "basis": "空格差异，值相同（21A）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 158,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "21A",
    "equivalents": [
      "21 A"
    ],
    "artifact_values": [
      "21A"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-34",
    "identity": {
      "book": 6,
      "test": 4,
      "skill": "listening",
      "question": 24,
      "group_id": null
    },
    "category": "extraction_artifact",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "pnmary",
    "source": "practicepteonline.com",
    "source_value": "primary",
    "page_raw_value": "primary",
    "basis": "'ri'→'n' 连字伪影；pte 'primary' 正确",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 158,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "primary",
    "equivalents": [
      "primary"
    ],
    "artifact_values": [
      "pnmary"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-35",
    "identity": {
      "book": 6,
      "test": 4,
      "skill": "listening",
      "question": 28,
      "group_id": "g-6-4-28-30"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E",
      "F"
    ],
    "page_raw_value": "28-30 IN ANY ORDER + C/E/F 垂直堆叠（x≈284：'c'[012] 'E'[014] 'F'[015]）",
    "basis": "官方键为 '28-30 IN ANY ORDER' 组，字母 C/E/F 垂直堆叠（提取仅捕获 'c'，dumpfull_b6_p158.txt）；pte 集合 [C,E,F] 一致",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 158,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E",
      "F"
    ],
    "equivalents": [
      [
        "C",
        "E",
        "F"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-6-4-28-30",
      "input_numbers": [
        28,
        29,
        30
      ],
      "accepted_sets": [
        [
          "C",
          "E",
          "F"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-36",
    "identity": {
      "book": 6,
      "test": 4,
      "skill": "listening",
      "question": 29,
      "group_id": "g-6-4-28-30"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E",
      "F"
    ],
    "page_raw_value": "28-30 IN ANY ORDER + C/E/F 垂直堆叠",
    "basis": "同 Q28：官方 'IN ANY ORDER' 组含 C/E/F；pte 集合一致（dumpfull_b6_p158.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 158,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E",
      "F"
    ],
    "equivalents": [
      [
        "C",
        "E",
        "F"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-6-4-28-30",
      "input_numbers": [
        28,
        29,
        30
      ],
      "accepted_sets": [
        [
          "C",
          "E",
          "F"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-37",
    "identity": {
      "book": 6,
      "test": 4,
      "skill": "listening",
      "question": 30,
      "group_id": "g-6-4-28-30"
    },
    "category": "order_semantics",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "IN ANY ORDER c",
    "source": "practicepteonline.com",
    "source_value": [
      "C",
      "E",
      "F"
    ],
    "page_raw_value": "28-30 IN ANY ORDER + C/E/F 垂直堆叠",
    "basis": "同 Q28：官方 'IN ANY ORDER' 组含 C/E/F；pte 集合一致（dumpfull_b6_p158.txt）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 158,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": [
      "C",
      "E",
      "F"
    ],
    "equivalents": [
      [
        "C",
        "E",
        "F"
      ]
    ],
    "artifact_values": [
      "IN ANY ORDER c"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-6-4-28-30",
      "input_numbers": [
        28,
        29,
        30
      ],
      "accepted_sets": [
        [
          "C",
          "E",
          "F"
        ]
      ],
      "required_count": 3,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set"
    }
  },
  {
    "id": "adj-38",
    "identity": {
      "book": 6,
      "test": 4,
      "skill": "listening",
      "question": 35,
      "group_id": null
    },
    "category": "representation",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "I ,450",
    "source": "practicepteonline.com",
    "source_value": "1450",
    "page_raw_value": "1,450",
    "basis": "视觉批 B：官方印 '1,450'（I/1 字形伪影 + 千分位逗号）；pte '1450' 数值相同，表示法差异",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_6.pdf",
      "page": 158,
      "sha256": "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "1,450",
    "equivalents": [
      "1450"
    ],
    "artifact_values": [
      "I ,450"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-39",
    "identity": {
      "book": 7,
      "test": 2,
      "skill": "listening",
      "question": 2,
      "group_id": null
    },
    "category": "source_error",
    "action": "correct",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "(a) dentist",
    "source": "practicepteonline.com",
    "source_value": "730453",
    "page_raw_value": "(a) dentist",
    "basis": "官方答案页 p159 Q2='(a) dentist'；官方原文 p140 'Dentist. Q2'；pte 页面把题干给定值 'Contact number: 730453' 误当答案（该值出现在题目页 p38 行 [008]-[010]，且 pte 页面无 Occupation 字段）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_7.pdf",
      "page": 159,
      "sha256": "a219bf469ba75c39938a2a9d8bfd4bf15caf206e8c249d70d188ff4e36ad3b00"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页 + 官方原文行交叉核验（视觉批 + dumpfull + 原文）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": "730453",
    "to": "(a) dentist",
    "book_value": "(a) dentist",
    "equivalents": [],
    "artifact_values": [],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-40",
    "identity": {
      "book": 7,
      "test": 2,
      "skill": "listening",
      "question": 12,
      "group_id": null
    },
    "category": "source_error",
    "action": "correct",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "Newtown",
    "source": "practicepteonline.com",
    "source_value": "newton",
    "page_raw_value": "Newtown",
    "basis": "官方答案页 p159 印 'Newtown'；官方原文 p142 行 [005] 'stop D Newtown. QJJ Ql2'；pte 'newton' 拼写错误（缺 w、大小写）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_7.pdf",
      "page": 159,
      "sha256": "a219bf469ba75c39938a2a9d8bfd4bf15caf206e8c249d70d188ff4e36ad3b00"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页 + 官方原文行交叉核验（视觉批 + dumpfull + 原文）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": "newton",
    "to": "Newtown",
    "book_value": "Newtown",
    "equivalents": [],
    "artifact_values": [],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-41",
    "identity": {
      "book": 7,
      "test": 2,
      "skill": "listening",
      "question": 38,
      "group_id": null
    },
    "category": "extraction_artifact",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "VISlOn",
    "source": "practicepteonline.com",
    "source_value": "vision",
    "page_raw_value": "vision",
    "basis": "官方原文 p145 'bigger area of vision Q38'；键页 'VISlOn' 为 I/l 字形伪影；pte 'vision' 正确",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_7.pdf",
      "page": 159,
      "sha256": "a219bf469ba75c39938a2a9d8bfd4bf15caf206e8c249d70d188ff4e36ad3b00"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "vision",
    "equivalents": [
      "vision"
    ],
    "artifact_values": [
      "VISlOn"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-42",
    "identity": {
      "book": 7,
      "test": 3,
      "skill": "listening",
      "question": 7,
      "group_id": null
    },
    "category": "extraction_artifact",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "8659",
    "source": "practicepteonline.com",
    "source_value": "B659",
    "page_raw_value": "B659",
    "basis": "视觉批 B：官方印 'B659'（B→8 字形伪影）；官方原文 p147 'Roo:n B569- no sorry B659. I always get that wrong.'（说话人自我纠正为 B659）；pte 'B659' 正确",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_7.pdf",
      "page": 161,
      "sha256": "a219bf469ba75c39938a2a9d8bfd4bf15caf206e8c249d70d188ff4e36ad3b00"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "B659",
    "equivalents": [
      "B659"
    ],
    "artifact_values": [
      "8659"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-43",
    "identity": {
      "book": 7,
      "test": 4,
      "skill": "listening",
      "question": 2,
      "group_id": null
    },
    "category": "extraction_artifact",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "106337",
    "source": "practicepteonline.com",
    "source_value": "JO6337",
    "page_raw_value": "JO6337",
    "basis": "视觉批 B：官方印 'JO6337'（J→1、O→0 字形伪影）；官方原文 p152 'your passport number is JO 6337'；pte 'JO6337' 正确",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_7.pdf",
      "page": 163,
      "sha256": "a219bf469ba75c39938a2a9d8bfd4bf15caf206e8c249d70d188ff4e36ad3b00"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "JO6337",
    "equivalents": [
      "JO6337"
    ],
    "artifact_values": [
      "106337"
    ],
    "mapping": null,
    "group": null
  },
  {
    "id": "adj-44",
    "identity": {
      "book": 12,
      "test": 1,
      "skill": "listening",
      "question": 14,
      "group_id": null
    },
    "category": "extraction_artifact",
    "action": "none",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "C 15&16 ORDER EITHER IN A E",
    "source": "practicepteonline.com",
    "source_value": "C",
    "page_raw_value": "C",
    "basis": "官方键 Q14='C'（字母在题号下垂直堆叠，行 [029]-[030]）；提取器把 Q15&16 的 'IN EITHER ORDER'+'A'/'E' 并入 Q14 行（15px 续行限，行 [031]-[036]）；官方 Q15&16=A,E 乱序；pte Q14='C' 正确",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_12.pdf",
      "page": 117,
      "sha256": "f791300937f11d8380eba7b7997db1da751d66802a96aed996db704947e52407"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": null,
    "to": null,
    "book_value": "C",
    "equivalents": [
      "C"
    ],
    "artifact_values": [
      "C 15&16 ORDER EITHER IN A E"
    ],
    "mapping": null,
    "group": {
      "group_id": "g-12-1-15-16",
      "input_numbers": [
        15,
        16
      ],
      "accepted_sets": [
        [
          "A",
          "E"
        ]
      ],
      "required_count": 2,
      "ordered": false,
      "allow_reuse": false,
      "scoring": "exact_set",
      "note": "Q15&16 IN EITHER ORDER；提取器把该组并入 Q14 行（行 [031]-[036]）"
    }
  },
  {
    "id": "adj-45",
    "identity": {
      "book": 17,
      "test": 4,
      "skill": "listening",
      "question": 38,
      "group_id": null
    },
    "category": "source_error",
    "action": "correct",
    "status": "resolved",
    "origin": "diff",
    "official_extracted": "steam",
    "source": "practicepteonline.com",
    "source_value": "Stream",
    "page_raw_value": "steam",
    "basis": "官方答案页 p125 行 [029] 列分析：右列 Q38 答案 token='steam'（x=295.6，dump_b17_p125_q38_cols.txt；视觉渲染 png_b17_p125_steam.png）；官方原文 p80 '38 • A lot of ___ is produced during the evaporation process'；pte 'Stream' 拼写错误（多 S、大写）",
    "pdf": {
      "file": "tmp_audit_ielts/downloads/book_17.pdf",
      "page": 125,
      "sha256": "90ae888c4cd495761fe5639418ca894e63c9e7066382ed9ffad6bd74a409726a"
    },
    "verifier": {
      "type": "independent_visual_review",
      "method": "官方答案页 + 官方原文行交叉核验（视觉批 + dumpfull + 原文）",
      "at": "2026-10-03T17:12:00+08:00"
    },
    "from": "Stream",
    "to": "steam",
    "book_value": "steam",
    "equivalents": [],
    "artifact_values": [],
    "mapping": null,
    "group": null
  }
];

/**
 * S08 组级官方核验覆盖（book 9 Test 1 Reading Passage 2）。
 * 来源：2026-10-04 对 book_9.pdf（扫描件）的 rapidocr 独立读数（150/300/600dpi，见 evidence.artifacts），
 * 覆盖网站版（practicepteonline raw-127.txt）的两处错误呈现：
 *   gv-01 分类+答案表示：Q21-26 官方为 YES/NO/NOT GIVEN（views of the writer），网站误作 TRUE/FALSE/NG；
 *   gv-02 字数限制：Q18-20 官方为 NO MORE THAN THREE WORDS AND/OR A NUMBER，网站作 NO MORE THAN TWO WORDS。
 * 应用语义：from 守卫 + 原值保留 + 官方值单独记录（见 question-index.mjs applyGroupVerifications）。
 */
export const GROUP_VERIFICATIONS_META = {
  "created_at": "2026-10-04",
  "created_by": "S08 agent OCR 复核（book_9.pdf 独立读数）",
  "purpose": "把官方 PDF 核验结论落为可追溯的组级覆盖（分类冲突 / 答案表示映射 / 字数限制冲突）",
  "summary": { "total": 2, "classification": 1, "word_limit": 1 },
  "official_pdfs": {
    "book_9.pdf": {
      "file": "tmp_audit_ielts/downloads/book_9.pdf",
      "sha256": "b25f954dd25e058dfc05913c8f3b9ffead6581aa23bb10f8f2e98e6314f7af24",
      "note": "扫描件（165 页，仅 4 页含 facebook.com/IELTSVN 水印文本层）；印刷页 = 文件页 + 8"
    }
  },
  "evidence_root": "ielts-data/runs/20261003T140007Z-repair/scratch/s08/"
};

export const GROUP_VERIFICATIONS = [
  {
    "id": "gv-01",
    "kind": "classification_conflict",
    "identity": {
      "book": 9,
      "variant": "academic",
      "skill": "reading",
      "test": "1",
      "part": "P2",
      "group_id": "cambridge:9:academic:reading:1:P2:G2",
      "range": [21, 26]
    },
    "from": {
      "type": "true_false_not_given",
      "classification_reason": "pool_overrides_instruction",
      "source_pool": ["TRUE", "FALSE", "NOT GIVEN"]
    },
    "to": { "type": "yes_no_not_given" },
    "answer_representation": {
      "form": "yes_no_not_given",
      "numbers": [21, 22, 23, 24, 25, 26],
      "map": { "true": "YES", "false": "NO", "not given": "NOT GIVEN" },
      "official_values": {
        "21": "YES",
        "22": "YES",
        "23": "NOT GIVEN",
        "24": "NO",
        "25": "NOT GIVEN",
        "26": "NO"
      }
    },
    "evidence": {
      "official_pdf": {
        "file": "tmp_audit_ielts/downloads/book_9.pdf",
        "sha256": "b25f954dd25e058dfc05913c8f3b9ffead6581aa23bb10f8f2e98e6314f7af24",
        "pages": "file_page 16 = printed_page 24（指令）；file_page 145 = printed_page 153（答案键）"
      },
      "instruction": {
        "file_page": 16,
        "printed_page": 24,
        "excerpt": "Do the following statements agree with the views of the writer in Reading Passage 2? In boxes 21-26 on your answer sheet, write YES if the statement agrees with the views of the writer / NO if the statement contradicts the views of the writer / NOT GIVEN if it is impossible to say what the writer thinks about this",
        "method": "rapidocr 150dpi 全页扫描 + 300dpi 复核 + 600dpi 裁剪复核",
        "note": "300dpi 全页 OCR 将 'NO' 读作 'ON'（字形伪影）；600dpi 裁剪读出 'NO'（conf 0.64），与 150dpi 一致",
        "artifacts": [
          "ielts-data/runs/20261003T140007Z-repair/scratch/s08/b9-ocr-sweep-150.jsonl",
          "ielts-data/runs/20261003T140007Z-repair/scratch/s08/b9-hi-300.json",
          "ielts-data/runs/20261003T140007Z-repair/scratch/s08/b9-600-p16-ynng.json"
        ]
      },
      "answer_key": {
        "file_page": 145,
        "printed_page": 153,
        "excerpt": "21 YES / 22 YES / 23 NOT GIVEN / 24 NO / 25 NOT GIVEN / 26 NO",
        "method": "rapidocr 300dpi 全页 + 600dpi 左/右栏裁剪复核（双次独立读数一致）",
        "artifacts": [
          "ielts-data/runs/20261003T140007Z-repair/scratch/s08/b9-hi-300.json",
          "ielts-data/runs/20261003T140007Z-repair/scratch/s08/b9-600-p145-left.json",
          "ielts-data/runs/20261003T140007Z-repair/scratch/s08/b9-600-p145-right.json"
        ]
      },
      "source_version": {
        "source": "practicepteonline",
        "file": "tmp_audit_ielts/completeness_20261003/raw-127.txt",
        "sha256": "6fedb6d909f36f23aed5a6d7d7661577a40fe10190ade36bc6a5fe558cd50675",
        "instruction_form": "TRUE / FALSE / NOT GIVEN",
        "answers": {
          "21": "true",
          "22": "true",
          "23": "not given",
          "24": "false",
          "25": "not given",
          "26": "false"
        },
        "note": "网站把官方 YES/NO/NG 错误呈现为 TRUE/FALSE/NG；网站原值保留于 answers[qid].raw，官方值记录于 answers[qid].official"
      },
      "notes": [
        "官方键 Q19 印 'radio (waves/signals)'，网站 raw 为 'radio (waves)'：括号备选写法差异，语义等价，未改值",
        "官方键 Q16/Q17（headings i/ii）在两次独立读数中均未被捕获；本核验不声称其值"
      ]
    },
    "verifier": {
      "type": "agent_ocr_review",
      "method": "rapidocr 三次独立读数（150/300/600dpi）+ 逐条比对",
      "at": "2026-10-04"
    }
  },
  {
    "id": "gv-02",
    "kind": "word_limit_conflict",
    "identity": {
      "book": 9,
      "variant": "academic",
      "skill": "reading",
      "test": "1",
      "part": "P2",
      "group_id": "cambridge:9:academic:reading:1:P2:G1",
      "range": [18, 20]
    },
    "from": { "word_limit": "NO MORE THAN TWO WORDS" },
    "to": { "word_limit": "NO MORE THAN THREE WORDS AND/OR A NUMBER" },
    "evidence": {
      "official_pdf": {
        "file": "tmp_audit_ielts/downloads/book_9.pdf",
        "sha256": "b25f954dd25e058dfc05913c8f3b9ffead6581aa23bb10f8f2e98e6314f7af24",
        "pages": "file_page 16 = printed_page 24"
      },
      "instruction": {
        "file_page": 16,
        "printed_page": 24,
        "excerpt": "Answer the questions below. Choose NO MORE THAN THREE WORDS AND/OR A NUMBER from the passage for each answer. Write your answers in boxes 18--20 on your answer sheet.",
        "method": "rapidocr 150dpi + 300dpi 两次独立全页读数（关键短语 conf 0.90）",
        "artifacts": [
          "ielts-data/runs/20261003T140007Z-repair/scratch/s08/b9-ocr-sweep-150.jsonl",
          "ielts-data/runs/20261003T140007Z-repair/scratch/s08/b9-hi-300.json"
        ]
      },
      "source_version": {
        "source": "practicepteonline",
        "file": "tmp_audit_ielts/completeness_20261003/raw-127.txt",
        "word_limit": "NO MORE THAN TWO WORDS"
      },
      "notes": [
        "600dpi 裁剪复核该行（rect 40,90,510,135）返回 0 词（OCR 异常，未解释）；150dpi 与 300dpi 两次独立读数一致，证据充分"
      ]
    },
    "verifier": {
      "type": "agent_ocr_review",
      "method": "rapidocr 两次独立全页读数（150/300dpi）",
      "at": "2026-10-04"
    }
  }
];

/** 按 id 取组级核验（测试用） */
export function groupVerificationById(id) {
  return GROUP_VERIFICATIONS.find((v) => v.id === id) || null;
}

/** 按完整 identity 过滤（book/test 必填；skill 默认 listening） */
export function decisionsFor(book, test, opts = {}) {
  const skill = opts.skill || "listening";
  return DECISIONS.filter(
    (d) => d.identity.book === Number(book) && d.identity.test === Number(test) && (!d.identity.skill || d.identity.skill === skill)
  );
}

/** 单题裁决（无则 null） */
export function decisionForQuestion(book, test, question, opts = {}) {
  return decisionsFor(book, test, opts).find((d) => d.identity.question === Number(question)) || null;
}

/** 按裁决条目 id 取（测试用） */
export function decisionById(id) {
  return DECISIONS.find((d) => d.id === id) || null;
}

/** 组裁决：group_id -> group spec（仅含 group 的裁决条目） */
export function groupDecisionsFor(book, test, opts = {}) {
  const out = new Map();
  for (const d of decisionsFor(book, test, opts)) {
    if (d.group) out.set(d.group.group_id, { ...d.group, decision_id: d.id, question: d.identity.question });
  }
  return out;
}

/** number -> {from,to,basis,decision_id}（仅 action=correct 的窄修正） */
export function correctionsFor(book, test, opts = {}) {
  const out = new Map();
  for (const d of decisionsFor(book, test, opts)) {
    if (d.action === "correct" && d.from != null) {
      out.set(d.identity.question, { from: d.from, to: d.to, basis: d.basis, decision_id: d.id });
    }
  }
  return out;
}

/**
 * 应用裁决窄修正到 pte 结果形状（{ok, answer_key, questions[]}）。
 * 非破坏性：仅当当前值 === from 时替换；from 不匹配 -> adjudication_stale（保留旧值，不强套）。
 * 返回带 answer_corrections / adjudication_stale 的新对象（无变化时原样返回）。
 */
export function applyAdjudications(book, test, r) {
  const corrections = correctionsFor(book, test);
  if (!corrections.size || !r || !r.ok || !Array.isArray(r.answer_key)) return r;
  const applied = [];
  const stale = [];
  const answer_key = r.answer_key.map((v, i) => {
    const c = corrections.get(i + 1);
    if (!c) return v;
    if (v === c.from) {
      applied.push({ question: i + 1, from: c.from, to: c.to, basis: c.basis, decision_id: c.decision_id });
      return c.to;
    }
    stale.push({ question: i + 1, decision_id: c.decision_id, expected_from: c.from, actual: v, reason: "upstream_value_changed" });
    return v;
  });
  const questions = Array.isArray(r.questions)
    ? r.questions.map((q) => {
        const c = corrections.get(q.number);
        if (c && q.answer === c.from) return { ...q, answer: c.to, answer_decision_id: c.decision_id };
        return q;
      })
    : r.questions;
  if (!applied.length && !stale.length) return r;
  const out = { ...r, answer_key, questions };
  if (applied.length) out.answer_corrections = applied;
  if (stale.length) out.adjudication_stale = stale;
  return out;
}
