"""Underwriting decision and pricing logic."""

from __future__ import annotations

import math
from typing import Any

from insurance_model.config import DECISION_THRESHOLDS, LOB_CONFIG
from insurance_model.features import enrich_policy_defaults
from insurance_model.rbc import calculate_cat_load, calculate_policy_scr


def _clip(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def _round_premium(value: float) -> float:
    if value < 10_000:
        step = 50
    elif value < 250_000:
        step = 500
    elif value < 2_000_000:
        step = 2_500
    else:
        step = 10_000
    return float(math.ceil(value / step) * step)



def _fmt_sar(value: float) -> str:
    if abs(value) >= 1_000_000_000:
        return f"SAR {value / 1_000_000_000:,.2f}B"
    if abs(value) >= 1_000_000:
        return f"SAR {value / 1_000_000:,.2f}M"
    if abs(value) >= 1_000:
        return f"SAR {value / 1_000:,.1f}K"
    return f"SAR {value:,.0f}"


def business_rule_descriptions() -> list[dict[str, str]]:
    """Natural-language rulebook exposed in the app."""

    return [
        {
            "Rule": "LOB appetite limit",
            "Natural language": (
                "Decline when the requested gross limit is above the configured maximum "
                "appetite for the selected line of business."
            ),
            "Where it is applied": "limit_sar > LOB_CONFIG[lob]['max_limit']",
        },
        {
            "Rule": "Controls plus extreme risk",
            "Natural language": (
                "Decline when controls are very weak and the composite risk score is already "
                "in the decline band."
            ),
            "Where it is applied": "risk_control_score < decline_min_control_score and score >= refer_max_score",
        },
        {
            "Rule": "Unrated reinsurance concentration",
            "Natural language": (
                "Decline when more than half of the risk is ceded to an unrated reinsurance "
                "counterparty."
            ),
            "Where it is applied": "counterparty_rating == 'Unrated' and reinsurance_ceded_pct > 50%",
        },
        {
            "Rule": "Composite risk score",
            "Natural language": (
                "Decline when the blended score from claim probability, loss adequacy, capital "
                "strain, cat load, accumulation, controls, prior claims, and limit intensity "
                "reaches the decline band."
            ),
            "Where it is applied": "score >= refer_max_score",
        },
        {
            "Rule": "Review band",
            "Natural language": (
                "Require review when the risk score is too high for straight-through quoting but not high "
                "enough for automatic decline."
            ),
            "Where it is applied": "score >= quote_max_score",
        },
        {
            "Rule": "Capital strain review",
            "Natural language": (
                "Require review when diversified proxy SCR is high relative to the technical premium."
            ),
            "Where it is applied": "scr_to_premium >= refer_scr_to_premium",
        },
        {
            "Rule": "Accumulation review",
            "Natural language": (
                "Require review when event accumulation or clash-risk concentration is high."
            ),
            "Where it is applied": "event_accumulation_score >= refer_accumulation_score",
        },
        {
            "Rule": "High cession review",
            "Natural language": (
                "Require review when the quote depends heavily on reinsurance support."
            ),
            "Where it is applied": "reinsurance_ceded_pct >= refer_reinsurance_ceded_pct",
        },
    ]


def _status_label(failed: bool, review: bool = False) -> str:
    if failed:
        return "Decline trigger"
    if review:
        return "Review trigger"
    return "Within appetite"


def _rule_evaluations(enriched: dict[str, Any], cfg: dict[str, float], score: float, scr_to_premium: float) -> list[dict[str, str]]:
    requested_limit = float(enriched["limit_sar"])
    max_limit = float(cfg["max_limit"])
    retained_limit = requested_limit * (1.0 - float(enriched["reinsurance_ceded_pct"]))
    return [
        {
            "Rule": "LOB appetite limit",
            "Status": _status_label(requested_limit > max_limit),
            "Evidence": f"Requested {_fmt_sar(requested_limit)} vs configured appetite {_fmt_sar(max_limit)}.",
        },
        {
            "Rule": "Controls plus extreme risk",
            "Status": _status_label(
                enriched["risk_control_score"] < DECISION_THRESHOLDS["decline_min_control_score"]
                and score >= DECISION_THRESHOLDS["refer_max_score"]
            ),
            "Evidence": (
                f"Control score {enriched['risk_control_score']:.0f}; decline control floor "
                f"{DECISION_THRESHOLDS['decline_min_control_score']:.0f}; risk score {score:.1f}."
            ),
        },
        {
            "Rule": "Unrated reinsurance concentration",
            "Status": _status_label(
                enriched["counterparty_rating"] == "Unrated" and enriched["reinsurance_ceded_pct"] > 0.50
            ),
            "Evidence": (
                f"Counterparty {enriched['counterparty_rating']}; ceded share "
                f"{enriched['reinsurance_ceded_pct']:.0%}."
            ),
        },
        {
            "Rule": "Composite risk score",
            "Status": _status_label(score >= DECISION_THRESHOLDS["refer_max_score"]),
            "Evidence": f"Risk score {score:.1f}; decline threshold {DECISION_THRESHOLDS['refer_max_score']:.1f}.",
        },
        {
            "Rule": "Review band",
            "Status": _status_label(False, score >= DECISION_THRESHOLDS["quote_max_score"]),
            "Evidence": f"Risk score {score:.1f}; straight-through quote maximum {DECISION_THRESHOLDS['quote_max_score']:.1f}.",
        },
        {
            "Rule": "Capital strain review",
            "Status": _status_label(False, scr_to_premium >= DECISION_THRESHOLDS["refer_scr_to_premium"]),
            "Evidence": (
                f"SCR-to-premium {scr_to_premium:.2f}; review threshold "
                f"{DECISION_THRESHOLDS['refer_scr_to_premium']:.2f}."
            ),
        },
        {
            "Rule": "Accumulation review",
            "Status": _status_label(
                False,
                enriched["event_accumulation_score"] >= DECISION_THRESHOLDS["refer_accumulation_score"],
            ),
            "Evidence": (
                f"Accumulation {enriched['event_accumulation_score']:.0%}; review threshold "
                f"{DECISION_THRESHOLDS['refer_accumulation_score']:.0%}."
            ),
        },
        {
            "Rule": "High cession review",
            "Status": _status_label(
                False,
                enriched["reinsurance_ceded_pct"] >= DECISION_THRESHOLDS["refer_reinsurance_ceded_pct"],
            ),
            "Evidence": (
                f"Ceded share {enriched['reinsurance_ceded_pct']:.0%}; retained line {_fmt_sar(retained_limit)}; "
                f"review threshold {DECISION_THRESHOLDS['refer_reinsurance_ceded_pct']:.0%}."
            ),
        },
    ]


def _limit_explanation(enriched: dict[str, Any], cfg: dict[str, float]) -> dict[str, list[str]]:
    requested_limit = float(enriched["limit_sar"])
    appetite_limit = float(cfg["max_limit"])
    exposure = max(float(enriched["exposure_value_sar"]), 1.0)
    deductible = max(float(enriched["deductible_sar"]), 0.0)
    ceded = min(max(float(enriched["reinsurance_ceded_pct"]), 0.0), 0.95)
    retained_limit = requested_limit * (1.0 - ceded)
    excess = max(requested_limit - appetite_limit, 0.0)
    excess_pct = excess / max(appetite_limit, 1.0)
    limit_to_exposure = requested_limit / exposure
    appetite_to_exposure = appetite_limit / exposure
    deductible_pct = deductible / max(requested_limit, 1.0)
    suggested_limit = min(appetite_limit, exposure)
    ceded_needed_for_net_appetite = _clip(1.0 - appetite_limit / max(requested_limit, 1.0), 0.0, 0.95)

    drivers = [
        (
            f"The requested gross limit is {_fmt_sar(requested_limit)}, while the configured "
            f"{enriched['lob']} appetite is {_fmt_sar(appetite_limit)}. The request is "
            f"{_fmt_sar(excess)} ({excess_pct:.0%}) above appetite."
        ),
        (
            f"The requested limit is {limit_to_exposure:.0%} of the declared exposure value "
            f"({_fmt_sar(exposure)}). The appetite cap would be {appetite_to_exposure:.0%} of that exposure."
        ),
        (
            f"After the selected {ceded:.0%} reinsurance cession, the retained line is about "
            f"{_fmt_sar(retained_limit)}. The gross limit still fails the current appetite rule."
        ),
        (
            f"The deductible is {_fmt_sar(deductible)}, equal to {deductible_pct:.2%} of the requested limit. "
            "For large commercial limits, a very small deductible gives limited risk sharing."
        ),
    ]

    actions = [
        f"Reduce the requested gross limit to no more than {_fmt_sar(appetite_limit)} for this LOB.",
        f"If the policy is intended to cover the declared exposure, consider a first layer around {_fmt_sar(suggested_limit)} and place excess layers separately.",
        "Split the placement into quota share, facultative reinsurance, co-insurance, or layered excess-of-loss support instead of one gross line.",
        "Use sublimits for high-accumulation perils such as flood, sandstorm, fire/explosion, delay in start-up, or business interruption where relevant.",
    ]
    if ceded_needed_for_net_appetite > ceded:
        actions.append(
            f"If appetite is treated on a net-retained basis by governance, increase reinsurance support to at least {ceded_needed_for_net_appetite:.0%}; still keep the gross-limit override documented."
        )
    if deductible_pct < 0.005:
        actions.append("Increase the deductible or add loss-sharing terms so the insured retains more attritional risk.")
    if enriched["risk_control_score"] < 65:
        actions.append("Improve risk controls before reconsideration, then resubmit with updated survey evidence.")

    return {"drivers": drivers, "recommended_actions": actions}


def deterministic_estimate(policy: dict[str, Any]) -> dict[str, float]:
    """Rules-based loss estimate used as fallback and model stabilizer."""

    enriched = enrich_policy_defaults(policy)
    cfg = LOB_CONFIG[enriched["lob"]]
    term = enriched["term_months"] / 12.0
    control_modifier = 1.42 - 0.0064 * enriched["risk_control_score"]
    prior_modifier = 1.0 + 0.18 * enriched["prior_claims_3y"]

    if enriched["lob"] == "Motor":
        vehicle_class_factor = {
            "Private car": 1.00,
            "SUV": 1.12,
            "Taxi/ride-hailing": 1.55,
            "Light commercial": 1.35,
            "Heavy truck": 1.85,
        }.get(enriched["vehicle_class"], 1.15)
        complexity = vehicle_class_factor
        complexity *= 1.0 + enriched["vehicle_age"] / 22.0
        complexity *= 1.0 + max(0.0, 25.0 - enriched["driver_age"]) / 35.0
        region_multiplier = enriched["traffic_density_score"]
    elif enriched["lob"] == "Property & Fire":
        complexity = (1.0 + enriched["occupancy_hazard_score"]) * (
            1.25 - 0.35 * enriched["fire_protection_score"]
        )
        region_multiplier = (
            0.45 * enriched["flood_zone_score"] + 0.55 * enriched["industrial_zone_score"]
        )
    elif enriched["lob"] == "Engineering & Construction":
        complexity = (
            1.0
            + enriched["project_complexity_score"]
            + enriched["project_duration_months"] / 80.0
            - min(enriched["contractor_experience_years"], 25.0) / 90.0
        )
        region_multiplier = (
            0.30 * enriched["flood_zone_score"]
            + 0.25 * enriched["sandstorm_score"]
            + 0.45 * enriched["industrial_zone_score"]
        )
    elif enriched["lob"] == "Marine & Cargo":
        complexity = (
            1.0
            + enriched["cargo_type_risk_score"]
            + enriched["transit_distance_km"] / 5000.0
            + enriched["storage_days"] / 70.0
        )
        region_multiplier = (
            0.45 * enriched["traffic_density_score"] + 0.55 * enriched["industrial_zone_score"]
        )
    else:
        complexity = (
            1.0
            + enriched["professional_risk_score"]
            + enriched["liability_limit_factor"] * 0.45
        )
        region_multiplier = 0.45 * enriched["industrial_zone_score"] + 0.55

    frequency = cfg["base_frequency"] * region_multiplier * control_modifier * prior_modifier * complexity * term
    frequency = _clip(frequency, 0.002, 1.85)

    severity_factor = (
        complexity
        * (0.60 + min(enriched["exposure_value_sar"] / max(enriched["limit_sar"], 1.0), 4.0) * 0.14)
        * enriched["inflation_index"]
        * enriched["repair_material_index"]
    )
    severity = min(cfg["base_severity"] * severity_factor, enriched["limit_sar"] * 0.92)
    deductible_relief = min(
        0.38,
        enriched["deductible_sar"] / (severity + enriched["deductible_sar"] + 1.0) * 0.75,
    )
    expected_loss = frequency * severity * (1.0 - deductible_relief)
    return {
        "claim_probability": _clip(frequency, 0.0, 1.0),
        "conditional_severity_sar": severity,
        "expected_loss_sar": max(expected_loss, 0.0),
    }


def _model_estimate(policy: dict[str, Any], model_bundle: dict[str, Any] | None) -> dict[str, float] | None:
    if not model_bundle:
        return None
    try:
        from insurance_model.model import predict_policy

        return predict_policy(policy, model_bundle)
    except Exception:
        return None


def _risk_score(
    policy: dict[str, Any],
    claim_probability: float,
    expected_loss: float,
    premium: float,
    scr: float,
    cat_load: float,
) -> float:
    enriched = enrich_policy_defaults(policy)
    limit = max(enriched["limit_sar"], 1.0)
    exposure = max(enriched["exposure_value_sar"], 1.0)
    premium = max(premium, 1.0)

    score = 0.0
    score += min(claim_probability * 42.0, 34.0)
    score += min(expected_loss / premium * 26.0, 24.0)
    score += min(scr / premium * 7.5, 18.0)
    score += min(cat_load / exposure * 950.0, 12.0)
    score += min(enriched["event_accumulation_score"] * 11.0, 11.0)
    score += max(0.0, 65.0 - enriched["risk_control_score"]) * 0.22
    score += min(enriched["prior_claims_3y"] * 3.5, 10.5)
    score += min(enriched["limit_sar"] / max(LOB_CONFIG[enriched["lob"]]["max_limit"], 1.0) * 8.0, 8.0)
    return _clip(score, 0.0, 100.0)


def quote_policy(
    policy: dict[str, Any],
    model_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an underwriting decision and premium breakdown for one policy."""

    enriched = enrich_policy_defaults(policy)
    cfg = LOB_CONFIG[enriched["lob"]]

    rule_estimate = deterministic_estimate(enriched)
    model_estimate = _model_estimate(enriched, model_bundle)

    if model_estimate:
        claim_probability = 0.65 * model_estimate["claim_probability"] + 0.35 * rule_estimate["claim_probability"]
        expected_loss = 0.65 * model_estimate["expected_loss_sar"] + 0.35 * rule_estimate["expected_loss_sar"]
        expected_loss = max(expected_loss, rule_estimate["expected_loss_sar"] * 0.55)
        conditional_severity = 0.65 * model_estimate["conditional_severity_sar"] + 0.35 * rule_estimate["conditional_severity_sar"]
        model_basis = "ML estimate blended with underwriting rules."
    else:
        claim_probability = rule_estimate["claim_probability"]
        expected_loss = rule_estimate["expected_loss_sar"]
        conditional_severity = rule_estimate["conditional_severity_sar"]
        model_basis = "Rules-based proxy estimate; ML bundle unavailable."

    cat_load = calculate_cat_load(enriched, expected_loss)

    provisional_base = expected_loss + cat_load
    provisional_premium = max(cfg["min_premium"], provisional_base / 0.70)
    provisional_scr = calculate_policy_scr(enriched, provisional_premium, expected_loss)
    capital_load = provisional_scr["diversified_scr_sar"] * cfg["cost_of_capital"]

    pricing_cost = expected_loss + cat_load + capital_load
    denominator = max(0.50, 1.0 - cfg["expense_ratio"] - cfg["profit_margin"])
    technical_premium = max(cfg["min_premium"], pricing_cost / denominator)

    final_scr = calculate_policy_scr(enriched, technical_premium, expected_loss)
    capital_load = final_scr["diversified_scr_sar"] * cfg["cost_of_capital"]
    pricing_cost = expected_loss + cat_load + capital_load
    technical_premium = max(cfg["min_premium"], pricing_cost / denominator)
    recommended_premium = _round_premium(technical_premium)

    expense_load = recommended_premium * cfg["expense_ratio"]
    profit_load = recommended_premium * cfg["profit_margin"]
    score = _risk_score(
        enriched,
        claim_probability,
        expected_loss,
        recommended_premium,
        final_scr["diversified_scr_sar"],
        cat_load,
    )
    scr_to_premium = final_scr["diversified_scr_sar"] / max(recommended_premium, 1.0)

    reasons: list[str] = []
    explanation_drivers = [
        (
            f"The blended estimate gives claim probability {claim_probability:.1%}, expected loss "
            f"{_fmt_sar(expected_loss)}, and conditional severity {_fmt_sar(conditional_severity)}."
        ),
        (
            f"The computed premium is {_fmt_sar(technical_premium)} before rounding, with proxy SCR "
            f"{_fmt_sar(final_scr['diversified_scr_sar'])} and SCR-to-premium {scr_to_premium:.2f}."
        ),
        (
            f"The risk score is {score:.1f}; straight-through quote maximum is "
            f"{DECISION_THRESHOLDS['quote_max_score']:.1f} and decline band starts at "
            f"{DECISION_THRESHOLDS['refer_max_score']:.1f}."
        ),
    ]
    recommended_actions: list[str] = []
    decision = "quote"

    if enriched["limit_sar"] > cfg["max_limit"]:
        decision = "decline"
        limit_detail = _limit_explanation(enriched, cfg)
        reasons.append(
            f"Requested limit {_fmt_sar(enriched['limit_sar'])} exceeds the configured "
            f"{enriched['lob']} appetite of {_fmt_sar(cfg['max_limit'])}."
        )
        explanation_drivers.extend(limit_detail["drivers"])
        recommended_actions.extend(limit_detail["recommended_actions"])
    if (
        enriched["risk_control_score"] < DECISION_THRESHOLDS["decline_min_control_score"]
        and score >= DECISION_THRESHOLDS["refer_max_score"]
    ):
        decision = "decline"
        reasons.append("Weak controls combined with very high modeled risk.")
        explanation_drivers.append(
            f"Risk controls are scored {enriched['risk_control_score']:.0f}, below the decline floor "
            f"of {DECISION_THRESHOLDS['decline_min_control_score']:.0f}, while the risk score is {score:.1f}."
        )
        recommended_actions.append("Complete a risk survey and raise the control score before reconsideration.")
    if enriched["counterparty_rating"] == "Unrated" and enriched["reinsurance_ceded_pct"] > 0.50:
        decision = "decline"
        reasons.append("Material dependence on unrated reinsurance counterparty.")
        explanation_drivers.append(
            f"The quote cedes {enriched['reinsurance_ceded_pct']:.0%} to an unrated reinsurer, creating "
            "counterparty concentration rather than risk transfer that can be relied on for appetite."
        )
        recommended_actions.append("Replace the unrated counterparty with rated support or reduce the ceded dependency below 50%.")
    if score >= DECISION_THRESHOLDS["refer_max_score"]:
        decision = "decline"
        reasons.append("Composite risk score is outside current appetite.")
        explanation_drivers.append(
            f"The composite risk score is {score:.1f}, above the automatic decline threshold of "
            f"{DECISION_THRESHOLDS['refer_max_score']:.1f}."
        )
        recommended_actions.append("Reduce exposure, limit, accumulation, or capital strain before resubmission.")

    if decision != "decline":
        if score >= DECISION_THRESHOLDS["quote_max_score"]:
            decision = "refer"
            reasons.append("Composite risk score requires senior underwriting review.")
            recommended_actions.append("Send to senior underwriting with model output, exposure schedule, and loss-control evidence.")
        if scr_to_premium >= DECISION_THRESHOLDS["refer_scr_to_premium"]:
            decision = "refer"
            reasons.append("Capital strain is high relative to technical premium.")
            explanation_drivers.append(
                f"SCR-to-premium is {scr_to_premium:.2f}, above the review threshold "
                f"of {DECISION_THRESHOLDS['refer_scr_to_premium']:.2f}."
            )
            recommended_actions.append("Increase premium, reduce limit, or add reinsurance support to lower capital strain.")
        if enriched["event_accumulation_score"] >= DECISION_THRESHOLDS["refer_accumulation_score"]:
            decision = "refer"
            reasons.append("High event accumulation or clash-risk concentration.")
            explanation_drivers.append(
                f"Accumulation score is {enriched['event_accumulation_score']:.0%}, above the review "
                f"threshold of {DECISION_THRESHOLDS['refer_accumulation_score']:.0%}."
            )
            recommended_actions.append("Add per-event sublimits, site-level accumulation assessment, or clash-risk controls.")
        if enriched["reinsurance_ceded_pct"] >= DECISION_THRESHOLDS["refer_reinsurance_ceded_pct"]:
            decision = "refer"
            reasons.append("High ceded share requires reinsurance security review.")
            recommended_actions.append("Send to the reinsurance team to assess reinsurer security, contract certainty, collateral, and recoverable concentration.")

    if not reasons:
        reasons.append("Risk is within current proxy appetite and pricing adequacy thresholds.")
    if not recommended_actions:
        recommended_actions.append("No remediation is required for straight-through quoting under the current proxy appetite.")

    rule_evaluations = _rule_evaluations(enriched, cfg, score, scr_to_premium)
    decision_explanation = {
        "summary": (
            f"Decision is {decision.upper()} for {enriched['lob']} in {enriched['region']} based on "
            "the current proxy appetite rules, ML estimate, and capital load."
        ),
        "drivers": explanation_drivers,
        "rule_evaluations": rule_evaluations,
        "recommended_actions": recommended_actions,
    }

    return {
        "decision": decision,
        "recommended_premium_sar": None if decision == "decline" else recommended_premium,
        "technical_premium_sar": technical_premium,
        "expected_loss_sar": expected_loss,
        "claim_probability": claim_probability,
        "conditional_severity_sar": conditional_severity,
        "cat_load_sar": cat_load,
        "capital_load_sar": capital_load,
        "expense_load_sar": expense_load,
        "profit_margin_sar": profit_load,
        "risk_score": score,
        "scr_impact_sar": final_scr["diversified_scr_sar"],
        "scr_to_premium": scr_to_premium,
        "decision_reasons": reasons,
        "decision_explanation": decision_explanation,
        "rbc": final_scr,
        "model_basis": model_basis,
        "policy": enriched,
    }

