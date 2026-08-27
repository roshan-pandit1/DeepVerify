"""
test_osint_threat.py — Unit test runner for OSINT Vision & Threat Restriction modules.
"""
import os
import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from pipeline.osint_vision import extract_keyframes, reverse_image_search
from pipeline.threat_restriction import calculate_panic_index, evaluate_context_mismatch


class TestOSINTVision(unittest.TestCase):

    def test_extract_keyframes_non_existent(self):
        result = extract_keyframes("non_existent_video.mp4")
        self.assertEqual(result, [])

    def test_reverse_image_search_fallback(self):
        # Should gracefully return error or empty lists without throwing an unhandled exception
        result = reverse_image_search("non_existent_frame.jpg")
        self.assertIn("best_guess_labels", result)
        self.assertIn("pages_with_matching_images", result)
        self.assertIsInstance(result["best_guess_labels"], list)
        self.assertIsInstance(result["pages_with_matching_images"], list)


class TestThreatRestriction(unittest.TestCase):

    def test_calculate_panic_index_high_risk(self):
        claim = "BREAKING: Military riot and violence at border invasion!"
        score = calculate_panic_index(claim, virality_speed=100.0)
        self.assertGreater(score, 80.0)
        self.assertLessEqual(score, 100.0)

    def test_calculate_panic_index_low_risk(self):
        claim = "Cute cats playing in a garden."
        score = calculate_panic_index(claim, virality_speed=0.0)
        self.assertLess(score, 80.0)
        self.assertGreaterEqual(score, 1.0)

    def test_evaluate_context_mismatch_empty(self):
        result = evaluate_context_mismatch("", [])
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
