
import fs from 'node:fs';
import zlib from 'node:zlib';
const MAGIC = Buffer.from([0x28,0xB5,0x2F,0xFD]);
const buf = fs.readFileSync(process.argv[2]);
const offs=[]; let i=0;
while(true){ const idx=buf.indexOf(MAGIC,i); if(idx<0)break; offs.push(idx); i=idx+4; }
const recs=[];
for(let k=0;k<offs.length;k++){
  const start=offs[k], end=k+1<offs.length?offs[k+1]:buf.length;
  let t; try{ t=zlib.zstdDecompressSync(buf.subarray(start,end)).toString('utf8'); }catch(e){ continue; }
  for(const line of t.split('\n')){ if(!line.trim())continue; try{recs.push(JSON.parse(line));}catch{} }
}
const first = recs.find(r=>r.type==='user/message' && r.data.source && r.data.source.kind==='user');
const txt = (first.data.content||[]).map(c=>c.text||'').join('');
console.log(txt);
