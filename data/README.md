# The Anatomy of Disrespect — Book Pipeline

Power dynamics book extracted from 1,397 conversations using AI-assisted mining, clustering, and chapter generation.

## What's Here

| File | Description |
|------|-------------|
| `chapter_01_final.md` | Chapter 1 final manuscript (2,173 words) |
| `chapter_01_draft.md` | Earlier draft for reference |
| `ch1_top20_passages.json` | Top 20 ranked source passages for Chapter 1 |
| `build_pdf.py` | Markdown → PDF converter (fpdf2) |
| `Chapter_01_The_Anatomy_of_Disrespect.pdf` | Generated PDF output |
| `projections/today.json` | Daily cognitive state snapshot |

## Related Files (in `services/cognitive-sensor/`)

| File | Description |
|------|-------------|
| `BOOK_OUTLINE.md` | Full 12-chapter outline with passage counts |
| `book_raw_material.json` | 2,070 extracted passages from 494 conversations |
| `agent_book_miner.py` | Mining pipeline (semantic similarity + keyword detection) |

## Generate PDF

```bash
pip install fpdf2
python build_pdf.py
```

Outputs `Chapter_01_The_Anatomy_of_Disrespect.pdf` with headers, footers, section formatting, and Unicode handling.

## Book Outline (12 Chapters)

| # | Chapter | Passages | Sources |
|---|---------|----------|---------|
| 1 | The Anatomy of Disrespect | 614 | 208 convos |
| 2 | Confidence as a Weapon | 266 | 151 convos |
| 3 | Reading People Like Code | 208 | 139 convos |
| 4 | Boundaries as Power | 166 | 111 convos |
| 5 | Control Games People Play | 157 | 110 convos |
| 6 | When Your Presence Threatens People | 134 | 94 convos |
| 7 | The Validation Trap | 108 | 71 convos |
| 8 | Workplace Power Dynamics | 101 | 66 convos |
| 9 | Deprogramming: Seeing the Game | 101 | 69 convos |
| 10 | The Power of Walking Away | 77 | 59 convos |
| 11 | Family as the First Power Structure | 74 | 57 convos |
| 12 | The Hierarchy Nobody Talks About | 64 | 41 convos |

## Pipeline (to mine more chapters)

```bash
cd services/cognitive-sensor
python agent_book_miner.py
# Outputs: book_raw_material.json, BOOK_OUTLINE.md
```

Then manually edit raw material into polished prose, save as `data/chapter_XX_final.md`, and run `python build_pdf.py`.

## Part of Pre Atlas

Lives at `data/` in the Pre Atlas monorepo. PDF generation is fully self-contained (only needs `fpdf2`). Book mining depends on `cognitive-sensor` for embeddings and conversation data.
