# 官方渠道探测记录（2026-10-04，匿名 curl）

UA: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36

## 请求清单
1. `https://www.neea.edu.cn/`（教育部教育考试院/中国教育考试网）→ 200, 68095B（`neea-home.html`）
   - 首页无 "真题/试题/试卷" 字样（仅新闻/考试项目导航）
2. `https://www.shmeea.edu.cn/`（上海市教育考试院）→ 200, 1329B（`shmeea-home.html`，JS 跳转 `/page/index.html`）
3. `https://www.shmeea.edu.cn/page/index.html` → 200, 19730B（`shmeea-index.html`）
   - 页面无 "真题/试题/试卷评析" 字样（导航 JS 渲染）
4. `https://www.zjzs.net/`（浙江省教育考试院）→ 200, 4884B（`zjzs-home.html`）门户首页
5. `https://eea.gd.gov.cn/`（广东省教育考试院）→ 200, 64491B（`gd-home.html`）
   - 首页无 "真题" 字样

## 结论
- 官方站点（考试院/教育部）均匿名可达（200），无封锁。
- 未发现官方渠道提供高考真题文件下载（与普遍认知一致：官方只发布考试安排、评析、成绩与录取信息；试题本身以评析/新闻形式出现，非可下载试卷）。
- 备注：本次仅浅探首页/入口页，未穷尽站内搜索；结论与用户既有认知一致。
