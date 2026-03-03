from __future__ import annotations
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Page

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
            try:
                page.wait_for_selector("#js_content", timeout=10000)
            except PlaywrightTimeoutError:
                result["error"] = "content_not_found"
                # fall through to finally — do NOT return here

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

    def _safe_text(self, page: Page, selector: str) -> str:
        try:
            el = page.query_selector(selector)
            return el.inner_text().strip() if el else ""
        except Exception:
            return ""

    def close(self):
        self.context.close()
        self.browser.close()
        self._playwright.stop()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
