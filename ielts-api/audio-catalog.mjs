/**
 * audio-catalog.mjs — 雅思听力音频目录与身份状态机（计划 S09）
 *
 * 状态机（单向推进，链接构造绝不算成功）：
 *   candidate  链接构造完成，仅登记候选 URL，未验证任何字节
 *   available  已下载/复用实际字节；magic 容器识别 + ffprobe 元数据 + 全文件解码检查通过
 *   verified   在 available 基础上，录音身份经可信证据核验（官方题本绑定 / 原文锚点匹配 / ASR 匹配）
 *   failed     全部候选 URL 尝试失败（404 / HTML / 坏文件 / 解码失败），保留错误链
 *
 * 关键约束（对应审计 A09/A10/A14）：
 *   - HEAD/Content-Length 不是可播放证明；只有实际字节 + 解码才到 available。
 *   - 同一 identity+scope+part 下 hash 相同 → 合并同一 audio_id 的多 URL（raw/cdn/local）；
 *     hash 不同 → 独立变体记录（:v2），分别核验，旧对齐不得自动继承。
 *   - 不同 Part 出现相同 hash → duplicate_content_across_parts 问题（防"同一音频复制四次"）。
 *   - 整套(full_test)音频可登记四 Part 区间(part_intervals)，派生 Part 视图永不单独计为 verified；
 *     只有真实 Part 级记录 verified 才能 audio_complete=true。
 *   - 内容类型（content-type）不可信：cam21 的 mp3 实际以 application/octet-stream 分发，必须 sniff magic。
 */
import crypto from "node:crypto";

export const AUDIO_SCHEMA = "ielts.audio-catalog/1";
export const CHECKPOINT_SCHEMA = "ielts.audio-verify-checkpoint/1";

export const AUDIO_STATUS = Object.freeze({
  CANDIDATE: "candidate",
  AVAILABLE: "available",
  VERIFIED: "verified",
  FAILED: "failed",
});

export const AUDIO_SCOPE = Object.freeze({
  FULL_TEST: "full_test",
  PART: "part",
});

/** 可接受的 verified 证据类别（每条须带 ref 指向可复查的原始证据） */
export const VERIFICATION_KINDS = Object.freeze([
  "official_binding",        // 题本页面/官方来源直接绑定 audio→test/part（如 cam21 听力页 audioTracks）
  "transcript_anchor_match", // 原文首/中/尾锚点与音频内容一致（ASR 或人工核验）
  "asr_match",               // 局部 ASR 转录与候选原文相符
]);

export const MASLOW = Object.freeze({
  name: "maslow/EnglishLearning",
  raw: "https://raw.githubusercontent.com/maslow/EnglishLearning/main/",
  cdn: "https://cdn.jsdelivr.net/gh/maslow/EnglishLearning@main/",
});

export const CAM21 = Object.freeze({
  name: "maqsudjon-cell/cambridge-21",
  raw: "https://raw.githubusercontent.com/maqsudjon-cell/cambridge-21/main/",
  cdn: "https://cdn.jsdelivr.net/gh/maqsudjon-cell/cambridge-21@main/",
});

export function pad2(n) {
  return String(n).padStart(2, "0");
}

export function partIdentity(book, test, part) {
  return `cambridge:${book}:shared:listening:${test}:P${part}`;
}

export function fullTestIdentity(book, test) {
  return `cambridge:${book}:shared:listening:${test}`;
}

export function audioIdFor(identity, scope, variant = 1) {
  const base = "audio:" + identity + (scope === AUDIO_SCOPE.FULL_TEST ? ":full" : "");
  return variant > 1 ? base + ":v" + variant : base;
}

export function maslowPartCandidates(book, test, part) {
  const p = `ielts_listening/book_${pad2(book)}/test_${test}_part_${part}.mp3`;
  return [
    { source: "maslow", url: MASLOW.raw + p, via: "raw" },
    { source: "maslow", url: MASLOW.cdn + p, via: "cdn" },
  ];
}

