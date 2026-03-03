# WeChat Scraper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 抓取指定微信公众号的完整文章列表及原文内容，导出为 CSV、JSON 和 Markdown 文件，无需登录。

**Architecture:** 两阶段流水线——阶段1用 requests+BeautifulSoup 抓取搜狗微信获取文章元数据列表；阶段2用 Playwright 模拟浏览器逐篇访问原文链接提取正文；阶段3合并数据导出文件。断点续抓避免重复请求。

**Tech Stack:** Python 3.10+, requests, beautifulsoup4, playwright, playwright-stealth, pandas, fake-useragent, argparse

---

### Task 1: 项目初始化

**Files:**
- Create: `wechat-scraper/requirements.txt`
- Create: `wechat-scraper/README.md`
- Create: `wechat-scraper/.gitignore`

**Step 1: 初始化 git 仓库**

```bash
cd /Users/haha/workspace/github/wechat-scraper
git init
```

Expected: `Initialized empty Git repository`

**Step 2: 创建 requirements.txt**

```
requests==2.31.0
beautifulsoup4==4.12.3
playwright==1.44.0
playwright-stealth==1.0.6
pandas==2.2.2
fake-useragent==1.5.1
lxml==5.2.2
```

**Step 3: 创建 .gitignore**

```
__pycache__/
*.pyc
.venv/
output/
*.json
*.csv
progress.json
```

**Step 4: 创建虚拟环境并安装依赖**

```bash
cd /Users/haha/workspace/github/wechat-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Expected: 所有包安装成功，`playwright install chromium` 下载 Chromium 浏览器

**Step 5: 提交**

```bash
git add requirements.txt .gitignore
git commit -m "chore: project init with dependencies"
```

---

### Task 2: 搜狗微信爬虫——搜索公众号获取 fakeid

**Files:**
- Create: `wechat-scraper/sogou_crawler.py`
- Create: `wechat-scraper/tests/test_sogou_crawler.py`

**背景知识：**
搜狗微信搜索入口：`https://weixin.sogou.com/weixin?type=1&query=公众号名称`
返回的页面中每个公众号结果包含一个跳转链接，解析其中的 `weixinhao`（即公众号ID/fakeid）用于后续翻页抓取文章列表。

**Step 1: 编写失败测试**

```python
# tests/test_sogou_crawler.py
import sys
sys.path.insert(0, '..')
from sogou_crawler import SogouCrawler

def test_search_account_returns_fakeid():
    """搜索公众号应返回包含 fakeid 的结果"""
    crawler = SogouCrawler()
    # 使用一个知名公众号做测试
    result = crawler.search_account("人民日报")
    assert result is not None
    assert "fakeid" in result
    assert len(result["fakeid"]) > 0
    assert "name" in result
```

**Step 2: 运行测试确认失败**

```bash
cd /Users/haha/workspace/github/wechat-scraper
source .venv/bin/activate
python -m pytest tests/test_sogou_crawler.py::test_search_account_returns_fakeid -v
```

Expected: `ImportError` 或 `ModuleNotFoundError`

**Step 3: 实现 SogouCrawler.search_account**

