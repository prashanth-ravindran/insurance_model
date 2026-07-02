"""Deterministic generated enrichment providers for underwriting intake."""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime
from typing import Any

from insurance_model.config import REGION_RISK
from underwriting_system.schemas import EnrichmentFlag, EnrichmentResult


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _rng(application_id: str, provider: str) -> random.Random:
    digest = hashlib.sha256(f"{application_id}:{provider}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _flag(code: str, label: str, severity: str, message: str) -> dict[str, str]:
    return EnrichmentFlag(code=code, label=label, severity=severity, message=message).model_dump()


def _response(provider: str, confidence: float, data: dict[str, Any], flags: list[dict[str, str]]) -> dict[str, Any]:
    requested_at = _now()
    return EnrichmentResult(
        provider=provider,
        status="completed",
        confidence=max(0.0, min(float(confidence), 1.0)),
        data=data,
        flags=[EnrichmentFlag(**flag) for flag in flags],
        requested_at=requested_at,
        completed_at=_now(),
    ).model_dump()


def _cross_cutting(application_id: str, applicant: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    rng = _rng(application_id, "identity_financial")
    score = int(rng.triangular(520, 840, 710))
    confidence = rng.uniform(0.82, 0.97)
    flags: list[dict[str, str]] = []
    applicant_id = str(applicant.get("national_id_or_cr", ""))
    if applicant_id.endswith("999"):
        flags.append(_flag("identity_watchlist", "Identity watchlist hit", "high", "Applicant identifier matched the demo watchlist pattern."))
    if score < 590:
        flags.append(_flag("low_financial_score", "Low financial score", "medium", "Financial score is below preferred appetite."))
    data = {
        "identity_verified": not applicant_id.endswith("999"),
        "financial_score": score,
        "payment_stability_index": round(rng.uniform(0.35, 0.96), 2),
        "applicant_segment": applicant.get("applicant_type", "company"),
    }
    return _response("identity_financial", confidence, data, flags)


def _reinsurance_security(application_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    rng = _rng(application_id, "reinsurance_security")
    ceded = float(policy.get("reinsurance_ceded_pct", 0.25))
    rating = str(policy.get("counterparty_rating", "A"))
    collateral = round(max(0.02, min(0.70, rng.uniform(0.06, 0.22) + ceded * 0.15)), 2)
    flags: list[dict[str, str]] = []
    if rating in {"BB", "Unrated"} and ceded > 0.35:
        flags.append(_flag("weak_reinsurance_security", "Weak reinsurance security", "high", "High cession depends on a weak or unrated counterparty."))
    elif ceded > 0.65:
        flags.append(_flag("high_reinsurance_dependency", "High reinsurance dependency", "medium", "The quote depends heavily on ceded reinsurance support."))
    data = {
        "counterparty_rating_confirmed": rating,
        "ceded_pct_confirmed": ceded,
        "collateral_pct": collateral,
        "recoverable_concentration_index": round(rng.uniform(0.18, 0.78), 2),
    }
    return _response("reinsurance_security", rng.uniform(0.80, 0.96), data, flags)


def _motor(application_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    rng = _rng(application_id, "motor_mvr_clue")
    prior_claims = int(policy.get("prior_claims_3y", 0))
    violations = max(0, int(rng.gauss(0.8 + prior_claims * 0.55, 1.0)))
    accidents = max(0, int(rng.gauss(0.35 + prior_claims * 0.45, 0.8)))
    flags: list[dict[str, str]] = []
    if violations >= 4:
        flags.append(_flag("major_mvr_activity", "Major MVR activity", "high", "Driving record shows multiple recent violations."))
    if accidents >= 3:
        flags.append(_flag("claim_frequency_concern", "Claim frequency concern", "medium", "Prior auto accidents exceed preferred appetite."))
    data = {
        "mvr_violations_3y": violations,
        "mvr_accidents_3y": accidents,
        "license_status": "valid" if violations < 5 else "restricted",
        "clue_claims_5y": prior_claims + max(0, int(rng.random() < 0.22)),
        "vin_match_quality": round(rng.uniform(0.86, 0.99), 2),
    }
    return _response("motor_mvr_clue", rng.uniform(0.84, 0.98), data, flags)


def _property(application_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    rng = _rng(application_id, "property_condition")
    region = str(policy.get("region", "Riyadh"))
    roof_condition = int(rng.triangular(35, 98, 76))
    fire_distance_km = round(rng.uniform(0.4, 18.0), 1)
    flood = float(REGION_RISK.get(region, REGION_RISK["Riyadh"])["flood_zone_score"])
    flags: list[dict[str, str]] = []
    if roof_condition < 50:
        flags.append(_flag("roof_condition", "Roof condition concern", "medium", "Property image score suggests roof or envelope maintenance issues."))
    if fire_distance_km > 12:
        flags.append(_flag("fire_response_distance", "Fire response distance", "medium", "Distance to fire response is outside preferred range."))
    if flood > 1.25:
        flags.append(_flag("elevated_flood_zone", "Elevated flood zone", "high", "Location has elevated flash-flood exposure."))
    data = {
        "property_record_match": True,
        "roof_condition_score": roof_condition,
        "fire_station_distance_km": fire_distance_km,
        "flood_zone_score_confirmed": flood,
        "satellite_image_age_months": int(rng.choice([3, 6, 9, 12, 18])),
    }
    return _response("property_condition", rng.uniform(0.78, 0.95), data, flags)


def _engineering(application_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    rng = _rng(application_id, "engineering_project")
    complexity = float(policy.get("project_complexity_score", 0.5))
    experience = float(policy.get("contractor_experience_years", 8))
    schedule_pressure = round(rng.uniform(0.18, 0.88) + max(0.0, complexity - 0.65) * 0.25, 2)
    flags: list[dict[str, str]] = []
    if complexity > 0.78:
        flags.append(_flag("project_complexity", "High project complexity", "high", "Project type and scope require human engineering review."))
    if experience < 4:
        flags.append(_flag("contractor_experience", "Limited contractor experience", "medium", "Contractor experience is weak for the declared project size."))
    if schedule_pressure > 0.82:
        flags.append(_flag("delay_startup_pressure", "Delay-startup pressure", "medium", "Schedule pressure increases delay and contract works exposure."))
    data = {
        "contractor_loss_history_index": round(rng.uniform(0.18, 0.84), 2),
        "schedule_pressure_index": schedule_pressure,
        "project_complexity_confirmed": complexity,
        "site_accumulation_index": round(float(policy.get("event_accumulation_score", 0.25)) + rng.uniform(0.02, 0.18), 2),
    }
    return _response("engineering_project", rng.uniform(0.77, 0.94), data, flags)


def _marine(application_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    rng = _rng(application_id, "marine_route_cargo")
    storage_days = float(policy.get("storage_days", 4))
    cargo_risk = float(policy.get("cargo_type_risk_score", 0.35))
    port_delay = round(rng.uniform(0.05, 0.72) + min(storage_days / 120.0, 0.22), 2)
    flags: list[dict[str, str]] = []
    if cargo_risk > 0.75:
        flags.append(_flag("sensitive_cargo", "Sensitive or hazardous cargo", "high", "Cargo type needs tighter terms and route controls."))
    if port_delay > 0.65:
        flags.append(_flag("port_delay", "Port delay risk", "medium", "Route and storage profile shows elevated delay exposure."))
    data = {
        "route_delay_index": port_delay,
        "theft_index": round(rng.uniform(0.10, 0.58), 2),
        "cargo_sensitivity_confirmed": cargo_risk,
        "storage_days_confirmed": storage_days,
    }
    return _response("marine_route_cargo", rng.uniform(0.80, 0.96), data, flags)


def _liability(application_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    rng = _rng(application_id, "liability_business")
    professional = float(policy.get("professional_risk_score", 0.35))
    litigation = round(rng.uniform(0.08, 0.74) + professional * 0.18, 2)
    flags: list[dict[str, str]] = []
    if litigation > 0.70:
        flags.append(_flag("litigation_index", "Elevated litigation index", "medium", "Business profile shows elevated litigation propensity."))
    if professional > 0.70:
        flags.append(_flag("professional_services_risk", "Professional services risk", "medium", "Professional or management-liability risk is above preferred range."))
    data = {
        "revenue_verified_sar": float(policy.get("annual_revenue_sar", policy.get("exposure_value_sar", 0))),
        "litigation_index": litigation,
        "professional_risk_confirmed": professional,
        "contractual_risk_index": round(rng.uniform(0.16, 0.82), 2),
    }
    return _response("liability_business", rng.uniform(0.79, 0.95), data, flags)


def enrich_application(application_id: str, applicant: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic enrichment responses for an application."""

    lob = policy.get("lob", "Motor")
    results = [_cross_cutting(application_id, applicant, policy), _reinsurance_security(application_id, policy)]
    if lob == "Motor":
        results.append(_motor(application_id, policy))
    elif lob == "Property & Fire":
        results.append(_property(application_id, policy))
    elif lob == "Engineering & Construction":
        results.append(_engineering(application_id, policy))
    elif lob == "Marine & Cargo":
        results.append(_marine(application_id, policy))
    elif lob == "Casualty/Liability":
        results.append(_liability(application_id, policy))
    return results


def merge_enrichment_into_policy(policy: dict[str, Any], enrichments: list[dict[str, Any]]) -> dict[str, Any]:
    """Translate provider evidence into model-ready risk attributes."""

    enriched = dict(policy)
    flags = [flag for result in enrichments for flag in result.get("flags", [])]
    high_flags = sum(1 for flag in flags if flag.get("severity") == "high")
    medium_flags = sum(1 for flag in flags if flag.get("severity") == "medium")
    current_controls = float(enriched.get("risk_control_score", 70))
    enriched["risk_control_score"] = max(5.0, current_controls - high_flags * 9.0 - medium_flags * 4.0)
    enriched["prior_claims_3y"] = int(float(enriched.get("prior_claims_3y", 0)))
    enriched["event_accumulation_score"] = min(
        0.99,
        float(enriched.get("event_accumulation_score", 0.25)) + high_flags * 0.04 + medium_flags * 0.015,
    )

    for result in enrichments:
        data = result.get("data", {})
        if "mvr_accidents_3y" in data:
            enriched["prior_claims_3y"] = max(enriched["prior_claims_3y"], int(data["mvr_accidents_3y"]))
        if "flood_zone_score_confirmed" in data:
            enriched["flood_zone_score"] = float(data["flood_zone_score_confirmed"])
        if "project_complexity_confirmed" in data:
            enriched["project_complexity_score"] = float(data["project_complexity_confirmed"])
        if "site_accumulation_index" in data:
            enriched["event_accumulation_score"] = max(enriched["event_accumulation_score"], min(0.99, float(data["site_accumulation_index"])))
        if "cargo_sensitivity_confirmed" in data:
            enriched["cargo_type_risk_score"] = float(data["cargo_sensitivity_confirmed"])
        if "professional_risk_confirmed" in data:
            enriched["professional_risk_score"] = float(data["professional_risk_confirmed"])
    return enriched
