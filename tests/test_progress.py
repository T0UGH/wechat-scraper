import sys, os, json, tempfile
sys.path.insert(0, '..')
from progress import ProgressTracker

def test_progress_tracker_saves_and_loads():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        tracker = ProgressTracker(path)
        tracker.mark_done("https://mp.weixin.qq.com/s/abc")
        assert tracker.is_done("https://mp.weixin.qq.com/s/abc")
        assert not tracker.is_done("https://mp.weixin.qq.com/s/xyz")

        # 重新加载，验证持久化
        tracker2 = ProgressTracker(path)
        assert tracker2.is_done("https://mp.weixin.qq.com/s/abc")
    finally:
        os.unlink(path)
