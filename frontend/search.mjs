export const normalize = value => String(value ?? '').normalize('NFKC').trim().toLowerCase().replace(/[·|/()[\]_,—–-]+/g,' ').replace(/\s+/g,' ').trim();
const aliases = { '数学':'mathematics','math':'mathematics','maths':'mathematics','进阶数学':'further mathematics','物理':'physics','化学':'chemistry','生物':'biology','经济':'economics','经济学':'economics','商务':'business','商科':'business','计算机':'computer science','计算机科学':'computer science','历史':'history','地理':'geography','中文':'chinese','汉语':'chinese','英语':'english','会计':'accounting','心理学':'psychology','社会学':'sociology' };
const defaults = {mathematics:'9709',physics:'9702',chemistry:'9701',biology:'9700',economics:'9708',business:'9609','computer science':'9618',history:'9489',geography:'9696',accounting:'9706',psychology:'9990',sociology:'9699','further mathematics':'9231'};
export const chineseNames = {mathematics:'数学',physics:'物理',chemistry:'化学',biology:'生物',economics:'经济',business:'商务','computer science':'计算机科学',history:'历史',geography:'地理',accounting:'会计',psychology:'心理学',sociology:'社会学','further mathematics':'进阶数学','mathematics further':'进阶数学','english language':'英语语言','english literature':'英语文学','information technology':'信息技术',french:'法语',german:'德语',spanish:'西班牙语',arabic:'阿拉伯语',law:'法律',greek:'希腊语'};
export const subjectLabel = s => `${chineseNames[normalize(s.title).replace(/\s*\d{4}$/, '').trim()] || ''} ${s.title}`.trim();
export function codeFrom(value) { const text = normalize(value); const match = text.match(/(?:^|[^\d])(\d{4})(?!\d)/); return match?.[1] || (/^\d{3}$/.test(text) ? text.padStart(4,'0') : null); }
export function subjectMatches(subjects,value) {
  const term = normalize(value); if (!term) return subjects;
  const code = codeFrom(term); if (code) return subjects.filter(s => s.code === code);
  const translated = aliases[term] || term;
  const words = translated.split(' ');
  return subjects.filter(s => words.every(w => normalize(`${subjectLabel(s)} ${s.qualification || ''} ${s.code}`).includes(w)));
}
export function resolveSubject(subjects,value,board = 'cie') {
  if (board === 'edexcel') {
    const exact = subjects.find(s=>s.code===String(value).trim() || value.includes(`· ${s.code}`));
    const matches=subjectMatches(subjects,value);
    const term=aliases[normalize(value)] || normalize(value);
    const preferred=matches.find(s=>normalize(s.title).replace(/\s*\d{4}$/, '').trim()===term && s.title.includes('2018')) || matches.find(s=>normalize(s.title).replace(/\s*\d{4}$/, '').trim()===term);
    return {code:exact?.code || preferred?.code || (matches.length===1?matches[0].code:null),matches};
  }
  const direct = codeFrom(value); if (direct) return {code:direct,matches:subjectMatches(subjects,value)};
  if (/^\d+$/.test(normalize(value))) return {code:null,matches:subjectMatches(subjects,value)};
  const matches = subjectMatches(subjects,value);
  const preferred=defaults[aliases[normalize(value)] || normalize(value)];
  return {code:preferred && /^\d{4}$/.test(preferred) ? preferred : matches.length === 1 ? matches[0].code : null,matches};
}
export function normalizePaper(value,board = 'cie') {
  let term = String(value ?? '').normalize('NFKC').trim().toLowerCase().replace(/^(?:paper|卷号|卷|p)\s*/i,'').replace(/\s+/g,'');
  if (board === 'edexcel') return term.replace(/[\/_]/g,'-');
  return /^\d{1,2}$/.test(term) ? term.padStart(2,'0') : term;
}
export function groupPapers(records) {
  const groups = new Map();
  for (const record of records) {
    const key = record.code && record.year && record.season && record.paper ? [record.board,record.code,record.year,record.season.toLowerCase(),normalizePaper(record.paper,record.board)].join(':') : record.url || record.key;
    if (!groups.has(key)) groups.set(key,{...record,documents:[]});
    const group = groups.get(key);
    if (!group.documents.some(d => d.url === record.url)) group.documents.push(record);
  }
  return [...groups.values()];
}
