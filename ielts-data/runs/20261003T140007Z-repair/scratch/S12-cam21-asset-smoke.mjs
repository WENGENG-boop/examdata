import { readFileSync } from "node:fs";
import { parseListeningHtml, parseReadingHtml } from "./cam21.mjs";
import { buildFromCam21Page } from "./question-index.mjs";

const DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21";
for (const [t, skill] of [[1, "listening"], [2, "listening"], [3, "listening"], [4, "listening"]]) {
  const html = readFileSync(`${DIR}/t${t}-${skill}.html`, "utf8");
  const parsed = parseListeningHtml(html, {});
  const built = buildFromCam21Page(parsed, { book: 21, test: t, skill });
  console.log(`\n=== b21 t${t} ${skill} ===`);
  for (const g of built.groups) {
    const assets = (g.assets || []).map((a) => `${a.kind}${a.title ? `(${a.title.slice(0, 30)})` : ""}${a.rows ? ` rows=${a.rows.length}` : ""}${a.steps ? ` steps=${a.steps.length}` : ""}${a.source_ref ? ` ref=${a.source_ref}` : ""}`);
    const wl = g.constraints ? `wl=${g.constraints.max_words}/${g.constraints.allows_number}` : "wl=null";
    const opts = g.options && g.options.length ? `opts=${g.options.map((o) => o.label).join("")}` : "opts=[]";
    console.log(`${g.id} ${g.type} [${g.range}] ${wl} ${opts} assets=[${assets.join("; ")}]`);
  }
  const byStatus = {};
  for (const q of built.questions) byStatus[q.content_status] = (byStatus[q.content_status] || 0) + 1;
  console.log("status:", JSON.stringify(byStatus));
  const missing = built.questions.filter((q) => q.content_status !== "complete").map((q) => `${q.number}:${q.content_status}`);
  if (missing.length) console.log("non-complete:", missing.join(" "));
}
