"""Build the one-page PDF from the same content as /guide (requires reportlab)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "web/static/guides/lingjian-quick-start.pdf"


def build(output: Path, language: str = "en") -> None:
    filename = "user_guide.json" if language == "zh" else "user_guide.en.json"
    guide = json.loads((ROOT / "web" / filename).read_text(encoding="utf-8"))
    labels = guide["ui"]
    pdfmetrics.registerFont(TTFont("GuideCJK", str(ROOT / "assets/fonts/LXGWWenKai-Regular.ttf")))
    font = "GuideCJK" if language == "zh" else "Helvetica"
    wrap = "CJK" if language == "zh" else None
    ink, muted, accent = (colors.HexColor(value) for value in ("#29292f", "#63636f", "#7560b7"))
    width = A4[0] - 88
    styles = {
        "title": ParagraphStyle("title", fontName=font, fontSize=25, leading=32, textColor=ink),
        "heading": ParagraphStyle("heading", fontName=font, fontSize=13.5, leading=19, textColor=ink),
        "body": ParagraphStyle("body", fontName=font, fontSize=10.5, leading=16 if language == "zh" else 14, textColor=ink, wordWrap=wrap),
        "small": ParagraphStyle("small", fontName=font, fontSize=9.5, leading=14 if language == "zh" else 12.5, textColor=muted, wordWrap=wrap),
        "number": ParagraphStyle("number", fontName=font, fontSize=15, leading=20, textColor=accent),
    }

    def p(text, style="body"):
        return Paragraph(escape(text), styles[style])

    def box(text, background):
        table = Table([[p(text, "small")]], colWidths=[width])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))
        return table

    story = [p(labels["pdf_eyebrow"], "small"), Spacer(1, 6), p(guide["title"], "title"),
             Spacer(1, 6), p(guide["subtitle"]), Spacer(1, 6)]
    story.append(Paragraph(f'<link href="{guide["url"]}" color="#7560b7">{guide["url"]}</link>', styles["body"]))
    story.extend([p(guide["access"], "small"), Spacer(1, 15)])
    for number, step in enumerate(guide["steps"], 1):
        table = Table([[p(f"0{number}", "number"), [p(step["title"], "heading"), p(step["body"])]]],
                      colWidths=[35, width - 35])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(table)
    story.extend([box(guide["ai_tip"], "#f2eef8"), Spacer(1, 14), p(labels["storage_title"], "heading"), Spacer(1, 5)])
    storage = Table([[p(row["place"]), p(row["content"], "small")] for row in guide["storage"]], colWidths=[88, width - 88])
    storage.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), .5, colors.HexColor("#e9e9ed")),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([storage, Spacer(1, 10), box(guide["storage_warning"], "#fcf8f0"), Spacer(1, 10),
                  p(labels["team_label"] + guide["team_tip"], "small")])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#e9e9ed"))
        canvas.line(44, 42, A4[0] - 44, 42)
        canvas.setFont(font, 8)
        canvas.setFillColor(muted)
        canvas.drawString(44, 27, labels["pdf_more"] + guide["url"] + "/guide?lang=" + language)
        canvas.linkURL(guide["url"] + "/guide?lang=" + language, (44, 24, 360, 38), relative=0)
        canvas.drawRightString(A4[0] - 44, 27, labels["brand"] + " Web Studio")
        canvas.restoreState()

    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=44, rightMargin=44,
                                 topMargin=34, bottomMargin=54, title=guide["title"], author="LingJian Team")
    document.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("en", "zh"), default="en")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (DEFAULT_OUTPUT if args.language == "zh" else DEFAULT_OUTPUT.with_name("lingjian-quick-start.en.pdf"))
    build(output, args.language)
    print(output)
