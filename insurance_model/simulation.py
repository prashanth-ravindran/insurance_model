"""Full simulated feed bundle for the Saudi P&C risk platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from insurance_model.config import DEFAULT_MODULE_CORRELATIONS, LOB_CONFIG, REGION_RISK
from insurance_model.data import generate_portfolio_data

SCENARIOS: dict[str, dict[str, float | str]] = {
    "Base": {
        "description": "Base case with current proxy assumptions.",
        "inflation_multiplier": 1.00,
        "repair_material_multiplier": 1.00,
        "claim_severity_multiplier": 1.00,
        "cat_frequency_multiplier": 1.00,
        "cat_severity_multiplier": 1.00,
        "traffic_multiplier": 1.00,
        "reinsurance_recoverable_multiplier": 1.00,
        "reinsurer_default_rate": 0.00,
        "interest_rate_shock_bps": 0.00,
        "credit_spread_shock_bps": 0.00,
        "accumulation_multiplier": 1.00,
    },
    "High Inflation": {
        "description": "Repair, spare-part, and construction material costs rise sharply.",
        "inflation_multiplier": 1.16,
        "repair_material_multiplier": 1.22,
        "claim_severity_multiplier": 1.18,
        "cat_frequency_multiplier": 1.00,
        "cat_severity_multiplier": 1.05,
        "traffic_multiplier": 1.02,
        "reinsurance_recoverable_multiplier": 1.00,
        "reinsurer_default_rate": 0.00,
        "interest_rate_shock_bps": 100.00,
        "credit_spread_shock_bps": 60.00,
        "accumulation_multiplier": 1.00,
    },
    "Severe Flood Year": {
        "description": "Heavy flood year affecting western and central regions.",
        "inflation_multiplier": 1.03,
        "repair_material_multiplier": 1.08,
        "claim_severity_multiplier": 1.10,
        "cat_frequency_multiplier": 1.70,
        "cat_severity_multiplier": 1.85,
        "traffic_multiplier": 1.08,
        "reinsurance_recoverable_multiplier": 1.10,
        "reinsurer_default_rate": 0.00,
        "interest_rate_shock_bps": 30.00,
        "credit_spread_shock_bps": 40.00,
        "accumulation_multiplier": 1.25,
    },
    "Sandstorm Heavy Year": {
        "description": "More severe sandstorm and windblown-dust events.",
        "inflation_multiplier": 1.02,
        "repair_material_multiplier": 1.10,
        "claim_severity_multiplier": 1.08,
        "cat_frequency_multiplier": 1.45,
        "cat_severity_multiplier": 1.35,
        "traffic_multiplier": 1.18,
        "reinsurance_recoverable_multiplier": 1.00,
        "reinsurer_default_rate": 0.00,
        "interest_rate_shock_bps": 20.00,
        "credit_spread_shock_bps": 30.00,
        "accumulation_multiplier": 1.15,
    },
    "Reinsurer Downgrade/Default": {
        "description": "Reinsurance recoverables become riskier and a small share defaults.",
        "inflation_multiplier": 1.00,
        "repair_material_multiplier": 1.00,
        "claim_severity_multiplier": 1.00,
        "cat_frequency_multiplier": 1.00,
        "cat_severity_multiplier": 1.00,
        "traffic_multiplier": 1.00,
        "reinsurance_recoverable_multiplier": 1.00,
        "reinsurer_default_rate": 0.12,
        "interest_rate_shock_bps": 75.00,
        "credit_spread_shock_bps": 180.00,
        "accumulation_multiplier": 1.00,
    },
    "Interest Rate Shock": {
        "description": "Rate and spread shock affecting market value and capital strain.",
        "inflation_multiplier": 1.00,
        "repair_material_multiplier": 1.00,
        "claim_severity_multiplier": 1.00,
        "cat_frequency_multiplier": 1.00,
        "cat_severity_multiplier": 1.00,
        "traffic_multiplier": 1.00,
        "reinsurance_recoverable_multiplier": 1.00,
        "reinsurer_default_rate": 0.00,
        "interest_rate_shock_bps": 250.00,
        "credit_spread_shock_bps": 120.00,
        "accumulation_multiplier": 1.00,
    },
    "Giga Project Accumulation": {
        "description": "Large engineering and construction packages accumulate at one event footprint.",
        "inflation_multiplier": 1.04,
        "repair_material_multiplier": 1.12,
        "claim_severity_multiplier": 1.16,
        "cat_frequency_multiplier": 1.15,
        "cat_severity_multiplier": 1.45,
        "traffic_multiplier": 1.00,
        "reinsurance_recoverable_multiplier": 1.15,
        "reinsurer_default_rate": 0.00,
        "interest_rate_shock_bps": 50.00,
        "credit_spread_shock_bps": 65.00,
        "accumulation_multiplier": 1.55,
    },
}

REQUIRED_METADATA_COLUMNS = [
    "record_id",
    "valuation_date",
    "source_type",
    "source_name",
    "production_required",
    "scenario_id",
    "seed",
]


def scenario_config(name: str = "Base", overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a normalized scenario configuration."""

    base = dict(SCENARIOS.get(name, SCENARIOS["Base"]))
    base["scenario_id"] = name
    if overrides:
        base.update(overrides)
    return base


