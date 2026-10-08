import { readFileSync } from "node:fs";
const j = JSON.parse(readFileSync(process.argv[2], "utf8"));
const html = j[0].content.rendered;
const needle = process.argv[3] || "Questions 16";
const i = html.indexOf(needle);
console.log("idx of", JSON.stringify(needle), "=", i);
console.log(html.slice(Math.max(0, i - 100), i + 2500).replace(/<br\s*\/?>/gi, "<br/>\n"));
