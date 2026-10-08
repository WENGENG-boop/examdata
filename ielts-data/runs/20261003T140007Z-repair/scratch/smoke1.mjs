import fs from "node:fs";
import {
  parseHtml, collectAnswerSlots, collectQuestionGroups, collectPassages,
  collectAssets, extractAudio, extractExplanations, nodeText, normalizeWs,
} from "../../../../ielts-api/html-questions.mjs";

const file = process.argv[2];
const html = fs.readFileSync(file, "utf8");
const root = parseHtml(html);

const ans = collectAnswerSlots(root, { maxNumber: 45 });
console.log("== answers ==", ans.entries.length, "containers:", JSON.stringify(ans.containers));
for (const e of ans.entries.slice(0, 6)) console.log("  ", e.number, JSON.stringify(e.raw), e.form);
const empty = ans.entries.filter((e) => e.raw === "");
console.log("  empty entries:", empty.map((e) => e.number).join(","));

const stopAtHeadings = !process.argv.includes("--no-break");
const groups = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings });
console.log("== groups ==", groups.groups.length);
for (const g of groups.groups) {
  console.log(`  G${g.index} [${g.range}] slots=${g.slots.length} pools=${g.pools.length} wl=${g.word_limit}`);
  console.log(`     instr: ${g.instruction.slice(0, 90)}`);
  console.log(`     shared: ${g.shared_prompt.slice(0, 70).replace(/\n/g, " | ")}`);
  const nums = g.slots.map((s) => s.number + ":" + s.kind).join(" ");
  console.log(`     slots: ${nums.slice(0, 160)}`);
}

const pass = collectPassages(root, { groups: groups.groups, expectedPassages: 3 });
console.log("== passages ==", pass.passages.length, JSON.stringify(pass.notes));
for (const p of pass.passages) {
  console.log(`  P${p.index} "${(p.title || "").slice(0, 50)}" paras=${p.paragraphs.length} tables=${p.tables.length} range=${JSON.stringify(p.range)} groups=${JSON.stringify(p.question_groups)}`);
}

const assets = collectAssets(root, { baseUrl: "https://practicepteonline.com" });
console.log("== assets ==", assets.length);
for (const a of assets.slice(0, 8)) console.log("  ", a.kind, (a.url || "").slice(0, 80), a.alt ? `alt="${a.alt}"` : "");

console.log("== audio ==", extractAudio(root, { baseUrl: "https://practicepteonline.com" }).join(" | "));
const expl = extractExplanations(root);
console.log("== explanations ==", Object.keys(expl).length);
console.log("== notes ==", JSON.stringify(ans.notes), JSON.stringify(groups.notes));
