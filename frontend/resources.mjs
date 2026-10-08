// Frontend-only read-only catalogue helper; no backend data or process is changed.
const origin='https://qualifications.pearson.com';
const types={qp:'question_paper',ms:'mark_scheme',er:'examiner_report',gt:'grade_threshold'};
export function cieDocuments(data,query) {
  if(!Array.isArray(data.rows) || Number(data.total)!==data.rows.length) throw new Error('CIE 文件目录不完整');
  const prefix=`${query.subject}_${{Jun:'s',Nov:'w',Mar:'m'}[query.season]}${String(query.year).slice(-2)}_`;
  return data.rows.flatMap(r=>{
    const name=r.file || '', m=name.match(/^(\d{4})_([msw])(\d{2})_(qp|ms|er|gt)(?:_(\d{1,2}))?\.pdf$/);
    if(!m || !name.startsWith(prefix) || (m[5] && query.paper && m[5]!==query.paper)) return [];
    return [{...query,type:types[m[4]],paper:m[5] || '',url:`https://cie.fraft.cn/obj/Common/Fetch/redir/${name}`,title:name,origin:'live'}];
  });
}
export function pearsonDocuments(records,query) {
  if(!Array.isArray(records)) throw new Error('Edexcel 文件目录格式错误');
  return records.flatMap(r=>{
    const raw=r.url || '',url=raw.startsWith('/')?origin+raw:raw;
    if(!/^https:\/\/qualifications\.pearson\.com\/content\/dam\/pdf\/[A-Za-z0-9_./ %()-]+\.pdf$/i.test(url) || /\/(?:secure|silver|gold|\.\.)\//i.test(url)) return [];
    const tag=(r.category || []).find(c=>c.startsWith('Pearson-UK:Document-Type/'))?.split('/').pop()?.toLowerCase();
    const type={'question-paper':'question_paper','mark-scheme':'mark_scheme','examiner-report':'examiner_report'}[tag];
    if(!type) return [];
    const paper=raw.split('/').pop().match(/^([a-z0-9]+-\d{2})[-_]/i)?.[1].toLowerCase() || '';
    if(query.paper && paper && ![paper,paper.split('-')[0]].includes(query.paper)) return [];
    return [{...query,type,paper,url,title:r.title || raw.split('/').pop(),origin:'live'}];
  });
}
async function request(url,options={}) {
  const res=await fetch(url,{...options,signal:AbortSignal.timeout(45000),redirect:'error'});
  if(!res.ok) throw new Error(`来源查询失败（HTTP ${res.status}）`);
  return res;
}
export function syllabusFor(syllabi,query) {
  const table=syllabi && (query.board==='edexcel'?syllabi.edexcel:syllabi.cie);
  const entry=table && query.subject ? table[query.subject] : null;
  if(!entry) return null;
  return {board:query.board,subject:query.subject,title:entry.title || query.subject,page:entry.page || '',syllabuses:entry.syllabuses || [],origin:'snapshot'};
}
const cache=new Map();
export async function allSeasonResources(query,load,syllabi) {
  const seasons=query.board==='cie'?['Mar','Jun','Nov']:['January','June','October','November'];
  const results=await Promise.allSettled(seasons.map(season=>load({...query,season})));
  const documents=[],warnings=[];
  results.forEach((result,i)=>{
    if(result.status==='fulfilled') {
      documents.push(...result.value.documents);
      if(result.value.warning) warnings.push(`${seasons[i]}：${result.value.warning}`);
    } else warnings.push(`${seasons[i]} 查询失败：${result.reason?.message || '来源暂不可用'}`);
  });
  if(results.every(r=>r.status==='rejected')) throw new Error(warnings.join('；'));
  return {documents:[...new Map(documents.map(d=>[d.url,d])).values()],warning:warnings.join('；'),syllabus:syllabusFor(syllabi,query)};
}
export async function resources(query,subjects,syllabi) {
  if(!query.season) return allSeasonResources(query,q=>resources(q,subjects,syllabi),syllabi);
  const syllabus=syllabusFor(syllabi,query);
  const key=JSON.stringify(query),cached=cache.get(key);
  if(cached && Date.now()-cached.time<600000) return {...cached.value,syllabus};
  let documents,warning='';
  if(query.board==='cie') {
    if(!/^\d{4}$/.test(query.subject) || !['Jun','Nov','Mar'].includes(query.season)) throw new Error('请选择有效科目与考季');
    const res=await request('https://cie.fraft.cn/obj/Common/Fetch/renum',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({subject:query.subject,year:query.year,season:query.season})});
    documents=cieDocuments(await res.json(),query);
  } else {
    const subject=subjects.find(s=>s.code===query.subject);
    if(!subject || !['January','June','October','November'].includes(query.season)) throw new Error('请从科目列表选择 Edexcel 课程');
    const fq=`category:"Pearson-UK:Qualification-Family/International-Advanced-Level" AND category:"Pearson-UK:Specification-Code/${subject.code}" AND category:"Pearson-UK:Exam-Series/${query.season}-${query.year}"`;
    const res=await request(origin+'/services/pearson/algolia/GET.servlet?'+new URLSearchParams({fq,hitsPerPage:'1000'}));
    const payload=await res.json(),records=payload.searchResults?.algoliaRecords;
    if(!Array.isArray(records) || records.length>=1000 || [payload.nbHits,payload.searchResults.nbHits].some(n=>n!=null && n>records.length)) throw new Error('Edexcel 目录不完整，请缩小查询范围');
    documents=pearsonDocuments(records,query);
    try {
      const html=await (await request(origin+'/en/support/support-topics/results-certification/grade-boundaries.html')).text();
      const urls=[...new Set(html.match(/\/content\/dam\/pdf\/Support\/Grade-boundaries\/International-A-level\/[^\s"'<>]+\.pdf/gi) || [])];
      const matches=urls.filter(u=>u.toLowerCase().includes(`${query.season.toLowerCase()}-${query.year}`) && u.toLowerCase().includes('international-advanced-level'));
      if(!matches.length) {
        // Official archive filenames follow this pattern; expose only a confirmed PDF.
        const path=`/content/dam/pdf/Support/Grade-boundaries/International-A-level/grade-boundaries-${query.season.toLowerCase()}-${query.year}-international-advanced-level.pdf`;
        const probe=await fetch(origin+path,{method:'HEAD',signal:AbortSignal.timeout(20000),redirect:'error'});
        if(probe.ok && /application\/pdf/i.test(probe.headers.get('content-type') || '')) matches.push(path);
      }
      documents.push(...matches.map(u=>({...query,paper:'',type:'grade_threshold',title:'International A Level Grade Boundaries（全科目）',url:origin+u,origin:'live'})));
    } catch {warning='GT 分数线来源暂时无法读取；其他文件已显示。';}
  }
  const value={documents:[...new Map(documents.map(d=>[d.url,d])).values()],warning,syllabus};cache.set(key,{time:Date.now(),value});return value;
}
