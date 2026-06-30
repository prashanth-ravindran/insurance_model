import unittest

from insurance_model.actuarial import build_reserving_analysis
from insurance_model.capital import FULL_RISK_MODULES, calculate_full_scr
from insurance_model.simulation import generate_simulation_bundle


class FullCapitalTests(unittest.TestCase):
    def test_expanded_scr_has_all_modules_and_diversification(self):
        bundle = generate_simulation_bundle(rows=600, seed=31)
        reserving = build_reserving_analysis(bundle)
        capital = calculate_full_scr(bundle, reserving)

        self.assertEqual(set(FULL_RISK_MODULES), set(capital["module_capitals"]))
        self.assertGreater(capital["diversified_scr_sar"], 0)
        self.assertGreater(capital["standalone_sum_sar"], capital["diversified_scr_sar"])
        self.assertGreaterEqual(capital["diversification_benefit_sar"], 0)


if __name__ == "__main__":
    unittest.main()
