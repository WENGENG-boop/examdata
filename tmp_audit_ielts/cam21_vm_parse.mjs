// 独立审查：用 Node 原生 vm 求值剑21 页面内嵌 JS 字面量（不使用被测代码的 jsToJson）
import fs from "node:fs";
import vm from "node:vm";

const DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21/";

function biggestScript(html) {
  const all = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)].map((m) => m[1]);
  all.sort((a, b) => b.length - a.length);
  return all[0] || "";
}

function extractLiteral(src, name, open = "{") {
  const close = open === "{" ? "}" : "]";
  const re = new RegExp("const\\s+" + name + "\\s*=\\s*\\" + open);
  const m = re.exec(src);
  if (!m) return null;
  const start = m.index + m[0].length - 1;
  let depth = 0, i = start, inStr = null, esc = false;
  for (; i < src.length; i++) {
    const ch = src[i];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === inStr) inStr = null;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === "`") { inStr = ch; continue; }
    if (ch === open) depth++;
    else if (ch === close) { depth--; if (depth === 0) { i++; break; } }
  }
  return src.slice(start, i);
}

function evalLit(lit) {
  if (!lit) return null;
  return vm.runInNewContext("(" + lit + ")", {}, { timeout: 10000 });
}

const report = { reading: {}, listening: {}, totals: {} };
let rAns = 0, lAns = 0, lines = 0, audio = 0;

for (const t of [1, 2, 3, 4]) {
  const rh = fs.readFileSync(DIR + "t" + t + "-reading.html", "utf8");
  const rs = biggestScript(rh);
  const rAnsObj = evalLit(extractLiteral(rs, "ANSWERS")) || {};
  const rQ = evalLit(extractLiteral(rs, "QUESTIONS", "[")) || [];
  const rP = evalLit(extractLiteral(rs, "PASSAGES")) || {};
  const rAnsKeys = Object.keys(rAnsObj);
  report.reading[t] = {
    passages: Object.keys(rP).length,
    questions: rQ.length,
    answers: rAnsKeys.length,
    answerNumbers: rAnsKeys.map(Number).sort((a, b) => a - b),
    qTypes: [...new Set(rQ.map((q) => q.type))],
    firstAnswers: Object.fromEntries(rAnsKeys.slice(0, 3).map((k) => [k, rAnsObj[k]])),
  };
  rAns += rAnsKeys.length;

  const lh = fs.readFileSync(DIR + "t" + t + "-listening.html", "utf8");
  const ls = biggestScript(lh);
  const cAns = evalLit(extractLiteral(ls, "correctAnswers")) || {};
  const mc = evalLit(extractLiteral(ls, "multiCorrect")) || {};
  const tr = evalLit(extractLiteral(ls, "TRANSCRIPTS")) || {};
  const at = evalLit(extractLiteral(ls, "audioTracks")) || {};
  const parts = evalLit(extractLiteral(ls, "PARTS")) || {};
  const union = new Set([...Object.keys(cAns), ...Object.keys(mc)]);
  const tLines = Object.values(tr).reduce((n, a) => n + (a || []).length, 0);
  const sampleLine = (tr["1"] || [])[0] || null;
  const linesWithTime = Object.values(tr).flat().filter((l) => l && l.t !== undefined && l.t !== null).length;
  const linesWithSp = Object.values(tr).flat().filter((l) => l && l.sp).length;
  report.listening[t] = {
    parts: Object.keys(parts).length,
    correctAnswers: Object.keys(cAns).length,
    multiCorrect: Object.keys(mc).length,
    answerUnion: union.size,
    audioTracks: Object.keys(at).length,
    transcriptSections: Object.keys(tr).length,
    transcriptLines: tLines,
    transcriptLinesWithTime: linesWithTime,
    transcriptLinesWithSpeaker: linesWithSp,
    sampleLine,
    firstKeys: [...union].map(Number).sort((a, b) => a - b).slice(0, 8),
  };
  lAns += union.size;
  lines += tLines;
  audio += Object.keys(at).length;
}

report.totals = {
  readingAnswers: rAns,
  listeningAnswers: lAns,
  transcriptLines: lines,
  audioFiles: audio,
};
fs.writeFileSync(DIR + "vm_parse_result.json", JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
