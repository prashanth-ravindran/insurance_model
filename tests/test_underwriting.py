import unittest

from insurance_model.underwriting import business_rule_descriptions, quote_policy


class UnderwritingTests(unittest.TestCase):
    def test_low_risk_motor_quote_has_premium_and_reasons(self):
        result = quote_policy(
            {
                "lob": "Motor",
                "region": "Riyadh",
                "policy_type": "Comprehensive",
                "vehicle_class": "Private car",
                "driver_age": 42,
                "vehicle_age": 2,
                "fleet_size": 1,
                "exposure_value_sar": 95_000,
                "limit_sar": 1_000_000,
                "deductible_sar": 2_500,
                "risk_control_score": 88,
                "prior_claims_3y": 0,
                "event_accumulation_score": 0.08,
                "reinsurance_ceded_pct": 0.10,
            }
        )

        self.assertEqual(result["decision"], "quote")
        self.assertIsNotNone(result["recommended_premium_sar"])
        self.assertGreater(result["technical_premium_sar"], result["expected_loss_sar"])
        self.assertGreater(result["scr_impact_sar"], 0)
        self.assertTrue(result["decision_reasons"])
        self.assertIn("decision_explanation", result)
        self.assertTrue(result["decision_explanation"]["rule_evaluations"])

    def test_limit_outside_appetite_declines(self):
        result = quote_policy(
            {
                "lob": "Engineering & Construction",
                "region": "Jubail/Yanbu",
                "project_type": "Giga-project package",
                "project_complexity_score": 0.95,
                "project_duration_months": 60,
                "contractor_experience_years": 2,
                "exposure_value_sar": 18_000_000_000,
                "limit_sar": 13_000_000_000,
                "deductible_sar": 10_000_000,
                "risk_control_score": 20,
                "event_accumulation_score": 0.95,
                "reinsurance_ceded_pct": 0.75,
            }
        )

        self.assertEqual(result["decision"], "decline")
        self.assertIsNone(result["recommended_premium_sar"])
        self.assertGreater(result["technical_premium_sar"], 0)

        explanation = result["decision_explanation"]
        self.assertTrue(any("above appetite" in item for item in explanation["drivers"]))
        self.assertTrue(any("Reduce the requested gross limit" in item for item in explanation["recommended_actions"]))
        self.assertTrue(
            any(
                row["Rule"] == "LOB appetite limit" and row["Status"] == "Decline trigger"
                for row in explanation["rule_evaluations"]
            )
        )

    def test_business_rules_are_available_as_natural_language(self):
        rules = business_rule_descriptions()

        self.assertGreaterEqual(len(rules), 5)
        self.assertTrue(all("Natural language" in rule for rule in rules))


if __name__ == "__main__":
    unittest.main()

