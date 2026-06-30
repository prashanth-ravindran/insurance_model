"""Configuration for the Saudi P&C risk model prototype.

The factors in this file are proxy assumptions for a prototype. They should be
replaced with official IA factors or internally approved calibration before
being used for regulatory or production pricing decisions.
"""

from __future__ import annotations

LOBS = [
    "Motor",
    "Property & Fire",
    "Engineering & Construction",
    "Marine & Cargo",
    "Casualty/Liability",
]

LOB_CONFIG = {
    "Motor": {
        "base_frequency": 0.18,
        "base_severity": 11500.0,
        "base_rate": 0.038,
        "min_premium": 750.0,
        "max_limit": 10_000_000.0,
        "underwriting_factor": 0.20,
        "cat_factor": 0.0015,
        "expense_ratio": 0.17,
        "profit_margin": 0.07,
        "cost_of_capital": 0.06,
    },
    "Property & Fire": {
        "base_frequency": 0.055,
        "base_severity": 1_250_000.0,
        "base_rate": 0.0022,
        "min_premium": 5_000.0,
        "max_limit": 5_000_000_000.0,
        "underwriting_factor": 0.13,
        "cat_factor": 0.0065,
        "expense_ratio": 0.14,
        "profit_margin": 0.08,
        "cost_of_capital": 0.06,
    },
    "Engineering & Construction": {
        "base_frequency": 0.07,
        "base_severity": 2_750_000.0,
        "base_rate": 0.0038,
        "min_premium": 15_000.0,
        "max_limit": 12_000_000_000.0,
        "underwriting_factor": 0.18,
        "cat_factor": 0.008,
        "expense_ratio": 0.15,
        "profit_margin": 0.09,
        "cost_of_capital": 0.065,
    },
    "Marine & Cargo": {
        "base_frequency": 0.075,
        "base_severity": 220_000.0,
        "base_rate": 0.0028,
        "min_premium": 3_000.0,
        "max_limit": 1_500_000_000.0,
        "underwriting_factor": 0.15,
        "cat_factor": 0.0035,
        "expense_ratio": 0.16,
        "profit_margin": 0.075,
        "cost_of_capital": 0.06,
    },
    "Casualty/Liability": {
        "base_frequency": 0.05,
        "base_severity": 650_000.0,
        "base_rate": 0.0018,
        "min_premium": 4_000.0,
        "max_limit": 2_000_000_000.0,
        "underwriting_factor": 0.16,
        "cat_factor": 0.001,
        "expense_ratio": 0.16,
        "profit_margin": 0.08,
        "cost_of_capital": 0.06,
    },
}

REGION_RISK = {
    "Riyadh": {
        "traffic_density_score": 1.25,
        "flood_zone_score": 0.85,
        "sandstorm_score": 1.15,
        "industrial_zone_score": 0.70,
        "logistics_score": 1.00,
    },
    "Jeddah": {
        "traffic_density_score": 1.20,
        "flood_zone_score": 1.40,
        "sandstorm_score": 0.90,
        "industrial_zone_score": 0.75,
        "logistics_score": 1.20,
    },
    "Dammam/Khobar": {
        "traffic_density_score": 1.10,
        "flood_zone_score": 0.80,
        "sandstorm_score": 0.95,
        "industrial_zone_score": 1.35,
        "logistics_score": 1.35,
    },
    "Jubail/Yanbu": {
        "traffic_density_score": 0.95,
        "flood_zone_score": 0.75,
        "sandstorm_score": 1.00,
        "industrial_zone_score": 1.80,
        "logistics_score": 1.25,
    },
    "Makkah/Madinah": {
        "traffic_density_score": 1.15,
        "flood_zone_score": 1.05,
        "sandstorm_score": 0.90,
        "industrial_zone_score": 0.55,
        "logistics_score": 0.90,
    },
    "NEOM/Red Sea": {
        "traffic_density_score": 0.80,
        "flood_zone_score": 1.15,
        "sandstorm_score": 1.20,
        "industrial_zone_score": 0.90,
        "logistics_score": 1.05,
    },
    "Rest of KSA": {
        "traffic_density_score": 0.80,
        "flood_zone_score": 0.90,
        "sandstorm_score": 1.05,
        "industrial_zone_score": 0.75,
        "logistics_score": 0.85,
    },
}

COUNTERPARTY_RATING_FACTORS = {
    "AAA": 0.004,
    "AA": 0.006,
    "A": 0.011,
    "BBB": 0.023,
    "BB": 0.055,
    "Unrated": 0.095,
}

DEFAULT_MODULE_CORRELATIONS = {
    "underwriting": {
        "underwriting": 1.00,
        "catastrophe": 0.25,
        "market_credit": 0.15,
    },
    "catastrophe": {
        "underwriting": 0.25,
        "catastrophe": 1.00,
        "market_credit": 0.10,
    },
    "market_credit": {
        "underwriting": 0.15,
        "catastrophe": 0.10,
        "market_credit": 1.00,
    },
}

DECISION_THRESHOLDS = {
    "quote_max_score": 68.0,
    "refer_max_score": 88.0,
    "refer_scr_to_premium": 2.75,
    "decline_min_control_score": 25.0,
    "refer_accumulation_score": 0.72,
    "refer_reinsurance_ceded_pct": 0.65,
}

DATA_NOTICE = (
    "Prototype only: portfolio data and proxy RBC factors are not a "
    "substitute for company experience data, approved pricing assumptions, or "
    "official IA capital calibration."
)