export function maslowFullCandidates(book, test) {
  const p = `ielts_listening/book_${pad2(book)}/test_${test}.mp3`;
  return [
    { source: "maslow", url: MASLOW.raw + p, via: "raw" },
    { source: "maslow", url: MASLOW.cdn + p, via: "cdn" },
  ];
}

export function cam21Candidates(test, section) {
  const p = `audio/C21T${test}_Section_${section}.mp3`;
  return [
    { source: "cam21", url: CAM21.raw + p, via: "raw" },
    { source: "cam21", url: CAM21.cdn + p, via: "cdn" },
  ];
}

function baseRecord({ identity, scope, part, source, urls }) {
  return {
    audio_id: audioIdFor(identity, scope),
    identity,
    scope,
    part,
    variant: 1,
    status: AUDIO_STATUS.CANDIDATE,
    source,
    urls: urls.map((u) => ({ url: u.url, via: u.via, tried: false, last_error: null })),
    local_samples: [],
    content_sha256: null,
    bytes: null,
    container: null,
    codec: null,
    sample_rate: null,
    channels: null,
    duration_sec: null,
    fetched_at: null,
    file_path: null,
    identity_status: "unverified",
    verification_refs: [],
    part_intervals: null,
    probe: null,
    decode: null,
    error: null,
    notes: [],
  };
}

/**
 * 构建初始目录：全部记录均为 candidate（未验证任何字节）。
 * @param {object} opts
 * @param {Array<{book:number,test:number,part:number}>} [opts.maslowParts]
 * @param {Array<{book:number,test:number}>} [opts.maslowFull]
 * @param {Array<{test:number,section:number}>} [opts.cam21]
 */
export function buildAudioCatalog({ maslowParts = [], maslowFull = [], cam21 = [], meta = {} } = {}) {
  const catalog = {
    schema: AUDIO_SCHEMA,
    generated_at: new Date().toISOString(),
    records: [],
    derived_parts: [],
    issues: [],
    meta,
  };
  const seen = new Set();
  for (const { book, test, part } of maslowParts) {
    const identity = partIdentity(book, test, part);
    const audio_id = audioIdFor(identity, AUDIO_SCOPE.PART);
    if (seen.has(audio_id)) continue;
    seen.add(audio_id);
    catalog.records.push(baseRecord({ identity, scope: AUDIO_SCOPE.PART, part, source: "maslow", urls: maslowPartCandidates(book, test, part) }));
  }
  for (const { book, test } of maslowFull) {
    const identity = fullTestIdentity(book, test);
    const audio_id = audioIdFor(identity, AUDIO_SCOPE.FULL_TEST);
    if (seen.has(audio_id)) continue;
    seen.add(audio_id);
    catalog.records.push(baseRecord({ identity, scope: AUDIO_SCOPE.FULL_TEST, part: null, source: "maslow", urls: maslowFullCandidates(book, test) }));
  }
  for (const { test, section } of cam21) {
    const identity = partIdentity(21, test, section);
    const audio_id = audioIdFor(identity, AUDIO_SCOPE.PART);
    if (seen.has(audio_id)) continue;
    seen.add(audio_id);
    catalog.records.push(baseRecord({ identity, scope: AUDIO_SCOPE.PART, part: section, source: "cam21", urls: cam21Candidates(test, section) }));
  }
  return catalog;
}

function pushIssue(catalog, issue) {
  if (!catalog.issues) catalog.issues = [];
  catalog.issues.push(issue);
}

function findRecordByUrl(catalog, url) {
  return catalog.records.find((r) => r.urls.some((u) => u.url === url)) || null;
}

/** 同 hash 跨不同 Part/identity 的内容重复检测（防同一音频冒充四个 Part） */
export function refreshDuplicateIssues(catalog) {
  const bySha = new Map();
  for (const r of catalog.records) {
    if (!r.content_sha256) continue;
    const key = r.content_sha256;
    if (!bySha.has(key)) bySha.set(key, []);
    bySha.get(key).push(r.audio_id);
  }
  const dupes = [];
  for (const [sha, ids] of bySha) {
    if (ids.length > 1) dupes.push({ sha256: sha, audio_ids: ids });
  }
  catalog.issues = (catalog.issues || []).filter((i) => i.kind !== "duplicate_content_across_parts");
  for (const d of dupes) {
    pushIssue(catalog, { kind: "duplicate_content_across_parts", severity: "high", ...d });
  }
  return dupes;
}