```python
# sogou_crawler.py
import requests
import time
import random
import re
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

SOGOU_SEARCH_URL = "https://weixin.sogou.com/weixin"

class SogouCrawler:
    def __init__(self, delay_min=1.0, delay_max=3.0):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.ua = UserAgent()
        self.session = requests.Session()

    def _headers(self):
        return {
            "User-Agent": self.ua.random,
            "Referer": "https://weixin.sogou.com/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def _sleep(self):
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def search_account(self, account_name: str) -> dict | None:
        """搜索公众号，返回 {name, fakeid, account_id, intro, avatar_url}"""
        params = {"type": 1, "query": account_name}
        resp = self.session.get(
            SOGOU_SEARCH_URL, params=params, headers=self._headers(), timeout=10
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # 找第一个公众号结果
        items = soup.select(".news-box .news-list li")
        if not items:
            return None

        item = items[0]
        # 提取跳转链接中的 weixinhao
        link = item.select_one("a[href]")
        if not link:
            return None

        href = link.get("href", "")
        # 从详情页链接提取 fakeid，格式如 /gzh?openid=xxx 或通过跳转
        name_el = item.select_one(".tit")
        intro_el = item.select_one(".txt-info")
        avatar_el = item.select_one("img")

        # 访问公众号详情页获取 fakeid
        detail_url = "https://weixin.sogou.com" + href if href.startswith("/") else href
        self._sleep()
        detail_resp = self.session.get(
            detail_url, headers=self._headers(), timeout=10, allow_redirects=True
        )
        # fakeid 在跳转后的 URL 或页面中
        fakeid = self._extract_fakeid(detail_resp.url, detail_resp.text)

        return {
            "name": name_el.get_text(strip=True) if name_el else account_name,
            "fakeid": fakeid,
            "intro": intro_el.get_text(strip=True) if intro_el else "",
            "avatar_url": avatar_el.get("src", "") if avatar_el else "",
        }

    def _extract_fakeid(self, url: str, html: str) -> str:
        """从 URL 或 HTML 中提取 fakeid"""
        # 尝试从 URL 参数提取
        match = re.search(r"fakeid=([a-zA-Z0-9_-]+)", url)
        if match:
            return match.group(1)
        # 尝试从 HTML 提取
        match = re.search(r'"fakeid"\s*:\s*"([a-zA-Z0-9_-]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'fakeid=([a-zA-Z0-9_-]+)', html)
        if match:
            return match.group(1)
        return ""
```

**Step 4: 运行测试**

```bash
python -m pytest tests/test_sogou_crawler.py::test_search_account_returns_fakeid -v
```

Expected: PASS（需要网络）。若搜狗返回验证码则先跳过，继续实现后续方法。

**Step 5: 提交**

```bash
git add sogou_crawler.py tests/test_sogou_crawler.py
git commit -m "feat: implement SogouCrawler.search_account"
```

---

### Task 3: 搜狗微信爬虫——翻页抓取文章列表

**Files:**
- Modify: `wechat-scraper/sogou_crawler.py`
- Modify: `wechat-scraper/tests/test_sogou_crawler.py`

**背景知识：**
搜狗微信文章搜索：`https://weixin.sogou.com/weixin?type=2&query=公众号名称&page=1`
过滤 `sourcename` 等于目标公众号名称的结果，提取每篇文章的标题、摘要、发布时间、URL、封面图。

**Step 1: 编写失败测试**

在 `tests/test_sogou_crawler.py` 追加：

```python
def test_get_article_list_returns_articles():
    """抓取文章列表应返回包含必要字段的列表"""
    crawler = SogouCrawler()
    articles = crawler.get_article_list("人民日报", limit=5)
    assert isinstance(articles, list)
    assert len(articles) > 0
    first = articles[0]
    assert "title" in first
    assert "url" in first
    assert "publish_date" in first
```

**Step 2: 运行确认失败**

```bash
python -m pytest tests/test_sogou_crawler.py::test_get_article_list_returns_articles -v
```

Expected: `AttributeError: 'SogouCrawler' object has no attribute 'get_article_list'`

**Step 3: 实现 get_article_list**

在 `sogou_crawler.py` 的 `SogouCrawler` 类中添加：

```python
def get_article_list(self, account_name: str, limit: int = 100) -> list[dict]:
    """翻页抓取文章列表元数据"""
    articles = []
    page = 1
    while len(articles) < limit:
        params = {"type": 2, "query": account_name, "page": page}
        resp = self.session.get(
            SOGOU_SEARCH_URL, params=params, headers=self._headers(), timeout=10
        )
        resp.raise_for_status()

        if "请输入验证码" in resp.text or "sogou.com/antispider" in resp.url:
            print(f"\n[!] 搜狗触发验证码，请手动处理后按 Enter 继续...")
            input()
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        items = soup.select(".news-box .news-list li")
        if not items:
            print(f"[i] 第 {page} 页无结果，停止翻页")
            break

        for item in items:
            if len(articles) >= limit:
                break
            article = self._parse_article_item(item, account_name)
            if article:
                articles.append(article)

        page += 1
        self._sleep()

    return articles

def _parse_article_item(self, item, account_name: str) -> dict | None:
    """解析单条文章搜索结果"""
    title_el = item.select_one("h3 a")
    if not title_el:
        return None

    # 过滤非目标公众号的文章
    source_el = item.select_one(".account")
    if source_el and account_name not in source_el.get_text():
        return None

    digest_el = item.select_one("p.txt-info")
    date_el = item.select_one("label.s2, span.s2, .time")
    cover_el = item.select_one("img")

    url = title_el.get("href", "")
    if url.startswith("/"):
        url = "https://weixin.sogou.com" + url

    # 日期处理：搜狗返回时间戳或相对时间
    publish_date = ""
    if date_el:
        ts = date_el.get("t")  # 时间戳属性
        if ts:
            import datetime
            publish_date = datetime.datetime.fromtimestamp(
                int(ts)
            ).strftime("%Y-%m-%d %H:%M:%S")
        else:
            publish_date = date_el.get_text(strip=True)

    return {
        "title": title_el.get_text(strip=True),
        "url": url,
        "digest": digest_el.get_text(strip=True) if digest_el else "",
        "publish_date": publish_date,
        "cover_url": cover_el.get("src", "") if cover_el else "",
        "source": source_el.get_text(strip=True) if source_el else "",
    }
```

