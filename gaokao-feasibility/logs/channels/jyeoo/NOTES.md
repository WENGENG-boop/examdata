# 菁优网 jyeoo.com 探测记录（2026-10-04，匿名 curl）

UA: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36

## 请求清单（5 个）
1. `https://www.jyeoo.com/` → 200, 242500B（`home.html`）首页正常，标题"专注小学初中高中试卷分析与组卷，备课平台 - 菁优网"
2. `https://www.jyeoo.com/partialgk` → 200, 187404B（`partialgk.html`）试题列表页，含大量试卷详情链接（如 `/bio2/report/detail/<uuid>`）
3. `https://www.jyeoo.com/specialgk` → 200, 96324B（`specialgk.html`）"2026高考"专题页，提及 高考真题/下载/VIP/会员
4. `https://www.jyeoo.com/math2/report/detail/<uuid>`（试卷详情）→ **302 → `/?ReturnUrl=...`**（强制登录）
5. `https://www.jyeoo.com/math2/training/testdoingnew?...`（在线做题）→ **302 → `/?ReturnUrl=...`**（强制登录）

## 关键证据
- `reportdetail.headers.txt`：302 Location: `/?ReturnUrl=%2fmath2%2freport%2fdetail%2f...`，随后 200 落地为登录首页
- `testdoing.headers.txt`：302 Location: `/?ReturnUrl=%2fmath2%2ftraining%2ftestdoingnew%3f...`

## 结论
- 可达性：域名与列表页匿名可达（200），无 IP 封锁；服务器 volc-dcdn。
- 内容形态：在线题库（题干/试卷以页面呈现，下载走站内端点）。
- 匿名下载：**不可行**——试卷详情页与做题页均 302 跳登录。
- 门槛：登录（注册）→ 疑似叠加积分/会员（页面出现 VIP/会员字样，未细验）。
- 未下载任何样本（匿名不可下）。
