import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from underwriting_system import api as api_module
from underwriting_system.api import config, health
from underwriting_system.database import UnderwritingRepository
from underwriting_system.schemas import ApplicationCreate, QuoteGenerateRequest
from underwriting_system.workflow import ModelRuntime, UnderwritingWorkflow


def _application():
    return ApplicationCreate(
        applicant={
            "name": "Acme Logistics",
            "applicant_type": "company",
            "national_id_or_cr": "CR12345",
            "email": "ops@example.com",
        },
        policy={
            "lob": "Motor",
            "region": "Riyadh",
            "counterparty_rating": "A",
            "exposure_value_sar": 120000,
            "limit_sar": 1000000,
            "deductible_sar": 2500,
            "term_months": 12,
            "prior_claims_3y": 0,
            "risk_control_score": 90,
            "reinsurance_ceded_pct": 0.1,
            "event_accumulation_score": 0.08,
            "policy_type": "Comprehensive",
            "vehicle_class": "Private car",
            "driver_age": 42,
            "vehicle_age": 2,
            "fleet_size": 1,
        },
    )


class UnderwritingApiTests(unittest.TestCase):
    def test_health_and_config(self):
        self.assertEqual(health(), {"status": "ok"})
        payload = config()["data"]
        self.assertIn("Motor", payload["lobs"])
        self.assertIn("Riyadh", payload["regions"])
        self.assertIn("agent", payload["roles"])

    def test_quote_pdf_response_is_inline_for_preview(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = UnderwritingRepository(Path(tmp.name) / "underwriting.db")
        service = UnderwritingWorkflow(repo, ModelRuntime(rows=250, seed=31))
        old_workflow = api_module.workflow
        api_module.workflow = service
        self.addCleanup(lambda: setattr(api_module, "workflow", old_workflow))

        case = service.create_application(_application())
        case = service.enrich(case["id"])
        case = service.underwrite(case["id"])
        case = service.generate_quote(case["id"], QuoteGenerateRequest(generated_by="demo.agent"))
        quote_id = case["latest_quote"]["id"]

        response = TestClient(api_module.app).get(f"/api/quotes/{quote_id}/pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.headers["content-disposition"].lower().startswith("inline;"))


if __name__ == "__main__":
    unittest.main()
