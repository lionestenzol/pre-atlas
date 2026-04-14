"""Extract top 20 passages per chapter from book_raw_material.json."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(os.path.dirname(BASE), "services", "cognitive-sensor", "book_raw_material.json")
OUTDIR = BASE

with open(RAW, "r", encoding="utf-8") as f:
    data = json.load(f)

chapters = data["chapters"]
chapter_num = 0

for ch in chapters:
    chapter_num += 1
    outpath = os.path.join(OUTDIR, f"ch{chapter_num}_top20_passages.json")

    # Skip chapter 1 — already exists
    if chapter_num == 1 and os.path.exists(outpath):
        print(f"  ch{chapter_num} already exists, skipping")
        continue

    passages = ch.get("passages", [])

    # Sort by relevance if available, otherwise take first 20
    sorted_passages = sorted(
        passages,
        key=lambda p: p.get("relevance_score", p.get("avg_relevance", 0)),
        reverse=True
    )[:20]

    output = {
        "chapter": ch["chapter_title"],
        "top_quotes": ch.get("top_quotes", [])[:10],
        "passages": [
            {
                "rank": i + 1,
                "convo_title": p.get("convo_title", ""),
                "convo_date": p.get("convo_date", ""),
                "relevance_score": p.get("relevance_score", p.get("avg_relevance", 0)),
                "passage": p.get("passage", ""),
                "best_sentences": p.get("best_sentences", [])
            }
            for i, p in enumerate(sorted_passages)
        ]
    }

    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ch{chapter_num}: {len(output['passages'])} passages -> {outpath}")

print("Done.")