def _add_metadata(df: pd.DataFrame, table_name: str, scenario: dict[str, Any], seed: int) -> pd.DataFrame:
    out = df.copy()
    out.insert(0, "record_id", [f"{table_name.upper()}-{i + 1:07d}" for i in range(len(out))])
    out.insert(1, "valuation_date", "2026-12-31")
    out.insert(2, "source_type", "simulated")
    out.insert(3, "source_name", table_name)
    out.insert(4, "production_required", True)
    out.insert(5, "scenario_id", str(scenario["scenario_id"]))
    out.insert(6, "seed", int(seed))
    return out


def _apply_scenario_to_policies(policies: pd.DataFrame, scenario: dict[str, Any]) -> pd.DataFrame:
    out = policies.copy()
    out["inflation_index"] *= float(scenario["inflation_multiplier"])
    out["repair_material_index"] *= float(scenario["repair_material_multiplier"])
    out["event_accumulation_score"] = np.clip(
        out["event_accumulation_score"] * float(scenario["accumulation_multiplier"]), 0, 0.99
    )
    severity_multiplier = float(scenario["claim_severity_multiplier"])
    out["severity_risk_score"] *= severity_multiplier
    out["expected_loss_sar"] *= severity_multiplier
    out["total_claim_sar"] *= severity_multiplier
    out["claim_severity_sar"] *= severity_multiplier
    out["technical_premium_sar"] *= max(1.0, severity_multiplier * 0.92)
    out["loss_ratio"] = out["total_claim_sar"] / out["technical_premium_sar"].clip(lower=1.0)
    return out


def _generate_premiums(policies: pd.DataFrame) -> pd.DataFrame:
    premiums = policies[["policy_id", "lob", "region", "term_months", "technical_premium_sar"]].copy()
    premiums["written_premium_sar"] = premiums["technical_premium_sar"]
    premiums["earned_premium_sar"] = premiums["written_premium_sar"] * np.minimum(premiums["term_months"], 12) / 12
    premiums["commission_sar"] = premiums["written_premium_sar"] * 0.08
    premiums["tax_fee_sar"] = premiums["written_premium_sar"] * 0.015
    return premiums


def _generate_exposures(policies: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "policy_id", "lob", "region", "exposure_value_sar", "limit_sar", "deductible_sar",
        "policy_type", "vehicle_class", "occupancy_type", "project_type", "cargo_type", "liability_type",
        "event_accumulation_score",
    ]
    exposures = policies[cols].copy()
    exposures["exposure_unit_id"] = [f"EXP-{i + 1:07d}" for i in range(len(exposures))]
    exposures["geocode_quality"] = np.where(exposures["region"].eq("Rest of KSA"), "regional", "city_region")
    return exposures


