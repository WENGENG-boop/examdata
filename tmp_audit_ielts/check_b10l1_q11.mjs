import { pteListening } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
const l = await pteListening(10, 1);
console.log("url=", l.url);
console.log("questions numbers:", l.questions.map(q=>q.number).join(","));
const q10 = l.questions.find(q=>q.number===10), q12 = l.questions.find(q=>q.number===12);
console.log("Q10:", JSON.stringify(q10));
console.log("Q12:", JSON.stringify(q12));