**Step 4: 运行测试**

```bash
python -m pytest tests/test_sogou_crawler.py -v
```

Expected: 2 tests PASS

**Step 5: 提交**

```bash
git add sogou_crawler.py tests/test_sogou_crawler.py
git commit -m "feat: implement SogouCrawler.get_article_list with pagination"
```

---

### Task 4: Playwright 原文内容抓取器

**Files:**
- Create: `wechat-scraper/article_crawler.py`
- Create: `wechat-scraper/tests/test_article_crawler.py`

**背景知识：**
微信原文页面是 JS 渲染的，需要 Playwright 渲染后提取。关键选择器：
- 正文：`#js_content`
- 标题：`#activity-name`
- 作者：`#js_name` 或 `#profileBt .rich_media_meta_text`
- 发布时间：`#publish_time`
- 阅读数：`#js_read_view span.voted_count`（不稳定，可能不存在）

**Step 1: 编写失败测试**

```python
# tests/test_article_crawler.py
import sys
sys.path.insert(0, '..')
from article_crawler import ArticleCrawler

def test_fetch_article_returns_content():
    """抓取原文应返回包含正文的字典"""
    crawler = ArticleCrawler(headless=True)
    # 使用一个已知有效的微信文章 URL（需替换为实际可访问的 URL）
    test_url = "https://mp.weixin.qq.com/s/example"  # placeholder
    result = crawler.fetch_article(test_url)
    # 至少返回字典结构（URL 可能已失效，所以只验证结构）
    assert isinstance(result, dict)
    assert "url" in result
    assert "content_text" in result
    assert "content_html" in result
    assert "author" in result
    assert "read_count" in result
    crawler.close()
```

**Step 2: 运行确认失败**

```bash
python -m pytest tests/test_article_crawler.py::test_fetch_article_returns_content -v
```

Expected: `ImportError`

**Step 3: 实现 ArticleCrawler**

```python
# article_crawler.py
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


class ArticleCrawler:
    def __init__(self, headless: bool = True, delay_min: float = 2.0, delay_max: float = 5.0):
        self.headless = headless
        self.delay_min = delay_min
        self.delay_max = delay_max
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )

    def fetch_article(self, url: str) -> dict:
        """访问原文页面，提取所有字段"""
        result = {
            "url": url,
            "title": "",
            "author": "",
            "publish_date": "",
            "content_text": "",
            "content_html": "",
            "read_count": "",
            "error": "",
        }
        page = self.context.new_page()
        try:
            if HAS_STEALTH:
                stealth_sync(page)
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            # 等待正文加载
            try:
                page.wait_for_selector("#js_content", timeout=10000)
            except PlaywrightTimeoutError:
                result["error"] = "content_not_found"
                return result

            result["title"] = self._safe_text(page, "#activity-name")
            result["author"] = (
                self._safe_text(page, "#js_name")
                or self._safe_text(page, ".rich_media_meta_text")
            )
            result["publish_date"] = self._safe_text(page, "#publish_time")
            result["read_count"] = self._safe_text(page, "#js_read_view .voted_count")

            content_el = page.query_selector("#js_content")
            if content_el:
                result["content_html"] = content_el.inner_html()
                result["content_text"] = content_el.inner_text()

        except PlaywrightTimeoutError:
            result["error"] = "timeout"
        except Exception as e:
            result["error"] = str(e)
        finally:
            page.close()
            time.sleep(random.uniform(self.delay_min, self.delay_max))

        return result

    def _safe_text(self, page, selector: str) -> str:
        try:
            el = page.query_selector(selector)
            return el.inner_text().strip() if el else ""
        except Exception:
            return ""

    def close(self):
        self.context.close()
        self.browser.close()
        self._playwright.stop()
```

