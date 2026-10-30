import os
import uuid
from datetime import datetime
from typing import Any

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

COLORS = {
    "purple": RGBColor(0x8B, 0x5C, 0xF6),
    "purple_light": RGBColor(0xA8, 0x55, 0xF7),
    "blue": RGBColor(0x38, 0xBD, 0xF8),
    "dark": RGBColor(0x08, 0x08, 0x10),
    "dark2": RGBColor(0x17, 0x17, 0x29),
    "white": RGBColor(0xFF, 0xFF, 0xFF),
    "gray": RGBColor(0x9C, 0xA3, 0xAF),
}


def _clear_placeholders(slide) -> None:
    for sh in list(slide.placeholders):
        sp = sh._element
        sp.getparent().remove(sp)


def _add_background(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_text(slide, left, top, width, height, text, size=18,
              bold=False, color=COLORS["white"], align=PP_ALIGN.LEFT) -> None:
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Calibri"


def _add_accent_bar(slide, left, top) -> None:
    bar = slide.shapes.add_shape(
        1, left, top, Inches(0.8), Emu(45000),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLORS["purple"]
    bar.line.fill.background()


def _max_chars_per_slide() -> int:
    return 600


def generate(content: dict[str, Any], options: dict[str, Any], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"doc_{uuid.uuid4().hex}.pptx")

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank = prs.slide_layouts[6]
    title_layout = prs.slide_layouts[0]
    content_layout = prs.slide_layouts[1]

    # Титульный слайд
    slide = prs.slides.add_slide(title_layout)
    _add_background(slide, COLORS["dark"])
    slide.shapes.title.text = content["title"]
    slide.shapes.title.text_frame.paragraphs[0].runs[0].font.color.rgb = COLORS["white"]
    slide.shapes.title.text_frame.paragraphs[0].runs[0].font.bold = True
    slide.shapes.title.text_frame.paragraphs[0].runs[0].font.size = Pt(44)

    if len(slide.placeholders) > 1:
        sub = slide.placeholders[1]
        sub.text = content.get("subtitle") or options.get("doc_type", "")
        for p in sub.text_frame.paragraphs:
            for r in p.runs:
                r.font.color.rgb = COLORS["purple_light"]
                r.font.size = Pt(22)

    _add_text(
        slide,
        Inches(0.5), Inches(6.7), Inches(12), Inches(0.5),
        datetime.utcnow().strftime("%d.%m.%Y  •  DocuFlow AI"),
        size=12, color=COLORS["gray"],
    )

    # Контентные слайды
    for section in content["sections"]:
        blocks = _split_section(section)
        for idx, (heading, paragraphs, bullets) in enumerate(blocks):
            slide = prs.slides.add_slide(content_layout)
            _add_background(slide, COLORS["dark2"])

            slide.shapes.title.text = (
                heading if idx == 0 else f"{heading} (продолжение)"
            )
            tp = slide.shapes.title.text_frame.paragraphs[0]
            if tp.runs:
                tp.runs[0].font.color.rgb = COLORS["white"]
                tp.runs[
