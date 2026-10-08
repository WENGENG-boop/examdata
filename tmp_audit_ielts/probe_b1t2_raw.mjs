import { pteListening } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
const r = await pteListening(1, 2);
console.log(JSON.stringify(r.answer_key, null, 1).slice(0, 1500));
console.log("---- questions sample ----");
console.log(JSON.stringify(r.questions, null, 1).slice(0, 1200));
console.log("questions_missing=", JSON.stringify(r.questions_missing));
