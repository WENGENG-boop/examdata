#!/usr/bin/env node
/**
 * verify-decisions.mjs — S15 裁决守卫回归（45 条裁决 + 2 条组级核验）
 *
 * 用法：
 *   node tools/verify-decisions.mjs [--data-dir <dir>] [--json]
 *
 * 检查四组：
 *   A 结构：45 条裁决（adj-01..45 唯一、none=38 / correct=7、全部 resolved、
 *     7 条窄修正 from/to/basis/pdf.sha256/verifier 齐全）、ADJUDICATIONS_META 汇总一致、
 *     2 条 GROUP_VERIFICATIONS（gv-01 classification / gv-02 word_limit）。
 *   B 合成守卫：对每条窄修正构造 pte 结果形状 —— from 匹配 → 应用到 to（记录 answer_corrections）；
 *     篡改值 → adjudication_stale 且保留旧值（不强套）。
 *   C 函数冒烟：decisionById / decisionsFor / decisionForQuestion / correctionsFor /
 *     groupDecisionsFor / groupVerificationById。
 *   D 真实索引：current 指针 → questions.json；7 条修正题存在且 answer_status=attached、
 *     源原值仍等于 from（原值保留）；对真实值跑 applyAdjudications 应 7 applied / 0 stale；
 *     official_verifications 含 gv-01/gv-02；cross_source_conflicts 含两决策；
 *     b9 G2 type=yes_no_not_given、G1 constraints.max_words=3/allows_number；
 *     verification_issues 为空。
 *
 * 退出码：0 = 全部通过；1 = 存在失败（逐条打印 FAIL）。
 */
import fs from "node:fs";
import path from "node:path";

import { resolveDataDir, readJson } from "../data-store.mjs";
import {
  ADJUDICATIONS_META,
  DECISIONS,
  GROUP_VERIFICATIONS,
  GROUP_VERIFICATIONS_META,
  groupVerificationById,
  decisionsFor,
  decisionForQuestion,
  decisionById,
  groupDecisionsFor,
  correctionsFor,
  applyAdjudications,
} from "../adjudications.mjs";

const opts = { dataDir: null, json: false };
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a === "--data-dir") opts.dataDir = process.argv[++i];
  else if (a === "--json") opts.json = true;
  else {
    console.error(`unknown argument: ${a}`);
    process.exit(2);
  }
}

let passed = 0;
const failures = [];
function check(id, cond, detail = "") {
  if (cond) {
    passed++;
    console.log(`PASS ${id}${detail ? " " + detail : ""}`);
  } else {
    failures.push({ id, detail });
    console.log(`FAIL ${id}${detail ? " " + detail : ""}`);
  }
}

// ---------------------------------------------------------------- A 结构

check("A01-count", DECISIONS.length === 45, `decisions=${DECISIONS.length}`);

const ids = DECISIONS.map((d) => d.id);
const expectedIds = Array.from({ length: 45 }, (_, i) => `adj-${String(i + 1).padStart(2, "0")}`);
check(
  "A02-ids",
  new Set(ids).size === 45 && ids.every((v) => /^adj-\d\d$/.test(v)) && expectedIds.every((v) => ids.includes(v)),
  `unique=${new Set(ids).size}`
);

const nCorrect = DECISIONS.filter((d) => d.action === "correct").length;
const nNone = DECISIONS.filter((d) => d.action === "none").length;
check("A03-actions", nCorrect === 7 && nNone === 38, `correct=${nCorrect} none=${nNone}`);
check("A04-resolved", DECISIONS.every((d) => d.status === "resolved"), "");
check("A05-category", DECISIONS.every((d) => typeof d.category === "string" && d.category.length > 0), "");

const corrections = DECISIONS.filter((d) => d.action === "correct");
const badCorrections = corrections.filter(
  (d) =>
    typeof d.from !== "string" ||
    typeof d.to !== "string" ||
    d.from === d.to ||
    !d.basis ||
    !d.pdf ||
    !/^[a-f0-9]{64}$/.test(d.pdf.sha256 || "") ||
    !d.verifier ||
    !d.verifier.method
);
check("A06-correction-fields", badCorrections.length === 0, badCorrections.map((d) => d.id).join(",") || "all-complete");

const metaSum = ADJUDICATIONS_META.summary || {};
check(
  "A07-meta",
  metaSum.total_items === 45 && metaSum.corrections_applied === 7 && metaSum.no_action === 38 && metaSum.resolved === 45 && metaSum.unresolved === 0,
  JSON.stringify(metaSum)
);

