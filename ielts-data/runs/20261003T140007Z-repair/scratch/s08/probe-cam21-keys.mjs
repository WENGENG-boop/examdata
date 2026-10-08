import fs from "node:fs";
import { parseListeningHtml, parseReadingHtml } from "../../../../../ielts-api/cam21.mjs";
const CAM = "../../../../../tmp_audit_ielts/cam21";
const l = parseListeningHtml(fs.readFileSync(`${CAM}/t1-listening.html`, "utf8"), { book: 21, test: 1, skill: "listening" });
console.log("listening answer_key len:", l.answer_key.length);
console.log("keys for 21,22,27,28:", JSON.stringify(l.answer_key.filter(e=>[21,22,27,28].includes(e.number))));
console.log("multi q21 accept:", JSON.stringify(l.questions.find(q=>q.number===21).accept));
console.log("answer_groups:", JSON.stringify(l.answer_groups));
console.log("gap q with empty prompt:", JSON.stringify(l.questions.filter(q=>q.type==='gap' && !String(q.prompt||'').trim()).slice(0,3).map(q=>({n:q.number,group:q.group,type:q.type}))));
const r = parseReadingHtml(fs.readFileSync(`${CAM}/t1-reading.html`, "utf8"), { book: 21, test: 1, skill: "reading" });
for (const g of r.groups) {
  const qs = r.questions.filter(q => q.group === g.id);
  const withOpts = qs.filter(q=>q.options&&q.options.length).length;
  console.log(`R ${g.id} ${g.type} | qs=${qs.length} withOptions=${withOpts} qTypes=${JSON.stringify([...new Set(qs.map(q=>q.type))])} slotKinds=${JSON.stringify([...new Set(qs.map(q=>q.slot_kind))])}`);
}
console.log("reading answer_key sample:", JSON.stringify(r.answer_key.slice(0,3)));
console.log("reading groups instructions sample:", JSON.stringify(r.groups.map(g=>({id:g.id,type:g.type,wl:g.word_limit}))).slice(0,600));
