from __future__ import annotations
import hashlib
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
        """生成单篇文章的 Markdown 文件名（URL hash 保证唯一）"""
        date_prefix = ""
        pd = article.get("publish_date", "")
        if pd:
            date_prefix = pd[:10].replace("/", "-") + "-"

        title = article.get("title", "untitled")
        slug = re.sub(r'[^\w\u4e00-\u9fff-]', '', title)[:30]
        slug = slug.strip("-") or "article"

        # 用 URL 末8位 hash 保证文件名唯一
        url = article.get("url", "")
        suffix = hashlib.md5(url.encode()).hexdigest()[:8] if url else ""
        suffix_part = f"-{suffix}" if suffix else ""

        return os.path.join(output_dir, f"{date_prefix}{slug}{suffix_part}.md")

    def _yaml_escape(self, value: str) -> str:
        """对 YAML 字符串值做简单转义（包含特殊字符时加引号）"""
        if not value:
            return '""'
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

            fm_lines = [
                "---",
                f"title: {self._yaml_escape(article.get('title', ''))}",
                f"author: {self._yaml_escape(article.get('author', ''))}",
                f"publish_date: {self._yaml_escape(article.get('publish_date', ''))}",
                f"url: {self._yaml_escape(article.get('url', ''))}",
                f"digest: {self._yaml_escape(article.get('digest', ''))}",
                f"cover_url: {self._yaml_escape(article.get('cover_url', ''))}",
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
