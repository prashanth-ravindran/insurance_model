"""Workflow orchestration for end-to-end underwriting."""

from __future__ import annotations

import copy
import math
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any

from insurance_model.actuarial import train_actuarial_models
from insurance_model.config import DECISION_THRESHOLDS, LOB_CONFIG, REGION_RISK
from insurance_model.model import train_ml_models
from insurance_model.pricing import price_policy
from insurance_model.simulation import generate_simulation_bundle
from underwriting_system.database import UnderwritingRepository, now_iso
from underwriting_system.enrichment import enrich_application, merge_enrichment_into_policy
from underwriting_system.pdf import generate_quote_pdf
from underwriting_system.schemas import (
    ApplicationCreate,
    ApplicationStatus,
    AssignmentRequest,
    BindRequest,
    DecisionBucket,
    PricingAdjustment,
    QuoteGenerateRequest,
    ReviewDecisionRequest,
    UnstructuredIntakeStatus,
    UnstructuredReviewRequest,
)
from underwriting_system.unstructured import (
    GeminiExtractionService,
    new_record_id,
    normalize_extraction,
    read_upload_records,
    validate_upload,
    write_upload,
)


class ModelRuntime:
    """Lazy model runtime for workflow pricing."""

    def __init__(self, rows: int = 2500, seed: int = 42):
        self.rows = rows
        self.seed = seed

    @cached_property
    def bundle(self):
        return generate_simulation_bundle(rows=self.rows, seed=self.seed, scenario_name="Base")

    @cached_property
    def ml(self):
        return train_ml_models(self.bundle["policies"], random_state=self.seed)

    @cached_property
    def actuarial(self):
        return train_actuarial_models(self.bundle)


def _round_money(value: float | None) -> float | None:
    if value is None:
        return None
    if value < 10_000:
        step = 50
    elif value < 250_000:
        step = 500
    elif value < 2_000_000:
        step = 2_500
    else:
        step = 10_000
    return float(math.ceil(float(value) / step) * step)


def _quote_number(prefix: str) -> str:
    today = datetime.now(UTC).strftime("%Y%m%d")
    return f"{prefix}-{today}-{uuid.uuid4().hex[:8].upper()}"


