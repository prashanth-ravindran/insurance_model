"""Expanded proxy SCR aggregation for the full risk model."""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np
import pandas as pd

from insurance_model.actuarial import build_reserving_analysis
from insurance_model.config import COUNTERPARTY_RATING_FACTORS, LOB_CONFIG

FULL_RISK_MODULES = [
    "premium_risk",
    "reserve_risk",
    "catastrophe_risk",
    "reinsurance_credit_risk",
    "market_risk",
]

FULL_MODULE_CORRELATIONS: dict[str, dict[str, float]] = {
    "premium_risk": {
        "premium_risk": 1.00,
        "reserve_risk": 0.45,
        "catastrophe_risk": 0.25,
        "reinsurance_credit_risk": 0.20,
        "market_risk": 0.15,
    },
    "reserve_risk": {
        "premium_risk": 0.45,
        "reserve_risk": 1.00,
        "catastrophe_risk": 0.20,
        "reinsurance_credit_risk": 0.25,
        "market_risk": 0.15,
    },
    "catastrophe_risk": {
        "premium_risk": 0.25,
        "reserve_risk": 0.20,
        "catastrophe_risk": 1.00,
        "reinsurance_credit_risk": 0.30,
        "market_risk": 0.10,
    },
    "reinsurance_credit_risk": {
        "premium_risk": 0.20,
        "reserve_risk": 0.25,
        "catastrophe_risk": 0.30,
        "reinsurance_credit_risk": 1.00,
        "market_risk": 0.35,
    },
    "market_risk": {
        "premium_risk": 0.15,
        "reserve_risk": 0.15,
        "catastrophe_risk": 0.10,
        "reinsurance_credit_risk": 0.35,
        "market_risk": 1.00,
    },
}

RESERVE_RISK_FACTORS = {
    "Motor": 0.18,
    "Property & Fire": 0.24,
    "Engineering & Construction": 0.28,
    "Marine & Cargo": 0.22,
    "Casualty/Liability": 0.32,
}


def aggregate_full_capital(
    module_capitals: Mapping[str, float],
    correlations: Mapping[str, Mapping[str, float]] | None = None,
) -> float:
    """Aggregate full module capital with square-root correlations."""

    corr = correlations or FULL_MODULE_CORRELATIONS
    total = 0.0
    for left in FULL_RISK_MODULES:
        for right in FULL_RISK_MODULES:
            total += float(module_capitals.get(left, 0.0)) * float(module_capitals.get(right, 0.0)) * float(corr[left][right])
    return math.sqrt(max(total, 0.0))


