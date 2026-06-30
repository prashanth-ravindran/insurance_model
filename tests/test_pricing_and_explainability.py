import unittest

from insurance_model.actuarial import train_actuarial_models
from insurance_model.explainability import explain_policy_prediction
from insurance_model.model import train_ml_models
from insurance_model.pricing import price_policy
from insurance_model.simulation import generate_simulation_bundle


class PricingAndExplainabilityTests(unittest.TestCase):
    def test_pricing_reconciles_glm_ml_and_selected_view(self):
        bundle = generate_simulation_bundle(rows=650, seed=44)
        actuarial = train_actuarial_models(bundle)
        ml = train_ml_models(bundle["policies"], random_state=44)
        policy = bundle["policies"].iloc[0].to_dict()

        quote = price_policy(policy, model_bundle=ml, actuarial_bundle=actuarial)
        explanation = explain_policy_prediction(policy, ml, bundle["policies"], max_features=5)

        self.assertIn("actuarial_glm", quote["indications"])
        self.assertIn("ml", quote["indications"])
        self.assertGreaterEqual(len(quote["pricing_reconciliation"]), 3)
        self.assertEqual(explanation["method"], "SHAP TreeExplainer")
        self.assertFalse(explanation["top_features"].empty)


if __name__ == "__main__":
    unittest.main()
