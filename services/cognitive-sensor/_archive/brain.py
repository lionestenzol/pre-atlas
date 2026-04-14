import os, json, re, sys
from collections import Counter
from pathlib import Path

# Base directory is the same folder as this script
BASE = Path(__file__).parent.resolve()

# RAW_JSON: Set via environment variable or place conversations.json in this folder
RAW_JSON = Path(os.environ.get("CONVERSATIONS_JSON", BASE / "conversations.json"))

# Memory database lives in the same folder as this script
DB = BASE / "memory_db.json"


def load_db():
    if DB.exists():
        return json.load(open(DB, encoding="utf-8"))
    return []


def save_db(db):
    json.dump(db, open(DB, "w", encoding="utf-8"), indent=2)


def build_db():
    print("Building memory database...")
    data = json.load(open(RAW_JSON, encoding="utf-8"))
    db = []

    for conv in data:
        title = conv.get("title", "Untitled")
        messages = []
        for m in conv.get("mapping", {}).values():
            msg = m.get("message")
            if msg and msg.get("content"):
                parts = msg["content"].get("parts")
                if parts:
                    messages.append({"role": msg["author"]["role"], "text": parts[0]})

        if messages:
            db.append({"title": title, "messages": messages})

    save_db(db)
    print(f"Indexed {len(db)} conversations.")


def search_db():
    q = input("Search keyword: ").lower()
    db = load_db()
    for c in db:
        if q in json.dumps(c).lower():
            print("—", c["title"])


def find_unfinished():
    db = load_db()
    for c in db:
        for m in c["messages"]:
            if re.search(r"\bi (need|should|want to)\b", m["text"].lower()):
                print("—", c["title"], "→", m["text"])


def main():
    while True:
        print("\nMY WORKSPACE")
        print("1) Build memory database")
        print("2) Search my conversations")
        print("3) Find unfinished goals")
        print("4) Exit")
        choice = input("> ").strip()

        if choice == "1": build_db()
        elif choice == "2": search_db()
        elif choice == "3": find_unfinished()
        elif choice == "4": sys.exit()
        else: print("Invalid.")


if __name__ == "__main__":
    main()
