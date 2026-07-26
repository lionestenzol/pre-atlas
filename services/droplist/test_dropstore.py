"""DropStore seam acceptance: backend selection + JSONL round-trip + dedup.

Proves the storage-adapter seam works and that the multi-device swap is a
one-flag change:
  - default backend is JsonlDropStore
  - append persists; read_all reads back
  - insert_if_new stores a new hash (True) and rejects a duplicate (False)
  - DROPLIST_STORE=jsonl selects JSONL explicitly
  - DROPLIST_STORE=supabase raises NotImplementedError (flag wired, backend TBD)
  - DROPLIST_STORE=<unknown> raises ValueError

Run from the droplist service root:

    python test_dropstore.py
"""

from __future__ import annotations

import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="dropstore_")
os.environ["DROPLIST_DATA"] = _TMP
os.environ.pop("DROPLIST_STORE", None)

from droplist import dropstore  # noqa: E402


def run() -> int:
    rows: list[tuple[str, bool]] = []

    def chk(label: str, ok: bool) -> None:
        rows.append((label, ok))

    # 1) default backend
    os.environ.pop("DROPLIST_STORE", None)
    s = dropstore.get_store()
    chk("default backend is JsonlDropStore", type(s).__name__ == "JsonlDropStore")

    # 2) append + read_all
    s.append({"drop_id": "d1", "input_hash": "h1", "raw_input": "alpha"})
    chk("append persists + read_all reads back", len(s.read_all()) == 1)

    # 3) insert_if_new for a NEW hash -> True, stored
    new = s.insert_if_new({"drop_id": "d2", "input_hash": "h2"})
    chk("insert_if_new(new) -> True + stored", new is True and len(s.read_all()) == 2)

    # 4) insert_if_new for a DUPLICATE hash -> False, not stored
    dup = s.insert_if_new({"drop_id": "d3", "input_hash": "h2"})
    chk("insert_if_new(dup) -> False + not stored", dup is False and len(s.read_all()) == 2)

    # 5) explicit jsonl
    os.environ["DROPLIST_STORE"] = "jsonl"
    chk("DROPLIST_STORE=jsonl selects JSONL", type(dropstore.get_store()).__name__ == "JsonlDropStore")

    # 6) supabase -> NotImplementedError (the flag is wired; backend is the only gap)
    os.environ["DROPLIST_STORE"] = "supabase"
    try:
        dropstore.get_store()
        ni = False
    except NotImplementedError:
        ni = True
    chk("DROPLIST_STORE=supabase raises NotImplementedError", ni)

    # 7) unknown backend -> ValueError (fail loud, not silent)
    os.environ["DROPLIST_STORE"] = "bogus"
    try:
        dropstore.get_store()
        ve = False
    except ValueError:
        ve = True
    chk("unknown backend raises ValueError", ve)
    os.environ.pop("DROPLIST_STORE", None)

    lbl_w = max(len("check"), max(len(r[0]) for r in rows))
    print(f"  {'check':<{lbl_w}}  result")
    print(f"  {'-'*lbl_w}  ------")
    for label, ok in rows:
        print(f"  {label:<{lbl_w}}  {'PASS' if ok else 'FAIL'}")
    all_pass = all(ok for _, ok in rows)
    print()
    print("DROPSTORE GATE: PASS" if all_pass else "DROPSTORE GATE: FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    try:
        code = run()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    raise SystemExit(code)
