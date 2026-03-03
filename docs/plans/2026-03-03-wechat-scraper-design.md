# 微信公众号文章抓取工具 设计文档

Date: 2026-03-03

## 背景与目标

抓取指定微信公众号（他人公众号，无管理权限）的完整文章列表及每篇文章的原文内容，导出为 CSV 和 JSON 文件。无需微信账号登录。

## 约束条件

- 完全免登录（无微信账号）
- 使用 Python
- 获取尽可能多的字段

## 整体架构

两阶段流水线：

```
[阶段1] 搜狗微信搜索
  输入：公众号名称
  → 搜索公众号 → 获取 fakeid
  → 翻页抓取文章列表元数据
  输出：[{title, date, url, digest, cover_url, ...}]

[阶段2] Playwright 原文抓取
  输入：文章 URL 列表
  → 模拟浏览器逐篇访问
  → 提取正文、作者、阅读数等
  输出：完整文章数据

[阶段3] 导出
  → 合并数据 → CSV + JSON
```

## 目录结构

```
wechat-scraper/
├── main.py              # 入口，命令行参数
├── sogou_crawler.py     # 搜狗微信：获取文章列表
├── article_crawler.py   # Playwright：抓取原文内容
├── exporter.py          # 导出 CSV / JSON
├── requirements.txt
└── README.md
```

## 数据字段

| 字段 | 来源 |
|------|------|
| `title` | 搜狗 |
| `publish_date` | 搜狗 |
| `url` | 搜狗 |
| `digest`（摘要） | 搜狗 |
| `cover_url`（封面图） | 搜狗 |
| `author` | 原文页面 |
| `content_text`（纯文本） | 原文页面 |
| `content_html`（原始HTML） | 原文页面 |
| `read_count`（阅读数，不保证有） | 原文页面 |

## 反爬策略

- 请求间随机延迟 1~3 秒
- Playwright 使用 stealth 模式（`playwright-stealth`）
- 搜狗遇到验证码时暂停并提示用户手动处理
- 断点续抓：记录已处理 URL，重跑时跳过

## 命令行接口

```bash
python main.py --account "公众号名称" --limit 100 --output ./output --format both
```

参数说明：
- `--account`：公众号名称（必填）
- `--limit`：最多抓取文章数，默认 100
- `--output`：输出目录，默认 `./output`
- `--format`：`csv` / `json` / `both`，默认 `both`

## 技术依赖

- `requests` + `beautifulsoup4`：搜狗页面抓取
- `playwright` + `playwright-stealth`：原文页面渲染
- `pandas`：CSV 导出
- `fake-useragent`：随机 UA
