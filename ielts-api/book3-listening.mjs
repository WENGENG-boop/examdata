/**
 * book3-listening.mjs — 剑3 听力 T2–T4 静态转录转换器（S12 融合；只读、离线、无网络、无写盘）
 *
 * 数据来源（全部为本地已验证证据）：
 * - PDF: tmp_audit_ielts/downloads/book_3.pdf
 *   （sha256 da273b47cbfa1fe324b2f289374bcfdbc7276a763e216be4f86ae6a070f06845；179 页；file page = printed page + 4）
 * - 文本层转储: derived/pdf/book3-txt/book3-pXXXX.txt
 * - 位图区域 OCR: derived/ocr/book3-listening-ocr.json / book3-listening-ocr2.json
 *   （rapidocr-onnxruntime 1.2.3 @300dpi；位图笔记区域文本由 OCR 转录）
 * - 图形/表格 bbox: derived/pdf/book3-extract.json
 * - 官方答案键页: file page 155（T2）/ 157（T3）/ 159（T4）
 *   （逐词 x 坐标核实；左右两栏同 y 行合并陷阱已排除，见 docs/ielts/EXECUTION_CHECKLIST.md S12）
 *
 * 规则（计划 S12）：
 * - 只覆盖 T2/T3/T4 听力；T1 已有 PTE 源，不在本模块处理。
 * - 官方答案键原样保留（含 NOT / ACCEPT / 压缩斜杠形式），不猜测、不补全；特殊标记入 note。
 * - 空位/缺答案不移位；题号 ↔ 槽位 ↔ 答案一一对应（40 题/套）。
 * - 位图笔记区域文本由 OCR 转录并记 content note；图片选项不伪造文字（assets + note，如实 partial）。
 * - 表格/地图/笔记资产以本地 PNG 或 source_ref 记录；本模块不生成任何占位内容。
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { expectedFor } from "./pte.mjs";

export const B3_PARSER_VERSION = "book3-listening/1.0.0";
export const B3_TESTS = Object.freeze(["2", "3", "4"]);

const PDF_REL = "tmp_audit_ielts/downloads/book_3.pdf";
const RUN_REL = "ielts-data/runs/20261003T140007Z-repair";
const OCR_RELS = Object.freeze([
  `${RUN_REL}/derived/ocr/book3-listening-ocr.json`,
  `${RUN_REL}/derived/ocr/book3-listening-ocr2.json`,
]);
const ASSET_DIR_REL = `${RUN_REL}/derived/pdf/book3-assets`;
const KEY_PAGE = Object.freeze({ 2: 155, 3: 157, 4: 159 });
const KEY_DECISION = Object.freeze({
  2: "b3-t2-listening-official-key",
  3: "b3-t3-listening-official-key",
  4: "b3-t4-listening-official-key",
});

const OCR_NOTE =
  "原书该区域为位图；文本经 OCR（book3-listening-ocr*.json，rapidocr-onnxruntime@300dpi）转录并逐行核对";

function sha256Of(file) {
  try {
    return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
  } catch {
    return null;
  }
}

/* ------------------------------ 构造工具 ------------------------------ */

const img = (fig) => ({
  kind: "image",
  source_ref: `pdf:book3:${fig.replace("-fig", ":fig")}`,
  local_path: `${ASSET_DIR_REL}/book3-${fig}.png`,
});

const tableAsset = (filePage) => ({
  kind: "table",
  source_ref: `pdf:book3:p${filePage}:table`,
  local_path: null,
});

const slot = (number, kind, prompt, options) => ({
  number,
  kind,
  prompt,
  options: options || null,
});

const cellGap = (number, prompt) => slot(number, "cell_gap", prompt);
const inputSlot = (number, prompt) => slot(number, "input", prompt);
const lineSlot = (number, prompt, options) => slot(number, "line", prompt, options);

const mcOptions = (texts) => texts.map((text, i) => ({ label: "ABCD"[i], text }));

function group(test, index, filePage, def) {
  const numbers = def.numbers;
  return {
    index,
    numbers,
    range: [numbers[0], numbers[numbers.length - 1]],
    instruction: def.instruction,
    shared_prompt: def.shared_prompt || null,
    heading_text: def.heading || null,
    word_limit: null,
    slots: def.slots,
    pools: def.pools || [],
    assets: def.assets || [],
    notes: def.notes || null,
    source_ref: `pdf:book3:t${test}:p${filePage}`,
  };
}

