from __future__ import annotations
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
