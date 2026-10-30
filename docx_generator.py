import os
import uuid
from datetime import datetime
from typing import Any

from docx import Document as Docx
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def _set_base_font(doc: Docx) -> None:
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), "Calibri")
    rfonts.set(qn("w:cs"), "Calibri")


def _add_page_number_footer(section) -> None:
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    fld1 = OxmlElement("w:fldChar")
    fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    run._r.append(fld1)
    run._r.append(instr)
    run._r.append(fld2)


def generate(content: dict[str, Any], options: dict[str, Any], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"doc_{uuid.uuid4().hex}.docx")

    include_title = options.get("include_title_page", True)
    include_toc = options.get("include_toc", True)
    include_conclusion = options.get("include_conclusion", True)
    include_sources = options.get("include_sources", False)

    doc = Docx()
    _set_base_font(doc)

    section = doc.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(1.5)
    _add_page_number_footer(section)

    if include_title:
        for _ in range(8):
            doc.add_paragraph()
        t = doc.add_paragraph()
        t.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = t.add_run(content["title"])
        run.bold = True
        run.font.size = Pt(26)

        if content.get("subtitle"):
            s = doc.add_paragraph()
            s.alignment = WD_ALIGN_PARAGRAPH.CENTER
            sr = s.add_run(content["subtitle"])
            sr.italic = True
            sr.font.size = Pt(14)
            sr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

        for _ in range(10):
            doc.add_paragraph()

        meta = doc.add_paragraph()
        meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
        meta.add_run(f"Тип: {options.get('doc_type', '')}\n").font.size = Pt(11)
        meta.add_run(datetime.utcnow().strftime("%d.%m.%Y")).font.size = Pt(11)

        doc.add_page_break()

    if include_toc and len(content["sections"]) > 1:
        doc.add_heading("Содержание", level=1)
        p = doc.add_paragraph()
        fld_begin = OxmlElement("w:fldChar")
        fld_begin.set(qn("w:fldCharType"), "begin")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = 'TOC \\o "1-2" \\h \\z \\u'
        fld_sep = OxmlElement("w:fldChar")
        fld_sep.set(qn("w:fldCharType"), "separate")
        fld_end = OxmlElement("w:fldChar")
        fld_end.set(qn("w:fldCharType"), "end")
        run = p.add_run()
        run._r.append(fld_begin)
        run._r.append(instr)
        run._r.append(fld_sep)
        run._r.append(fld_end)
        doc.add_page_break()

    for sec in content["sections"]:
        doc.add_heading(sec["heading"] or "Раздел", level=1)
        for para in sec["paragraphs"]:
            p = doc.add_paragraph(para)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.first_line_indent = Cm(1.0)
            p.paragraph_format.space_after = Pt(6)
        for bullet in sec["bullets"]:
            p = doc.add_paragraph(bullet, style="List Bullet")

    if include_conclusion and content.get("conclusion"):
        doc.add_heading("Заключение", level=1)
        p = doc.add_paragraph(content["conclusion"])
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    if include_sources and content.get("sources"):
        doc.add_heading("Список источников", level=1)
        for i, src in enumerate(content["sources"], 1):
            doc.add_paragraph(f"{i}. {src}", style="List Number")

    doc.save(path)
    return path
