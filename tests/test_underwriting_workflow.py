import tempfile
import unittest
from pathlib import Path

from underwriting_system.database import UnderwritingRepository
from underwriting_system.schemas import ApplicationCreate, AssignmentRequest, BindRequest, QuoteGenerateRequest, ReviewDecisionRequest
from underwriting_system.workflow import ModelRuntime, UnderwritingWorkflow


def _service(testcase):
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    repo = UnderwritingRepository(Path(tmp.name) / "underwriting.db")
    return UnderwritingWorkflow(repo, ModelRuntime(rows=650, seed=13))


def _application(policy_overrides=None, applicant_overrides=None):
    policy = {
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
    }
    if policy_overrides:
        policy.update(policy_overrides)
    applicant = {
        "name": "Acme Logistics",
        "applicant_type": "company",
        "national_id_or_cr": "CR12345",
        "email": "ops@example.com",
    }
    if applicant_overrides:
        applicant.update(applicant_overrides)
    return ApplicationCreate(applicant=applicant, policy=policy)


class UnderwritingWorkflowTests(unittest.TestCase):
    def test_stp_quote_and_bind_lifecycle(self):
        service = _service(self)
        case = service.create_application(_application())
        case = service.enrich(case["id"])
        self.assertGreaterEqual(len(case["enrichments"]), 3)

        case = service.underwrite(case["id"])
        self.assertEqual(case["latest_decision"]["decision_bucket"], "stp")
        self.assertEqual(case["status"], "stp_quoted")
        self.assertGreater(case["latest_rating"]["adjusted_premium_sar"], 0)

        case = service.generate_quote(case["id"], QuoteGenerateRequest(generated_by="demo.agent"))
        self.assertEqual(case["status"], "quoted")
        self.assertTrue(Path(case["latest_quote"]["pdf_path"]).exists())

        case = service.bind(case["latest_quote"]["id"], BindRequest(bound_by="demo.agent"))
        self.assertEqual(case["status"], "bound")
        self.assertTrue(case["bound_policies"][-1]["policy_number"].startswith("POL-"))

    def test_requires_review_can_be_approved_and_quoted(self):
        service = _service(self)
        case = service.create_application(
            _application(
                {
                    "lob": "Engineering & Construction",
                    "region": "NEOM/Red Sea",
                    "exposure_value_sar": 1500000000,
                    "limit_sar": 950000000,
                    "deductible_sar": 2500000,
                    "risk_control_score": 68,
                    "reinsurance_ceded_pct": 0.55,
                    "event_accumulation_score": 0.62,
                    "policy_type": "CAR/EAR",
                    "project_type": "Giga-project package",
                    "project_complexity_score": 0.88,
                    "project_duration_months": 48,
                    "contractor_experience_years": 7,
                }
            )
        )
        case = service.underwrite(case["id"])
        self.assertEqual(case["status"], "requires_review")

        case = service.assign_review(case["id"], AssignmentRequest(assignee="demo.underwriter"))
        self.assertEqual(case["assigned_to"], "demo.underwriter")

        case = service.review_decision(
            case["id"],
            ReviewDecisionRequest(
                action="approve",
                underwriter="demo.underwriter",
                notes="Approved with flood sublimit and schedule adjustment.",
                premium_delta_pct=0.08,
                sublimits={"flood_sar": 120000000},
                exclusions=["Delay in start-up sublimit applies."],
            ),
        )
        self.assertEqual(case["status"], "underwriter_approved")
        case = service.generate_quote(case["id"], QuoteGenerateRequest(generated_by="demo.underwriter"))
        self.assertEqual(case["status"], "quoted")
        self.assertIn("Delay in start-up", case["latest_quote"]["exclusions"][0])

    def test_watchlist_pattern_auto_declines(self):
        service = _service(self)
        case = service.create_application(_application(applicant_overrides={"national_id_or_cr": "CR999"}))
        case = service.underwrite(case["id"])
        self.assertEqual(case["status"], "declined")
        self.assertEqual(case["latest_decision"]["decision_bucket"], "declined")


if __name__ == "__main__":
    unittest.main()
