import unittest

from insurance_model.config import LOBS
from insurance_model.simulation import REQUIRED_METADATA_COLUMNS, generate_simulation_bundle, metadata_coverage


class SimulationTests(unittest.TestCase):
    def test_bundle_has_required_tables_and_metadata(self):
        bundle = generate_simulation_bundle(rows=500, seed=21, scenario_name="Severe Flood Year")

        expected_tables = {
            "policies",
            "premiums",
            "exposures",
            "claims",
            "reinsurance",
            "economic_indices",
            "traffic_events",
            "weather_events",
            "cat_events",
            "market_curves",
            "rbc_factors",
        }
        self.assertEqual(expected_tables, set(bundle))
        self.assertEqual(set(LOBS), set(bundle["policies"]["lob"].unique()))
        for table in bundle.values():
            for column in REQUIRED_METADATA_COLUMNS:
                self.assertIn(column, table.columns)

        coverage = metadata_coverage(bundle)
        self.assertTrue(coverage["has_required_metadata"].all())


if __name__ == "__main__":
    unittest.main()
