#!/usr/bin/env node
/**
 * compare-official.mjs — S07 官方答案比较工具（唯一新比较路径）
 *
 * 调用 answer-matcher.mjs 的严格比较器，接收「PDF 官方候选」与「normalized 答案候选」，
 * 输出逐题 match / conflict / unverified / missing，并保留 matcher 的完整状态与来源。
 *
 * 用法：
 *   node ielts-api/tools/compare-official.mjs \
 *     --identity book=10,test=1,skill=reading \
 *     --pdf <pdf-candidates.json> --answers <answers.json> \
 *     [--groups <groups.json>] [--expected 1-40] [--out <file.json>] \
 *     [--pdf-file <path>] [--number-word] [--date-variants]
 *
 * 输入 JSON：
 *   --pdf      {identity?, source?, entries:[{number,value,raw?,page?,sha256?,visual_verified?,ocr?,source_ref?}]}
 *              或直接 [entries]
 *   --answers  {source?, identity?, kind, entries|values, start?, range?, order_verified?, ...}
 *              或 [候选对象, ...]（同 matchAnswers.answerCandidates 形状）
 *   --groups   {groups?} 或 [...]
 *   --pdf-file 可选：给定 PDF 文件时计算 sha256，校验 entries[].sha256 是否与文件一致
 *
 * 输出：{ok, identity, summary:{total,match,conflict,pdf_only,answer_only,missing,unverified,status_counts},
 *        items:[{number, verdict, matcher_status, rule_id, pdf:{value,page,sha256,visual_verified,hash_verified},
 *                answer:{value,source}, display, raw_values, conflicts, decision}]}
 *
 * 禁止：不调用历史 match_one / official_pdf_cmp_v3（历史证据目录只读，不得作为验收裁判）。
 * 比较语义完全由 answer-matcher.mjs 决定（单字母保护、选项唯一映射、显式 allowed_variants）。
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { matchAnswers, compareAnswers } from "../answer-matcher.mjs";

const PDF_SOURCE = "pdf_official";

function parseIdentityArg(s) {
  const out = {};
  for (const kv of String(s || "").split(",")) {
    const [k, v] = kv.split("=");
    if (!k || v === undefined) continue;
    out[k.trim()] = (k.trim() === "book" || k.trim() === "test") ? Number(v) : v.trim();
  }
  return out;
}

function parseArgs(argv) {
  const opts = { flags: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--identity") opts.identity = parseIdentityArg(argv[++i]);
    else if (a === "--pdf") opts.pdf = argv[++i];
    else if (a === "--answers") opts.answers = argv[++i];
    else if (a === "--groups") opts.groups = argv[++i];
    else if (a === "--expected") opts.expected = argv[++i];
    else if (a === "--out") opts.out = argv[++i];
    else if (a === "--pdf-file") opts.pdfFile = argv[++i];
    else if (a === "--number-word") opts.flags.numberWord = true;
    else if (a === "--date-variants") opts.flags.dateVariants = true;
    else if (a === "--no-decisions") opts.flags.noDecisions = true;
    else return { error: "unknown arg: " + a };
  }
  if (!opts.pdf || !opts.answers) return { error: "usage: --identity book=..,test=..,skill=.. --pdf <f> --answers <f> [--groups <f>] [--expected 1-40] [--out <f>]" };
  return opts;
}

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function rangeOf(spec) {
  const out = [];
  for (const part of String(spec).split(",")) {
    const m = /^(\d+)-(\d+)$/.exec(part.trim());
    if (m) { for (let n = Number(m[1]); n <= Number(m[2]); n++) out.push(n); continue; }
    const n = Number(part.trim());
    if (Number.isInteger(n)) out.push(n);
  }
  return out;
}

function sha256File(p) {
  return crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
}

export function compareOfficial({ identity, pdfCandidates, answerCandidates, groups, expected, numberWord, dateVariants, noDecisions, pdfFile }) {
  if (!identity || identity.book == null || identity.test == null || identity.skill == null) {
    return { ok: false, error: "identity requires book/test/skill" };
  }

  // PDF 候选：entry 级 visual_verified/ocr 如实传递；不因名叫 official 就升级
  const pdfDoc = Array.isArray(pdfCandidates) ? { entries: pdfCandidates } : pdfCandidates || {};
  const pdfEntries = Array.isArray(pdfDoc.entries) ? pdfDoc.entries : [];
  const fileHash = pdfFile ? sha256File(pdfFile) : null;

  const pdfInput = {
    source: pdfDoc.source || PDF_SOURCE,
    source_class: "official_pdf",
    identity: pdfDoc.identity || identity,
    kind: "numbered",
    entries: pdfEntries.map((e) => ({
      number: Number(e.number),
      value: e.raw != null ? e.raw : e.value,
      raw: e.raw != null ? e.raw : (e.value == null ? "" : String(e.value)),
      source_ref: e.source_ref || (e.page != null ? `${path.basename(pdfDoc.file || pdfFile || "pdf")}#p${e.page}` : null),
    })),
    visual_verified: pdfEntries.length > 0 && pdfEntries.every((e) => e.visual_verified === true),
    ocr: pdfEntries.some((e) => e.ocr === true) && !pdfEntries.every((e) => e.visual_verified === true),
  };

  const answerInputs = Array.isArray(answerCandidates) ? answerCandidates : [answerCandidates];
  const inputs = [pdfInput, ...answerInputs].filter(Boolean);

  const expectedObj = expected
    ? { numbers: Array.isArray(expected) ? expected : rangeOf(expected), numberWord: !!numberWord, dateVariants: !!dateVariants }
    : { numbers: [...new Set(pdfEntries.map((e) => Number(e.number)).filter(Number.isInteger))].sort((a, b) => a - b), numberWord: !!numberWord, dateVariants: !!dateVariants };

  const result = matchAnswers({
    identity,
    questions: expectedObj.numbers.map((n) => ({ number: n })),
    groups: Array.isArray(groups) ? groups : groups && Array.isArray(groups.groups) ? groups.groups : [],
    answerCandidates: inputs,
    expected: expectedObj,
    decisions: noDecisions ? [] : undefined,
  });
  if (!result.ok) return result;

  const pdfByNum = new Map();
  for (const e of pdfEntries) {
    const n = Number(e.number);
    if (!Number.isInteger(n)) continue;
    pdfByNum.set(n, e);
  }
  const answersSourceNames = new Set(answerInputs.map((a) => (a && a.source) || "answers"));

  const items = [];
  const summary = { total: 0, match: 0, conflict: 0, pdf_only: 0, answer_only: 0, missing: 0, unverified: 0, status_counts: {} };

  for (const q of result.questions) {
    const pdfEntry = pdfByNum.get(q.number) || null;
    const ansRefs = q.candidates.filter((c) => answersSourceNames.has(c.source) && c.source !== pdfInput.source);
    const pdfRef = q.candidates.find((c) => c.source === pdfInput.source) || null;
    const ansVals = ansRefs.filter((c) => !c.empty).map((c) => c.value);

    let verdict;
    if (!pdfEntry && !ansVals.length) verdict = "missing";
    else if (pdfEntry && !ansVals.length) verdict = "pdf_only";
    else if (!pdfEntry && ansVals.length) verdict = "answer_only";
    else {
      // 双方都在：严格比较（选项映射结果优先于原文；显式 allowed_variants 由 matcher 展开）
      const pdfVal = pdfEntry.raw != null ? pdfEntry.raw : pdfEntry.value;
      const hit = ansVals.some((v) => compareAnswers(pdfVal, v, {
        family: q.family,
        numberWord: !!numberWord,
        dateVariants: !!dateVariants,
        allowedVariantsA: (pdfEntry.allowed_variants || []),
        allowedVariantsB: (q.allowed_variants || []),
      }).equal)
        || (pdfRef && pdfRef.mapped_label != null && ansRefs.some((c) => c.mapped_label === pdfRef.mapped_label));
      verdict = hit ? "match" : "conflict";
    }
    if (verdict === "pdf_only" || verdict === "answer_only" || verdict === "missing") summary.unverified++;
    summary[verdict]++;
    summary.total++;

    items.push({
      number: q.number,
      verdict,
      matcher_status: q.status,
      rule_id: q.rule_id,
      family: q.family,
      word_limit: q.word_limit,
      pdf: pdfEntry ? {
        value: pdfEntry.value != null ? pdfEntry.value : pdfEntry.raw,
        page: pdfEntry.page != null ? pdfEntry.page : null,
        sha256: pdfEntry.sha256 || null,
        visual_verified: pdfEntry.visual_verified === true,
        ocr: pdfEntry.ocr === true,
        hash_verified: pdfEntry.sha256 && fileHash ? pdfEntry.sha256 === fileHash : null,
      } : null,
      answer: ansRefs.length ? { values: ansVals, sources: [...new Set(ansRefs.map((c) => c.source))] } : null,
      answer_resolved: q.answer,
      display: q.display,
      raw_values: q.raw_values,
      conflicts: q.conflicts,
      decision: q.decision,
    });
  }

  summary.status_counts = result.coverage.status_counts;
  return {
    ok: true,
    identity: result.identity,
    pdf_file: pdfFile ? { path: pdfFile, sha256: fileHash } : null,
    summary,
    coverage: result.coverage,
    rejections: result.rejections,
    notes: result.notes,
    items,
  };
}

/* ---------------- CLI ---------------- */