def _generate_claims(policies: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 101)
    rows: list[dict[str, Any]] = []
    causes = {
        "Motor": ["collision", "bodily_injury", "theft", "weather"],
        "Property & Fire": ["fire", "flood", "machinery", "escape_of_water"],
        "Engineering & Construction": ["contract_works", "delay_start_up", "machinery_breakdown", "flood"],
        "Marine & Cargo": ["transit_damage", "theft", "temperature_excursion", "port_delay"],
        "Casualty/Liability": ["third_party_injury", "professional_error", "product_liability", "directors_officers"],
    }
    claim_id = 1
    for _, policy in policies.iterrows():
        count = int(max(policy.get("claim_count", 0), 0))
        if count == 0 and rng.random() < min(float(policy["claim_frequency"]) * 0.18, 0.12):
            count = 1
        for claim_no in range(count):
            incurred = max(float(policy["total_claim_sar"]) / max(count, 1), float(policy["expected_loss_sar"]) * rng.uniform(0.15, 1.35))
            paid_pct = float(np.clip(rng.beta(2.2, 2.0), 0.05, 0.98))
            paid = incurred * paid_pct
            outstanding = max(incurred - paid, 0.0)
            accident_year = int(rng.choice([2022, 2023, 2024, 2025, 2026], p=[0.12, 0.18, 0.24, 0.25, 0.21]))
            development_year = int(np.clip(2026 - accident_year + 1, 1, 5))
            rows.append(
                {
                    "claim_id": f"CLM-{claim_id:07d}",
                    "policy_id": policy["policy_id"],
                    "lob": policy["lob"],
                    "region": policy["region"],
                    "accident_year": accident_year,
                    "development_year": development_year,
                    "claim_cause": str(rng.choice(causes[policy["lob"]])),
                    "reported_lag_days": int(rng.integers(1, 180)),
                    "paid_loss_sar": paid,
                    "case_reserve_sar": outstanding,
                    "incurred_loss_sar": incurred,
                    "claim_status": "open" if outstanding > incurred * 0.15 else "closed",
                }
            )
            claim_id += 1
    if not rows:
        rows.append(
            {
                "claim_id": "CLM-0000001",
                "policy_id": policies.iloc[0]["policy_id"],
                "lob": policies.iloc[0]["lob"],
                "region": policies.iloc[0]["region"],
                "accident_year": 2026,
                "development_year": 1,
                "claim_cause": "prototype_minimum_claim",
                "reported_lag_days": 7,
                "paid_loss_sar": 0.0,
                "case_reserve_sar": 0.0,
                "incurred_loss_sar": 0.0,
                "claim_status": "closed",
            }
        )
    return pd.DataFrame(rows)


def _generate_reinsurance(policies: pd.DataFrame, claims: pd.DataFrame, scenario: dict[str, Any], seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 202)
    claim_by_policy = claims.groupby("policy_id")["incurred_loss_sar"].sum().rename("incurred_loss_sar")
    out = policies[["policy_id", "lob", "counterparty_rating", "reinsurance_ceded_pct", "technical_premium_sar"]].merge(
        claim_by_policy, on="policy_id", how="left"
    )
    out["incurred_loss_sar"] = out["incurred_loss_sar"].fillna(0.0)
    out["treaty_type"] = np.where(out["reinsurance_ceded_pct"] > 0.45, "facultative", "quota_share")
    out["reinsurer_name"] = [f"Reinsurer {chr(65 + (i % 6))}" for i in range(len(out))]
    out["recoverable_sar"] = out["incurred_loss_sar"] * out["reinsurance_ceded_pct"] * float(scenario["reinsurance_recoverable_multiplier"])
    default_rate = float(scenario["reinsurer_default_rate"])
    out["default_flag"] = rng.random(len(out)) < default_rate
    out["expected_default_loss_sar"] = np.where(out["default_flag"], out["recoverable_sar"] * 0.65, out["recoverable_sar"] * default_rate * 0.20)
    out["collateral_pct"] = np.where(out["treaty_type"].eq("facultative"), 0.18, 0.08)
    return out