/**
 * 应用一次探测结果。
 * 失败形态： { url, error:{kind,message,status} } → 标记该 URL 已尝试；
 *           全部 URL 尝试完且无成功 → status=failed。
 * 成功形态： { url?, via?, identity?, scope?, part?, source?, sha256, bytes, container,
 *             codec, sample_rate, channels, duration_sec, file_path, fetched_at,
 *             decode_ok, decode_error, local_sample? }
 *           → 按 identity+scope+part 合并（同 hash 合并 URL；异 hash 建变体记录）。
 * @returns {{record: object|null, issues: Array<object>}}
 */
export function applyProbe(catalog, probe) {
  const issues = [];

  // ---------- 失败尝试 ----------
  if (probe.error && !probe.sha256) {
    const rec = probe.audio_id
      ? catalog.records.find((r) => r.audio_id === probe.audio_id) || null
      : probe.url
        ? findRecordByUrl(catalog, probe.url)
        : null;
    if (!rec) return { record: null, issues };
    const u = rec.urls.find((x) => x.url === probe.url);
    if (u) {
      u.tried = true;
      u.last_error = { kind: probe.error.kind || "error", message: String(probe.error.message || probe.error), status: probe.error.status ?? null };
    }
    const allTried = rec.urls.every((x) => x.tried);
    if (allTried && rec.status === AUDIO_STATUS.CANDIDATE) {
      rec.status = AUDIO_STATUS.FAILED;
      rec.error = { kind: "all_urls_failed", attempts: rec.urls.map((x) => ({ url: x.url, error: x.last_error })) };
    }
    return { record: rec, issues };
  }

  // ---------- 内容探测成功 ----------
  if (!probe.sha256) throw new Error("applyProbe: probe needs sha256 or error");
  let rec = probe.audio_id
    ? catalog.records.find((r) => r.audio_id === probe.audio_id) || null
    : probe.url
      ? findRecordByUrl(catalog, probe.url)
      : null;
  if (!rec && probe.identity) {
    const scope = probe.scope || AUDIO_SCOPE.PART;
    const same = catalog.records.filter((r) => r.identity === probe.identity && r.scope === scope && (scope === AUDIO_SCOPE.FULL_TEST || r.part === probe.part));
    rec = same.find((r) => r.content_sha256 === probe.sha256) || same[0] || null;
  }
  if (!rec && probe.identity) {
    // 目录中不存在该 identity（例如 PTE 兜底新增）→ 就地创建候选记录
    const scope = probe.scope || AUDIO_SCOPE.PART;
    rec = baseRecord({
      identity: probe.identity,
      scope,
      part: scope === AUDIO_SCOPE.PART ? probe.part ?? null : null,
      source: probe.source || "unknown",
      urls: probe.url ? [{ url: probe.url, via: probe.via || "unknown" }] : [],
    });
    catalog.records.push(rec);
  }
  if (!rec) return { record: null, issues };

  const sameGroup = catalog.records.filter(
    (r) => r.identity === rec.identity && r.scope === rec.scope && (rec.scope === AUDIO_SCOPE.FULL_TEST || r.part === rec.part)
  );

  if (rec.content_sha256 && rec.content_sha256 !== probe.sha256) {
    // 目标记录已绑定不同内容 → 这是新的内容变体
    const existingVariant = sameGroup.find((r) => r.content_sha256 === probe.sha256);
    if (existingVariant) {
      rec = existingVariant;
    } else {
      const variant = Math.max(...sameGroup.map((r) => r.variant || 1)) + 1;
      const newRec = { ...rec, variant, urls: [], local_samples: [], notes: [] };
      newRec.audio_id = audioIdFor(rec.identity, rec.scope, variant);
      newRec.status = AUDIO_STATUS.CANDIDATE;
      newRec.content_sha256 = null;
      newRec.bytes = null;
      newRec.container = null;
      newRec.codec = null;
      newRec.sample_rate = null;
      newRec.channels = null;
      newRec.duration_sec = null;
      newRec.fetched_at = null;
      newRec.file_path = null;
      newRec.identity_status = "unverified";
      newRec.verification_refs = [];
      newRec.probe = null;
      newRec.decode = null;
      newRec.error = null;
      catalog.records.push(newRec);
      issues.push({ kind: "content_variant", identity: rec.identity, base_audio_id: rec.audio_id, new_audio_id: newRec.audio_id, sha256: probe.sha256 });
      pushIssue(catalog, issues[issues.length - 1]);
      rec = newRec;
    }
  } else {
    const exact = sameGroup.find((r) => r.content_sha256 === probe.sha256 && r !== rec);
    if (exact && !rec.content_sha256) {
      // 同 hash 的其它记录已存在 → 合并进它（多 URL 归并到同一 audio_id）
      rec = exact;
    }
  }

  // URL 归并
  if (probe.url) {
    const u = rec.urls.find((x) => x.url === probe.url);
    if (u) {
      u.tried = true;
      u.last_error = null;
    } else {
      rec.urls.push({ url: probe.url, via: probe.via || "unknown", tried: true, last_error: null });
    }
  }
  if (probe.local_sample) {
    if (!rec.local_samples.some((s) => s.path === probe.local_sample)) rec.local_samples.push({ path: probe.local_sample, sha256: probe.sha256 });
  }

  rec.content_sha256 = probe.sha256;
  rec.bytes = probe.bytes ?? rec.bytes;
  rec.container = probe.container ?? rec.container;
  rec.codec = probe.codec ?? rec.codec;
  rec.sample_rate = probe.sample_rate ?? rec.sample_rate;
  rec.channels = probe.channels ?? rec.channels;
  rec.duration_sec = probe.duration_sec ?? rec.duration_sec;
  rec.fetched_at = probe.fetched_at || rec.fetched_at;
  rec.file_path = probe.file_path || rec.file_path;
  rec.probe = {
    magic_ok: probe.magic_ok ?? null,
    html: probe.html ?? null,
    reason: probe.reason ?? null,
    probed_at: new Date().toISOString(),
  };
  rec.decode = { ok: probe.decode_ok ?? null, error: probe.decode_error ?? null };

  if (probe.decode_ok === true) {
    rec.status = rec.status === AUDIO_STATUS.VERIFIED ? rec.status : AUDIO_STATUS.AVAILABLE;
    rec.identity_status = rec.status === AUDIO_STATUS.VERIFIED ? "verified" : "available";
    rec.error = null;
  } else if (probe.decode_ok === false) {
    rec.status = AUDIO_STATUS.FAILED;
    rec.error = {
      kind: probe.magic_ok === false ? "probe_failed" : "decode_failed",
      message: probe.decode_error || (probe.reason || "decode failed"),
    };
  }

  const dupes = refreshDuplicateIssues(catalog);
  for (const d of dupes) issues.push({ kind: "duplicate_content_across_parts", severity: "high", ...d });
  return { record: rec, issues };
}

