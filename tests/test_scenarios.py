import unittest

from insurance_model.scenarios import scenario_comparison


class ScenarioTests(unittest.TestCase):
    def test_scenario_comparison_changes_capital(self):
        comparison = scenario_comparison(rows=500, seed=52, scenario_names=["Base", "Severe Flood Year", "Interest Rate Shock"])

        self.assertEqual(["Base", "Severe Flood Year", "Interest Rate Shock"], comparison["scenario"].tolist())
        self.assertTrue((comparison["diversified_scr_sar"] > 0).all())
        self.assertNotEqual(
            float(comparison.loc[comparison["scenario"] == "Base", "diversified_scr_sar"].iloc[0]),
            float(comparison.loc[comparison["scenario"] == "Severe Flood Year", "diversified_scr_sar"].iloc[0]),
        )


if __name__ == "__main__":
    unittest.main()
