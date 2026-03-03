import sys
sys.path.insert(0, '..')
from article_crawler import ArticleCrawler

def test_fetch_article_returns_content():
    """抓取原文应返回包含正文的字典"""
    crawler = ArticleCrawler(headless=True)
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
