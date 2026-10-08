# 易试卷/第一试卷网 yishijuan.com 探测记录（2026-10-04，匿名 curl）

UA: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36

## 请求清单
1. `https://www.yishijuan.com/` → 200, 31505B (`home.html`) 站名"第一试卷网"，主打免费中小学试卷下载
2. `https://www.yishijuan.com/gaozhongshijuan/search.php?kw=高考真题` → 302→200, 20400B (`search-gaokao.html`)
   命中大量高考真题条目（2025/2026 各卷），例：
   - 《2025高考真题数学试卷及答题卡》 /gaozhongshijuan/1544.html
   - 2026年高考山东湖南卷高考真题（生物+地理+政治+历史） /gaozhongshijuan/2057.html
   - 《历年高考真题1990-2025》 /gaozhongshijuan/998.html
3. `https://www.yishijuan.com/gaozhongshijuan/1544.html` → 200, 23682B (`item1544.html`)
4. `https://www.yishijuan.com/gaozhongshijuan/998.html` → 200, 20209B (`item998.html`)
5. `https://pan.baidu.com/s/1WFFk45THwXlzntEx0cn85A?pwd=6677`（百度网盘分享页）→ 302→200, 16034B (`baidupan-share.html`)
   - 标题："百度网盘 请输入提取码"，纯 JS 应用，curl 只见静态骨架（`baidupan-share.headers.txt`）
   - FetchURL 复核：同样只得到"百度网盘 请输入提取码"标题页

## 关键证据
- item1544.html 正文（无需登录即可见）：
  ```
  直接点击下面链接进入【百度网盘】下载
  点击这里进入【百度网盘】下载 https://pan.baidu.com/s/1wbgfJenS1BNowgCosdpeRw?pwd=6677 提取码 6677
  ```
- item998.html 正文（同结构）：`https://pan.baidu.com/s/1WFFk45THwXlzntEx0cn85A?pwd=6677`

## 结论
- 可达性：站点 curl 直接可达（首页/搜索/条目页均 200），无 IP 封锁、无验证码。
- 内容形态：PDF 资源索引页；下载由**百度网盘分享链接（含提取码）**承载，非站内文件。
- 匿名下载：站点层无门槛（链接+提取码在 HTML 明文，无需登录/积分/付费）；
  但实际下载依赖百度网盘。分享页为 JS 渲染，匿名经 HTTP 工具无法完成提取码验证；
  **匿名是否可下载文件：未验证**（需浏览器；百度网盘惯例通常要求登录账号）。
- 未下载样本（网盘流程无法以 curl 完成；未登录百度账号）。
- 风险：链接为第三方网盘，可能失效；资源版权不明。