function questionsOf(groups) {
  const out = [];
  for (const g of groups) {
    for (const s of g.slots) {
      out.push({
        number: s.number,
        prompt: s.prompt || null,
        group: g.index,
        options: s.options || null,
        notes: g.notes || null,
        source_ref: g.source_ref,
      });
    }
  }
  return out;
}

/** 官方答案槽位：raw=官方键原样字符串；official 记录来源与裁决 id；note 透传特殊标记 */
function answerSlots(test, entries) {
  const keyRef = `pdf:book3:answer-key:p${KEY_PAGE[test]}`;
  const decision = KEY_DECISION[test];
  return entries.map(([number, raw, note]) => {
    const official = {
      value: raw,
      form: "book_answer_key",
      decision_id: decision,
      source_ref: keyRef,
    };
    const entry = { number, raw, form: "book_answer_key", source_ref: keyRef, official };
    if (note) {
      entry.note = note;
      official.note = note;
    }
    return entry;
  });
}

/* ------------------------------ T2（file page 34/35/36/37/38/39/40/41；答案键 p155） ------------------------------ */

function t2() {
  const T = "2";
  const groups = [
    group(T, 0, 34, {
      numbers: [1, 2, 3, 4, 5],
      instruction: "Complete the table below. Write NO MORE THAN THREE WORDS OR A NUMBER for each answer.",
      heading: "Programme of Activities for First Day",
      slots: [
        cellGap(1, "(1) ......................"),
        cellGap(2, "Talk by (2) ......................."),
        cellGap(3, "Talk by (3) ......................."),
        cellGap(4, "(4) ......................."),
        cellGap(5, "(5) ....................... test"),
      ],
      assets: [tableAsset(34)],
      notes: [
        "原书表格首行时间单元格带斜体 Example 标注（示例行 10.00 已填）",
        "Place 列单元格跨 10.00/10.15/10.45 三行合并；文本层转录（derived/pdf/book3-txt/book3-p0034.txt）",
      ],
    }),
    group(T, 1, 35, {
      numbers: [6, 7, 8, 9, 10],
      instruction:
        "Label the rooms on the map below. Choose your answers from the box below and write them next to questions 6-10.",
      heading: "Questions 6-10",
      slots: [lineSlot(6, "(6)"), lineSlot(7, "(7)"), lineSlot(8, "(8)"), lineSlot(9, "(9)"), lineSlot(10, "(10)")],
      pools: [
        {
          kind: "box",
          source_ref: "pdf:book3:p35:box",
          options: [
            { label: "CL", text: "Computer Laboratory" },
            { label: "DO", text: "Director’s Office" },
            { label: "L", text: "Library" },
            { label: "MH", text: "Main Hall" },
            { label: "S", text: "Storeroom" },
            { label: "SAR", text: "Self Access Room" },
            { label: "SCR", text: "Student Common Room" },
            { label: "SR", text: "Staff Room" },
          ],
        },
      ],
      assets: [img("p0035-fig1")],
    }),
    group(T, 2, 36, {
      numbers: [11, 12, 13, 14, 15],
      instruction: "Complete the table below. Write NO MORE THAN THREE WORDS for each answer.",
      heading: "TYPE OF HELP | EXAMPLES",
      slots: [
        cellGap(11, "• (11) ......................."),
        cellGap(12, "(12) ......................."),
        cellGap(13, "• (13) ......................."),
        cellGap(14, "(14) ......................."),
        cellGap(15, "• (15) ......................."),
      ],
      assets: [tableAsset(36)],
      notes: ["文本层表格转录（derived/pdf/book3-txt/book3-p0036.txt）"],
    }),
    group(T, 3, 37, {
      numbers: [16, 17, 18, 19, 20],
      instruction: "Complete the notes below. Write NUMBERS OR NO MORE THAN THREE WORDS for each answer.",
      heading: "HELPLINE DETAILS",
      slots: [
        inputSlot(16, "Officer Jackie (16)"),
        inputSlot(17, "Telephone number (17)"),
        inputSlot(18, "(18) (Saturdays)"),
        inputSlot(19, "Ring or visit office for (19)"),
        inputSlot(20, "N.B. At peak times there may be a (20)"),
      ],
      assets: [img("p0037-fig1")],
      notes: [OCR_NOTE],
    }),
    group(T, 4, 38, {
      numbers: [21, 22, 23, 24],
      instruction: "Choose the correct letters A-C.",
      heading: "Questions 21-24",
      slots: [
        lineSlot(21, "At the start of the tutorial, the tutor emphasises the importance of", mcOptions(["interviews.", "staff selection.", "question techniques."])),
        lineSlot(22, "An example of a person who doesn’t ‘fit in’ is someone who", mcOptions(["is over-qualified for the job.", "lacks experience of the tasks set.", "disagrees with the rest of the group."])),
        lineSlot(23, "An important part of teamwork is having trust in your", mcOptions(["colleagues’ ability.", "employer’s directions.", "company training."])),
        lineSlot(24, "The tutor says that finding out personal information is", mcOptions(["a skill that needs practice.", "avoided by many interviewers.", "already a part of job interviews."])),
      ],
    }),
    group(T, 5, 39, {
      numbers: [25, 26, 27, 28, 29],
      instruction: "Complete the notes below. Write NO MORE THAN THREE WORDS for each answer.",
      heading: "Personality Questionnaires",
      slots: [
        inputSlot(25, "completed during (25)"),
        inputSlot(26, "used in the past by the (26) ... and the (27)"),
        inputSlot(27, "used in the past by the (26) ... and the (27)"),
        inputSlot(28, "nowadays used by (28) of large employers"),
        inputSlot(29, "written by (29) who say candidates tend to be truthful"),
      ],
      assets: [img("p0039-fig1")],
      notes: [OCR_NOTE, "questions about things like: working under pressure or keeping deadlines（无空行，原文保留）"],
    }),
    group(T, 6, 39, {
      numbers: [30],
      instruction: "Choose the correct letter A—C.",
      heading: "Question 30",
      slots: [
        lineSlot(30, "What is the tutor trying to do in the tutorial?", mcOptions(["describe one selection technique", "criticise traditional approaches to interviews", "illustrate how she uses personality questionnaires"])),
      ],
    }),
    group(T, 7, 40, {
      numbers: [31, 32],
      instruction: "Complete the notes below. Write NO MORE THAN THREE WORDS AND/OR A NUMBER for each answer.",
      heading: "HAT-MAKING PROJECT — Project Profile",
      slots: [inputSlot(31, "Type of school: (31)"), inputSlot(32, "Age of pupils: (32)")],
      assets: [img("p0040-fig1")],
      notes: [OCR_NOTE, "Example Answer / Name of student: Vivien（示例行已填）"],
    }),
    group(T, 8, 40, {
      numbers: [33, 34],
      instruction: "Label the diagrams. Write NO MORE THAN THREE WORDS for each answer.",
      heading: "Introduction to Hat-Making",
      slots: [
        inputSlot(33, "First Hat (Conical hat): cut into centre and (33) the cut"),
        inputSlot(34, "Second Hat (Pillbox): stick flaps to (34) of circle"),
      ],
      assets: [img("p0040-fig2"), img("p0040-fig3")],
      notes: [OCR_NOTE],
    }),
    group(T, 9, 41, {
      numbers: [35, 36, 37],
      instruction: "Complete the notes below. Write NO MORE THAN THREE WORDS for each answer.",
      heading: "DESIGN PHASE",
      slots: [
        inputSlot(35, "Stage A: Refer to research and design a hat (35)"),
        inputSlot(36, "Stage B: Make a small-scale (36) hat"),
        inputSlot(37, "Constraints — colours: (37)"),
      ],
      assets: [img("p0041-fig1")],
      notes: [OCR_NOTE],
    }),
    group(T, 10, 41, {
      numbers: [38, 39, 40],
      instruction: "Indicate who made the hats below. Write the appropriate letter A-E next to each name.",
      heading: "Hats A-E",
      slots: [lineSlot(38, "(38) Theresa"), lineSlot(39, "(39) Muriel"), lineSlot(40, "(40) Fabrice")],
      assets: [img("p0041-fig2")],
      notes: ["选项为原书图片（Hats A-E），未伪造文字选项；见 assets（如实 partial）"],
    }),
  ];
  const answers = answerSlots(T, [
    [1, "(the) Main Hall NOT Hall"],
    [2, "(the) Director (of) (Studies) // DOS"],
    [3, "(the) Student(s) Advisor/Adviser"],
    [4, "eleven/11 o’clock //11.00 (am)"],
    [5, "placement/English (test)"],
    [6, "L // Library"],
    [7, "MH // Main Hall"],
    [8, "CL // Computer Laboratory"],
    [9, "SR // Staff Room"],
    [10, "SCR // Student Common Room"],
    [11, "(overseas)(student(s’)) (tuition) fees"],
    [12, "(the) domestic (area)"],
    [13, "(essay(s’)) deadlines NOT ressay(s)"],
    [14, "social (life)"],
    [15, "outings // trips"],
    [16, "KOUACHI"],
    [17, "3269940"],
    [18, "ten/10(am)-/to4/four(pm)", "官方键原样保留（压缩斜杠形式，未猜测补全）"],
    [19, "(an) appointment(s)"],
    [20, "waiting list"],
    [21, "B // staff selection"],
    [22, "C // disagrees with the rest of the group"],
    [23, "A // colleagues’ ability"],
    [24, "C // already a part of job interviews"],
    [25, "selection (procedure)"],
    [26, "(the) (ancient) Chinese // (the) military // army", "EITHER ORDER（26-27 共享键行）"],
    [27, "(the) (ancient) Chinese // (the) military // army", "EITHER ORDER（26-27 共享键行）"],
    [28, "(almost) two thirds // f", "官方键原样保留（含 // f 标记）"],
    [29, "experts NOT expert"],
    [30, "A // describe one selection technique"],
    [31, "secondary"],
    [32, "14 // fourteen (year olds/years old)"],
    [33, "overlap // overlapping ACCEPT over(-)lap // over(-)lapping"],
    [34, "underside // underneath // bottom NOT side"],
    [35, "on paper // in two dimensions"],
    [36, "3/three(-)dimensional // 3(-)D"],
    [37, "MUST STATE ALL THREE white, grey/gray, brown"],
    [38, "C"],
    [39, "D"],
    [40, "A"],
  ]);
  const answerGroups = [
    {
      key: "b3-t2-q26-27",
      slots: [26, 27],
      inputs_raw: ["26", "27"],
      accept: ["(the) (ancient) Chinese", "(the) military // army"],
      required_count: 2,
      section: 3,
      source: "book3-pdf",
    },
  ];
  return { groups, answers, answerGroups };
}

