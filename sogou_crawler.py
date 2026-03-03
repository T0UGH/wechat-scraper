from __future__ import annotations
import requests
import time
import random
import re
import datetime
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

SOGOU_SEARCH_URL = "https://weixin.sogou.com/weixin"


class CaptchaRequiredError(Exception):
    """搜狗触发验证码保护，需要人工干预"""
    pass


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
        """搜索公众号，返回 {name, fakeid, account_id, intro, avatar_url}

        注意：搜狗微信搜索会对爬虫进行反爬虫保护，包括：
        - JS 动态渲染结果（.news-list2 / .news-list 由 JavaScript 填充）
        - 验证码拦截
        如遇到这些情况，本方法返回 None。
        """
        params = {"type": 1, "query": account_name}
        resp = self.session.get(
            SOGOU_SEARCH_URL, params=params, headers=self._headers(), timeout=10
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # 搜狗可能通过 JS 动态填充 .news-list2 或 .news-list
        # 静态 HTML 可能只有空的 .news-box
        items = soup.select(".news-box .news-list li")
        if not items:
            items = soup.select(".news-list2 li")
        if not items:
            return None

        item = items[0]
        link = item.select_one("a[href]")
        if not link:
            return None

        href = link.get("href", "")
        name_el = item.select_one(".tit")
        intro_el = item.select_one(".txt-info")
        avatar_el = item.select_one("img")

        detail_url = "https://weixin.sogou.com" + href if href.startswith("/") else href
        self._sleep()
        detail_resp = self.session.get(
            detail_url, headers=self._headers(), timeout=10, allow_redirects=True
        )
        fakeid = self._extract_fakeid(detail_resp.url, detail_resp.text)

        return {
            "name": name_el.get_text(strip=True) if name_el else account_name,
            "fakeid": fakeid,
            "intro": intro_el.get_text(strip=True) if intro_el else "",
            "avatar_url": avatar_el.get("src", "") if avatar_el else "",
        }

    def get_article_list(self, account_name: str, limit: int = 100) -> list[dict]:
        """翻页抓取文章列表元数据"""
        MAX_PAGES = 50
        articles = []
        page = 1
        while len(articles) < limit:
            params = {"type": 2, "query": account_name, "page": page}
            resp = self.session.get(
                SOGOU_SEARCH_URL, params=params, headers=self._headers(), timeout=10
            )
            resp.raise_for_status()

            if "请输入验证码" in resp.text or "antispider" in resp.url:
                raise CaptchaRequiredError("搜狗触发验证码保护，请在浏览器中手动处理后重试")

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
            if page > MAX_PAGES:
                print(f"[i] 已达最大翻页限制 {MAX_PAGES} 页，停止")
                break
            self._sleep()

        return articles

    def _parse_article_item(self, item, account_name: str) -> dict | None:
        """解析单条文章搜索结果"""
        title_el = item.select_one("h3 a")
        if not title_el:
            return None

        # 公众号名称在 .all-time-y2（不再使用不存在的 .account selector）
        source_el = item.select_one(".all-time-y2")
        # 过滤非目标公众号的文章（仅在能识别来源时过滤）
        if source_el and account_name and account_name not in source_el.get_text():
            return None

        digest_el = item.select_one("p.txt-info")
        cover_el = item.select_one("img")

        url = title_el.get("href", "")
        if url.startswith("/"):
            url = "https://weixin.sogou.com" + url

        # 先尝试 script 标签内的时间戳（搜狗实际结构）
        publish_date = ""
        script_el = item.select_one("span.s2 script, label.s2 script")
        if script_el:
            m = re.search(r"timeConvert\('(\d+)'\)", script_el.string or "")
            if m:
                publish_date = datetime.datetime.fromtimestamp(
                    int(m.group(1))
                ).strftime("%Y-%m-%d %H:%M:%S")
        else:
            # fallback: 尝试 "t" 属性或直接文本
            date_el = item.select_one("label.s2, span.s2, .time")
            if date_el:
                ts = date_el.get("t")
                if ts:
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

    def _extract_fakeid(self, url: str, html: str) -> str:
        """从 URL 或 HTML 中提取 fakeid"""
        match = re.search(r"fakeid=([a-zA-Z0-9_-]+)", url)
        if match:
            return match.group(1)
        match = re.search(r'"fakeid"\s*:\s*"([a-zA-Z0-9_-]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'fakeid=([a-zA-Z0-9_-]+)', html)
        if match:
            return match.group(1)
        return ""
