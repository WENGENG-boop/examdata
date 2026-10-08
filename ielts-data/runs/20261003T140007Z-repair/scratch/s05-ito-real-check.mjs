// S05 适配器：用真实 raw 验证 extractItoAnswerKey
import fs from "node:fs";
const rawPath = "C:/Users/weo/Desktop/api/ielts-data/raw/ieltstrainingonline.com/a57bd226ecc49000fdb5af9d082ad3ab3f928506d2735c52602e2bce45217294.body";
const mod = await import("file:///C:/Users/weo/Desktop/api/ielts-api/ito.mjs");
const { extractItoAnswerKey, toText } = mod.__internals;

const b = JSON.parse(fs.readFileSync(rawPath, "utf8"));
const p = Array.isArray(b) ? b[0] : b;
const text = toText(p.content.rendered);
const ai = text.search(/\bAnswers?\s+(?:Cam|Cambridge|IELTS)/i);
console.log("answer heading index:", ai, "| heading line:", JSON.stringify(text.slice(ai, ai + 60).split("\n")[0]));
const answerText = ai >= 0 ? text.slice(ai) : "";
const key = extractItoAnswerKey(answerText);
console.log("count:", key.length);
for (const k of key) console.log(k.number, "|", k.answer, k.paired ? ("| paired=" + k.paired) : "");
