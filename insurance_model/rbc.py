"""Proxy RBC-style capital calculations for the prototype."""

from __future__ import annotations

import math
from typing import Mapping

from insurance_model.config import (
    COUNTERPARTY_RATING_FACTORS,
    DEFAULT_MODULE_CORRELATIONS,
    LOB_CONFIG,
)
from insurance_model.features import enrich_policy_defaults

RISK_MODULES = ["underwriting", "catastrophe", "market_credit"]


def aggregate_capital(
    module_capitals: Mapping[str, float],
    correlations: Mapping[str, Mapping[str, float]] | None = None,
) -> float:
    """Aggregate module capital with a square-root correlation formula."""

    corr = correlations or DEFAULT_MODULE_CORRELATIONS
    total = 0.0
    for left in RISK_MODULES:
        for right in RISK_MODULES:
            total += (
                float(module_capitals.get(left, 0.0))
                * float(module_capitals.get(right, 0.0))
                * float(corr[left][right])
            )
    return math.sqrt(max(total, 0.0))


def calculate_policy_scr(
    policy: dict,
    premium_sar: float,
    expected_loss_sar: float,
) -> dict:
    """Calculate proxy standalone and diversified capital for one policy."""

    enriched = enrich_policy_defaults(policy)
    lob_cfg = LOB_CONFIG[enriched["lob"]]

    premium = max(float(premium_sar), 0.0)
    expected_loss = max(float(expected_loss_sar), 0.0)
    exposure = max(float(enriched["exposure_value_sar"]), 1.0)
    ceded = min(max(float(enriched["reinsurance_ceded_pct"]), 0.0), 0.95)

    cat_region = (
        0.38 * float(enriched["flood_zone_score"])
        + 0.24 * float(enriched["sandstorm_score"])
        + 0.38 * float(enriched["industrial_zone_score"])
    )
    accumulation = 0.65 + 0.70 * min(max(float(enriched["event_accumulation_score"]), 0.0), 1.0)
    net_cat_factor = lob_cfg["cat_factor"] * cat_region * accumulation * (1.0 - 0.55 * ceded)

    rating_factor = COUNTERPARTY_RATING_FACTORS.get(
        enriched["counterparty_rating"], COUNTERPARTY_RATING_FACTORS["Unrated"]
    )
    reinsurance_recoverable = expected_loss * ceded * 2.5

    modules = {
        "underwriting": max(
            premium * lob_cfg["underwriting_factor"],
            expected_loss * 0.55,
        ),
        "catastrophe": exposure * net_cat_factor,
        "market_credit": premium * 0.045 + reinsurance_recoverable * rating_factor,
    }
    diversified = aggregate_capital(modules)

    return {
        "module_capitals": modules,
        "standalone_sum_sar": sum(modules.values()),
        "diversified_scr_sar": diversified,
        "diversification_benefit_sar": sum(modules.values()) - diversified,
        "proxy_basis": "Configurable proxy factors; not an official IA regulatory calculation.",
    }


def calculate_cat_load(policy: dict, expected_loss_sar: float) -> float:
    """Calculate a pricing catastrophe load separate from capital charge."""

    enriched = enrich_policy_defaults(policy)
    lob_cfg = LOB_CONFIG[enriched["lob"]]
    exposure = max(float(enriched["exposure_value_sar"]), 1.0)
    ceded = min(max(float(enriched["reinsurance_ceded_pct"]), 0.0), 0.95)
    region_cat = max(
        float(enriched["flood_zone_score"]),
        float(enriched["sandstorm_score"]),
        float(enriched["industrial_zone_score"]),
    )
    accumulation = 0.5 + float(enriched["event_accumulation_score"])
    cat_load = exposure * lob_cfg["cat_factor"] * 0.18 * region_cat * accumulation
    return max(cat_load * (1.0 - 0.45 * ceded), expected_loss_sar * 0.025)


def aggregate_portfolio_scr(policy_scrs: list[dict]) -> dict:
    """Aggregate pre-computed policy SCR results at portfolio level."""

    modules = {module: 0.0 for module in RISK_MODULES}
    for scr in policy_scrs:
        for module in RISK_MODULES:
            modules[module] += float(scr["module_capitals"].get(module, 0.0))
    diversified = aggregate_capital(modules)
    standalone = sum(modules.values())
    return {
        "module_capitals": modules,
        "standalone_sum_sar": standalone,
        "diversified_scr_sar": diversified,
        "diversification_benefit_sar": standalone - diversified,
    }

