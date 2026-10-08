import fs from "node:fs";
import { parseHtml, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";

const file = process.argv[2];
const gi = Number(process.argv[3] ?? 6);
const root = parseHtml(fs.readFileSync(file, "utf8"));
const { groups } = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: false });
const g = groups[gi];
console.log(JSON.stringify({ index: g.index, range: g.range, instruction: g.instruction, shared: g.shared_prompt, word_limit: g.word_limit, pools: g.pools, slots: g.slots, block_span: g.block_span }, null, 2));
