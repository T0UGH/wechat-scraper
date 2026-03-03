# tests/test_exporter.py
import sys, os, json, tempfile
sys.path.insert(0, '..')
from exporter import Exporter

SAMPLE = [
    {
        "title": "测试文章标题",
        "url": "https://mp.weixin.qq.com/s/test",
        "publish_date": "2024-01-01",
        "digest": "摘要",
        "cover_url": "",
        "author": "作者",
        "content_text": "正文内容第一段。\n\n正文内容第二段。",
        "content_html": "<p>正文内容</p>",
        "read_count": "1000",
        "error": "",
    }
]

def test_export_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = Exporter(output_dir=tmpdir)
        path = exporter.export_json(SAMPLE, "test_account")
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["title"] == "测试文章标题"

def test_export_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = Exporter(output_dir=tmpdir)
        path = exporter.export_csv(SAMPLE, "test_account")
        assert os.path.exists(path)
        import csv
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["title"] == "测试文章标题"

def test_export_markdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = Exporter(output_dir=tmpdir)
        paths = exporter.export_markdown(SAMPLE, "test_account")
        assert len(paths) == 1
        assert os.path.exists(paths[0])
        content = open(paths[0], encoding="utf-8").read()
        # 验证 YAML front matter 存在
        assert content.startswith("---\n")
        assert "title: 测试文章标题" in content
        assert "author: 作者" in content
        assert "url: https://mp.weixin.qq.com/s/test" in content
        assert "account: test_account" in content
        assert "scraped_at:" in content
        # 验证正文在 front matter 之后
        parts = content.split("---\n", 2)
        assert len(parts) == 3  # ["", front_matter, body]
        assert "正文内容第一段" in parts[2]
