"""Render plain text (quotations, reports) to a simple, clean PDF."""
from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def text_to_pdf(title: str, body: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    left = 20 * mm
    top = height - 20 * mm
    line_height = 6 * mm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(left, top, title)
    y = top - 12 * mm

    c.setFont("Helvetica", 10)
    max_chars = 95
    for raw_line in body.splitlines() or [""]:
        # naive wrap
        chunks = [raw_line[i : i + max_chars] for i in range(0, len(raw_line), max_chars)] or [""]
        for chunk in chunks:
            if y < 20 * mm:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = top
            c.drawString(left, y, chunk)
            y -= line_height

    c.showPage()
    c.save()
    return buf.getvalue()
