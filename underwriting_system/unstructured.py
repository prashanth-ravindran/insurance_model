"""Unstructured intake parsing and extraction services."""

from __future__ import annotations

import csv
import json
import os
import re
import uuid
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from html import unescape
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from insurance_model.config import COUNTERPARTY_RATING_FACTORS, LOBS, REGION_RISK
from underwriting_system.schemas import ApplicationCreate

UPLOAD_DIR = Path(os.getenv("UNSTRUCTURED_UPLOAD_DIR", "artifacts/uploads"))
MAX_UPLOAD_MB = int(os.getenv("UNSTRUCTURED_MAX_UPLOAD_MB", "25"))
ALLOWED_EXTENSIONS = {".eml", ".pdf", ".csv", ".xlsx", ".xls"}
TEXT_LIMIT = 24000

REQUIRED_FIELD_PATHS = [
    "applicant.name",
    "applicant.applicant_type",
    "applicant.national_id_or_cr",
    "policy.lob",
    "policy.region",
    "policy.exposure_value_sar",
    "policy.limit_sar",
    "policy.deductible_sar",
]

NUMERIC_FIELD_PATHS = [
    "policy.exposure_value_sar",
    "policy.limit_sar",
    "policy.deductible_sar",
    "policy.term_months",
    "policy.prior_claims_3y",
    "policy.risk_control_score",
    "policy.reinsurance_ceded_pct",
    "policy.event_accumulation_score",
]

FIELD_ALIASES = {
    "applicant_name": "applicant.name",
    "name": "applicant.name",
    "applicant_type": "applicant.applicant_type",
    "national_id": "applicant.national_id_or_cr",
    "national_id_or_cr": "applicant.national_id_or_cr",
    "cr": "applicant.national_id_or_cr",
    "email": "applicant.email",
    "phone": "applicant.phone",
    "lob": "policy.lob",
    "line_of_business": "policy.lob",
    "region": "policy.region",
    "counterparty_rating": "policy.counterparty_rating",
    "reinsurer_rating": "policy.counterparty_rating",
    "exposure_value_sar": "policy.exposure_value_sar",
    "exposure": "policy.exposure_value_sar",
    "limit_sar": "policy.limit_sar",
    "coverage_limit": "policy.limit_sar",
    "deductible_sar": "policy.deductible_sar",
    "deductible": "policy.deductible_sar",
    "term_months": "policy.term_months",
    "prior_claims_3y": "policy.prior_claims_3y",
    "prior_claims": "policy.prior_claims_3y",
    "risk_control_score": "policy.risk_control_score",
    "risk_controls": "policy.risk_control_score",
    "reinsurance_ceded_pct": "policy.reinsurance_ceded_pct",
    "event_accumulation_score": "policy.event_accumulation_score",
}


@dataclass(frozen=True)
class RawDocumentRecord:
    raw_text: str
    raw_preview: dict[str, Any]
    batch_index: int = 0


def upload_directory() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def stored_upload_path(record_id: str, original_filename: str) -> Path:
    suffix = Path(original_filename).suffix.lower()
    return upload_directory() / f"{record_id}{suffix}"


def validate_upload(original_filename: str, content: bytes) -> str:
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported upload type {suffix or '(none)'}. Allowed types: {allowed}.")
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(f"Upload exceeds {MAX_UPLOAD_MB} MB limit.")
    if not content:
        raise ValueError("Upload is empty.")
    return suffix


def write_upload(record_id: str, original_filename: str, content: bytes) -> Path:
    path = stored_upload_path(record_id, original_filename)
    path.write_bytes(content)
    return path


def read_upload_records(path: Path, original_filename: str, content_type: str | None = None) -> list[RawDocumentRecord]:
    suffix = Path(original_filename).suffix.lower()
    if suffix == ".eml":
        return [_read_eml(path)]
    if suffix == ".pdf":
        return [_read_pdf(path)]
    if suffix == ".csv":
        return _read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return _read_excel(path)
    raise ValueError(f"Unsupported upload type {suffix}.")


def _preview_text(text: str, kind: str, **metadata: Any) -> dict[str, Any]:
    return {"kind": kind, "text": text[:TEXT_LIMIT], **metadata}


def _decode_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _strip_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _read_eml(path: Path) -> RawDocumentRecord:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        payload = message.get_payload(decode=True) or b""
        text = _decode_bytes(payload)
    else:
        text = body.get_content()
        if body.get_content_type() == "text/html":
            text = _strip_html(text)
    header_lines = [
        f"Subject: {message.get('subject', '')}",
        f"From: {message.get('from', '')}",
        f"To: {message.get('to', '')}",
        f"Date: {message.get('date', '')}",
    ]
    raw_text = "\n".join(header_lines + ["", text.strip()])
    return RawDocumentRecord(raw_text=raw_text, raw_preview=_preview_text(raw_text, "email"))