class UnderwritingWorkflow:
    """Service facade used by the FastAPI app and tests."""

    def __init__(
        self,
        repository: UnderwritingRepository | None = None,
        runtime: ModelRuntime | None = None,
        extractor: Any | None = None,
    ):
        self.repo = repository or UnderwritingRepository()
        rows = int(os.getenv("UNDERWRITING_MODEL_ROWS", "2500"))
        self.runtime = runtime or ModelRuntime(rows=rows, seed=42)
        self.extractor = extractor or GeminiExtractionService()

    def create_application(self, request: ApplicationCreate) -> dict[str, Any]:
        application_id = f"APP-{uuid.uuid4().hex[:10].upper()}"
        payload = request.model_dump(mode="json")
        return self.repo.create_application(application_id, payload, ApplicationStatus.SUBMITTED.value)

    def upload_unstructured_file(self, original_filename: str, content_type: str | None, content: bytes) -> list[dict[str, Any]]:
        suffix = validate_upload(original_filename, content)
        parent_record_id = new_record_id()
        path = write_upload(parent_record_id, original_filename, content)
        raw_records = read_upload_records(path, original_filename, content_type)
        stored_path = str(path)
        created_records = []
        for index, raw_record in enumerate(raw_records):
            record_id = parent_record_id if index == 0 else new_record_id()
            payload = {
                "parent_id": None if index == 0 else parent_record_id,
                "batch_index": raw_record.batch_index,
                "status": UnstructuredIntakeStatus.UPLOADED.value,
                "original_filename": original_filename,
                "content_type": content_type,
                "file_extension": suffix,
                "storage_path": stored_path,
                "raw_text": raw_record.raw_text,
                "raw_preview": raw_record.raw_preview,
                "extraction": {},
                "field_confidence": {},
                "source_evidence": {},
                "missing_fields": [],
                "warnings": [],
            }
            created_records.append(self.repo.create_unstructured_record(record_id, payload))
        return created_records

    def list_unstructured_records(self, status: str | None = None) -> list[dict[str, Any]]:
        return self.repo.list_unstructured_records(status)

    def get_unstructured_record(self, record_id: str) -> dict[str, Any]:
        return self.repo.get_unstructured_record(record_id)

    def extract_unstructured(self, record_id: str) -> dict[str, Any]:
        record = self.repo.get_unstructured_record(record_id)
        if record["status"] == UnstructuredIntakeStatus.APPLICATION_CREATED.value:
            raise ValueError("Extraction is already approved and converted to an application.")
        self.repo.update_unstructured_status(record_id, UnstructuredIntakeStatus.EXTRACTING.value)
        try:
            raw_result = self.extractor.extract(record["raw_text"], record["original_filename"])
            normalized = normalize_extraction(raw_result)
            return self.repo.update_unstructured_extraction(
                record_id,
                status=UnstructuredIntakeStatus.NEEDS_REVIEW.value,
                extraction=normalized["extraction"],
                field_confidence=normalized["field_confidence"],
                source_evidence=normalized["source_evidence"],
                missing_fields=normalized["missing_fields"],
                warnings=normalized["warnings"],
            )
        except Exception as exc:
            return self.repo.update_unstructured_extraction(
                record_id,
                status=UnstructuredIntakeStatus.FAILED.value,
                extraction=record.get("extraction", {}),
                field_confidence=record.get("field_confidence", {}),
                source_evidence=record.get("source_evidence", {}),
                missing_fields=record.get("missing_fields", []),
                warnings=record.get("warnings", []),
                error_message=str(exc),
            )

    def review_unstructured(self, record_id: str, request: UnstructuredReviewRequest) -> dict[str, Any]:
        record = self.repo.get_unstructured_record(record_id)
        if request.action == "reject":
            updated = self.repo.update_unstructured_review(
                record_id,
                status=UnstructuredIntakeStatus.REJECTED.value,
                reviewer=request.reviewer,
                notes=request.notes,
                reviewer_edits=None,
            )
            return {"record": updated, "application": None}
        if record["status"] != UnstructuredIntakeStatus.NEEDS_REVIEW.value:
            raise ValueError("Only needs-review extraction records can be approved.")
        assert request.application is not None
        application_payload = self._review_application_payload(record, request.application)
        requested_coverages = dict(application_payload.get("requested_coverages", {}))
        requested_coverages.update({"source": "unstructured_intake", "unstructured_record_id": record_id})
        application_payload["requested_coverages"] = requested_coverages
        application = ApplicationCreate.model_validate(application_payload)
        case = self.create_application(application)
        updated = self.repo.update_unstructured_review(
            record_id,
            status=UnstructuredIntakeStatus.APPLICATION_CREATED.value,
            reviewer=request.reviewer,
            notes=request.notes,
            reviewer_edits={"application": application_payload},
            application_id=case["id"],
        )
        return {"record": updated, "application": case}

    @staticmethod
    def _review_application_payload(record: dict[str, Any], application: dict[str, Any]) -> dict[str, Any]:
        payload = copy.deepcopy(application)
        extracted = record.get("extraction", {}).get("application", {})
        if extracted:
            base = copy.deepcopy(extracted)
            base.update({key: value for key, value in payload.items() if key not in {"applicant", "policy", "requested_coverages"}})
            base["applicant"] = {**base.get("applicant", {}), **payload.get("applicant", {})}
            base["policy"] = {**base.get("policy", {}), **payload.get("policy", {})}
            base["requested_coverages"] = {**base.get("requested_coverages", {}), **payload.get("requested_coverages", {})}
            payload = base

        payload.setdefault("channel", "manual")
        payload.setdefault("submitted_by", "unstructured.intake")
        payload.setdefault("role", "agent")
        applicant = payload.setdefault("applicant", {})
        policy = payload.setdefault("policy", {})
        raw_text = record.get("raw_text", "")

        if not str(applicant.get("name") or "").strip():
            applicant["name"] = Path(record.get("original_filename", "Uploaded record")).stem[:80] or "Uploaded record"
        if not str(applicant.get("applicant_type") or "").strip():
            applicant["applicant_type"] = "company"
        if len(str(applicant.get("national_id_or_cr") or "").strip()) < 4:
            source_id = UnderwritingWorkflow._source_document_id(raw_text, record.get("id", ""))
            applicant["national_id_or_cr"] = source_id

        policy.setdefault("lob", "Motor")
        policy.setdefault("region", "Riyadh")
        policy.setdefault("counterparty_rating", "A")
        limit = UnderwritingWorkflow._positive_float(policy.get("limit_sar"))
        exposure = UnderwritingWorkflow._positive_float(policy.get("exposure_value_sar"))
        if exposure <= 0:
            policy["exposure_value_sar"] = limit if limit > 0 else 120000
        if limit <= 0:
            policy["limit_sar"] = UnderwritingWorkflow._positive_float(policy.get("exposure_value_sar")) or 1000000
        if UnderwritingWorkflow._float_or_zero(policy.get("deductible_sar")) < 0:
            policy["deductible_sar"] = 0
        policy.setdefault("deductible_sar", 0)
        policy.setdefault("term_months", 12)
        policy.setdefault("prior_claims_3y", 0)
        policy.setdefault("risk_control_score", 70)
        policy.setdefault("reinsurance_ceded_pct", 0.0)
        policy.setdefault("event_accumulation_score", 0.0)
        return payload

    @staticmethod
    def _source_document_id(raw_text: str, record_id: str) -> str:
        match = re.search(r"\bAPP-[A-Z0-9]+\b", raw_text, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()
        return f"DOC-{str(record_id).replace('URI-', '')[:12] or 'UNSTRUCT'}"

    @staticmethod
    def _positive_float(value: Any) -> float:
        number = UnderwritingWorkflow._float_or_zero(value)
        return number if number > 0 else 0.0

    @staticmethod
    def _float_or_zero(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def enrich(self, application_id: str) -> dict[str, Any]:
        case = self.repo.get_case(application_id)
        responses = enrich_application(application_id, case["applicant"], case["policy"])
        for response in responses:
            self.repo.insert_enrichment(application_id, response)
        self.repo.update_status(application_id, ApplicationStatus.ENRICHED.value, "enrichment-service", {"providers": [r["provider"] for r in responses]})
        return self.repo.get_case(application_id)

    def underwrite(self, application_id: str) -> dict[str, Any]:
        case = self.repo.get_case(application_id)
        if not case["enrichments"]:
            case = self.enrich(application_id)

        enriched_policy = merge_enrichment_into_policy(case["policy"], case["enrichments"])
        quote = price_policy(enriched_policy, model_bundle=self.runtime.ml, actuarial_bundle=self.runtime.actuarial)
        flags = [flag for result in case["enrichments"] for flag in result.get("flags", [])]
        confidence = self._average_confidence(case["enrichments"])
        decision_bucket = self._decision_bucket(quote, flags, confidence, enriched_policy)
        rating = self._rating_result(quote, enriched_policy, flags)
        decision = {
            "decision_bucket": decision_bucket.value,
            "engine_decision": quote["decision"],
            "reasons": self._decision_reasons(quote, flags, confidence, decision_bucket),
            "recommended_actions": quote["decision_explanation"].get("recommended_actions", []),
            "rule_evaluations": quote["decision_explanation"].get("rule_evaluations", []),
            "enrichment_flags": flags,
        }

        self.repo.insert_decision(application_id, decision)
        self.repo.insert_rating(application_id, rating)
        next_status = {
            DecisionBucket.STP: ApplicationStatus.STP_QUOTED,
            DecisionBucket.REQUIRES_REVIEW: ApplicationStatus.REQUIRES_REVIEW,
            DecisionBucket.DECLINED: ApplicationStatus.DECLINED,
        }[decision_bucket]
        self.repo.update_status(application_id, next_status.value, "underwriting-engine", {"decision_bucket": decision_bucket.value})
        return self.repo.get_case(application_id)

    def assign_review(self, application_id: str, request: AssignmentRequest) -> dict[str, Any]:
        case = self.repo.get_case(application_id)
        if case["status"] != ApplicationStatus.REQUIRES_REVIEW.value:
            raise ValueError("Only requires-review applications can be assigned.")
        self.repo.assign(application_id, request.assignee)
        return self.repo.get_case(application_id)

    def review_decision(self, application_id: str, request: ReviewDecisionRequest) -> dict[str, Any]:
        case = self.repo.get_case(application_id)
        if case["status"] != ApplicationStatus.REQUIRES_REVIEW.value:
            raise ValueError("Only requires-review applications can receive an underwriter decision.")
        review = request.model_dump(mode="json")
        review["created_at"] = now_iso()
        self.repo.insert_review(application_id, review)
        status = ApplicationStatus.UNDERWRITER_APPROVED if request.action == "approve" else ApplicationStatus.UNDERWRITER_DECLINED
        self.repo.update_status(application_id, status.value, request.underwriter, {"action": request.action})
        return self.repo.get_case(application_id)

    def generate_quote(self, application_id: str, request: QuoteGenerateRequest) -> dict[str, Any]:
        case = self.repo.get_case(application_id)
        if case["status"] not in {ApplicationStatus.STP_QUOTED.value, ApplicationStatus.UNDERWRITER_APPROVED.value, ApplicationStatus.QUOTED.value}:
            raise ValueError("Application is not approved for quote generation.")
        rating = case.get("latest_rating") or {}
        if not rating.get("adjusted_premium_sar"):
            raise ValueError("No offered premium is available for this application.")
        review = case.get("latest_review") or {}
        premium = float(rating["adjusted_premium_sar"])
        if review and review.get("action") == "approve":
            premium *= 1.0 + float(review.get("premium_delta_pct", 0.0))
        premium = _round_money(premium)
        quote_id = _quote_number("QTE")
        expires_at = (datetime.now(UTC) + timedelta(days=request.expiry_days)).date().isoformat()
        quote = {
            "quote_id": quote_id,
            "quote_number": quote_id,
            "application_id": application_id,
            "premium_sar": premium,
            "decision_bucket": (case.get("latest_decision") or {}).get("decision_bucket"),
            "deductible_sar": review.get("deductible_sar") or case["policy"].get("deductible_sar"),
            "sublimits": review.get("sublimits", {}),
            "exclusions": review.get("exclusions", []) or ["Standard sanctions, fraud, and policy wording exclusions apply."],
            "expires_at": expires_at,
            "generated_by": request.generated_by,
            "created_at": now_iso(),
        }
        pdf_path = generate_quote_pdf(case, quote)
        quote["pdf_path"] = pdf_path
        self.repo.insert_quote(quote_id, application_id, quote)
        self.repo.update_status(application_id, ApplicationStatus.QUOTED.value, request.generated_by, {"quote_id": quote_id})
        return self.repo.get_case(application_id)

    def bind(self, quote_id: str, request: BindRequest) -> dict[str, Any]:
        if not request.accepted_terms:
            raise ValueError("accepted_terms must be true to bind.")
        case = self._case_by_quote(quote_id)
        if case["status"] not in {ApplicationStatus.QUOTED.value, ApplicationStatus.BOUND.value}:
            raise ValueError("Only quoted applications can be bound.")
        quote = next((quote for quote in case["quotes"] if quote["id"] == quote_id), None)
        if quote is None:
            raise KeyError(quote_id)
        policy_id = _quote_number("POL")
        bound = {
            "policy_number": policy_id,
            "quote_id": quote_id,
            "application_id": case["id"],
            "premium_sar": quote["premium_sar"],
            "bound_by": request.bound_by,
            "bound_at": now_iso(),
        }
        self.repo.insert_bound_policy(policy_id, quote_id, case["id"], bound)
        self.repo.update_status(case["id"], ApplicationStatus.BOUND.value, request.bound_by, {"policy_number": policy_id})
        return self.repo.get_case(case["id"])

    def get_case(self, application_id: str) -> dict[str, Any]:
        return self.repo.get_case(application_id)

    def list_cases(self, status: str | None = None) -> list[dict[str, Any]]:
        return self.repo.list_cases(status)

    def list_reviews(self, status: str | None = None) -> list[dict[str, Any]]:
        return self.repo.list_cases(status or ApplicationStatus.REQUIRES_REVIEW.value)

    def _case_by_quote(self, quote_id: str) -> dict[str, Any]:
        for case in self.repo.list_cases():
            if any(quote["id"] == quote_id for quote in case["quotes"]):
                return case
        raise KeyError(quote_id)

    @staticmethod
    def _average_confidence(enrichments: list[dict[str, Any]]) -> float:
        if not enrichments:
            return 0.0
        return sum(float(item.get("confidence", 0.0)) for item in enrichments) / len(enrichments)

    @staticmethod
    def _decision_bucket(quote: dict[str, Any], flags: list[dict[str, Any]], confidence: float, policy: dict[str, Any]) -> DecisionBucket:
        high_flags = [flag for flag in flags if flag.get("severity") == "high"]
        if quote["decision"] == "decline" or any(flag.get("code") == "identity_watchlist" for flag in flags):
            return DecisionBucket.DECLINED
        if quote["decision"] == "refer" or high_flags or confidence < 0.74:
            return DecisionBucket.REQUIRES_REVIEW
        if policy.get("lob") == "Engineering & Construction" and float(policy.get("project_complexity_score", 0.0)) > 0.78:
            return DecisionBucket.REQUIRES_REVIEW
        return DecisionBucket.STP

    @staticmethod
    def _decision_reasons(quote: dict[str, Any], flags: list[dict[str, Any]], confidence: float, bucket: DecisionBucket) -> list[str]:
        reasons = list(quote.get("decision_reasons", []))
        for flag in flags:
            if flag.get("severity") in {"medium", "high"}:
                reasons.append(flag.get("message", flag.get("label", "Enrichment flag")))
        if confidence < 0.74:
            reasons.append(f"Average enrichment confidence is low at {confidence:.0%}.")
        if bucket == DecisionBucket.STP and not reasons:
            reasons.append("Risk is eligible for straight-through processing.")
        return reasons

    @staticmethod
    def _rating_result(quote: dict[str, Any], policy: dict[str, Any], flags: list[dict[str, Any]]) -> dict[str, Any]:
        base_premium = quote.get("recommended_premium_sar")
        adjustments = []
        total_pct = 0.0
        base_for_amount = float(base_premium or quote.get("technical_premium_sar") or 0.0)

        def add(code: str, label: str, kind: str, pct: float, reason: str) -> None:
            nonlocal total_pct
            total_pct += pct
            adjustments.append(
                PricingAdjustment(
                    code=code,
                    label=label,
                    kind=kind,
                    pct=pct,
                    amount_sar=base_for_amount * pct,
                    reason=reason,
                ).model_dump()
            )

        controls = float(policy.get("risk_control_score", 70.0))
        deductible_ratio = float(policy.get("deductible_sar", 0.0)) / max(float(policy.get("limit_sar", 1.0)), 1.0)
        prior = int(float(policy.get("prior_claims_3y", 0)))
        accumulation = float(policy.get("event_accumulation_score", 0.25))
        high_flags = sum(1 for flag in flags if flag.get("severity") == "high")
        medium_flags = sum(1 for flag in flags if flag.get("severity") == "medium")

        if controls >= 85:
            add("strong_controls", "Strong controls", "discount", -0.05, "Risk controls are in the preferred range.")
        if deductible_ratio >= 0.01:
            add("meaningful_retention", "Meaningful deductible", "discount", -0.03, "Customer retention reduces attritional loss exposure.")
        if prior == 0:
            add("clean_loss_history", "Clean prior claims", "discount", -0.04, "No declared prior claims in the last three years.")
        if prior > 0:
            add("prior_claims", "Prior claims", "surcharge", min(0.20, prior * 0.05), "Prior claims increase expected future loss.")
        if accumulation >= DECISION_THRESHOLDS["refer_accumulation_score"]:
            add("accumulation", "Accumulation surcharge", "surcharge", 0.06, "Event accumulation is above review threshold.")
        if high_flags or medium_flags:
            add("enrichment_flags", "Enrichment flags", "surcharge", min(0.18, high_flags * 0.08 + medium_flags * 0.035), "Provider evidence added underwriting concern.")

        adjusted = None if base_premium is None else _round_money(max(LOB_CONFIG[policy["lob"]]["min_premium"], float(base_premium) * (1.0 + total_pct)))
        return {
            "base_premium_sar": base_premium,
            "adjusted_premium_sar": adjusted,
            "expected_loss_sar": quote["expected_loss_sar"],
            "risk_score": quote["risk_score"],
            "scr_impact_sar": quote["scr_impact_sar"],
            "premium_breakdown": {
                "expected_loss_sar": quote["expected_loss_sar"],
                "cat_load_sar": quote["cat_load_sar"],
                "capital_load_sar": quote["capital_load_sar"],
                "expense_load_sar": quote["expense_load_sar"],
                "profit_margin_sar": quote["profit_margin_sar"],
                "technical_premium_sar": quote["technical_premium_sar"],
            },
            "adjustments": adjustments,
            "pricing_reconciliation": quote.get("pricing_reconciliation", []),
            "model_basis": quote.get("model_basis", ""),
        }