/**
 * 标记 verified：必须已有可用字节且提供至少一条有效核验证据。
 * @param {object} catalog
 * @param {string} audio_id
 * @param {{refs: Array<{kind:string, ref:string, note?:string}>}} opts
 */
export function markVerified(catalog, audio_id, { refs = [] } = {}) {
  const rec = catalog.records.find((r) => r.audio_id === audio_id);
  if (!rec) return { ok: false, error: "not_found" };
  if (rec.status !== AUDIO_STATUS.AVAILABLE && rec.status !== AUDIO_STATUS.VERIFIED) {
    return { ok: false, error: "not_available", status: rec.status };
  }
  const valid = refs.filter((r) => r && VERIFICATION_KINDS.includes(r.kind) && typeof r.ref === "string" && r.ref.length > 0);
  if (!valid.length) return { ok: false, error: "no_verification_refs" };
  rec.status = AUDIO_STATUS.VERIFIED;
  rec.identity_status = "verified";
  for (const v of valid) {
    if (!rec.verification_refs.some((x) => x.kind === v.kind && x.ref === v.ref)) {
      rec.verification_refs.push({ kind: v.kind, ref: v.ref, note: v.note || null, at: new Date().toISOString() });
    }
  }
  return { ok: true, record: rec };
}

/** 整套音频登记四 Part 区间（不把同一整套 URL 当四个独立 Part） */
export function setFullTestIntervals(catalog, audio_id, intervals) {
  const rec = catalog.records.find((r) => r.audio_id === audio_id);
  if (!rec) return { ok: false, error: "not_found" };
  if (rec.scope !== AUDIO_SCOPE.FULL_TEST) return { ok: false, error: "not_full_test_scope" };
  const errs = [];
  if (!Array.isArray(intervals) || intervals.length !== 4) errs.push("need_4_intervals");
  if (!errs.length) {
    const parts = new Set(intervals.map((i) => i.part));
    if (parts.size !== 4 || ![1, 2, 3, 4].every((p) => parts.has(p))) errs.push("parts_must_be_1_to_4");
    let prevEnd = -1;
    for (const i of [...intervals].sort((a, b) => a.part - b.part)) {
      if (!(i.start_sec >= 0) || !(i.end_sec > i.start_sec)) errs.push(`bad_interval_part_${i.part}`);
      if (i.start_sec < prevEnd) errs.push("intervals_overlap");
      prevEnd = i.end_sec;
    }
    if (rec.duration_sec && intervals.some((i) => i.end_sec > rec.duration_sec + 1)) errs.push("interval_exceeds_duration");
  }
  if (errs.length) return { ok: false, errors: errs };
  rec.part_intervals = [...intervals].sort((a, b) => a.part - b.part).map((i) => ({ part: i.part, start_sec: i.start_sec, end_sec: i.end_sec, status: "derived", source_audio_id: audio_id }));
  catalog.derived_parts = (catalog.derived_parts || []).filter((d) => d.derived_from !== audio_id);
  for (const iv of rec.part_intervals) {
    catalog.derived_parts.push({ identity: `${rec.identity}:P${iv.part}`, part: iv.part, start_sec: iv.start_sec, end_sec: iv.end_sec, derived_from: audio_id, status: "derived", clock: "full_test_source" });
  }
  return { ok: true, record: rec };
}

