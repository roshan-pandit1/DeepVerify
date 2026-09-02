"""
test_social_context.py — Unit & Integration tests for Social Context & Crowd OSINT Layer.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from pipeline.social_context import fetch_comments, filter_bot_noise, analyze_crowd_consensus


class TestSocialContext(unittest.TestCase):

    def test_fetch_comments(self):
        url = "https://youtube.com/watch?v=panic_test"
        comments = fetch_comments(url, max_comments=50)
        self.assertIsInstance(comments, list)
        self.assertLessEqual(len(comments), 50)
        self.assertTrue(any("evacuate" in c.lower() or "military" in c.lower() for c in comments))

    def test_filter_bot_noise(self):
        raw_comments = [
            "This clip is fake! It is from the 2018 movie CGI sequence.",
            "This clip is fake! It is from the 2018 movie CGI sequence.",  # Exact duplicate
            "THIS CLIP IS FAKE! IT IS FROM THE 2018 MOVIE CGI SEQUENCE.",  # Case-insensitive duplicate
            "   ",  # Whitespace only
            "hi",  # Too short (< 3 chars)
            "First!",  # Bot spam
            "dm me for promo",  # Bot spam
            "Check link in bio to earn $5000 fast",  # Bot spam
            "Follow me back guys",  # Bot spam
            "Guys this was debunked years ago.",  # Valid comment
        ]

        cleaned = filter_bot_noise(raw_comments)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(cleaned[0], "This clip is fake! It is from the 2018 movie CGI sequence.")
        self.assertEqual(cleaned[1], "Guys this was debunked years ago.")

    def test_analyze_crowd_consensus_empty(self):
        result = analyze_crowd_consensus([])
        self.assertEqual(result["debunk_consensus"], 0.5)
        self.assertEqual(result["societal_panic_index"], 0)
        self.assertEqual(result["extracted_claims"], [])
        self.assertIsNone(result["error"])

    @patch("config.get_settings")
    def test_analyze_crowd_consensus_timeout_or_error_fallback(self, mock_settings):
        # Mock settings to throw exception simulating missing/failing credentials or network failure
        mock_settings.side_effect = Exception("Network connection timeout")

        clean_comments = ["Fake clip from 2019", "CGI confirmed"]
        result = analyze_crowd_consensus(clean_comments)

        # Must gracefully return neutral 0.5 score and not crash
        self.assertEqual(result["debunk_consensus"], 0.5)
        self.assertEqual(result["societal_panic_index"], 0)
        self.assertEqual(result["extracted_claims"], [])
        self.assertIsNotNone(result["error"])

    def test_priority_threat_routing_logic(self):
        # Check pre-triage routing thresholds
        debunk_high = 0.90
        panic_low = 20
        is_priority_1 = (debunk_high > 0.85 or panic_low > 75)
        self.assertTrue(is_priority_1)

        debunk_low = 0.20
        panic_high = 85
        is_priority_2 = (debunk_low > 0.85 or panic_high > 75)
        self.assertTrue(is_priority_2)

        debunk_mid = 0.50
        panic_mid = 30
        is_priority_3 = (debunk_mid > 0.85 or panic_mid > 75)
        self.assertFalse(is_priority_3)


if __name__ == "__main__":
    unittest.main()
