import json
from pathlib import Path
import os 
from datetime import datetime, timezone, timedelta
# Simple Cache Implementation using JSON
class NotificationCache:
    def __init__(self, cache_file="notification_cache.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)

    def has_been_sent(self, assignment_id, window):
        cache_key = f"{assignment_id}_{window}"
        return cache_key in self.cache

    def mark_as_sent(self, assignment_id, window):
        cache_key = f"{assignment_id}_{window}"
        self.cache[cache_key] = datetime.now().isoformat()
        self._save_cache()

    def clean_old_entries(self, days=7):
        now = datetime.now()
        self.cache = {
            k: v for k, v in self.cache.items()
            if (now - datetime.fromisoformat(v)).days < days
        }
        self._save_cache()