check("A08-gv-count", GROUP_VERIFICATIONS.length === 2, `gv=${GROUP_VERIFICATIONS.length}`);
const gvKinds = GROUP_VERIFICATIONS.map((v) => v.kind).sort();
check("A09-gv-kinds", gvKinds.join(",") === "classification_conflict,word_limit_conflict", gvKinds.join(","));
check(
  "A10-gv-fields",
  GROUP_VERIFICATIONS.every((v) => v.id && v.identity && v.from && v.to && v.evidence && v.verifier && v.verifier.method),
  ""
);
check("A11-gv-meta", GROUP_VERIFICATIONS_META.summary && GROUP_VERIFICATIONS_META.summary.total === 2, JSON.stringify(GROUP_VERIFICATIONS_META.summary));

// ---------------------------------------------------------------- B 合成守卫

for (const d of corrections) {
  const { book, test, question } = d.identity;
  const n = question;
  const mkR = (value) => ({
    ok: true,
    answer_key: Array.from({ length: n }, (_, i) => (i === n - 1 ? value : null)),
    questions: [{ number: n, answer: value }],
  });

  const applied = applyAdjudications(book, Number(test), mkR(d.from));
  const okApplied =
    applied.answer_key[n - 1] === d.to &&
    Array.isArray(applied.answer_corrections) &&
    applied.answer_corrections.some((c) => c.decision_id === d.id && c.from === d.from && c.to === d.to) &&
    applied.questions[0].answer === d.to &&
    applied.questions[0].answer_decision_id === d.id;
  check(`B-${d.id}-apply`, okApplied, `${d.from} -> ${d.to}`);

  const tampered = "__tampered__";
  const stale = applyAdjudications(book, Number(test), mkR(tampered));
  const okStale =
    stale.answer_key[n - 1] === tampered &&
    Array.isArray(stale.adjudication_stale) &&
    stale.adjudication_stale.some(
      (s) => s.decision_id === d.id && s.expected_from === d.from && s.actual === tampered
    ) &&
    !stale.answer_corrections;
  check(`B-${d.id}-stale`, okStale, "tampered keeps old value, records adjudication_stale");
}

// ---------------------------------------------------------------- C 函数冒烟

const d10 = decisionById("adj-10");
check("C01-decisionById", d10 && d10.identity.book === 5 && d10.identity.question === 4, d10 ? d10.id : "null");

const dFor = decisionsFor(5, 1);
check("C02-decisionsFor", Array.isArray(dFor) && dFor.length >= 1 && dFor.every((d) => d.identity.book === 5 && d.identity.test === 1), `len=${dFor.length}`);

const dQ = decisionForQuestion(5, 1, 4);
check("C03-decisionForQuestion", dQ && dQ.id === "adj-10", dQ ? dQ.id : "null");

const corr = correctionsFor(5, 1);
check(
  "C04-correctionsFor",
  corr instanceof Map && corr.size >= 1 && corr.get(4) && corr.get(4).to === "Pallisades" && corr.get(4).decision_id === "adj-10",
  `size=${corr.size}`
);

const gd = groupDecisionsFor(5, 1);
check("C05-groupDecisionsFor", gd instanceof Map, `isMap=${gd instanceof Map}`);

const gv1 = groupVerificationById("gv-01");
check("C06-groupVerificationById", gv1 && gv1.kind === "classification_conflict" && gv1.to.type === "yes_no_not_given", gv1 ? gv1.id : "null");

// ---------------------------------------------------------------- D 真实索引

const dataDir = resolveDataDir(opts.dataDir);
const currentPath = path.join(dataDir, "indexes", "current");
let current = null;
try {
  current = readJson(currentPath, { missingOk: false });
} catch (e) {
  check("D01-current", false, `cannot read ${currentPath}: ${e.message}`);
}
let index = null;
if (current && current.dataset_revision) {
  const idxPath = path.join(dataDir, "indexes", current.dataset_revision, "questions.json");
  try {
    index = readJson(idxPath, { missingOk: false });
    check("D01-current", true, `rev=${current.dataset_revision}`);
  } catch (e) {
    check("D01-current", false, `cannot read ${idxPath}: ${e.message}`);
  }
} else if (current) {
  check("D01-current", false, "current.json missing dataset_revision");
}

