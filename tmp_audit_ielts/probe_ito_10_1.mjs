import { itoScript } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
const s = await itoScript(10, 1);
console.log("slug=", s.slug, "sections=", s.section_count);
const s2 = (s.sections||{}).section2 || "";
console.log("s2 tail:", JSON.stringify(s2.slice(-120)));
console.log("s2 has …:", /…/.test(s2));
