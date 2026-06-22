"""File Ops DAG, executed against a real folder. Metadata only.

This is the `inventory_metadata` -> `cluster_inventory` portion of file_ops_dag
run for real, by `script`. Hard rule from the spec: do NOT open file contents.
We read names, sizes, mtimes, extensions, parent dirs — never bytes. Optional
--hash reads bytes to confirm duplicates and is OFF by default.

Output: a metadata inventory JSONL under data/memory_index/, plus a Work Packet
whose next_action is the next DAG node (cluster review), with deep reads blocked.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid

from . import dropstore, storage
from .schema import WorkPacket


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def _quick_hash(path: str, cap: int = 65536) -> str | None:
    """Hash first+last cap bytes + size. Reads bytes, so opt-in only."""
    try:
        size = os.path.getsize(path)
        h = hashlib.sha256()
        h.update(str(size).encode())
        with open(path, "rb") as f:
            h.update(f.read(cap))
            if size > cap * 2:
                f.seek(-cap, os.SEEK_END)
                h.update(f.read(cap))
        return h.hexdigest()[:16]
    except OSError:
        return None


def scan(folder: str, do_hash: bool = False) -> dict:
    """Collect metadata for every file under folder. Never reads contents
    unless do_hash is True (and even then only a capped sample)."""
    folder = os.path.expanduser(folder)
    entries: list[dict] = []
    by_ext: dict[str, int] = {}
    by_dir: dict[str, int] = {}
    size_by_ext: dict[str, int] = {}
    total_size = 0
    errors = 0

    for root, _dirs, files in os.walk(folder):
        for name in files:
            full = os.path.join(root, name)
            try:
                st = os.stat(full)
            except OSError:
                errors += 1
                continue
            ext = os.path.splitext(name)[1].lower() or "(none)"
            rel_dir = os.path.relpath(root, folder)
            rec = {
                "path": os.path.relpath(full, folder),
                "size": st.st_size,
                "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime)),
                "ext": ext,
            }
            if do_hash:
                rec["hash"] = _quick_hash(full)
            entries.append(rec)
            by_ext[ext] = by_ext.get(ext, 0) + 1
            by_dir[rel_dir] = by_dir.get(rel_dir, 0) + 1
            size_by_ext[ext] = size_by_ext.get(ext, 0) + st.st_size
            total_size += st.st_size

    # duplicate candidates: same (size, name) — cheap, no byte reads;
    # if hashed, narrow to identical short-hash.
    seen: dict[tuple, list[str]] = {}
    for e in entries:
        key = (e["size"], os.path.basename(e["path"]))
        if do_hash and e.get("hash"):
            key = (e["size"], e["hash"])
        seen.setdefault(key, []).append(e["path"])
    dup_groups = {str(k): v for k, v in seen.items() if len(v) > 1}

    return {
        "folder": folder,
        "file_count": len(entries),
        "total_size": total_size,
        "total_size_h": _human(total_size),
        "errors": errors,
        "by_ext": dict(sorted(by_ext.items(), key=lambda x: -x[1])),
        "size_by_ext": {k: _human(v) for k, v in sorted(size_by_ext.items(), key=lambda x: -x[1])},
        "by_dir": dict(sorted(by_dir.items(), key=lambda x: -x[1])[:15]),
        "duplicate_candidate_groups": len(dup_groups),
        "duplicates": dict(list(dup_groups.items())[:20]),
        "entries": entries,
        "hashed": do_hash,
    }


def run_inventory(folder: str, do_hash: bool = False) -> tuple[dict, WorkPacket, str]:
    """Scan, persist inventory, and emit a Work Packet for the file_ops DAG."""
    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        raise NotADirectoryError(folder)

    report = scan(folder, do_hash=do_hash)

    storage.ensure_data_dir()
    inv_name = f"inventory_{uuid.uuid4().hex[:8]}.jsonl"
    inv_path = os.path.join(storage.DATA_DIR, "memory_index", inv_name)
    with open(inv_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({k: v for k, v in report.items() if k != "entries"}, ensure_ascii=False) + "\n")
        for e in report["entries"]:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # next concrete step in the DAG: review the largest / duplicate clusters
    dup = report["duplicate_candidate_groups"]
    next_action = (
        f"review {dup} duplicate-candidate group(s) and the largest extension clusters; "
        "pick clusters to deep-read"
    )

    packet = WorkPacket(
        drop_id="drop_" + uuid.uuid4().hex[:12],
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        raw_input=f"inventory {folder}",
        normalized_input=f"metadata inventory of {folder} "
                         f"({report['file_count']} files, {report['total_size_h']})",
        input_hash=hashlib.sha256(inv_path.encode()).hexdigest(),
        type="asset",
        domain="file_ops",
        entities=[folder],
        retrieved_context=[],
        selected_workflow="file_ops_dag",
        current_node="cluster_inventory",
        next_node="select_priority_clusters",
        assigned_to="script",
        next_action=next_action,
        stop_condition="priority clusters chosen; nothing moved, deleted, or fully read",
        allowed_actions=["cluster_by_metadata", "rank_by_size", "flag_duplicates", "select_clusters"],
        blocked_actions=["delete_files", "move_files", "deep_read_all_files",
                         "dispatch_automatically", "execute_without_approval"],
        confidence=0.95,
        needs_human_decision=dup > 0,
        memory_update=f"file_ops: inventoried {folder} -> {inv_path} "
                      f"({report['file_count']} files, {dup} dup groups)",
        status="routed",
    )
    dropstore.get_store().append(packet.to_dict())
    return report, packet, inv_path
