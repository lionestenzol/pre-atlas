"""
Build Chapter 1 PDF from edited markdown.
Uses fpdf2 for clean, publishable output.
"""
from fpdf import FPDF
import re

class ChapterPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, "Power Dynamics Mastery Guide", align="C")
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, str(self.page_no()), align="C")

    def chapter_title(self, title):
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(0, 0, 0)
        self.ln(40)
        self.multi_cell(0, 14, title, align="C")
        self.ln(5)

    def subtitle(self, text):
        self.set_font("Helvetica", "I", 14)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 8, text, align="C")
        self.ln(15)

    def section_heading(self, text):
        self.ln(6)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 10, text)
        self.ln(3)

    def body_text(self, text):
        self.set_font("Times", "", 12)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 7, text)
        self.ln(3)

    def italic_text(self, text):
        self.set_font("Times", "I", 12)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 7, text)
        self.ln(3)

    def bold_text(self, text):
        self.set_font("Times", "B", 12)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 7, text)
        self.ln(2)

    def separator(self):
        self.ln(4)
        self.set_draw_color(180, 180, 180)
        x = self.get_x()
        w = self.w - self.l_margin - self.r_margin
        center = x + w / 2
        self.line(center - 30, self.get_y(), center + 30, self.get_y())
        self.ln(8)


def parse_markdown(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into lines
    lines = content.split("\n")
    elements = []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # H1 title
        if line.startswith("# ") and not line.startswith("## "):
            elements.append(("title", line[2:].strip()))
            i += 1
            continue

        # H3 subtitle
        if line.startswith("### "):
            elements.append(("subtitle", line[4:].strip()))
            i += 1
            continue

        # H2 section heading
        if line.startswith("## "):
            elements.append(("heading", line[3:].strip()))
            i += 1
            continue

        # Horizontal rule
        if line.strip() == "---":
            elements.append(("separator", None))
            i += 1
            continue

        # Collect paragraph (consecutive non-empty, non-heading lines)
        para_lines = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith("#") and lines[i].strip() != "---":
            para_lines.append(lines[i].rstrip())
            i += 1

        if para_lines:
            para = " ".join(para_lines)
            # Detect if it's a bold law line
            if para.startswith("**") and "**" in para[2:]:
                elements.append(("law", para))
            else:
                elements.append(("paragraph", para))

    return elements


def sanitize(text):
    """Replace Unicode chars that core fonts can't handle."""
    text = text.replace("\u2014", " - ")   # em dash
    text = text.replace("\u2013", " - ")   # en dash
    text = text.replace("\u2018", "'")     # left single quote
    text = text.replace("\u2019", "'")     # right single quote
    text = text.replace("\u201c", '"')     # left double quote
    text = text.replace("\u201d", '"')     # right double quote
    text = text.replace("\u2026", "...")   # ellipsis
    return text


def build_pdf(elements, output_path):
    pdf = ChapterPDF()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_left_margin(25)
    pdf.set_right_margin(25)
    pdf.add_page()

    for etype, content in elements:
        if content:
            content = sanitize(content)
        if etype == "title":
            pdf.chapter_title(content)

        elif etype == "subtitle":
            pdf.subtitle(content)

        elif etype == "heading":
            pdf.section_heading(content)

        elif etype == "separator":
            pdf.separator()

        elif etype == "law":
            # Parse bold + regular text
            # Pattern: **bold text.** regular text
            match = re.match(r'\*\*(.+?)\*\*\s*(.*)', content)
            if match:
                bold_part = match.group(1)
                rest = match.group(2)
                pdf.bold_text(bold_part)
                if rest:
                    pdf.body_text(rest)
            else:
                pdf.body_text(content.replace("**", ""))

        elif etype == "paragraph":
            # Handle inline italics: *text* or _text_
            # For simplicity, check if paragraph has italic markers
            cleaned = content.replace("--", " - ")  # em dash as spaced hyphen

            if cleaned.startswith("*") and not cleaned.startswith("**"):
                # Full italic paragraph
                cleaned = cleaned.strip("*").strip("_")
                pdf.italic_text(cleaned)
            else:
                # Replace *text* with text (fpdf2 doesn't do inline styling easily)
                # We'll just clean the markers for now
                cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
                cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)
                pdf.body_text(cleaned)

    pdf.output(output_path)
    print(f"PDF written to {output_path}")


if __name__ == "__main__":
    import os
    base = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(base, "chapter_01_final.md")
    pdf_path = os.path.join(base, "Chapter_01_The_Anatomy_of_Disrespect.pdf")
    elements = parse_markdown(md_path)
    build_pdf(elements, pdf_path)