def _read_pdf(path: Path) -> RawDocumentRecord:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - dependency failure path
        raise RuntimeError("pypdf is required to extract PDF text.") from exc
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        pages.append(f"Page {index}\n{page_text.strip()}")
    raw_text = "\n\n".join(pages).strip()
    if not raw_text:
        raw_text = "PDF text extraction returned no selectable text."
    return RawDocumentRecord(raw_text=raw_text, raw_preview=_preview_text(raw_text, "pdf", page_count=len(reader.pages)))


def _read_csv(path: Path) -> list[RawDocumentRecord]:
    text = _decode_bytes(path.read_bytes())
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(text.splitlines(), dialect=dialect))
    if not rows:
        return [RawDocumentRecord(raw_text=text, raw_preview=_preview_text(text, "csv"))]
    records = []
    for index, row in enumerate(rows, start=1):
        raw_text = _row_to_text(row, f"CSV row {index}")
        records.append(RawDocumentRecord(raw_text=raw_text, raw_preview=_preview_text(raw_text, "csv_row", row_number=index), batch_index=index - 1))
    return records


def _read_excel(path: Path) -> list[RawDocumentRecord]:
    try:
        import pandas as pd
    except Exception as exc:  # pragma: no cover - dependency failure path
        raise RuntimeError("pandas with openpyxl/xlrd is required to extract Excel records.") from exc
    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    records: list[RawDocumentRecord] = []
    batch_index = 0
    for sheet_name, frame in sheets.items():
        frame = frame.dropna(how="all")
        for row_number, row in frame.iterrows():
            row_dict = {str(key): "" if value is None or str(value) == "nan" else str(value) for key, value in row.to_dict().items()}
            if not any(value.strip() for value in row_dict.values()):
                continue
            raw_text = _row_to_text(row_dict, f"Excel sheet {sheet_name} row {int(row_number) + 2}")
            records.append(
                RawDocumentRecord(
                    raw_text=raw_text,
                    raw_preview=_preview_text(raw_text, "excel_row", sheet=sheet_name, row_number=int(row_number) + 2),
                    batch_index=batch_index,
                )
            )
            batch_index += 1
    if records:
        return records
    raw_text = "Excel workbook contains no non-empty quote rows."
    return [RawDocumentRecord(raw_text=raw_text, raw_preview=_preview_text(raw_text, "excel"))]


