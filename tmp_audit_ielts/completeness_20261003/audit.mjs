import fs from 'node:fs';
import path from 'node:path';
import * as api from '../../ielts-api/ielts-api.mjs';
import * as cam from '../../ielts-api/cam21.mjs';
const dir=path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/i,'$1'));
const root=path.resolve(dir,'../..');
const nativeFetch=globalThis.fetch;
const requests=[];
globalThis.fetch=async (url,options)=>{
 const r=await nativeFetch(url,options); const copy=r.clone();
 const body=await copy.text(); const index=requests.length;
 fs.writeFileSync(path.join(dir,`raw-${index}.txt`),body);
 requests.push({index,url:String(url),status:r.status,at:new Date().toISOString()});
 fs.writeFileSync(path.join(dir,'requests.json'),JSON.stringify(requests,null,2));
 return r;
};
const rows=[];
const summarize=(r,book,test,skill)=>({book,test,skill,ok:r.ok,error:r.error,questions:(r.questions||[]).length,missing:r.questions_missing||[],answer_entries:(r.answer_key||[]).length,nonempty_answers:(r.answer_key||[]).filter(x=>x!=null&&String(typeof x==='object'?x.answer:x).trim()).length,audio:(r.audio||[]).length});
for(let book=1;book<=21;book++){
 const jobs=[];for(let test=1;test<=4;test++)for(const skill of ['reading','listening'])jobs.push({book,test,skill});
 let i=0;
 await Promise.all(Array.from({length:2},async()=>{while(i<jobs.length){const j=jobs[i++];try{const r=await (j.skill==='reading'?api.pteReading:api.pteListening)(j.book,j.test);fs.writeFileSync(path.join(dir,`pte-${j.book}-${j.test}-${j.skill}.json`),JSON.stringify(r,null,2));rows.push(summarize(r,j.book,j.test,j.skill));}catch(e){rows.push({...j,ok:false,error:String(e)})}fs.writeFileSync(path.join(dir,'live-matrix.json'),JSON.stringify(rows,null,2));}}));
 console.log(`book ${book}: ${rows.filter(x=>x.book===book&&x.ok).length}/8 returned; missing question slots ${rows.filter(x=>x.book===book).reduce((s,x)=>s+(x.missing?.length||0),0)}`);
}
for(let test=1;test<=4;test++)for(const skill of ['reading','listening']){
 const r=await cam[skill](test);fs.writeFileSync(path.join(dir,`cam21-${test}-${skill}.json`),JSON.stringify(r,null,2));
}
console.log('done',rows.length);
