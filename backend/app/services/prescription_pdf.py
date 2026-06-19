"""Generate professionally styled clinical prescription PDFs."""
from __future__ import annotations

import datetime
import hashlib
import random
import string
from typing import Iterable, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Healthcare brand palette
PRIMARY = colors.HexColor("#00355f")
SECONDARY = colors.HexColor("#006970")
ACCENT = colors.HexColor("#e8f4f4")
MUTED = colors.HexColor("#5f6368")
BORDER = colors.HexColor("#c5d5d8")


class _SignatureBlock:
    """Draws a randomised digital signature flourish on the PDF canvas."""

    def __init__(
        self,
        doctor_name: str,
        signature_id: str,
        width: float = 16 * cm,
        height: float = 2.8 * cm,
    ):
        self.doctor_name = doctor_name
        self.signature_id = signature_id
        self.width = width
        self.height = height
        rng = random.Random(signature_id)
        self._points = self._build_signature_path(rng)

    @staticmethod
    def _build_signature_path(rng: random.Random) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        x = 0.4
        y = 0.55 + rng.uniform(-0.08, 0.08)
        points.append((x, y))
        steps = rng.randint(5, 8)
        for _ in range(steps):
            x += rng.uniform(0.8, 1.6)
            y = 0.35 + rng.uniform(0, 0.45)
            points.append((x, y))
        return points

    def draw_on_canvas(self, canvas: Canvas, x: float, y: float) -> None:
        scale_x = self.width * 0.55
        scale_y = self.height * 0.45
        path = canvas.beginPath()
        start = self._points[0]
        path.moveTo(x + start[0] * scale_x, y + start[1] * scale_y)
        for px, py in self._points[1:]:
            path.lineTo(x + px * scale_x, y + py * scale_y)
        canvas.setStrokeColor(PRIMARY)
        canvas.setLineWidth(1.4)
        canvas.drawPath(path, stroke=1, fill=0)

        canvas.setFont("Helvetica-Oblique", 11)
        canvas.setFillColor(PRIMARY)
        canvas.drawString(x, y - 6 * mm, _display_doctor_name(self.doctor_name))

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(x, y - 11 * mm, f"Digital Signature ID: {self.signature_id}")
        canvas.drawString(
            x,
            y - 15 * mm,
            "This document was electronically generated and is valid without a physical stamp.",
        )


def _display_doctor_name(name: str) -> str:
    cleaned = name.strip()
    if cleaned.lower().startswith("dr."):
        return cleaned
    if cleaned.lower().startswith("dr "):
        return f"Dr. {cleaned[3:].strip()}"
    return f"Dr. {cleaned}"


