import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.scanner.scanner import is_path_security_blacklisted, sanitize_content
from backend.models.db import add_monitored_path, get_monitored_paths, remove_monitored_path

class TestSecurityAndHorizons(unittest.TestCase):
    def test_blacklist_paths(self):
        self.assertTrue(is_path_security_blacklisted("C:/Users/tejas/.ssh/id_rsa"))
        self.assertTrue(is_path_security_blacklisted("C:/Users/tejas/.aws/credentials"))
        self.assertTrue(is_path_security_blacklisted("D:/project/.env"))
        self.assertTrue(is_path_security_blacklisted("D:/project/secret.key"))
        self.assertTrue(is_path_security_blacklisted("D:/project/cert.pem"))
        self.assertTrue(is_path_security_blacklisted("C:/Windows/System32/calc.exe"))
        self.assertTrue(is_path_security_blacklisted("C:/Users/tejas/AppData/Local/file.txt"))
        self.assertTrue(is_path_security_blacklisted("D:/project/node_modules/package.json"))
        
        # Valid files should NOT be blacklisted
        self.assertFalse(is_path_security_blacklisted("D:/projects/ml_model.py"))
        self.assertFalse(is_path_security_blacklisted("C:/Users/tejas/Documents/resume.pdf"))
        self.assertFalse(is_path_security_blacklisted("D:/compass/data/test_corpus/doc1_python_intro.txt"))

    def test_content_sanitizer(self):
        text = 'Here is an OpenAI key: sk-abcdef1234567890abcdef123456 and password = "mysecretpassword123"'
        sanitized = sanitize_content(text)
        self.assertNotIn("sk-abcdef1234567890abcdef123456", sanitized)
        self.assertIn("[REDACTED_API_KEY]", sanitized)
        self.assertNotIn("mysecretpassword123", sanitized)
        self.assertIn("[REDACTED_SECRET]", sanitized)

    def test_monitored_horizons_crud(self):
        test_path = os.path.abspath("D:/compass/data/test_corpus")
        added = add_monitored_path(test_path, "Test Corpus Horizon")
        horizons = get_monitored_paths()
        found = any(h["path"] == test_path for h in horizons)
        self.assertTrue(found)

if __name__ == "__main__":
    unittest.main()
