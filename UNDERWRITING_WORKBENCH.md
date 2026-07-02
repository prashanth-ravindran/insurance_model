# Xtract.io for Chubb Arabia Workbench Guide

This guide covers both application surfaces in the repository:

- **Streamlit risk model app**: `app.py`, titled **Chubb Arabia Portfolio Risk Model**.
- **React underwriting workbench**: `frontend/src/App.tsx` plus FastAPI backend in `underwriting_system/`, titled **Xtract.io for Chubb Arabia**.

The Streamlit app is the analytical model lab. The React app is the operational underwriting workflow. They share the same Saudi P&C domain assumptions, LOBs, generated data approach, pricing concepts, and proxy RBC framing.

## Product Shape

| Surface | Primary user | Main purpose |
|---|---|---|
| Streamlit risk model | Actuary, model owner, portfolio manager, risk team | Explore pricing, ML diagnostics, reserving, capital, scenarios, and rules. |
| React workbench | Agent, underwriter, underwriting manager | Process a case from document intake through extraction, enrichment, triage, review, quote, and bind. |
| FastAPI backend | React app and API clients | Stores cases, uploaded records, extracted values, decisions, ratings, quotes, PDFs, and audit events. |

## Shared Saudi P&C Scope

Both apps use these LOBs:

- Motor
- Property & Fire
- Engineering & Construction
- Marine & Cargo
- Casualty/Liability

Both apps use Saudi-specific dimensions such as region, traffic density, flood exposure, sandstorm exposure, industrial concentration, reinsurance credit quality, construction/project complexity, cargo risk, liability exposure, and proxy capital factors.

## Streamlit Risk Model App

The Streamlit app is a model-development and governance view. It is not a queue or workflow system. It answers questions like:

- What premium would the model recommend for a representative policy?
- What are the expected loss, catastrophe load, capital load, expense load, and profit margin?
- Which rules triggered quote, review, or decline?
- How do actuarial GLMs compare with predictive ML?
- Which features explain the model through SHAP?
- How large are reserves under Chain Ladder and Bornhuetter-Ferguson methods?
- How does proxy SCR move under stress scenarios?

### Streamlit Tabs

| Tab | Contents |
|---|---|
| Underwriting | Policy input controls, quote/review/decline decision, premium breakdown, pricing reconciliation, policy SCR, decision reasons, remediation, and rule checks. |
| Data | Generated feed inventory, metadata coverage, LOB mix chart, loss-ratio histogram, and selected feed table. |
| Actuarial | GLM frequency/severity diagnostics, GLM indication summary, GLM expected-loss scatter, and policy-level GLM outputs. |
| Model Diagnostics | XGBoost diagnostics, frequency/severity feature importance, and SHAP explanation for the current quote. |
| Reserving | Reserve summary by LOB, paid triangle, incurred triangle, and link ratios. |
| Capital | Standalone capital, diversified SCR, diversification benefit, expanded module capital, detail tables, and correlation matrices. |
| Scenarios | SCR comparison across Base, inflation, flood, sandstorm, reinsurer, interest-rate, and giga-project accumulation scenarios. |
| Rules | Natural-language business rules, decision thresholds, and LOB appetite limits. |
| Proxy Factors | LOB factors, policy correlations, expanded SCR correlations, scenario assumptions, and generated RBC factor feed. |

### Streamlit Model Inputs

The Underwriting tab uses common inputs for every LOB:

- Line of business
- Region
- Reinsurer rating
- Exposure value
- Coverage limit
- Deductible
- Term
- Prior claims in the last three years
- Risk controls
- Reinsurance ceded
- Event accumulation

LOB-specific inputs include motor vehicle class and driver details, property occupancy and fire protection, engineering project type and complexity, marine cargo type and route/storage details, and liability revenue/limit/professional-risk details.

### Streamlit Outputs

Key Streamlit outputs include:

- Decision: Quote, Requires Review, or Decline.
- Offered premium.
- Risk score.
- Expected loss.
- SCR impact.
- Premium component chart and table.
- Pricing reconciliation between predictive ML and selected pricing view.
- Capital module chart and diversification benefit.
- Decision reasons, detailed explanation, recommended actions, and rule checks.
- Data feed tables and metadata coverage.
- Actuarial GLM and predictive ML diagnostics.
- Reserve estimates and triangles.
- Expanded proxy capital model and scenario stresses.

## React Underwriting Workbench

The React workbench is the end-to-end operational experience. It demonstrates how a case moves through a realistic underwriting process.

### React Navigation

| Screen | Purpose |
|---|---|
| Unstructured Intake | Upload source records and perform HITL extraction review before creating an application. |
| Intake | Manually create a structured application. |
| Triage | Enrich and underwrite the selected application. |
| Review Queue | Manage cases requiring human underwriter review. |
| Quote & Bind | Generate quote documents and bind accepted quotes into policies. |
| Config | Inspect LOB appetite and decision thresholds. |

### Stage 1: Unstructured Intake

Supported source formats:

- `.eml`
- `.pdf`
- `.csv`
- `.xlsx`
- `.xls`

The workbench shows a compact intake rail with Upload, Extract, Approve, and Reject actions. Uploaded records appear as record chips. The main HITL layout places the raw record on the left and extracted editable values on the right.

Important fields in this stage:

| Field | Meaning |
|---|---|
| Original filename | Source document name. |
| File extension | Source format. |
| Batch row | Spreadsheet row number when a CSV/XLSX upload creates multiple records. |
| Status | Uploaded, extracting, needs review, failed, rejected, approved, or application created. |
| Raw record | Original PDF preview or raw text. |
| Extracted values | Editable application draft created from the source record. |
| Field confidence | High/low indicator per extracted attribute. |
| Evidence/rationale | Tooltip explanation behind the confidence badge. |
| Missing fields | Required fields not found in the source. |
| Warnings | Extraction quality issues or defaulted values. |

### Stage 2: HITL Extraction Review

The human reviewer compares the raw source with extracted values. The reviewer can correct applicant fields, policy fields, and LOB-specific fields before approval.

Approve creates a structured application. Reject keeps the record out of the underwriting workflow.

Extraction is designed for Gemini. Configure it with:

- `GEMINI_API_KEY`
- `GEMINI_EXTRACTION_MODEL`, defaulting to `gemini-3.5-flash`

If no Gemini API key is configured, upload and preview still work, but extraction fails with a clear remediation message.

### Stage 3: Structured Intake

Manual/API intake creates an application directly. The application includes:

- Channel: manual or API.
- Submitted by.
- Role: agent, underwriter, or manager.
- Applicant fields: name, type, National ID / CR, email, phone.
- Policy fields: LOB, region, rating, exposure, limit, deductible, term, prior claims, controls, reinsurance, accumulation, and LOB-specific attributes.
- Requested coverages metadata.

### Stage 4: Enrichment

The Triage screen can run generated enrichment providers. Providers simulate third-party verification and supplemental risk evidence.

Examples include:

- Identity and financial verification.
- Reinsurance security checks.
- Motor driving/claim-history style checks.
- Property/geospatial hazard checks.
- Engineering project intelligence.
- Marine logistics intelligence.
- Liability/public-records style checks.

Each enrichment stores provider name, status, confidence, response data, flags, requested time, and completed time.

### Stage 5: Underwriting Rules, Rating, and Triage

The Underwrite action runs:

- Enrichment merge into policy features.
- Business rules.
- Risk scoring.
- Premium rating.
- Pricing adjustments.
- Decision bucket assignment.

Possible decisions:

| Decision | Meaning |
|---|---|
| STP | Straight-through processing. Case is eligible for quote without human review. |
| Requires review | Human underwriter must review, assign, approve, decline, or modify terms. |
| Declined | Case is outside appetite as entered. |

Triage outputs include decision reasons, adjusted premium, expected loss, risk score, SCR, and adjustment rows.

### Stage 6: Review Queue

Requires-review cases enter the review queue. The underwriter can:

- Assign the case.
- Enter notes.
- Apply a schedule rating adjustment.
- Add exclusions.
- Approve the case.
- Decline the case.

Review approval allows the case to proceed to quote generation. Review decline ends the case.

### Stage 7: Quote Generation

Quote generation packages pricing and terms into a quote record and PDF.

Quote fields include:

- Quote ID / quote number.
- Application ID.
- Premium.
- Decision bucket.
- Deductible.
- Sublimits.
- Exclusions.
- Expiry date.
- Generated-by actor.
- PDF path.

The quote PDF title is **Chubb Arabia Underwriting Quote**.

### Stage 8: Bind

Binding converts an accepted quote into an active policy in the workflow. In this prototype, binding creates a policy number and updates status to bound. In real insurance operations, binding means coverage is made effective under the accepted terms.

### Audit Trail

The workbench records workflow actions as audit events, including:

- `application.created`
- `status.enriched`
- `underwriting.decision`
- `rating.created`
- `status.stp_quoted`
- `review.assigned`
- `review.decision`
- `quote.generated`
- `policy.bound`

Audit rows show event type, actor, payload, and timestamp.

## FastAPI Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Backend health check. |
| `GET /api/config` | LOBs, regions, ratings, thresholds, and scenario options. |
| `POST /api/unstructured-intake/uploads` | Upload `.eml`, `.pdf`, `.csv`, `.xlsx`, or `.xls` source records. CSV/Excel rows can create multiple pre-intake records. |
| `GET /api/unstructured-intake` | List uploaded pre-intake records and their review state. |
| `GET /api/unstructured-intake/{id}/raw` | Stream original file for raw preview. |
| `POST /api/unstructured-intake/{id}/extract` | Run extraction and store field confidence, missing fields, warnings, and extracted application values. |
| `POST /api/unstructured-intake/{id}/review` | Approve or reject extracted values. Approval creates a structured application. |
| `POST /api/applications` | Create application from manual or API intake. |
| `GET /api/applications` | List applications. |
| `GET /api/applications/{id}` | Read full case state. |
| `POST /api/applications/{id}/enrich` | Run generated enrichment providers. |
| `POST /api/applications/{id}/underwrite` | Run rules, risk scoring, rating, and triage. |
| `GET /api/reviews` | List requires-review cases. |
| `POST /api/reviews/{id}/assign` | Assign a review case. |
| `POST /api/reviews/{id}/decision` | Approve or decline a review case. |
| `POST /api/applications/{id}/quote` | Generate quote record and PDF. |
| `GET /api/quotes/{quote_id}/pdf` | Download quote PDF. |
| `POST /api/quotes/{quote_id}/bind` | Simulate policy bind. |

## Local State

| Location | Purpose |
|---|---|
| `artifacts/underwriting.db` | SQLite database for applications, unstructured records, decisions, ratings, reviews, quotes, bound policies, and audit events. |
| `artifacts/uploads/` | Uploaded source files. |
| `artifacts/quotes/` | Generated quote PDFs. |
| `.env` | Local secrets and runtime settings, such as `GEMINI_API_KEY`. |
| `.env.example` | Template for local environment configuration. |

Local artifacts and `.env` are ignored by git.

## Relationship Between Apps

The Streamlit app and React workbench are complementary:

- Use **Streamlit** to understand model mechanics, diagnostics, reserve methods, capital modules, scenarios, and rule governance.
- Use **React/FastAPI** to demonstrate operational underwriting workflow, document extraction, human review, triage, quote generation, and binding.
- Both are driven by generated data and proxy assumptions until real company/external feeds are integrated.
- Both should be recalibrated and governed before production use.

## Production Caveats

This repository is a prototype. Before production use, the following are required:

- Real historical policy, exposure, claims, premium, reserve, reinsurance, and external data feeds.
- Data quality checks and lineage controls.
- Approved actuarial calibration.
- Official Saudi RBC interpretation and regulatory validation.
- Legal policy wording and authority controls.
- Authentication, authorization, secrets management, and audit hardening.
- Model validation, monitoring, and change governance.