def _generate_signature_id(doctor_name: str, patient_name: str, issued_at: datetime.datetime) -> str:
    seed = f"{doctor_name}|{patient_name}|{issued_at.isoformat()}"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:12].upper()
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"SIG-{digest[:4]}-{suffix}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "RxTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=PRIMARY,
            spaceAfter=2,
            alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "RxSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=MUTED,
            spaceAfter=0,
        ),
        "section": ParagraphStyle(
            "RxSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=SECONDARY,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "RxBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.black,
            leading=14,
        ),
        "label": ParagraphStyle(
            "RxLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            textColor=MUTED,
            spaceAfter=2,
        ),
        "value": ParagraphStyle(
            "RxValue",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            textColor=colors.black,
            spaceAfter=0,
        ),
        "diagnosis": ParagraphStyle(
            "RxDiagnosis",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=PRIMARY,
            leading=15,
            backColor=ACCENT,
            borderPadding=8,
        ),
        "instructions": ParagraphStyle(
            "RxInstructions",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.black,
            leading=15,
            leftIndent=6,
            rightIndent=6,
        ),
        "footer": ParagraphStyle(
            "RxFooter",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _header_table(st: dict, issued_at: datetime.datetime) -> Table:
    left = [
        Paragraph("HealthAI Medical Center", st["title"]),
        Paragraph("Clinical Prescription · Electronic Medical Record", st["subtitle"]),
    ]
    right = [
        Paragraph("PRESCRIPTION", ParagraphStyle(
            "RxBadge", fontName="Helvetica-Bold", fontSize=13,
            textColor=colors.white, alignment=TA_RIGHT,
        )),
        Paragraph(issued_at.strftime("%d %B %Y, %I:%M %p"), st["subtitle"]),
    ]
    data = [[left, right]]
    tbl = Table(data, colWidths=[11 * cm, 6 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), SECONDARY),
        ("BOX", (1, 0), (1, 0), 0, SECONDARY),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _info_panel(
    st: dict,
    *,
    patient_name: str,
    patient_details: Optional[str],
    doctor_name: str,
    doctor_specialization: Optional[str],
    license_number: Optional[str],
    prescription_id: str,
) -> Table:
    patient_block = [
        Paragraph("PATIENT", st["label"]),
        Paragraph(patient_name, st["value"]),
    ]
    if patient_details:
        patient_block.append(Paragraph(patient_details, st["subtitle"]))

    doctor_lines = [Paragraph("PRESCRIBING PHYSICIAN", st["label"]), Paragraph(_display_doctor_name(doctor_name), st["value"])]
    if doctor_specialization:
        doctor_lines.append(Paragraph(doctor_specialization, st["subtitle"]))
    if license_number:
        doctor_lines.append(Paragraph(f"License No: {license_number}", st["subtitle"]))
    doctor_lines.append(Paragraph(f"Rx ID: {prescription_id}", st["subtitle"]))

    data = [[patient_block, doctor_lines]]
    tbl = Table(data, colWidths=[8.5 * cm, 8.5 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def _medicines_table(medicines: Iterable) -> Table:
    header = ["#", "Medication", "Dosage", "Frequency", "Duration"]
    rows = [header]
    for idx, med in enumerate(medicines, start=1):
        rows.append([
            str(idx),
            med.name,
            med.dosage,
            med.frequency,
            med.duration,
        ])

    col_widths = [0.8 * cm, 5.5 * cm, 3.2 * cm, 3.5 * cm, 3.5 * cm]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9.5),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (1, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fbfb")]),
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def generate_prescription_pdf(
    filepath: str,
    *,
    doctor_name: str,
    doctor_specialization: Optional[str] = None,
    license_number: Optional[str] = None,
    patient_name: str,
    patient_details: Optional[str] = None,
    diagnosis: str,
    medicines: Iterable,
    instructions: Optional[str] = None,
    issued_at: Optional[datetime.datetime] = None,
) -> str:
    """
    Build a styled prescription PDF at `filepath`.
    Returns the digital signature ID embedded in the document.
    """
    issued_at = issued_at or datetime.datetime.now()
    prescription_id = f"RX-{issued_at.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    signature_id = _generate_signature_id(doctor_name, patient_name, issued_at)
    advice = instructions.strip() if instructions and instructions.strip() else (
        "Take all medications exactly as prescribed. Complete the full course even if symptoms improve. "
        "Return for follow-up if symptoms worsen or new symptoms appear."
    )

    st = _styles()
    signature = _SignatureBlock(doctor_name, signature_id)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.4 * cm,
        bottomMargin=2 * cm,
        title=f"Prescription - {patient_name}",
        author=_display_doctor_name(doctor_name),
    )

    story = [
        _header_table(st, issued_at),
        Spacer(1, 0.35 * cm),
        _info_panel(
            st,
            patient_name=patient_name,
            patient_details=patient_details,
            doctor_name=doctor_name,
            doctor_specialization=doctor_specialization,
            license_number=license_number,
            prescription_id=prescription_id,
        ),
        Spacer(1, 0.4 * cm),
        Paragraph("Diagnosis / Clinical Impression", st["section"]),
        Paragraph(diagnosis, st["diagnosis"]),
        Spacer(1, 0.25 * cm),
        Paragraph("Prescribed Medications", st["section"]),
        _medicines_table(medicines),
        Spacer(1, 0.35 * cm),
        Paragraph("Physician Advice &amp; Instructions", st["section"]),
        Table(
            [[Paragraph(advice, st["instructions"])]],
            colWidths=[16.5 * cm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafcfd")),
                ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]),
        ),
        Spacer(1, 0.6 * cm),
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=4, spaceAfter=12),
        Spacer(1, signature.height),
        Paragraph(
            "Disclaimer: This is a digitally generated prescription for clinical reference. "
            "Always consult your physician before altering dosage. "
            "In case of emergency, contact local emergency services immediately.",
            st["footer"],
        ),
    ]

    def _draw_signature(canvas: Canvas, _doc) -> None:
        canvas.saveState()
        sig_y = 3.2 * cm
        signature.draw_on_canvas(canvas, doc.leftMargin, sig_y)
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_signature, onLaterPages=_draw_signature)
    return signature_id
