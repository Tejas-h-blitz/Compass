import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.search.recommend import get_smart_recommendations

class TestRecommendations(unittest.TestCase):
    def test_smart_recommendations(self):
        recs = get_smart_recommendations(limit=4)
        self.assertIsInstance(recs, list)
        for r in recs:
            self.assertIn("filepath", r)
            self.assertIn("filename", r)
            self.assertIn("reason", r)
            self.assertIn("badge", r)
            self.assertIn("score", r)

if __name__ == "__main__":
    unittest.main()
