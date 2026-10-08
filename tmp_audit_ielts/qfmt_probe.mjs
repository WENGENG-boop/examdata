// 抽样：题干编号格式与提取覆盖率（无点格式 vs 有点格式）
import { bookTests, readingTest, listeningTest } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/pte.mjs';
const books = [2, 5, 8, 10, 12, 15, 17, 19, 20, 21];
for (const b of books) {
  for (const kind of ['reading', 'listening']) {
    const r = kind === 'reading' ? await readingTest(b, 1) : await listeningTest(b, 1);
    if (!r.ok) { console.log(`b${b} ${kind}: FAIL ${r.error}`); continue; }
    const text = r.passage ? null : null;
    // 重新拉 text 不易；用 questions 统计 + 直接抓页面文本
    const qc = r.question_count, ac = r.answer_count;
    const nums = r.questions.map(q => q.number);
    const missing = []; for (let i = 1; i <= 40; i++) if (!nums.includes(i)) missing.push(i);
    console.log(`b${b} ${kind}: q=${qc} a=${ac} missing=[${missing.join(',')}]`);
    await new Promise(s => setTimeout(s, 300));
  }
}
