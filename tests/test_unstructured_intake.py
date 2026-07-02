import tempfile
import unittest
from pathlib import Path

from underwriting_system import unstructured
from underwriting_system.database import UnderwritingRepository
from underwriting_system.schemas import UnstructuredReviewRequest
from underwriting_system.unstructured import LocalKeyValueExtractor
from underwriting_system.workflow import ModelRuntime, UnderwritingWorkflow


class FailingExtractor:
    def extract(self, raw_text, original_filename):
        raise RuntimeError("extractor offline")


def _service(testcase, extractor=None):
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    old_upload_dir = unstructured.UPLOAD_DIR
    unstructured.UPLOAD_DIR = Path(tmp.name) / "uploads"
    testcase.addCleanup(lambda: setattr(unstructured, "UPLOAD_DIR", old_upload_dir))
    repo = UnderwritingRepository(Path(tmp.name) / "underwriting.db")
    return UnderwritingWorkflow(repo, ModelRuntime(rows=250, seed=21), extractor or LocalKeyValueExtractor())


class UnstructuredIntakeTests(unittest.TestCase):
    def test_csv_upload_extract_and_hitl_approval_creates_application(self):
        service = _service(self)
        content = (
            b"applicant_name,national_id_or_cr,lob,region,exposure_value_sar,limit_sar,deductible_sar,risk_controls\n"
            b"Acme Logistics,CR12345,Motor,Riyadh,120000,1000000,2500,88\n"
            b"Red Sea Build,CR55555,Engineering & Construction,NEOM/Red Sea,900000000,650000000,1500000,75\n"
        )
        records = service.upload_unstructured_file("quotes.csv", "text/csv", content)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["status"], "uploaded")
        self.assertTrue(Path(records[0]["storage_path"]).exists())

        extracted = service.extract_unstructured(records[0]["id"])
        self.assertEqual(extracted["status"], "needs_review")
        application_payload = extracted["extraction"]["application"]
        self.assertEqual(application_payload["applicant"]["name"], "Acme Logistics")
        self.assertEqual(extracted["field_confidence"]["applicant.name"]["confidence"], "high")

        result = service.review_unstructured(
            extracted["id"],
            UnstructuredReviewRequest(action="approve", reviewer="demo.underwriter", notes="Approved", application=application_payload),
        )
        self.assertEqual(result["record"]["status"], "application_created")
        self.assertTrue(result["record"]["application_id"].startswith("APP-"))
        self.assertEqual(result["application"]["status"], "submitted")
        self.assertEqual(result["application"]["requested_coverages"]["unstructured_record_id"], extracted["id"])

    def test_extraction_failure_is_returned_as_failed_record(self):
        service = _service(self, FailingExtractor())
        records = service.upload_unstructured_file(
            "quote.csv",
            "text/csv",
            (
                b"applicant_name,national_id_or_cr,lob,region,exposure_value_sar,limit_sar,deductible_sar\n"
                b"Acme,CR1,Motor,Riyadh,100000,500000,1000\n"
            ),
        )
        failed = service.extract_unstructured(records[0]["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertIn("extractor offline", failed["error_message"])

    def test_pdf_quote_missing_cr_and_exposure_can_be_approved_after_repair(self):
        service = _service(self)
        raw_text = """Page 1
Chubb Arabia Underwriting Quote
Quote Summary
Application
APP-1A2E608E61
Applicant
Live Demo Motors
Line of business
Motor
Region
Riyadh
Coverage limit
SAR 1,000,000
Deductible
SAR 2,500
Term
12 months
"""
        record = service.repo.create_unstructured_record(
            "URI-PDFREPAIR",
            {
                "status": "needs_review",
                "original_filename": "quote.pdf",
                "content_type": "application/pdf",
                "file_extension": ".pdf",
                "storage_path": str(Path("/tmp/quote.pdf")),
                "raw_text": raw_text,
                "raw_preview": {"kind": "pdf", "text": raw_text, "page_count": 1},
                "extraction": {
                    "application": {
                        "channel": "manual",
                        "submitted_by": "unstructured.intake",
                        "role": "agent",
                        "applicant": {
                            "name": "Live Demo Motors",
                            "applicant_type": "company",
                            "national_id_or_cr": "",
                            "email": "",
                            "phone": "",
                        },
                        "policy": {
                            "lob": "Motor",
                            "region": "Riyadh",
                            "counterparty_rating": "Unrated",
                            "exposure_value_sar": 0,
                            "limit_sar": 1000000,
                            "deductible_sar": 2500,
                            "term_months": 12,
                            "prior_claims_3y": 0,
                            "risk_control_score": 38,
                            "reinsurance_ceded_pct": 0.0,
                            "event_accumulation_score": 0.0,
                        },
                        "requested_coverages": {"source": "unstructured_intake"},
                    }
                },
                "field_confidence": {},
                "source_evidence": {},
                "missing_fields": ["applicant.national_id_or_cr", "policy.exposure_value_sar"],
                "warnings": [],
            },
        )

        result = service.review_unstructured(
            record["id"],
            UnstructuredReviewRequest(
                action="approve",
                reviewer="demo.underwriter",
                notes="Approved after HITL repair",
                application=record["extraction"]["application"],
            ),
        )

        self.assertEqual(result["record"]["status"], "application_created")
        self.assertEqual(result["application"]["applicant"]["national_id_or_cr"], "APP-1A2E608E61")
        self.assertEqual(result["application"]["policy"]["exposure_value_sar"], 1000000)


if __name__ == "__main__":
    unittest.main()
