import unittest

from underwriting_system.api import config, health


class UnderwritingApiTests(unittest.TestCase):
    def test_health_and_config(self):
        self.assertEqual(health(), {"status": "ok"})
        payload = config()["data"]
        self.assertIn("Motor", payload["lobs"])
        self.assertIn("Riyadh", payload["regions"])
        self.assertIn("agent", payload["roles"])


if __name__ == "__main__":
    unittest.main()