/* ------------------------------ T3（file page 58/59/60/61/62/63；答案键 p157） ------------------------------ */

function t3() {
  const T = "3";
  const groups = [
    group(T, 0, 58, {
      numbers: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
      instruction:
        "Complete the notes below. Write NO MORE THAN THREE WORDS AND/OR A NUMBER for each answer.",
      heading: "NOTES - Christmas Dinner",
      slots: [
        inputSlot(1, "First choice: (1) ......................."),
        inputSlot(2, "Second choice: (2) ......................."),
        inputSlot(3, "Third choice: (3) ......................."),
        inputSlot(4, "Third choice tel. number: (4) ......................."),
        inputSlot(5, "Restaurant must have vegetarian food and a (5) ......................."),
        inputSlot(6, "Main course - Roast Dinner OR (6) ......................."),
        inputSlot(7, "(7) ....................... and letter of confirmation"),
        inputSlot(8, "and we must (8) ....................... in advance."),
        inputSlot(9, "Must confirm in writing by: (9) ......................."),
        inputSlot(10, "Put notice in (10) ......................."),
      ],
      assets: [img("p0058-fig1")],
      notes: [
        OCR_NOTE,
        "Example Answer / Number to book for: 45 / Date of dinner: 21 December（示例行已填）",
      ],
    }),
    group(T, 1, 59, {
      numbers: [11, 12, 13],
      instruction:
        "Complete the table below. Write NO MORE THAN THREE WORDS OR A NUMBER for each answer.",
      slots: [
        cellGap(11, "(11) £ ....................... per"),
        cellGap(12, "(12) ......................."),
        cellGap(13, "Where: (13) ......................."),
      ],
      assets: [tableAsset(59)],
      notes: ["表头：MEMBERSHIP OF SPORTS CENTRE（文本层转录 book3-p0059.txt）"],
    }),
    group(T, 2, 59, {
      numbers: [14, 15, 16],
      instruction: "Complete the table below. Write NO MORE THAN THREE WORDS for each answer.",
      slots: [
        cellGap(14, "Always bring sports (14) ......................."),
        cellGap(15, "when you come to (15) ....................... or use the Centre’s facilities"),
        cellGap(16, "Opening hours: 9 am to 10 pm on (16) ......................."),
      ],
      assets: [tableAsset(59)],
      notes: null,
    }),
    group(T, 3, 60, {
      numbers: [17, 18, 19, 20],
      instruction:
        "Look at the map of the Sports Complex below. Label the buildings on the map of the Sports Complex. Choose your answers from the box below and write your answers against Questions 17-20.",
      heading: "Questions 17-20",
      slots: [
        lineSlot(17, "(17)"),
        lineSlot(18, "(18)"),
        lineSlot(19, "(19)"),
        lineSlot(20, "(20)"),
      ],
      pools: [
        {
          kind: "box",
          source_ref: "pdf:book3:p60:box",
          options: [
            { label: null, text: "Arts Studio" },
            { label: null, text: "Football Pitch" },
            { label: null, text: "Tennis Courts" },
            { label: null, text: "Dance Studio" },
            { label: null, text: "Fitness Room" },
            { label: null, text: "Reception" },
            { label: null, text: "Squash Courts" },
          ],
        },
      ],
      assets: [img("p0060-fig1")],
      notes: null,
    }),
    group(T, 4, 61, {
      numbers: [21, 22, 23, 24, 25, 26, 27, 28, 29, 30],
      instruction:
        "Complete the form below. Write NO MORE THAN THREE WORDS AND/OR NUMBER for each answer.",
      heading: "YOUNG ELECTRONIC ENGINEER COMPETITION",
      slots: [
        inputSlot(21, "(21) ......................."),
        inputSlot(22, "Age: (22) ......................."),
        inputSlot(23, "Name of design: (23) ......................."),
        inputSlot(24, "Dimensions of equipment: (24) ......................."),
        inputSlot(25, "Special features: (25) ......................."),
        inputSlot(26, "(26) ......................."),
        inputSlot(27, "(27) ......................."),
        inputSlot(28, "(28) ......................."),
        inputSlot(29, "Other comments: need help to make (29) ......................."),
        inputSlot(30, "Send by: (30) ......................."),
      ],
      assets: [img("p0061-fig1")],
      notes: [OCR_NOTE],
    }),
    group(T, 5, 62, {
      numbers: [31, 32, 33],
      instruction: "Complete the table below. Write NO MORE THAN TWO WORDS for each answer.",
      heading: "NEW MEAT | CAN BE COMPARED TO | PROBLEM",
      slots: [
        cellGap(31, "kangaroo: (31) ......................."),
        cellGap(32, "kangaroo: (32) ......................."),
        cellGap(33, "ostrich: (33) ......................."),
      ],
      assets: [tableAsset(62)],
      notes: null,
    }),
    group(T, 6, 62, {
      numbers: [34, 35, 36],
      instruction: "Complete the table below. Write NO MORE THAN THREE WORDS for each answer.",
      heading: "OSTRICH PRODUCT | USE",
      slots: [
        cellGap(
          34,
          "Ostrich feathers: • tribal ceremonial dress • (34) ....................... • decorated hats"
        ),
        cellGap(35, "Ostrich hide: • (35) ......................."),
        cellGap(36, "Ostrich (36) .......................: • 'biltong'"),
      ],
      assets: [tableAsset(62)],
      notes: null,
    }),
    group(T, 7, 63, {
      numbers: [37, 38, 39, 40],
      instruction: "Choose the correct letters A-C.",
      slots: [
        slot(37, "line", "Ostrich meat", mcOptions([
          "has more protein than beef.",
          "tastes nearly as good as beef.",
          "is very filling.",
        ])),
        slot(38, "line", "One problem with ostrich farming in Britain is", mcOptions([
          "the climate.",
          "the cost of transporting birds.",
          "the price of ostrich eggs.",
        ])),
        slot(39, "line", "Ostrich chicks reared on farms", mcOptions([
          "must be kept in incubators until mature.",
          "are very independent.",
          "need looking after carefully.",
        ])),
        slot(40, "line", "The speaker suggests ostrich farms are profitable because", mcOptions([
          "little initial outlay is required.",
          "farmed birds are very productive.",
          "there is a good market for the meat.",
        ])),
      ],
      assets: [],
      notes: null,
    }),
  ];
  const answers = answerSlots(T, [
    [1, "Rajdoot"],
    [2, "Park View (Hotel)"],
    [3, "London Arms"],
    [4, "208657"],
    [5, "no/non(-)smoking section/area"],
    [6, "Lentil curry"],
    [7, "fifty pound(s)/£50 deposit // deposit (of) £50/fifty pound(s)"],
    [8, "choose/decide (on)/select (the) menu"],
    [9, "4 November", "ALTERNATIVE FORMS ACCEPTED（官方键标记）"],
    [10, "(the) Newsletter", "ALTERNATIVE FORMS ACCEPTED（官方键标记）"],
    [11, "(£)9.50"],
    [12, "year // annum NOT annual"],
    [13, "reception NOT Sports Centre"],
    [14, "card"],
    [15, "book"],
    [16, "weekdays"],
    [17, "Reception (Area)"],
    [18, "Dance Studio"],
    [19, "Squash Courts"],
    [20, "Fitness Room"],
    [21, "Anne Rea"],
    [22, "(both) 16 (years old)"],
    [23, "Blind (Jigsaw) Puzzle NOT Jigsaw"],
    [24, "20 (cm) 50 (cm) 2.5 (cm) // 2 and a half (cm)", "MUST BE IN ORDER（官方键标记）"],
    [25, "safe for children (it’s) educational price (is) good // inexpensive // not expensive // cheap (price) // (is) good price", "IN ANY ORDER（25-27 共享键行）"],
    [26, "safe for children (it’s) educational price (is) good // inexpensive // not expensive // cheap (price) // (is) good price", "IN ANY ORDER（25-27 共享键行）"],
    [27, "safe for children (it’s) educational price (is) good // inexpensive // not expensive // cheap (price) // (is) good price", "IN ANY ORDER（25-27 共享键行）"],
    [28, "electrics NOT electric"],
    [29, "plastic pieces // in plastic NOT pieces"],
    [30, "1 July", "ALTERNATIVE FORMS ACCEPTED（官方键标记）"],
    [31, "rabbit (meat)"],
    [32, "(rather) tough"],
    [33, "beef"],
    [34, "(ladies’) (feather) fans"],
    [35, "(delicate) (fine) (good quality) leather"],
    [36, "meat"],
    [37, "A // has more protein than beef"],
    [38, "C // the price of ostrich eggs"],
    [39, "C // need looking after carefully"],
    [40, "B // farmed birds are very productive"],
  ]);
  const answerGroups = [
    {
      key: "b3-t3-q25-27",
      slots: [25, 26, 27],
      inputs_raw: ["25", "26", "27"],
      accept: [
        "safe for children",
        "(it’s) educational",
        "price (is) good // inexpensive // not expensive // cheap (price) // (is) good price",
      ],
      required_count: 3,
      section: 3,
      source: "book3-pdf",
    },
  ];
  return { groups, answers, answerGroups };
}

