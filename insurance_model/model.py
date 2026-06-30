"""ML training and prediction helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from insurance_model.features import (
    CATEGORICAL_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    policy_to_frame,
    prepare_feature_frame,
)


def _preprocessor() -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_COLUMNS),
            ("cat", categorical_pipeline, CATEGORICAL_COLUMNS),
        ]
    )


def _split_targets(df: pd.DataFrame, random_state: int):
    X = prepare_feature_frame(df)
    y_frequency = df["had_claim"].astype(int)
    y_loss = np.log1p(df["total_claim_sar"].clip(lower=0.0))
    stratify = y_frequency if y_frequency.nunique() > 1 and len(df) >= 200 else None
    return train_test_split(
        X,
        y_frequency,
        y_loss,
        test_size=0.22,
        random_state=random_state,
        stratify=stratify,
    )


def _diagnostics(
    df: pd.DataFrame,
    frequency_model: Pipeline,
    loss_model: Pipeline,
    X_test: pd.DataFrame,
    y_freq_test: pd.Series,
    y_loss_test: pd.Series,
    model_type: str,
) -> dict[str, Any]:
    freq_prob = frequency_model.predict_proba(X_test)[:, 1]
    try:
        auc = float(roc_auc_score(y_freq_test, freq_prob))
    except ValueError:
        auc = float("nan")

    loss_pred = loss_model.predict(X_test)
    rmse_log = float(np.sqrt(mean_squared_error(y_loss_test, loss_pred)))
    return {
        "rows": int(len(df)),
        "claim_rate": float(df["had_claim"].astype(int).mean()),
        "frequency_auc": auc,
        "loss_rmse_log": rmse_log,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_type": model_type,
        "basis": f"{model_type} trained on portfolio data.",
    }


def _build_bundle(
    df: pd.DataFrame,
    frequency_model: Pipeline,
    loss_model: Pipeline,
    X_test: pd.DataFrame,
    y_freq_test: pd.Series,
    y_loss_test: pd.Series,
    model_type: str,
    artifact_dir: str | Path | None,
) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "frequency_model": frequency_model,
        "loss_model": loss_model,
        "feature_columns": MODEL_FEATURE_COLUMNS,
        "diagnostics": _diagnostics(df, frequency_model, loss_model, X_test, y_freq_test, y_loss_test, model_type),
    }

    if artifact_dir is not None:
        path = Path(artifact_dir)
        path.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, path / "model_bundle.joblib")

    return bundle


def train_models(
    df: pd.DataFrame,
    artifact_dir: str | Path | None = None,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train baseline random-forest frequency and severity models."""

    if df.empty:
        raise ValueError("Training data is empty.")

    X_train, X_test, y_freq_train, y_freq_test, y_loss_train, y_loss_test = _split_targets(df, random_state)

    frequency_model = Pipeline(
        steps=[
            ("preprocess", _preprocessor()),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=9,
                    min_samples_leaf=18,
                    class_weight="balanced_subsample",
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    loss_model = Pipeline(
        steps=[
            ("preprocess", _preprocessor()),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=120,
                    max_depth=10,
                    min_samples_leaf=14,
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    frequency_model.fit(X_train, y_freq_train)
    loss_model.fit(X_train, y_loss_train)
    return _build_bundle(df, frequency_model, loss_model, X_test, y_freq_test, y_loss_test, "RandomForest", artifact_dir)


def train_ml_models(
    df: pd.DataFrame,
    artifact_dir: str | Path | None = None,
    random_state: int = 42,
    model_type: str = "xgboost",
) -> dict[str, Any]:
    """Train the fuller predictive ML layer, defaulting to XGBoost."""

    if df.empty:
        raise ValueError("Training data is empty.")

    requested = model_type.lower()
    if requested not in {"xgboost", "random_forest"}:
        raise ValueError("model_type must be 'xgboost' or 'random_forest'.")
    if requested == "random_forest":
        return train_models(df, artifact_dir=artifact_dir, random_state=random_state)

    from xgboost import XGBClassifier, XGBRegressor

    X_train, X_test, y_freq_train, y_freq_test, y_loss_train, y_loss_test = _split_targets(df, random_state)
    pos = float(y_freq_train.sum())
    neg = float(len(y_freq_train) - y_freq_train.sum())
    scale_pos_weight = max(neg / max(pos, 1.0), 1.0)

    frequency_model = Pipeline(
        steps=[
            ("preprocess", _preprocessor()),
            (
                "model",
                XGBClassifier(
                    n_estimators=140,
                    max_depth=4,
                    learning_rate=0.055,
                    subsample=0.86,
                    colsample_bytree=0.84,
                    objective="binary:logistic",
                    eval_metric="logloss",
                    tree_method="hist",
                    random_state=random_state,
                    n_jobs=2,
                    scale_pos_weight=scale_pos_weight,
                ),
            ),
        ]
    )
    loss_model = Pipeline(
        steps=[
            ("preprocess", _preprocessor()),
            (
                "model",
                XGBRegressor(
                    n_estimators=160,
                    max_depth=4,
                    learning_rate=0.055,
                    subsample=0.88,
                    colsample_bytree=0.86,
                    objective="reg:squarederror",
                    tree_method="hist",
                    random_state=random_state,
                    n_jobs=2,
                ),
            ),
        ]
    )

    frequency_model.fit(X_train, y_freq_train)
    loss_model.fit(X_train, y_loss_train)
    return _build_bundle(df, frequency_model, loss_model, X_test, y_freq_test, y_loss_test, "XGBoost", artifact_dir)


def load_model_bundle(path: str | Path) -> dict[str, Any]:
    """Load a trained model bundle."""

    return joblib.load(path)


def predict_policy(policy: dict[str, Any], bundle: dict[str, Any]) -> dict[str, float]:
    """Predict claim probability and expected loss for a single policy."""

    X = policy_to_frame(policy)
    p_claim = float(bundle["frequency_model"].predict_proba(X)[:, 1][0])
    modeled_loss = float(np.expm1(bundle["loss_model"].predict(X)[0]))
    modeled_loss = max(modeled_loss, 0.0)
    conditional_severity = modeled_loss / max(p_claim, 0.01)
    return {
        "claim_probability": min(max(p_claim, 0.0), 1.0),
        "conditional_severity_sar": conditional_severity,
        "expected_loss_sar": modeled_loss,
    }
