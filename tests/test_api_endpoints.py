import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.main import app

class TestApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_recommendations_endpoint(self):
        response = self.client.get("/api/recommendations")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("recommendations", data)

    def test_horizons_endpoints(self):
        # 1. Get horizons
        res_get = self.client.get("/api/horizons")
        self.assertEqual(res_get.status_code, 200)
        
        # 2. Security restriction: try adding a blacklisted path (like .ssh)
        res_bad = self.client.post("/api/horizons", json={"path": "C:/Users/tejas/.ssh"})
        # Should fail with 400
        self.assertEqual(res_bad.status_code, 400)

if __name__ == "__main__":
    unittest.main()
