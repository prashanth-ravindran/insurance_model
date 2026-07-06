"""Model summary payloads for the React workbench."""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Mapping

import numpy as np
import pandas as pd

from insurance_model.actuarial import build_reserving_analysis, train_actuarial_models
from insurance_model.capital import FULL_MODULE_CORRELATIONS, FULL_RISK_MODULES, calculate_full_scr
from insurance_model.config import (
    DATA_NOTICE,
    DECISION_THRESHOLDS,
    DEFAULT_MODULE_CORRELATIONS,
    LOB_CONFIG,
    LOBS,
    REGION_RISK,
)
from insurance_model.explainability import explain_policy_prediction, feature_importance_table
from insurance_model.model import train_ml_models
from insurance_model.pricing import price_policy
from insurance_model.rbc import aggregate_portfolio_scr, calculate_policy_scr
from insurance_model.scenarios import scenario_comparison
from insurance_model.simulation import SCENARIOS, generate_simulation_bundle, metadata_coverage
from insurance_model.underwriting import business_rule_descriptions


def _clean_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _clean_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_clean_value(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _df_records(df: pd.DataFrame | None, limit: int | None = None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.head(limit).copy() if limit is not None else df.copy()
    return [
        {str(key): _clean_value(value) for key, value in row.items()}
        for row in out.to_dict(orient="records")
    ]


def _correlation_rows(matrix: pd.DataFrame) -> list[dict[str, Any]]:
    out = matrix.reset_index().rename(columns={"index": "module"})
    return _df_records(out)


def _build_portfolio_capital(df: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    sample = df.sample(min(len(df), 900), random_state=19)
    lob_rows: list[dict[str, Any]] = []
    portfolio_scrs: list[dict[str, Any]] = []
    for lob, group in sample.groupby("lob"):
        scrs = [
            calculate_policy_scr(row.to_dict(), row["technical_premium_sar"], row["expected_loss_sar"])
            for _, row in group.iterrows()
        ]
        group_agg = aggregate_portfolio_scr(scrs)
        portfolio_scrs.extend(scrs)
        lob_rows.append(
            {
                "LOB": lob,
                "Sample policies": len(group),
                "Standalone capital": group_agg["standalone_sum_sar"],
                "Diversified SCR": group_agg["diversified_scr_sar"],
                "Diversification benefit": group_agg["diversification_benefit_sar"],
            }
        )
    return aggregate_portfolio_scr(portfolio_scrs), pd.DataFrame(lob_rows)


def _threshold_rows() -> list[dict[str, Any]]:
    return [
        {
            "Threshold": "Straight-through quote maximum score",
            "Value": DECISION_THRESHOLDS["quote_max_score"],
            "Meaning": "Scores at or below this value can be quoted if no hard decline or review rule fires.",
        },
        {
            "Threshold": "Automatic decline score",
            "Value": DECISION_THRESHOLDS["refer_max_score"],
            "Meaning": "Scores at or above this value are outside current proxy appetite.",
        },
        {
            "Threshold": "SCR-to-premium review",
            "Value": DECISION_THRESHOLDS["refer_scr_to_premium"],
            "Meaning": "Capital strain above this ratio requires review.",
        },
        {
            "Threshold": "Control score decline floor",
            "Value": DECISION_THRESHOLDS["decline_min_control_score"],
            "Meaning": "Very weak controls can trigger decline when combined with an extreme score.",
        },
        {
            "Threshold": "Accumulation review",
            "Value": DECISION_THRESHOLDS["refer_accumulation_score"],
            "Meaning": "High event accumulation or clash-risk concentration requires review.",
        },
        {
            "Threshold": "High cession review",
            "Value": DECISION_THRESHOLDS["refer_reinsurance_ceded_pct"],
            "Meaning": "Heavy dependence on reinsurance support requires reinsurance security review.",
        },
    ]


def _appetite_rows() -> list[dict[str, Any]]:
    return [
        {
            "LOB": lob,
            "Maximum gross limit": cfg["max_limit"],
            "Minimum premium": cfg["min_premium"],
            "Expense ratio": cfg["expense_ratio"],
            "Profit margin": cfg["profit_margin"],
            "Cost of capital": cfg["cost_of_capital"],
        }
        for lob, cfg in LOB_CONFIG.items()
    ]


@lru_cache(maxsize=8)
def _runtime(rows: int, seed: int, scenario_name: str) -> dict[str, Any]:
    bundle = generate_simulation_bundle(rows=rows, seed=seed, scenario_name=scenario_name)
    reserving = build_reserving_analysis(bundle)
    return {
        "bundle": bundle,
        "model_bundle": train_ml_models(bundle["policies"], artifact_dir=None, random_state=seed),
        "actuarial_bundle": train_actuarial_models(bundle),
        "reserving": reserving,
        "full_capital": calculate_full_scr(bundle, reserving),
        "scenario_comparison": scenario_comparison(rows=rows, seed=seed),
    }


def _bounded_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, low), high)


def _safe_scenario(value: Any) -> str:
    scenario = str(value or "Base")
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    return scenario


def build_model_summary(request: dict[str, Any]) -> dict[str, Any]:
    """Build the React payload equivalent of the Streamlit model application."""

    rows = _bounded_int(request.get("rows"), 2500, 1000, 10000)
    seed = _bounded_int(request.get("seed"), 42, 1, 9999)
    scenario_name = _safe_scenario(request.get("scenario"))
    policy = dict(request.get("policy") or {})
    if policy.get("lob") not in LOBS:
        policy["lob"] = "Motor"
    if policy.get("region") not in REGION_RISK:
        policy["region"] = "Riyadh"

    runtime = _runtime(rows, seed, scenario_name)
    bundle: dict[str, pd.DataFrame] = runtime["bundle"]
    portfolio_df = bundle["policies"]
    model_bundle = runtime["model_bundle"]
    actuarial_bundle = runtime["actuarial_bundle"]
    reserving_result = runtime["reserving"]
    full_capital = runtime["full_capital"]

    quote = price_policy(policy, model_bundle=model_bundle, actuarial_bundle=actuarial_bundle)
    rbc_modules = pd.DataFrame(
        [
            {"module": key.replace("_", " ").title(), "capital_sar": value}
            for key, value in quote["rbc"]["module_capitals"].items()
        ]
    )
    premium_breakdown = pd.DataFrame(
        [
            {"Component": "Expected loss", "Amount SAR": quote["expected_loss_sar"]},
            {"Component": "Cat load", "Amount SAR": quote["cat_load_sar"]},
            {"Component": "Capital load", "Amount SAR": quote["capital_load_sar"]},
            {"Component": "Expense load", "Amount SAR": quote["expense_load_sar"]},
            {"Component": "Profit margin", "Amount SAR": quote["profit_margin_sar"]},
            {"Component": "Technical premium", "Amount SAR": quote["technical_premium_sar"]},
        ]
    )

    indication_summary = actuarial_bundle["indications"].groupby("lob", as_index=False).agg(
        policies=("policy_id", "count"),
        avg_frequency=("glm_claim_frequency", "mean"),
        avg_severity_sar=("glm_claim_severity_sar", "mean"),
        avg_expected_loss_sar=("glm_expected_loss_sar", "mean"),
        avg_premium_sar=("glm_technical_premium_sar", "mean"),
    )
    diagnostics = pd.DataFrame([model_bundle["diagnostics"]]).T.reset_index()
    diagnostics.columns = ["Metric", "Value"]
    diagnostics["Value"] = diagnostics["Value"].astype(str)
    shap_result = explain_policy_prediction(quote["policy"], model_bundle, portfolio_df, max_features=10)

    module_df = full_capital["module_table"].copy()
    module_df["module_label"] = module_df["module"].str.replace("_", " ").str.title()
    portfolio_scr, lob_capital = _build_portfolio_capital(portfolio_df)

    comparison = runtime["scenario_comparison"].copy()
    base_scr = float(comparison.loc[comparison["scenario"] == "Base", "diversified_scr_sar"].iloc[0])
    comparison["change_vs_base_sar"] = comparison["diversified_scr_sar"] - base_scr
    comparison["change_vs_base_pct"] = comparison["change_vs_base_sar"] / max(base_scr, 1.0)

    loss_ratio = portfolio_df.groupby("lob", as_index=False).agg(
        policies=("policy_id", "count"),
        mean_loss_ratio=("loss_ratio", "mean"),
        p90_loss_ratio=("loss_ratio", lambda series: series.quantile(0.90)),
        mean_premium_sar=("technical_premium_sar", "mean"),
        mean_expected_loss_sar=("expected_loss_sar", "mean"),
    )

    return _clean_value(
        {
            "run": {
                "rows": rows,
                "seed": seed,
                "scenario": scenario_name,
                "scenario_description": SCENARIOS[scenario_name]["description"],
                "data_notice": DATA_NOTICE,
            },
            "underwriting": {
                "decision": quote["decision"],
                "recommended_premium_sar": quote["recommended_premium_sar"],
                "technical_premium_sar": quote["technical_premium_sar"],
                "risk_score": quote["risk_score"],
                "expected_loss_sar": quote["expected_loss_sar"],
                "scr_impact_sar": quote["scr_impact_sar"],
                "scr_to_premium": quote["scr_to_premium"],
                "claim_probability": quote["claim_probability"],
                "conditional_severity_sar": quote["conditional_severity_sar"],
                "model_basis": quote["model_basis"],
                "proxy_basis": quote["rbc"]["proxy_basis"],
                "premium_breakdown": _df_records(premium_breakdown),
                "pricing_reconciliation": _df_records(pd.DataFrame(quote["pricing_reconciliation"])),
                "rbc_modules": _df_records(rbc_modules),
                "rbc_diversification_benefit_sar": quote["rbc"]["diversification_benefit_sar"],
                "decision_reasons": quote["decision_reasons"],
                "decision_explanation": quote["decision_explanation"],
            },
            "data": {
                "metrics": {
                    "policies": len(portfolio_df),
                    "claim_rate": float(portfolio_df["had_claim"].mean()),
                    "mean_technical_premium_sar": float(portfolio_df["technical_premium_sar"].mean()),
                    "mean_expected_loss_sar": float(portfolio_df["expected_loss_sar"].mean()),
                },
                "metadata_coverage": _df_records(metadata_coverage(bundle)),
                "lob_counts": _df_records(portfolio_df["lob"].value_counts().rename_axis("LOB").reset_index(name="Policies")),
                "loss_ratio_by_lob": _df_records(loss_ratio),
                "table_previews": {name: _df_records(table, 30) for name, table in bundle.items()},
            },
            "actuarial": {
                "basis": actuarial_bundle["basis"],
                "diagnostics": _df_records(actuarial_bundle["diagnostics"]),
                "indication_summary": _df_records(indication_summary),
                "sample_indications": _df_records(actuarial_bundle["indications"], 40),
            },
            "diagnostics": {
                "model_diagnostics": _df_records(diagnostics),
                "frequency_importance": _df_records(feature_importance_table(model_bundle, "frequency", 15)),
                "severity_importance": _df_records(feature_importance_table(model_bundle, "loss", 15)),
                "shap_method": shap_result["method"],
                "shap_error": shap_result["error"],
                "shap_features": _df_records(shap_result["top_features"]),
            },
            "reserving": {
                "basis": reserving_result.get("basis", ""),
                "reserve_summary": _df_records(reserving_result["reserve_summary"]),
                "paid_triangle": _df_records(reserving_result["paid_triangle"]),
                "incurred_triangle": _df_records(reserving_result["incurred_triangle"]),
                "link_ratios": _df_records(reserving_result["link_ratios"]),
            },
            "capital": {
                "standalone_sum_sar": full_capital["standalone_sum_sar"],
                "diversified_scr_sar": full_capital["diversified_scr_sar"],
                "diversification_benefit_sar": full_capital["diversification_benefit_sar"],
                "module_table": _df_records(module_df[["module_label", "capital_sar"]]),
                "details": {name: _df_records(detail, 30) for name, detail in full_capital["details"].items()},
                "correlation_matrix": _correlation_rows(full_capital["correlation_matrix"]),
                "legacy_lob_capital": _df_records(lob_capital),
                "legacy_diversified_scr_sar": portfolio_scr["diversified_scr_sar"],
            },
            "scenarios": {
                "comparison": _df_records(comparison),
            },
            "rules": {
                "business_rules": business_rule_descriptions(),
                "thresholds": _threshold_rows(),
                "appetite": _appetite_rows(),
            },
            "proxy_factors": {
                "lob_factors": _df_records(pd.DataFrame.from_dict(LOB_CONFIG, orient="index").reset_index(names="LOB")),
                "three_module_correlations": _correlation_rows(
                    pd.DataFrame(DEFAULT_MODULE_CORRELATIONS).loc[
                        ["underwriting", "catastrophe", "market_credit"],
                        ["underwriting", "catastrophe", "market_credit"],
                    ]
                ),
                "expanded_correlations": _correlation_rows(pd.DataFrame(FULL_MODULE_CORRELATIONS).loc[FULL_RISK_MODULES, FULL_RISK_MODULES]),
                "scenario_assumptions": _df_records(pd.DataFrame.from_dict(SCENARIOS, orient="index").reset_index(names="Scenario")),
                "rbc_factors": _df_records(bundle["rbc_factors"]),
            },
        }
    )
