import { listeningSegments } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
const s = await listeningSegments(8, 4, 2);
console.log("ok=", s.ok, "segments=", (s.segments||[]).length);
for (const g of (s.segments||[]).slice(0, 5)) {
  console.log(JSON.stringify(g));
}
