import { coverage, listening } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/cam21.mjs";
const c = await coverage();
console.log("reading_tests=", c.reading_tests, "listening_tests=", c.listening_tests);
console.log("total_reading_answers=", c.total_reading_answers, "total_listening_answers=", c.total_listening_answers, "audio_files=", c.audio_files);
console.log("reading:", JSON.stringify(c.reading));
console.log("listening:", JSON.stringify(c.listening));
// transcript 行数与质量
for (const t of [1,2,3,4]) {
  const l = await listening(t);
  const totalLines = l.transcript.reduce((n,s)=>n+s.lines.length,0);
  const withSpeaker = l.transcript.reduce((n,s)=>n+s.lines.filter(x=>x.speaker).length,0);
  const withTime = l.transcript.reduce((n,s)=>n+s.lines.filter(x=>x.time!=null).length,0);
  const withText = l.transcript.reduce((n,s)=>n+s.lines.filter(x=>(x.text||"").trim()).length,0);
  console.log(`t${t}: lines=${totalLines} speaker=${withSpeaker} time=${withTime} text=${withText}`);
  const s1 = l.transcript[0];
  console.log(`   sample: `, JSON.stringify(s1.lines.slice(0,3)));
}
