// tmp_live_check.mjs — live check of aggregator-side values for adjudication (diagnostic only)
import { pteListening } from "file:///C:/Users/weo/Desktop/api/ielts-api/ielts-api.mjs";

const targets = [
  [5, 1, [4]],
  [5, 2, [9]],
  [5, 4, [19]],
  [6, 4, [6]],
  [7, 2, [2, 12, 38]],
  [17, 4, [38]],
];

for (const [b, t, qs] of targets) {
  let r;
  try {
    r = await pteListening(b, t);
  } catch (e) {
    console.log(`${b}-${t}: THREW ${e.message}`);
    continue;
  }
  if (!r.ok) { console.log(`${b}-${t}: NOT OK ${r.error}`); continue; }
  const key = r.answer_key || [];
  const shape = key[0] ? Object.keys(key[0]).join(",") : "(empty)";
  const out = [];
  for (const q of qs) {
    const item = key.find((x) => Number(x.question ?? x.q ?? x.number ?? x.n) === q);
    out.push(`Q${q}=${JSON.stringify(item)}`);
  }
  console.log(`${b}-${t} source=${r.source} count=${key.length} shape=[${shape}]`);
  console.log("  " + out.join("  "));
}
