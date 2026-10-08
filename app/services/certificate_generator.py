"""PDF certificate generation service using ReportLab.

This module is intentionally kept free of any database or FastAPI imports
so it can be tested in complete isolation.
"""

import textwrap
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_CENTER


@dataclass
class CertificateData:
    """All the information needed to render one certificate PDF."""

    recipient_name: str
    recipient_email: str
    certificate_title: str
    course_name: str
    event_name: str
    issue_date: str          # e.g. "October 08, 2026"
    issuer_name: str
    certificate_number: str


def generate_certificate_pdf(data: CertificateData, output_path: Path) -> None:
    """
    Render a professional-looking certificate PDF to *output_path*.

    Raises:
        OSError: if the output directory cannot be written.
        Exception: for any ReportLab rendering failure.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    page_width, page_height = landscape(A4)
    c = canvas.Canvas(str(output_path), pagesize=landscape(A4))

    _draw_background(c, page_width, page_height)
    _draw_border(c, page_width, page_height)
    _draw_content(c, data, page_width, page_height)

    c.save()


# ---------------------------------------------------------------------------
# Private drawing helpers
# ---------------------------------------------------------------------------

def _draw_background(c: canvas.Canvas, w: float, h: float) -> None:
    """Fills the page with a cream/off-white background."""
    c.setFillColor(colors.HexColor("#FDFAF4"))
    c.rect(0, 0, w, h, fill=1, stroke=0)


def _draw_border(c: canvas.Canvas, w: float, h: float) -> None:
    """Draws a layered decorative border."""
    margin = 18 * mm

    # Outer gold border
    c.setStrokeColor(colors.HexColor("#B8960C"))
    c.setLineWidth(3)
    c.rect(margin, margin, w - 2 * margin, h - 2 * margin, fill=0, stroke=1)

    # Inner thin border
    inner_margin = margin + 6 * mm
    c.setStrokeColor(colors.HexColor("#D4AF37"))
    c.setLineWidth(1)
    c.rect(inner_margin, inner_margin, w - 2 * inner_margin, h - 2 * inner_margin, fill=0, stroke=1)

    # Corner decorative squares
    sq = 8 * mm
    c.setFillColor(colors.HexColor("#D4AF37"))
    for x, y in [
        (margin, h - margin - sq),                        # top-left
        (w - margin - sq, h - margin - sq),               # top-right
        (margin, margin),                                  # bottom-left
        (w - margin - sq, margin),                         # bottom-right
    ]:
        c.rect(x, y, sq, sq, fill=1, stroke=0)


def _draw_content(c: canvas.Canvas, data: CertificateData, w: float, h: float) -> None:
    """Places all text content on the certificate."""
    center_x = w / 2

    # ---- Organisation name at the top ----
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor("#5C4A1E"))
    c.drawCentredString(center_x, h - 55 * mm, data.issuer_name.upper())

    # Decorative separator line
    line_y = h - 62 * mm
    c.setStrokeColor(colors.HexColor("#D4AF37"))
    c.setLineWidth(1.5)
    c.line(center_x - 60 * mm, line_y, center_x + 60 * mm, line_y)

    # ---- Certificate title ----
    c.setFont("Times-BoldItalic", 36)
    c.setFillColor(colors.HexColor("#1A1A2E"))
    c.drawCentredString(center_x, h - 82 * mm, data.certificate_title)

    # ---- Presentation line ----
    c.setFont("Helvetica", 13)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawCentredString(center_x, h - 100 * mm, "This certificate is proudly presented to")

    # ---- Recipient name ----
    c.setFont("Times-BoldItalic", 30)
    c.setFillColor(colors.HexColor("#B8960C"))
    c.drawCentredString(center_x, h - 118 * mm, data.recipient_name)

    # Underline beneath recipient name
    name_width = c.stringWidth(data.recipient_name, "Times-BoldItalic", 30)
    line_start = center_x - name_width / 2
    c.setStrokeColor(colors.HexColor("#B8960C"))
    c.setLineWidth(1)
    c.line(line_start, h - 121 * mm, line_start + name_width, h - 121 * mm)

    # ---- Course / event ----
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawCentredString(center_x, h - 135 * mm, f"for successfully completing")

    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor("#1A1A2E"))
    c.drawCentredString(center_x, h - 145 * mm, data.course_name)

    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawCentredString(center_x, h - 155 * mm, f"presented at  {data.event_name}")

    # ---- Bottom section: date | cert number | issuer ----
    bottom_y = 42 * mm

    # Issue date (left third)
    left_x = w * 0.25
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawCentredString(left_x, bottom_y + 8 * mm, data.issue_date)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawCentredString(left_x, bottom_y, "DATE ISSUED")
    c.line(left_x - 30 * mm, bottom_y + 5 * mm, left_x + 30 * mm, bottom_y + 5 * mm)

    # Certificate number (centre)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawCentredString(center_x, bottom_y + 8 * mm, data.certificate_number)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawCentredString(center_x, bottom_y, "CERTIFICATE NO.")
    c.line(center_x - 30 * mm, bottom_y + 5 * mm, center_x + 30 * mm, bottom_y + 5 * mm)

    # Issuer (right third)
    right_x = w * 0.75
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawCentredString(right_x, bottom_y + 8 * mm, data.issuer_name)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawCentredString(right_x, bottom_y, "AUTHORIZED BY")
    c.line(right_x - 30 * mm, bottom_y + 5 * mm, right_x + 30 * mm, bottom_y + 5 * mm)