/** magic 容器识别（content-type 不可信；HTML/零长度直接拒绝） */
export function sniffAudio(buf) {
  const b = Buffer.isBuffer(buf) ? buf : Buffer.from(buf || []);
  if (b.length === 0) return { ok: false, container: null, html: false, reason: "zero_length" };
  if (b.length < 16) return { ok: false, container: null, html: false, reason: "too_short" };
  const ascii = b.subarray(0, 64).toString("latin1");
  if (/^\s*(<!doctype\s+html|<html|<\?xml)/i.test(ascii) || ascii.includes("<html")) {
    return { ok: false, container: null, html: true, reason: "html_body" };
  }
  if (ascii.startsWith("ID3")) return { ok: true, container: "mp3", html: false, reason: null };
  if (b[0] === 0xff && (b[1] & 0xe0) === 0xe0) return { ok: true, container: "mp3", html: false, reason: null };
  if (b.subarray(4, 8).toString("latin1") === "ftyp") return { ok: true, container: "m4a", html: false, reason: null };
  if (ascii.startsWith("OggS")) return { ok: true, container: "ogg", html: false, reason: null };
  if (ascii.startsWith("fLaC")) return { ok: true, container: "flac", html: false, reason: null };
  if (ascii.startsWith("RIFF") && ascii.slice(8, 12) === "WAVE") return { ok: true, container: "wav", html: false, reason: null };
  return { ok: false, container: null, html: false, reason: "unknown_magic" };
}

