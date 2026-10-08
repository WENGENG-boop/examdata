# 百度网盘渠道探测记录（2026-10-04，匿名浏览器 + 匿名 curl）

对象：易试卷条目页给出的分享链接 `https://pan.baidu.com/s/1wbgfJenS1BNowgCosdpeRw?pwd=6677`
（即《2025高考真题数学试卷及答题卡》，见 `../yishijuan/NOTES.md` 的 item1544 证据）

## 1. 匿名 curl 流程（无任何账号）
1. GET `https://pan.baidu.com/s/1wbgfJenS1BNowgCosdpeRw?pwd=6677`
   → 200, 16034B（`pan-share1.html`），标题「百度网盘 请输入提取码」，落在 `/share/init` 页
2. POST `https://pan.baidu.com/share/verify?surl=wbgfJenS1BNowgCosdpeRw&t=<ts>&channel=chunlei&web=1&app_id=250528&clienttype=0`
   body `pwd=6677`（携 BAIDUID cookie）
   → **200 `{"errno":0,"randsk":"rMAIphQEHBrDDMAa2wwfKgWn%2Fawl9tpD"}`**（`verify.json`）
   —— 匿名即可通过提取码校验，服务端发放 BDCLND(randsk) cookie
3. 携 BDCLND cookie GET `https://pan.baidu.com/s/1wbgfJenS1BNowgCosdpeRw`
   → 200, 53991B（`share-view.html`），标题变为「百度网盘-分享文件」，HTML 内嵌
   `"share_uk":"50844815"`、`"shareid":7553454265`、顶层项 `"server_filename":"2025高考真题数学试卷及答题卡"`（isdir=1）
4. 尝试匿名调 `share/list` API（uk=50844815, shareid=7553454265, dir=/）
   → 200 但 `{"errno":2,"show_msg":"啊哦，链接出错了"}`（`list-root.json`）
   —— 列表 API 匿名调用被拒（参数/签名门槛），HTTP 工具链到此为止

## 2. 匿名浏览器流程（未登录，截图证据）
1. 打开分享链接 → 自动过提取码 → 分享页显示分享者 `wan****8143 (SVIP8)`、文件夹
   《2025高考真题数学试卷及答题卡》、过期时间"永久有效"（`pan-share-root.png`）
2. 双击进入文件夹 → **匿名可见 16 个子文件夹**（全国一卷/二卷、天津卷、上海卷、八省联考、
   2024 新课标I卷 …）（`pan-share-folder-list.png`）
3. 再进《1.2025年普通高等学校招生全国统一考试（全国一卷）》
   → **匿名可见具体文件**：`…（全国一卷）答题卡.pdf` 813KB、`…（全国一卷）试卷.pdf` 1.3M（`pan-file-level.png`）
4. 点击下载图标 → 弹「文件下载」对话框（高速下载/普通下载）（`pan-download-dialog.png`）
5. 点「普通下载」→ **弹出登录墙**（扫码登录/账号登录/短信登录）（`pan-download-login-wall.png`）
   —— 下载环节必须百度账号

## 结论
- 可达性：全流程匿名可达（无 IP 封锁）；提取码校验匿名可过。
- 匿名能力：**分享页、目录树、文件名/大小可匿名浏览**（可自动化发现与编目）。
- 门槛：**下载文件必须登录百度账号**（或客户端）；高速下载还需会员。
- 分级：**L3（需账号）**——发现与浏览 L1/L2 级，下载 L3 级；作为"网盘渠道"整体按 L3 记。
- 关联：易试卷（yishijuan）条目页明文给出该链接+提取码，即"站点索引 + 网盘承载"模式；
  同类还有知乎/贴吧帖子外链（知乎 web 端点击外链被登录弹窗拦截，见下）。
- 风险：网盘分享可能失效；资源版权不明；自动化批量下载会触发百度风控。

## 附：知乎发现渠道实测（2026-10-04）
- 文章 `https://zhuanlan.zhihu.com/p/2020198457005098898`（《历年高考真题电子版免费可打印…》）
  匿名可读全文，正文有「2008到2025《全国高考真题及答案》百度网盘下载地址点击此处」链接。
- 实测点击该外链 3 次：均未跳转；首次点击弹出知乎登录框（web 端外链受登录墙拦截），
  `click_if_interactive` 报告该处"无可点击元素"。→ 知乎作为**发现渠道**可用（文章文本可读），
  但**外链跳转在 web 端匿名不可用**；链接目标未能取得（不影响结论：网盘门槛已用易试卷链接完整验证）。
