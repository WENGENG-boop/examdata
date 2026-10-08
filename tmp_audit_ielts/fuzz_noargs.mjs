// 无参调用所有带参函数：是否抛异常？
import * as api from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const calls = [
  ["aggregate()", () => api.aggregate()],
  ["pteReading()", () => api.pteReading()],
  ["pteListening()", () => api.pteListening()],
  ["pteBook()", () => api.pteBook()],
  ["pteAudio()", () => api.pteAudio()],
  ["reading()", () => api.reading()],
  ["listeningQA()", () => api.listeningQA()],
  ["listeningScript()", () => api.listeningScript()],
  ["listeningAudio()", () => api.listeningAudio()],
  ["listeningSegments()", () => api.listeningSegments()],
  ["itoScript()", () => api.itoScript()],
  ["itoListening()", () => api.itoListening()],
  ["cam21Reading()", () => api.cam21Reading()],
  ["cam21Listening()", () => api.cam21Listening()],
  ["cam21Audio()", () => api.cam21Audio()],
  ["pdfLfs()", () => api.pdfLfs()],
  ["explainPdf()", () => api.explainPdf()],
  ["pdf()", () => api.pdf()],
  ["miniList()", () => api.miniList()],
  ["miniSolution()", () => api.miniSolution()],
  ["lfsProbe()", () => api.lfsProbe()],
  ["book20Set()", () => api.book20Set()],
  ["cam21Coverage()", () => api.cam21Coverage()],
  ["itoCoverage()", () => api.itoCoverage()],
  ["lfsCoverage()", () => api.lfsCoverage()],
];
const timeout = (p, ms) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("HANG")), ms))]);
for (const [label, fn] of calls) {
  try {
    const r = await timeout(fn(), 90000);
    const hasOk = r && typeof r === "object" && ("ok" in r);
    console.log(`PASS ${label} ok=${hasOk ? String(r.ok) : "MISSING"} keys=${r && typeof r==="object" ? Object.keys(r).slice(0,5).join(",") : typeof r}`);
  } catch (e) {
    console.log(`FAIL ${label} -> ${String(e.message||e).slice(0,110)}`);
  }
}