def _generate_economic_indices(scenario: dict[str, Any]) -> pd.DataFrame:
    months = pd.date_range("2024-01-01", periods=36, freq="MS")
    t = np.arange(len(months))
    inflation = 1.0 + 0.0025 * t
    repair = 1.0 + 0.0032 * t
    material = 1.0 + 0.0038 * t
    return pd.DataFrame(
        {
            "month": months.strftime("%Y-%m"),
            "cpi_index": inflation * float(scenario["inflation_multiplier"]),
            "repair_cost_index": repair * float(scenario["repair_material_multiplier"]),
            "construction_material_index": material * float(scenario["repair_material_multiplier"]),
            "medical_wage_proxy_index": (1.0 + 0.0028 * t) * float(scenario["inflation_multiplier"]),
        }
    )


def _generate_traffic_events(scenario: dict[str, Any], seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 303)
    rows = []
    vehicle_classes = ["Private car", "SUV", "Taxi/ride-hailing", "Light commercial", "Heavy truck"]
    for region, region_cfg in REGION_RISK.items():
        for vehicle_class in vehicle_classes:
            base = region_cfg["traffic_density_score"] * float(scenario["traffic_multiplier"])
            rows.append(
                {
                    "region": region,
                    "vehicle_class": vehicle_class,
                    "traffic_density_score": region_cfg["traffic_density_score"],
                    "accident_frequency_index": max(0.05, base * rng.normal(1.0, 0.08)),
                    "bodily_injury_severity_index": max(0.05, base * rng.normal(0.95, 0.10)),
                }
            )
    return pd.DataFrame(rows)


def _generate_weather_events(scenario: dict[str, Any], seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 404)
    rows = []
    months = pd.date_range("2026-01-01", periods=12, freq="MS")
    for region, cfg in REGION_RISK.items():
        for month in months:
            rows.append(
                {
                    "month": month.strftime("%Y-%m"),
                    "region": region,
                    "rainfall_index": max(0.0, cfg["flood_zone_score"] * float(scenario["cat_frequency_multiplier"]) * rng.normal(1.0, 0.20)),
                    "sandstorm_index": max(0.0, cfg["sandstorm_score"] * float(scenario["cat_frequency_multiplier"]) * rng.normal(1.0, 0.18)),
                    "heat_stress_index": max(0.0, rng.normal(1.0, 0.10)),
                    "wind_index": max(0.0, cfg["sandstorm_score"] * rng.normal(0.85, 0.15)),
                }
            )
    return pd.DataFrame(rows)


def _generate_cat_events(policies: pd.DataFrame, scenario: dict[str, Any], seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 505)
    event_types = ["flash_flood", "sandstorm", "industrial_fire_explosion", "project_clash"]
    rows = []
    for idx, event_type in enumerate(event_types, start=1):
        if event_type == "flash_flood":
            regions = ["Jeddah", "Riyadh", "Makkah/Madinah"]
            region_factor = policies["flood_zone_score"].mean()
        elif event_type == "sandstorm":
            regions = ["Riyadh", "NEOM/Red Sea", "Rest of KSA"]
            region_factor = policies["sandstorm_score"].mean()
        elif event_type == "industrial_fire_explosion":
            regions = ["Jubail/Yanbu", "Dammam/Khobar"]
            region_factor = policies["industrial_zone_score"].mean()
        else:
            regions = ["NEOM/Red Sea", "Riyadh"]
            region_factor = policies["event_accumulation_score"].mean() + 0.5
        exposed = policies[policies["region"].isin(regions)]
        exposure = float(exposed["exposure_value_sar"].sum()) if not exposed.empty else float(policies["exposure_value_sar"].sum() * 0.08)
        gross_loss = exposure * rng.uniform(0.002, 0.018) * region_factor * float(scenario["cat_severity_multiplier"])
        ceded_pct = float(exposed["reinsurance_ceded_pct"].mean()) if not exposed.empty else float(policies["reinsurance_ceded_pct"].mean())
        rows.append(
            {
                "event_id": f"CAT-{idx:04d}",
                "event_type": event_type,
                "affected_regions": ", ".join(regions),
                "return_period_years": int(rng.choice([25, 50, 100, 200], p=[0.35, 0.30, 0.22, 0.13])),
                "gross_loss_sar": gross_loss,
                "ceded_loss_sar": gross_loss * ceded_pct,
                "net_loss_sar": gross_loss * (1.0 - ceded_pct),
                "pml_sar": gross_loss * rng.uniform(1.15, 1.65),
            }
        )
    return pd.DataFrame(rows)


