# 21书城 book.21cnjy.com 探测记录（2026-10-04，匿名 curl）

UA: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36

## 请求清单（5 个，达上限）
1. `https://book.21cnjy.com/` → 200, 97653B (`home.html`) 书城首页，含搜索框（书籍/工作室/专题）
2. `https://book.21cnjy.com/search/search-special?searchVal=高考真题` → 200, 29524B (`search-special.html`)，命中 17 个专题
3. `https://book.21cnjy.com/series/list?series_id=898` → 200, 140045B (`series898.html`)
   - 专题名：**【高考真题】近六年（2020—2025年）高考真题卷免费下载**，下载量 218926，2025-07-24 更新
   - 收录 2020–2025 各省/各卷种试卷打包（如 /store/311667.shtml 2025年广东省高考各科试卷）
4. `https://book.21cnjy.com/store/311667.shtml` → 200, 217691B (`store311667.html`)
   - 含 9+ 个文件项，`data-payMoney="0" data-coinMoney="0"`（0 元 / 0 学币）
   - 例：2025年新高考Ⅰ卷语文真题试卷（含答案）→ https://www.21cnjy.com/H/99/31070/23174067.shtml?bkid=311667
   - 按钮："免费下载（校网通专属）"、"订阅包免费下载"、"立即下载"（走 S_down_load_resource）
5. `https://www.21cnjy.com/H/99/31070/23174067.shtml` → 200 但响应头 `X-Tengine-Error: denied by custom_acl`，正文为阿里云 WAF JS 挑战（acw_sc__v2 cookie 计算），curl 无法读取真实内容 (`res23174067.decoded.html`)

## 关键证据（store311667.html 内嵌 JS）
```js
function down_load_resource(e, paySuit, assetId) {
var isLogin = 0; //是否登录
...
if (!isLogin) {
window.location = 'https://passport.21cnjy.com/login?jump_url=https://book.21cnjy.com/store/311667.shtml';
return false;
}
```
→ 匿名点击"立即下载"直接跳登录页。文件价格虽为 0 学币，但下载动作强制登录。

## 结论
- 可达性：book.21cnjy.com 可直接匿名浏览（首页/搜索/专题/书籍页均 200）。
- 内容形态：打包书籍/专辑（多文件打包，单文件 0 学币）；文件本体在 www.21cnjy.com（阿里云 WAF 保护）。
- 匿名下载：不可行（JS 强制跳登录；资源页另有 WAF JS 挑战）。
- 门槛：登录（注册）。免费账号登录后能否 0 学币直接下载：未验证（未注册）。
  另有商业通道：校网通专属免费、订阅包、包月会员（￥9.9 起，会员免单）。
- 未下载任何样本（匿名不可下）。
