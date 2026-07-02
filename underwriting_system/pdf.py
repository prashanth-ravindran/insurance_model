"""Quote PDF generation for the underwriting system."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(value: float | int | None) -> str:
    if value is None:
        return "Not offered"
    return f"SAR {float(value):,.0f}"


def _kv_table(rows: list[tuple[str, Any]]) -> Table:
    table = Table([[label, str(value)] for label, value in rows], colWidths=[5.2 * cm, 10.4 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f5f8")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1f2937")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9dee7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def generate_quote_pdf(case: dict[str, Any], quote: dict[str, Any], output_dir: str | Path = "artifacts/quotes") -> str:
    """Generate a professional quote summary PDF and return its path."""

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{quote['quote_number']}.pdf"

    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=1.6 * cm, leftMargin=1.6 * cm, topMargin=1.4 * cm, bottomMargin=1.4 * cm)
    styles = getSampleStyleSheet()
    story: list[Any] = []

    story.append(Paragraph("Chubb Arabia Underwriting Quote", styles["Title"]))
    story.append(Paragraph("Professional summary for generated underwriting workflow output. Not a regulatory filing or binding legal wording.", styles["BodyText"]))
    story.append(Spacer(1, 0.35 * cm))

    applicant = case["applicant"]
    policy = case["policy"]
    latest_decision = case.get("latest_decision") or {}
    latest_rating = case.get("latest_rating") or {}

    story.append(Paragraph("Quote Summary", styles["Heading2"]))
    story.append(
        _kv_table(
            [
                ("Quote number", quote["quote_number"]),
                ("Application", case["id"]),
                ("Applicant", applicant.get("name", "")),
                ("National ID / CR", applicant.get("national_id_or_cr", "")),
                ("Line of business", policy.get("lob", "")),
                ("Region", policy.get("region", "")),
                ("Exposure value", _money(policy.get("exposure_value_sar"))),
                ("Coverage limit", _money(policy.get("limit_sar"))),
                ("Deductible", _money(quote.get("deductible_sar", policy.get("deductible_sar")))),
                ("Offered premium", _money(quote.get("premium_sar"))),
                ("Quote expiry", quote.get("expires_at", "")),
                ("Decision", quote.get("decision_bucket", "")),
            ]
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Terms", styles["Heading2"]))
    exclusions = quote.get("exclusions") or ["Standard policy exclusions apply."]
    sublimits = quote.get("sublimits") or {}
    term_rows = [("Term", f"{policy.get('term_months', 12)} months"), ("Sublimits", ", ".join(f"{k}: {_money(v)}" for k, v in sublimits.items()) or "None specified"), ("Exclusions", "; ".join(exclusions))]
    story.append(_kv_table(term_rows))
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Pricing and Risk Basis", styles["Heading2"]))
    story.append(
        _kv_table(
            [
                ("Expected loss", _money(latest_rating.get("expected_loss_sar"))),
                ("Risk score", f"{float(latest_rating.get('risk_score', 0.0)):.1f}/100"),
                ("SCR impact", _money(latest_rating.get("scr_impact_sar"))),
                ("Model basis", latest_rating.get("model_basis", "")),
                ("Decision reasons", "; ".join(latest_decision.get("reasons", []))),
            ]
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Audit Note", styles["Heading2"]))
    story.append(Paragraph("This quote was generated from the underwriting workbench using generated provider evidence, company-configurable rules, and proxy model assumptions. Final production use requires approved wording, authority controls, and regulatory calibration.", styles["BodyText"]))

    doc.build(story)
    return str(path)
