import os
import uuid
from typing import Any


def generate(content: dict[str, Any], options: dict[str, Any], out_dir: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"doc_{uuid.uuid4().hex}.pdf")

    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 60
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, content["title"][:80])
    y -= 40
    c.setFont("Helvetica", 11)

    for section in content["sections"]:
        if y < 80:
            c.showPage()
            y = height - 60
            c.setFont("Helvetica", 11)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y, section["heading"][:80])
        y -= 20
        c.setFont("Helvetica", 11)
        for p in section["paragraphs"]:
            for line in _wrap(p, 90):
                if y < 60:
                    c.showPage()
                    y = height - 60
                    c.setFont("Helvetica", 11)
                c.drawString(50, y, line)
                y -= 15
        y -= 10

    c.save()
    return path


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]
