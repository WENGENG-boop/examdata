import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveSubject,subjectMatches,normalizePaper,groupPapers } from './search.mjs';
const subjects = [{code:'0580',title:'Mathematics',qualification:'IGCSE'},{code:'9709',title:'Mathematics',qualification:'A Level'},{code:'9231',title:'Further Mathematics',qualification:'A Level'},{code:'0455',title:'Economics',qualification:'IGCSE'}];
test('code with a Chinese name and full-width digits is exact',()=>assert.equal(resolveSubject(subjects,'数学 ９７０９').code,'9709'));
test('three-digit numeric input preserves leading-zero syllabus codes',()=>assert.equal(resolveSubject(subjects,'580').code,'0580'));
test('math defaults to 9709 while explicit IGCSE stays selectable',()=>{assert.equal(resolveSubject(subjects,'数学').code,'9709');assert.equal(resolveSubject(subjects,'maths').code,'9709');assert.equal(resolveSubject(subjects,'mathematics igcse').code,'0580');});
test('qualification resolves a duplicate subject title',()=>assert.equal(resolveSubject(subjects,'mathematics igcse').code,'0580'));
test('name and code pair resolves exact code, not all named subjects',()=>assert.deepEqual(subjectMatches(subjects,'Mathematics · 9709').map(s=>s.code),['9709']));
test('unknown but valid syllabus codes can query live without catalog membership',()=>assert.equal(resolveSubject(subjects,'9868').code,'9868'));
test('partial number cannot match arbitrary syllabus codes',()=>assert.equal(resolveSubject(subjects,'97').code,null));
test('paper prefixes and zero padding normalize consistently',()=>{assert.equal(normalizePaper('Paper 11'),'11');assert.equal(normalizePaper('P1'),'01');assert.equal(normalizePaper('卷 １'),'01');assert.notEqual(normalizePaper('1'),normalizePaper('11'));});
test('Edexcel variant and Chinese subject alias normalize',()=>{assert.equal(normalizePaper('WEC11/01','edexcel'),'wec11-01');assert.equal(resolveSubject([{code:'ial18-economics',title:'Economics (2018)'}],'经济学','edexcel').code,'ial18-economics');});
test('paper and mark scheme pair only with a complete matching identity',()=>{const base={board:'cie',code:'9709',year:2024,season:'Jun',paper:'11'};const groups=groupPapers([{...base,url:'https://test/qp',type:'question_paper'},{...base,url:'https://test/ms',type:'mark_scheme'},{...base,paper:'12',url:'https://test/other'},{...base,paper:null,url:'https://test/unknown'}]);assert.equal(groups.length,3);assert.equal(groups[0].documents.length,2);});

import {cieDocuments,pearsonDocuments,allSeasonResources} from './resources.mjs';
test('CIE session ER/GT remain visible when filtering a paper',()=>{const q={board:'cie',subject:'9709',year:'2024',season:'Jun',paper:'11'};const files=['9709_s24_qp_11.pdf','9709_s24_qp_12.pdf','9709_s24_gt.pdf','9709_s24_er.pdf','9709_s23_gt.pdf'];const d=cieDocuments({total:5,rows:files.map(file=>({file}))},q);assert.deepEqual(d.map(r=>r.type),['question_paper','grade_threshold','examiner_report']);assert.throws(()=>cieDocuments({total:8,rows:[]},q));});
test('Pearson rejects gated files and keeps reports for matching unit',()=>{const category=['Pearson-UK:Document-Type/Examiner-report'];const records=[{category,url:'/content/dam/pdf/test/wec11-01-pef-2024.pdf'},{category,url:'/content/dam/secure/silver/wec11-01-pef.pdf'},{category,url:'/content/dam/pdf/test/wec12-01-pef-2024.pdf'}];const d=pearsonDocuments(records,{paper:'wec11-01'});assert.equal(d.length,1);assert.equal(d[0].type,'examiner_report');});
test('Edexcel label with specification resolves exactly',()=>assert.equal(resolveSubject([{title:'Mathematics (2018)',code:'ial18-mathematics'}],'数学 Mathematics (2018) · International A Level · ial18-mathematics','edexcel').code,'ial18-mathematics'));
test('all seasons queries each board season and preserves paper identities',async()=>{
  for(const [board,expected] of [['cie',['Mar','Jun','Nov']],['edexcel',['January','June','October','November']]]) {
    const calls=[];
    const result=await allSeasonResources({board,subject:'math',year:'2024',paper:'11',season:''},async q=>{
      calls.push(q.season);assert.equal(q.paper,'11');assert.equal(q.year,'2024');
      return {documents:[{...q,code:q.subject,url:`https://test/${q.season}`,type:'question_paper'}],warning:''};
    });
    assert.deepEqual(calls,expected);assert.equal(groupPapers(result.documents).length,expected.length);assert.equal(result.warning,'');
  }
});
test('an empty or failed season does not discard other season results',async()=>{
  const result=await allSeasonResources({board:'cie',season:''},async q=>{
    if(q.season==='Mar') throw new Error('timeout');
    return {documents:q.season==='Jun'?[{url:'https://test/june',season:q.season}]:[],warning:''};
  });
  assert.equal(result.documents.length,1);assert.match(result.warning,/Mar 查询失败：timeout/);assert.doesNotMatch(result.warning,/Nov/);
});
test('all failed seasons report failure instead of claiming no matches',async()=>{
  await assert.rejects(allSeasonResources({board:'edexcel',season:''},async()=>{throw new Error('offline');}),/January 查询失败.*November 查询失败/);
});
