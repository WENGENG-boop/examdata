// S07 smoke: answer-matcher 关键路径（非正式测试，先跑通再写 tests/ielts-answer-matcher.test.mjs）
import { matchAnswers, compareAnswers, compareGroupAnswer } from "../../../../../ielts-api/answer-matcher.mjs";

const base = { book: 5, test: 1, skill: "listening" };

// 1. 显式编号 + 决策修正（5-1 Q4 palisades -> Pallisades）
{
  const r = matchAnswers({
    identity: base,
    expected: { numbers: [1, 2, 3, 4] },
    questions: [{ number: 4 }],
    groups: [],
    answerCandidates: [
      { source: "practicepteonline.com", identity: base, kind: "numbered", entries: [{ number: 4, value: "palisades" }] },
      { source: "official-pdf", source_class: "official_pdf", visual_verified: true, identity: { ...base, edition: "official" }, kind: "numbered", entries: [{ number: 4, value: "Pallisades", source_ref: "book5 p153" }] },
    ],
  });
  const q4 = r.questions.find((q) => q.number === 4);
  console.log("1) decision correction:", q4.status, JSON.stringify(q4.answer), q4.rule_id);
}

// 2. 顺序数组未验证 -> order_unverified，且不补位
{
  const r = matchAnswers({
    identity: base,
    expected: { numbers: [1, 2, 3] },
    answerCandidates: [
      { source: "x", identity: base, kind: "answer_key_array", values: ["A", "", "C"], start: 1 },
    ],
  });
  console.log("2) order unverified:", r.questions.map((q) => `${q.number}:${q.status}`).join(" "));
}

// 3. 顺序数组已验证 + 空位保留（空 LI 不移位）
{
  const r = matchAnswers({
    identity: base,
    expected: { numbers: [1, 2, 3] },
    answerCandidates: [
      { source: "x", identity: base, kind: "answer_key_array", values: ["A", "", "C"], start: 1, order_verified: true },
    ],
  });
  console.log("3) empty LI:", r.questions.map((q) => `${q.number}:${q.status}:${q.answer ?? "-"}`).join(" "));
}

// 4. 字母 vs 文本：E 与 read research methods 直接比较 false；经选项表映射 true
{
  const direct = compareAnswers("E", "read research methods");
  const r = matchAnswers({
    identity: { book: 4, test: 1, skill: "listening" },
    expected: { numbers: [23] },
    questions: [{ number: 23 }],
    groups: [{ group_id: "g0", numbers: [23], options: [{ label: "E", text: "read research methods" }, { label: "A", text: "uncooperative landlord" }] }],
    answerCandidates: [
      { source: "practicepteonline.com", identity: { book: 4, test: 1, skill: "listening" }, kind: "numbered", entries: [{ number: 23, value: "read research methods" }] },
      { source: "official", source_class: "official_pdf", visual_verified: true, identity: { book: 4, test: 1, skill: "listening", edition: "official" }, kind: "numbered", entries: [{ number: 23, value: "E" }] },
    ],
  });
  const q = r.questions[0];
  console.log("4) direct:", direct.equal, "| mapped:", q.status, JSON.stringify(q.display));
}

// 5. 冲突：无裁决的官方 vs 来源
{
  const r = matchAnswers({
    identity: { book: 9, test: 1, skill: "listening" },
    expected: { numbers: [1] },
    answerCandidates: [
      { source: "practicepteonline.com", identity: { book: 9, test: 1, skill: "listening" }, kind: "numbered", entries: [{ number: 1, value: "cat" }] },
      { source: "official", source_class: "official_pdf", visual_verified: true, identity: { book: 9, test: 1, skill: "listening", edition: "official" }, kind: "numbered", entries: [{ number: 1, value: "dog" }] },
    ],
  });
  console.log("5) conflict:", r.questions[0].status, JSON.stringify(r.questions[0].conflicts));
}

// 6. decision_stale：上游值变化
{
  const r = matchAnswers({
    identity: { book: 7, test: 2, skill: "listening" },
    expected: { numbers: [2] },
    answerCandidates: [
      { source: "practicepteonline.com", identity: { book: 7, test: 2, skill: "listening" }, kind: "numbered", entries: [{ number: 2, value: "730453x" }] },
    ],
  });
  console.log("6) stale:", r.questions[0].status, JSON.stringify(r.notes));
}

// 7. 组答案：5-2 Q18-20 IN ANY ORDER
{
  const r = matchAnswers({
    identity: { book: 5, test: 2, skill: "listening" },
    expected: { numbers: [18, 19, 20] },
    groups: [{ group_id: "g0", numbers: [18, 19, 20], instruction: "Choose THREE letters. IN ANY ORDER" }],
    answerCandidates: [
      { source: "practicepteonline.com", identity: { book: 5, test: 2, skill: "listening" }, kind: "group", group_id: "g-5-2-18-20", input_numbers: [18, 19, 20], accepted_sets: [["C", "E", "F"]], required_count: 3, ordered: false, allow_reuse: false, scoring: "exact_set" },
    ],
  });
  console.log("7) group:", r.questions.map((q) => `${q.number}:${q.status}`).join(" "), "| groups:", JSON.stringify(r.groups[0]));
  const cmp = compareGroupAnswer(["F", "C", "E"], [["C", "E", "F"]], { required_count: 3, ordered: false, allow_reuse: false });
  const dup = compareGroupAnswer(["C", "C", "E"], [["C", "E", "F"]], { required_count: 3, ordered: false, allow_reuse: false });
  const short = compareGroupAnswer(["C", "E"], [["C", "E", "F"]], { required_count: 3, ordered: false, allow_reuse: false });
  console.log("   set:", cmp.pass, "dup:", dup.pass, dup.reason, "short:", short.pass, short.reason);
}

// 8. 无候选不伪造
{
  const r = matchAnswers({ identity: base, expected: { numbers: [40] }, answerCandidates: [] });
  console.log("8) missing:", r.questions[0].status, r.questions[0].answer);
}
