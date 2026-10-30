import os
import uuid
from datetime import datetime
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    PageBreak, Image, Table, TableStyle, NextPageTemplate,
)
from reportlab.platypus.tableofcontents import TableOfContents

_FONT = "DocuFont"
_FONT_BOLD = "DocuFont-Bold"
_fonts_registered = False

CANDIDATE_DIRS = [
    os.path.join("static", "fonts"),
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/Library/Fonts",
]


def _find_font(name: str) -> str | None:
    for d in CANDIDATE_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def _register_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return
    regular = _find_font("DejaVuSans.ttf")
    bold = _find_font("DejaVuSans-Bold.ttf")
    if not regular:
        raise RuntimeError(
            "DejaVuSans.ttf не найден. Положите его в static/fonts/ "
            "или установите fonts-dejavu-core."
        )
    pdfmetrics.registerFont(TTFont(_FONT, regular))
    if bold:
        pdfmetrics.registerFont(TTFont(_FONT_BOLD, bold))
        pdfmetrics.registerFontFamily(_FONT, normal=_FONT, bold=_FONT_BOLD)
    else:
        pdfmetrics.registerFontFamily(_FONT, normal=_FONT, bold=_FONT)
    _fonts_registered = True


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title", fontName=_FONT_BOLD, fontSize=26, leading=32,
            alignment=TA_CENTER, spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName=_FONT, fontSize=14, leading=20,
            alignment=TA_CENTER, textColor=colors.HexColor("#555555"),
            spaceAfter=6,
        ),
        "meta": ParagraphStyle(
            "meta", fontName=_FONT, fontSize=11, leading=16,
            alignment=TA_CENTER, textColor=colors.HexColor("#666666"),
        ),
        "h1": ParagraphStyle(
            "h1", fontName=_FONT_BOLD, fontSize=18, leading=24,
            spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#1F1F2E"),
        ),
        "body": ParagraphStyle(
            "body", fontName=_FONT, fontSize=11, leading=16,
            alignment=TA_JUSTIFY, spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName=_FONT, fontSize=11, leading=16,
            alignment=TA_LEFT, leftIndent=16, bulletIndent=4, spaceAfter=4,
        ),
        "toc_title": ParagraphStyle(
            "toc_title", fontName=_FONT_BOLD, fontSize=16, leading=22,
            spaceAfter=10,
        ),
    }


class _Doc(BaseDocTemplate):
    def __init__(self, path: str, title: str, show_numbers: bool = True):
        super().__init__(
            path,
            pagesize=A4,
            leftMargin=22 * mm, rightMargin=18 * mm,
            topMargin=20 * mm, bottomMargin=20 * mm,
            title=title,
        )
        self._title = title
        self._show_numbers = show_numbers
        self._toc_entries: list[tuple[str, int]] = []

        frame_title = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height, id="title_frame",
        )
        frame_body = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height, id="body_frame",
        )
        self.addPageTemplates([
            PageTemplate(id="title", frames=[frame_title]),
            PageTemplate(id="body", frames=[frame_body], onPage=self._decorate),
        ])

    def _decorate(self, canvas, doc):
        canvas.saveState()
        if self._show_numbers and doc.page > 1:
            canvas.setFont(_FONT, 9)
            canvas.setFillColor(colors.HexColor("#888888"))
            canvas.drawCentredString(A4[0] / 2, 12 * mm, str(doc.page))
        canvas.setFont(_FONT, 8)
        canvas.setFillColor(colors.HexColor("#BBBBBB"))
        canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 12 * mm, self._title[:60])
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "h1":
            text = flowable.getPlainText()
            self._toc_entries.append((text, self.page))
            key = f"h1-{id(flowable)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=0, closed=False)
            self.notify("TOCEntry", (0, text, self.page))


def generate(content: dict[str, Any], options: dict[str, Any], out_dir: str) -> str:
    _register_fonts()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"doc_{uuid.uuid4().hex}.pdf")
    styles = _styles()

    include_title = options.get("include_title_page", True)
    include_toc = options.get("include_toc", True)
    include_conclusion = options.get("include_conclusion", True)
    include_sources = options.get("include_sources", False)

    story: list[Any] = []

    if include_title:
        story.append(NextPageTemplate("title"))
        story.append(Spacer(1, 60 * mm))
        story.append(Paragraph(_esc(content["title"]), styles["title"]))
        if content.get("subtitle"):
            story.append(Paragraph(_esc(content["subtitle"]), styles["subtitle"]))
        story.append(Spacer(1, 20 * mm))
        story.append(Paragraph(
            f"Тип: {_esc(options.get('doc_type', ''))}",
            styles["meta"],
        ))
        story.append(Paragraph(
            f"Дата: {datetime.utcnow().strftime('%d.%m.%Y')}",
            styles["meta"],
        ))
        story.append(PageBreak())

    story.append(NextPageTemplate("body"))

    if include_toc and len(content["sections"]) > 1:
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(
                "toc0", fontName=_FONT, fontSize=11, leading=16, leftIndent=0,
            ),
        ]
        story.append(Paragraph("Содержание", styles["toc_title"]))
        story.append(toc)
        story.append(PageBreak())

    for section in content["sections"]:
        heading = _esc(section["heading"] or "Раздел")
        p = Paragraph(heading, styles["h1"])
        story.append(p)
        for para in section["paragraphs"]:
            story.append(Paragraph(_esc(para), styles["body"]))
        for bullet in section["bullets"]:
            story.append(Paragraph(f"• {_esc(bullet)}", styles["bullet"]))
        story.append(Spacer(1, 4 * mm))

    if include_conclusion and content.get("conclusion"):
        story.append(Paragraph("Заключение", styles["h1"]))
        story.append(Paragraph(_esc(content["conclusion"]), styles["body"]))

    if include_sources and content.get("sources"):
        story.append(Paragraph("Список источников", styles["h1"]))
        for i, src in enumerate(content["sources"], 1):
            story.append(Paragraph(f"{i}. {_esc(src)}", styles["bullet"]))

    doc = _Doc(path, title=content["title"], show_numbers=True)
    doc.multiBuild(story)
    return path


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
