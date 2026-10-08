/** detail.mjs — kmf 详情页统一抓取（TPO Official 与机经通用）。
 *
 *  纯增量模块：不改变 jj.mjs / kmf.mjs 既有解析路径。
 *  - 复用 jj.fetchJjDetail 的提取逻辑（read/listen 逐题全解析；speak/write 整页文本 +
 *    口语题干 / 写作范文（如页面内嵌）/ 音频直链）。
 *  - 对 TPO Official 条目（data/kmf-index.json 内 URL）补充 label/official/set_id，
 *    使 TPO speak/write 详情不再依赖机经元数据即可归因。
 */
import { kmf } from './catalog.mjs';
import { fetchJjDetail, jjHashOf } from './jj.mjs';

/** 抓取任意 kmf 详情页（/detail/{read|listen|speak|write}/{hash}.html）。
 *  业务失败返回 {ok:false,error}。 */
export async function fetchKmfDetail({ url, refresh = false } = {}) {
  const h = jjHashOf(url);
  if (!h) return { ok: false, error: `无法识别的详情页 URL：${url}` };
  const item = kmf().items.find((x) => x.url === String(url)) || null;
  const r = await fetchJjDetail({ url, refresh });
  if (!r.ok) return r;
  const out = { ...r };
  if (item) {
    out.kmf_item = { section: item.section, label: item.label, official: item.official, url: item.url };
    out.label = out.label || item.label;
    out.official = item.official;
    out.set_id = `tpo-${item.official}`;
  }
  return out;
}
