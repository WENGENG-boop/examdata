import { readFileSync } from "node:fs";
for (const f of process.argv.slice(2)) {
  const j = JSON.parse(readFileSync(f, "utf8"));
  console.log("=== " + f + " G" + j.index + " range=" + JSON.stringify(j.range) + " span=" + JSON.stringify(j.span) + " n_slots=" + j.slots.length);
  for (const s of j.slots) {
    const p = (s.prompt || "").slice(0, 90).replace(/\n/g, "\n");
    console.log(`  Q${s.n} [${s.kind}] opts=${s.opts} prompt="${p}"`);
  }
}
