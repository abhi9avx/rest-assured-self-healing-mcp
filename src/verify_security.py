import os
import unittest
from unittest.mock import patch, MagicMock
from src.security_utils import SecurityUtils
from src.gemini_client import GeminiClient

class TestSecurityUtils(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            "GITHUB_TOKEN": "ghp_SECRET123",
            "GEMINI_API_KEY": "AIzaSy_SECRET456"
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_redact_text(self):
        text = "My GitHub token is ghp_SECRET123 and my Gemini key is AIzaSy_SECRET456."
        redacted = SecurityUtils.redact_text(text)
        expected = "My GitHub token is [REDACTED] and my Gemini key is [REDACTED]."
        self.assertEqual(redacted, expected)

    def test_safe_print(self):
        with patch('builtins.print') as mock_print:
            SecurityUtils.safe_print("Error: ghp_SECRET123 failed")
            mock_print.assert_called_with("Error: [REDACTED] failed")

    def test_gemini_client_url_security(self):
        client = GeminiClient(api_key="AIzaSy_SECRET456")
        # Ensure raw API key is NOT in the URL string
        self.assertNotIn("AIzaSy_SECRET456", client.api_url)
        self.assertTrue(client.api_url.startswith("https://generativelanguage.googleapis.com"))

if __name__ == '__main__':
    unittest.main()
