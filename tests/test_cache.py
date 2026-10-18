import json
from pathlib import Path
import unittest

from src.storage.cache import CacheManager


class CacheManagerTests(unittest.TestCase):
    def test_cache_save_and_get(self) -> None:
        metadata = Path(__file__).parent / ".test-metadata.json"
        try:
            metadata.write_text(json.dumps({"tracks": {}}), encoding="utf-8")
            cache = CacheManager(metadata)
            cache.save("track-1", {"title": "Prueba", "artist": "KTO"})

            self.assertEqual(cache.get("track-1")["title"], "Prueba")
        finally:
            metadata.unlink(missing_ok=True)
