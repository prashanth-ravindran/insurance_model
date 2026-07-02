# Underwriting Workbench Guide

This guide describes the FastAPI + React underwriting workbench.

## Workflow

1. **Unstructured Intake** accepts `.eml`, `.pdf`, `.csv`, `.xlsx`, and `.xls` source records before application creation.
2. **HITL Extraction Review** shows the raw record on the left and Gemini-extracted editable fields on the right with high/low confidence per field.
3. **Intake** creates an application only after reviewer approval, or from the manual UI / `POST /api/applications`.
4. **Enrichment** runs generated provider services and stores provider responses, confidence, and flags.
5. **Underwriting** runs rules, risk scoring, rating, pricing adjustments, and triage.
6. **Review Queue** holds requires-review cases for assignment, notes, approval, decline, schedule rating, sublimits, and exclusions.
7. **Quote & Bind** generates the quote, writes a PDF, and simulates binding with a policy number.

## Main API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Backend health check. |
| `GET /api/config` | LOBs, regions, ratings, thresholds, and scenario options. |
| `POST /api/unstructured-intake/uploads` | Upload one or more `.eml`, `.pdf`, `.csv`, `.xlsx`, or `.xls` source records. CSV/Excel rows can become multiple pre-intake records. |
| `GET /api/unstructured-intake` | List pre-intake records and review state. |
| `GET /api/unstructured-intake/{id}/raw` | Stream the original file for raw preview. |
| `POST /api/unstructured-intake/{id}/extract` | Run Gemini extraction and store field confidence, missing fields, warnings, and extracted application values. |
| `POST /api/unstructured-intake/{id}/review` | Approve or reject the extraction. Approval creates a structured application. |
| `POST /api/applications` | Create application from manual or API intake. |
| `GET /api/applications/{id}` | Read full case state. |
| `POST /api/applications/{id}/enrich` | Run generated enrichment providers. |
| `POST /api/applications/{id}/underwrite` | Run triage, rating, pricing, and rules. |
| `GET /api/reviews` | List requires-review cases. |
| `POST /api/reviews/{id}/assign` | Assign a review case. |
| `POST /api/reviews/{id}/decision` | Approve or decline a review case. |
| `POST /api/applications/{id}/quote` | Generate quote and PDF. |
| `GET /api/quotes/{quote_id}/pdf` | Download quote PDF. |
| `POST /api/quotes/{quote_id}/bind` | Simulate policy bind. |

## Local State

- SQLite database: `artifacts/underwriting.db`
- Uploaded unstructured files: `artifacts/uploads/`
- Quote PDFs: `artifacts/quotes/`
- These local artifacts are ignored by git.

## Demo Roles

The UI includes a role switcher for Agent, Underwriter, and Manager. It is a workflow simulator, not authentication.

## Gemini Extraction

Set `GEMINI_API_KEY` for real extraction. The default model is `gemini-3.5-flash`, overrideable with `GEMINI_EXTRACTION_MODEL`. If the API key is missing, uploads and raw preview still work, but extraction records move to `failed` with a remediation message.

The backend asks Gemini for strict JSON shaped like the existing `ApplicationCreate` payload plus `field_confidence`, `source_evidence`, `missing_fields`, and `warnings`. Backend heuristics can downgrade confidence when required fields are blank, numeric values are invalid, or values are out of expected ranges.
