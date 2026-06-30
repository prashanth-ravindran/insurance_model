"""Actuarial baseline models and reserving analysis."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from insurance_model.config import LOB_CONFIG
from insurance_model.features import enrich_policy_defaults, prepare_feature_frame

ACTUARIAL_FORMULA = (
    "claim_count ~ C(lob) + C(region) + log_exposure + limit_ratio + "
    "deductible_ratio + term_years + risk_control_score + prior_claims_3y + "
    "event_accumulation_score + flood_zone_score + sandstorm_score + industrial_zone_score"
)
SEVERITY_FORMULA = ACTUARIAL_FORMULA.replace("claim_count", "avg_claim_severity_sar")


def _table(bundle_or_policies: dict[str, pd.DataFrame] | pd.DataFrame, name: str) -> pd.DataFrame:
    if isinstance(bundle_or_policies, dict):
        return bundle_or_policies[name]
    if name != "policies":
        return pd.DataFrame()
    return bundle_or_policies


def _model_frame(policies: pd.DataFrame) -> pd.DataFrame:
    frame = prepare_feature_frame(policies)
    frame = frame.join(
        policies[[c for c in ["policy_id", "claim_count", "total_claim_sar", "expected_loss_sar", "technical_premium_sar"] if c in policies]].reset_index(drop=True)
    )
    frame["claim_count"] = pd.to_numeric(frame.get("claim_count", 0), errors="coerce").fillna(0).clip(lower=0)
    total_claim = pd.to_numeric(frame.get("total_claim_sar", 0), errors="coerce").fillna(0).clip(lower=0)
    count = frame["claim_count"].clip(lower=1)
    fallback_severity = pd.to_numeric(frame.get("expected_loss_sar", 0), errors="coerce").fillna(0).clip(lower=1)
    frame["avg_claim_severity_sar"] = np.where(frame["claim_count"] > 0, total_claim / count, fallback_severity)
    frame["avg_claim_severity_sar"] = pd.Series(frame["avg_claim_severity_sar"]).clip(lower=100.0)
    frame["log_exposure"] = np.log(frame["exposure_value_sar"].clip(lower=1.0))
    frame["limit_ratio"] = (frame["limit_sar"] / frame["exposure_value_sar"].clip(lower=1.0)).clip(0, 20)
    frame["deductible_ratio"] = (frame["deductible_sar"] / frame["limit_sar"].clip(lower=1.0)).clip(0, 0.5)
    frame["term_years"] = (frame["term_months"] / 12.0).clip(0.1, 5)
    return frame


def _fit_gamma_severity(frame: pd.DataFrame):
    severity_frame = frame[frame["avg_claim_severity_sar"] > 0].copy()
    if len(severity_frame) > 2500:
        severity_frame = severity_frame.sample(2500, random_state=17)
    try:
        family = sm.families.Gamma(link=sm.families.links.Log())
    except AttributeError:
        family = sm.families.Gamma(link=sm.families.links.log())
    return smf.glm(formula=SEVERITY_FORMULA, data=severity_frame, family=family).fit(maxiter=80)


def train_actuarial_models(bundle_or_policies: dict[str, pd.DataFrame] | pd.DataFrame) -> dict[str, Any]:
    """Train transparent GLM frequency and severity baselines."""

    policies = _table(bundle_or_policies, "policies").copy()
    if policies.empty:
        raise ValueError("Policy data is empty.")

    frame = _model_frame(policies)
    fit_frame = frame.sample(4000, random_state=23) if len(frame) > 4000 else frame
    frequency_model = smf.glm(formula=ACTUARIAL_FORMULA, data=fit_frame, family=sm.families.Poisson()).fit(maxiter=80)
    severity_model = _fit_gamma_severity(fit_frame)

    freq_pred = np.asarray(frequency_model.predict(frame), dtype=float)
    sev_pred = np.asarray(severity_model.predict(frame), dtype=float)
    freq_pred = np.clip(freq_pred, 0.001, 5.0)
    sev_pred = np.clip(sev_pred, 100.0, frame["limit_sar"].to_numpy(dtype=float) * 0.95)
    deductible_relief = np.minimum(
        0.38,
        frame["deductible_sar"].to_numpy(dtype=float) / (sev_pred + frame["deductible_sar"].to_numpy(dtype=float) + 1.0) * 0.75,
    )
    expected_loss = freq_pred * sev_pred * (1.0 - deductible_relief)
    premium = np.maximum(
        [LOB_CONFIG[lob]["min_premium"] for lob in frame["lob"]],
        expected_loss / np.maximum(
            0.55,
            [1.0 - LOB_CONFIG[lob]["expense_ratio"] - LOB_CONFIG[lob]["profit_margin"] for lob in frame["lob"]],
        ),
    )

    indications = pd.DataFrame(
        {
            "policy_id": policies.get("policy_id", pd.Series(range(len(frame)))).to_numpy(),
            "lob": frame["lob"].to_numpy(),
            "region": frame["region"].to_numpy(),
            "glm_claim_frequency": freq_pred,
            "glm_claim_severity_sar": sev_pred,
            "glm_expected_loss_sar": expected_loss,
            "glm_technical_premium_sar": premium,
        }
    )
    indications["glm_loss_ratio"] = indications["glm_expected_loss_sar"] / indications["glm_technical_premium_sar"].clip(lower=1.0)

    diagnostics = pd.DataFrame(
        [
            {
                "model": "Poisson GLM frequency",
                "rows_fit": int(len(fit_frame)),
                "target": "claim_count",
                "aic": float(frequency_model.aic),
                "deviance": float(frequency_model.deviance),
                "basis": "Transparent actuarial baseline for claim frequency.",
            },
            {
                "model": "Gamma GLM severity",
                "rows_fit": int(len(fit_frame)),
                "target": "average claim severity",
                "aic": float(severity_model.aic),
                "deviance": float(severity_model.deviance),
                "basis": "Transparent actuarial baseline for conditional claim severity.",
            },
        ]
    )

    return {
        "frequency_model": frequency_model,
        "severity_model": severity_model,
        "indications": indications,
        "diagnostics": diagnostics,
        "basis": "Statsmodels GLM baseline: Poisson frequency and Gamma severity.",
    }


def predict_actuarial_policy(policy: dict[str, Any], actuarial_bundle: dict[str, Any]) -> dict[str, float]:
    """Predict GLM frequency, severity, and expected loss for one policy."""

    enriched = enrich_policy_defaults(policy)
    frame = _model_frame(pd.DataFrame([enriched]))
    freq = float(np.clip(actuarial_bundle["frequency_model"].predict(frame)[0], 0.001, 5.0))
    severity = float(np.clip(actuarial_bundle["severity_model"].predict(frame)[0], 100.0, enriched["limit_sar"] * 0.95))
    deductible_relief = min(0.38, enriched["deductible_sar"] / (severity + enriched["deductible_sar"] + 1.0) * 0.75)
    expected_loss = freq * severity * (1.0 - deductible_relief)
    return {
        "claim_frequency": freq,
        "conditional_severity_sar": severity,
        "expected_loss_sar": max(expected_loss, 0.0),
    }


def _latest_cumulative(row: pd.Series) -> tuple[int, float]:
    positive = row[row > 0]
    if positive.empty:
        return 1, 0.0
    return int(positive.index.max()), float(positive.iloc[-1])


def build_reserving_analysis(bundle_or_claims: dict[str, pd.DataFrame] | pd.DataFrame) -> dict[str, Any]:
    """Build chain-ladder style paid/incurred triangles and reserve summary."""

    if isinstance(bundle_or_claims, dict):
        claims = bundle_or_claims.get("claims", pd.DataFrame()).copy()
        premiums = bundle_or_claims.get("premiums", pd.DataFrame()).copy()
        policies = bundle_or_claims.get("policies", pd.DataFrame()).copy()
    else:
        claims = bundle_or_claims.copy()
        premiums = pd.DataFrame()
        policies = pd.DataFrame()

    if claims.empty:
        empty = pd.DataFrame()
        return {"paid_triangle": empty, "incurred_triangle": empty, "link_ratios": empty, "reserve_summary": empty}

    for column in ["paid_loss_sar", "incurred_loss_sar", "case_reserve_sar"]:
        claims[column] = pd.to_numeric(claims[column], errors="coerce").fillna(0).clip(lower=0)
    claims["accident_year"] = pd.to_numeric(claims["accident_year"], errors="coerce").fillna(2026).astype(int)
    claims["development_year"] = pd.to_numeric(claims["development_year"], errors="coerce").fillna(1).astype(int).clip(lower=1)

    max_dev = int(max(2, claims["development_year"].max()))
    dev_cols = list(range(1, max_dev + 1))

    paid_incremental = claims.pivot_table(
        index="accident_year", columns="development_year", values="paid_loss_sar", aggfunc="sum", fill_value=0.0
    ).reindex(columns=dev_cols, fill_value=0.0)
    incurred_incremental = claims.pivot_table(
        index="accident_year", columns="development_year", values="incurred_loss_sar", aggfunc="sum", fill_value=0.0
    ).reindex(columns=dev_cols, fill_value=0.0)
    paid_triangle = paid_incremental.cumsum(axis=1)
    incurred_triangle = incurred_incremental.cumsum(axis=1)

    ratios = []
    for dev in dev_cols[:-1]:
        current = paid_triangle[dev]
        nxt = paid_triangle[dev + 1]
        mask = current > 0
        selected = float(nxt[mask].sum() / current[mask].sum()) if mask.any() and current[mask].sum() > 0 else 1.0
        selected = max(selected, 1.0)
        ratios.append({"development_from": dev, "development_to": dev + 1, "selected_link_ratio": selected})
    link_ratios = pd.DataFrame(ratios)

    cdf_by_dev = {}
    for dev in dev_cols:
        cdf = 1.0
        for row in ratios:
            if row["development_from"] >= dev:
                cdf *= row["selected_link_ratio"]
        cdf_by_dev[dev] = cdf

    case_by_lob = claims.groupby("lob", dropna=False)["case_reserve_sar"].sum()
    paid_by_lob = claims.groupby("lob", dropna=False)["paid_loss_sar"].sum()
    incurred_by_lob = claims.groupby("lob", dropna=False)["incurred_loss_sar"].sum()

    reserve_rows = []
    for lob, lob_claims in claims.groupby("lob", dropna=False):
        latest_paid = 0.0
        ultimate = 0.0
        for accident_year, ay_claims in lob_claims.groupby("accident_year"):
            ay_paid = paid_triangle.loc[accident_year] if accident_year in paid_triangle.index else pd.Series(dtype=float)
            latest_dev, latest_value = _latest_cumulative(ay_paid)
            latest_paid += latest_value
            ultimate += latest_value * cdf_by_dev.get(latest_dev, 1.0)
        chain_ladder_reserve = max(ultimate - latest_paid, 0.0)
        earned_premium = 0.0
        expected_loss = 0.0
        if not premiums.empty:
            earned_premium = float(premiums.loc[premiums["lob"] == lob, "earned_premium_sar"].sum())
        if not policies.empty:
            expected_loss = float(policies.loc[policies["lob"] == lob, "expected_loss_sar"].sum())
        bf_reserve = max(expected_loss - paid_by_lob.get(lob, 0.0), 0.0) * 0.45 + case_by_lob.get(lob, 0.0) * 0.55
        selected_reserve = max(case_by_lob.get(lob, 0.0), 0.55 * chain_ladder_reserve + 0.45 * bf_reserve)
        reserve_rows.append(
            {
                "lob": lob,
                "paid_loss_sar": float(paid_by_lob.get(lob, 0.0)),
                "incurred_loss_sar": float(incurred_by_lob.get(lob, 0.0)),
                "case_reserve_sar": float(case_by_lob.get(lob, 0.0)),
                "chain_ladder_reserve_sar": float(chain_ladder_reserve),
                "bornhuetter_ferguson_reserve_sar": float(bf_reserve),
                "selected_reserve_sar": float(selected_reserve),
                "earned_premium_sar": earned_premium,
            }
        )

    reserve_summary = pd.DataFrame(reserve_rows).sort_values("lob").reset_index(drop=True)
    paid_out = paid_triangle.reset_index()
    incurred_out = incurred_triangle.reset_index()
    paid_out.columns = [str(column) for column in paid_out.columns]
    incurred_out.columns = [str(column) for column in incurred_out.columns]
    return {
        "paid_triangle": paid_out,
        "incurred_triangle": incurred_out,
        "link_ratios": link_ratios,
        "reserve_summary": reserve_summary,
        "basis": "Paid chain ladder with Bornhuetter-Ferguson and case reserve cross-checks.",
    }
