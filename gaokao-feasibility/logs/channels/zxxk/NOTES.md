# 学科网 zxxk.com 探测记录（2026-10-04，匿名 curl）

UA: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36

## 请求清单（3 个）
1. `https://www.zxxk.com/gaokao/` → 200，但正文为 8235B 的 **JS 反爬挑战页**（`gaokao.html`）
   - 页面含隐藏字段 parm_0/parm_1 与混淆 JS `check()`（hash32 计算 + setCookie + location.reload）
   - 关键特征串：`alicfw_gfver`、`v1.200309.1` → 阿里云防火墙（alicfw）人机校验
2. FetchURL 复核同一 URL → 仅返回同一段混淆 JS 原文，无法执行
3. `https://m.zxxk.com/gaokao/` → 301 重定向回 `https://www.zxxk.com/gaokao/`，同样返回挑战页（`m.html`）

## 结论
- 可达性：域名可达，但**所有 curl/HTTP 客户端均被 alicfw JS 人机校验拦截**，无法获得任何真实页面内容。
- 内容形态：**JS 反爬墙**（需浏览器执行挑战后 reload）。
- 匿名预览/下载门槛：**未验证**（无法进入任何资源页）。
- 未下载任何样本。
- 风险/备注：反爬严格；如需评估需真实浏览器环境（本任务禁用桌面浏览器工具，故未做）。