**Step 4: 运行测试**

```bash
python -m pytest tests/test_article_crawler.py::test_fetch_article_returns_content -v
```

Expected: PASS（即使 URL 失效，结构验证应通过）

**Step 5: 提交**

```bash
git add article_crawler.py tests/test_article_crawler.py
git commit -m "feat: implement ArticleCrawler with Playwright stealth"
```

---

### Task 5: 断点续抓进度管理

**Files:**
- Create: `wechat-scraper/progress.py`
- Create: `wechat-scraper/tests/test_progress.py`

**Step 1: 编写失败测试**

```python
# tests/test_progress.py
import sys, os, json, tempfile
sys.path.insert(0, '..')
from progress import ProgressTracker

def test_progress_tracker_saves_and_loads():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        tracker = ProgressTracker(path)
        tracker.mark_done("https://mp.weixin.qq.com/s/abc")
        assert tracker.is_done("https://mp.weixin.qq.com/s/abc")
        assert not tracker.is_done("https://mp.weixin.qq.com/s/xyz")

        # 重新加载，验证持久化
        tracker2 = ProgressTracker(path)
        assert tracker2.is_done("https://mp.weixin.qq.com/s/abc")
    finally:
        os.unlink(path)
```

**Step 2: 运行确认失败**

```bash
python -m pytest tests/test_progress.py -v
```

**Step 3: 实现 ProgressTracker**

```python
# progress.py
import json
import os

class ProgressTracker:
    def __init__(self, path: str = "progress.json"):
        self.path = path
        self._done: set[str] = set()
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                data = json.load(f)
                self._done = set(data.get("done", []))

    def _save(self):
        with open(self.path, "w") as f:
            json.dump({"done": list(self._done)}, f, indent=2)

    def mark_done(self, url: str):
        self._done.add(url)
        self._save()

    def is_done(self, url: str) -> bool:
        return url in self._done

    def count(self) -> int:
        return len(self._done)
```

**Step 4: 运行测试**

```bash
python -m pytest tests/test_progress.py -v
```

Expected: PASS

**Step 5: 提交**

```bash
git add progress.py tests/test_progress.py
git commit -m "feat: add ProgressTracker for resume support"
```

---

### Task 6: 数据导出器

**Files:**
- Create: `wechat-scraper/exporter.py`
- Create: `wechat-scraper/tests/test_exporter.py`

**Markdown 格式说明：**
每篇文章导出为一个独立的 `.md` 文件，文件名为 `YYYY-MM-DD-<slug>.md`（slug 取标题前20字符，去除特殊符号）。
文件头部为 YAML front matter，包含所有元信息；正文在分隔符后。

示例输出：
```markdown
---
title: 这是文章标题
author: 作者名
publish_date: 2024-01-15 10:30:00
url: https://mp.weixin.qq.com/s/xxxxx
digest: 这是文章摘要内容
cover_url: https://mmbiz.qpic.cn/xxx.jpg
read_count: "1234"
account: 人民日报
scraped_at: 2026-03-03T12:00:00
---

这是正文内容第一段。

这是正文内容第二段。
```

**Step 1: 编写失败测试**

```python
# tests/test_exporter.py
import sys, os, json, tempfile
sys.path.insert(0, '..')
from exporter import Exporter

SAMPLE = [
    {
        "title": "测试文章标题",
        "url": "https://mp.weixin.qq.com/s/test",
        "publish_date": "2024-01-01",
        "digest": "摘要",
        "cover_url": "",
        "author": "作者",
        "content_text": "正文内容第一段。\n\n正文内容第二段。",
        "content_html": "<p>正文内容</p>",
        "read_count": "1000",
        "error": "",
    }
]

def test_export_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = Exporter(output_dir=tmpdir)
        path = exporter.export_json(SAMPLE, "test_account")
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["title"] == "测试文章标题"

def test_export_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = Exporter(output_dir=tmpdir)
        path = exporter.export_csv(SAMPLE, "test_account")
        assert os.path.exists(path)
        import csv
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["title"] == "测试文章标题"

def test_export_markdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = Exporter(output_dir=tmpdir)
        paths = exporter.export_markdown(SAMPLE, "test_account")
        assert len(paths) == 1
        assert os.path.exists(paths[0])
        content = open(paths[0], encoding="utf-8").read()
        # 验证 YAML front matter 存在
        assert content.startswith("---\n")
        assert "title: 测试文章标题" in content
        assert "author: 作者" in content
        assert "url: https://mp.weixin.qq.com/s/test" in content
        assert "account: test_account" in content
        assert "scraped_at:" in content
        # 验证正文在 front matter 之后
        parts = content.split("---\n", 2)
        assert len(parts) == 3  # ["", front_matter, body]
        assert "正文内容第一段" in parts[2]
```