def _row_to_text(row: dict[str, Any], title: str) -> str:
    lines = [title]
    for key, value in row.items():
        if value is None:
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def parse_json_text(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def build_extraction_prompt(raw_text: str, original_filename: str) -> str:
    lobs = ", ".join(LOBS)
    regions = ", ".join(REGION_RISK)
    ratings = ", ".join(COUNTERPARTY_RATING_FACTORS)
    return f"""
You extract Chubb Arabia underwriting intake data for Saudi P&C insurance from one raw record.
Return only valid JSON. Do not include markdown.

Use this JSON shape:
{{
  "application": {{
    "channel": "manual",
    "submitted_by": "unstructured.intake",
    "role": "agent",
    "applicant": {{
      "name": "...",
      "applicant_type": "company or individual",
      "national_id_or_cr": "...",
      "email": "...",
      "phone": "..."
    }},
    "policy": {{
      "lob": "one allowed LOB",
      "region": "one allowed region",
      "counterparty_rating": "one allowed rating",
      "exposure_value_sar": 0,
      "limit_sar": 0,
      "deductible_sar": 0,
      "term_months": 12,
      "prior_claims_3y": 0,
      "risk_control_score": 70,
      "reinsurance_ceded_pct": 0.1,
      "event_accumulation_score": 0.1
    }},
    "requested_coverages": {{}}
  }},
  "field_confidence": {{
    "applicant.name": {{"confidence": "high or low", "evidence": "short evidence", "rationale": "short rationale"}}
  }},
  "source_evidence": {{"applicant.name": "short quoted source fragment"}},
  "missing_fields": ["field.path"],
  "warnings": ["short warning"]
}}

Allowed LOBs: {lobs}
Allowed regions: {regions}
Allowed reinsurer ratings: {ratings}
Use SAR numeric values without currency symbols or commas.
Use high confidence only when the field is explicit in the source; use low when inferred, defaulted, converted, or absent.
If the record is a quote PDF with an Application ID but no National ID / CR, put the Application ID in applicant.national_id_or_cr and mark confidence low.
If exposure value is absent but coverage limit is present, use the coverage limit as exposure_value_sar and mark confidence low.
For fields not present, use sensible defaults and mark confidence low.

Filename: {original_filename}
Raw record:
{raw_text[:TEXT_LIMIT]}
""".strip()


class GeminiExtractionService:
    """Gemini-backed extractor. The import stays lazy so tests do not need the SDK."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("GEMINI_EXTRACTION_MODEL", "gemini-3.5-flash")
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")

    def extract(self, raw_text: str, original_filename: str) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for unstructured extraction.")
        try:
            from google import genai
        except Exception as exc:  # pragma: no cover - dependency failure path
            raise RuntimeError("google-genai is required for Gemini extraction.") from exc

        prompt = build_extraction_prompt(raw_text, original_filename)
        client = genai.Client(api_key=self.api_key)
        if hasattr(client, "interactions"):
            response = client.interactions.create(model=self.model, input=prompt)
            text = getattr(response, "output_text", None) or getattr(response, "text", None) or str(response)
        else:  # compatibility with older google-genai releases
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            text = getattr(response, "text", "")
        return parse_json_text(text)


class LocalKeyValueExtractor:
    """Deterministic extractor for tests and local fixtures."""

    def extract(self, raw_text: str, original_filename: str) -> dict[str, Any]:
        flat: dict[str, str] = {}
        for line in raw_text.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            clean_key = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
            flat[clean_key] = value.strip()
        application = _application_from_flat(flat)
        confidence = {path: {"confidence": "high", "evidence": str(value)[:160]} for key, value in flat.items() if (path := FIELD_ALIASES.get(key))}
        return {
            "application": application,
            "field_confidence": confidence,
            "source_evidence": {path: data.get("evidence") for path, data in confidence.items()},
            "missing_fields": [],
            "warnings": [],
        }


def normalize_extraction(raw_result: dict[str, Any]) -> dict[str, Any]:
    application = _normalize_application(raw_result)
    confidence = _normalize_confidence(raw_result.get("field_confidence", {}))
    source_evidence = raw_result.get("source_evidence", {}) if isinstance(raw_result.get("source_evidence", {}), dict) else {}
    missing_fields = list(raw_result.get("missing_fields", [])) if isinstance(raw_result.get("missing_fields", []), list) else []
    warnings = list(raw_result.get("warnings", [])) if isinstance(raw_result.get("warnings", []), list) else []

    for path in REQUIRED_FIELD_PATHS:
        if _is_blank(_get_path(application, path)) and path not in missing_fields:
            missing_fields.append(path)

    for path in REQUIRED_FIELD_PATHS + NUMERIC_FIELD_PATHS:
        _ensure_confidence(confidence, path)

    _apply_value_heuristics(application, confidence, missing_fields, warnings)
    try:
        ApplicationCreate.model_validate(application)
    except Exception as exc:
        warnings.append(f"Structured application validation needs review: {exc}")

    return {
        "extraction": {"application": application},
        "field_confidence": confidence,
        "source_evidence": source_evidence,
        "missing_fields": sorted(set(missing_fields)),
        "warnings": _dedupe(warnings),
    }


def _normalize_application(raw_result: dict[str, Any]) -> dict[str, Any]:
    candidate = raw_result.get("application") if isinstance(raw_result.get("application"), dict) else raw_result
    if not isinstance(candidate, dict):
        candidate = {}
    flat_source = candidate if not any(key in candidate for key in ("applicant", "policy")) else {}
    application = _application_from_flat(flat_source)
    for key in ("channel", "submitted_by", "role"):
        if candidate.get(key):
            application[key] = candidate[key]
    if isinstance(candidate.get("applicant"), dict):
        application["applicant"].update({key: value for key, value in candidate["applicant"].items() if value is not None})
    if isinstance(candidate.get("policy"), dict):
        application["policy"].update({key: value for key, value in candidate["policy"].items() if value is not None})
    if isinstance(candidate.get("requested_coverages"), dict):
        application["requested_coverages"].update(candidate["requested_coverages"])
    _coerce_application_values(application)
    return application


def _application_from_flat(flat: dict[str, Any]) -> dict[str, Any]:
    application: dict[str, Any] = {
        "channel": "manual",
        "submitted_by": "unstructured.intake",
        "role": "agent",
        "applicant": {
            "name": "",
            "applicant_type": "company",
            "national_id_or_cr": "",
            "email": None,
            "phone": None,
        },
        "policy": {
            "lob": "Motor",
            "region": "Riyadh",
            "counterparty_rating": "A",
            "exposure_value_sar": 0,
            "limit_sar": 0,
            "deductible_sar": 0,
            "term_months": 12,
            "prior_claims_3y": 0,
            "risk_control_score": 70,
            "reinsurance_ceded_pct": 0.1,
            "event_accumulation_score": 0.1,
        },
        "requested_coverages": {"source": "unstructured_intake"},
    }
    for key, value in flat.items():
        clean_key = re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")
        path = FIELD_ALIASES.get(clean_key)
        if path:
            _set_path(application, path, value)
    return application


def _coerce_application_values(application: dict[str, Any]) -> None:
    applicant = application.setdefault("applicant", {})
    if str(applicant.get("applicant_type", "company")).lower() not in {"individual", "company"}:
        applicant["applicant_type"] = "company"
    else:
        applicant["applicant_type"] = str(applicant.get("applicant_type", "company")).lower()

    policy_payload = application.setdefault("policy", {})
    policy_payload["lob"] = _match_choice(str(policy_payload.get("lob", "Motor")), LOBS, "Motor")
    policy_payload["region"] = _match_choice(str(policy_payload.get("region", "Riyadh")), list(REGION_RISK), "Riyadh")
    policy_payload["counterparty_rating"] = _match_choice(
        str(policy_payload.get("counterparty_rating", "A")), list(COUNTERPARTY_RATING_FACTORS), "A"
    )
    for path in NUMERIC_FIELD_PATHS:
        value = _get_path(application, path)
        if value is None or value == "":
            continue
        _set_path(application, path, _coerce_number(value))


def _match_choice(value: str, choices: list[str], default: str) -> str:
    normalized = value.strip().lower()
    for choice in choices:
        if normalized == choice.lower():
            return choice
    for choice in choices:
        if normalized and (normalized in choice.lower() or choice.lower() in normalized):
            return choice
    return default


def _coerce_number(value: Any) -> float | int:
    if isinstance(value, (int, float)):
        return value
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if cleaned in {"", ".", "-"}:
        return 0
    number = float(cleaned)
    return int(number) if number.is_integer() else number


def _normalize_confidence(raw: Any) -> dict[str, dict[str, str | None]]:
    normalized: dict[str, dict[str, str | None]] = {}
    if not isinstance(raw, dict):
        return normalized
    for key, value in raw.items():
        path = FIELD_ALIASES.get(str(key), str(key))
        if isinstance(value, dict):
            level = str(value.get("confidence") or value.get("level") or "low").lower()
            evidence = value.get("evidence")
            rationale = value.get("rationale") or value.get("reason")
        else:
            level = str(value).lower()
            evidence = None
            rationale = None
        normalized[path] = {
            "confidence": "high" if level == "high" else "low",
            "evidence": None if evidence is None else str(evidence)[:240],
            "rationale": None if rationale is None else str(rationale)[:240],
        }
    return normalized


def _ensure_confidence(confidence: dict[str, Any], path: str) -> None:
    if path not in confidence:
        confidence[path] = {"confidence": "low", "evidence": None, "rationale": "No explicit extracted evidence."}


def _apply_value_heuristics(application: dict[str, Any], confidence: dict[str, Any], missing_fields: list[str], warnings: list[str]) -> None:
    for path in missing_fields:
        _downgrade(confidence, path, "Field is missing or blank.")
    for path in ["policy.exposure_value_sar", "policy.limit_sar"]:
        if float(_get_path(application, path) or 0) <= 0:
            _downgrade(confidence, path, "Required amount is not positive.")
    if float(_get_path(application, "policy.deductible_sar") or 0) < 0:
        _downgrade(confidence, "policy.deductible_sar", "Deductible is negative.")
    if float(_get_path(application, "policy.limit_sar") or 0) > float(_get_path(application, "policy.exposure_value_sar") or 0) * 2:
        warnings.append("Coverage limit is materially higher than the exposure value and should be checked.")
        _downgrade(confidence, "policy.limit_sar", "Limit is unusually high versus exposure value.")
    controls = float(_get_path(application, "policy.risk_control_score") or 0)
    if controls < 0 or controls > 100:
        warnings.append("Risk control score should be between 0 and 100.")
        _downgrade(confidence, "policy.risk_control_score", "Risk control score is outside expected range.")
    for path in ["policy.reinsurance_ceded_pct", "policy.event_accumulation_score"]:
        value = float(_get_path(application, path) or 0)
        if value < 0 or value > 1:
            warnings.append(f"{path} should usually be between 0 and 1.")
            _downgrade(confidence, path, "Percentage-like value is outside expected range.")


def _downgrade(confidence: dict[str, Any], path: str, rationale: str) -> None:
    current = confidence.setdefault(path, {"confidence": "low", "evidence": None, "rationale": None})
    current["confidence"] = "low"
    current["rationale"] = rationale


def _get_path(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_path(payload: dict[str, Any], path: str, value: Any) -> None:
    current = payload
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def new_record_id(prefix: str = "URI") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"
