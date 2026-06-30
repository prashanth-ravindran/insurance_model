import unittest

from insurance_model.model import predict_policy, train_models
from insurance_model.data import generate_portfolio_data


class ModelTests(unittest.TestCase):
    def test_train_and_predict_policy(self):
        df = generate_portfolio_data(rows=650, seed=11)
        bundle = train_models(df, random_state=11)
        prediction = predict_policy(df.iloc[0].to_dict(), bundle)

        self.assertIn("frequency_auc", bundle["diagnostics"])
        self.assertGreaterEqual(prediction["claim_probability"], 0.0)
        self.assertLessEqual(prediction["claim_probability"], 1.0)
        self.assertGreaterEqual(prediction["expected_loss_sar"], 0.0)


if __name__ == "__main__":
    unittest.main()

