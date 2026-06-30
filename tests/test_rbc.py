import unittest

from insurance_model.config import DEFAULT_MODULE_CORRELATIONS
from insurance_model.rbc import aggregate_capital, calculate_policy_scr


class RbcTests(unittest.TestCase):
    def test_diversified_capital_is_not_simple_sum_with_proxy_correlations(self):
        modules = {"underwriting": 100.0, "catastrophe": 60.0, "market_credit": 40.0}
        scr = aggregate_capital(modules)

        self.assertGreater(scr, max(modules.values()))
        self.assertLess(scr, sum(modules.values()))

    def test_perfect_correlation_equals_standalone_sum(self):
        modules = {"underwriting": 100.0, "catastrophe": 60.0, "market_credit": 40.0}
        perfect = {
            left: {right: 1.0 for right in DEFAULT_MODULE_CORRELATIONS}
            for left in DEFAULT_MODULE_CORRELATIONS
        }
        scr = aggregate_capital(modules, perfect)

        self.assertAlmostEqual(scr, sum(modules.values()), places=6)

    def test_policy_scr_has_expected_modules(self):
        policy = {
            "lob": "Property & Fire",
            "region": "Jeddah",
            "exposure_value_sar": 100_000_000,
            "limit_sar": 80_000_000,
            "deductible_sar": 100_000,
            "risk_control_score": 70,
            "event_accumulation_score": 0.45,
        }
        result = calculate_policy_scr(policy, premium_sar=250_000, expected_loss_sar=150_000)

        self.assertEqual(
            set(result["module_capitals"]),
            {"underwriting", "catastrophe", "market_credit"},
        )
        self.assertGreater(result["diversified_scr_sar"], 0)
        self.assertGreaterEqual(result["diversification_benefit_sar"], 0)


if __name__ == "__main__":
    unittest.main()

