# Saudi P&C Portfolio Risk Model

Prototype underwriting, pricing, reserving, ML, and proxy RBC platform for Saudi Arabia P&C portfolios ahead of the January 1, 2027 risk-based capital transition.

The app can run without company data. It generates full portfolio data feeds, trains actuarial and ML models, prices individual policy requests, explains decisions, estimates reserves, aggregates capital, and runs scenario stresses. Outputs are prototype analytics, not official IA/SAMA regulatory capital calculations.

## What Is Included

- Saudi-specific LOB segmentation: Motor, Property & Fire, Engineering & Construction, Marine & Cargo, and Casualty/Liability.
- Generated data feeds: policies, premiums, exposures, claims, reinsurance, economic indices, traffic events, weather events, catastrophe events, market curves, and proxy RBC factors.
- Baseline actuarial models: Poisson GLM frequency, Gamma GLM severity, paid chain ladder, and Bornhuetter-Ferguson reserve cross-checks.
- Predictive ML: XGBoost frequency and severity models, with SHAP explanations for the current quote.
- Underwriting rules: quote, requires review, or decline, with natural-language rule explanations and remediation steps.
- Capital model: premium risk, reserve risk, catastrophe risk, reinsurance credit risk, market risk, correlation aggregation, and scenario comparison.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## Test

```bash
.venv/bin/python -m unittest discover -s tests
```

## UI Guide

See [UI_DATA_DICTIONARY.md](UI_DATA_DICTIONARY.md) for a plain-English explanation of each tab and the major datapoints shown in the app.

## Caveat

The factors and generated data are intentionally configurable placeholders. Replace them with company experience data, approved actuarial assumptions, external Saudi data feeds, governance controls, and official RBC calibration before using this for production pricing or regulatory solvency work.