/* ------------------------------ T4（file page 80/81/82/83/84/85/86/87；答案键 p159） ------------------------------ */

function t4() {
  const T = "4";
  const groups = [
    group(T, 0, 80, {
      numbers: [1, 2],
      instruction:
        "Complete the form opposite. Write NO MORE THAN THREE WORDS AND/OR A NUMBER for each answer.",
      heading: "Birth Statistics",
      slots: [
        inputSlot(1, "Weight: (1)"),
        inputSlot(2, "Length: (2) cms"),
      ],
      assets: [img("p0080-fig1")],
      notes: [
        OCR_NOTE,
        "Example 行已填：Date of birth: 10 August / Sex: male / First name: Tom / Surname: Lightfoot / Colour of hair: black",
      ],
    }),
    group(T, 1, 80, {
      numbers: [3, 4, 5],
      instruction:
        "Label the map. Choose your answers from the box below. Write the appropriate letters A-E on the map.",
      heading: "Questions 3-5",
      slots: [lineSlot(3, "(3)"), lineSlot(4, "(4)"), lineSlot(5, "(5)")],
      pools: [
        {
          kind: "box",
          source_ref: "pdf:book3:p80:box",
          options: [
            { label: "A", text: "State Bank" },
            { label: "B", text: "St George’s Hospital" },
            { label: "C", text: "Garage" },
            { label: "D", text: "Library" },
            { label: "E", text: "University" },
          ],
        },
      ],
      assets: [img("p0080-fig2")],
      notes: null,
    }),
    group(T, 2, 81, {
      numbers: [6, 7, 8, 9, 10],
      instruction: "Write NO MORE THAN THREE WORDS OR A NUMBER for each answer.",
      heading: "Gift for Susan | Gift for baby",
      slots: [
        cellGap(6, "What will they buy? (6) ......................."),
        cellGap(7, "What will they buy? (7) ......................."),
        cellGap(8, "Where will they buy the gifts? (8) ......................."),
        cellGap(9, "Where will they buy the gifts? (9) ......................."),
        cellGap(10, "Approximate prices? (10) $ ......................."),
      ],
      assets: [tableAsset(81)],
      notes: ["原书该表格无 Complete the table 字样指令，按单元格空缺回退识别"],
    }),
    group(T, 3, 82, {
      numbers: [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
      instruction:
        "Complete the table below. Write NO MORE THAN THREE WORDS for each answer. For the recommendation column, write A You must buy this. B Maybe you should buy this. C You should never buy this.",
      heading: "Questions 11-20",
      slots: [
        cellGap(11, "Unbreakable Vacuum Flask: contains no (11) ......................."),
        cellGap(12, "Unbreakable Vacuum Flask: keeps warm for (12) ......................."),
        cellGap(13, "Unbreakable Vacuum Flask: leaves (13) ......................."),
        cellGap(14, "Whistle Key Holder: (14) ......................."),
        cellGap(15, "Whistle Key Holder: doesn't work through (15) ......................."),
        cellGap(16, "Whistle Key Holder: recommendation (16) ......................."),
        cellGap(17, "Army Flashlight: useful for (17) ......................."),
        cellGap(18, "Army Flashlight: works (18) ......................."),
        cellGap(19, "Army Flashlight: has (19) ......................."),
        cellGap(20, "Decoy Camera: realistic (20) ......................."),
      ],
      assets: [tableAsset(82)],
      notes: null,
    }),
    group(T, 4, 83, {
      numbers: [21, 22, 23],
      instruction: "Choose the correct letters A—C.",
      slots: [
        slot(21, "line", "Amina’s project is about a local", mcOptions([
          "school.",
          "hospital.",
          "factory.",
        ])),
        slot(22, "line", "Dr Bryson particularly liked", mcOptions([
          "the introduction.",
          "the first chapter.",
          "the middle section.",
        ])),
        slot(23, "line", "Amina was surprised because she", mcOptions([
          "thought it was bad.",
          "wrote it quickly.",
          "found it difficult to do.",
        ])),
      ],
      assets: [],
      notes: null,
    }),
    group(T, 5, 83, {
      numbers: [24, 25, 26],
      instruction:
        "What suggestions does Dr Bryson make? Complete the table as follows. Write A if he says KEEP UNCHANGED / Write B if he says REWRITE / Write C if he says REMOVE COMPLETELY",
      heading: "Questions 24-26",
      slots: [
        cellGap(24, "Information on housing: (24)"),
        cellGap(25, "Interview data: (25)"),
        cellGap(26, "Chronology: (26)"),
      ],
      assets: [tableAsset(83)],
      notes: ["示例行：Section headings | B（原书已填）"],
    }),
    group(T, 6, 84, {
      numbers: [27, 28, 29, 30],
      instruction:
        "Complete the notes below. Write NO MORE THAN THREE WORDS AND/OR A NUMBER for each answer.",
      heading: "SCHEDULE OF ACTION",
      slots: [
        inputSlot(27, "Read (27) ....................... by Kate Oakwell."),
        inputSlot(28, "Make changes and show to (28) ......................."),
        inputSlot(29, "Do (29) ....................... by 29 June."),
        inputSlot(30, "Laser print before (30) ......................."),
      ],
      assets: [img("p0084-fig1")],
      notes: [OCR_NOTE, "Hand in to Faculty Office.（无空行，原文保留）"],
    }),
    group(T, 7, 85, {
      numbers: [31, 32, 33, 34],
      instruction: "Write NUMBERS AND/OR NO MORE THAN FOUR WORDS for each answer.",
      heading: "Questions 31-34",
      slots: [
        lineSlot(31, "Between what times is the road traffic lightest?"),
        lineSlot(32, "Who will notice the noise most?"),
        lineSlot(33, "Which day of the week has the least traffic?"),
        lineSlot(34, "What will be the extra cost of modifying houses?"),
      ],
      assets: [],
      notes: null,
    }),
    group(T, 8, 85, {
      numbers: [35],
      instruction: "Choose the correct letter A-D.",
      slots: [
        slot(35, "line", "The noise levels at the site can reach", mcOptions([
          "45 decibels.",
          "55 decibels.",
          "67 decibels.",
          "70 decibels.",
        ])),
      ],
      assets: [],
      notes: null,
    }),
    group(T, 9, 86, {
      numbers: [36, 37, 38],
      instruction:
        "Complete the table showing where devices used in reducing noise could be fitted in the houses. Write: W for walls / D for doors / C for ceilings",
      heading: "Questions 36-38",
      slots: [
        cellGap(36, "(36) double thickness plaster board"),
        cellGap(37, "(37) mechanical ventilation"),
        cellGap(38, "(38) air conditioning"),
      ],
      assets: [tableAsset(86)],
      notes: ["示例行：acoustic seals D（原书已填）"],
    }),
    group(T, 10, 86, {
      numbers: [39, 40],
      instruction: "Choose the correct letters A-D.",
      heading: "Questions 39-40",
      slots: [
        lineSlot(39, "Which is the correct construction for acoustic double glazing?"),
        lineSlot(40, "What is the best layout for the houses?"),
      ],
      assets: [img("p0086-fig2"), img("p0087-fig1")],
      notes: [
        "选项为原书图片（四种双玻结构图 / 四种布局图），未伪造文字选项；见 assets（如实 partial）",
      ],
    }),
  ];
  const answers = answerSlots(T, [
    [1, "4.25 // 4 1/4 // four and (a) quarter"],
    [2, "46 // forty-six"],
    [3, "A // State Bank"],
    [4, "D // Library"],
    [5, "C // Garage"],
    [6, "(a) (box) (of) chocolates"],
    [7, "(a) (soft) toy // (a) (teddy (bear)) // (a) bear"],
    [8, "(at the) market(s)"],
    [9, "(at the) market(s)"],
    [10, "($)35/thirty-five (dollars)"],
    [11, "glass"],
    [12, "eighteen/18 hours/hrs"],
    [13, "(a) (strange) taste"],
    [14, "(the) small size // small // (the) size"],
    [15, "metal"],
    [16, "A"],
    [17, "outside/outdoor activities // outdoors"],
    [18, "underwater // under/beneath water"],
    [19, "(a) weak light"],
    [20, "flashing light"],
    [21, "B // hospital"],
    [22, "C // the middle section"],
    [23, "C // found it difficult to do"],
    [24, "C // remove completely"],
    [25, "B // rewrite"],
    [26, "C // remove completely"],
    [27, "Sight and Sound"],
    [28, "Support Tutor NOT Tutor"],
    [29, "proof reading // proof read"],
    [30, "10 July", "ALTERNATIVE FORMS ACCEPTED（官方键标记）"],
    [31, "7.30pm (to/and) 5.30am NOT 7.30 to 5.30"],
    [32, "housewives // housewifes"],
    [33, "Sunday(s)"],
    [34, "(about) $25,000/twenty-five thousand dollars NOT 25,000"],
    [35, "C // 67 decibels"],
    [36, "C // for ceilings"],
    [37, "W // for walls"],
    [38, "C // for ceilings"],
    [39, "D"],
    [40, "C"],
  ]);
  const answerGroups = [];
  return { groups, answers, answerGroups };
}

/* ------------------------------ 构建器 ------------------------------ */

function buildTest(t) {
  const data = t === "2" ? t2() : t === "3" ? t3() : t4();
  return {
    ok: true,
    parser_version: B3_PARSER_VERSION,
    test: String(t),
    question_groups: data.groups,
    questions: questionsOf(data.groups),
    answer_slots: data.answers,
    answer_groups: data.answerGroups,
    passages: [],
    warnings: data.warnings || [],
  };
}

export function parseBook3ListeningPage(test, opts = {}) {
  const t = String(test);
  if (!B3_TESTS.includes(t)) {
    return { ok: false, error: `book3 listening 支持 T2/T3/T4，收到 ${JSON.stringify(test)}` };
  }
  return buildTest(t);
}

export function buildBook3ListeningTests({ repoRoot } = {}) {
  const root = repoRoot || process.cwd();
  const sources = [];
  for (const rel of [PDF_REL, ...OCR_RELS]) {
    const abs = path.join(root, rel);
    if (fs.existsSync(abs)) sources.push({ file: rel, sha256: sha256Of(abs) });
  }
  return B3_TESTS.map((t) => {
    const parsed = buildTest(t);
    return {
      ok: true,
      parsed,
      sources,
      warnings: parsed.warnings,
      meta: {
        book: 3,
        test: t,
        skill: "listening",
        page_key: `pdf:3:${t}:listening`,
        page_kind: "pdf-extract",
        source: "book3-pdf",
        source_refs: [PDF_REL, ...OCR_RELS],
        raw_file: PDF_REL,
        expected: expectedFor(3, t, "listening"),
        source_skill: "listening",
      },
    };
  });
}
