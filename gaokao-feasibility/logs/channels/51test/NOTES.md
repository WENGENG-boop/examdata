# 无忧考网 51test.net 探测记录（2026-10-04，匿名 curl）

UA: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36
注意：本站为 GBK 编码，证据文件已另存 UTF-8 转码版（*.gbk-decoded.html）。

## 请求清单（5 个）
1. `https://www.51test.net/gaokao/zhenti/` → 200, 43175B (`zhenti.html` / `zhenti.gbk-decoded.html`)
   栏目"2026高考真题"：大量条目如"2026年北京高考数学真题及答案(Word版)" /show/11299289.html
2. `https://www.51test.net/show/11299289.html` → 200, 9835B (`article11299289.gbk-decoded.html`)
   - 正文：【文档名称】2026年北京高考数学真题及答案(Word版).doc；【文档格式】Word版
   - 【文档下载】"点击下载WORD文档" → `onclick="opendownform(strVarViewURL,'Word文档下载')"`（JS）
   - 【文档预览】"前五页预览" → 图片直链 `https://img.wykw.com/uploadfile/tiku/2026/0616/1114520666109.png` 等
3. `https://js.wykw.com/js_new/func_show.js` → 200, 4667B（无下载逻辑）
4. `https://js.wykw.com/js_new/s.js` → 200, 3646B（含下载 URL 构造逻辑）
   ```js
   var strVarViewURL = "https://user.51test.net/vip/download/word/?id=" + str_articleid + "&classid=" + str_classid + "&nclassid=" + str_nclassid + "&nkey=" + str_nkey + "&is_downloadurl=" + is_downloadurl;
   ```
5. `https://user.51test.net/vip/download/word/?id=11299289&classid=1&nclassid=1&nkey=zt&is_downloadurl=1` → **302 → `https://user.51test.net/wap/user/reg_wx.html`**（"微信注册无忧考网"）
   证据：`vip-download.headers.txt`、`vip-download.html`（注册页 HTML）

## 附加证据（CDN 域名，非站内请求）
- `https://img.wykw.com/uploadfile/tiku/2026/0616/1114520666109.png` → 200, PNG 38KB, 794x1123（A4 预览图）
- 已存样本：`samples/channels/51test/preview1.png`（前五页预览图之一，匿名可下）

## 结论
- 可达性：栏目页/文章页匿名可达（200），无 IP 封锁。
- 内容形态：在线图文（预览图 PNG 直链）+ Word 文档下载（站内端点）。
- 匿名下载：**不可行**。Word 下载端点 302 跳转微信注册页；路径含 `/vip/download/`，疑似还需会员。
- 门槛：注册（微信扫码）→ 可能叠加 VIP。
- 匿名可得：文章正文 + 前五页预览图（图片）。
- 风险：下载路径 `/vip/` 表明文档下载与会员体系绑定；注册方式为微信，自动化不可行。