def _generate_market_curves(scenario: dict[str, Any]) -> pd.DataFrame:
    tenors = [1, 2, 3, 5, 7, 10]
    base_yields = [4.8, 4.65, 4.55, 4.45, 4.40, 4.35]
    rate_shock = float(scenario["interest_rate_shock_bps"]) / 10000.0
    spread_shock = float(scenario["credit_spread_shock_bps"]) / 10000.0
    return pd.DataFrame(
        {
            "tenor_years": tenors,
            "base_yield_pct": base_yields,
            "stressed_yield_pct": [y + rate_shock * 100 for y in base_yields],
            "credit_spread_bps": [80 + 8 * i for i, _ in enumerate(tenors)],
            "stressed_credit_spread_bps": [80 + 8 * i + spread_shock * 10000 for i, _ in enumerate(tenors)],
            "sar_usd_peg_assumption": "maintained",
        }
    )


def _generate_rbc_factors() -> pd.DataFrame:
    rows = []
    for lob, cfg in LOB_CONFIG.items():
        rows.append(
            {
                "lob": lob,
                "premium_risk_factor": cfg["underwriting_factor"],
                "cat_factor": cfg["cat_factor"],
                "market_credit_factor": 0.045,
                "cost_of_capital": cfg["cost_of_capital"],
                "basis": "proxy_non_regulatory",
            }
        )
    for left, right_map in DEFAULT_MODULE_CORRELATIONS.items():
        for right, value in right_map.items():
            rows.append(
                {
                    "lob": "ALL",
                    "premium_risk_factor": np.nan,
                    "cat_factor": np.nan,
                    "market_credit_factor": np.nan,
                    "cost_of_capital": np.nan,
                    "basis": f"correlation:{left}:{right}:{value}",
                }
            )
    return pd.DataFrame(rows)


def generate_simulation_bundle(
    seed: int = 42,
    rows: int = 5000,
    scenario_name: str = "Base",
    scenario_overrides: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    """Generate all simulated feeds required by the full prototype architecture."""

    scenario = scenario_config(scenario_name, scenario_overrides)
    policies = _apply_scenario_to_policies(generate_portfolio_data(rows=rows, seed=seed), scenario)
    claims = _generate_claims(policies, seed)
    tables = {
        "policies": policies,
        "premiums": _generate_premiums(policies),
        "exposures": _generate_exposures(policies),
        "claims": claims,
        "reinsurance": _generate_reinsurance(policies, claims, scenario, seed),
        "economic_indices": _generate_economic_indices(scenario),
        "traffic_events": _generate_traffic_events(scenario, seed),
        "weather_events": _generate_weather_events(scenario, seed),
        "cat_events": _generate_cat_events(policies, scenario, seed),
        "market_curves": _generate_market_curves(scenario),
        "rbc_factors": _generate_rbc_factors(),
    }
    return {name: _add_metadata(df, name, scenario, seed) for name, df in tables.items()}


def metadata_coverage(bundle: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Summarize metadata coverage across generated tables."""

    rows = []
    for table_name, df in bundle.items():
        rows.append(
            {
                "table": table_name,
                "rows": len(df),
                "has_required_metadata": all(column in df.columns for column in REQUIRED_METADATA_COLUMNS),
                "source_type": ", ".join(sorted(df["source_type"].dropna().astype(str).unique())) if "source_type" in df else "missing",
                "scenario_id": ", ".join(sorted(df["scenario_id"].dropna().astype(str).unique())) if "scenario_id" in df else "missing",
            }
        )
    return pd.DataFrame(rows)
