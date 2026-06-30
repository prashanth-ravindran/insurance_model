"""Saudi P&C portfolio data generation."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from insurance_model.config import LOB_CONFIG, LOBS, REGION_RISK

REGIONS = list(REGION_RISK)
RATINGS = ["AAA", "AA", "A", "BBB", "BB", "Unrated"]


def _choice(rng: np.random.Generator, values: list, probabilities: list[float] | None = None):
    return rng.choice(values, p=probabilities)


def _lognormal_from_mean(
    rng: np.random.Generator,
    mean: float,
    sigma: float,
) -> float:
    mean = max(mean, 1.0)
    return float(rng.lognormal(math.log(mean) - 0.5 * sigma * sigma, sigma))


def _bounded_beta(
    rng: np.random.Generator,
    low: float,
    high: float,
    alpha: float = 2.0,
    beta: float = 2.0,
) -> float:
    return float(low + (high - low) * rng.beta(alpha, beta))


def _lob_sequence(rng: np.random.Generator, rows: int) -> np.ndarray:
    weights = np.array([0.38, 0.19, 0.17, 0.12, 0.14], dtype=float)
    lobs = rng.choice(LOBS, size=rows, p=weights)
    if rows >= len(LOBS):
        lobs[: len(LOBS)] = LOBS
        rng.shuffle(lobs)
    return lobs


def generate_portfolio_data(rows: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Generate Saudi P&C exposure, claims, and pricing data."""

    rng = np.random.default_rng(seed)
    lobs = _lob_sequence(rng, rows)
    records = []

    for idx, lob in enumerate(lobs, start=1):
        region = str(
            _choice(
                rng,
                REGIONS,
                [0.26, 0.20, 0.15, 0.09, 0.12, 0.10, 0.08],
            )
        )
        cfg = LOB_CONFIG[lob]
        region_cfg = REGION_RISK[region]

        term_months = int(_choice(rng, [6, 12, 18, 24], [0.12, 0.72, 0.08, 0.08]))
        prior_claims = int(min(rng.poisson(0.45), 5))
        risk_control_score = float(np.clip(rng.normal(68, 16), 15, 98))
        inflation_index = float(np.clip(rng.normal(1.055, 0.035), 0.98, 1.18))
        repair_material_index = float(np.clip(rng.normal(1.07, 0.045), 0.99, 1.22))
        rating = str(_choice(rng, RATINGS, [0.08, 0.22, 0.38, 0.22, 0.07, 0.03]))

        base = {
            "policy_id": f"POL-{idx:06d}",
            "lob": lob,
            "region": region,
            "term_months": term_months,
            "prior_claims_3y": prior_claims,
            "risk_control_score": risk_control_score,
            "counterparty_rating": rating,
            "inflation_index": inflation_index,
            "repair_material_index": repair_material_index,
            "traffic_density_score": region_cfg["traffic_density_score"],
            "flood_zone_score": region_cfg["flood_zone_score"],
            "sandstorm_score": region_cfg["sandstorm_score"],
            "industrial_zone_score": region_cfg["industrial_zone_score"],
            "base_rate": cfg["base_rate"],
        }

        if lob == "Motor":
            fleet_size = int(max(1, rng.geometric(0.48)))
            vehicle_age = float(np.clip(rng.normal(5.2, 3.2), 0, 18))
            driver_age = float(np.clip(rng.normal(36, 11), 18, 75))
            vehicle_class = str(
                _choice(
                    rng,
                    ["Private car", "SUV", "Taxi/ride-hailing", "Light commercial", "Heavy truck"],
                    [0.46, 0.24, 0.08, 0.16, 0.06],
                )
            )
            class_factor = {
                "Private car": 1.0,
                "SUV": 1.12,
                "Taxi/ride-hailing": 1.55,
                "Light commercial": 1.35,
                "Heavy truck": 1.85,
            }[vehicle_class]
            exposure = _lognormal_from_mean(rng, 85_000 * fleet_size * class_factor, 0.55)
            limit = float(_choice(rng, [500_000, 1_000_000, 2_000_000, 5_000_000], [0.24, 0.55, 0.16, 0.05]))
            deductible = float(_choice(rng, [500, 1_000, 2_500, 5_000], [0.22, 0.42, 0.27, 0.09]))
            ceded = _bounded_beta(rng, 0.02, 0.24)
            policy_type = str(_choice(rng, ["Compulsory", "Comprehensive"], [0.42, 0.58]))
            complexity = class_factor * (1.0 + vehicle_age / 22.0) * (1.0 + max(0, 25 - driver_age) / 35.0)
            event_accumulation = min(0.95, 0.08 + fleet_size / 60.0)
            extra = {
                "policy_type": policy_type,
                "vehicle_class": vehicle_class,
                "driver_age": driver_age,
                "vehicle_age": vehicle_age,
                "fleet_size": fleet_size,
                "occupancy_type": "N/A",
                "project_type": "N/A",
                "cargo_type": "N/A",
                "liability_type": "N/A",
                "occupancy_hazard_score": 0.0,
                "construction_quality_score": 0.0,
                "fire_protection_score": 0.0,
                "project_complexity_score": 0.0,
                "project_duration_months": 0.0,
                "contractor_experience_years": 0.0,
                "cargo_type_risk_score": 0.0,
                "transit_distance_km": 0.0,
                "storage_days": 0.0,
                "liability_limit_factor": 0.0,
                "annual_revenue_sar": 0.0,
                "professional_risk_score": 0.0,
            }

        elif lob == "Property & Fire":
            occupancy_type = str(
                _choice(
                    rng,
                    ["Residential", "Retail", "Warehouse", "Manufacturing", "Petrochemical support"],
                    [0.22, 0.22, 0.21, 0.23, 0.12],
                )
            )
            hazard = {
                "Residential": 0.25,
                "Retail": 0.38,
                "Warehouse": 0.52,
                "Manufacturing": 0.70,
                "Petrochemical support": 0.86,
            }[occupancy_type]
            exposure = _lognormal_from_mean(rng, 95_000_000 * (1 + hazard), 1.0)
            limit = min(_lognormal_from_mean(rng, exposure * rng.uniform(0.45, 1.2), 0.45), cfg["max_limit"])
            deductible = max(10_000.0, limit * rng.uniform(0.001, 0.015))
            ceded = _bounded_beta(rng, 0.20, 0.72)
            fire_protection = float(np.clip(rng.normal(0.70 - hazard * 0.15, 0.18), 0.15, 0.98))
            construction_quality = float(np.clip(rng.normal(0.68, 0.17), 0.18, 0.98))
            complexity = (1.0 + hazard) * (1.25 - 0.35 * fire_protection)
            event_accumulation = float(np.clip(hazard * 0.65 + exposure / 2_500_000_000, 0.08, 0.95))
            extra = {
                "policy_type": "Commercial property",
                "vehicle_class": "N/A",
                "driver_age": 0.0,
                "vehicle_age": 0.0,
                "fleet_size": 1,
                "occupancy_type": occupancy_type,
                "project_type": "N/A",
                "cargo_type": "N/A",
                "liability_type": "N/A",
                "occupancy_hazard_score": hazard,
                "construction_quality_score": construction_quality,
                "fire_protection_score": fire_protection,
                "project_complexity_score": 0.0,
                "project_duration_months": 0.0,
                "contractor_experience_years": 0.0,
                "cargo_type_risk_score": 0.0,
                "transit_distance_km": 0.0,
                "storage_days": 0.0,
                "liability_limit_factor": 0.0,
                "annual_revenue_sar": 0.0,
                "professional_risk_score": 0.0,
            }

        elif lob == "Engineering & Construction":
            project_type = str(
                _choice(
                    rng,
                    ["Civil works", "Power/renewables", "Metro/rail", "Industrial plant", "Giga-project package"],
                    [0.24, 0.20, 0.14, 0.22, 0.20],
                )
            )
            project_risk = {
                "Civil works": 0.36,
                "Power/renewables": 0.48,
                "Metro/rail": 0.62,
                "Industrial plant": 0.76,
                "Giga-project package": 0.84,
            }[project_type]
            duration = float(_choice(rng, [12, 18, 24, 36, 48, 60], [0.08, 0.18, 0.27, 0.24, 0.15, 0.08]))
            contractor_experience = float(np.clip(rng.normal(9, 5), 1, 30))
            exposure = _lognormal_from_mean(rng, 850_000_000 * (0.55 + project_risk), 0.95)
            limit = min(_lognormal_from_mean(rng, exposure * rng.uniform(0.35, 1.05), 0.42), cfg["max_limit"])
            deductible = max(50_000.0, limit * rng.uniform(0.0025, 0.025))
            ceded = _bounded_beta(rng, 0.38, 0.82)
            complexity = 1.0 + project_risk + duration / 80.0 - min(contractor_experience, 25) / 90.0
            event_accumulation = float(np.clip(0.18 + project_risk * 0.72 + exposure / 15_000_000_000, 0.10, 0.98))
            extra = {
                "policy_type": "CAR/EAR",
                "vehicle_class": "N/A",
                "driver_age": 0.0,
                "vehicle_age": 0.0,
                "fleet_size": 1,
                "occupancy_type": "N/A",
                "project_type": project_type,
                "cargo_type": "N/A",
                "liability_type": "N/A",
                "occupancy_hazard_score": 0.0,
                "construction_quality_score": 0.0,
                "fire_protection_score": 0.0,
                "project_complexity_score": project_risk,
                "project_duration_months": duration,
                "contractor_experience_years": contractor_experience,
                "cargo_type_risk_score": 0.0,
                "transit_distance_km": 0.0,
                "storage_days": 0.0,
                "liability_limit_factor": 0.0,
                "annual_revenue_sar": 0.0,
                "professional_risk_score": 0.0,
            }

        elif lob == "Marine & Cargo":
            cargo_type = str(
                _choice(
                    rng,
                    ["General cargo", "Electronics", "Pharma/cold chain", "Project cargo", "Hazardous cargo"],
                    [0.34, 0.20, 0.12, 0.20, 0.14],
                )
            )
            cargo_risk = {
                "General cargo": 0.30,
                "Electronics": 0.48,
                "Pharma/cold chain": 0.58,
                "Project cargo": 0.66,
                "Hazardous cargo": 0.82,
            }[cargo_type]
            distance = float(np.clip(rng.normal(900, 520), 50, 4500))
            storage_days = float(np.clip(rng.exponential(5), 0, 45))
            exposure = _lognormal_from_mean(rng, 22_000_000 * (0.8 + cargo_risk), 0.85)
            limit = min(_lognormal_from_mean(rng, exposure * rng.uniform(0.55, 1.1), 0.38), cfg["max_limit"])
            deductible = max(5_000.0, limit * rng.uniform(0.001, 0.02))
            ceded = _bounded_beta(rng, 0.12, 0.58)
            complexity = 1.0 + cargo_risk + distance / 5000.0 + storage_days / 70.0
            event_accumulation = float(np.clip(0.10 + cargo_risk * 0.45 + storage_days / 85.0, 0.05, 0.92))
            extra = {
                "policy_type": "Single transit/open cover",
                "vehicle_class": "N/A",
                "driver_age": 0.0,
                "vehicle_age": 0.0,
                "fleet_size": 1,
                "occupancy_type": "N/A",
                "project_type": "N/A",
                "cargo_type": cargo_type,
                "liability_type": "N/A",
                "occupancy_hazard_score": 0.0,
                "construction_quality_score": 0.0,
                "fire_protection_score": 0.0,
                "project_complexity_score": 0.0,
                "project_duration_months": 0.0,
                "contractor_experience_years": 0.0,
                "cargo_type_risk_score": cargo_risk,
                "transit_distance_km": distance,
                "storage_days": storage_days,
                "liability_limit_factor": 0.0,
                "annual_revenue_sar": 0.0,
                "professional_risk_score": 0.0,
            }

        else:
            liability_type = str(
                _choice(
                    rng,
                    ["General liability", "Professional indemnity", "D&O", "Product liability"],
                    [0.42, 0.24, 0.18, 0.16],
                )
            )
            professional_risk = {
                "General liability": 0.34,
                "Professional indemnity": 0.62,
                "D&O": 0.72,
                "Product liability": 0.56,
            }[liability_type]
            annual_revenue = _lognormal_from_mean(rng, 95_000_000 * (1 + professional_risk), 1.05)
            limit_factor = float(np.clip(rng.beta(2.4, 2.8), 0.10, 0.96))
            exposure = annual_revenue
            limit = min(max(1_000_000.0, annual_revenue * limit_factor * rng.uniform(0.04, 0.22)), cfg["max_limit"])
            deductible = max(10_000.0, limit * rng.uniform(0.002, 0.018))
            ceded = _bounded_beta(rng, 0.18, 0.65)
            complexity = 1.0 + professional_risk + limit_factor * 0.45
            event_accumulation = float(np.clip(0.12 + professional_risk * 0.42 + limit_factor * 0.20, 0.06, 0.88))
            extra = {
                "policy_type": "Liability",
                "vehicle_class": "N/A",
                "driver_age": 0.0,
                "vehicle_age": 0.0,
                "fleet_size": 1,
                "occupancy_type": "N/A",
                "project_type": "N/A",
                "cargo_type": "N/A",
                "liability_type": liability_type,
                "occupancy_hazard_score": 0.0,
                "construction_quality_score": 0.0,
                "fire_protection_score": 0.0,
                "project_complexity_score": 0.0,
                "project_duration_months": 0.0,
                "contractor_experience_years": 0.0,
                "cargo_type_risk_score": 0.0,
                "transit_distance_km": 0.0,
                "storage_days": 0.0,
                "liability_limit_factor": limit_factor,
                "annual_revenue_sar": annual_revenue,
                "professional_risk_score": professional_risk,
            }

        exposure = float(max(exposure, 10_000.0))
        limit = float(max(limit, 100_000.0))
        deductible = float(max(min(deductible, limit * 0.25), 0.0))
        ceded = float(min(max(ceded, 0.0), 0.95))

        region_multiplier = (
            0.38 * region_cfg["traffic_density_score"]
            + 0.22 * region_cfg["flood_zone_score"]
            + 0.17 * region_cfg["sandstorm_score"]
            + 0.23 * region_cfg["industrial_zone_score"]
        )
        control_modifier = 1.42 - 0.0064 * risk_control_score
        prior_modifier = 1.0 + 0.18 * prior_claims
        term_modifier = term_months / 12.0
        frequency = cfg["base_frequency"] * region_multiplier * control_modifier * prior_modifier * complexity * term_modifier
        frequency = float(np.clip(frequency, 0.002, 1.85))

        severity_factor = (
            complexity
            * (0.60 + min(exposure / max(limit, 1.0), 4.0) * 0.14)
            * inflation_index
            * repair_material_index
        )
        expected_severity = min(cfg["base_severity"] * severity_factor, limit * 0.92)
        deductible_relief = min(0.38, deductible / (expected_severity + deductible + 1.0) * 0.75)
        expected_loss = frequency * expected_severity * (1.0 - deductible_relief)

        claim_count = int(rng.poisson(frequency))
        claim_severity = 0.0
        total_claim = 0.0
        if claim_count > 0:
            sigma = 0.78 if lob in {"Motor", "Marine & Cargo"} else 1.05
            gross = sum(_lognormal_from_mean(rng, expected_severity, sigma) for _ in range(claim_count))
            claim_severity = gross / claim_count
            total_claim = max(0.0, min(gross - deductible * claim_count, limit))

        cat_load = exposure * cfg["cat_factor"] * 0.18 * max(
            region_cfg["flood_zone_score"],
            region_cfg["sandstorm_score"],
            region_cfg["industrial_zone_score"],
        ) * (0.5 + event_accumulation) * (1.0 - 0.45 * ceded)
        base_pricing_cost = expected_loss + max(cat_load, expected_loss * 0.025)
        technical_premium = max(
            cfg["min_premium"],
            base_pricing_cost / max(0.55, 1.0 - cfg["expense_ratio"] - cfg["profit_margin"]),
        )

        records.append(
            {
                **base,
                **extra,
                "exposure_value_sar": exposure,
                "limit_sar": limit,
                "deductible_sar": deductible,
                "reinsurance_ceded_pct": ceded,
                "event_accumulation_score": event_accumulation,
                "frequency_risk_score": frequency,
                "severity_risk_score": expected_severity,
                "claim_frequency": frequency,
                "claim_count": claim_count,
                "had_claim": int(claim_count > 0),
                "claim_severity_sar": claim_severity,
                "total_claim_sar": total_claim,
                "expected_loss_sar": expected_loss,
                "technical_premium_sar": technical_premium,
                "loss_ratio": total_claim / technical_premium if technical_premium else 0.0,
            }
        )

    return pd.DataFrame.from_records(records)

