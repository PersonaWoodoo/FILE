import os
import uuid
from typing import Any


def generate(content: dict[str, Any], options: dict[str, Any], out_dir: str) -> str:
    from pptx import Presentation
    from pptx.util import Inches, Pt

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"doc_{uuid.uuid4().hex}.pptx")

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    title_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_layout)
    slide.shapes.title.text = content["title"]
    if slide.placeholders[1]:
        slide.placeholders[1].text = content.get("subtitle", "")

    for section in content["sections"]:
        layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(layout)
        slide.shapes.title.text = section["heading"]
        body = slide.placeholders[1].text_frame
        body.clear()
        items = section["paragraphs"][:3] + section["bullets"][:3]
        for i, line in enumerate(items):
            p = body.paragraphs[0] if i == 0 else body.add_paragraph()
            p.text = line[:200]
            p.font.size = Pt(18)

    prs.save(path)
    return path
