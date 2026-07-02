# Chubb Arabia Portfolio Risk Model and Underwriting Workbench

Prototype underwriting, pricing, reserving, ML, and proxy RBC platform for Saudi Arabia P&C portfolios ahead of the January 1, 2027 risk-based capital transition.

The repository now contains two usable experiences:

- **Analytics prototype:** the original Streamlit app for model diagnostics, generated feeds, reserving, capital, scenarios, and underwriting exploration.
- **End-to-end underwriting workbench:** a FastAPI + React application for unstructured intake, structured intake, enrichment, triage, review, quote generation, PDF output, and simulated bind.

Outputs are prototype analytics, not official IA/SAMA regulatory capital calculations.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && npm install
```

## Run the Underwriting Workbench

Start the backend and React frontend together:

```bash
./start_local.sh
```

Open `http://127.0.0.1:5173`. The API runs at `http://127.0.0.1:8000`.

Useful overrides:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=5174 ./start_local.sh
START_STREAMLIT=1 ./start_local.sh
```

The backend stores local workflow state in `artifacts/underwriting.db`, uploaded source records in `artifacts/uploads/`, and quote PDFs in `artifacts/quotes/`.
Unstructured extraction uses Gemini through the Google AI API when `GEMINI_API_KEY` is set. The app loads `.env` automatically; start from the example file:

```bash
cp .env.example .env
# edit .env and set GEMINI_API_KEY
./start_local.sh
```

Optional overrides can also be passed directly:

```bash
GEMINI_API_KEY=... ./start_local.sh
GEMINI_EXTRACTION_MODEL=gemini-3.5-flash ./start_local.sh
UNSTRUCTURED_UPLOAD_DIR=artifacts/uploads ./start_local.sh
UNSTRUCTURED_MAX_UPLOAD_MB=25 ./start_local.sh
```


## Run the Streamlit Analytics App

```bash
.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## Test

```bash
.venv/bin/python -m unittest discover -s tests
cd frontend && npm run build
```

## Underwriting Workbench Capabilities

- Unstructured intake for `.eml`, `.pdf`, `.csv`, `.xlsx`, and `.xls` records with HITL review before application creation.
- Manual and API intake for all configured Saudi P&C LOBs.
- Generated provider-style enrichment for identity/financial, reinsurance, motor, property, engineering, marine, and liability signals.
- Rules triage into straight-through processing, requires review, or decline.
- Existing actuarial/ML pricing engine reused through backend workflow services.
- Review queue with assignment, notes, approval/decline, schedule adjustment, sublimits, and exclusions.
- Quote generation with downloadable PDF and simulated bind/policy number.
- SQLite audit trail for application, enrichment, decision, rating, review, quote, and bind events.

## UI Guide

See [UI_DATA_DICTIONARY.md](UI_DATA_DICTIONARY.md) for a plain-English explanation of the analytics app tabs and datapoints.

## Caveat

The factors and generated data are intentionally configurable placeholders. Replace them with company experience data, approved actuarial assumptions, external Saudi data feeds, governance controls, official RBC calibration, production security, and legal wording before using this for production pricing or regulatory solvency work.
