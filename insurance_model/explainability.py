"""Model explainability helpers using SHAP where possible."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shap

from insurance_model.features import policy_to_frame, prepare_feature_frame


def _feature_names(pipeline) -> np.ndarray:
    preprocessor = pipeline.named_steps["preprocess"]
    try:
        return preprocessor.get_feature_names_out()
    except Exception:
        return np.array([f"feature_{i}" for i in range(preprocessor.transformers_.shape[0])])


def _to_dense(matrix):
    return matrix.toarray() if hasattr(matrix, "toarray") else matrix


def feature_importance_table(bundle: dict[str, Any], target: str = "frequency", max_features: int = 20) -> pd.DataFrame:
    """Return model feature importance from the fitted tree model."""

    key = "frequency_model" if target == "frequency" else "loss_model"
    pipeline = bundle[key]
    estimator = pipeline.named_steps["model"]
    names = _feature_names(pipeline)
    importances = getattr(estimator, "feature_importances_", np.zeros(len(names)))
    out = pd.DataFrame({"feature": names, "importance": importances})
    out["importance"] = pd.to_numeric(out["importance"], errors="coerce").fillna(0.0)
    return out.sort_values("importance", ascending=False).head(max_features).reset_index(drop=True)


def explain_policy_prediction(
    policy: dict[str, Any],
    bundle: dict[str, Any],
    background: pd.DataFrame | None = None,
    max_features: int = 8,
) -> dict[str, Any]:
    """Explain a policy claim-probability prediction with SHAP, falling back to importances."""

    pipeline = bundle["frequency_model"]
    preprocessor = pipeline.named_steps["preprocess"]
    estimator = pipeline.named_steps["model"]
    names = _feature_names(pipeline)
    row = _to_dense(preprocessor.transform(policy_to_frame(policy)))

    try:
        try:
            explainer = shap.TreeExplainer(estimator, feature_perturbation="tree_path_dependent")
            values = explainer.shap_values(row, check_additivity=False)
        except TypeError:
            explainer = shap.TreeExplainer(estimator, feature_perturbation="tree_path_dependent")
            values = explainer.shap_values(row)
        except Exception:
            if background is not None and not background.empty:
                bg = background.sample(min(len(background), 120), random_state=31)
                transformed_bg = _to_dense(preprocessor.transform(prepare_feature_frame(bg)))
                explainer = shap.TreeExplainer(estimator, transformed_bg, feature_perturbation="interventional")
            else:
                explainer = shap.TreeExplainer(estimator)
            try:
                values = explainer.shap_values(row, check_additivity=False)
            except TypeError:
                values = explainer.shap_values(row)
        if isinstance(values, list):
            values = values[1] if len(values) > 1 else values[0]
        values = np.asarray(values)
        if values.ndim == 3:
            values = values[0, :, min(1, values.shape[2] - 1)]
        elif values.ndim == 2:
            values = values[0]
        shap_df = pd.DataFrame({"feature": names, "contribution": values})
        shap_df["absolute_contribution"] = shap_df["contribution"].abs()
        top = shap_df.sort_values("absolute_contribution", ascending=False).head(max_features).reset_index(drop=True)
        return {"method": "SHAP TreeExplainer", "top_features": top, "error": None}
    except Exception as exc:
        fallback = feature_importance_table(bundle, "frequency", max_features).rename(columns={"importance": "absolute_contribution"})
        fallback["contribution"] = fallback["absolute_contribution"]
        return {"method": "Feature importance fallback", "top_features": fallback, "error": str(exc)}