/** 解析 HTTP Content-Range: "bytes 0-299/123456" */
export function parseContentRange(h) {
  const m = /^bytes\s+(\d+)-(\d+)\/(\d+)$/.exec(String(h || "").trim());
  if (!m) return null;
  const start = +m[1];
  const end = +m[2];
  const total = +m[3];
  if (!(start <= end && end < total)) return null;
  return { start, end, total };
}

/**
 * 校验 300 字节探测响应：206 必须带一致 Content-Range；
 * 200 表示服务端忽略 Range（不能把整文件当探测成功）；其余状态失败。
 */
export function validateRangeProbe({ status, content_range = null, bytes_len = null }) {
  if (status === 206) {
    const cr = parseContentRange(content_range);
    if (!cr) return { ok: false, reason: "bad_content_range", content_range: content_range || null };
    if (cr.start !== 0) return { ok: false, reason: "range_start_not_zero", content_range };
    if (bytes_len != null && bytes_len !== cr.end - cr.start + 1) {
      return { ok: false, reason: "range_length_mismatch", content_range, bytes_len };
    }
    return { ok: true, total: cr.total, content_range };
  }
  if (status === 200) return { ok: false, reason: "range_ignored_full_body", note: "server ignored Range header" };
  return { ok: false, reason: "http_" + status };
}

/** 目录摘要：按状态/来源统计 + 每册每套 audio_complete（四 Part 均须真实 verified） */
export function summarizeAudioCatalog(catalog) {
  const by_status = {};
  const by_source = {};
  for (const r of catalog.records) {
    by_status[r.status] = (by_status[r.status] || 0) + 1;
    by_source[r.source] = (by_source[r.source] || 0) + 1;
  }
  const books = {};
  for (const r of catalog.records) {
    const m = /^cambridge:(\d+):shared:listening:(\d+)/.exec(r.identity);
    if (!m) continue;
    const book = +m[1];
    const test = +m[2];
    books[book] = books[book] || { tests: {} };
    const t = (books[book].tests[test] = books[book].tests[test] || { parts: {} });
    if (r.scope === AUDIO_SCOPE.PART) {
      const p = (t.parts[r.part] = t.parts[r.part] || { records: [], statuses: {}, derived: 0 });
      p.records.push(r.audio_id);
      p.statuses[r.status] = (p.statuses[r.status] || 0) + 1;
    }
  }
  for (const d of catalog.derived_parts || []) {
    const m = /^cambridge:(\d+):shared:listening:(\d+)/.exec(d.identity);
    if (!m) continue;
    const book = +m[1];
    const test = +m[2];
    const t = books[book] && books[book].tests[test];
    if (!t) continue;
    const p = (t.parts[d.part] = t.parts[d.part] || { records: [], statuses: {}, derived: 0 });
    p.derived += 1;
  }
  for (const book of Object.keys(books)) {
    for (const test of Object.keys(books[book].tests)) {
      const t = books[book].tests[test];
      const incomplete_parts = [];
      let complete = true;
      for (let p = 1; p <= 4; p++) {
        const st = t.parts[p];
        const verified = st && st.statuses && st.statuses[AUDIO_STATUS.VERIFIED] ? st.statuses[AUDIO_STATUS.VERIFIED] : 0;
        if (!verified) {
          complete = false;
          incomplete_parts.push({
            part: p,
            status: !st ? "missing" : st.statuses[AUDIO_STATUS.FAILED] ? "failed" : st.statuses[AUDIO_STATUS.AVAILABLE] ? "available" : st.derived ? "derived_only" : "candidate",
          });
        }
      }
      t.audio_complete = complete;
      t.incomplete_parts = incomplete_parts;
    }
  }
  return {
    records: catalog.records.length,
    by_status,
    by_source,
    derived_parts: (catalog.derived_parts || []).length,
    issues: (catalog.issues || []).length,
    issue_kinds: [...new Set((catalog.issues || []).map((i) => i.kind))],
    books,
  };
}

