import {resolveSubject,subjectMatches,normalizePaper,groupPapers,subjectLabel} from './search.mjs';
import {searchDocuments,clientEnabled} from './client.mjs';
const $ = id => document.getElementById(id);
setupOpening();
const esc = v => String(v ?? '').replace(/[&<>"']/g,c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = value => {try {const u = new URL(value);return ['http:','https:'].includes(u.protocol) ? u.href : '';} catch {return '';}};
const seasonName = s => ({jun:'June',june:'June',nov:'November',november:'November',mar:'March',march:'March',jan:'January',january:'January',oct:'October',october:'October'}[String(s || '').toLowerCase()] || s || '—');
let catalog = [], cieSubjects = [], edexcelSubjects = [], subjects = [], rows = [], filtered = [], grouped = [], page = 0, requestId = 0, syllabi = null, liveSyllabus = null;
const pageSize = 10;
const documentLabel = type => ({question_paper:'QP 试卷',mark_scheme:'MS 评分标准',examiner_report:'ER 考官报告',grade_threshold:'GT 分数线'}[type] || '资料');
function sessionExtras() {return catalog.filter(r=>r.type==='examiner_report' && r.board===submitted.board && r.code===subjectCode(submitted.subject) && String(r.year)===submitted.year && (!submitted.season || seasonName(r.season)===seasonName(submitted.season)));}
let submitted = {board:'cie',subject:'',year:'',season:'',paper:''};
function syllabusEntry(board,code) {const table = syllabi && (board === 'edexcel' ? syllabi.edexcel : syllabi.cie);const entry = table && code ? table[code] : null;return entry ? {board,subject:code,title:entry.title || code,page:entry.page || '',syllabuses:entry.syllabuses || []} : null;}
function submittedSyllabus() {if (liveSyllabus) return liveSyllabus;if (!submitted.subject) return null;const list = submitted.board === 'edexcel' ? edexcelSubjects : cieSubjects;const code = resolveSubject(list,submitted.subject,submitted.board).code;return code ? syllabusEntry(submitted.board,code) : null;}
function syllabusStrip(info) {if (!info) return '';const links = (info.syllabuses || []).map(s => {const url = safeUrl(s.url);return url ? `<a class="document-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(s.title || 'Syllabus')} <span>↗</span></a>` : '';}).join('');const page = safeUrl(info.page || '');const body = links || (page ? `<a class="document-link" href="${esc(page)}" target="_blank" rel="noopener noreferrer">${esc(info.title || '科目页')} · 科目页 <span>↗</span></a>` : '');return body ? `<div class="syllabus-strip"><span class="syllabus-label">考纲</span><div class="document-actions">${body}</div></div>` : '';}
function formValues() {const values=Object.fromEntries(['board','subject','year','season','paper'].map(k => [k,$(k).value.trim()]));values.paper=normalizePaper(values.paper,values.board);return values;}
function empty(title,message,extra = '') {$('results').innerHTML = `<div class="empty"><h3>${esc(title)}</h3><p>${esc(message)}</p>${extra}</div>`;}
function subjectCode(value) {return resolveSubject(subjects,value,$('board').value).code;}
function render() {
  grouped=groupPapers(filtered);rows = grouped.slice(page * pageSize,(page + 1) * pageSize);$('result-count').textContent = `${grouped.length} 组资料 · ${filtered.length} 份文件`;
  const canLive = submitted.subject && submitted.year;
  if (!rows.length) return empty('没有找到符合条件的资料','可以调整查询条件。如果已填写科目和年份，也可以直接查找来源中的试卷。',(canLive ? '<button class="primary" id="live-search">查找原始试卷 ↗</button>' : '') + syllabusStrip(submittedSyllabus()));
  $('results').innerHTML = `${canLive?'<div class="resource-summary">'+['question_paper','mark_scheme','examiner_report','grade_threshold'].map(type=>'<span class="'+(filtered.some(d=>d.type===type)?'available':'')+'">'+documentLabel(type)+' · '+(filtered.some(d=>d.type===type)?'已找到':'来源未提供')+'</span>').join('')+'</div>':''}${syllabusStrip(submittedSyllabus())}<div class="table-wrap"><table><thead><tr><th>科目 / 试卷</th><th>考季</th><th>卷号</th><th>QP / MS / ER / GT</th></tr></thead><tbody>${rows.map((r,i) => `<tr style="--row:${i}" data-detail="${i}"><td class="subject-column"><button class="title-button" data-detail="${i}"><span class="file-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h9l5 5v16H5zM14 3v6h5M9 13h6M9 17h4"/></svg></span><span><strong>${esc(r.origin==='live' ? (subjects.find(s=>s.code===r.code) ? subjectLabel(subjects.find(s=>s.code===r.code)) : r.code) : r.title)}</strong><span class="meta">${esc(r.code)} · ${esc(r.qualification || (r.board === 'cie' ? 'Cambridge' : 'Edexcel'))}</span></span></button></td><td><span class="year-label">${esc(r.year || '—')}</span><span class="meta">${esc(seasonName(r.season))}</span></td><td><span class="paper-tag">${esc(r.paper || (r.type==='grade_threshold' && r.board==='edexcel'?'全科分数线':'整季资料'))}</span></td><td><div class="document-actions">${r.documents.map(d=>safeUrl(d.url) ? `<a class="document-link ${d.type==='mark_scheme'?'answer-link':''}" href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener noreferrer">${esc(documentLabel(d.type))} <span>↗</span></a>` : '').join('')}</div></td></tr>`).join('')}</tbody></table></div><div class="pager"><span>显示 ${page * pageSize + 1}–${Math.min((page + 1) * pageSize,grouped.length)}，共 ${grouped.length} 组</span><div><button data-page="-1" ${page === 0 ? 'disabled' : ''}>← 上一页</button><span>${page + 1} / ${Math.ceil(grouped.length / pageSize)}</span><button data-page="1" ${(page + 1) * pageSize >= grouped.length ? 'disabled' : ''}>下一页 →</button></div></div>${canLive && submitted.board === 'cie' && filtered[0]?.origin === 'catalog' ? '<p class="lookup-note">这是一份目录快照。<button id="live-search">查询来源中的最新文件 ↗</button></p>' : ''}`;
  animateResults();
}
function queryCatalog() {
  if (subjects !== ($('board').value === 'edexcel' ? edexcelSubjects : cieSubjects)) configureBoard(true);
  requestId++;page = 0;liveSyllabus = null;submitted = formValues();$('submit').disabled = false;$('results').setAttribute('aria-busy','false');
  closeSuggestions();
  if (submitted.subject && submitted.year) {
    const resolution=resolveSubject(subjects,submitted.subject,submitted.board);
    if (!resolution.code) {
      $('results-title').textContent='选择具体科目';$('results-note').textContent='从下方选择课程即可，无需记忆代码。';$('result-count').textContent='';
      empty(resolution.matches.length?'选择你要查的课程':'请选择科目',resolution.matches.length?'请选择对应课程。':'点击科目输入框可浏览课程，也可以输入中文或英文名称。',resolution.matches.map(s=>`<button class="subject-choice" data-subject="${esc(s.code)}">${esc(subjectLabel(s))} <span>${esc(s.qualification)} · ${esc(s.code)}</span> ↗</button>`).join(''));
      return;
    }
    liveSearch();return;
  }
  if (submitted.board === 'edexcel') {
    if (!submitted.subject || !submitted.year) {$('results-title').textContent = '查询 Edexcel 试卷';$('results-note').textContent = '选择科目，查询 QP / MS / ER / GT';$('result-count').textContent = '';empty('选好条件，即可查找','点击科目框选择中文课程，再选择年份。所有考季会汇总该年资料，卷号选填。');return;}
    liveSearch();return;
  }
  const resolved=resolveSubject(subjects,submitted.subject,'cie');const matchingCodes=new Set(resolved.code?[resolved.code]:subjectMatches(subjects,submitted.subject).map(s=>s.code));
  filtered = catalog.filter(r => (!submitted.subject || matchingCodes.has(r.code)) && (!submitted.year || String(r.year) === submitted.year) && (!submitted.season || seasonName(r.season) === seasonName(submitted.season)) && (!submitted.paper || r.type==='examiner_report' || normalizePaper(r.paper) === submitted.paper));
  $('results-title').textContent = ['subject','year','season','paper'].some(k => submitted[k]) ? '查询结果' : '浏览试卷';$('results-note').textContent = 'CIE 官方目录 · 2026.10.01 快照；目录收录不表示题目已解析。';render();
}
async function liveSearch() {
  const id = ++requestId;const query = {...submitted,subject:subjectCode(submitted.subject)};
  if (!query.subject || !query.year) return;
  $('submit').disabled = true;$('results').setAttribute('aria-busy','true');$('result-count').textContent = '';$('results-title').textContent = '查询结果';$('results-note').textContent = '正在查找 QP / MS / ER / GT…';$('results').innerHTML = '<div class="loading">正在查找来源中的试卷…</div>';
  try {
    if (!clientEnabled()) {if (id !== requestId) return;filtered = sessionExtras();if (filtered.length) {render();$('results-note').textContent = '在线查询已关闭（examdata.v2-client=off） · 下方仅显示目录快照中的 ER';} else empty('在线查询已关闭','在线查询已关闭（examdata.v2-client=off）。移除浏览器标记后可重试。');return;}
    const result = await searchDocuments(query);if (id !== requestId) return;liveSyllabus = result.syllabus || null;
    filtered = (result.documents || []).map(d=>({...d,code:query.subject,url:safeUrl(d.url)}));
    for(const extra of sessionExtras()) {if(!filtered.some(d=>d.type==='examiner_report' && seasonName(d.season)===seasonName(extra.season))) filtered.push(extra);}
    page = 0;$('results-note').textContent = `${query.subject} · ${query.year} · ${query.season?seasonName(query.season):'所有考季'}${query.paper?' · Paper '+query.paper:''} / ${result.origin === 'staged_fixture' ? '暂存夹具验证（staged fixture validation）· 合成夹具数据' : '原始来源文件'} · ER/GT 按文件适用范围显示${result.warning?' · '+result.warning:''}`;
    if (!filtered.length) {$('result-count').textContent = '0 份资料';empty('没有找到对应试卷','请检查科目、年份、考季与卷号。');} else render();
  } catch (e) {if (id === requestId) {$('results-note').textContent = '本次在线查询未完成';filtered=sessionExtras();if(filtered.length) {render();$('results-note').textContent=e.message+' · 下方仅显示目录快照中的 ER';}else empty('暂时无法获取试卷',e.message,syllabusStrip(submittedSyllabus()));}}
  finally {if (id === requestId) {$('results').setAttribute('aria-busy','false');$('submit').disabled = false;}}
}
function detail(row) {
  $('detail-body').innerHTML = `<span class="source-text">${row.origin === 'catalog' ? 'OFFICIAL CATALOG' : row.quality === 'synthetic_fixture' ? 'STAGED FIXTURE · 合成夹具' : 'ORIGINAL SOURCE'}</span><h2>${esc(row.origin==='live'?row.code:row.title)}</h2><dl><dt>考试局</dt><dd>${row.board === 'cie' ? 'Cambridge International' : 'Pearson Edexcel'}</dd><dt>科目代码</dt><dd>${esc(row.code)}</dd><dt>年份 / 考季</dt><dd>${esc(row.year || '—')} / ${esc(seasonName(row.season))}</dd><dt>卷号</dt><dd>${esc(row.paper || '—')}</dd></dl><p class="detail-note">${row.origin === 'catalog' ? '来自 2026 年 10 月 1 日的官方资源目录快照。文件可用性以来源站点为准。' : '来自本次查询返回的原始文件清单。'}</p><div class="document-actions">${row.documents.map(d=>safeUrl(d.url)?`<a class="primary" href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener noreferrer">${esc(documentLabel(d.type))} ↗</a>`:'').join('')}</div>${syllabusStrip(syllabusEntry(row.board,row.code) || submittedSyllabus())}`;$('detail').showModal();
}
$('query-form').onsubmit = e => {e.preventDefault();queryCatalog();};
function configureBoard(keepValues = false) {const edx = $('board').value === 'edexcel';const season = keepValues ? $('season').value : '';subjects=edx?edexcelSubjects:cieSubjects;$('subject-hint').textContent=edx?'点击选择 IAL 科目 · 中文名自动匹配 · 卷号选填':'点击选择课程 · 数学默认 A Level 9709 · 可切换 IGCSE';const seasons = edx ? ['January','June','October','November'] : ['Jun','Nov','Mar'];$('season').innerHTML = '<option value="">所有考季</option>' + seasons.map(s => `<option value="${s}">${seasonName(s)}</option>`).join('');if (season && [...$('season').options].some(o => o.value === season)) $('season').value = season;if (!keepValues) {$('subject').value='';$('paper').value='';}$('subject').placeholder = edx ? '点击选择科目，如数学 / 经济' : '输入科目、中文名或代码';$('paper').placeholder = edx ? '如 wec11-01' : '如 11 / Paper 11';closeSuggestions();}
$('reset').onclick = () => {$('query-form').reset();configureBoard();queryCatalog();};$('board').onchange = ()=>{configureBoard();queryCatalog();};
$('close-detail').onclick = () => $('detail').close();
$('detail').onclick = e => {if (e.target === $('detail')) {const r = e.target.getBoundingClientRect();if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) e.target.close();}};
document.addEventListener('click',e => {if (e.target.closest('a')) return;const row = e.target.closest('tr[data-detail]');if (row) {const selection = window.getSelection();if (!(selection && !selection.isCollapsed && selection.containsNode(row,true))) detail(rows[Number(row.dataset.detail)]);return;}const el = e.target.closest('button');if (!el) return;if (el.dataset.page) {page += Number(el.dataset.page);render();}if (el.id === 'live-search') liveSearch();if (el.dataset.subject) {chooseSubject(el.dataset.subject);if (el.classList.contains('subject-choice')) queryCatalog();}});
for (let year = 2026;year >= 2000;year--) $('year').add(new Option(String(year),String(year)));
function animateResults() {if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;$('results').animate([{opacity:0,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}],{duration:280,easing:'ease-out'});}
function closeSuggestions() {$('subject-options').hidden=true;$('subject').setAttribute('aria-expanded','false');$('subject').removeAttribute('aria-activedescendant');}
function chooseSubject(code) {const s=subjects.find(s=>s.code===code);$('subject').value=s?`${subjectLabel(s)} · ${s.qualification} · ${s.code}`:code;$('subject').focus();closeSuggestions();}
function suggestions() {
  const choices=subjectMatches(subjects,$('subject').value);
  $('subject-options').innerHTML=choices.map((s,i)=>`<button type="button" role="option" aria-selected="false" tabindex="-1" id="subject-option-${i}" data-subject="${esc(s.code)}"><span>${esc(subjectLabel(s))}</span><small>${esc(s.qualification)} <b>${esc(s.code)}</b></small></button>`).join('') || '<p class="suggestion-note">可直接输入四位科目代码查询。</p>';
  $('subject-options').hidden=false;$('subject').setAttribute('aria-expanded','true');activeOption=-1;
}
let activeOption=-1;
$('subject').oninput=suggestions;$('subject').onfocus=suggestions;
$('subject').onblur=closeSuggestions;
$('subject-options').onpointerdown=e=>e.preventDefault();
$('subject').onkeydown=e=>{
  const options=[...$('subject-options').querySelectorAll('[role="option"]')];
  if (e.key==='Escape') return closeSuggestions();
  if (e.key==='ArrowDown'||e.key==='ArrowUp') {e.preventDefault();if ($('subject-options').hidden) suggestions();const items=[...$('subject-options').querySelectorAll('[role="option"]')];if (!items.length) return;activeOption=(activeOption+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;items.forEach((el,i)=>el.setAttribute('aria-selected',String(i===activeOption)));$('subject').setAttribute('aria-activedescendant',items[activeOption].id);items[activeOption].scrollIntoView({block:'nearest'});}
  if (e.key==='Enter'&&!$('subject-options').hidden&&activeOption>=0&&options[activeOption]) {e.preventDefault();chooseSubject(options[activeOption].dataset.subject);}
};
document.addEventListener('pointerdown',e=>{if (!e.target.closest('.subject-field')) closeSuggestions();});
try {const response = await fetch('/syllabi.json');if (response.ok) syllabi = await response.json();} catch {}
try {const response = await fetch('/catalog.json');if (!response.ok) throw new Error('目录快照加载失败');const data=await response.json();catalog=data.items;edexcelSubjects=data.edexcelSubjects || [];cieSubjects=[...new Map(catalog.map(r=>[r.code,{code:r.code,title:r.title,qualification:r.qualification || ''}])).values()].sort((a,b)=>a.title.localeCompare(b.title));subjects=cieSubjects;const popular=['9709','0580','9702','9701','9700','0455'];catalog.sort((a,b)=>{const ai=popular.indexOf(a.code),bi=popular.indexOf(b.code);return (ai<0?100:ai)-(bi<0?100:bi);});configureBoard(true);queryCatalog();} catch(e) {$('results').setAttribute('aria-busy','false');empty('暂时无法加载目录',e.message);}

function setupOpening() {
  const overlay=$('opening'),canvas=$('opening-canvas'),skip=$('skip-opening'),replay=$('replay-opening');
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  const ctx=canvas.getContext('2d');
  const content=[document.querySelector('.site-header'),document.querySelector('main')];
  const duration=2450;
  let frame=0,timer=0,finishTimer=0,failsafe=0,startTime=0,active=false,returnFocus=null,width=0,height=0,particles=[];
  const colors={ink:'#111827',blue:'#2563eb',gray:'#f4f6f8'};
  const ease=t=>1-Math.pow(1-Math.max(0,Math.min(1,t)),4);
  function resize() {
    width=innerWidth;height=innerHeight;
    const ratio=Math.min(devicePixelRatio || 1,2);
    canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);ctx.setTransform(ratio,0,0,ratio,0,0);
    const scale=width<540?.76:1;
    const centerX=width/2,centerY=height/2-69*scale;
    const segments=[[-32,-45,34,-45],[-32,0,20,0],[-32,45,34,45],[-32,-45,-32,45]];
    particles=[];
    segments.forEach(([x1,y1,x2,y2],line)=>{
      const count=Math.ceil(Math.hypot(x2-x1,y2-y1)/3.1);
      for(let j=0;j<=count;j++) {
        const index=particles.length,angle=index*2.39996323,radius=Math.min(width,height)*(.18+(index%17)/52);
        particles.push({x:centerX+(x1+(x2-x1)*j/count)*scale,y:centerY+(y1+(y2-y1)*j/count)*scale,sx:centerX+Math.cos(angle)*radius,sy:centerY+Math.sin(angle)*radius,delay:(index%9)*.012,blue:index%13===0,size:index%7===0?2.2:1.45});
      }
    });
  }
  function draw(now) {
    if(!active) return;
    const elapsed=now-startTime,t=Math.min(elapsed/duration,1);
    const phase=elapsed<1500?'assembling':elapsed<2100?'identity':'reveal';
    if(overlay.dataset.phase!==phase) overlay.dataset.phase=phase;
    ctx.clearRect(0,0,width,height);
    const gather=ease((elapsed-160)/1150),scatter=ease((elapsed-2040)/400);
    particles.forEach((p,index)=>{
      const g=ease(Math.max(0,gather-p.delay)/(1-p.delay));
      const swirl=(1-g)*.48,dx=p.sx-width/2,dy=p.sy-(height/2-(width<540?52.44:69));
      const x=p.sx+(p.x-p.sx)*g+Math.sin(index+elapsed*.0014)*(1-g)*16+(Math.cos(swirl)*dx-Math.sin(swirl)*dy-dx)*(1-g);
      const y=p.sy+(p.y-p.sy)*g+Math.cos(index+elapsed*.0012)*(1-g)*16+(Math.sin(swirl)*dx+Math.cos(swirl)*dy-dy)*(1-g);
      ctx.globalAlpha=Math.min(elapsed/350,1)*(1-scatter)*(.5+.5*g);
      ctx.fillStyle=p.blue?colors.blue:colors.ink;
      ctx.fillRect(x-p.size/2,y-p.size/2,p.size,p.size);
      if(g<.85 && index%6===0) {
        ctx.globalAlpha*=.16;ctx.strokeStyle=colors.ink;ctx.lineWidth=.5;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(p.x,p.y);ctx.stroke();
      }
    });
    ctx.globalAlpha=1;
    $('opening-progress').style.transform=`scaleX(${t})`;
    $('opening-counter').textContent=String(Math.round(t*100)).padStart(3,'0');
    if(t<1) frame=requestAnimationFrame(draw);else finish();
  }
  function unlock() {
    content.forEach(el=>{if(el) el.inert=false;});
    document.body.classList.remove('opening-active');
  }
  function release() {
    clearTimeout(finishTimer);clearTimeout(failsafe);overlay.hidden=true;overlay.dataset.phase='complete';overlay.classList.remove('is-running','is-leaving');
    unlock();
    if(returnFocus instanceof HTMLElement && returnFocus.isConnected) returnFocus.focus({preventScroll:true});
    returnFocus=null;
  }
  function finish(immediate=false) {
    if(!active && overlay.hidden) return;
    active=false;cancelAnimationFrame(frame);clearTimeout(timer);
    unlock();
    if(immediate || motion.matches) return release();
    overlay.classList.add('is-leaving');document.body.classList.remove('opening-active');
    finishTimer=setTimeout(release,460);
  }
  function play() {
    if(active) return;
    clearTimeout(finishTimer);clearTimeout(failsafe);returnFocus=document.activeElement===replay?replay:null;
    if(motion.matches || !ctx) {release();return;}
    active=true;content.forEach(el=>{if(el) el.inert=true;});document.body.classList.remove('opening-complete');document.body.classList.add('opening-active');
    overlay.hidden=false;overlay.dataset.phase='assembling';overlay.classList.remove('is-running','is-leaving');
    // Recreate CSS animations for replay without altering the search form or results.
    void overlay.offsetWidth;overlay.classList.add('is-running');resize();startTime=performance.now();skip.focus({preventScroll:true});
    frame=requestAnimationFrame(draw);timer=setTimeout(()=>finish(),duration+350);
    failsafe=setTimeout(()=>{if(active) finish(true);else if(!overlay.hidden) release();else unlock();},duration+1200);
  }
  skip.onclick=()=>finish();replay.onclick=play;
  document.addEventListener('keydown',e=>{if(!overlay.hidden && e.key==='Escape') {e.preventDefault();finish();}else if(!overlay.hidden && e.key==='Tab') {e.preventDefault();skip.focus();}});
  addEventListener('resize',()=>{if(active) resize();});
  addEventListener('pagehide',()=>finish(true));
  document.addEventListener('pointerdown',()=>{if(overlay.hidden || overlay.classList.contains('is-leaving')) unlock();},true);
  document.addEventListener('visibilitychange',()=>{if(!overlay.hidden && (document.hidden || performance.now()-startTime>duration+400)) finish(true);else if(overlay.hidden) unlock();});
  motion.addEventListener('change',()=>{if(motion.matches) finish(true);});
  play();
}
