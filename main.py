# main.py
from __future__ import annotations
import argparse
import sys
from sogou_crawler import SogouCrawler, CaptchaRequiredError
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
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口（遇到验证码时使用）")
    args = parser.parse_args()

    headless = not args.no_headless

    print(f"[→] 目标公众号: {args.account}")
    print(f"[→] 最多抓取: {args.limit} 篇")
    if not headless:
        print("[→] 浏览器模式：可见窗口")

    # 阶段1：搜狗抓文章列表
    print("\n[阶段1] 搜狗微信：抓取文章列表...")
    try:
        with SogouCrawler(headless=headless) as sogou:
            articles = sogou.get_article_list(
                args.account,
                limit=args.limit,
                resolve_urls=not args.no_content,
            )
    except CaptchaRequiredError as e:
        print(f"[!] {e}")
        print("[!] 提示：加 --no-headless 参数以显示浏览器窗口，手动通过验证码后继续")
        sys.exit(1)
    except Exception as e:
        print(f"[!] 抓取文章列表失败: {e}")
        sys.exit(1)
    print(f"[✓] 共获取 {len(articles)} 篇文章元数据")

    if not articles:
        print("[!] 未找到文章，请检查公众号名称是否正确")
        sys.exit(1)

    # 阶段2：Playwright 抓原文
    if not args.no_content:
        print("\n[阶段2] Playwright：抓取原文内容...")
        progress = ProgressTracker(f"./progress_{args.account}.json") if args.resume else None
        with ArticleCrawler(headless=True) as crawler:
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
        print("[✓] 原文抓取完成")

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
