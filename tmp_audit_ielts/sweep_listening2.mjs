// 听力全量复扫：镜像 aggregate() 的 listening_qa 链（cam21 → pte → tarof → iprog）
import * as api from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";

const books = Array.from({ length: 21 }, (_, i) => i + 1);
const jobs = [];
for (const b of books) for (let t = 1; t <= 4; t++) jobs.push([b, t]);

const results = [];
async function one(b, t) {
  let source = null, count = 0, via = null;
  try {
    if (b === 21) {
      const r = await api.cam21Listening(t);
      if (r.ok) { source = r.source; count = r.counts.answers; via = "cam21"; }
    }
    if (!via) {
      const r = await api.pteListening(b, t);
      if (r.ok) { source = r.source; count = r.answer_count ?? (r.answer_key || []).length; via = "pte"; }
    }
    if (!via) {
      const r = await api.listeningQA(b, t);
      if (r.ok) { source = r.source; count = (r.answer_key || []).length || (r.questions || []).length; via = "tarof"; }
    }
    if (!via && b === 3) {
      const r = await api.iprogListening(b, t);
      if (r.ok) { source = r.source; count = r.answer_count; via = "iprog"; }
    }
    if (!via) via = "none";
  } catch (e) { via = "ERR:" + e.message; }
  results.push({ book: b, test: t, via, count, source });
  console.error(`${b}-${t} ${via} ${count}`);
}

const CONC = 6;
let i = 0;
async function worker() {
  while (i < jobs.length) {
    const [b, t] = jobs[i++];
    await one(b, t);
  }
}
await Promise.all(Array.from({ length: CONC }, worker));

const ok = results.filter((r) => r.via !== "none" && !r.via.startsWith("ERR"));
const total = ok.reduce((s, r) => s + r.count, 0);
const byVia = {};
for (const r of results) byVia[r.via] = (byVia[r.via] || 0) + 1;
const zero = results.filter((r) => r.count === 0 && !r.via.startsWith("ERR"));
console.log(JSON.stringify({
  sets_ok: `${ok.length}/84`,
  total_answers: total,
  by_via: byVia,
  zero_answer_sets: zero.map((r) => `${r.book}-${r.test}:${r.via}`),
  missing: results.filter((r) => r.via === "none" || r.via.startsWith("ERR")).map((r) => `${r.book}-${r.test}:${r.via}`),
}, null, 2));