**Step 2: 运行确认失败**

```bash
python -m pytest tests/test_exporter.py -v
```

**Step 3: 实现 Exporter**

```python
# exporter.py
import json
import os
import csv
import re
from datetime import datetime

FIELDS = [
    "title", "publish_date", "url", "digest", "cover_url",
    "author", "content_text", "content_html", "read_count", "error"
]

class Exporter:
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _filename(self, account: str, ext: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = account.replace("/", "_").replace(" ", "_")
        return os.path.join(self.output_dir, f"{safe}_{ts}.{ext}")

    def _article_md_filename(self, article: dict, output_dir: str) -> str:
        """生成单篇文章的 Markdown 文件名"""
        date_prefix = ""
        pd = article.get("publish_date", "")
        if pd:
            # 取日期部分 YYYY-MM-DD
            date_prefix = pd[:10].replace("/", "-") + "-"

        title = article.get("title", "untitled")
        # 去除不适合做文件名的字符，保留中文、字母、数字、连字符
        slug = re.sub(r'[^\w\u4e00-\u9fff-]', '', title)[:30]
        slug = slug.strip("-") or "article"
        return os.path.join(output_dir, f"{date_prefix}{slug}.md")

    def _yaml_escape(self, value: str) -> str:
        """对 YAML 字符串值做简单转义（包含特殊字符时加引号）"""
        if not value:
            return '""'
        # 含冒号、引号、换行等需要引号包裹
        if any(c in value for c in (':', '"', "'", '\n', '#', '[')):
            escaped = value.replace('"', '\\"').replace('\n', ' ')
            return f'"{escaped}"'
        return value

    def export_json(self, articles: list[dict], account: str) -> str:
        path = self._filename(account, "json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        print(f"[✓] JSON 已保存: {path}")
        return path

    def export_csv(self, articles: list[dict], account: str) -> str:
        path = self._filename(account, "csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(articles)
        print(f"[✓] CSV 已保存: {path}")
        return path

    def export_markdown(self, articles: list[dict], account: str) -> list[str]:
        """每篇文章导出为独立 .md 文件，头部含 YAML front matter"""
        md_dir = os.path.join(self.output_dir, account)
        os.makedirs(md_dir, exist_ok=True)
        paths = []
        scraped_at = datetime.now().isoformat(timespec="seconds")

        for article in articles:
            path = self._article_md_filename(article, md_dir)

            # 构建 YAML front matter
            fm_lines = [
                "---",
                f"title: {self._yaml_escape(article.get('title', ''))}",
                f"author: {self._yaml_escape(article.get('author', ''))}",
                f"publish_date: {self._yaml_escape(article.get('publish_date', ''))}",
                f"url: {article.get('url', '')}",
                f"digest: {self._yaml_escape(article.get('digest', ''))}",
                f"cover_url: {article.get('cover_url', '')}",
                f"read_count: \"{article.get('read_count', '')}\"",
                f"account: {self._yaml_escape(account)}",
                f"scraped_at: {scraped_at}",
                "---",
                "",
            ]

            body = article.get("content_text", "").strip()
            content = "\n".join(fm_lines) + "\n" + body + "\n"

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            paths.append(path)

        print(f"[✓] Markdown 已保存: {md_dir}/ ({len(paths)} 篇)")
        return paths
```

**Step 4: 运行测试**

```bash
python -m pytest tests/test_exporter.py -v
```

Expected: 3 tests PASS

**Step 5: 提交**

```bash
git add exporter.py tests/test_exporter.py
git commit -m "feat: implement Exporter for CSV, JSON, and Markdown with front matter"
```

---

### Task 7: 主入口 main.py

