"""Pricing reconciliation across underwriting rules, GLM, and ML."""

from __future__ import annotations

from typing import Any

from insurance_model.actuarial import predict_actuarial_policy
from insurance_model.model import predict_policy
from insurance_model.underwriting import quote_policy


def price_policy(
    policy: dict[str, Any],
    model_bundle: dict[str, Any] | None = None,
    actuarial_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Quote a policy and attach actuarial/ML reconciliation details."""

    quote = quote_policy(policy, model_bundle=model_bundle)
    indications: dict[str, Any] = {
        "selected_expected_loss_sar": quote["expected_loss_sar"],
        "selected_claim_probability": quote["claim_probability"],
        "technical_premium_sar": quote["technical_premium_sar"],
        "basis": quote["model_basis"],
    }

    if model_bundle is not None:
        try:
            ml_prediction = predict_policy(policy, model_bundle)
            indications["ml"] = {
                "claim_probability": ml_prediction["claim_probability"],
                "conditional_severity_sar": ml_prediction["conditional_severity_sar"],
                "expected_loss_sar": ml_prediction["expected_loss_sar"],
            }
        except Exception as exc:
            indications["ml_error"] = str(exc)

    if actuarial_bundle is not None:
        try:
            actuarial_prediction = predict_actuarial_policy(policy, actuarial_bundle)
            indications["actuarial_glm"] = actuarial_prediction
        except Exception as exc:
            indications["actuarial_error"] = str(exc)

    reconciliation = []
    if "actuarial_glm" in indications:
        actuarial_loss = indications["actuarial_glm"]["expected_loss_sar"]
        reconciliation.append(
            {
                "source": "Actuarial GLM",
                "expected_loss_sar": actuarial_loss,
                "difference_from_selected_sar": actuarial_loss - quote["expected_loss_sar"],
            }
        )
    if "ml" in indications:
        ml_loss = indications["ml"]["expected_loss_sar"]
        reconciliation.append(
            {
                "source": "Predictive ML",
                "expected_loss_sar": ml_loss,
                "difference_from_selected_sar": ml_loss - quote["expected_loss_sar"],
            }
        )
    reconciliation.append(
        {
            "source": "Selected pricing view",
            "expected_loss_sar": quote["expected_loss_sar"],
            "difference_from_selected_sar": 0.0,
        }
    )

    quote["indications"] = indications
    quote["pricing_reconciliation"] = reconciliation
    return quote
