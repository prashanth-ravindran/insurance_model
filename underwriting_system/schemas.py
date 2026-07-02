"""Typed API schemas for the underwriting workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from insurance_model.config import LOBS, REGION_RISK


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ENRICHED = "enriched"
    STP_QUOTED = "stp_quoted"
    REQUIRES_REVIEW = "requires_review"
    DECLINED = "declined"
    UNDERWRITER_APPROVED = "underwriter_approved"
    UNDERWRITER_DECLINED = "underwriter_declined"
    QUOTED = "quoted"
    BOUND = "bound"


class UnstructuredIntakeStatus(StrEnum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLICATION_CREATED = "application_created"
    FAILED = "failed"


class IntakeChannel(StrEnum):
    MANUAL = "manual"
    API = "api"


class UserRole(StrEnum):
    AGENT = "agent"
    UNDERWRITER = "underwriter"
    MANAGER = "manager"


class DecisionBucket(StrEnum):
    STP = "stp"
    REQUIRES_REVIEW = "requires_review"
    DECLINED = "declined"


class Applicant(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=2)
    applicant_type: Literal["individual", "company"] = "company"
    national_id_or_cr: str = Field(min_length=4)
    email: str | None = None
    phone: str | None = None


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    channel: IntakeChannel = IntakeChannel.MANUAL
    submitted_by: str = "demo.agent"
    role: UserRole = UserRole.AGENT
    applicant: Applicant
    policy: dict[str, Any]
    requested_coverages: dict[str, Any] = Field(default_factory=dict)

    @field_validator("policy")
    @classmethod
    def validate_policy(cls, value: dict[str, Any]) -> dict[str, Any]:
        missing = [key for key in ["lob", "region", "exposure_value_sar", "limit_sar", "deductible_sar"] if key not in value]
        if missing:
            raise ValueError(f"policy is missing required fields: {', '.join(missing)}")
        if value["lob"] not in LOBS:
            raise ValueError(f"unsupported lob: {value['lob']}")
        if value["region"] not in REGION_RISK:
            raise ValueError(f"unsupported region: {value['region']}")
        for key in ["exposure_value_sar", "limit_sar"]:
            if float(value[key]) <= 0:
                raise ValueError(f"{key} must be positive")
        if float(value["deductible_sar"]) < 0:
            raise ValueError("deductible_sar must be non-negative")
        return value


class EnrichmentFlag(BaseModel):
    code: str
    label: str
    severity: Literal["low", "medium", "high"]
    message: str


class EnrichmentResult(BaseModel):
    provider: str
    status: Literal["completed", "failed"] = "completed"
    confidence: float = Field(ge=0.0, le=1.0)
    data: dict[str, Any] = Field(default_factory=dict)
    flags: list[EnrichmentFlag] = Field(default_factory=list)
    requested_at: str
    completed_at: str


class PricingAdjustment(BaseModel):
    code: str
    label: str
    kind: Literal["discount", "surcharge", "schedule"]
    pct: float
    amount_sar: float
    reason: str


class UnderwritingDecision(BaseModel):
    decision_bucket: DecisionBucket
    engine_decision: str
    reasons: list[str]
    recommended_actions: list[str]
    rule_evaluations: list[dict[str, Any]]
    enrichment_flags: list[EnrichmentFlag]


class RatingResult(BaseModel):
    base_premium_sar: float | None
    adjusted_premium_sar: float | None
    expected_loss_sar: float
    risk_score: float
    scr_impact_sar: float
    premium_breakdown: dict[str, float]
    adjustments: list[PricingAdjustment]
    pricing_reconciliation: list[dict[str, Any]]
    model_basis: str


class ReviewDecisionRequest(BaseModel):
    action: Literal["approve", "decline"]
    underwriter: str = "demo.underwriter"
    notes: str = Field(min_length=2)
    premium_delta_pct: float = 0.0
    deductible_sar: float | None = None
    sublimits: dict[str, float] = Field(default_factory=dict)
    exclusions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_adjustment(self) -> "ReviewDecisionRequest":
        if self.action == "approve" and self.premium_delta_pct < -0.25:
            raise ValueError("premium_delta_pct cannot reduce premium by more than 25%")
        return self


class AssignmentRequest(BaseModel):
    assignee: str


class QuoteGenerateRequest(BaseModel):
    generated_by: str = "demo.agent"
    expiry_days: int = Field(default=30, ge=1, le=120)


class BindRequest(BaseModel):
    bound_by: str = "demo.agent"
    accepted_terms: bool = True


class FieldConfidence(BaseModel):
    confidence: Literal["high", "low"] = "low"
    evidence: str | None = None
    rationale: str | None = None


class UnstructuredReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    reviewer: str = "demo.underwriter"
    notes: str = ""
    application: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_application_for_approval(self) -> "UnstructuredReviewRequest":
        if self.action == "approve" and self.application is None:
            raise ValueError("application is required when approving an extraction")
        return self


class ApiResponse(BaseModel):
    ok: bool = True
    data: dict[str, Any]