def _premium_risk(policies: pd.DataFrame, premiums: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    rows = []
    for lob, group in policies.groupby("lob"):
        written = float(premiums.loc[premiums["lob"] == lob, "written_premium_sar"].sum()) if not premiums.empty else float(group["technical_premium_sar"].sum())
        expected_loss = float(group["expected_loss_sar"].sum())
        factor = LOB_CONFIG[lob]["underwriting_factor"]
        capital = max(written * factor, expected_loss * 0.55)
        rows.append({"lob": lob, "premium_risk_sar": capital, "written_premium_sar": written, "expected_loss_sar": expected_loss})
    detail = pd.DataFrame(rows)
    return float(detail["premium_risk_sar"].sum()) if not detail.empty else 0.0, detail


def _reserve_risk(reserve_summary: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    if reserve_summary.empty:
        return 0.0, pd.DataFrame(columns=["lob", "reserve_risk_sar"])
    detail = reserve_summary.copy()
    detail["reserve_risk_factor"] = detail["lob"].map(RESERVE_RISK_FACTORS).fillna(0.25)
    detail["reserve_risk_sar"] = detail["selected_reserve_sar"] * detail["reserve_risk_factor"]
    return float(detail["reserve_risk_sar"].sum()), detail[["lob", "reserve_risk_factor", "selected_reserve_sar", "reserve_risk_sar"]]


def _catastrophe_risk(policies: pd.DataFrame, cat_events: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    exposure_charge = 0.0
    rows = []
    for lob, group in policies.groupby("lob"):
        factor = LOB_CONFIG[lob]["cat_factor"]
        cat_region = (0.38 * group["flood_zone_score"] + 0.24 * group["sandstorm_score"] + 0.38 * group["industrial_zone_score"]).mean()
        accumulation = (0.65 + 0.70 * group["event_accumulation_score"].clip(0, 1)).mean()
        charge = float(group["exposure_value_sar"].sum() * factor * cat_region * accumulation * 0.28)
        exposure_charge += charge
        rows.append({"lob": lob, "exposure_cat_charge_sar": charge})
    pml_charge = float(cat_events["net_loss_sar"].sum() * 1.35 + cat_events["pml_sar"].max() * 0.45) if not cat_events.empty else 0.0
    detail = pd.DataFrame(rows)
    return max(exposure_charge, pml_charge), detail.assign(pml_overlay_sar=pml_charge)


def _reinsurance_credit_risk(reinsurance: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    if reinsurance.empty:
        return 0.0, pd.DataFrame()
    detail = reinsurance.copy()
    detail["rating_default_factor"] = detail["counterparty_rating"].map(COUNTERPARTY_RATING_FACTORS).fillna(COUNTERPARTY_RATING_FACTORS["Unrated"])
    detail["credit_capital_sar"] = (
        detail["expected_default_loss_sar"]
        + detail["recoverable_sar"] * detail["rating_default_factor"] * (1.0 - detail["collateral_pct"].clip(0, 0.95))
    )
    summary = detail.groupby(["reinsurer_name", "counterparty_rating"], as_index=False).agg(
        recoverable_sar=("recoverable_sar", "sum"),
        expected_default_loss_sar=("expected_default_loss_sar", "sum"),
        credit_capital_sar=("credit_capital_sar", "sum"),
    )
    return float(summary["credit_capital_sar"].sum()), summary


def _market_risk(premiums: pd.DataFrame, reserve_summary: pd.DataFrame, market_curves: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    premium_base = float(premiums["earned_premium_sar"].sum()) if not premiums.empty else 0.0
    reserve_base = float(reserve_summary["selected_reserve_sar"].sum()) if not reserve_summary.empty else 0.0
    fixed_income_value = premium_base * 1.8 + reserve_base
    if market_curves.empty:
        rate_shock = 0.010
        spread_shock = 0.006
    else:
        rate_shock = max(float((market_curves["stressed_yield_pct"] - market_curves["base_yield_pct"]).mean()) / 100.0, 0.0025)
        spread_shock = max(float((market_curves["stressed_credit_spread_bps"] - market_curves["credit_spread_bps"]).mean()) / 10000.0, 0.0015)
    duration = 3.2
    rate_capital = fixed_income_value * duration * rate_shock
    spread_capital = fixed_income_value * 1.15 * spread_shock
    currency_basis_capital = fixed_income_value * 0.0025
    detail = pd.DataFrame(
        [
            {"market_component": "interest_rate", "capital_sar": rate_capital},
            {"market_component": "credit_spread", "capital_sar": spread_capital},
            {"market_component": "sar_usd_peg_basis", "capital_sar": currency_basis_capital},
        ]
    )
    return float(detail["capital_sar"].sum()), detail


def calculate_full_scr(bundle: dict[str, pd.DataFrame], reserving_result: dict[str, pd.DataFrame] | None = None) -> dict[str, object]:
    """Calculate an expanded proxy SCR from all generated feeds."""

    policies = bundle.get("policies", pd.DataFrame()).copy()
    premiums = bundle.get("premiums", pd.DataFrame()).copy()
    reinsurance = bundle.get("reinsurance", pd.DataFrame()).copy()
    cat_events = bundle.get("cat_events", pd.DataFrame()).copy()
    market_curves = bundle.get("market_curves", pd.DataFrame()).copy()
    reserving = reserving_result or build_reserving_analysis(bundle)
    reserve_summary = reserving.get("reserve_summary", pd.DataFrame()).copy()

    premium_capital, premium_detail = _premium_risk(policies, premiums)
    reserve_capital, reserve_detail = _reserve_risk(reserve_summary)
    cat_capital, cat_detail = _catastrophe_risk(policies, cat_events)
    credit_capital, credit_detail = _reinsurance_credit_risk(reinsurance)
    market_capital, market_detail = _market_risk(premiums, reserve_summary, market_curves)

    modules = {
        "premium_risk": premium_capital,
        "reserve_risk": reserve_capital,
        "catastrophe_risk": cat_capital,
        "reinsurance_credit_risk": credit_capital,
        "market_risk": market_capital,
    }
    diversified = aggregate_full_capital(modules)
    standalone = float(sum(modules.values()))
    module_df = pd.DataFrame(
        [{"module": module, "capital_sar": value} for module, value in modules.items()]
    )

    return {
        "module_capitals": modules,
        "module_table": module_df,
        "standalone_sum_sar": standalone,
        "diversified_scr_sar": diversified,
        "diversification_benefit_sar": standalone - diversified,
        "correlation_matrix": pd.DataFrame(FULL_MODULE_CORRELATIONS).loc[FULL_RISK_MODULES, FULL_RISK_MODULES],
        "details": {
            "premium_risk": premium_detail,
            "reserve_risk": reserve_detail,
            "catastrophe_risk": cat_detail,
            "reinsurance_credit_risk": credit_detail,
            "market_risk": market_detail,
        },
        "proxy_basis": "Expanded proxy SCR using configurable non-regulatory factors and generated feed data.",
    }
