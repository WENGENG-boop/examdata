import { pteReading, pteListening } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
const r = await pteReading(10, 1);
console.log("pteReading(10,1).questions_missing =", JSON.stringify(r.questions_missing));
const l = await pteListening(10, 1);
console.log("pteListening(10,1).questions_missing =", JSON.stringify(l.questions_missing));