const isMain = process.argv[1] && import.meta.url === new URL(`file://${process.argv[1].replace(/\\/g, "/")}`).href;
if (isMain || process.argv[1] && process.argv[1].endsWith("compare-official.mjs")) {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.error) { console.error(opts.error); process.exit(2); }
  try {
    const pdfCandidates = readJson(opts.pdf);
    const answerCandidates = readJson(opts.answers);
    const groups = opts.groups ? readJson(opts.groups) : [];
    const out = compareOfficial({
      identity: opts.identity,
      pdfCandidates, answerCandidates, groups,
      expected: opts.expected,
      numberWord: !!opts.flags.numberWord,
      dateVariants: !!opts.flags.dateVariants,
      noDecisions: !!opts.flags.noDecisions,
      pdfFile: opts.pdfFile,
    });
    const s = JSON.stringify(out, null, 2);
    if (opts.out) fs.writeFileSync(opts.out, s);
    if (!out.ok) { console.error(s); process.exit(1); }
    if (opts.out) {
      const sm = out.summary;
      console.log(`compare-official: ${sm.total} questions — match=${sm.match} conflict=${sm.conflict} pdf_only=${sm.pdf_only} answer_only=${sm.answer_only} missing=${sm.missing} -> ${opts.out}`);
    } else {
      console.log(s);
    }
    process.exit(0);
  } catch (e) {
    console.error(String(e && e.stack || e));
    process.exit(1);
  }
}
