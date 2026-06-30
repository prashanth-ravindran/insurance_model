import unittest

from insurance_model.actuarial import build_reserving_analysis, train_actuarial_models
from insurance_model.simulation import generate_simulation_bundle


class ActuarialTests(unittest.TestCase):
    def test_glm_and_reserving_outputs_are_positive(self):
        bundle = generate_simulation_bundle(rows=700, seed=14)
        actuarial = train_actuarial_models(bundle)
        reserving = build_reserving_analysis(bundle)

        self.assertIn("Poisson GLM frequency", set(actuarial["diagnostics"]["model"]))
        self.assertTrue((actuarial["indications"]["glm_expected_loss_sar"] >= 0).all())
        self.assertFalse(reserving["reserve_summary"].empty)
        self.assertTrue((reserving["reserve_summary"]["selected_reserve_sar"] >= 0).all())
        self.assertFalse(reserving["paid_triangle"].empty)


if __name__ == "__main__":
    unittest.main()
