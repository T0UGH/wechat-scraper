from __future__ import annotations
import re
import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Page

SOGOU_SEARCH_URL = "https://weixin.sogou.com/weixin"


class CaptchaRequiredError(Exception):
    """搜狗触发验证码保护，需要人工干预"""
    pass


class SogouCrawler:
    def __init__(self, headless: bool = True, delay_ms: int = 2000):
        """
        headless: 是否无头模式。遭遇验证码时建议改为 False 以便手动处理。
        delay_ms: 每次翻页后等待时间（毫秒）。
        """
        self.headless = headless
        self.delay_ms = delay_ms
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.context = self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            viewport={"width": 1280, "height": 800},
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        try:
            self.context.close()
        except Exception:
            pass
        try:
            self.browser.close()
        except Exception:
            pass
        try:
            self._playwright.stop()
        except Exception:
            pass

    def _check_captcha(self, page: Page):
        """检测当前页面是否出现验证码，若出现则抛出异常"""
        if (
            page.query_selector("#verify_con") is not None
            or page.query_selector(".gt_container") is not None
            or "antispider" in page.url
            or "请输入验证码" in page.content()
        ):
            raise CaptchaRequiredError(
                "搜狗触发验证码保护，请使用 --no-headless 模式手动处理后重试"
            )

    def get_article_list(self, account_name: str, limit: int = 100) -> list[dict]:
        """用 Playwright 翻页抓取文章列表元数据。

        先按来源过滤，只保留来自目标公众号的文章。
        若前 3 页搜索结果全被过滤（说明搜狗关键词搜索未能召回该账号文章），
        则自动切换为不过滤模式并打印提示。
        """
        MAX_PAGES = 50
        articles: list[dict] = []
        all_raw: list[dict] = []  # 未过滤的原始结果，仅在回退时使用
        filter_active = True
        page = self.context.new_page()
        try:
            current_page = 1
            while len(articles) < limit:
                url = f"{SOGOU_SEARCH_URL}?type=2&query={account_name}&page={current_page}"
                page.goto(url, timeout=30000, wait_until="domcontentloaded")

                # 等待文章列表渲染（最多10秒）
                try:
                    page.wait_for_selector(".news-box .news-list li", timeout=10000)
                except PlaywrightTimeoutError:
                    # 可能是验证码或无结果
                    self._check_captcha(page)
                    print(f"[i] 第 {current_page} 页无结果，停止翻页")
                    break

                self._check_captcha(page)

                # 用 BeautifulSoup 解析渲染后的 HTML
                soup = BeautifulSoup(page.content(), "lxml")
                items = soup.select(".news-box .news-list li")
                if not items:
                    print(f"[i] 第 {current_page} 页无结果，停止翻页")
                    break

                for item in items:
                    if len(articles) >= limit:
                        break
                    # 先解析一次（不过滤），跟随跳转拿真实 URL（避免重复跳转）
                    article_raw = self._parse_article_item(item, "")
                    if not article_raw:
                        continue
                    article_raw["url"] = self._resolve_url(article_raw["url"])
                    # 收集未过滤结果备用
                    if filter_active and len(all_raw) < limit:
                        all_raw.append(article_raw)
                    # 判断是否通过来源过滤
                    source = article_raw.get("source", "")
                    if not account_name or not source or account_name in source:
                        articles.append(article_raw)

                # 若前 3 页过滤后仍无结果，切换到不过滤模式
                if filter_active and current_page >= 3 and len(articles) == 0:
                    print(
                        f"[!] 前 {current_page} 页搜索结果均来自其他公众号（非「{account_name}」），"
                        "搜狗关键词搜索未能直接召回目标账号的文章。\n"
                        "    已切换为不过滤模式，返回所有含该关键词的文章，请通过 source 字段自行判断。\n"
                        "    提示：若想精准抓取，请尝试使用更具唯一性的账号名称或 ID。"
                    )
                    filter_active = False
                    articles = all_raw.copy()

                current_page += 1
                if current_page > MAX_PAGES:
                    print(f"[i] 已达最大翻页限制 {MAX_PAGES} 页，停止")
                    break

                page.wait_for_timeout(self.delay_ms)

        finally:
            page.close()

        return articles

    def _parse_article_item(self, item, account_name: str) -> dict | None:
        """解析单条文章搜索结果"""
        title_el = item.select_one("h3 a")
        if not title_el:
            return None

        # 公众号名称在 .all-time-y2
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

    def _resolve_url(self, url: str) -> str:
        """跟随搜狗跳转链接，返回真实的微信文章 URL。
        若已是 mp.weixin.qq.com 地址则直接返回。
        跳转失败时返回原 URL。
        """
        if "mp.weixin.qq.com" in url:
            return url
        if "weixin.sogou.com/link" not in url:
            return url
        tab = self.context.new_page()
        try:
            tab.goto(url, timeout=20000, wait_until="domcontentloaded")
            try:
                tab.wait_for_url("**/mp.weixin.qq.com/**", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            return tab.url
        except Exception:
            return url
        finally:
            tab.close()

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
