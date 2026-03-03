# main.py
from __future__ import annotations
import argparse
import sys
import requests
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
    args = parser.parse_args()

    print(f"[→] 目标公众号: {args.account}")
    print(f"[→] 最多抓取: {args.limit} 篇")

    # 阶段1：搜狗抓文章列表
    print("\n[阶段1] 搜狗微信：抓取文章列表...")
    sogou = SogouCrawler()
    try:
        articles = sogou.get_article_list(args.account, limit=args.limit)
    except CaptchaRequiredError as e:
        print(f"[!] {e}")
        print("[!] 请在浏览器访问 https://weixin.sogou.com 完成验证后重新运行")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"[!] 网络请求失败: {e}")
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