if (index) {
  const questions = index.questions || [];
  const answers = index.answers || {};
  const findQ = (b, t, n) =>
    questions.find((q) => q.book === b && q.test === String(t) && q.skill === "listening" && q.number === n);

  const realR = { ok: true, answer_key: [], questions: [] };
  let allPresent = true;
  const detail = [];
  for (const d of corrections) {
    const { book, test, question } = d.identity;
    const q = findQ(book, test, question);
    if (!q) {
      allPresent = false;
      detail.push(`${d.id}:question-missing`);
      continue;
    }
    const a = answers[q.id];
    if (!a || a.status !== "attached") {
      allPresent = false;
      detail.push(`${d.id}:not-attached`);
      continue;
    }
    if (a.raw !== d.from) {
      allPresent = false;
      detail.push(`${d.id}:raw=${JSON.stringify(a.raw)}!=from`);
      continue;
    }
    realR.answer_key[question - 1] = a.raw;
    realR.questions.push({ number: question, answer: a.raw });
  }
  check("D02-questions", allPresent, detail.join(" ") || "7 attached, raw==from");

  if (allPresent) {
    // 按 book/test 分组：同一册同一套的多条修正在同一个 r 形状上一起应用，
    // 避免未填的题号位置被误判为 adjudication_stale。
    const groupsByBT = new Map();
    for (const d of corrections) {
      const key = `${d.identity.book}|${d.identity.test}`;
      if (!groupsByBT.has(key)) groupsByBT.set(key, []);
      groupsByBT.get(key).push(d);
    }
    let appliedTotal = 0;
    let staleTotal = 0;
    const perGroup = [];
    for (const [key, list] of groupsByBT) {
      const [book, test] = key.split("|");
      const maxQ = Math.max(...list.map((d) => d.identity.question));
      const answer_key = Array.from({ length: maxQ }, () => null);
      const questions = [];
      for (const d of list) {
        answer_key[d.identity.question - 1] = d.from;
        questions.push({ number: d.identity.question, answer: d.from });
      }
      const out = applyAdjudications(Number(book), Number(test), { ok: true, answer_key, questions });
      const applied = out.answer_corrections ? out.answer_corrections.length : 0;
      const stale = out.adjudication_stale ? out.adjudication_stale.length : 0;
      appliedTotal += applied;
      staleTotal += stale;
      perGroup.push(`${key}:${applied}/${list.length}${stale ? ` stale=${stale}` : ""}`);
    }
    check("D03-apply-real", appliedTotal === 7 && staleTotal === 0, perGroup.join(" "));
  }

  const ov = index.official_verifications || [];
  const ovIds = new Set(ov.map((o) => o.decision_id));
  const ovOk =
    ovIds.has("gv-01") &&
    ovIds.has("gv-02") &&
    ov.some((o) => o.decision_id === "gv-01" && o.to && o.to.type === "yes_no_not_given") &&
    ov.some((o) => o.decision_id === "gv-02" && o.to && /THREE WORDS/.test(o.to.word_limit || ""));
  check("D04-official-verifications", ovOk, `len=${ov.length}`);

  const csc = index.cross_source_conflicts || [];
  const cscIds = new Set(csc.map((c) => c.decision_id));
  check("D05-cross-source-conflicts", cscIds.has("gv-01") && cscIds.has("gv-02"), `len=${csc.length}`);

  const groups = index.groups || [];
  const g2 = groups.find((g) => g.id === "cambridge:9:academic:reading:1:P2:G2");
  const g1 = groups.find((g) => g.id === "cambridge:9:academic:reading:1:P2:G1");
  check("D06-gv01-group-type", g2 && g2.type === "yes_no_not_given", g2 ? `type=${g2.type}` : "group-missing");
  check(
    "D07-gv02-word-limit",
    g1 && g1.constraints && g1.constraints.max_words === 3 && g1.constraints.allows_number === true,
    g1 ? JSON.stringify(g1.constraints) : "group-missing"
  );

  check("D08-verification-issues", Array.isArray(index.verification_issues) && index.verification_issues.length === 0, `len=${(index.verification_issues || []).length}`);
}

// ---------------------------------------------------------------- 汇总

const ok = failures.length === 0;
console.log(`verify-decisions: ${passed} passed, ${failures.length} failed (data-dir=${dataDir})`);
if (opts.json) {
  console.log("RESULT " + JSON.stringify({ ok, passed, failed: failures.length, failures, data_dir: dataDir }));
}
process.exit(ok ? 0 : 1);