**Files:**
- Create: `wechat-scraper/main.py`

**Step 1: 实现 main.py**

```python
# main.py
import argparse
import sys
from sogou_crawler import SogouCrawler
from article_crawler import ArticleCrawler
from exporter import Exporter
from progress import ProgressTracker

def main():
    parser = argparse.ArgumentParser(description="微信公众号文章抓取工具")
    parser.add_argument("--account", required=True, help="公众号名称")
    parser.add_argument("--limit", type=int, default=100, help="最多抓取文章数")
    parser.add_argument("--output", default="./output", help="输出目录")
    parser.add_argument(
        "--format",
        choices=["csv", "json", "markdown", "all"],
        default="all",
        help="输出格式：csv / json / markdown / all（默认 all）",
    )
    parser.add_argument("--no-content", action="store_true", help="跳过原文抓取，只保存文章列表")
    parser.add_argument("--resume", action="store_true", help="断点续抓（跳过已抓取的文章）")
    args = parser.parse_args()

    print(f"[→] 目标公众号: {args.account}")
    print(f"[→] 最多抓取: {args.limit} 篇")

    # 阶段1：搜狗抓文章列表
    print("\n[阶段1] 搜狗微信：抓取文章列表...")
    sogou = SogouCrawler()
    articles = sogou.get_article_list(args.account, limit=args.limit)
    print(f"[✓] 共获取 {len(articles)} 篇文章元数据")

    if not articles:
        print("[!] 未找到文章，请检查公众号名称是否正确")
        sys.exit(1)

    # 阶段2：Playwright 抓原文
    if not args.no_content:
        print("\n[阶段2] Playwright：抓取原文内容...")
        progress = ProgressTracker(f"./progress_{args.account}.json") if args.resume else None
        crawler = ArticleCrawler(headless=True)
        try:
            for i, article in enumerate(articles):
                url = article.get("url", "")
                if not url:
                    continue
                if progress and progress.is_done(url):
                    print(f"  [{i+1}/{len(articles)}] 跳过（已抓取）: {article['title'][:30]}")
                    continue
                print(f"  [{i+1}/{len(articles)}] 抓取: {article['title'][:40]}")
                detail = crawler.fetch_article(url)
                article.update({
                    "author": detail["author"],
                    "content_text": detail["content_text"],
                    "content_html": detail["content_html"],
                    "read_count": detail["read_count"],
                    "error": detail["error"],
                })
                if progress:
                    progress.mark_done(url)
        finally:
            crawler.close()
        print(f"[✓] 原文抓取完成")

    # 阶段3：导出
    print("\n[阶段3] 导出文件...")
    exporter = Exporter(output_dir=args.output)
    fmt = args.format
    if fmt in ("json", "all"):
        exporter.export_json(articles, args.account)
    if fmt in ("csv", "all"):
        exporter.export_csv(articles, args.account)
    if fmt in ("markdown", "all"):
        exporter.export_markdown(articles, args.account)

    print("\n[完成] 全部任务完成！")

if __name__ == "__main__":
    main()
```

**Step 2: 验证 help 输出正常**

```bash
cd /Users/haha/workspace/github/wechat-scraper
source .venv/bin/activate
python main.py --help
```

Expected: 显示帮助信息，无报错

**Step 3: 提交**

```bash
git add main.py
git commit -m "feat: add main.py entry point with CLI"
```

---

### Task 8: 运行所有测试 + 完善 README

**Files:**
- Create: `wechat-scraper/README.md`

**Step 1: 运行全部测试**

```bash
cd /Users/haha/workspace/github/wechat-scraper
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: 所有非网络测试 PASS（test_progress, test_exporter 必须通过）

**Step 2: 创建 README.md**

```markdown
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

## 注意

- 搜狗微信可能触发验证码，工具会暂停并等待你手动处理
- 微信原文链接有有效期，尽快抓取
- 请控制抓取频率，避免被封 IP
```

**Step 3: 提交**

```bash
git add README.md
git commit -m "docs: add README with usage instructions"
```

---

## 执行方式

计划已保存。两种执行方式：

**1. Subagent-Driven（当前 session）** — 每个 Task 派发独立子 agent，任务间可 review，迭代快

**2. Parallel Session（新 session）** — 新开 session 使用 `superpowers:executing-plans` skill，批量执行并在检查点暂停

请选择执行方式。
