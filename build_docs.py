"""Render proposal.md and mini_rfc.md to PDF with reportlab (pip install reportlab).

Usage: python build_docs.py
"""
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, Paragraph,
                                Preformatted, SimpleDocTemplate, Spacer, Table,
                                TableStyle, KeepTogether)

HERE = os.path.dirname(os.path.abspath(__file__))
ss = getSampleStyleSheet()
BODY = ParagraphStyle("B", parent=ss["BodyText"], fontName="Times-Roman",
                      fontSize=10, leading=12.6, spaceAfter=4)
CELL = ParagraphStyle("C", parent=BODY, fontSize=8.2, leading=10, spaceAfter=0)
CELLH = ParagraphStyle("CH", parent=CELL, fontName="Times-Bold",
                       textColor=colors.white)
H1 = ParagraphStyle("H1", parent=ss["Title"], fontName="Times-Bold",
                    fontSize=16, leading=19, alignment=TA_CENTER, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Times-Bold",
                    fontSize=12.5, leading=15, spaceBefore=9, spaceAfter=3,
                    textColor=colors.HexColor("#1F3864"))
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName="Times-Bold",
                    fontSize=10.5, leading=13, spaceBefore=6, spaceAfter=2)
CODE = ParagraphStyle("K", fontName="Courier", fontSize=7.6, leading=9.2,
                      backColor=colors.HexColor("#F3F3F3"), borderPadding=4,
                      spaceBefore=3, spaceAfter=6)


def inline(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r'<font face="Courier" size="8.5">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", text)
    return text


def make_table(rows, aligns):
    data = []
    for r, row in enumerate(rows):
        data.append([Paragraph(inline(c), CELLH if r == 0 else CELL) for c in row])
    ncol = len(rows[0])
    avail = A4[0] - 4 * cm
    weights = [max(6, max(len(row[c]) for row in rows)) for c in range(ncol)]
    weights = [min(w, 70) for w in weights]
    total = sum(weights)
    t = Table(data, colWidths=[avail * w / total for w in weights], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#EEF2F8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return [t, Spacer(1, 5)]


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render(md_path, pdf_path, title, footer):
    lines = open(md_path, encoding="utf-8").read().splitlines()
    story, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i]); i += 1
            story.append(Preformatted("\n".join(block), CODE))
        elif ln.startswith("# "):
            story.append(Paragraph(inline(ln[2:]), H1))
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#1F3864")))
            story.append(Spacer(1, 4))
        elif ln.startswith("## "):
            story.append(Paragraph(inline(ln[3:]), H2))
        elif ln.startswith("### ") or ln.startswith("#### "):
            story.append(Paragraph(inline(ln.lstrip("#").strip()), H3))
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s:|-]+\|$", lines[i]):
                    rows.append(split_row(lines[i]))
                i += 1
            story += make_table(rows, None)
            continue
        elif re.match(r"^(\s*)([-*]|\d+\.)\s+", ln):
            items = []
            ordered = bool(re.match(r"^\s*\d+\.", ln))
            while i < len(lines) and re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i]):
                text = re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i])
                items.append(ListItem(Paragraph(inline(text), BODY), leftIndent=14))
                i += 1
            story.append(ListFlowable(items, bulletType="1" if ordered else "bullet",
                                      start=None if not ordered else 1,
                                      bulletFontSize=8, leftIndent=14))
            continue
        elif ln.strip():
            para = [ln.strip() + ("<br/>" if ln.endswith("  ") else "")]
            while (i + 1 < len(lines) and lines[i + 1].strip()
                   and not re.match(r"^(#|\||```|\s*([-*]|\d+\.)\s)", lines[i + 1])):
                i += 1
                para.append(lines[i].strip() + ("<br/>" if lines[i].endswith("  ") else ""))
            story.append(Paragraph(inline(" ".join(para)).replace("&lt;br/&gt;", "<br/>"), BODY))
        i += 1

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, 1.2 * cm, footer)
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, "Page %d" % doc.page)
        canvas.restoreState()

    SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=1.8 * cm, bottomMargin=2 * cm, title=title,
                      author="CSE361 Team").build(story, onFirstPage=decorate,
                                                  onLaterPages=decorate)


if __name__ == "__main__":
    foot = "CSE361 (UG2023) - Peer-to-Peer Content-Addressable Chunk Streaming Protocol"
    render(os.path.join(HERE, "proposal.md"), os.path.join(HERE, "proposal.pdf"),
           "Project Proposal - P2P-CASP", foot)
    render(os.path.join(HERE, "mini_rfc.md"), os.path.join(HERE, "mini_rfc.pdf"),
           "Mini-RFC - P2P-CASP", foot)
    print("Wrote proposal.pdf and mini_rfc.pdf")
