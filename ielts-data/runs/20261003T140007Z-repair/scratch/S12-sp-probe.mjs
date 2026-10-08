// S12 shared_prompt 修复探针：raw-41 (b3t3r), raw-127 (b9t1r)
import fs from "node:fs";
import { parsePtePage } from "./pte.mjs";

const cases = [
  ["raw-41", { book: 3, test: 3, skill: "academic_reading" }],
  ["raw-127", { book: 9, test: 1, skill: "academic_reading" }],
];
for (const [name, identity] of cases) {
  const raw = fs.readFileSync(`../tmp_audit_ielts/completeness_20261003/${name}.txt`, "utf8");
  const r = parsePtePage(raw, identity, null);
  console.log(`\n=== ${name} ${identity.book}/${identity.test} ok=${r.ok}`);
  const gs = r.question_groups || [];
  for (const g of gs) {
    const sp = g.shared_prompt || "";
    console.log(`  G${g.index} [${g.range[0]}-${g.range[1]}] slots=${g.slots.length} opts=${g.options.length} sp_len=${sp.length} sp_head=${JSON.stringify(sp.slice(0, 70))}`);
  }
  console.log(`  passages=${r.passages?.length} notes=${JSON.stringify((r.passages?.notes || []).map((n) => n.kind))}`);
  const total = r.questions?.length ?? 0;
  console.log(`  questions=${total}`);
}
