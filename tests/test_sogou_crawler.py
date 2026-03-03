import sys
import pytest
sys.path.insert(0, '..')
from sogou_crawler import SogouCrawler, CaptchaRequiredError


def test_get_article_list_returns_articles():
    """抓取文章列表应返回包含必要字段的列表（Playwright 版本，网络依赖测试）"""
    with SogouCrawler(headless=True) as crawler:
        try:
            articles = crawler.get_article_list("人民日报", limit=5)
        except CaptchaRequiredError:
            pytest.skip("搜狗触发验证码保护，跳过网络依赖测试")
        if not articles:
            pytest.skip("搜狗未返回文章（可能触发反爬虫保护），跳过网络依赖测试")
        assert isinstance(articles, list)
        assert len(articles) > 0
        first = articles[0]
        assert "title" in first
        assert "url" in first
        assert "publish_date" in first
