"""
Build the complete Power Dynamics Mastery Guide PDF.
Assembles: title page, table of contents, introduction, all 12 chapters, author bio.
"""
from fpdf import FPDF
import re
import os

BASE = os.path.dirname(os.path.abspath(__file__))

CHAPTERS = [
    ("chapter_01_final.md", "The Anatomy of Disrespect"),
    ("chapter_02_final.md", "Confidence as a Weapon"),
    ("chapter_03_final.md", "Reading People Like Code"),
    ("chapter_04_final.md", "Boundaries as Power"),
    ("chapter_05_final.md", "Control Games People Play"),
    ("chapter_06_final.md", "When Your Presence Threatens People"),
    ("chapter_07_final.md", "The Validation Trap"),
    ("chapter_08_final.md", "Workplace Power Dynamics"),
    ("chapter_09_final.md", "Deprogramming: Seeing the Game"),
    ("chapter_10_final.md", "The Power of Walking Away"),
    ("chapter_11_final.md", "Family as the First Power Structure"),
    ("chapter_12_final.md", "The Hierarchy Nobody Talks About"),
]


class BookPDF(FPDF):
    def header(self):
        if self.page_no() > 2:  # Skip title page and TOC
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, "Power Dynamics Mastery Guide", align="C")
            self.ln(5)

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, str(self.page_no()), align="C")


def sanitize(text):
    """Replace Unicode chars that core fonts can't handle."""
    text = text.replace("\u2014", " - ")
    text = text.replace("\u2013", " - ")
    text = text.replace("\u2018", "'")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    text = text.replace("\u2026", "...")
    return text


