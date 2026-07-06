"""FastAPI application for the underwriting workbench."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from insurance_model.config import COUNTERPARTY_RATING_FACTORS, DECISION_THRESHOLDS, LOB_CONFIG, LOBS, REGION_RISK
from insurance_model.simulation import SCENARIOS
from underwriting_system.schemas import (
    ApiResponse,
    ApplicationCreate,
    AssignmentRequest,
    BindRequest,
    QuoteGenerateRequest,
    ReviewDecisionRequest,
    UnstructuredReviewRequest,
)
from underwriting_system.model_api import build_model_summary
from underwriting_system.workflow import UnderwritingWorkflow

app = FastAPI(title="Chubb Arabia Underwriting API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workflow = UnderwritingWorkflow()


def _ok(data: dict[str, Any] | list[Any]) -> dict[str, Any]:
    return ApiResponse(data={"items": data} if isinstance(data, list) else data).model_dump(mode="json")


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=f"Record not found: {exc}")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def config() -> dict[str, Any]:
    return _ok(
        {
            "lobs": LOBS,
            "regions": REGION_RISK,
            "lob_config": LOB_CONFIG,
            "counterparty_ratings": list(COUNTERPARTY_RATING_FACTORS),
            "decision_thresholds": DECISION_THRESHOLDS,
            "scenarios": SCENARIOS,
            "roles": ["agent", "underwriter", "manager"],
            "channels": ["manual", "api"],
        }
    )


@app.post("/api/model/summary")
def model_summary(request: dict[str, Any]) -> dict[str, Any]:
    try:
        return _ok(build_model_summary(request))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/unstructured-intake/uploads")
async def upload_unstructured(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    try:
        records = []
        for upload in files:
            if not upload.filename:
                raise ValueError("Uploaded file must have a filename.")
            content = await upload.read()
            records.extend(workflow.upload_unstructured_file(upload.filename, upload.content_type, content))
        return _ok(records)
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.get("/api/unstructured-intake")
def list_unstructured(status: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        return _ok(workflow.list_unstructured_records(status=status))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.get("/api/unstructured-intake/{record_id}")
def get_unstructured(record_id: str) -> dict[str, Any]:
    try:
        return _ok(workflow.get_unstructured_record(record_id))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.get("/api/unstructured-intake/{record_id}/raw")
def get_unstructured_raw(record_id: str) -> FileResponse:
    try:
        record = workflow.get_unstructured_record(record_id)
        path = Path(record["storage_path"])
        if not path.exists():
            raise KeyError(record_id)
        media_type = record.get("content_type") or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(path, media_type=media_type, filename=record["original_filename"], content_disposition_type="inline")
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/unstructured-intake/{record_id}/extract")
def extract_unstructured(record_id: str) -> dict[str, Any]:
    try:
        return _ok(workflow.extract_unstructured(record_id))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/unstructured-intake/{record_id}/review")
def review_unstructured(record_id: str, request: UnstructuredReviewRequest) -> dict[str, Any]:
    try:
        return _ok(workflow.review_unstructured(record_id, request))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/applications")
def create_application(request: ApplicationCreate) -> dict[str, Any]:
    try:
        return _ok(workflow.create_application(request))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.get("/api/applications")
def list_applications(status: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        return _ok(workflow.list_cases(status=status))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.get("/api/applications/{application_id}")
def get_application(application_id: str) -> dict[str, Any]:
    try:
        return _ok(workflow.get_case(application_id))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/applications/{application_id}/enrich")
def enrich(application_id: str) -> dict[str, Any]:
    try:
        return _ok(workflow.enrich(application_id))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/applications/{application_id}/underwrite")
def underwrite(application_id: str) -> dict[str, Any]:
    try:
        return _ok(workflow.underwrite(application_id))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.get("/api/reviews")
def list_reviews(status: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        return _ok(workflow.list_reviews(status=status))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/reviews/{application_id}/assign")
def assign_review(application_id: str, request: AssignmentRequest) -> dict[str, Any]:
    try:
        return _ok(workflow.assign_review(application_id, request))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/reviews/{application_id}/decision")
def review_decision(application_id: str, request: ReviewDecisionRequest) -> dict[str, Any]:
    try:
        return _ok(workflow.review_decision(application_id, request))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/applications/{application_id}/quote")
def generate_quote(application_id: str, request: QuoteGenerateRequest) -> dict[str, Any]:
    try:
        return _ok(workflow.generate_quote(application_id, request))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.post("/api/quotes/{quote_id}/bind")
def bind_quote(quote_id: str, request: BindRequest) -> dict[str, Any]:
    try:
        return _ok(workflow.bind(quote_id, request))
    except Exception as exc:
        raise _handle_error(exc) from exc


@app.get("/api/quotes/{quote_id}/pdf")
def download_quote_pdf(quote_id: str) -> FileResponse:
    try:
        for case in workflow.list_cases():
            for quote in case.get("quotes", []):
                if quote.get("id") == quote_id:
                    path = Path(quote["pdf_path"])
                    if not path.exists():
                        raise KeyError(quote_id)
                    return FileResponse(path, media_type="application/pdf", filename=path.name, content_disposition_type="inline")
        raise KeyError(quote_id)
    except Exception as exc:
        raise _handle_error(exc) from exc

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

