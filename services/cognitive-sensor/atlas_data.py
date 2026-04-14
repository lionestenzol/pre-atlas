"""
atlas_data.py -- Load message embeddings from results.db for atlas construction.

Reads the message_embeddings table (384-dim float32 vectors) along with
conversation metadata (titles, dates, roles).
"""
import sqlite3
import numpy as np
from pathlib import Path

BASE = Path(__file__).parent.resolve()
DB_FILE = BASE / "results.db"


def load_message_data(db_path=None):
    """
    Load message embeddings and metadata from results.db.

    Args:
        db_path: Optional Path to override the default DB_FILE.
                 Used for testing with synthetic databases.

    Returns:
        dict with keys:
            msg_ids: list[str]
            convo_ids: list[str]
            msg_indices: list[int]
            roles: list[str]
            matrix: np.ndarray of shape (N, 384), dtype float32
            text_lengths: list[int]
            word_counts: list[int]
            titles: list[str]
            dates: list[str]

    Raises:
        SystemExit: if no embeddings found in DB.
    """
    path = db_path or DB_FILE
    con = sqlite3.connect(str(path))
    cur = con.cursor()

    count = cur.execute("SELECT COUNT(*) FROM message_embeddings").fetchone()[0]
    if count == 0:
        print("ERROR: No message embeddings found. Run: python init_message_embeddings.py")
        exit(1)

    rows = cur.execute("""
        SELECT me.msg_id, me.convo_id, me.msg_index, me.role, me.embedding,
               me.text_length, me.word_count, ct.title, c.date
        FROM message_embeddings me
        LEFT JOIN convo_titles ct ON me.convo_id = ct.convo_id
        LEFT JOIN convo_time c ON me.convo_id = c.convo_id
        ORDER BY CAST(me.convo_id AS INTEGER), me.msg_index
    """).fetchall()

    msg_ids, convo_ids, msg_indices, roles = [], [], [], []
    embeddings_list, text_lengths, word_counts = [], [], []
    titles, dates = [], []

    for mid, cid, midx, role, emb_blob, tlen, wc, title, date in rows:
        msg_ids.append(mid)
        convo_ids.append(cid)
        msg_indices.append(midx)
        roles.append(role)
        embeddings_list.append(np.frombuffer(emb_blob, dtype=np.float32))
        text_lengths.append(tlen)
        word_counts.append(wc)
        titles.append(title if title else "(untitled)")
        dates.append(date if date else "")

    con.close()

    return {
        "msg_ids": msg_ids,
        "convo_ids": convo_ids,
        "msg_indices": msg_indices,
        "roles": roles,
        "matrix": np.array(embeddings_list),
        "text_lengths": text_lengths,
        "word_counts": word_counts,
        "titles": titles,
        "dates": dates,
    }
