"""
test_pipeline_restriction.py — End-to-end integration test for Threat Restriction & OSINT Vision pipeline integration.
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from pipeline import osint_vision, threat_restriction


class TestPipelineRestrictionIntegration(unittest.TestCase):

    def test_panic_index_threshold(self):
        # Claim with military, riot, border -> panic index should be > 80 when virality speed is high
        claim = "BREAKING: Military riot and armed violence at border invasion!"
        panic = threat_restriction.calculate_panic_index(claim, virality_speed=100.0)
        self.assertGreater(panic, 80.0)

    @patch("pipeline.threat_restriction.evaluate_context_mismatch")
    def test_restriction_trigger_logic(self, mock_mismatch):
        mock_mismatch.return_value = True

        claim = "BREAKING: Military riot and violence at border invasion!"
        panic = threat_restriction.calculate_panic_index(claim, virality_speed=100.0)
        mismatch = threat_restriction.evaluate_context_mismatch(claim, ["Thai festival 2022"])

        self.assertTrue(mismatch)
        self.assertGreater(panic, 80.0)

        if mismatch and panic > 80:
            status = "RESTRICTED - High Impact Misinformation"
        else:
            status = "CLEARED"

        self.assertEqual(status, "RESTRICTED - High Impact Misinformation")

    def test_cleared_logic(self):
        claim = "Peaceful morning walk in the park."
        panic = threat_restriction.calculate_panic_index(claim, virality_speed=5.0)
        mismatch = threat_restriction.evaluate_context_mismatch(claim, ["Park", "Nature"])

        if mismatch and panic > 80:
            status = "RESTRICTED - High Impact Misinformation"
        else:
            status = "CLEARED"

        self.assertEqual(status, "CLEARED")


if __name__ == "__main__":
    unittest.main()