def parse_markdown(filepath):
    """Parse markdown into structured elements."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    elements = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

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

        # Collect paragraph
        para_lines = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith("#") and lines[i].strip() != "---":
            para_lines.append(lines[i].rstrip())
            i += 1

        if para_lines:
            para = " ".join(para_lines)
            if para.startswith("**") and "**" in para[2:]:
                elements.append(("law", para))
            else:
                elements.append(("paragraph", para))

    return elements


def render_title_page(pdf):
    """Render the book title page."""
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 16, "POWER DYNAMICS\nMASTERY GUIDE", align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "Understanding the Invisible Rules", align="C")
    pdf.ln(20)
    pdf.set_draw_color(180, 180, 180)
    w = pdf.w - pdf.l_margin - pdf.r_margin
    center_x = pdf.l_margin + w / 2
    pdf.line(center_x - 40, pdf.get_y(), center_x + 40, pdf.get_y())
    pdf.ln(15)
    pdf.set_font("Helvetica", "I", 12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "12 Chapters. 12 Laws. One Framework.", align="C")
    pdf.ln(6)
    pdf.cell(0, 8, "Extracted from 1,397 conversations.", align="C")


def render_toc(pdf, chapter_pages):
    """Render table of contents."""
    pdf.add_page()
    pdf.ln(15)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 12, "CONTENTS", align="C")
    pdf.ln(15)

    # Introduction
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(30, 30, 30)
    intro_page = chapter_pages.get("Introduction", "")
    pdf.cell(0, 8, f"  Introduction {'.' * 50} {intro_page}")
    pdf.ln(6)

    pdf.ln(3)

    for i, (_, title) in enumerate(CHAPTERS, 1):
        page = chapter_pages.get(title, "")
        prefix = f"  {i}. "
        dots = "." * max(3, 50 - len(prefix) - len(title))
        pdf.cell(0, 8, f"{prefix}{title} {dots} {page}")
        pdf.ln(6)

    pdf.ln(3)
    bio_page = chapter_pages.get("About the Author", "")
    pdf.cell(0, 8, f"  About the Author {'.' * 46} {bio_page}")
    pdf.ln(6)


def render_elements(pdf, elements):
    """Render parsed markdown elements to PDF."""
    for etype, content in elements:
        if content:
            content = sanitize(content)

        if etype == "title":
            pdf.ln(30)
            pdf.set_font("Helvetica", "B", 26)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 13, content, align="C")
            pdf.ln(5)

        elif etype == "subtitle":
            pdf.set_font("Helvetica", "I", 13)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(0, 8, content, align="C")
            pdf.ln(12)

        elif etype == "heading":
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 15)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 9, content)
            pdf.ln(3)

        elif etype == "separator":
            pdf.ln(3)
            pdf.set_draw_color(180, 180, 180)
            x = pdf.get_x()
            w = pdf.w - pdf.l_margin - pdf.r_margin
            center = x + w / 2
            pdf.line(center - 25, pdf.get_y(), center + 25, pdf.get_y())
            pdf.ln(6)

        elif etype == "law":
            match = re.match(r'\*\*(.+?)\*\*\s*(.*)', content)
            if match:
                bold_part = match.group(1)
                rest = match.group(2)
                pdf.set_font("Times", "B", 12)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(0, 7, bold_part)
                pdf.ln(1)
                if rest:
                    pdf.set_font("Times", "", 12)
                    pdf.multi_cell(0, 7, rest)
                    pdf.ln(2)
            else:
                pdf.set_font("Times", "", 12)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(0, 7, content.replace("**", ""))
                pdf.ln(2)

        elif etype == "paragraph":
            cleaned = content.replace("--", " - ")
            if cleaned.startswith("*") and not cleaned.startswith("**"):
                cleaned = cleaned.strip("*").strip("_")
                pdf.set_font("Times", "I", 12)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(0, 7, cleaned)
                pdf.ln(3)
            else:
                cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
                cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)
                pdf.set_font("Times", "", 12)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(0, 7, cleaned)
                pdf.ln(3)


def build_book():
    """Build the complete book PDF."""
    pdf = BookPDF()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_left_margin(25)
    pdf.set_right_margin(25)

    # Title page
    render_title_page(pdf)

    # Placeholder TOC page (we'll come back to fill it)
    toc_page_num = pdf.page_no() + 1

    # First pass: render everything and track page numbers
    chapter_pages = {}

    # Introduction
    pdf.add_page()
    intro_page = pdf.page_no()
    chapter_pages["Introduction"] = intro_page
    intro_path = os.path.join(BASE, "book_intro.md")
    intro_elements = parse_markdown(intro_path)
    render_elements(pdf, intro_elements)

    # Chapters
    for filename, title in CHAPTERS:
        filepath = os.path.join(BASE, filename)
        if not os.path.exists(filepath):
            print(f"WARNING: {filename} not found, skipping")
            continue

        pdf.add_page()
        chapter_pages[title] = pdf.page_no()
        elements = parse_markdown(filepath)
        render_elements(pdf, elements)

    # Author bio
    pdf.add_page()
    chapter_pages["About the Author"] = pdf.page_no()
    bio_path = os.path.join(BASE, "author_bio.md")
    bio_elements = parse_markdown(bio_path)
    render_elements(pdf, bio_elements)

    # Now build the final PDF with TOC
    final_pdf = BookPDF()
    final_pdf.set_auto_page_break(auto=True, margin=25)
    final_pdf.set_left_margin(25)
    final_pdf.set_right_margin(25)

    # Title page
    render_title_page(final_pdf)

    # TOC (page numbers will be offset by 1 because of TOC page itself)
    adjusted_pages = {}
    for key, page in chapter_pages.items():
        adjusted_pages[key] = page + 1  # +1 for TOC page
    render_toc(final_pdf, adjusted_pages)

    # Introduction
    final_pdf.add_page()
    render_elements(final_pdf, parse_markdown(os.path.join(BASE, "book_intro.md")))

    # Chapters
    for filename, title in CHAPTERS:
        filepath = os.path.join(BASE, filename)
        if not os.path.exists(filepath):
            continue
        final_pdf.add_page()
        elements = parse_markdown(filepath)
        render_elements(final_pdf, elements)

    # Author bio
    final_pdf.add_page()
    render_elements(final_pdf, parse_markdown(os.path.join(BASE, "author_bio.md")))

    output_path = os.path.join(BASE, "Power_Dynamics_Mastery_Guide.pdf")
    final_pdf.output(output_path)
    print(f"Book PDF written to {output_path}")
    print(f"Total pages: {final_pdf.page_no()}")


if __name__ == "__main__":
    build_book()
