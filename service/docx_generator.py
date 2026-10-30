import os
import uuid
from typing import Any


def generate(content: dict[str, Any], options: dict[str, Any], out_dir: str) -> str:
    from docx import Document as Docx

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"doc_{uuid.uuid4().hex}.docx")

    doc = Docx()
    doc.add_heading(content["title"], level=0)
    for section in content["sections"]:
        doc.add_heading(section["heading"], level=1)
        for p in section["paragraphs"]:
            doc.add_paragraph(p)
        for b in section["bullets"]:
            doc.add_paragraph(b, style="List Bullet")
    if content.get("conclusion"):
        doc.add_heading("Заключение", level=1)
        doc.add_paragraph(content["conclusion"])
    doc.save(path)
    return path
