"""Feature definitions and policy normalization helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from insurance_model.config import LOB_CONFIG, REGION_RISK

CATEGORICAL_COLUMNS = [
    "lob",
    "region",
    "policy_type",
    "vehicle_class",
    "occupancy_type",
    "project_type",
    "cargo_type",
    "liability_type",
    "counterparty_rating",
]

NUMERIC_COLUMNS = [
    "exposure_value_sar",
    "limit_sar",
    "deductible_sar",
    "term_months",
    "prior_claims_3y",
    "risk_control_score",
    "reinsurance_ceded_pct",
    "driver_age",
    "vehicle_age",
    "fleet_size",
    "occupancy_hazard_score",
    "construction_quality_score",
    "fire_protection_score",
    "project_complexity_score",
    "project_duration_months",
    "contractor_experience_years",
    "cargo_type_risk_score",
    "transit_distance_km",
    "storage_days",
    "liability_limit_factor",
    "annual_revenue_sar",
    "professional_risk_score",
    "inflation_index",
    "repair_material_index",
    "event_accumulation_score",
    "traffic_density_score",
    "flood_zone_score",
    "sandstorm_score",
    "industrial_zone_score",
    "base_rate",
]

MODEL_FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS

DEFAULT_POLICY_VALUES: dict[str, Any] = {
    "lob": "Motor",
    "region": "Riyadh",
    "policy_type": "Comprehensive",
    "vehicle_class": "Private car",
    "occupancy_type": "Residential",
    "project_type": "Civil works",
    "cargo_type": "General cargo",
    "liability_type": "General liability",
    "counterparty_rating": "A",
    "exposure_value_sar": 100_000.0,
    "limit_sar": 1_000_000.0,
    "deductible_sar": 2_500.0,
    "term_months": 12,
    "prior_claims_3y": 0,
    "risk_control_score": 70.0,
    "reinsurance_ceded_pct": 0.20,
    "driver_age": 35,
    "vehicle_age": 4,
    "fleet_size": 1,
    "occupancy_hazard_score": 0.35,
    "construction_quality_score": 0.70,
    "fire_protection_score": 0.70,
    "project_complexity_score": 0.35,
    "project_duration_months": 18,
    "contractor_experience_years": 8,
    "cargo_type_risk_score": 0.35,
    "transit_distance_km": 500,
    "storage_days": 3,
    "liability_limit_factor": 0.45,
    "annual_revenue_sar": 10_000_000.0,
    "professional_risk_score": 0.35,
    "inflation_index": 1.05,
    "repair_material_index": 1.05,
    "event_accumulation_score": 0.25,
    "traffic_density_score": 1.00,
    "flood_zone_score": 1.00,
    "sandstorm_score": 1.00,
    "industrial_zone_score": 1.00,
    "base_rate": 0.01,
}


def enrich_policy_defaults(policy: dict[str, Any]) -> dict[str, Any]:
    """Return a policy dict with all model features populated."""

    enriched = dict(DEFAULT_POLICY_VALUES)
    enriched.update({k: v for k, v in policy.items() if v is not None})

    lob = enriched.get("lob", "Motor")
    region = enriched.get("region", "Riyadh")

    lob_cfg = LOB_CONFIG.get(lob, LOB_CONFIG["Motor"])
    region_cfg = REGION_RISK.get(region, REGION_RISK["Riyadh"])

    enriched["base_rate"] = float(enriched.get("base_rate") or lob_cfg["base_rate"])
    for key, value in region_cfg.items():
        enriched[key] = float(enriched.get(key) or value)

    for column in NUMERIC_COLUMNS:
        enriched[column] = float(enriched.get(column, DEFAULT_POLICY_VALUES.get(column, 0.0)))

    for column in CATEGORICAL_COLUMNS:
        enriched[column] = str(enriched.get(column, DEFAULT_POLICY_VALUES.get(column, 0.0)))

    enriched["term_months"] = int(round(enriched["term_months"]))
    enriched["prior_claims_3y"] = int(round(enriched["prior_claims_3y"]))
    enriched["fleet_size"] = int(max(1, round(enriched["fleet_size"])))
    return enriched


def prepare_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Select and fill model feature columns from a frame."""

    prepared = df.copy()
    for column in CATEGORICAL_COLUMNS:
        if column not in prepared:
            prepared[column] = DEFAULT_POLICY_VALUES.get(column, 0.0)
        prepared[column] = prepared[column].fillna(DEFAULT_POLICY_VALUES.get(column, 0.0)).astype(str)

    for column in NUMERIC_COLUMNS:
        if column not in prepared:
            prepared[column] = DEFAULT_POLICY_VALUES.get(column, 0.0)
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce").fillna(
            DEFAULT_POLICY_VALUES.get(column, 0.0)
        )

    return prepared[MODEL_FEATURE_COLUMNS]


def policy_to_frame(policy: dict[str, Any]) -> pd.DataFrame:
    """Convert a policy dictionary to a one-row feature frame."""

    return prepare_feature_frame(pd.DataFrame([enrich_policy_defaults(policy)]))