/** git blob sha1：sha1("blob <size>\0" + content)。用于把下载字节钉到仓库 tree 的 blob sha（内容级身份）。 */
export function gitBlobSha1Buffer(buf) {
  const b = Buffer.isBuffer(buf) ? buf : Buffer.from(buf || []);
  const h = crypto.createHash("sha1");
  h.update(Buffer.from(`blob ${b.length}\0`, "utf8"));
  h.update(b);
  return h.digest("hex");
}

/** 从转录行 HTML（h 字段）的 <sup class="tr-q">Q21/22</sup> 标签提取题号 */
export function transcriptQNums(h) {
  const out = new Set();
  for (const m of String(h || "").matchAll(/<sup\s+class="tr-q">([^<]*)<\/sup>/g)) {
    for (const n of m[1].matchAll(/\d+/g)) out.add(+n[0]);
  }
  return [...out].sort((a, b) => a - b);
}

/** 转录行 HTML → 纯文本。题号 <sup class="tr-q">Qn</sup> 是行内标记（已由 transcriptQNums 单独提取），
 *  先替换为空格避免与相邻单词粘连（如 "ten<sup>Q1</sup>" → "ten "），再去掉其余标签、解码常见
 *  HTML 实体（&#x27; 等，避免 token 化产生 x27 垃圾词）、归一空白。 */
export function transcriptPlainText(h) {
  return String(h || "")
    .replace(/<sup\s+class="tr-q">[^<]*<\/sup>/g, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;|&#34;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;|&#160;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * 解析 cam21 听力页面（tN-listening.html）内嵌的 audioTracks 与 TRANSCRIPTS 字面量。
 * 纯函数，无 IO。返回：
 *   audio_tracks  {section: 相对路径} 或 null
 *   transcripts   {section: [{sp,h,t}...]} 或 null（t 为候选时间戳，须 S10 校验时钟后使用）
 *   sections      {section: {lines, first_t, last_t, q_numbers}}
 *   warnings      解析告警（不抛异常）
 */
export function parseCam21ListeningPage(html) {
  const text = String(html || "");
  const warnings = [];

  let audio_tracks = null;
  const atM = /const\s+audioTracks\s*=\s*(\{[^}]*\})/.exec(text);
  if (atM) {
    try { audio_tracks = JSON.parse(atM[1]); } catch { warnings.push("audioTracks_json_invalid"); }
  } else warnings.push("audioTracks_not_found");

  let transcripts = null;
  const mi = text.indexOf("const TRANSCRIPTS");
  if (mi < 0) warnings.push("TRANSCRIPTS_not_found");
  else {
    const start = text.indexOf("{", mi);
    if (start < 0) warnings.push("TRANSCRIPTS_no_brace");
    else {
      let depth = 0, inStr = false, esc = false, end = -1;
      for (let i = start; i < text.length; i++) {
        const ch = text[i];
        if (inStr) {
          if (esc) esc = false;
          else if (ch === "\\") esc = true;
          else if (ch === '"') inStr = false;
        } else if (ch === '"') inStr = true;
        else if (ch === "{") depth++;
        else if (ch === "}") { depth--; if (depth === 0) { end = i; break; } }
      }
      if (end > start) {
        try { transcripts = JSON.parse(text.slice(start, end + 1)); } catch { warnings.push("TRANSCRIPTS_json_invalid"); }
      } else warnings.push("TRANSCRIPTS_unbalanced");
    }
  }

  const sections = {};
  if (transcripts) {
    for (const [k, lines] of Object.entries(transcripts)) {
      const ts = (lines || []).map((l) => (typeof l.t === "number" ? l.t : null)).filter((x) => x != null);
      const qnums = new Set();
      for (const l of lines || []) for (const q of transcriptQNums(l.h)) qnums.add(q);
      sections[k] = {
        lines: (lines || []).length,
        first_t: ts.length ? Math.min(...ts) : null,
        last_t: ts.length ? Math.max(...ts) : null,
        q_numbers: [...qnums].sort((a, b) => a - b),
      };
    }
  }
  return { audio_tracks, transcripts, sections, warnings };
}
