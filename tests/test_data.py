import unittest

from insurance_model.config import LOBS
from insurance_model.data import generate_portfolio_data


class DataTests(unittest.TestCase):
    def test_generates_all_lobs_and_required_targets(self):
        df = generate_portfolio_data(rows=1000, seed=7)

        self.assertEqual(set(LOBS), set(df["lob"].unique()))
        self.assertTrue((df["exposure_value_sar"] > 0).all())
        self.assertTrue((df["limit_sar"] > 0).all())
        self.assertTrue(df["had_claim"].isin([0, 1]).all())
        self.assertTrue((df["expected_loss_sar"] >= 0).all())
        self.assertTrue((df["technical_premium_sar"] > 0).all())


if __name__ == "__main__":
    unittest.main()

