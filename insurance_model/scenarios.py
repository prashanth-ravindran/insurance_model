"""Scenario generation and comparison."""

from __future__ import annotations

import pandas as pd

from insurance_model.actuarial import build_reserving_analysis
from insurance_model.capital import calculate_full_scr
from insurance_model.simulation import SCENARIOS, generate_simulation_bundle


def run_scenario(seed: int = 42, rows: int = 5000, scenario_name: str = "Base") -> dict[str, object]:
    """Generate feeds and capital for a single scenario."""

    bundle = generate_simulation_bundle(seed=seed, rows=rows, scenario_name=scenario_name)
    reserving = build_reserving_analysis(bundle)
    capital = calculate_full_scr(bundle, reserving)
    return {"bundle": bundle, "reserving": reserving, "capital": capital}


def scenario_comparison(
    seed: int = 42,
    rows: int = 5000,
    scenario_names: list[str] | None = None,
) -> pd.DataFrame:
    """Compare SCR outcomes across scenarios."""

    names = scenario_names or list(SCENARIOS)
    records = []
    for name in names:
        result = run_scenario(seed=seed, rows=rows, scenario_name=name)
        capital = result["capital"]
        modules = capital["module_capitals"]
        records.append(
            {
                "scenario": name,
                "description": SCENARIOS[name]["description"],
                "standalone_sum_sar": capital["standalone_sum_sar"],
                "diversified_scr_sar": capital["diversified_scr_sar"],
                "diversification_benefit_sar": capital["diversification_benefit_sar"],
                "premium_risk_sar": modules["premium_risk"],
                "reserve_risk_sar": modules["reserve_risk"],
                "catastrophe_risk_sar": modules["catastrophe_risk"],
                "reinsurance_credit_risk_sar": modules["reinsurance_credit_risk"],
                "market_risk_sar": modules["market_risk"],
            }
        )
    return pd.DataFrame(records)
