from __future__ import annotations
import json
import os

class ProgressTracker:
    def __init__(self, path: str = "progress.json"):
        self.path = path
        self._done: set[str] = set()
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return
                data = json.loads(content)
                self._done = set(data.get("done", []))

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"done": list(self._done)}, f, indent=2)

    def mark_done(self, url: str):
        self._done.add(url)
        self._save()

    def is_done(self, url: str) -> bool:
        return url in self._done

    def count(self) -> int:
        return len(self._done)
