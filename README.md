# WeChat Scraper

抓取微信公众号文章列表及原文内容，导出为 CSV / JSON / Markdown。无需登录微信账号。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## 使用

```bash
# 抓取「人民日报」最近100篇，导出 CSV、JSON 和 Markdown
python main.py --account "人民日报" --limit 100

# 只抓文章列表，不抓原文
python main.py --account "人民日报" --limit 50 --no-content

# 断点续抓
python main.py --account "人民日报" --limit 200 --resume

# 只导出 Markdown（每篇文章一个 .md 文件，含 YAML front matter）
python main.py --account "人民日报" --format markdown

# 只导出 JSON
python main.py --account "人民日报" --format json
```

## 输出字段

| 字段 | 说明 |
|------|------|
| title | 文章标题 |
| publish_date | 发布时间 |
| url | 原文链接 |
| digest | 摘要 |
| cover_url | 封面图 URL |
| author | 作者 |
| content_text | 正文纯文本 |
| content_html | 正文 HTML |
| read_count | 阅读数（不保证有） |

## Markdown 导出格式

每篇文章生成一个独立 `.md` 文件（存放于 `output/<公众号>/` 目录），文件头部为 YAML front matter：

```markdown
---
title: 文章标题
author: 作者
publish_date: 2024-01-15 10:30:00
url: "https://mp.weixin.qq.com/s/xxxxx"
digest: 摘要内容
cover_url: ""
read_count: "1234"
account: 人民日报
scraped_at: 2026-03-03T12:00:00
---

正文内容...
```

## 注意

- 搜狗微信可能触发验证码，工具会退出并提示你在浏览器手动处理后重试
- 微信原文链接有有效期，尽快抓取
- 请控制抓取频率，避免被封 IP
- 需要 Python 3.10+ 或 Python 3.9+（配合 `from __future__ import annotations`）
