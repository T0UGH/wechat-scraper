import sys
import pytest
sys.path.insert(0, '..')
from sogou_crawler import SogouCrawler

def test_search_account_returns_fakeid():
    """搜索公众号应返回包含 fakeid 的结果

    网络依赖测试：搜狗微信搜索会对爬虫进行反爬虫保护（JS 动态渲染、验证码等），
    在无真实浏览器的环境下可能无法获取结果。若 result 为 None 则跳过。
    """
    crawler = SogouCrawler()
    result = crawler.search_account("人民日报")
    if result is None:
        pytest.skip(
            "搜狗返回空结果（可能触发反爬虫保护或 JS 动态渲染限制），跳过网络依赖测试"
        )
    assert result is not None
    assert "fakeid" in result
    assert len(result["fakeid"]) > 0
    assert "name" in result


def test_get_article_list_returns_articles():
    """抓取文章列表应返回包含必要字段的列表"""
    crawler = SogouCrawler()
    articles = crawler.get_article_list("人民日报", limit=5)
    if not articles:
        pytest.skip("搜狗未返回文章（可能触发反爬虫保护），跳过网络依赖测试")
    assert isinstance(articles, list)
    assert len(articles) > 0
    first = articles[0]
    assert "title" in first
    assert "url" in first
    assert "publish_date" in first
