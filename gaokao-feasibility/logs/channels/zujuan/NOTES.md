# 组卷网 zujuan.xkw.com 探测记录（2026-10-04，匿名 curl）

UA: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36

## 请求清单（2 个）
1. `https://zujuan.xkw.com/` → 200，但正文为 8235B **JS 反爬挑战页**（`home.html`）
   - 与 zxxk.com 完全相同的 alicfw 挑战：隐藏 parm_0/parm_1 + 混淆 `check()`（hash32 → setCookie → reload）
2. FetchURL 复核同一 URL → 仅返回同一段混淆 JS 原文（无法执行）

## 结论
- 可达性：域名可达，但**所有 HTTP 客户端均被阿里云 alicfw JS 人机校验拦截**，无法获得任何真实页面。
- 内容形态：**JS 反爬墙**（需浏览器执行挑战）。
- 匿名在线预览/下载门槛：**未验证**（无法进入任何试卷页）。
- 未下载任何样本。
- 备注：组卷网与学科网同属 xkw.com 体系，反爬策略一致；本任务禁用桌面浏览器，未做浏览器复核。
