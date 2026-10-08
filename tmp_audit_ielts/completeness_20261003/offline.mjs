import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const dir=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(dir,'../..');
const api=await import('../../ielts-api/ielts-api.mjs');
const pte=await import('../../ielts-api/pte.mjs');
const cam=await import('../../ielts-api/cam21.mjs');
const hub={title:{rendered:'fixture'},content:{rendered:'<a href="/ielts-reading-test-1/">Academic Reading Test 1</a>'}};
const content='<p>1. first question</p><p>2. second question</p><p>3. third question</p><button>Show Answers</button><div id="bg-showmore-hidden-1"><ol>'+Array.from({length:40},(_,i)=>`<li>${i===1?'':`answer${i+1}`}</li>`).join('')+'</ol></div>';
globalThis.fetch=async url=>new Response(JSON.stringify(String(url).includes('?slug=')?[{id:1,title:{rendered:'fixture'},content:{rendered:content}}]:hub),{status:200,headers:{'content-type':'application/json'}});
const shift=await pte.readingTest(1,1);
const result={blank_list_shift:{answer_count:shift.answer_count,questions:shift.questions.slice(0,3)},cam21_audio_generic:[1,2,3,4].map(x=>api.listeningAudio(21,1,x)),cam21:[]};
globalThis.fetch=async url=>new Response(fs.readFileSync(path.join(root,'tmp_audit_ielts/cam21',String(url).split('/').at(-1)),'utf8'),{status:200});
for(let t=1;t<=4;t++)for(const skill of ['reading','listening']){
 const r=await cam[skill](t);fs.writeFileSync(path.join(dir,`offline-cam21-${t}-${skill}.json`),JSON.stringify(r,null,2));
 const nums=(r.questions||[]).map(x=>x.number);const covered=new Set();for(const a of r.answer_key||[]){covered.add(a.number);for(const n of a.inputs||[])covered.add(Number(n));}
 result.cam21.push({test:t,skill,counts:r.counts,missing_questions:Array.from({length:40},(_,i)=>i+1).filter(n=>!nums.includes(n)),answer_covered_with_inputs:[...covered].sort((a,b)=>a-b)});
}
fs.writeFileSync(path.join(dir,'offline-findings.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify(result,null,2));
